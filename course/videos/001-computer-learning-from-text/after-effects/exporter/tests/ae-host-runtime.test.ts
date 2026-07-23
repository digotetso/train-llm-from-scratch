import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

type FileRecord = { contents: string; exists: boolean; length?: number };
type CanonicalShot = {
  figmaNodeId: string;
  name: string;
  start: number;
  duration: number;
};
type CanonicalTiming = {
  canvas: { width: number; height: number; fps: number; timeUnit: string; duration: number };
  source: { figmaFileKey: string; figmaPageNodeId: string };
  shots: CanonicalShot[];
};
type ImporterHarnessBehavior = {
  failShapeLayerCreation?: boolean;
  failMasterCompCreation?: boolean;
  failMasterLayerAt?: number;
};

class FolderItemMock {
  name: string;
  comment = "";
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

class PropertyMock {
  numProperties = 0;

  property(_name: string | number): PropertyMock {
    return new PropertyMock();
  }

  addProperty(_name: string): PropertyMock {
    return new PropertyMock();
  }

  setValue(_value: unknown): void {}
}

class LayerMock {
  name = "";
  comment = "";
  startTime = 0;
  inPoint = 0;
  outPoint = 0;
  readonly source: CompItemMock | null;

  constructor(source: CompItemMock | null) {
    this.source = source;
  }

  property(_name: string): PropertyMock {
    return new PropertyMock();
  }
}

class CompItemMock extends FolderItemMock {
  width = 0;
  height = 0;
  duration = 0;
  frameRate = 0;
  private readonly timelineLayers: LayerMock[] = [];
  readonly layers: {
    add: (source: CompItemMock) => LayerMock;
    addShape: () => LayerMock;
  };

  constructor(
    name: string,
    removalLog: string[] = [],
    width = 0,
    height = 0,
    duration = 0,
    frameRate = 0,
    onAddSource?: () => void,
    onAddShape?: () => void
  ) {
    super(name, removalLog);
    this.width = width;
    this.height = height;
    this.duration = duration;
    this.frameRate = frameRate;
    this.layers = {
      add: (source: CompItemMock) => {
        if (onAddSource !== undefined) onAddSource();
        const layer = new LayerMock(source);
        this.timelineLayers.unshift(layer);
        return layer;
      },
      addShape: () => {
        if (onAddShape !== undefined) onAddShape();
        const layer = new LayerMock(null);
        this.timelineLayers.unshift(layer);
        return layer;
      }
    };
  }

  get numLayers(): number {
    return this.timelineLayers.length;
  }

  get layersInTimelineOrder(): LayerMock[] {
    return this.timelineLayers.slice();
  }

  layer(index: number): LayerMock {
    return this.timelineLayers[index - 1]!;
  }
}
class FootageItemMock extends FolderItemMock {}

function canonicalJson(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return "[" + value.map(canonicalJson).join(",") + "]";
  const record = value as Record<string, unknown>;
  return "{" + Object.keys(record).sort().map((key) => JSON.stringify(key) + ":" + canonicalJson(record[key])).join(",") + "}";
}

function stampCanonicalContentHash<T extends { exportedAt: string; contentHash: string }>(value: T): T {
  const fingerprintValue = { ...value, exportedAt: "", contentHash: "" };
  value.contentHash = createHash("sha256").update(canonicalJson(fingerprintValue), "utf8").digest("hex");
  return value;
}

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
            addText: addText,
            addRunAnimator: addRunAnimator,
            applyResolvedFont: applyResolvedFont,
            resolveRunFont: resolveRunFont,
            setLayerGeometry: setLayerGeometry,
            isQueuedPackageFile: isQueuedPackageFile,
            parseJson: function (value) { return JSON.parse(value); }
        }
    };
}(Video001ExporterCore));\n`;
}

function makeImporterHarness(
  forcedSystemHash?: string,
  duplicateHash = false,
  behavior: ImporterHarnessBehavior = {}
) {
  const sourceUrl = new URL("../src/ae/importer.jsxinc", import.meta.url);
  const source = instrumentImporter(readFileSync(sourceUrl, "utf8"));
  const records = new Map<string, FileRecord>();
  const projectItems: FolderItemMock[] = [];
  const removalLog: string[] = [];
  const systemCommands: string[] = [];
  const fontsByPostScriptName = new Map<string, Array<{ postScriptName: string; hasGlyphsFor(value: string): boolean }>>();
  let beginUndoCount = 0;
  let endUndoCount = 0;
  let masterLayerAddCount = 0;

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
  const preexisting = new FolderItemMock("preexisting", removalLog);
  preexisting.parentFolder = rootFolder;
  projectItems.push(preexisting);
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
      addComp(
        name: string,
        width: number,
        height: number,
        _pixelAspect: number,
        duration: number,
        frameRate: number
      ): CompItemMock {
        if (
          behavior.failMasterCompCreation &&
          name.indexOf("VIDEO001_MASTER_v") === 0
        ) {
          throw new Error("mock master comp creation failure");
        }
        const item = new CompItemMock(
          name,
          removalLog,
          width,
          height,
          duration,
          frameRate,
          name.indexOf("VIDEO001_MASTER_v") === 0
            ? () => {
                masterLayerAddCount += 1;
                if (masterLayerAddCount === behavior.failMasterLayerAt) {
                  throw new Error("mock master layer creation failure");
                }
              }
            : undefined,
          behavior.failShapeLayerCreation
            ? () => { throw new Error("mock shape layer creation failure"); }
            : undefined
        );
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
      isDuplicateHash(items: Array<{ comment?: string }>, contentHash: string) {
        return duplicateHash || items.some(
          (item) => item.comment === "Video001Export sha256:" + contentHash
        );
      },
      makeImportReport(value: unknown) {
        return value;
      }
    },
    app: {
      project,
      fonts: {
        getFontsByPostScriptName(postScriptName: string) {
          return fontsByPostScriptName.get(postScriptName) ?? [];
        }
      },
      beginUndoGroup() {
        beginUndoCount += 1;
      },
      endUndoGroup() {
        endUndoCount += 1;
      }
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
    loadTiming(file: InstanceType<typeof FileMock>): {
      shots: Array<{ index: number; nodeId: string; name: string; start: number; duration: number }>;
      shotsByNodeId: Record<string, { index: number; nodeId: string; name: string; start: number; duration: number }>;
    };
    __test: {
      rememberItem(items: FolderItemMock[], item: FolderItemMock): FolderItemMock;
      rollbackItems(items: FolderItemMock[]): void;
      addText(comp: unknown, node: unknown, context: unknown): unknown;
      addRunAnimator(layer: unknown, run: { start: number; end: number; color: string; fontSize: number }, dominant: { fontSize: number }, scaleY: number): void;
      applyResolvedFont(documentValue: { fontObject: unknown; fauxBold: boolean }, resolved: { fontObject: unknown; fauxBold: boolean }): void;
      resolveRunFont(run: { start: number; end: number; fontFamily: string; fontStyle: string }, node: { id: string; name: string; text: string }, state: { missingFonts: string[]; fallbacks: unknown[]; warnings: string[] }): { fontObject: unknown; postScriptName: string; fauxBold: boolean };
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
    canvas: { width: 1920, height: 1080, fps: 30, timeUnit: "seconds", duration: 840 },
    source: { figmaFileKey: "file-key", figmaPageNodeId: "page-id" },
    shots: [{ figmaNodeId: "1:1", name: "Shot", start: 0, duration: 30 }]
  });
  const trustedQueuePath = "/user-data/Video001FigmaAEExporter";
  const assetRoot = new FolderMock(trustedQueuePath + "/assets");
  const reportFolder = new FolderMock(trustedQueuePath);

  function validPackage() {
    return {
      schemaVersion: "2.0.0",
      exporterVersion: "0.2.0",
      exportedAt: "2026-07-22T00:00:00.000Z",
      contentHash: "a".repeat(64),
      source: { fileKey: "file-key", pageId: "page-id" },
      target: { width: 1920, height: 1080, fps: 30, timeUnit: "seconds" },
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

  function options(removeAfterReport: boolean, queueRootPath = trustedQueuePath) {
    return {
      allowDuplicate: false,
      removeAfterReport,
      queueRoot: new FolderMock(queueRootPath),
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
    preexisting,
    projectItems,
    fontsByPostScriptName,
    trustedQueuePath,
    get beginUndoCount() {
      return beginUndoCount;
    },
    get endUndoCount() {
      return endUndoCount;
    }
  };
}

function canonicalTiming(): CanonicalTiming {
  const sourceUrl = new URL("../config/video001-figma-scenes.json", import.meta.url);
  return JSON.parse(readFileSync(sourceUrl, "utf8")) as CanonicalTiming;
}

function makeFullLessonPackage(harness: ReturnType<typeof makeImporterHarness>) {
  const timing = canonicalTiming();
  harness.put("/timing/figma-scenes.json", timing);
  const value = harness.validPackage();
  const templateFrame = value.frames[0]!;
  const templateShape = templateFrame.children[0]!;
  value.source = {
    fileKey: timing.source.figmaFileKey,
    pageId: timing.source.figmaPageNodeId
  };
  value.frames = timing.shots.map((shot, index) => ({
    ...templateFrame,
    nodeId: shot.figmaNodeId,
    name: shot.name,
    duration: shot.duration,
    children: [{
      ...templateShape,
      id: "shape-" + String(index + 1),
      name: "Shape " + String(index + 1)
    }]
  }));
  return { timing, value };
}

test("retains canonical timing order and seconds metadata for full-lesson assembly", () => {
  const harness = makeImporterHarness();
  const timing = canonicalTiming();
  const timingFile = harness.put("/timing/canonical-figma-scenes.json", timing);

  const loaded = harness.importer.loadTiming(timingFile);

  assert.deepEqual(
    JSON.parse(JSON.stringify(loaded.shots)),
    timing.shots.map((shot, index) => ({
      index: index + 1,
      nodeId: shot.figmaNodeId,
      name: shot.name,
      start: shot.start,
      duration: shot.duration
    }))
  );
  assert.deepEqual(
    JSON.parse(JSON.stringify(loaded.shotsByNodeId[timing.shots[31]!.figmaNodeId])),
    {
      index: 32,
      nodeId: timing.shots[31]!.figmaNodeId,
      name: timing.shots[31]!.name,
      start: timing.shots[31]!.start,
      duration: timing.shots[31]!.duration
    }
  );
});

test("imports the exact canonical 48-frame lesson into one chronological 14-minute master", () => {
  const harness = makeImporterHarness();
  const { timing, value } = makeFullLessonPackage(harness);
  const packageFile = harness.put(
    "/manual/full-lesson.video001-ae.json",
    stampCanonicalContentHash(value)
  );

  const result = harness.importer.importPackageFile(
    packageFile,
    harness.options(false)
  ) as {
    status: string;
    report: { createdCompNames: string[]; createdMasterCompName: string | null };
  };
  const master = harness.projectItems.find(
    (item): item is CompItemMock => item instanceof CompItemMock && item.name === "VIDEO001_MASTER_v001"
  );

  assert.equal(result.status, "IMPORTED");
  assert.equal(result.report.createdCompNames.length, 48);
  assert.equal(result.report.createdMasterCompName, "VIDEO001_MASTER_v001");
  assert.ok(master);
  assert.equal(master.duration, 840);
  assert.equal(master.frameRate, 30);
  assert.equal(master.numLayers, 48);
  assert.deepEqual(master.layersInTimelineOrder.map((layer) => ({
    source: layer.source!.name,
    startTime: layer.startTime,
    inPoint: layer.inPoint,
    outPoint: layer.outPoint
  })), timing.shots.map((shot) => ({
    source: `${shot.name}_v001`,
    startTime: shot.start,
    inPoint: shot.start,
    outPoint: shot.start + shot.duration
  })));
  assert.equal(master.comment, "Video001Export sha256:" + value.contentHash);
});

test("rejects a reordered 48-frame lesson before After Effects mutation", () => {
  const harness = makeImporterHarness();
  const { value } = makeFullLessonPackage(harness);
  const first = value.frames[0]!;
  value.frames[0] = value.frames[1]!;
  value.frames[1] = first;
  const packageFile = harness.put(
    "/manual/reordered-full-lesson.video001-ae.json",
    stampCanonicalContentHash(value)
  );

  assert.throws(
    () => harness.importer.importPackageFile(packageFile, harness.options(false)),
    /full-lesson package frames must preserve canonical shot order/i
  );
  assert.equal(harness.beginUndoCount, 0);
  assert.deepEqual(harness.projectItems.map((item) => item.name), ["preexisting"]);
});

test("rejects a duplicated node ID in a 48-frame lesson before After Effects mutation", () => {
  const harness = makeImporterHarness();
  const { value } = makeFullLessonPackage(harness);
  value.frames[1] = JSON.parse(JSON.stringify(value.frames[0]!)) as typeof value.frames[number];
  const packageFile = harness.put(
    "/manual/duplicated-full-lesson.video001-ae.json",
    stampCanonicalContentHash(value)
  );

  assert.throws(
    () => harness.importer.importPackageFile(packageFile, harness.options(false)),
    /full-lesson package frames must preserve canonical shot order/i
  );
  assert.equal(harness.beginUndoCount, 0);
  assert.deepEqual(harness.projectItems.map((item) => item.name), ["preexisting"]);
});

test("rejects a 48-frame lesson with a missing configured shot before After Effects mutation", () => {
  const harness = makeImporterHarness();
  const { value } = makeFullLessonPackage(harness);
  value.frames[20] = {
    ...value.frames[20]!,
    nodeId: "missing:shot"
  };
  const packageFile = harness.put(
    "/manual/missing-shot-full-lesson.video001-ae.json",
    stampCanonicalContentHash(value)
  );

  assert.throws(
    () => harness.importer.importPackageFile(packageFile, harness.options(false)),
    /does not match the approved Video 001 timing/i
  );
  assert.equal(harness.beginUndoCount, 0);
  assert.deepEqual(harness.projectItems.map((item) => item.name), ["preexisting"]);
});

test("rolls back the master and all frame roots when master layer creation fails", () => {
  const harness = makeImporterHarness(undefined, false, { failMasterLayerAt: 24 });
  const { value } = makeFullLessonPackage(harness);
  const packageFile = harness.put(
    "/manual/master-failure.video001-ae.json",
    stampCanonicalContentHash(value)
  );

  assert.throws(
    () => harness.importer.importPackageFile(packageFile, harness.options(false)),
    /mock master layer creation failure/
  );
  assert.equal(harness.beginUndoCount, 1);
  assert.equal(harness.removalLog[0], "VIDEO001_MASTER_v001");
  assert.equal(harness.preexisting.removed, false);
  assert.deepEqual(
    harness.projectItems.filter((item) => !item.removed).map((item) => item.name),
    ["preexisting"]
  );
});

test("rolls back all frame roots when master comp creation fails before the master exists", () => {
  const harness = makeImporterHarness(undefined, false, {
    failMasterCompCreation: true
  });
  const { timing, value } = makeFullLessonPackage(harness);
  const packageFile = harness.put(
    "/manual/master-comp-creation-failure.video001-ae.json",
    stampCanonicalContentHash(value)
  );

  assert.throws(
    () => harness.importer.importPackageFile(packageFile, harness.options(false)),
    /mock master comp creation failure/
  );

  const createdItems = harness.projectItems.filter((item) => item !== harness.preexisting);
  assert.equal(createdItems.length, 1 + timing.shots.length * 3);
  assert.ok(createdItems.every((item) => item.removed));
  assert.equal(harness.removalLog.length, createdItems.length);
  assert.equal(harness.removalLog[0], timing.shots[47]!.name + "_v001");
  assert.equal(harness.removalLog[harness.removalLog.length - 1], "01_Exporter_Imports");
  assert.equal(harness.preexisting.removed, false);
  assert.equal(harness.removalLog.indexOf(harness.preexisting.name), -1);
  assert.equal(
    harness.projectItems.some((item) => item.name.indexOf("VIDEO001_MASTER_v") === 0),
    false
  );
  assert.equal(harness.beginUndoCount, 1);
  assert.equal(harness.endUndoCount, 1);
  assert.deepEqual(
    harness.projectItems.filter((item) => !item.removed).map((item) => item.name),
    ["preexisting"]
  );
});

test("unchanged full-lesson resend remains a duplicate no-op", () => {
  const harness = makeImporterHarness();
  const { value } = makeFullLessonPackage(harness);
  const packageFile = harness.put(
    "/manual/unchanged-full-lesson.video001-ae.json",
    stampCanonicalContentHash(value)
  );
  const first = harness.importer.importPackageFile(
    packageFile,
    harness.options(false)
  ) as { status: string };
  const itemCountAfterFirst = harness.projectItems.filter((item) => !item.removed).length;
  const duplicate = harness.importer.importPackageFile(
    packageFile,
    harness.options(false)
  ) as { status: string; report: null };

  assert.equal(first.status, "IMPORTED");
  assert.equal(duplicate.status, "DUPLICATE_CONTENT");
  assert.equal(duplicate.report, null);
  assert.equal(harness.projectItems.filter((item) => !item.removed).length, itemCountAfterFirst);
  assert.equal(harness.beginUndoCount, 1);
});

test("partial selected-frame import remains valid without creating a master", () => {
  const harness = makeImporterHarness();
  const { value } = makeFullLessonPackage(harness);
  value.frames = [value.frames[31]!];
  stampCanonicalContentHash(value);
  const packageFile = harness.put("/manual/partial.video001-ae.json", value);

  const result = harness.importer.importPackageFile(
    packageFile,
    harness.options(false)
  ) as {
    status: string;
    report: { createdCompNames: string[]; createdMasterCompName: string | null };
  };

  assert.equal(result.status, "IMPORTED");
  assert.deepEqual(
    Array.from(result.report.createdCompNames),
    ["S001_SH32_Repo_PreparationNotLearning_v001"]
  );
  assert.equal(result.report.createdMasterCompName, null);
  assert.equal(
    harness.projectItems.some((item) => item.name.indexOf("VIDEO001_MASTER_v") === 0),
    false
  );
});

test("font resolution rejects an installed font that cannot render the exact run text", () => {
  const harness = makeImporterHarness();
  harness.fontsByPostScriptName.set("Sora-Bold", [{
    postScriptName: "Sora-Bold",
    hasGlyphsFor(value: string) { return value !== "θ"; }
  }]);
  harness.fontsByPostScriptName.set("Inter-Regular", [{
    postScriptName: "Inter-Regular",
    hasGlyphsFor() { return true; }
  }]);
  const state = { missingFonts: [] as string[], fallbacks: [] as unknown[], warnings: [] as string[] };

  const result = harness.importer.__test.resolveRunFont(
    { start: 17, end: 18, fontFamily: "Sora", fontStyle: "Bold" },
    { id: "model-label", name: "MODEL_Parameters θ", text: "MODEL_Parameters θ" },
    state
  );

  assert.equal(result.postScriptName, "Inter-Regular");
  assert.deepEqual(state.missingFonts, ["Sora-Bold"]);
  assert.deepEqual(JSON.parse(JSON.stringify(state.fallbacks)), [{
    type: "font-substitution",
    nodeId: "model-label",
    nodeName: "MODEL_Parameters θ",
    property: "font",
    start: 17,
    end: 18,
    requested: "Sora-Bold",
    replacement: "Inter-Regular"
  }]);
});

test("font resolution checks visible glyphs without treating paragraph breaks as missing glyphs", () => {
  const harness = makeImporterHarness();
  harness.fontsByPostScriptName.set("Sora-SemiBold", [{
    postScriptName: "Sora-SemiBold",
    hasGlyphsFor(value: string) { return value === "LEARNINGBOUNDARY"; }
  }]);
  harness.fontsByPostScriptName.set("Inter-Regular", [{
    postScriptName: "Inter-Regular",
    hasGlyphsFor(value: string) { return value === "LEARNINGBOUNDARY"; }
  }]);
  const state = { missingFonts: [] as string[], fallbacks: [] as unknown[], warnings: [] as string[] };

  const result = harness.importer.__test.resolveRunFont(
    { start: 0, end: 17, fontFamily: "Sora", fontStyle: "SemiBold" },
    { id: "boundary-label", name: "TXT_BoundaryLabel", text: "LEARNING\nBOUNDARY" },
    state
  );

  assert.equal(result.postScriptName, "Sora-SemiBold");
  assert.deepEqual(state.missingFonts, []);
  assert.deepEqual(state.fallbacks, []);
  assert.deepEqual(state.warnings, []);
});

test("font substitution preserves bold emphasis without bolding ordinary Inter text", () => {
  const harness = makeImporterHarness();
  const soraBold = {
    postScriptName: "Sora-Bold",
    hasGlyphsFor(value: string) { return value !== "θ"; }
  };
  const interRegular = {
    postScriptName: "Inter-Regular",
    hasGlyphsFor() { return true; }
  };
  harness.fontsByPostScriptName.set("Sora-Bold", [soraBold]);
  harness.fontsByPostScriptName.set("Inter-Regular", [interRegular]);
  const state = { missingFonts: [] as string[], fallbacks: [] as unknown[], warnings: [] as string[] };

  const substitutedBold = harness.importer.__test.resolveRunFont(
    { start: 0, end: 1, fontFamily: "Sora", fontStyle: "Bold" },
    { id: "model-parameters", name: "MODEL_Parameters", text: "θ" },
    state
  );
  const ordinaryInter = harness.importer.__test.resolveRunFont(
    { start: 0, end: 4, fontFamily: "Inter", fontStyle: "Regular" },
    { id: "node-detail", name: "TXT_NodeDetail", text: "text" },
    state
  );
  const substitutedDocument = { fontObject: null as unknown, fauxBold: false };
  const ordinaryDocument = { fontObject: null as unknown, fauxBold: false };

  harness.importer.__test.applyResolvedFont(substitutedDocument, substitutedBold);
  harness.importer.__test.applyResolvedFont(ordinaryDocument, ordinaryInter);

  assert.equal(substitutedBold.postScriptName, "Inter-Regular");
  assert.equal(substitutedDocument.fontObject, interRegular);
  assert.equal(substitutedDocument.fauxBold, true);
  assert.equal(ordinaryInter.postScriptName, "Inter-Regular");
  assert.equal(ordinaryDocument.fontObject, interRegular);
  assert.equal(ordinaryDocument.fauxBold, false);
});

function mixedTextHostRecorder() {
  const ranges: Array<{
    start: number;
    end: number;
    fontObject: unknown;
    fauxBold: boolean;
  }> = [];
  const transformValues = new Map<string, unknown>();
  const animatorValues = new Map<string, unknown>();
  const documentValue = {
    text: "",
    fontObject: null as unknown,
    fauxBold: false,
    fontSize: 0,
    applyFill: false,
    fillColor: [] as number[],
    applyStroke: true,
    autoLeading: true,
    leading: 0,
    tracking: 0,
    justification: 0,
    boxTextPos: [-100, -20],
    resetCharStyle() {
      this.fontObject = null;
      this.fauxBold = false;
    },
    resetParagraphStyle() {},
    characterRange(start: number, end: number) {
      const range = {
        start,
        end,
        fontObject: this.fontObject,
        fauxBold: this.fauxBold
      };
      ranges.push(range);
      return range;
    }
  };
  const propertyValue = (name: string) => ({
    setValue(value: unknown) {
      animatorValues.set(name, value);
    }
  });
  const advanced = {
    property(name: string) {
      return name === "ADBE Text Range Units" ? propertyValue(name) : null;
    }
  };
  const selector = {
    property(name: string) {
      if (name === "ADBE Text Range Advanced") return advanced;
      if (name === "ADBE Text Index Start" || name === "ADBE Text Index End") return propertyValue(name);
      return null;
    }
  };
  const animator = {
    name: "",
    property(name: string) {
      if (name === "ADBE Text Animator Properties") {
        return { addProperty: (propertyName: string) => propertyValue(propertyName) };
      }
      if (name === "ADBE Text Selectors") {
        return { addProperty: () => selector };
      }
      return null;
    }
  };
  const source = {
    value: documentValue,
    setValue(value: typeof documentValue) {
      this.value = value;
    }
  };
  const textProperties = {
    property(name: string) {
      if (name === "ADBE Text Document") return source;
      if (name === "ADBE Text Animators") return { addProperty: () => animator };
      return null;
    }
  };
  const transform = {
    property(name: string) {
      return {
        setValue(value: unknown) {
          transformValues.set(name, value);
        }
      };
    }
  };
  const layer = {
    name: "",
    comment: "",
    property(name: string) {
      if (name === "ADBE Text Properties") return textProperties;
      if (name === "ADBE Transform Group") return transform;
      return null;
    }
  };
  const comp = {
    layers: {
      addBoxText(size: number[]) {
        assert.deepEqual(Array.from(size), [200, 40]);
        return layer;
      }
    }
  };
  const state = {
    layerCount: 0,
    nativeCount: 0,
    missingFonts: [] as string[],
    fallbacks: [] as unknown[],
    warnings: [] as string[]
  };
  return {
    comp,
    documentValue,
    ranges,
    animatorValues,
    transformValues,
    context: {
      frame: { width: 1920, height: 1080 },
      target: { width: 1920, height: 1080 },
      state
    },
    state
  };
}

test("addText keeps ordinary Inter dominant while bolding only the fallback secondary run", () => {
  const harness = makeImporterHarness();
  const host = mixedTextHostRecorder();
  const interRegular = {
    postScriptName: "Inter-Regular",
    hasGlyphsFor() { return true; }
  };
  harness.fontsByPostScriptName.set("Sora-Bold", [{
    postScriptName: "Sora-Bold",
    hasGlyphsFor(value: string) { return value !== "θ"; }
  }]);
  harness.fontsByPostScriptName.set("Inter-Regular", [interRegular]);

  harness.importer.__test.addText(host.comp, {
    id: "mixed-bold-dominant",
    name: "TXT_Mixed",
    x: 10,
    y: 20,
    rotation: 0,
    opacity: 1,
    text: "θtext",
    textBox: { width: 200, height: 40 },
    paragraph: { align: "LEFT", lineHeightPx: 32, letterSpacingPx: 0 },
    runs: [
      { start: 0, end: 1, fontFamily: "Sora", fontStyle: "Bold", fontSize: 32, color: "#FFFFFF" },
      { start: 1, end: 5, fontFamily: "Inter", fontStyle: "Regular", fontSize: 32, color: "#FFFFFF" }
    ]
  }, host.context);

  assert.equal(host.documentValue.fontObject, interRegular);
  assert.equal(host.documentValue.fauxBold, false);
  assert.deepEqual(host.ranges.map((range) => ({
    start: range.start,
    end: range.end,
    font: (range.fontObject as { postScriptName: string }).postScriptName,
    fauxBold: range.fauxBold
  })), [{ start: 0, end: 1, font: "Inter-Regular", fauxBold: true }]);
  assert.equal(host.state.layerCount, 1);
  assert.equal(host.state.nativeCount, 1);
});

test("addText keeps a bold fallback dominant while restoring the ordinary Inter secondary run", () => {
  const harness = makeImporterHarness();
  const host = mixedTextHostRecorder();
  const interRegular = {
    postScriptName: "Inter-Regular",
    hasGlyphsFor() { return true; }
  };
  harness.fontsByPostScriptName.set("Sora-Bold", [{
    postScriptName: "Sora-Bold",
    hasGlyphsFor(value: string) { return value.indexOf("θ") === -1; }
  }]);
  harness.fontsByPostScriptName.set("Inter-Regular", [interRegular]);

  harness.importer.__test.addText(host.comp, {
    id: "mixed-bold-dominant",
    name: "TXT_Mixed",
    x: 10,
    y: 20,
    rotation: 0,
    opacity: 1,
    text: "θθθθθtext",
    textBox: { width: 200, height: 40 },
    paragraph: { align: "LEFT", lineHeightPx: 32, letterSpacingPx: 0 },
    runs: [
      { start: 0, end: 5, fontFamily: "Sora", fontStyle: "Bold", fontSize: 32, color: "#FFFFFF" },
      { start: 5, end: 9, fontFamily: "Inter", fontStyle: "Regular", fontSize: 32, color: "#FFFFFF" }
    ]
  }, host.context);

  assert.equal(host.documentValue.fontObject, interRegular);
  assert.equal(host.documentValue.fauxBold, true);
  assert.deepEqual(host.ranges.map((range) => ({
    start: range.start,
    end: range.end,
    font: (range.fontObject as { postScriptName: string }).postScriptName,
    fauxBold: range.fauxBold
  })), [{ start: 5, end: 9, font: "Inter-Regular", fauxBold: false }]);
  assert.equal(host.state.layerCount, 1);
  assert.equal(host.state.nativeCount, 1);
});

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

test("public file importer automatically rolls back only its new items in reverse after a post-creation failure", () => {
  const harness = makeImporterHarness(undefined, false, { failShapeLayerCreation: true });
  const packageFile = harness.put(
    "/manual/rollback.video001-ae.json",
    stampCanonicalContentHash(harness.validPackage())
  );

  assert.throws(
    () => harness.importer.importPackageFile(packageFile, harness.options(false)),
    /mock shape layer creation failure/
  );

  assert.equal(harness.beginUndoCount, 1);
  assert.deepEqual(harness.removalLog, ["Shot_v001", "v001", "Shot", "01_Exporter_Imports"]);
  assert.equal(harness.preexisting.removed, false);
  assert.deepEqual(
    harness.projectItems.filter((item) => !item.removed).map((item) => item.name),
    ["preexisting"]
  );
});

test("top-level and recursive group comps use frame duration as seconds", () => {
  const harness = makeImporterHarness(undefined, false, { failShapeLayerCreation: true });
  const value = harness.validPackage() as unknown as {
    exportedAt: string;
    contentHash: string;
    frames: Array<{ children: unknown[] }>;
    [key: string]: unknown;
  };
  value.frames[0]!.children = [{
    id: "group",
    name: "Group",
    kind: "group",
    x: 0,
    y: 0,
    width: 100,
    height: 100,
    rotation: 0,
    opacity: 1,
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
    }]
  }];
  const packageFile = harness.put(
    "/manual/seconds.video001-ae.json",
    stampCanonicalContentHash(value)
  );

  assert.throws(
    () => harness.importer.importPackageFile(packageFile, harness.options(false)),
    /mock shape layer creation failure/
  );

  const createdComps = harness.projectItems.filter((item): item is CompItemMock => item instanceof CompItemMock);
  assert.equal(createdComps.length, 2);
  for (const comp of createdComps) {
    assert.equal(comp.duration, 30);
    assert.equal(comp.frameRate, 30);
    assert.equal(comp.duration * comp.frameRate, 900);
  }
});

test("After Effects rejects an ambiguous package time unit before project mutation", () => {
  const harness = makeImporterHarness();
  const value = harness.validPackage();
  (value.target as { timeUnit: string }).timeUnit = "frames";
  const packageFile = harness.put(
    "/manual/ambiguous-time-unit.video001-ae.json",
    stampCanonicalContentHash(value)
  );

  assert.throws(
    () => harness.importer.importPackageFile(packageFile, harness.options(false)),
    /durations in seconds/i
  );
  assert.equal(harness.beginUndoCount, 0);
});

test("After Effects rejects legacy 1.x packages with an actionable 2.0.0 error before mutation", () => {
  const harness = makeImporterHarness();
  const value = harness.validPackage();
  (value as { schemaVersion: string }).schemaVersion = "1.0.0";
  const packageFile = harness.put(
    "/manual/legacy-schema.video001-ae.json",
    stampCanonicalContentHash(value)
  );

  assert.throws(
    () => harness.importer.importPackageFile(packageFile, harness.options(false)),
    /schema 1\.0\.0 is unsupported.*requires 2\.0\.0/i
  );
  assert.equal(harness.beginUndoCount, 0);
});

test("After Effects accepts a fractional-second duration on an exact frame boundary", () => {
  const harness = makeImporterHarness();
  const value = harness.validPackage();
  value.frames[0]!.duration = 1 / 30;
  harness.put("/timing/figma-scenes.json", {
    canvas: { width: 1920, height: 1080, fps: 30, timeUnit: "seconds", duration: 840 },
    source: { figmaFileKey: "file-key", figmaPageNodeId: "page-id" },
    shots: [{ figmaNodeId: "1:1", name: "Shot", start: 0, duration: 1 / 30 }]
  });
  const packageFile = harness.put(
    "/manual/fractional-seconds.video001-ae.json",
    stampCanonicalContentHash(value)
  );
  const result = harness.importer.importPackageFile(
    packageFile,
    harness.options(false)
  ) as { status: string };

  assert.equal(result.status, "IMPORTED");
  assert.equal(harness.beginUndoCount, 1);
  const createdComp = harness.projectItems.find((item): item is CompItemMock => item instanceof CompItemMock);
  assert.ok(createdComp);
  assert.equal(createdComp.duration, 1 / 30);
  assert.equal(createdComp.duration * createdComp.frameRate, 1);
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
    "/user-data/Video001FigmaAEExporter/incoming/" + "b".repeat(64) + ".video001-ae.json",
    "/user-data/Video001FigmaAEExporter/incoming/nested/" + "a".repeat(64) + ".video001-ae.json"
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
    harness.trustedQueuePath + "/incoming/" + value.contentHash + ".video001-ae.json",
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

test("custom queue roots cannot bypass public package fingerprint verification", () => {
  const incorrectHash = "a".repeat(64);
  const harness = makeImporterHarness("c".repeat(64));
  const value = harness.validPackage();
  value.contentHash = incorrectHash;
  const packageFile = harness.put(
    "/tmp/custom/incoming/" + incorrectHash + ".video001-ae.json",
    value
  );

  assert.throws(
    () => harness.importer.importPackageFile(
      packageFile,
      harness.options(true, "/tmp/custom")
    ),
    /trusted queue root|content fingerprint|content hash/i
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
  const value = stampCanonicalContentHash(harness.validPackage());
  const packageFile = harness.put("/manual/package.video001-ae.json", value);
  const result = harness.importer.importPackageFile(
    packageFile,
    harness.options(false)
  ) as { status: string };
  assert.equal(result.status, "IMPORTED");
  assert.equal(harness.beginUndoCount, 1);
  assert.ok(harness.systemCommands.some((command) => command.startsWith("/bin/chmod 600 ")));
});

test("unchanged live resend is consumed after a duplicate no-op", () => {
  const harness = makeImporterHarness(undefined, true);
  const value = stampCanonicalContentHash(harness.validPackage());
  const queuePath = `${harness.trustedQueuePath}/incoming/${value.contentHash}.video001-ae.json`;
  const packageFile = harness.put(queuePath, value);
  const result = harness.importer.importPackageFile(
    packageFile,
    harness.options(true)
  ) as { status: string };

  assert.equal(result.status, "DUPLICATE_CONTENT");
  assert.equal(harness.records.get(queuePath)?.exists, false);
  assert.equal(harness.beginUndoCount, 0);
});

type BridgeState = {
  pid: number;
  port: number;
  pairingCode: string;
  pairingExpiresAt: number;
};

type PanelHarnessOptions = {
  nodePaths?: string[];
  stateCommand?: string;
  stateExists?: boolean;
  stateSequence?: BridgeState[];
  psByPid?: Record<number, string[]>;
  whichNode?: string;
};

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

function makePanelHarness({
  nodePaths = ["/usr/local/bin/node"],
  stateCommand = "",
  stateExists = true,
  stateSequence,
  psByPid,
  whichNode = "/usr/local/bin/node\n"
}: PanelHarnessOptions) {
  const sourceUrl = new URL("../src/ae/panel.jsx", import.meta.url);
  const source = instrumentPanel(readFileSync(sourceUrl, "utf8"));
  const statePath = "/user-data/Video001FigmaAEExporter/state.json";
  const bridgePath = "/bundle/bridge/video001-bridge.mjs";
  const existing = new Set<string>([bridgePath, ...nodePaths]);
  if (stateExists) existing.add(statePath);
  const commands: string[] = [];
  const defaultState: BridgeState = {
    pid: 4242,
    port: 3456,
    pairingCode: "123456",
    pairingExpiresAt: 2_000_000_000_000
  };
  const stateValues = stateSequence ?? [defaultState];
  let stateReadIndex = 0;
  const psIndexes: Record<number, number> = {};

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
        const value = stateValues[Math.min(stateReadIndex, stateValues.length - 1)]!;
        stateReadIndex += 1;
        return JSON.stringify(value);
      }
    },
    system: {
      callSystem(command: string) {
        commands.push(command);
        if (command === "/usr/bin/which node") return whichNode;
        const psMatch = /^\/bin\/ps -p ([0-9]+) -o command=$/.exec(command);
        if (psMatch) {
          const pid = Number(psMatch[1]);
          const sequence = psByPid?.[pid] ?? [stateCommand];
          const index = psIndexes[pid] ?? 0;
          psIndexes[pid] = index + 1;
          return sequence[Math.min(index, sequence.length - 1)] ?? "";
        }
        return "";
      }
    },
    app: { cancelTask() {}, scheduleTask() { return 1; } }
  };
  (context.$ as Record<string, unknown>).global = context;
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

test("Start uses a trusted fixed Node location when the application PATH omits Node", () => {
  const harness = makePanelHarness({
    nodePaths: ["/opt/homebrew/bin/node"],
    stateCommand: "",
    whichNode: ""
  });
  harness.panel.startBridge();
  assert.ok(harness.commands.some((command) => command.startsWith("'/opt/homebrew/bin/node' ")));
});

test("Stop recovers an unrelated reused PID without signaling it", () => {
  const harness = makePanelHarness({ stateCommand: "/usr/bin/python unrelated.py\n" });
  harness.panel.stopBridge(false);
  assert.equal(harness.existing.has(harness.statePath), false);
  assert.ok(harness.commands.every((command) => !command.startsWith("/bin/kill")));
});

test("Start preserves a replacement state file that appears during stale-state revalidation", () => {
  const bridgeCommand = "/usr/local/bin/node /bundle/bridge/video001-bridge.mjs --root /user-data/Video001FigmaAEExporter\n";
  const firstState: BridgeState = {
    pid: 4242,
    port: 3456,
    pairingCode: "123456",
    pairingExpiresAt: 2_000_000_000_000
  };
  const replacementState: BridgeState = {
    pid: 5252,
    port: 3456,
    pairingCode: "654321",
    pairingExpiresAt: 2_000_000_100_000
  };
  const harness = makePanelHarness({
    stateSequence: [firstState, replacementState, replacementState],
    psByPid: {
      4242: ["/usr/bin/python unrelated.py\n", "/usr/bin/python unrelated.py\n"],
      5252: [bridgeCommand, bridgeCommand]
    }
  });

  harness.panel.startBridge();

  assert.equal(harness.existing.has(harness.statePath), true);
  assert.ok(harness.commands.every((command) => !command.includes(" --root ") || command.startsWith("/bin/ps")));
  assert.ok(harness.commands.every((command) => !command.startsWith("/bin/kill")));
});

test("Start preserves state when a PID is reused by the bridge during stale-state revalidation", () => {
  const bridgeCommand = "/usr/local/bin/node /bundle/bridge/video001-bridge.mjs --root /user-data/Video001FigmaAEExporter\n";
  const harness = makePanelHarness({
    psByPid: {
      4242: [
        "/usr/bin/python unrelated.py\n",
        bridgeCommand,
        bridgeCommand,
        bridgeCommand,
        bridgeCommand
      ]
    }
  });

  harness.panel.startBridge();

  assert.equal(harness.existing.has(harness.statePath), true);
  assert.ok(harness.commands.every((command) => !command.includes(" --root ") || command.startsWith("/bin/ps")));
  assert.ok(harness.commands.every((command) => !command.startsWith("/bin/kill")));
});

test("Stop refuses a PID that is reused after live-state verification", () => {
  const bridgeCommand = "/usr/local/bin/node /bundle/bridge/video001-bridge.mjs --root /user-data/Video001FigmaAEExporter\n";
  const harness = makePanelHarness({
    psByPid: {
      4242: [bridgeCommand, bridgeCommand, "/usr/bin/python unrelated.py\n"]
    }
  });

  assert.throws(() => harness.panel.stopBridge(false), /Refusing to stop PID 4242/);
  assert.equal(harness.existing.has(harness.statePath), true);
  assert.ok(harness.commands.every((command) => !command.startsWith("/bin/kill")));
});

class UiElementMock {
  text = "";
  active = false;
  characters = 0;
  readonly children: UiElementMock[] = [];
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
  private readonly eventListeners = new Map<string, Array<(event: {
    keyName: string;
    preventDefault(): void;
  }) => void>>();
  add(type: string, _bounds?: unknown, text?: string): UiElementMock {
    const element = new UiElementMock();
    if (type === "statictext" || type === "edittext" || type === "button") element.text = text ?? "";
    this.children.push(element);
    return element;
  }
  addEventListener(
    type: string,
    listener: (event: { keyName: string; preventDefault(): void }) => void
  ): void {
    const listeners = this.eventListeners.get(type) ?? [];
    listeners.push(listener);
    this.eventListeners.set(type, listeners);
  }
  dispatchKey(keyName: string): boolean {
    let prevented = false;
    const event = {
      keyName,
      preventDefault() { prevented = true; }
    };
    for (const listener of this.eventListeners.get("keydown") ?? []) listener(event);
    return prevented;
  }
  findByText(text: string): UiElementMock | undefined {
    if (this.text === text) return this;
    for (const child of this.children) {
      const match = child.findByText(text);
      if (match) return match;
    }
    return undefined;
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
  (context.$ as Record<string, unknown>).global = context;
  vm.runInNewContext(source, context, { filename: sourceUrl.pathname });
  assert.deepEqual(scheduled, [["$.global.Video001ExporterPanel.poll()", 1000, true]]);
  const stopButton = windowValue?.findByText("Stop bridge");
  assert.ok(stopButton);
  assert.equal(stopButton.dispatchKey("A"), false);
  assert.equal(windowValue?.children[0]?.text, "0 package(s) queued; bridge stopped");
  assert.equal(stopButton.dispatchKey("Space"), true);
  assert.equal(windowValue?.children[0]?.text, "Bridge is stopped");
  const panel = (context as typeof context & {
    Video001ExporterPanel: { dispose?: () => void };
  }).Video001ExporterPanel;
  assert.equal(typeof panel.dispose, "function");
  panel.dispose?.();
  assert.deepEqual(cancelled, [73]);
  assert.ok(windowValue?.onClose);
  windowValue.onClose();
  assert.deepEqual(cancelled, [73]);
});

function mutationRejectingProxy<T extends object>(target: T, label: string, cache = new WeakMap<object, object>()): T {
  const cached = cache.get(target);
  if (cached) return cached as T;
  const proxy = new Proxy(target, {
    get(object, property, receiver) {
      const value = Reflect.get(object, property, receiver) as unknown;
      if (value !== null && typeof value === "object") {
        return mutationRejectingProxy(value, label + "." + String(property), cache);
      }
      return value;
    },
    set(_object, property) {
      throw new Error("audit mutated " + label + "." + String(property));
    },
    defineProperty(_object, property) {
      throw new Error("audit mutated " + label + "." + String(property));
    },
    deleteProperty(_object, property) {
      throw new Error("audit mutated " + label + "." + String(property));
    }
  });
  cache.set(target, proxy);
  return proxy;
}

test("read-only audit deeply preserves project, comp, layer, and property state while separating fallback categories", () => {
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
  class TextLayerMockLocal {
    name = "TXT_Title";
    comment = "source text";
    readonly sourceProperty: object;

    constructor(sourceProperty: object) {
      this.sourceProperty = sourceProperty;
    }

    property(name: string): object {
      assert.equal(name, "ADBE Text Properties");
      return {
        property: (propertyName: string) => {
          assert.equal(propertyName, "ADBE Text Document");
          return this.sourceProperty;
        }
      };
    }
  }
  class CompItemMockLocal {
    name = "Shot_v001";
    width = 1920;
    height = 1080;
    frameRate = 30;
    duration = 1;
    numLayers = 1;
    comment = "Video001Export sha256:" + hash;
    readonly textLayer: object;

    constructor(textLayer: object) {
      this.textLayer = textLayer;
    }

    layer(index: number): object {
      assert.equal(index, 1);
      return this.textLayer;
    }
  }
  class EmptyClass {}
  const fontObject = mutationRejectingProxy({ postScriptName: "Inter-Regular" }, "fontObject");
  const documentValue = mutationRejectingProxy({
    text: "How a computer learns from text",
    font: "Inter",
    fontSize: 64,
    fontObject,
    boxTextSize: [1200, 180]
  }, "textDocument");
  const sourceProperty = mutationRejectingProxy({ value: documentValue }, "sourceProperty");
  const textLayer = mutationRejectingProxy(new TextLayerMockLocal(sourceProperty), "textLayer");
  const comp = mutationRejectingProxy(new CompItemMockLocal(textLayer), "comp");
  const project = mutationRejectingProxy({
    activeItem: comp,
    file: null,
    numItems: 1,
    items: { addComp(): never { throw new Error("audit mutated project"); } }
  }, "project");
  const snapshot = () => ({
    project: { activeItem: project.activeItem, file: project.file, numItems: project.numItems },
    comp: {
      name: comp.name,
      width: comp.width,
      height: comp.height,
      frameRate: comp.frameRate,
      duration: comp.duration,
      numLayers: comp.numLayers,
      comment: comp.comment,
      textLayer: comp.textLayer
    },
    layer: {
      name: textLayer.name,
      comment: textLayer.comment,
      sourceProperty: textLayer.sourceProperty
    },
    property: { value: sourceProperty.value },
    textDocument: {
      text: documentValue.text,
      font: documentValue.font,
      fontSize: documentValue.fontSize,
      fontObject: documentValue.fontObject,
      boxTextSize: Array.from(documentValue.boxTextSize)
    },
    fontObject: { postScriptName: fontObject.postScriptName }
  });
  const before = snapshot();
  const context = {
    $: { fileName: "/bundle/ae/audit-export.jsx" },
    File: FileMock,
    Folder: FolderMock,
    CompItem: CompItemMockLocal,
    TextLayer: TextLayerMockLocal,
    ShapeLayer: EmptyClass,
    CameraLayer: EmptyClass,
    LightLayer: EmptyClass,
    AVLayer: EmptyClass,
    app: { project }
  };
  vm.runInNewContext(source, context, { filename: sourceUrl.pathname });
  assert.deepEqual(snapshot(), before);
  const audit = JSON.parse(output) as {
    comp: { durationSeconds: number; durationFrames: number; duration?: number };
    precompHierarchy: { durationSeconds: number; durationFrames: number; duration?: number };
    missingFonts: string[];
    rasterFallbacks: Array<{ type: string; property: string }>;
    layers: Array<{ name: string; text: string; font: string; boxDimensions: number[] }>;
  };
  assert.equal(Object.prototype.hasOwnProperty.call(audit.comp, "duration"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(audit.precompHierarchy, "duration"), false);
  assert.deepEqual(audit.comp, {
    name: "Shot_v001",
    width: 1920,
    height: 1080,
    fps: 30,
    durationSeconds: 1,
    durationFrames: 30
  });
  assert.equal(audit.precompHierarchy.durationSeconds, 1);
  assert.equal(audit.precompHierarchy.durationFrames, 30);
  assert.deepEqual(audit.missingFonts, ["Missing-Regular"]);
  assert.deepEqual(audit.rasterFallbacks, [{ type: "raster-fallback", property: "gradient", replacement: "PNG" }]);
  assert.deepEqual(audit.layers, [{
    comp: "Shot_v001",
    name: "TXT_Title",
    type: "text",
    comment: "source text",
    text: "How a computer learns from text",
    font: "Inter-Regular",
    fontSize: 64,
    boxDimensions: [1200, 180],
    shapeMatchNames: [],
    sourceComp: null
  }]);
});

test("read-only audit records timing only for precomp layers without changing project item count", () => {
  const sourceUrl = new URL("../src/ae/audit-export.jsx", import.meta.url);
  const source = readFileSync(sourceUrl, "utf8");
  const hash = "b".repeat(64);
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
    get exists(): boolean { return false; }
    open(): boolean { return true; }
    read(): string { return ""; }
    write(value: string): boolean { output = value; return true; }
    close(): void {}
  }
  class CompItemMockLocal {
    readonly name: string;
    readonly width = 1920;
    readonly height = 1080;
    readonly frameRate = 30;
    readonly duration: number;
    readonly comment: string;
    readonly layers: object[];

    constructor(name: string, duration: number, comment: string, layers: object[]) {
      this.name = name;
      this.duration = duration;
      this.comment = comment;
      this.layers = layers;
    }

    get numLayers(): number { return this.layers.length; }
    layer(index: number): object { return this.layers[index - 1]!; }
  }
  class AVLayerMockLocal {
    readonly name: string;
    readonly comment = "";
    readonly source: CompItemMockLocal;
    readonly startTime: number;
    readonly inPoint: number;
    readonly outPoint: number;

    constructor(
      name: string,
      sourceComp: CompItemMockLocal,
      startTime: number,
      inPoint: number,
      outPoint: number
    ) {
      this.name = name;
      this.source = sourceComp;
      this.startTime = startTime;
      this.inPoint = inPoint;
      this.outPoint = outPoint;
    }
  }
  class EmptyClass {}
  const shot = mutationRejectingProxy(
    new CompItemMockLocal("S001_SH32_Repo_PreparationNotLearning_v001", 28, "", []),
    "shot"
  );
  const precompLayer = mutationRejectingProxy(
    new AVLayerMockLocal("S001_SH32_Repo_PreparationNotLearning_v001", shot, 512, 512, 540),
    "precompLayer"
  );
  const master = mutationRejectingProxy(
    new CompItemMockLocal(
      "VIDEO001_MASTER_v001",
      840,
      "Video001Export sha256:" + hash,
      [precompLayer]
    ),
    "master"
  );
  const project = mutationRejectingProxy({
    activeItem: master,
    file: null,
    numItems: 2
  }, "project");
  const context = {
    $: { fileName: "/bundle/ae/audit-export.jsx" },
    File: FileMock,
    Folder: FolderMock,
    CompItem: CompItemMockLocal,
    TextLayer: EmptyClass,
    ShapeLayer: EmptyClass,
    CameraLayer: EmptyClass,
    LightLayer: EmptyClass,
    AVLayer: AVLayerMockLocal,
    app: { project }
  };

  vm.runInNewContext(source, context, { filename: sourceUrl.pathname });

  const audit = JSON.parse(output) as {
    itemCountBefore: number;
    itemCountAfter: number;
    layers: Array<Record<string, unknown>>;
  };
  assert.equal(audit.itemCountBefore, 2);
  assert.equal(audit.itemCountAfter, 2);
  assert.deepEqual(audit.layers[0], {
    comp: "VIDEO001_MASTER_v001",
    name: "S001_SH32_Repo_PreparationNotLearning_v001",
    type: "precomp",
    comment: "",
    text: null,
    font: null,
    fontSize: null,
    boxDimensions: null,
    shapeMatchNames: [],
    sourceComp: "S001_SH32_Repo_PreparationNotLearning_v001",
    startTime: 512,
    inPoint: 512,
    outPoint: 540
  });
});

type FullLessonAuditDefect =
  | "gap"
  | "overlap"
  | "wrong-source"
  | "wrong-hash"
  | "wrong-recursive-duration"
  | "unexpected-raster"
  | "project-mutation";

function runFullLessonAudit(defect?: FullLessonAuditDefect) {
  const sourceUrl = new URL("../src/ae/audit-full-lesson.jsx", import.meta.url);
  const source = readFileSync(sourceUrl, "utf8");
  const timing = canonicalTiming();
  const hash = "c".repeat(64);
  const records = new Map<string, string>();
  let output = "";

  class FolderMock {
    static userData = new FolderMock("/user-data");
    readonly fsName: string;
    constructor(path: string) { this.fsName = path.replace(/\/$/, ""); }
  }
  class FileMock {
    static encoding = "UTF-8";
    readonly fsName: string;
    encoding = "UTF-8";
    private mode = "";
    constructor(path: string) { this.fsName = path; }
    get parent(): FolderMock {
      return new FolderMock(this.fsName.slice(0, this.fsName.lastIndexOf("/")));
    }
    get exists(): boolean { return records.has(this.fsName); }
    open(mode: string): boolean {
      this.mode = mode;
      return mode === "r" ? this.exists : true;
    }
    read(): string {
      if (defect === "project-mutation" && this.fsName.endsWith("/figma-scenes.json")) {
        projectItems.push(new FolderItemMock("mutation"));
      }
      return records.get(this.fsName) ?? "";
    }
    write(value: string): boolean {
      assert.equal(this.mode, "w");
      output = value;
      records.set(this.fsName, value);
      return true;
    }
    close(): void {}
  }
  class AuditComp {
    readonly name: string;
    readonly width = 1920;
    readonly height = 1080;
    readonly frameRate = 30;
    readonly duration: number;
    readonly comment: string;
    readonly timelineLayers: object[];
    constructor(name: string, duration: number, comment: string, layers: object[] = []) {
      this.name = name;
      this.duration = duration;
      this.comment = comment;
      this.timelineLayers = layers;
    }
    get numLayers(): number { return this.timelineLayers.length; }
    layer(index: number): object { return this.timelineLayers[index - 1]!; }
  }
  class AuditAvLayer {
    readonly name: string;
    readonly comment: string;
    readonly source: AuditComp | AuditFootage;
    readonly startTime: number;
    readonly inPoint: number;
    readonly outPoint: number;
    readonly enabled = true;
    constructor(
      name: string,
      comment: string,
      source: AuditComp | AuditFootage,
      startTime = 0,
      inPoint = 0,
      outPoint = source instanceof AuditComp ? source.duration : 1
    ) {
      this.name = name;
      this.comment = comment;
      this.source = source;
      this.startTime = startTime;
      this.inPoint = inPoint;
      this.outPoint = outPoint;
    }
    property(matchName: string): object | null {
      return matchName === "ADBE Transform Group" ? { matchName } : null;
    }
  }
  class AuditShapeLayer {
    readonly name: string;
    readonly comment: string;
    readonly enabled = true;
    constructor(name: string, comment: string) {
      this.name = name;
      this.comment = comment;
    }
    property(matchName: string): object | null {
      return matchName === "ADBE Transform Group" ? { matchName } : null;
    }
  }
  class AuditFootage {
    readonly name: string;
    constructor(name: string) { this.name = name; }
  }
  class EmptyClass {}

  const roots: AuditComp[] = [];
  const allComps: AuditComp[] = [];
  for (let index = 0; index < timing.shots.length; index += 1) {
    const shot = timing.shots[index]!;
    const recursiveDuration =
      defect === "wrong-recursive-duration" && index === 12
        ? shot.duration - 1
        : shot.duration;
    const recursive = new AuditComp(
      shot.name + "_v001__Group",
      recursiveDuration,
      "Figma recursive precomp " + shot.figmaNodeId + "::group",
      [new AuditShapeLayer(
        "Native " + String(index + 1),
        "Figma native vector " + shot.figmaNodeId + "::shape rect"
      )]
    );
    const rootLayers: object[] = [
      new AuditAvLayer(
        "Group",
        "Figma group precomp " + shot.figmaNodeId + "::group",
        recursive,
        0,
        0,
        shot.duration
      )
    ];
    if (defect === "unexpected-raster" && index === 20) {
      rootLayers.push(new AuditAvLayer(
        "Unexpected raster",
        "Figma raster fallback " + shot.figmaNodeId + "::raster sha256:" + "d".repeat(64),
        new AuditFootage("unexpected.png")
      ));
    }
    const rootHash = defect === "wrong-hash" && index === 7 ? "e".repeat(64) : hash;
    const root = new AuditComp(
      shot.name + "_v001",
      shot.duration,
      "Video001Export sha256:" + rootHash,
      rootLayers
    );
    roots.push(root);
    allComps.push(recursive, root);
  }
  const masterLayers = timing.shots.map((shot, index) => {
    let source = roots[index]!;
    let start = shot.start;
    if (defect === "wrong-source" && index === 9) source = roots[index + 1]!;
    if (defect === "gap" && index === 18) start += 1;
    if (defect === "overlap" && index === 18) start -= 1;
    return new AuditAvLayer(
      source.name,
      "",
      source,
      start,
      start,
      start + shot.duration
    );
  });
  const master = new AuditComp(
    "VIDEO001_MASTER_v001",
    840,
    "Video001Export sha256:" + hash,
    masterLayers
  );
  const projectItems: Array<AuditComp | FolderItemMock> = [...allComps, master];
  const project = mutationRejectingProxy({
    activeItem: master,
    file: null,
    get numItems() { return projectItems.length; },
    item(index: number) { return projectItems[index - 1]!; }
  }, "fullLessonProject");
  records.set("/bundle/ae/figma-scenes.json", JSON.stringify(timing));
  records.set(
    "/user-data/Video001FigmaAEExporter/import-report-" + hash + ".json",
    JSON.stringify({
      contentHash: hash,
      createdCompNames: roots.map((root) => root.name),
      createdMasterCompName: master.name,
      nativeCount: 96,
      rasterCount: 0,
      missingFonts: [],
      fallbacks: [],
      warnings: []
    })
  );
  const context = {
    $: { fileName: "/bundle/ae/audit-full-lesson.jsx" },
    File: FileMock,
    Folder: FolderMock,
    CompItem: AuditComp,
    AVLayer: AuditAvLayer,
    TextLayer: EmptyClass,
    ShapeLayer: AuditShapeLayer,
    CameraLayer: EmptyClass,
    LightLayer: EmptyClass,
    app: { project }
  };

  vm.runInNewContext(source, context, { filename: sourceUrl.pathname });
  return {
    audit: JSON.parse(output) as {
      contentHash: string;
      itemCountBefore: number;
      itemCountAfter: number;
      projectStateUnchanged: boolean;
      master: {
        durationSeconds: number;
        durationFrames: number;
        layers: Array<Record<string, unknown>>;
      };
      shots: Array<{
        nodeId: string;
        durationSeconds: number;
        durationFrames: number;
        nativeNodeIds: string[];
        hierarchy: { children: unknown[] };
      }>;
    },
    timing
  };
}

test("full-lesson audit traverses all 48 root comps and recursive precomps without mutation", () => {
  const { audit, timing } = runFullLessonAudit();
  const timingById = new Map(timing.shots.map((shot) => [shot.figmaNodeId, shot]));

  assert.equal(audit.master.durationSeconds, 840);
  assert.equal(audit.master.durationFrames, 25_200);
  assert.equal(audit.master.layers.length, 48);
  assert.equal(audit.shots.length, 48);
  assert.ok(audit.shots.every((shot) =>
    shot.durationSeconds === timingById.get(shot.nodeId)!.duration
  ));
  assert.ok(audit.shots.every((shot) => shot.hierarchy.children.length === 1));
  assert.deepEqual(audit.shots[0]!.nativeNodeIds, [
    timing.shots[0]!.figmaNodeId + "::group",
    timing.shots[0]!.figmaNodeId + "::shape"
  ]);
  assert.equal(audit.itemCountBefore, audit.itemCountAfter);
  assert.equal(audit.projectStateUnchanged, true);
});

for (const [defect, expected] of [
  ["gap", /gap|start/i],
  ["overlap", /overlap|start/i],
  ["wrong-source", /source comp/i],
  ["wrong-hash", /content hash/i],
  ["wrong-recursive-duration", /recursive precomp duration/i],
  ["unexpected-raster", /unexpected raster fallback/i],
  ["project-mutation", /project.*change|item-count/i]
] as const) {
  test("full-lesson audit rejects " + defect, () => {
    assert.throws(() => runFullLessonAudit(defect), expected);
  });
}
