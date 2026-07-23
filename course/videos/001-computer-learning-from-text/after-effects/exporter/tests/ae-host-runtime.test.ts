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

function makeImporterHarness(forcedSystemHash?: string, duplicateHash = false) {
  const sourceUrl = new URL("../src/ae/importer.jsxinc", import.meta.url);
  const source = instrumentImporter(readFileSync(sourceUrl, "utf8"));
  const records = new Map<string, FileRecord>();
  const projectItems: FolderItemMock[] = [];
  const removalLog: string[] = [];
  const systemCommands: string[] = [];
  const fontsByPostScriptName = new Map<string, Array<{ postScriptName: string; hasGlyphsFor(value: string): boolean }>>();
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
        return duplicateHash;
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
    canvas: { width: 1920, height: 1080, fps: 30, duration: 840 },
    source: { figmaFileKey: "file-key", figmaPageNodeId: "page-id" },
    shots: [{ figmaNodeId: "1:1", name: "Shot", duration: 30 }]
  });
  const trustedQueuePath = "/user-data/Video001FigmaAEExporter";
  const assetRoot = new FolderMock(trustedQueuePath + "/assets");
  const reportFolder = new FolderMock(trustedQueuePath);

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
    }
  };
}

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
  const harness = makeImporterHarness();
  const packageFile = harness.put(
    "/manual/rollback.video001-ae.json",
    stampCanonicalContentHash(harness.validPackage())
  );

  assert.throws(
    () => harness.importer.importPackageFile(packageFile, harness.options(false)),
    /layers|addShape/
  );

  assert.equal(harness.beginUndoCount, 1);
  assert.deepEqual(harness.removalLog, ["Shot_v001", "v001", "Shot", "01_Exporter_Imports"]);
  assert.equal(harness.preexisting.removed, false);
  assert.deepEqual(
    harness.projectItems.filter((item) => !item.removed).map((item) => item.name),
    ["preexisting"]
  );
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
    missingFonts: string[];
    rasterFallbacks: Array<{ type: string; property: string }>;
    layers: Array<{ name: string; text: string; font: string; boxDimensions: number[] }>;
  };
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
