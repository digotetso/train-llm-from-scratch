import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

type FileRecord = { contents: string; exists: boolean; length?: number };

class FolderItemMock {
  name: string;
  parentFolder: unknown = null;
  removed = false;
  readonly removalLog: string[];

  constructor(name: string, removalLog: string[] = []) {
    this.name = name;
    this.removalLog = removalLog;
  }

  remove(): void {
    this.removed = true;
    this.removalLog.push(this.name);
  }
}

class CompItemMock extends FolderItemMock {}
class FootageItemMock extends FolderItemMock {}

function instrumentImporter(source: string): string {
  const marker = "    return {\n        importPackage: importPackage,";
  const index = source.indexOf(marker);
  assert.notEqual(index, -1, "importer return marker must remain discoverable");
  return source.slice(0, index) + `    return {
        importPackage: importPackage,
        importPackageFile: importPackageFile,
        loadTiming: loadTiming,
        readUtf8: readUtf8,
        writeUtf8: writeUtf8,
        __test: {
            rememberItem: rememberItem,
            rollbackItems: rollbackItems,
            addRunAnimator: addRunAnimator,
            setLayerGeometry: setLayerGeometry,
            isQueuedPackageFile: isQueuedPackageFile,
            parseJson: function (value) { return JSON.parse(value); }
        }
    };
}(Video001ExporterCore));\n`;
}

function makeImporterHarness(forcedSystemHash?: string) {
  const sourceUrl = new URL("../src/ae/importer.jsxinc", import.meta.url);
  const source = instrumentImporter(readFileSync(sourceUrl, "utf8"));
  const records = new Map<string, FileRecord>();
  const projectItems: FolderItemMock[] = [];
  const removalLog: string[] = [];
  const systemCommands: string[] = [];
  let beginUndoCount = 0;

  function parentPath(path: string): string {
    const slash = path.lastIndexOf("/");
    return slash <= 0 ? "/" : path.slice(0, slash);
  }

  class FolderMock {
    static userData = new FolderMock("/user-data");
    static temp = new FolderMock("/tmp");
    readonly fsName: string;
    readonly name: string;

    constructor(path: string) {
      this.fsName = path.replace(/\/$/, "") || "/";
      this.name = this.fsName.slice(this.fsName.lastIndexOf("/") + 1);
    }

    get parent(): FolderMock {
      return new FolderMock(parentPath(this.fsName));
    }

    get exists(): boolean {
      return records.get(this.fsName)?.exists ?? true;
    }

    create(): boolean {
      records.set(this.fsName, { contents: "", exists: true });
      return true;
    }

    getFiles(): unknown[] {
      return [];
    }
  }

  class FileMock {
    static encoding = "UTF-8";
    readonly fsName: string;
    readonly name: string;
    encoding = "UTF-8";
    private mode = "";

    constructor(path: string) {
      this.fsName = path;
      this.name = path.slice(path.lastIndexOf("/") + 1);
    }

    get parent(): FolderMock {
      return new FolderMock(parentPath(this.fsName));
    }

    get exists(): boolean {
      return records.get(this.fsName)?.exists ?? false;
    }

    get length(): number {
      const record = records.get(this.fsName);
      return record?.length ?? Buffer.byteLength(record?.contents ?? "", "utf8");
    }

    open(mode: string): boolean {
      this.mode = mode;
      if (mode === "r") return this.exists;
      records.set(this.fsName, { contents: "", exists: true });
      return true;
    }

    read(): string {
      return records.get(this.fsName)?.contents ?? "";
    }

    write(value: string): boolean {
      assert.equal(this.mode, "w");
      records.set(this.fsName, { contents: value, exists: true });
      return true;
    }

    close(): void {}

    remove(): boolean {
      const record = records.get(this.fsName);
      if (record === undefined) return false;
      record.exists = false;
      return true;
    }

    rename(name: string): boolean {
      const record = records.get(this.fsName);
      if (record === undefined) return false;
      records.set(parentPath(this.fsName) + "/" + name, record);
      record.exists = false;
      return true;
    }
  }

  const rootFolder = new FolderItemMock("Root", removalLog);
  const project = {
    rootFolder,
    get numItems(): number {
      return projectItems.filter((item) => !item.removed).length;
    },
    item(index: number): FolderItemMock {
      return projectItems.filter((item) => !item.removed)[index - 1]!;
    },
    items: {
      addFolder(name: string): FolderItemMock {
        const item = new FolderItemMock(name, removalLog);
        item.parentFolder = rootFolder;
        projectItems.push(item);
        return item;
      },
      addComp(name: string): CompItemMock {
        const item = new CompItemMock(name, removalLog);
        projectItems.push(item);
        return item;
      }
    },
    importFile(): FootageItemMock {
      const item = new FootageItemMock("footage", removalLog);
      projectItems.push(item);
      return item;
    }
  };

  const context: Record<string, unknown> = {
    File: FileMock,
    Folder: FolderMock,
    FolderItem: FolderItemMock,
    CompItem: CompItemMock,
    FootageItem: FootageItemMock,
    ImportOptions: class ImportOptionsMock {},
    ParagraphJustification: {
      CENTER_JUSTIFY: 1,
      RIGHT_JUSTIFY: 2,
      LEFT_JUSTIFY: 3
    },
    Video001ExporterCore: {
      scaleRect(rect: { x: number; y: number; width: number; height: number }) {
        return { ...rect };
      },
      sanitizeAeName(name: string) {
        return name;
      },
      nextVersionName(_names: string[], name: string) {
        return name + "_v001";
      },
      isDuplicateHash() {
        return false;
      },
      makeImportReport(value: unknown) {
        return value;
      }
    },
    app: {
      project,
      beginUndoGroup() {
        beginUndoCount += 1;
      },
      endUndoGroup() {}
    },
    system: {
      callSystem(command: string) {
        systemCommands.push(command);
        if (command.startsWith("/usr/bin/shasum -a 256 ")) {
          if (forcedSystemHash !== undefined) return forcedSystemHash + "  file\n";
          const path = /'([^']+)'/.exec(command)?.[1];
          assert.ok(path, "mock shasum command must contain one quoted file path");
          const contents = records.get(path)?.contents;
          assert.notEqual(contents, undefined, "mock shasum input must exist");
          return createHash("sha256").update(contents!, "utf8").digest("hex") + "  file\n";
        }
        return "";
      }
    }
  };

  vm.runInNewContext(source, context, { filename: sourceUrl.pathname });
  const importer = context.Video001ExporterImporter as {
    importPackage(value: unknown, options: Record<string, unknown>, untrustedBypass?: boolean): unknown;
    importPackageFile(file: InstanceType<typeof FileMock>, options: Record<string, unknown>): unknown;
    __test: {
      rememberItem(items: FolderItemMock[], item: FolderItemMock): FolderItemMock;
      rollbackItems(items: FolderItemMock[]): void;
      addRunAnimator(layer: unknown, run: { start: number; end: number; color: string; fontSize: number }, dominant: { fontSize: number }, scaleY: number): void;
      setLayerGeometry(layer: unknown, rect: { x: number; y: number; width: number; height: number }, rotation: number, opacity: number, boxTextPos?: number[]): void;
      parseJson(value: string): unknown;
    };
  };

  function put(path: string, value: unknown, length?: number): InstanceType<typeof FileMock> {
    const record: FileRecord = {
      contents: typeof value === "string" ? value : JSON.stringify(value),
      exists: true
    };
    if (length !== undefined) record.length = length;
    records.set(path, record);
    return new FileMock(path);
  }

  const timingFile = put("/timing/figma-scenes.json", {
    canvas: { width: 1920, height: 1080, fps: 30, duration: 840 },
    source: { figmaFileKey: "file-key", figmaPageNodeId: "page-id" },
    shots: [{ figmaNodeId: "1:1", name: "Shot", duration: 30 }]
  });
  const queueRoot = new FolderMock("/queue");
  const assetRoot = new FolderMock("/queue/assets");
  const reportFolder = new FolderMock("/queue");

  function validPackage() {
    return {
      schemaVersion: "1.0.0",
      exporterVersion: "0.1.0",
      exportedAt: "2026-07-22T00:00:00.000Z",
      contentHash: "a".repeat(64),
      source: { fileKey: "file-key", pageId: "page-id" },
      target: { width: 1920, height: 1080, fps: 30 },
      frames: [{
        nodeId: "1:1",
        name: "Shot",
        width: 1920,
        height: 1080,
        duration: 30,
        children: [{
          id: "shape",
          name: "Shape",
          kind: "rect",
          x: 0,
          y: 0,
          width: 100,
          height: 100,
          rotation: 0,
          opacity: 1,
          fill: "#000000",
          stroke: null,
          strokeWidth: 0,
          radius: 0
        }],
        warnings: []
      }],
      assets: []
    };
  }

  function options(removeAfterReport: boolean) {
    return {
      allowDuplicate: false,
      removeAfterReport,
      queueRoot,
      assetRoot,
      reportFolder,
      timingFile
    };
  }

  return {
    importer,
    put,
    validPackage,
    options,
    records,
    removalLog,
    systemCommands,
    get beginUndoCount() {
      return beginUndoCount;
    }
  };
}

function transformRecorder() {
  const values = new Map<string, unknown>();
  const transform = {
    property(name: string) {
      return {
        setValue(value: unknown) {
          values.set(name, value);
        }
      };
    }
  };
  return {
    layer: {
      property(name: string) {
        assert.equal(name, "ADBE Transform Group");
        return transform;
      }
    },
    values
  };
}

test("transaction tracking accepts concrete AE items and rolls back only new identities in reverse", () => {
  const harness = makeImporterHarness();
  const preexisting = new FolderItemMock("preexisting", harness.removalLog);
  const transactionItems: FolderItemMock[] = [];
  const created = [
    new FolderItemMock("folder", harness.removalLog),
    new CompItemMock("comp", harness.removalLog),
    new FootageItemMock("footage", harness.removalLog)
  ];

  assert.throws(() => {
    for (const item of created) harness.importer.__test.rememberItem(transactionItems, item);
    throw new Error("later layer failure");
  }, /later layer failure/);
  harness.importer.__test.rollbackItems(transactionItems);

  assert.equal(preexisting.removed, false);
  assert.deepEqual(harness.removalLog, ["footage", "comp", "folder"]);
  assert.ok(created.every((item) => item.removed));
});

test("mixed text runs use Advanced index units and exact index bounds", () => {
  const harness = makeImporterHarness();
  const values = new Map<string, unknown>();
  const property = (name: string) => ({ setValue: (value: unknown) => values.set(name, value) });
  const advanced = { property: (name: string) => name === "ADBE Text Range Units" ? property(name) : null };
  const selector = {
    property(name: string) {
      if (name === "ADBE Text Range Advanced") return advanced;
      if (name === "ADBE Text Index Start" || name === "ADBE Text Index End") return property(name);
      return null;
    }
  };
  const animatorProperties = { addProperty: (name: string) => property(name) };
  const animator = {
    name: "",
    property(name: string) {
      if (name === "ADBE Text Animator Properties") return animatorProperties;
      if (name === "ADBE Text Selectors") return { addProperty: () => selector };
      return null;
    }
  };
  const layer = {
    property() {
      return { property: () => ({ addProperty: () => animator }) };
    }
  };

  harness.importer.__test.addRunAnimator(
    layer,
    { start: 3, end: 7, color: "#112233", fontSize: 16 },
    { fontSize: 16 },
    1
  );

  assert.equal(values.get("ADBE Text Range Units"), 2);
  assert.equal(values.get("ADBE Text Index Start"), 3);
  assert.equal(values.get("ADBE Text Index End"), 7);
});

test("paragraph geometry anchors the actual box origin for unrotated text", () => {
  const harness = makeImporterHarness();
  const recorder = transformRecorder();
  harness.importer.__test.setLayerGeometry(
    recorder.layer,
    { x: 100, y: 200, width: 80, height: 40 },
    0,
    1,
    [-7, -23]
  );
  assert.deepEqual(Array.from(recorder.values.get("ADBE Anchor Point") as number[]), [33, -3]);
  assert.deepEqual(Array.from(recorder.values.get("ADBE Position") as number[]), [140, 220]);
});

test("paragraph geometry preserves the box origin through rotation", () => {
  const harness = makeImporterHarness();
  const recorder = transformRecorder();
  harness.importer.__test.setLayerGeometry(
    recorder.layer,
    { x: 100, y: 200, width: 80, height: 40 },
    90,
    1,
    [-7, -23]
  );
  const anchor = recorder.values.get("ADBE Anchor Point") as number[];
  const position = recorder.values.get("ADBE Position") as number[];
  const delta = [-7 - anchor[0]!, -23 - anchor[1]!];
  const transformedOrigin = [position[0]! - delta[1]!, position[1]! + delta[0]!];
  assert.deepEqual(Array.from(anchor), [33, -3]);
  assert.ok(Math.abs(transformedOrigin[0]! - 100) < 1e-9);
  assert.ok(Math.abs(transformedOrigin[1]! - 200) < 1e-9);
});

test("queue filename and direct-parent identity fail before AE mutation", () => {
  for (const path of [
    "/queue/incoming/" + "b".repeat(64) + ".video001-ae.json",
    "/queue/incoming/nested/" + "a".repeat(64) + ".video001-ae.json"
  ]) {
    const harness = makeImporterHarness();
    const packageFile = harness.put(path, harness.validPackage());
    assert.throws(
      () => harness.importer.importPackageFile(packageFile, harness.options(true)),
      /queue package.*identity|direct.*incoming|filename.*content hash/i
    );
    assert.equal(harness.beginUndoCount, 0);
  }
});

test("every declared asset is verified before AE mutation even when unreferenced", () => {
  const harness = makeImporterHarness();
  const value = harness.validPackage();
  value.assets.push({
    hash: "b".repeat(64),
    mimeType: "image/png",
    byteLength: 1,
    path: "/outside/unverified.png"
  } as never);
  const packageFile = harness.put(
    "/queue/incoming/" + value.contentHash + ".video001-ae.json",
    value
  );
  assert.throws(
    () => harness.importer.importPackageFile(packageFile, harness.options(true)),
    /raster fallback path|verifiable/i
  );
  assert.equal(harness.beginUndoCount, 0);
});

test("manual packages with an unverifiable content fingerprint fail before AE mutation", () => {
  const harness = makeImporterHarness("c".repeat(64));
  const value = harness.validPackage();
  const packageFile = harness.put("/manual/package.video001-ae.json", value);
  assert.throws(
    () => harness.importer.importPackageFile(packageFile, harness.options(false)),
    /content fingerprint|content hash/i
  );
  assert.equal(harness.beginUndoCount, 0);
});

test("the public package API cannot bypass manual fingerprint verification", () => {
  const harness = makeImporterHarness("c".repeat(64));
  const packageValue = harness.importer.__test.parseJson(JSON.stringify(harness.validPackage()));
  assert.throws(
    () => harness.importer.importPackage(packageValue, harness.options(false), true),
    /content fingerprint|content hash/i
  );
  assert.equal(harness.beginUndoCount, 0);
});

test("manual packages use the shared canonical content fingerprint before import", () => {
  const harness = makeImporterHarness();
  const value = harness.validPackage();
  const fingerprintValue = { ...value, exportedAt: "", contentHash: "" };
  const canonical = (input: unknown): string => {
    if (input === null || typeof input !== "object") return JSON.stringify(input);
    if (Array.isArray(input)) return "[" + input.map(canonical).join(",") + "]";
    const record = input as Record<string, unknown>;
    return "{" + Object.keys(record).sort().map((key) => JSON.stringify(key) + ":" + canonical(record[key])).join(",") + "}";
  };
  value.contentHash = createHash("sha256").update(canonical(fingerprintValue), "utf8").digest("hex");
  const packageFile = harness.put("/manual/package.video001-ae.json", value);
  let error: unknown;
  try {
    harness.importer.importPackageFile(packageFile, harness.options(false));
  } catch (caught) {
    error = caught;
  }
  assert.equal(typeof (error as { message?: unknown } | undefined)?.message, "string", "the intentionally partial AE layer mock must fail after preflight");
  assert.doesNotMatch((error as { message: string }).message, /content fingerprint|content hash/i);
  assert.equal(harness.beginUndoCount, 1);
  assert.ok(harness.systemCommands.some((command) => command.startsWith("/bin/chmod 600 ")));
});

type PanelHarnessOptions = { stateCommand: string; stateExists?: boolean };

function instrumentPanel(source: string): string {
  const marker = "    palette = buildPalette();";
  const index = source.indexOf(marker);
  assert.notEqual(index, -1, "panel boot marker must remain discoverable");
  return source.slice(0, index) + `    return {
        poll: poll,
        startBridge: startBridge,
        stopBridge: stopBridge,
        resetPairing: resetPairing,
        importNext: importNext,
        buildPalette: buildPalette
    };
}(this, Video001ExporterImporter));\n`;
}

function makePanelHarness({ stateCommand, stateExists = true }: PanelHarnessOptions) {
  const sourceUrl = new URL("../src/ae/panel.jsx", import.meta.url);
  const source = instrumentPanel(readFileSync(sourceUrl, "utf8"));
  const statePath = "/user-data/Video001FigmaAEExporter/state.json";
  const bridgePath = "/bundle/bridge/video001-bridge.mjs";
  const existing = new Set<string>([bridgePath, "/usr/local/bin/node"]);
  if (stateExists) existing.add(statePath);
  const commands: string[] = [];

  function parentPath(path: string): string {
    const slash = path.lastIndexOf("/");
    return slash <= 0 ? "/" : path.slice(0, slash);
  }

  class FolderMock {
    static userData = new FolderMock("/user-data");
    readonly fsName: string;
    constructor(path: string) { this.fsName = path; }
    get parent(): FolderMock { return new FolderMock(parentPath(this.fsName)); }
    get exists(): boolean { return existing.has(this.fsName); }
    create(): boolean { existing.add(this.fsName); return true; }
    getFiles(): unknown[] { return []; }
  }

  class FileMock {
    readonly fsName: string;
    readonly name: string;
    constructor(path: string) { this.fsName = path; this.name = path.slice(path.lastIndexOf("/") + 1); }
    get parent(): FolderMock { return new FolderMock(parentPath(this.fsName)); }
    get exists(): boolean { return existing.has(this.fsName); }
    remove(): boolean { return existing.delete(this.fsName); }
    static openDialog(): null { return null; }
  }

  const context: Record<string, unknown> = {
    $: { fileName: "/bundle/ae/Video001-Figma-AE-Exporter.jsx" },
    File: FileMock,
    Folder: FolderMock,
    Panel: class PanelMock {},
    Window: class WindowMock {},
    Video001ExporterImporter: {
      readUtf8(file: InstanceType<typeof FileMock>) {
        assert.equal(file.fsName, statePath);
        return JSON.stringify({
          pid: 4242,
          port: 3456,
          pairingCode: "123456",
          pairingExpiresAt: 2_000_000_000_000
        });
      }
    },
    system: {
      callSystem(command: string) {
        commands.push(command);
        if (command === "/usr/bin/which node") return "/usr/local/bin/node\n";
        if (command.startsWith("/bin/ps -p 4242")) return stateCommand;
        return "";
      }
    },
    app: { cancelTask() {}, scheduleTask() { return 1; } }
  };
  vm.runInNewContext(source, context, { filename: sourceUrl.pathname });
  return {
    panel: context.Video001ExporterPanel as {
      startBridge(): void;
      stopBridge(silent: boolean): void;
    },
    commands,
    existing,
    statePath
  };
}

test("Start recovers a structurally valid stale state for a nonexistent PID", () => {
  const harness = makePanelHarness({ stateCommand: "" });
  harness.panel.startBridge();
  assert.equal(harness.existing.has(harness.statePath), false);
  assert.ok(harness.commands.some((command) => command.includes("video001-bridge.mjs") && command.includes(" --root ")));
  assert.ok(harness.commands.every((command) => !command.startsWith("/bin/kill")));
});

test("Stop recovers an unrelated reused PID without signaling it", () => {
  const harness = makePanelHarness({ stateCommand: "/usr/bin/python unrelated.py\n" });
  harness.panel.stopBridge(false);
  assert.equal(harness.existing.has(harness.statePath), false);
  assert.ok(harness.commands.every((command) => !command.startsWith("/bin/kill")));
});

class UiElementMock {
  text = "";
  active = false;
  characters = 0;
  preferredSize: { height?: number } | number[] = {};
  alignment: unknown;
  orientation = "";
  alignChildren: unknown;
  spacing = 0;
  margins = 0;
  onClick?: () => void;
  onClose?: () => boolean;
  onResize?: () => void;
  onResizing?: () => void;
  readonly layout = { layout() {}, resize() {} };
  add(type: string, _bounds?: unknown, text?: string): UiElementMock {
    const element = new UiElementMock();
    if (type === "statictext" || type === "edittext" || type === "button") element.text = text ?? "";
    return element;
  }
  center(): void {}
  show(): void {}
}

test("panel polls exactly once per second and cancels its task when closed", () => {
  const sourceUrl = new URL("../src/ae/panel.jsx", import.meta.url);
  const source = readFileSync(sourceUrl, "utf8");
  const scheduled: unknown[][] = [];
  const cancelled: number[] = [];
  let windowValue: UiElementMock | undefined;

  class FolderMock {
    static userData = new FolderMock("/user-data");
    readonly fsName: string;
    constructor(path: string) { this.fsName = path; }
    get parent(): FolderMock { return new FolderMock(this.fsName.slice(0, this.fsName.lastIndexOf("/")) || "/"); }
    get exists(): boolean { return false; }
    getFiles(): unknown[] { return []; }
  }
  class FileMock {
    readonly fsName: string;
    readonly name: string;
    constructor(path: string) { this.fsName = path; this.name = path.slice(path.lastIndexOf("/") + 1); }
    get parent(): FolderMock { return new FolderMock(this.fsName.slice(0, this.fsName.lastIndexOf("/")) || "/"); }
    get exists(): boolean { return false; }
    static openDialog(): null { return null; }
  }
  class WindowMock extends UiElementMock {
    constructor() { super(); windowValue = this; }
  }
  const context = {
    $: { fileName: "/bundle/ae/Video001-Figma-AE-Exporter.jsx" },
    File: FileMock,
    Folder: FolderMock,
    Panel: class PanelMock extends UiElementMock {},
    Window: WindowMock,
    Video001ExporterImporter: { readUtf8() { return ""; } },
    system: { callSystem() { return ""; } },
    app: {
      scheduleTask(...args: unknown[]) { scheduled.push(args); return 73; },
      cancelTask(id: number) { cancelled.push(id); }
    }
  };
  vm.runInNewContext(source, context, { filename: sourceUrl.pathname });
  assert.deepEqual(scheduled, [["Video001ExporterPanel.poll()", 1000, true]]);
  assert.ok(windowValue?.onClose);
  windowValue.onClose();
  assert.deepEqual(cancelled, [73]);
});

test("read-only audit keeps font substitutions and raster fallbacks disjoint", () => {
  const sourceUrl = new URL("../src/ae/audit-export.jsx", import.meta.url);
  const source = readFileSync(sourceUrl, "utf8");
  const hash = "a".repeat(64);
  const reportPath = "/user-data/Video001FigmaAEExporter/import-report-" + hash + ".json";
  let output = "";

  class FolderMock {
    static userData = new FolderMock("/user-data");
    readonly fsName: string;
    constructor(path: string) { this.fsName = path; }
  }
  class FileMock {
    static encoding = "UTF-8";
    readonly fsName: string;
    encoding = "UTF-8";
    constructor(path: string) { this.fsName = path; }
    get parent(): FolderMock { return new FolderMock(this.fsName.slice(0, this.fsName.lastIndexOf("/"))); }
    get exists(): boolean { return this.fsName === reportPath; }
    open(): boolean { return true; }
    read(): string {
      return JSON.stringify({
        missingFonts: ["Missing-Regular"],
        fallbacks: [
          { type: "font-substitution", property: "font", replacement: "Inter-Regular" },
          { type: "raster-fallback", property: "gradient", replacement: "PNG" }
        ],
        warnings: []
      });
    }
    write(value: string): boolean { output = value; return true; }
    close(): void {}
  }
  class CompItemMockLocal {
    name = "Shot_v001";
    width = 1920;
    height = 1080;
    frameRate = 30;
    duration = 1;
    numLayers = 0;
    comment = "Video001Export sha256:" + hash;
    layer(): never { throw new Error("no layers"); }
  }
  class EmptyClass {}
  const comp = new CompItemMockLocal();
  const project = {
    activeItem: comp,
    file: null,
    numItems: 1,
    items: { addComp(): never { throw new Error("audit mutated project"); } }
  };
  const context = {
    $: { fileName: "/bundle/ae/audit-export.jsx" },
    File: FileMock,
    Folder: FolderMock,
    CompItem: CompItemMockLocal,
    TextLayer: EmptyClass,
    ShapeLayer: EmptyClass,
    CameraLayer: EmptyClass,
    LightLayer: EmptyClass,
    AVLayer: EmptyClass,
    app: { project }
  };
  vm.runInNewContext(source, context, { filename: sourceUrl.pathname });
  assert.equal(project.numItems, 1);
  const audit = JSON.parse(output) as {
    missingFonts: string[];
    rasterFallbacks: Array<{ type: string; property: string }>;
  };
  assert.deepEqual(audit.missingFonts, ["Missing-Regular"]);
  assert.deepEqual(audit.rasterFallbacks, [{ type: "raster-fallback", property: "gradient", replacement: "PNG" }]);
});
