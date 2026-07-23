import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { createContext, runInContext, runInNewContext } from "node:vm";
import {
  BRIDGE_BASE_URL,
  BRIDGE_TOKEN_KEY,
  EXPORT_MEDIA_TYPE,
  createController,
  normalizeFigmaNode,
  validateUiToController,
  type ControllerHost,
  type ControllerFetchOptions,
  type ControllerFetchResponse,
  type EmbeddedVideo001Config,
  type FigmaNodeLike
} from "../src/figma/controller.ts";
import {
  createUiController,
  downloadPackage,
  packageFilename,
  validateControllerToUi,
  type UiViewModel
} from "../src/figma/ui.ts";
import { contentFingerprintInput, validatePackage, type ExporterPackage } from "../src/shared/contract.ts";
import { sha256Hex } from "../src/shared/sha256.ts";
import { makeValidPackage } from "./helpers/package.ts";

const PROJECT_ROOT = new URL("../", import.meta.url);

const APPROVED_SECTIONS = [
  { firstShot: 1, lastShot: 4, timingName: "Hook", sectionId: "90:5", sectionName: "02 Shots 01-04 — Hook" },
  { firstShot: 5, lastShot: 9, timingName: "Direct Explanation", sectionId: "90:6", sectionName: "03 Shots 05-09 — Direct Explanation" },
  { firstShot: 10, lastShot: 17, timingName: "Technical Meaning", sectionId: "90:7", sectionName: "04 Shots 10-17 — Technical Meaning" },
  { firstShot: 18, lastShot: 25, timingName: "Tiny Example", sectionId: "90:8", sectionName: "05 Shots 18-25 — Tiny Example" },
  { firstShot: 26, lastShot: 32, timingName: "Repository Walkthrough", sectionId: "90:9", sectionName: "06 Shots 26-32 — Repository Walkthrough" },
  { firstShot: 33, lastShot: 39, timingName: "Live Mini-Lab", sectionId: "90:10", sectionName: "07 Shots 33-39 — Live Mini-Lab" },
  { firstShot: 40, lastShot: 43, timingName: "Common Mistake", sectionId: "90:11", sectionName: "08 Shots 40-43 — Common Mistake" },
  { firstShot: 44, lastShot: 48, timingName: "Recap and Exercise", sectionId: "90:12", sectionName: "09 Shots 44-48 — Recap & Exercise" }
] as const;

function approvedTimingSource(): string {
  return join(fileURLToPath(PROJECT_ROOT), "config", "video001-figma-scenes.json");
}

const config: EmbeddedVideo001Config = {
  source: {
    fileKey: "fFTux3sx2AzVQtoya67f95",
    pageId: "90:2"
  },
  target: { width: 1920, height: 1080, fps: 30, timeUnit: "seconds" },
  shots: [
    {
      index: 1,
      nodeId: "94:2",
      name: "S001_SH01_Hook_CatWord",
      duration: 8,
      sectionId: "90:5",
      sectionName: "02 Shots 01-04 — Hook"
    },
    {
      index: 31,
      nodeId: "95:41",
      name: "S001_SH31_Repo_PrepareRecord",
      duration: 27,
      sectionId: "90:9",
      sectionName: "06 Shots 26-32 — Repository Walkthrough"
    },
    {
      index: 32,
      nodeId: "95:44",
      name: "S001_SH32_Repo_PreparationNotLearning",
      duration: 28,
      sectionId: "90:9",
      sectionName: "06 Shots 26-32 — Repository Walkthrough"
    }
  ]
};

interface CanonicalTimingFixture {
  source: { figmaFileKey: string; figmaPageNodeId: string };
  canvas: { width: number; height: number; fps: number; timeUnit: "seconds" };
  shots: Array<{ index: number; figmaNodeId: string; name: string; duration: number }>;
}

const canonicalTimingFixture = JSON.parse(
  readFileSync(approvedTimingSource(), "utf8")
) as CanonicalTimingFixture;

const fullConfig: EmbeddedVideo001Config = {
  source: {
    fileKey: canonicalTimingFixture.source.figmaFileKey,
    pageId: canonicalTimingFixture.source.figmaPageNodeId
  },
  target: {
    width: canonicalTimingFixture.canvas.width,
    height: canonicalTimingFixture.canvas.height,
    fps: canonicalTimingFixture.canvas.fps,
    timeUnit: canonicalTimingFixture.canvas.timeUnit
  },
  shots: canonicalTimingFixture.shots.map((shot) => {
    const section = APPROVED_SECTIONS.find(
      ({ firstShot, lastShot }) => shot.index >= firstShot && shot.index <= lastShot
    );
    assert.ok(section, `missing approved section fixture for shot ${shot.index}`);
    return {
      index: shot.index,
      nodeId: shot.figmaNodeId,
      name: shot.name,
      duration: shot.duration,
      sectionId: section.sectionId,
      sectionName: section.sectionName
    };
  })
};

function solidPaint(): { type: "SOLID"; color: { r: number; g: number; b: number }; opacity: number; visible: true } {
  return { type: "SOLID", color: { r: 0.1, g: 0.2, b: 0.3 }, opacity: 1, visible: true };
}

function sceneNode(overrides: Partial<FigmaNodeLike> = {}): FigmaNodeLike {
  return {
    id: "95:44",
    name: "S001_SH32_Repo_PreparationNotLearning",
    type: "FRAME",
    width: 1920,
    height: 1080,
    opacity: 1,
    visible: true,
    absoluteTransform: [[1, 0, 0], [0, 1, 0]],
    fills: [],
    strokes: [],
    effects: [],
    blendMode: "NORMAL",
    isMask: false,
    children: [{
      id: "shape-1",
      name: "BG_Base",
      type: "RECTANGLE",
      width: 1920,
      height: 1080,
      opacity: 1,
      visible: true,
      absoluteTransform: [[1, 0, 0], [0, 1, 0]],
      fills: [solidPaint()],
      strokes: [],
      strokeWeight: 0,
      cornerRadius: 0,
      effects: [],
      blendMode: "NORMAL",
      isMask: false,
      exportAsync: async () => new Uint8Array([137, 80, 78, 71])
    }],
    exportAsync: async () => new Uint8Array([137, 80, 78, 71]),
    ...overrides
  };
}

function documentedFigmaFetchResponse(body: string, status: number): ControllerFetchResponse {
  const bytes = Buffer.from(body, "utf8");
  const arrayBuffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  return {
    headersObject: { "content-length": String(bytes.byteLength), "content-type": "application/json" },
    ok: status >= 200 && status < 300,
    redirected: false,
    status,
    statusText: "",
    type: "basic",
    url: BRIDGE_BASE_URL,
    arrayBuffer: async () => arrayBuffer,
    text: async () => body,
    json: async () => JSON.parse(body)
  };
}

interface HostHarness {
  host: ControllerHost;
  messages: unknown[];
  nodes: Map<string, FigmaNodeLike>;
  requests: Array<{ input: string; init?: ControllerFetchOptions }>;
  storage: Map<string, unknown>;
  setSelection(nodes: FigmaNodeLike[]): void;
}

function hostHarness(
  fetchResponses: ControllerFetchResponse[] = [],
  nodes: Map<string, FigmaNodeLike> = new Map()
): HostHarness {
  const page = { id: "90:2", selection: [] as FigmaNodeLike[] };
  const messages: unknown[] = [];
  const requests: Array<{ input: string; init?: ControllerFetchOptions }> = [];
  const storage = new Map<string, unknown>();
  return {
    messages,
    nodes,
    requests,
    storage,
    setSelection(nodes): void {
      page.selection = nodes;
      for (const node of nodes) {
        const timing = config.shots.find((shot) => shot.nodeId === node.id) ?? config.shots.at(-1)!;
        node.parent = {
          id: timing.sectionId,
          name: timing.sectionName,
          type: "SECTION",
          parent: { id: page.id, name: "02 Video 001 - AE Assets", type: "PAGE" }
        };
      }
    },
    host: {
      fileKey: "fFTux3sx2AzVQtoya67f95",
      getCurrentPage: () => page,
      getNodeByIdAsync: async (nodeId) => nodes.get(nodeId) ?? null,
      postMessage: (message) => messages.push(structuredClone(message)),
      closePlugin: () => undefined,
      now: () => new Date("2026-07-22T00:00:00.000Z"),
      mixed: Symbol("figma.mixed"),
      clientStorage: {
        getAsync: async (key) => storage.get(key),
        setAsync: async (key, value) => { storage.set(key, value); },
        deleteAsync: async (key) => { storage.delete(key); }
      },
      fetch: async (input, init) => {
        requests.push({ input: String(input), ...(init === undefined ? {} : { init }) });
        const response = fetchResponses.shift();
        if (response === undefined) throw new TypeError("bridge unavailable");
        return response;
      }
    }
  };
}

function fullLessonNodes(): Map<string, FigmaNodeLike> {
  return new Map(fullConfig.shots.map((timing) => [
    timing.nodeId,
    sceneNode({
      id: timing.nodeId,
      name: timing.name,
      children: [sceneNode({
        id: `${timing.nodeId}:background`,
        name: "BG_Base",
        type: "RECTANGLE",
        children: undefined
      })],
      parent: {
        id: timing.sectionId,
        name: timing.sectionName,
        type: "SECTION",
        parent: { id: fullConfig.source.pageId, name: "02 Video 001 - AE Assets", type: "PAGE" }
      }
    })
  ]));
}

function lastFailure(messages: unknown[]): { type: string; code: string; message: string } {
  const value = messages.at(-1);
  assert.equal(typeof value, "object");
  return value as { type: string; code: string; message: string };
}

function deferred<T>(): {
  promise: Promise<T>;
  resolve(value: T): void;
} {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

test("selection refresh reports empty, non-frame, unknown, and over-limit selections safely", async () => {
  const harness = hostHarness();
  const controller = createController(harness.host, config);

  await controller.handleMessage({ type: "refresh-selection" });
  assert.equal(lastFailure(harness.messages).code, "NO_FRAME_SELECTED");

  harness.setSelection([sceneNode({ type: "RECTANGLE" })]);
  await controller.handleMessage({ type: "refresh-selection" });
  assert.equal(lastFailure(harness.messages).code, "SELECTION_NOT_FRAME");

  harness.setSelection([sceneNode({ id: "999:999" })]);
  await controller.handleMessage({ type: "refresh-selection" });
  assert.equal(lastFailure(harness.messages).code, "SHOT_TIMING_NOT_FOUND");

  harness.setSelection(Array.from({ length: 49 }, (_, index) => sceneNode({ id: index === 0 ? "94:2" : `94:${index + 2}` })));
  await controller.handleMessage({ type: "refresh-selection" });
  assert.equal(lastFailure(harness.messages).code, "TOO_MANY_FRAMES");
});

test("selection rejects the wrong lesson source before looking up unconfigured frame timing", async () => {
  const harness = hostHarness();
  harness.host.fileKey = "wrong-file";
  harness.setSelection([sceneNode({ id: "999:999" })]);
  const controller = createController(harness.host, config);

  await controller.handleMessage({ type: "refresh-selection" });

  assert.equal(lastFailure(harness.messages).code, "WRONG_LESSON_SOURCE");
});

test("selection accepts only exact approved section ancestry by identifier", async () => {
  const harness = hostHarness();
  const shot31 = sceneNode({ id: "95:41", name: "S001_SH31_Repo_PrepareRecord" });
  harness.setSelection([shot31]);
  const controller = createController(harness.host, config);

  await controller.handleMessage({ type: "refresh-selection" });
  assert.deepEqual(harness.messages.at(-1), {
    type: "selection",
    generation: 1,
    frames: [{ nodeId: "95:41", name: "S001_SH31_Repo_PrepareRecord", duration: 27 }]
  });

  const rejectParent = async (parent: unknown): Promise<void> => {
    const node = sceneNode({ id: "95:41", name: "S001_SH31_Repo_PrepareRecord", parent });
    harness.host.getCurrentPage().selection = [node];
    await controller.handleMessage({ type: "refresh-selection" });
    const failure = lastFailure(harness.messages);
    assert.equal(failure.code, "SELECTION_NOT_IN_APPROVED_SECTION");
    assert.match(failure.message, /direct child/i);
    assert.match(failure.message, /90:9/);
    assert.match(failure.message, /06 Shots 26-32 — Repository Walkthrough/);
  };

  await rejectParent(harness.host.getCurrentPage());
  await rejectParent({
    id: "90:9",
    name: "06 Shots 26-32 — Repository Walkthrough",
    type: "GROUP",
    parent: { id: "90:2", type: "PAGE" }
  });
  await rejectParent({
    id: "90:8",
    name: "06 Shots 26-32 — Repository Walkthrough",
    type: "SECTION",
    parent: { id: "90:2", type: "PAGE" }
  });
  await rejectParent({
    id: "90:9",
    name: "Wrong section name",
    type: "SECTION",
    parent: { id: "90:2", type: "PAGE" }
  });
  await rejectParent({
    id: "90:9",
    name: "06 Shots 26-32 — Repository Walkthrough",
    type: "SECTION",
    parent: { id: "nested-group", type: "GROUP", parent: { id: "90:2", type: "PAGE" } }
  });
});

test("full lesson resolves all 48 configured shots in order without changing the user's selection", async () => {
  assert.equal(fullConfig.shots.length, 48);
  const harness = hostHarness([], fullLessonNodes());
  harness.setSelection([sceneNode()]);
  const controller = createController(harness.host, fullConfig);

  await controller.handleMessage({ type: "build-full-lesson" });

  const selection = harness.messages.find((value) =>
    (value as { type?: string }).type === "selection"
  ) as { frames: Array<{ nodeId: string }> };
  assert.deepEqual(selection.frames.map((frame) => frame.nodeId), fullConfig.shots.map((shot) => shot.nodeId));
  assert.equal(harness.host.getCurrentPage().selection.length, 1, "full build changed the user's selection");
  const packageMessage = harness.messages.find((value) =>
    (value as { type?: string }).type === "package-unhashed"
  ) as { generation: number; value: ExporterPackage } | undefined;
  assert.ok(packageMessage, JSON.stringify(harness.messages));
  assert.equal(packageMessage.generation, 1, "one request incremented the package generation more than once");
  assert.equal(packageMessage.value.schemaVersion, "2.0.0");
  assert.equal(packageMessage.value.target.timeUnit, "seconds");
  assert.deepEqual(packageMessage.value.frames.map((frame) => frame.nodeId), fullConfig.shots.map((shot) => shot.nodeId));
});

test("full lesson fails when a configured shot node is unavailable", async () => {
  const nodes = fullLessonNodes();
  const missing = fullConfig.shots[17]!;
  nodes.delete(missing.nodeId);
  const harness = hostHarness([], nodes);
  const controller = createController(harness.host, fullConfig);

  await controller.handleMessage({ type: "build-full-lesson" });

  const failure = lastFailure(harness.messages);
  assert.equal(failure.code, "SHOT_NODE_NOT_FOUND");
  assert.equal(failure.message, `Shot ${missing.index} node ${missing.nodeId} is unavailable.`);
});

test("full lesson fails when a shot is not a direct child of its approved SECTION", async () => {
  const nodes = fullLessonNodes();
  const timing = fullConfig.shots[9]!;
  nodes.get(timing.nodeId)!.parent = {
    id: "nested-group",
    name: "Nested",
    type: "GROUP",
    parent: {
      id: timing.sectionId,
      name: timing.sectionName,
      type: "SECTION",
      parent: { id: fullConfig.source.pageId, type: "PAGE" }
    }
  };
  const harness = hostHarness([], nodes);
  const controller = createController(harness.host, fullConfig);

  await controller.handleMessage({ type: "build-full-lesson" });

  assert.equal(lastFailure(harness.messages).code, "SELECTION_NOT_IN_APPROVED_SECTION");
});

test("full lesson fails when an approved SECTION belongs to the wrong PAGE", async () => {
  const nodes = fullLessonNodes();
  const timing = fullConfig.shots[10]!;
  nodes.get(timing.nodeId)!.parent = {
    id: timing.sectionId,
    name: timing.sectionName,
    type: "SECTION",
    parent: { id: "wrong-page", type: "PAGE" }
  };
  const harness = hostHarness([], nodes);
  const controller = createController(harness.host, fullConfig);

  await controller.handleMessage({ type: "build-full-lesson" });

  assert.equal(lastFailure(harness.messages).code, "SELECTION_NOT_IN_APPROVED_SECTION");
});

test("full lesson fails when a configured shot name has drifted", async () => {
  const nodes = fullLessonNodes();
  const timing = fullConfig.shots[11]!;
  nodes.get(timing.nodeId)!.name = "Renamed shot";
  const harness = hostHarness([], nodes);
  const controller = createController(harness.host, fullConfig);

  await controller.handleMessage({ type: "build-full-lesson" });

  assert.equal(lastFailure(harness.messages).code, "SHOT_NAME_MISMATCH");
});

test("full lesson fails when a configured shot has the wrong dimensions", async () => {
  const nodes = fullLessonNodes();
  const timing = fullConfig.shots[12]!;
  nodes.get(timing.nodeId)!.width = 1919;
  const harness = hostHarness([], nodes);
  const controller = createController(harness.host, fullConfig);

  await controller.handleMessage({ type: "build-full-lesson" });

  assert.equal(lastFailure(harness.messages).code, "SHOT_DIMENSIONS_MISMATCH");
});

test("full lesson discards a stale generation during raster export", async () => {
  const rasterStarted = deferred<void>();
  const rasterBytes = deferred<Uint8Array>();
  const nodes = fullLessonNodes();
  const first = fullConfig.shots[0]!;
  const firstNode = nodes.get(first.nodeId)!;
  firstNode.opacity = 0.5;
  firstNode.exportAsync = async () => {
    rasterStarted.resolve();
    return rasterBytes.promise;
  };
  const harness = hostHarness([], nodes);
  harness.setSelection([sceneNode()]);
  const controller = createController(harness.host, fullConfig);

  const staleBuild = controller.handleMessage({ type: "build-full-lesson" });
  const started = await Promise.race([
    rasterStarted.promise.then(() => true),
    staleBuild.then(() => false)
  ]);
  assert.equal(started, true, "full build did not reach raster export");
  await controller.handleMessage({ type: "refresh-selection" });
  rasterBytes.resolve(new Uint8Array([137, 80, 78, 71]));
  await staleBuild;

  const stalePackages = harness.messages.filter((value) =>
    (value as { type?: string; generation?: number }).type === "package-unhashed" &&
    (value as { generation?: number }).generation === 1
  );
  assert.equal(stalePackages.length, 0);
});

test("full lesson rejects a configuration larger than the 48-frame package limit", async () => {
  const extraTiming = {
    ...fullConfig.shots.at(-1)!,
    index: 49,
    nodeId: "95:95",
    name: "S001_SH49_Invalid"
  };
  const oversizedConfig = { ...fullConfig, shots: [...fullConfig.shots, extraTiming] };
  const nodes = fullLessonNodes();
  nodes.set(extraTiming.nodeId, sceneNode({
    id: extraTiming.nodeId,
    name: extraTiming.name,
    parent: {
      id: extraTiming.sectionId,
      name: extraTiming.sectionName,
      type: "SECTION",
      parent: { id: fullConfig.source.pageId, type: "PAGE" }
    }
  }));
  const harness = hostHarness([], nodes);
  const controller = createController(harness.host, oversizedConfig);

  await controller.handleMessage({ type: "build-full-lesson" });

  assert.equal(lastFailure(harness.messages).code, "TOO_MANY_FRAMES");
});

test("full lesson rejects a configuration smaller than the required 48-shot set", async () => {
  const undersizedConfig = { ...fullConfig, shots: fullConfig.shots.slice(0, -1) };
  assert.equal(undersizedConfig.shots.length, 47);
  const harness = hostHarness([], fullLessonNodes());
  const controller = createController(harness.host, undersizedConfig);

  await controller.handleMessage({ type: "build-full-lesson" });

  const failure = lastFailure(harness.messages);
  assert.equal(failure.code, "FULL_LESSON_SHOT_COUNT_MISMATCH");
  assert.equal(failure.message, "Full-lesson builds require exactly 48 configured shots; received 47.");
  assert.equal(harness.messages.some((value) =>
    (value as { type?: string }).type === "package-unhashed"
  ), false);
});

test("Shot 32 maps node 95:44 to the exact frame name and 28-second duration", async () => {
  const harness = hostHarness();
  harness.setSelection([sceneNode()]);
  const controller = createController(harness.host, config);
  await controller.handleMessage({ type: "refresh-selection" });
  assert.deepEqual(harness.messages.at(-1), {
    type: "selection",
    generation: 1,
    frames: [{ nodeId: "95:44", name: "S001_SH32_Repo_PreparationNotLearning", duration: 28 }]
  });

  await controller.handleMessage({ type: "build-package" });
  const message = harness.messages.at(-1) as { type: string; value: ExporterPackage };
  assert.equal(message.type, "package-unhashed");
  assert.equal(message.value.contentHash, "");
  assert.equal(message.value.frames[0]?.duration, 28);
  assert.equal(message.value.frames[0]?.name, "S001_SH32_Repo_PreparationNotLearning");
  assert.equal(contentFingerprintInput(message.value).length > 0, true);
});

test("adapter preserves exact transforms and requested text fields and falls back for AUTO/mixed paragraph values", async () => {
  const requests: unknown[] = [];
  const text = sceneNode({
    id: "text-1",
    name: "TXT_Title",
    type: "TEXT",
    width: 420,
    height: 120,
    absoluteTransform: [[0, -1, 300], [1, 0, 200]],
    fills: [solidPaint()],
    strokes: [],
    characters: "θ · →",
    textAlignHorizontal: "RIGHT",
    lineHeight: { unit: "PIXELS", value: 58 },
    letterSpacing: { unit: "PIXELS", value: 1.25 },
    getStyledTextSegments: (fields) => {
      requests.push(fields);
      return [{
        characters: "θ · →",
        start: 0,
        end: 5,
        fontName: { family: "Sora", style: "Bold" },
        fontSize: 64,
        fills: [solidPaint()]
      }];
    },
    children: undefined
  });
  const normalized = normalizeFigmaNode(text, Symbol("mixed"));
  assert.deepEqual(requests, [["fontName", "fontSize", "fills"]]);
  assert.deepEqual(normalized.absoluteTransform, [[0, -1, 300], [1, 0, 200]]);
  assert.equal(normalized.characters, "θ · →");
  assert.equal(normalized.textAlignHorizontal, "RIGHT");
  assert.equal(normalized.lineHeightPx, 58);
  assert.equal(normalized.letterSpacingPx, 1.25);
  assert.deepEqual(normalized.styledTextSegments?.[0], {
    start: 0,
    end: 5,
    fontName: { family: "Sora", style: "Bold" },
    fontSize: 64,
    fills: [solidPaint()]
  });

  const auto = normalizeFigmaNode({ ...text, lineHeight: { unit: "AUTO" } }, Symbol("mixed"));
  assert.equal(auto.lineHeightPx, undefined);
  const mixed = Symbol("figma.mixed");
  const mixedNode = normalizeFigmaNode({ ...text, letterSpacing: mixed }, mixed);
  assert.equal(mixedNode.letterSpacingPx, undefined);
});

test("raster export is serializer-classified, SCALE=1, sequential, byte-exact, and hash-deduplicated", async () => {
  const bytes = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10, 42]);
  const calls: Array<{ id: string; settings: unknown; active: number }> = [];
  let active = 0;
  let maximumActive = 0;
  const raster = (id: string): FigmaNodeLike => sceneNode({
    id,
    name: `FX_${id.replace(":", "_")}`,
    type: "RECTANGLE",
    width: 100,
    height: 100,
    fills: [{ type: "GRADIENT_LINEAR", visible: true }],
    children: undefined,
    exportAsync: async (settings) => {
      active += 1;
      maximumActive = Math.max(maximumActive, active);
      calls.push({ id, settings, active });
      await Promise.resolve();
      active -= 1;
      return bytes;
    }
  });
  const native = sceneNode({
    id: "native",
    name: "DATA_Native",
    type: "RECTANGLE",
    width: 10,
    height: 10,
    fills: [solidPaint()],
    children: undefined
  });
  let nativeExported = false;
  native.exportAsync = async () => {
    nativeExported = true;
    return bytes;
  };
  const root = sceneNode({ children: [raster("raster:1"), native, raster("raster:2")] });
  const harness = hostHarness();
  harness.setSelection([root]);
  const controller = createController(harness.host, config);
  await controller.handleMessage({ type: "build-package" });
  const message = harness.messages.at(-1) as { type: string; value: ExporterPackage };
  assert.equal(message.type, "package-unhashed");
  assert.equal(maximumActive, 1);
  assert.equal(nativeExported, false);
  assert.deepEqual(calls.map(({ id }) => id), ["raster:1", "raster:2"]);
  assert.deepEqual(calls.map(({ settings }) => settings), [
    { format: "PNG", constraint: { type: "SCALE", value: 1 } },
    { format: "PNG", constraint: { type: "SCALE", value: 1 } }
  ]);
  assert.equal(message.value.assets.length, 1);
  assert.equal(message.value.assets[0]?.hash, createHash("sha256").update(bytes).digest("hex"));
  assert.equal(message.value.assets[0]?.byteLength, bytes.byteLength);
  assert.deepEqual(Buffer.from(message.value.assets[0]!.dataBase64, "base64"), Buffer.from(bytes));
  assert.equal(message.value.frames[0]?.children[0]?.opacity, 1, "BAKED raster appearance must not be reapplied");
});

test("a visible stroke with figma.mixed weight is rasterized instead of reaching native serialization", async () => {
  const harness = hostHarness();
  let rasterExports = 0;
  const stroked = sceneNode({
    id: "mixed-stroke",
    name: "DATA_MixedStroke",
    type: "RECTANGLE",
    width: 100,
    height: 100,
    fills: [solidPaint()],
    strokes: [solidPaint()],
    strokeWeight: harness.host.mixed,
    children: undefined,
    exportAsync: async () => {
      rasterExports += 1;
      return new Uint8Array([137, 80, 78, 71]);
    }
  });
  harness.setSelection([sceneNode({ children: [stroked] })]);
  const controller = createController(harness.host, config);

  await controller.handleMessage({ type: "build-package" });

  const message = harness.messages.at(-1) as { type: string; value: ExporterPackage };
  assert.equal(message.type, "package-unhashed");
  assert.equal(rasterExports, 1);
  assert.equal(message.value.frames[0]?.children[0]?.kind, "raster");
  assert.equal(message.value.frames[0]?.warnings[0]?.property, "strokeWeight");
});

test("controller discards a stale raster build after a newer build generation completes", async () => {
  const firstRaster = deferred<Uint8Array>();
  let exportCount = 0;
  const node = sceneNode({
    opacity: 0.5,
    exportAsync: async () => {
      exportCount += 1;
      if (exportCount === 1) return firstRaster.promise;
      return new Uint8Array([2]);
    }
  });
  const harness = hostHarness();
  harness.setSelection([node]);
  const controller = createController(harness.host, config);

  const staleBuild = controller.handleMessage({ type: "build-package" });
  await Promise.resolve();
  const currentBuild = controller.handleMessage({ type: "build-package" });
  await currentBuild;
  firstRaster.resolve(new Uint8Array([1]));
  await staleBuild;

  const packages = harness.messages.filter((message): message is { type: "package-unhashed"; generation: number; value: ExporterPackage } =>
    typeof message === "object" && message !== null && "type" in message && message.type === "package-unhashed"
  );
  assert.equal(packages.length, 1);
  assert.equal(packages[0]?.generation, 2);
  assert.equal(packages[0]?.value.assets[0]?.dataBase64, "Ag==");
});

test("both protocol boundaries reject unknown keys, invalid types, and exotic prototypes", () => {
  assert.deepEqual(validateUiToController({ type: "build-full-lesson" }), { type: "build-full-lesson" });
  assert.throws(() => validateUiToController({ type: "build-full-lesson", extra: true }), /unknown field/i);
  assert.throws(() => validateUiToController({ type: "send-live", token: "secret" }), /unknown field/i);
  assert.throws(() => validateUiToController({ type: "pair", operation: 1, code: "12345" }), /pairing code/i);
  const inherited = Object.create({ polluted: true }) as Record<string, unknown>;
  inherited.type = "close";
  assert.throws(() => validateUiToController(inherited), /plain object/i);

  assert.throws(() => validateControllerToUi({ type: "selection", frames: [], token: "secret" }), /unknown field/i);
  assert.throws(() => validateControllerToUi({
    type: "bridge-result",
    operation: 1,
    status: -1,
    code: "X",
    message: "bad"
  }), /status/i);
});

test("plugin protocol uses Figma's documented localhost development origin", () => {
  assert.equal(BRIDGE_BASE_URL, "http://localhost:3456");
});

async function hashedPackage(): Promise<ExporterPackage> {
  const value = makeValidPackage();
  value.contentHash = "";
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(contentFingerprintInput(value)));
  value.contentHash = Buffer.from(digest).toString("hex");
  return validatePackage(value);
}

test("UI hashes with pure SHA-256 parity, returns only package-ready, exposes counts, and downloads exact UTF-8 vendor bytes", async () => {
  const posted: unknown[] = [];
  const views: UiViewModel[] = [];
  const downloads: Array<{ bytes: Uint8Array; filename: string; mimeType: string }> = [];
  const ui = createUiController({
    postMessage: (message) => posted.push(structuredClone(message)),
    render: (view) => views.push(structuredClone(view)),
    sha256: async (bytes) => sha256Hex(bytes),
    download: (value) => downloads.push(value)
  });
  const unhashed = makeValidPackage();
  unhashed.contentHash = "";
  await ui.handleMessage({
    type: "selection",
    generation: 1,
    frames: [{ nodeId: "95:44", name: unhashed.frames[0]!.name, duration: 28 }]
  });
  await ui.handleMessage({ type: "package-unhashed", generation: 1, value: unhashed });
  const ready = posted.at(-1) as { type: string; generation: number; value: ExporterPackage };
  assert.equal(ready.type, "package-ready");
  assert.equal(ready.generation, 1);
  const nodeHash = createHash("sha256").update(contentFingerprintInput(unhashed), "utf8").digest("hex");
  assert.equal(ready.value.contentHash, nodeHash);
  assert.deepEqual(validatePackage(ready.value), ready.value);
  assert.equal(views.at(-1)?.nativeCount, 1);
  assert.equal(views.at(-1)?.rasterCount, 0);
  assert.equal(views.at(-1)?.downloadDisabled, false);

  ui.download();
  assert.equal(downloads.length, 1);
  assert.equal(downloads[0]?.mimeType, EXPORT_MEDIA_TYPE);
  assert.equal(downloads[0]?.filename, `S001_SH32_Repo_PreparationNotLearning-${nodeHash.slice(0, 12)}.video001-ae.json`);
  assert.deepEqual(JSON.parse(new TextDecoder().decode(downloads[0]?.bytes)), ready.value);
});

test("UI starts a full-lesson build independently of selected-frame availability", async () => {
  const posted: unknown[] = [];
  const views: UiViewModel[] = [];
  const ui = createUiController({
    postMessage: (message) => posted.push(structuredClone(message)),
    render: (view) => views.push(structuredClone(view)),
    sha256: async (bytes) => sha256Hex(bytes),
    download: () => undefined
  });

  ui.buildFullLesson();

  assert.deepEqual(posted, [{ type: "build-full-lesson" }]);
  assert.equal(views.at(-1)?.busy, true);
  assert.equal(views.at(-1)?.buildDisabled, true);
  assert.match(readFileSync(new URL("../src/figma/ui.html", import.meta.url), "utf8"), /<button id="build-full-lesson" type="button">Build full lesson \(48 shots\)<\/button>/);
});

test("UI discards a stale hash after a newer selection and package generation", async () => {
  const firstHash = deferred<string>();
  let digestCount = 0;
  const posted: unknown[] = [];
  const views: UiViewModel[] = [];
  const ui = createUiController({
    postMessage: (message) => posted.push(structuredClone(message)),
    render: (view) => views.push(structuredClone(view)),
    sha256: async (bytes) => {
      digestCount += 1;
      if (digestCount === 1) return firstHash.promise;
      return sha256Hex(bytes);
    },
    download: () => undefined
  });
  const stale = makeValidPackage();
  stale.contentHash = "";
  const current = makeValidPackage();
  current.contentHash = "";
  current.exportedAt = "2026-07-22T00:00:01.000Z";

  await ui.handleMessage({
    type: "selection",
    generation: 1,
    frames: [{ nodeId: "95:44", name: stale.frames[0]!.name, duration: 28 }]
  });
  const staleHash = ui.handleMessage({ type: "package-unhashed", generation: 1, value: stale });
  await Promise.resolve();
  await ui.handleMessage({
    type: "selection",
    generation: 2,
    frames: [{ nodeId: "95:44", name: current.frames[0]!.name, duration: 28 }]
  });
  await ui.handleMessage({ type: "package-unhashed", generation: 2, value: current });
  firstHash.resolve("0".repeat(64));
  await staleHash;

  const readyMessages = posted.filter((message): message is { type: "package-ready"; generation: number; value: ExporterPackage } =>
    typeof message === "object" && message !== null && "type" in message && message.type === "package-ready"
  );
  assert.equal(readyMessages.length, 1);
  assert.equal(readyMessages[0]?.generation, 2);
  assert.equal(readyMessages[0]?.value.exportedAt, current.exportedAt);
  assert.equal(views.at(-1)?.packageReady, true);
});

test("UI gates bridge actions with matching operation generations and a busy state", async () => {
  const posted: unknown[] = [];
  const views: UiViewModel[] = [];
  const ui = createUiController({
    postMessage: (message) => posted.push(structuredClone(message)),
    render: (view) => views.push(structuredClone(view)),
    sha256: async (bytes) => sha256Hex(bytes),
    download: () => undefined
  });

  ui.pair("123456");
  assert.deepEqual(posted.at(-1), { type: "pair", operation: 1, code: "123456" });
  assert.equal(views.at(-1)?.busy, true);
  ui.send();
  assert.equal(posted.length, 1, "a second bridge action must not be posted while pairing is active");

  await ui.handleMessage({
    type: "bridge-result",
    operation: 1,
    status: 200,
    code: "PAIRED",
    message: "Paired with After Effects."
  });
  assert.equal(views.at(-1)?.busy, false);
});

test("downloadPackage uses a UTF-8 vendor Blob and deterministic safe filename", async () => {
  const value = await hashedPackage();
  const captured: Array<{ blob: Blob; filename: string }> = [];
  downloadPackage(value, (blob, filename) => captured.push({ blob, filename }));
  assert.equal(captured[0]?.blob.type, EXPORT_MEDIA_TYPE);
  assert.equal(captured[0]?.filename, packageFilename(value));
  assert.equal(await captured[0]?.blob.text(), JSON.stringify(value));
});

test("controller validates package-ready state, pairs and sends exact requests, never posts a token, and clears token on 401", async () => {
  const token = "A".repeat(43);
  const harness = hostHarness([
    documentedFigmaFetchResponse(JSON.stringify({ token }), 200),
    documentedFigmaFetchResponse(JSON.stringify({ error: { code: "UNAUTHORIZED", message: "Expired" } }), 401)
  ]);
  harness.setSelection([sceneNode()]);
  const controller = createController(harness.host, config);

  await controller.handleMessage({ type: "refresh-selection" });
  await controller.handleMessage({ type: "package-ready", generation: 1, value: await hashedPackage() });
  assert.equal(lastFailure(harness.messages).code, "PACKAGE_NOT_PENDING");

  await controller.handleMessage({ type: "build-package" });
  const pendingMessage = harness.messages.at(-1) as { generation: number; value: ExporterPackage };
  const pending = pendingMessage.value;
  const finalValue = structuredClone(pending);
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(contentFingerprintInput(finalValue)));
  finalValue.contentHash = Buffer.from(digest).toString("hex");
  await controller.handleMessage({ type: "package-ready", generation: pendingMessage.generation, value: finalValue });

  await controller.handleMessage({ type: "pair", operation: 1, code: "123456" });
  assert.equal(harness.requests[0]?.input, `${BRIDGE_BASE_URL}/v1/pair`);
  assert.equal(harness.requests[0]?.init?.method, "POST");
  assert.deepEqual(harness.requests[0]?.init?.headers, { "Content-Type": "application/json" });
  assert.equal(harness.requests[0]?.init?.body, JSON.stringify({ code: "123456" }));
  assert.equal(harness.storage.get(BRIDGE_TOKEN_KEY), token);
  assert.equal(JSON.stringify(harness.messages).includes(token), false);

  await controller.handleMessage({ type: "send-live", operation: 2 });
  assert.equal(harness.requests[1]?.input, `${BRIDGE_BASE_URL}/v1/export`);
  assert.equal(harness.requests[1]?.init?.method, "POST");
  assert.deepEqual(harness.requests[1]?.init?.headers, {
    Authorization: `Bearer ${token}`,
    "Content-Type": EXPORT_MEDIA_TYPE
  });
  assert.equal(harness.requests[1]?.init?.body, JSON.stringify(finalValue));
  assert.equal(harness.storage.has(BRIDGE_TOKEN_KEY), false);
  assert.deepEqual(harness.messages.at(-1), {
    type: "bridge-result",
    operation: 2,
    status: 401,
    code: "UNAUTHORIZED",
    message: "Expired"
  });
  assert.equal(JSON.stringify(harness.messages).includes(token), false);
});

test("controller rejects a concurrent bridge action while the first request is in flight", async () => {
  const pendingResponse = deferred<ControllerFetchResponse>();
  const harness = hostHarness();
  harness.host.fetch = async (input, init) => {
    harness.requests.push({ input: String(input), ...(init === undefined ? {} : { init }) });
    return pendingResponse.promise;
  };
  const controller = createController(harness.host, config);

  const first = controller.handleMessage({ type: "pair", operation: 1, code: "123456" });
  await Promise.resolve();
  await controller.handleMessage({ type: "pair", operation: 2, code: "654321" });

  assert.equal(harness.requests.length, 1);
  assert.deepEqual(harness.messages.at(-1), {
    type: "failure",
    operation: 2,
    code: "BRIDGE_BUSY",
    message: "Wait for the active bridge operation to finish."
  });
  pendingResponse.resolve(documentedFigmaFetchResponse(JSON.stringify({ token: "A".repeat(43) }), 200));
  await first;
});

test("pairing accepts only the bridge's exact 200 response and canonical 32-byte base64url token", async () => {
  const invalidToken = hostHarness([
    documentedFigmaFetchResponse(JSON.stringify({ token: "bridge-token-not-for-ui" }), 200)
  ]);
  const first = createController(invalidToken.host, config);
  await first.handleMessage({ type: "pair", operation: 1, code: "123456" });
  assert.equal(lastFailure(invalidToken.messages).code, "INVALID_BRIDGE_RESPONSE");
  assert.equal(invalidToken.storage.has(BRIDGE_TOKEN_KEY), false);

  const wrongStatus = hostHarness([
    documentedFigmaFetchResponse(JSON.stringify({ token: "A".repeat(43) }), 201)
  ]);
  const second = createController(wrongStatus.host, config);
  await second.handleMessage({ type: "pair", operation: 1, code: "123456" });
  assert.equal(lastFailure(wrongStatus.messages).code, "INVALID_BRIDGE_RESPONSE");
  assert.equal(wrongStatus.storage.has(BRIDGE_TOKEN_KEY), false);
});

async function makeControllerReady(harness: HostHarness): Promise<ReturnType<typeof createController>> {
  harness.setSelection([sceneNode()]);
  const controller = createController(harness.host, config);
  await controller.handleMessage({ type: "build-package" });
  const pendingMessage = harness.messages.at(-1) as { generation: number; value: ExporterPackage };
  const pending = pendingMessage.value;
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(contentFingerprintInput(pending)));
  const ready = { ...pending, contentHash: Buffer.from(digest).toString("hex") };
  await controller.handleMessage({ type: "package-ready", generation: pendingMessage.generation, value: ready });
  harness.storage.set(BRIDGE_TOKEN_KEY, "A".repeat(43));
  return controller;
}

test("a selection refresh invalidates the controller's previously ready package", async () => {
  const harness = hostHarness();
  const controller = await makeControllerReady(harness);

  await controller.handleMessage({ type: "refresh-selection" });
  await controller.handleMessage({ type: "send-live", operation: 1 });

  assert.equal(lastFailure(harness.messages).code, "PACKAGE_NOT_READY");
});

test("send deletes only its matching rejected token before awaiting a slow 401 body", async () => {
  const body = deferred<string>();
  const bodyReadStarted = deferred<void>();
  const harness = hostHarness();
  const controller = await makeControllerReady(harness);
  const oldToken = "A".repeat(43);
  const replacementToken = "B".repeat(42) + "A";
  harness.host.fetch = async (input, init) => {
    harness.requests.push({ input: String(input), ...(init === undefined ? {} : { init }) });
    return {
      headersObject: { "content-type": "application/json" },
      status: 401,
      ok: false,
      redirected: false,
      statusText: "Unauthorized",
      type: "basic",
      url: BRIDGE_BASE_URL + "/v1/export",
      arrayBuffer: async () => {
        bodyReadStarted.resolve(undefined);
        const value = Buffer.from(await body.promise, "utf8");
        return value.buffer.slice(value.byteOffset, value.byteOffset + value.byteLength);
      },
      json: async () => JSON.parse(await body.promise),
      text: () => {
        bodyReadStarted.resolve(undefined);
        return body.promise;
      }
    };
  };

  const send = controller.handleMessage({ type: "send-live", operation: 1 });
  await bodyReadStarted.promise;
  assert.equal(harness.storage.has(BRIDGE_TOKEN_KEY), false, "the rejected token must be removed before body parsing");
  harness.storage.set(BRIDGE_TOKEN_KEY, replacementToken);
  body.resolve(JSON.stringify({ error: { code: "UNAUTHORIZED", message: "Expired" } }));
  await send;

  assert.equal(harness.storage.get(BRIDGE_TOKEN_KEY), replacementToken);
});

test("pair 401 clears only the token snapshot present at request start before body parsing", async () => {
  const oldToken = "A".repeat(43);
  const replacementToken = "B".repeat(42) + "A";
  const responseBody = JSON.stringify({ error: { code: "UNAUTHORIZED", message: "Rejected" } });
  const responseBytes = Buffer.from(responseBody, "utf8");
  const makeSlow401 = () => {
    const bodyReadStarted = deferred<void>();
    const releaseBody = deferred<void>();
    const response: ControllerFetchResponse = {
      headersObject: { "content-length": String(responseBytes.byteLength) },
      ok: false,
      redirected: false,
      status: 401,
      statusText: "Unauthorized",
      type: "basic",
      url: BRIDGE_BASE_URL + "/v1/pair",
      arrayBuffer: async () => {
        bodyReadStarted.resolve(undefined);
        await releaseBody.promise;
        return responseBytes.buffer.slice(
          responseBytes.byteOffset,
          responseBytes.byteOffset + responseBytes.byteLength
        );
      },
      text: async () => {
        bodyReadStarted.resolve(undefined);
        await releaseBody.promise;
        return responseBody;
      },
      json: async () => JSON.parse(responseBody)
    };
    return { bodyReadStarted, releaseBody, response };
  };

  const unchanged = hostHarness();
  unchanged.storage.set(BRIDGE_TOKEN_KEY, oldToken);
  const firstResponse = makeSlow401();
  unchanged.host.fetch = async () => firstResponse.response;
  const firstController = createController(unchanged.host, config);
  const firstPair = firstController.handleMessage({ type: "pair", operation: 1, code: "123456" });
  await firstResponse.bodyReadStarted.promise;
  try {
    assert.equal(unchanged.storage.has(BRIDGE_TOKEN_KEY), false);
  } finally {
    firstResponse.releaseBody.resolve(undefined);
  }
  await firstPair;

  const replaced = hostHarness();
  replaced.storage.set(BRIDGE_TOKEN_KEY, oldToken);
  const secondResponse = makeSlow401();
  const fetchResponse = deferred<ControllerFetchResponse>();
  const fetchStarted = deferred<void>();
  replaced.host.fetch = async () => {
    fetchStarted.resolve(undefined);
    return fetchResponse.promise;
  };
  const secondController = createController(replaced.host, config);
  const secondPair = secondController.handleMessage({ type: "pair", operation: 1, code: "123456" });
  await fetchStarted.promise;
  replaced.storage.set(BRIDGE_TOKEN_KEY, replacementToken);
  fetchResponse.resolve(secondResponse.response);
  await secondResponse.bodyReadStarted.promise;
  try {
    assert.equal(replaced.storage.get(BRIDGE_TOKEN_KEY), replacementToken);
  } finally {
    secondResponse.releaseBody.resolve(undefined);
  }
  await secondPair;
});

test("bridge responses are size-bounded and stalled requests time out without wedging the gate", async () => {
  const oversized = hostHarness([
    documentedFigmaFetchResponse(JSON.stringify({ error: { code: "X", message: "x".repeat(20_000) } }), 400)
  ]);
  const oversizedController = createController(oversized.host, config);
  await oversizedController.handleMessage({ type: "pair", operation: 1, code: "123456" });
  assert.equal(lastFailure(oversized.messages).code, "INVALID_BRIDGE_RESPONSE");

  const stalled = hostHarness();
  Object.assign(stalled.host, { bridgeTimeoutMs: 5 });
  let requestCount = 0;
  stalled.host.fetch = async () => {
    requestCount += 1;
    if (requestCount === 1) return new Promise<ControllerFetchResponse>(() => undefined);
    return documentedFigmaFetchResponse(JSON.stringify({ token: "A".repeat(43) }), 200);
  };
  const stalledController = createController(stalled.host, config);
  const outcome = await Promise.race([
    stalledController.handleMessage({ type: "pair", operation: 1, code: "123456" }).then(() => "completed"),
    new Promise<string>((resolve) => setTimeout(() => resolve("test-timeout"), 50))
  ]);
  assert.equal(outcome, "completed");
  assert.equal(lastFailure(stalled.messages).code, "BRIDGE_TIMEOUT");
  await stalledController.handleMessage({ type: "pair", operation: 2, code: "654321" });
  assert.equal(requestCount, 2);
});

test("live send accepts only the bridge's exact 202 envelope for the retained content hash", async () => {
  const wrongStatus = hostHarness([
    documentedFigmaFetchResponse(JSON.stringify({ status: "accepted", contentHash: "a".repeat(64) }), 200)
  ]);
  const first = await makeControllerReady(wrongStatus);
  await first.handleMessage({ type: "send-live", operation: 1 });
  assert.equal(lastFailure(wrongStatus.messages).code, "INVALID_BRIDGE_RESPONSE");

  const wrongHash = hostHarness([
    documentedFigmaFetchResponse(JSON.stringify({ status: "accepted", contentHash: "b".repeat(64) }), 202)
  ]);
  const second = await makeControllerReady(wrongHash);
  await second.handleMessage({ type: "send-live", operation: 1 });
  assert.equal(lastFailure(wrongHash.messages).code, "INVALID_BRIDGE_RESPONSE");
});

test("bridge outage reports a structured result and leaves UI manual download enabled", async () => {
  const harness = hostHarness();
  harness.setSelection([sceneNode()]);
  const controller = createController(harness.host, config);
  await controller.handleMessage({ type: "pair", operation: 1, code: "123456" });
  assert.deepEqual(harness.messages.at(-1), {
    type: "bridge-result",
    operation: 1,
    status: 0,
    code: "BRIDGE_UNAVAILABLE",
    message: "The local After Effects bridge is unavailable. Download the package instead."
  });

  const views: UiViewModel[] = [];
  const ui = createUiController({
    postMessage: () => undefined,
    render: (view) => views.push(structuredClone(view)),
    sha256: async (bytes) => sha256Hex(bytes),
    download: () => undefined
  });
  const value = makeValidPackage();
  value.contentHash = "";
  await ui.handleMessage({
    type: "selection",
    generation: 1,
    frames: [{ nodeId: "95:44", name: value.frames[0]!.name, duration: 28 }]
  });
  await ui.handleMessage({ type: "package-unhashed", generation: 1, value });
  ui.pair("123456");
  await ui.handleMessage(harness.messages.at(-1));
  assert.equal(views.at(-1)?.downloadDisabled, false);
  assert.equal(views.at(-1)?.bridgeCode, "BRIDGE_UNAVAILABLE");
});

test("timing build validates approved section ranges and embeds exact section identity per shot", async () => {
  const buildModule = await import(new URL("../scripts/build.mjs", import.meta.url).href) as unknown as {
    validateVideo001Scenes(value: unknown): {
      shots: Array<{ index: number; sectionId: string; sectionName: string }>;
    };
  };
  const timing = JSON.parse(readFileSync(approvedTimingSource(), "utf8")) as {
    sections: Array<{ name: string; firstShot: number; lastShot: number }>;
  };
  const embedded = buildModule.validateVideo001Scenes(timing);

  for (const shot of embedded.shots) {
    const expected = APPROVED_SECTIONS.find(({ firstShot, lastShot }) =>
      shot.index >= firstShot && shot.index <= lastShot
    );
    assert.ok(expected, `missing approved section for Shot ${shot.index}`);
    assert.equal(shot.sectionId, expected.sectionId);
    assert.equal(shot.sectionName, expected.sectionName);
  }

  for (const [index, expected] of APPROVED_SECTIONS.entries()) {
    const wrongName = structuredClone(timing);
    wrongName.sections[index]!.name = `${expected.timingName} changed`;
    assert.throws(() => buildModule.validateVideo001Scenes(wrongName), /section/i);

    const wrongStart = structuredClone(timing);
    wrongStart.sections[index]!.firstShot = expected.firstShot + 1;
    assert.throws(() => buildModule.validateVideo001Scenes(wrongStart), /section/i);

    const wrongEnd = structuredClone(timing);
    wrongEnd.sections[index]!.lastShot = expected.lastShot - 1;
    assert.throws(() => buildModule.validateVideo001Scenes(wrongEnd), /section/i);
  }
});

test("manifest generator rejects missing, malformed, and example IDs and emits exact current fields for a real-looking fixture ID", () => {
  const fixture = mkdtempSync(join(tmpdir(), "video001-manifest-"));
  try {
    const script = new URL("../scripts/generate-figma-manifest.mjs", import.meta.url);
    const run = (): ReturnType<typeof spawnSync> => spawnSync(process.execPath, [script.pathname, "--root", fixture], {
      cwd: PROJECT_ROOT,
      encoding: "utf8"
    });
    assert.notEqual(run().status, 0);
    writeFileSync(join(fixture, ".figma-plugin-id"), "not-an-id\n", "utf8");
    assert.notEqual(run().status, 0);
    writeFileSync(join(fixture, ".figma-plugin-id"), "1661000000000000000\n", "utf8");
    assert.notEqual(run().status, 0);

    writeFileSync(join(fixture, ".figma-plugin-id"), "987654321012345678\n", "utf8");
    const success = run();
    assert.equal(success.status, 0, String(success.stderr));
    const manifest = JSON.parse(readFileSync(join(fixture, "dist/figma/manifest.json"), "utf8"));
    assert.deepEqual(manifest, {
      name: "Video 001 → After Effects",
      id: "987654321012345678",
      api: "1.0.0",
      main: "code.js",
      ui: "ui.html",
      editorType: ["figma"],
      documentAccess: "dynamic-page",
      enablePrivatePluginApi: true,
      networkAccess: {
        allowedDomains: ["none"],
        devAllowedDomains: [BRIDGE_BASE_URL],
        reasoning: "Transfers selected lesson frames to the local After Effects bridge."
      }
    });
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});

test("controller-specific typecheck excludes DOM ambient types", () => {
  const result = spawnSync("npm", ["run", "typecheck:controller"], {
    cwd: PROJECT_ROOT,
    encoding: "utf8"
  });
  assert.equal(result.status, 0, result.stdout + "\n" + result.stderr);
});

test("isolated build embeds exact timings and separates browser-only APIs from the controller bundle", () => {
  const fixture = mkdtempSync(join(tmpdir(), "video001-build-"));
  try {
    const pluginIdFile = join(fixture, ".figma-plugin-id");
    const outDir = join(fixture, "dist/figma");
    const timingFixture = join(fixture, "figma-scenes.json");
    copyFileSync(approvedTimingSource(), timingFixture);
    writeFileSync(pluginIdFile, "987654321012345678\n", "utf8");
    const script = new URL("../scripts/build.mjs", import.meta.url);
    const result = spawnSync(process.execPath, [
      script.pathname,
      "--plugin-id-file", pluginIdFile,
      "--out-dir", outDir
    ], {
      cwd: PROJECT_ROOT,
      encoding: "utf8",
      env: { ...process.env, VIDEO001_FIGMA_SCENES: timingFixture }
    });
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
    const code = readFileSync(join(outDir, "code.js"), "utf8");
    const html = readFileSync(join(outDir, "ui.html"), "utf8");
    const manifest = readFileSync(join(outDir, "manifest.json"), "utf8");
    const parsedManifest = JSON.parse(manifest) as {
      enablePrivatePluginApi: boolean;
      networkAccess: { allowedDomains: string[]; devAllowedDomains: string[] };
    };
    assert.match(code, /95:44/);
    assert.match(code, /S001_SH32_Repo_PreparationNotLearning/);
    assert.match(code, /duration:28|"duration":28/);
    for (const section of APPROVED_SECTIONS) {
      assert.equal(code.includes(section.sectionId), true, `controller bundle omitted section ${section.sectionId}`);
      assert.equal(code.includes(section.sectionName), true, `controller bundle omitted ${section.sectionName}`);
    }
    assert.match(html, /Send to After Effects/);
    assert.match(html, /Download package/);
    assert.doesNotMatch(
      `${code}\n${html}`,
      /node:(?:fs|path|crypto|http|https|net|tls|child_process)|require\(|process\.|(?<![A-Za-z])Buffer\b|child_process/
    );
    assert.doesNotMatch(html, /https?:\/\//);
    assert.doesNotMatch(html, /clientStorage|Authorization|Bearer\s/);
    assert.doesNotMatch(`${code}\n${html}`, /console\.(?:log|debug|info)\s*\(/);
    assert.doesNotMatch(`${code}\n${html}`, /1661000000000000000/);
    assert.doesNotMatch(code, /TextEncoder|crypto\.subtle|globalThis\.crypto/);
    assert.doesNotMatch(html, /crypto\.subtle|globalThis\.crypto|SubtleCrypto/);
    assert.equal(parsedManifest.enablePrivatePluginApi, true);
    assert.deepEqual(parsedManifest.networkAccess.allowedDomains, ["none"]);
    assert.deepEqual(parsedManifest.networkAccess.devAllowedDomains, [BRIDGE_BASE_URL]);
    assert.match(code, /http:\/\/localhost:3456/);
    assert.doesNotMatch(code, /http:\/\/127\.0\.0\.1:3456/);
    assert.match(manifest, /987654321012345678/);
    assert.equal(
      readFileSync(join(outDir, ".video001-figma-build-owned"), "utf8"),
      "video001-figma-exporter-build-v1\n"
    );

    const replacement = spawnSync(process.execPath, [
      script.pathname,
      "--plugin-id-file", pluginIdFile,
      "--out-dir", outDir
    ], {
      cwd: PROJECT_ROOT,
      encoding: "utf8",
      env: { ...process.env, VIDEO001_FIGMA_SCENES: timingFixture }
    });
    assert.equal(replacement.status, 0, `${replacement.stdout}\n${replacement.stderr}`);
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});

test("After Effects build packages the exact validated timing beside the panel", () => {
  const projectRoot = fileURLToPath(PROJECT_ROOT);
  const script = new URL("../scripts/build.mjs", import.meta.url);
  const timingSource = approvedTimingSource();
  const fixture = mkdtempSync(join(tmpdir(), "video001-ae-build-"));
  try {
    const pluginIdFile = join(fixture, ".figma-plugin-id");
    writeFileSync(pluginIdFile, "987654321012345678\n", "utf8");
    const result = spawnSync(process.execPath, [
      script.pathname,
      "--plugin-id-file", pluginIdFile
    ], {
      cwd: projectRoot,
      encoding: "utf8",
      env: { ...process.env, VIDEO001_FIGMA_SCENES: timingSource }
    });
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);

    const builtTiming = join(projectRoot, "dist/ae/figma-scenes.json");
    const builtPanel = readFileSync(join(projectRoot, "dist/ae/Video001-Figma-AE-Exporter.jsx"), "utf8");
    assert.equal(readFileSync(builtTiming, "utf8"), readFileSync(timingSource, "utf8"));
    assert.match(builtPanel, /scriptDirectory\.fsName \+ "\/figma-scenes\.json"/);
    assert.doesNotMatch(builtPanel, /timingDirectory = timingDirectory\.parent/);
    assert.match(builtPanel, /\$\.global\.Video001ExporterPanel\s*=/);
    assert.match(builtPanel, /app\.scheduleTask\("\$\.global\.Video001ExporterPanel\.poll\(\)"/);
    assert.doesNotMatch(builtPanel, /app\.scheduleTask\("Video001ExporterPanel\.poll\(\)"/);
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});

test("plain build uses the committed canonical Video 001 timing", () => {
  const projectRoot = fileURLToPath(PROJECT_ROOT);
  const script = new URL("../scripts/build.mjs", import.meta.url);
  const fixture = mkdtempSync(join(tmpdir(), "video001-plain-build-"));
  try {
    const pluginIdFile = join(fixture, ".figma-plugin-id");
    writeFileSync(pluginIdFile, "987654321012345678\n", "utf8");
    const environment = { ...process.env };
    delete environment.VIDEO001_FIGMA_SCENES;
    const result = spawnSync(process.execPath, [
      script.pathname,
      "--plugin-id-file", pluginIdFile
    ], {
      cwd: projectRoot,
      encoding: "utf8",
      env: environment
    });
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);

    const canonicalTiming = join(projectRoot, "config/video001-figma-scenes.json");
    const builtTiming = join(projectRoot, "dist/ae/figma-scenes.json");
    assert.equal(readFileSync(builtTiming, "utf8"), readFileSync(canonicalTiming, "utf8"));
    assert.equal(readFileSync(canonicalTiming, "utf8"), readFileSync(approvedTimingSource(), "utf8"));
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});

test("built UI accepts routed messages and hashes packages without crypto", async () => {
  const fixture = mkdtempSync(join(tmpdir(), "video001-ui-runtime-"));
  try {
    const pluginIdFile = join(fixture, ".figma-plugin-id");
    const outDir = join(fixture, "dist/figma");
    const timingFixture = join(fixture, "figma-scenes.json");
    copyFileSync(approvedTimingSource(), timingFixture);
    writeFileSync(pluginIdFile, "987654321012345678\n", "utf8");
    const script = new URL("../scripts/build.mjs", import.meta.url);
    const result = spawnSync(process.execPath, [
      script.pathname,
      "--plugin-id-file", pluginIdFile,
      "--out-dir", outDir
    ], {
      cwd: PROJECT_ROOT,
      encoding: "utf8",
      env: { ...process.env, VIDEO001_FIGMA_SCENES: timingFixture }
    });
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);

    const html = readFileSync(join(outDir, "ui.html"), "utf8");
    const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
    assert.equal(scripts.length, 1, "expected one inline UI runtime");
    const uiJavaScript = scripts[0]![1]!;
    const listeners = new Map<string, (event: unknown) => void>();
    const posted: unknown[] = [];
    const elements = new Map<string, ReturnType<typeof makeElement>>();

    function makeElement() {
      return {
        children: [] as unknown[],
        textContent: "",
        value: "",
        disabled: false,
        hidden: false,
        addEventListener: () => undefined,
        append: () => undefined,
        click: () => undefined,
        remove: () => undefined,
        reportValidity: () => undefined,
        setAttribute: () => undefined,
        setCustomValidity: () => undefined,
        replaceChildren(...children: unknown[]) {
          this.children = children;
        }
      };
    }

    const document = {
      body: makeElement(),
      documentElement: makeElement(),
      createElement: () => makeElement(),
      getElementById: (id: string) => {
        let element = elements.get(id);
        if (element === undefined) {
          element = makeElement();
          elements.set(id, element);
        }
        return element;
      }
    };
    const parentWindow = {
      postMessage: (message: unknown) => posted.push(structuredClone(message))
    };
    const window = {
      addEventListener: (type: string, listener: (event: unknown) => void) => listeners.set(type, listener),
      dispatchMessage: (event: unknown) => listeners.get("message")?.(event)
    };
    const sandbox = {
      Blob,
      TextEncoder,
      URL: {
        createObjectURL: () => "blob:fixture",
        revokeObjectURL: () => undefined
      },
      crypto: undefined,
      document,
      messageJson: "",
      nonParentSource: {},
      parent: parentWindow,
      window
    };
    const context = createContext(sandbox);
    runInContext("globalThis.structuredClone = value => JSON.parse(JSON.stringify(value))", context);
    runInContext(uiJavaScript, context);

    assert.deepEqual(posted, [{ pluginMessage: { type: "refresh-selection" } }]);
    const receive = listeners.get("message");
    assert.ok(receive, "UI runtime did not install its message listener");
    assert.notEqual(sandbox.nonParentSource, parentWindow);
    sandbox.messageJson = JSON.stringify({
      pluginMessage: {
        type: "selection",
        generation: 1,
        frames: [{ nodeId: "95:44", name: "S001_SH32_Repo_PreparationNotLearning", duration: 28 }]
      }
    });
    runInContext("window.dispatchMessage({ source: nonParentSource, data: JSON.parse(messageJson) })", context);
    assert.equal(elements.get("status")?.textContent, "1 frame selected.");
    assert.deepEqual(
      elements.get("selection-list")?.children.map((child) => (child as { textContent: string }).textContent),
      ["S001_SH32_Repo_PreparationNotLearning · 28 seconds"]
    );

    sandbox.messageJson = JSON.stringify({
      pluginMessage: { type: "selection", generation: 2, frames: [] },
      pluginId: "987654321012345678"
    });
    runInContext("window.dispatchMessage({ source: nonParentSource, data: JSON.parse(messageJson) })", context);
    assert.equal(elements.get("status")?.textContent, "0 frames selected.");

    sandbox.messageJson = JSON.stringify({ pluginId: "987654321012345678" });
    runInContext("window.dispatchMessage({ source: nonParentSource, data: JSON.parse(messageJson) })", context);
    assert.equal(elements.get("status")?.textContent, "0 frames selected.");

    runInContext(`
      const inheritedEnvelope = Object.create({
        pluginMessage: {
          type: "selection",
          generation: 3,
          frames: [{ nodeId: "95:44", name: "Inherited", duration: 28 }]
        }
      });
      inheritedEnvelope.pluginId = "987654321012345678";
      window.dispatchMessage({ source: nonParentSource, data: inheritedEnvelope });
    `, context);
    assert.equal(elements.get("status")?.textContent, "0 frames selected.");

    sandbox.messageJson = JSON.stringify({
      pluginMessage: { type: "selection", generation: 2, frames: [], unexpected: true }
    });
    runInContext("window.dispatchMessage({ source: nonParentSource, data: JSON.parse(messageJson) })", context);
    assert.equal(elements.get("status")?.textContent, "Plugin message rejected.");
    assert.match(elements.get("error")?.textContent ?? "", /unknown field/i);

    const unhashed = makeValidPackage();
    unhashed.contentHash = "";
    sandbox.messageJson = JSON.stringify({
      pluginMessage: {
        type: "selection",
        generation: 3,
        frames: [{ nodeId: "95:44", name: unhashed.frames[0]!.name, duration: 28 }]
      },
      pluginId: "987654321012345678"
    });
    runInContext("window.dispatchMessage({ source: nonParentSource, data: JSON.parse(messageJson) })", context);
    sandbox.messageJson = JSON.stringify({
      pluginMessage: { type: "package-unhashed", generation: 3, value: unhashed },
      pluginId: "987654321012345678"
    });
    runInContext("window.dispatchMessage({ source: nonParentSource, data: JSON.parse(messageJson) })", context);
    for (let attempt = 0; attempt < 20 && !posted.some((message) =>
      typeof message === "object" && message !== null &&
      "pluginMessage" in message &&
      typeof message.pluginMessage === "object" && message.pluginMessage !== null &&
      "type" in message.pluginMessage && message.pluginMessage.type === "package-ready"
    ); attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
    const readyEnvelope = posted.find((message) =>
      typeof message === "object" && message !== null &&
      "pluginMessage" in message &&
      typeof message.pluginMessage === "object" && message.pluginMessage !== null &&
      "type" in message.pluginMessage && message.pluginMessage.type === "package-ready"
    ) as { pluginMessage: { type: "package-ready"; generation: number; value: ExporterPackage } } | undefined;
    assert.ok(readyEnvelope, JSON.stringify(posted));
    assert.equal(readyEnvelope.pluginMessage.generation, 3);
    assert.equal(
      readyEnvelope.pluginMessage.value.contentHash,
      createHash("sha256").update(contentFingerprintInput(unhashed), "utf8").digest("hex")
    );
    assert.equal(elements.get("status")?.textContent, "Package ready for live send or download.");
    assert.equal(elements.get("native-count")?.textContent, "1");
    assert.equal(elements.get("raster-count")?.textContent, "0");
    assert.equal(elements.get("download-package")?.disabled, false);
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});

test("build destination policy rejects the project root and its ancestors without filesystem mutation", async () => {
  const fixture = mkdtempSync(join(tmpdir(), "video001-build-policy-"));
  try {
    const projectRoot = join(fixture, "project", "exporter");
    mkdirSync(projectRoot, { recursive: true });
    const buildScriptUrl = new URL("../scripts/build.mjs", import.meta.url);
    const buildModule = await import(buildScriptUrl.href) as unknown as {
      validateBuildDestination(options: { projectRoot: string; outDir: string }): string;
    };
    assert.equal(typeof buildModule.validateBuildDestination, "function");
    assert.throws(
      () => buildModule.validateBuildDestination({ projectRoot, outDir: projectRoot }),
      /project root|ancestor/i
    );
    assert.throws(
      () => buildModule.validateBuildDestination({ projectRoot, outDir: dirname(projectRoot) }),
      /project root|ancestor/i
    );
    assert.throws(
      () => buildModule.validateBuildDestination({ projectRoot, outDir: join(projectRoot, "src", "generated") }),
      /exactly dist\/figma/i
    );
    assert.throws(
      () => buildModule.validateBuildDestination({ projectRoot, outDir: join(fixture, "isolated-output") }),
      /dedicated dist\/figma/i
    );
    assert.doesNotThrow(() => buildModule.validateBuildDestination({
      projectRoot,
      outDir: join(fixture, "isolated", "dist", "figma")
    }));
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});

test("build refuses an existing unowned output directory and preserves its contents", () => {
  const fixture = mkdtempSync(join(tmpdir(), "video001-build-unowned-"));
  try {
    const pluginIdFile = join(fixture, ".figma-plugin-id");
    const outDir = join(fixture, "dist", "figma");
    const timingFixture = join(fixture, "figma-scenes.json");
    mkdirSync(outDir, { recursive: true });
    writeFileSync(join(outDir, "sentinel.txt"), "preserve me\n", "utf8");
    copyFileSync(approvedTimingSource(), timingFixture);
    writeFileSync(pluginIdFile, "987654321012345678\n", "utf8");
    const script = new URL("../scripts/build.mjs", import.meta.url);
    const result = spawnSync(process.execPath, [
      script.pathname,
      "--plugin-id-file", pluginIdFile,
      "--out-dir", outDir
    ], {
      cwd: PROJECT_ROOT,
      encoding: "utf8",
      env: { ...process.env, VIDEO001_FIGMA_SCENES: timingFixture }
    });

    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /not owned|ownership marker/i);
    assert.equal(readFileSync(join(outDir, "sentinel.txt"), "utf8"), "preserve me\n");
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});

test("controller bundle builds a root-opacity raster package with only documented Figma main globals", async () => {
  const fixture = mkdtempSync(join(tmpdir(), "video001-controller-smoke-"));
  try {
    const pluginIdFile = join(fixture, ".figma-plugin-id");
    const outDir = join(fixture, "dist/figma");
    const timingFixture = join(fixture, "figma-scenes.json");
    copyFileSync(approvedTimingSource(), timingFixture);
    writeFileSync(pluginIdFile, "987654321012345678\n", "utf8");
    const script = new URL("../scripts/build.mjs", import.meta.url);
    const result = spawnSync(process.execPath, [
      script.pathname,
      "--plugin-id-file", pluginIdFile,
      "--out-dir", outDir
    ], {
      cwd: PROJECT_ROOT,
      encoding: "utf8",
      env: { ...process.env, VIDEO001_FIGMA_SCENES: timingFixture }
    });
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
    const code = readFileSync(join(outDir, "code.js"), "utf8");
    const messages: unknown[] = [];
    const fetchRequests: Array<{ input: string; init?: { method?: string; headers?: Record<string, string>; body?: string } }> = [];
    const pluginStorage = new Map<string, unknown>();
    const currentPage = { id: "90:2", selection: [] as unknown[] };
    const sandbox = {
      __html__: "<!doctype html><title>fixture</title>",
      crypto: undefined,
      TextEncoder: undefined,
      TextDecoder: undefined,
      Response: undefined,
      Headers: undefined,
      ReadableStream: undefined,
      pluginMessageJson: "",
      fetch: async (
        input: string,
        init?: { method?: string; headers?: Record<string, string>; body?: string }
      ) => {
        fetchRequests.push({ input, ...(init === undefined ? {} : { init }) });
        if (input.endsWith("/v1/pair")) {
          return documentedFigmaFetchResponse(JSON.stringify({ token: "A".repeat(43) }), 200);
        }
        const sent = JSON.parse(String(init?.body)) as ExporterPackage;
        return documentedFigmaFetchResponse(JSON.stringify({
          status: "accepted",
          contentHash: sent.contentHash
        }), 202);
      },
      setTimeout,
      clearTimeout,
      figma: {
        fileKey: "fFTux3sx2AzVQtoya67f95",
        currentPage,
        mixed: Symbol("figma.mixed"),
        showUI: () => undefined,
        closePlugin: () => undefined,
        on: () => undefined,
        ui: {
          onmessage: undefined as ((message: unknown) => void) | undefined,
          postMessage: (message: unknown) => messages.push(structuredClone(message))
        },
        clientStorage: {
          getAsync: async (key: string) => pluginStorage.get(key),
          setAsync: async (key: string, value: unknown) => { pluginStorage.set(key, value); },
          deleteAsync: async (key: string) => { pluginStorage.delete(key); }
        }
      }
    };
    runInNewContext(code, sandbox);
    runInNewContext(`
      const frame = {
        id: "95:44",
        name: "S001_SH32_Repo_PreparationNotLearning",
        type: "FRAME",
        width: 1920,
        height: 1080,
        opacity: 0.4,
        visible: true,
        absoluteTransform: [[1, 0, 0], [0, 1, 0]],
        fills: [], strokes: [], effects: [], blendMode: "NORMAL", isMask: false,
        children: [{
          id: "shape-1", name: "BG_Base", type: "RECTANGLE",
          width: 1920, height: 1080, opacity: 1, visible: true,
          absoluteTransform: [[1, 0, 0], [0, 1, 0]],
          fills: [{ type: "SOLID", color: { r: 0, g: 0, b: 0 }, opacity: 1, visible: true }],
          strokes: [], strokeWeight: 0, cornerRadius: 0, effects: [], blendMode: "NORMAL", isMask: false
        }],
        exportAsync: async () => new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10])
      };
      frame.parent = {
        id: "90:9",
        name: "06 Shots 26-32 — Repository Walkthrough",
        type: "SECTION",
        parent: { id: figma.currentPage.id, type: "PAGE" }
      };
      figma.currentPage.selection = [frame];
      figma.ui.onmessage({ type: "build-package" });
    `, sandbox);
    for (let attempt = 0; attempt < 20 && !messages.some((message) =>
      typeof message === "object" && message !== null && "type" in message && message.type === "package-unhashed"
    ); attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
    const packageMessage = messages.find((message) =>
      typeof message === "object" && message !== null && "type" in message && message.type === "package-unhashed"
    ) as { type: "package-unhashed"; generation: number; value: ExporterPackage } | undefined;
    assert.ok(packageMessage, JSON.stringify(messages));
    assert.doesNotMatch(code, /\.headers\.get\(|\.body(?:\?\.|\.)getReader\(/);

    const readyValue = structuredClone(packageMessage.value);
    readyValue.contentHash = createHash("sha256")
      .update(contentFingerprintInput(readyValue), "utf8")
      .digest("hex");
    sandbox.pluginMessageJson = JSON.stringify({
      type: "package-ready",
      generation: packageMessage.generation,
      value: readyValue
    });
    runInNewContext("figma.ui.onmessage(JSON.parse(pluginMessageJson))", sandbox);
    runInNewContext('figma.ui.onmessage({ type: "pair", operation: 1, code: "123456" })', sandbox);
    for (let attempt = 0; attempt < 20 && !messages.some((message) =>
      typeof message === "object" && message !== null && "code" in message && message.code === "PAIRED"
    ); attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
    assert.ok(messages.some((message) =>
      typeof message === "object" && message !== null && "code" in message && message.code === "PAIRED"
    ), JSON.stringify(messages));

    runInNewContext('figma.ui.onmessage({ type: "send-live", operation: 2 })', sandbox);
    for (let attempt = 0; attempt < 20 && !messages.some((message) =>
      typeof message === "object" && message !== null && "code" in message && message.code === "EXPORT_ACCEPTED"
    ); attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
    assert.ok(messages.some((message) =>
      typeof message === "object" && message !== null && "code" in message && message.code === "EXPORT_ACCEPTED"
    ), JSON.stringify(messages));
    assert.deepEqual(fetchRequests.map(({ input }) => input), [
      BRIDGE_BASE_URL + "/v1/pair",
      BRIDGE_BASE_URL + "/v1/export"
    ]);
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});
