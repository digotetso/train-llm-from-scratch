import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { copyFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { execFileSync, spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { runInNewContext } from "node:vm";
import {
  BRIDGE_BASE_URL,
  BRIDGE_TOKEN_KEY,
  EXPORT_MEDIA_TYPE,
  createController,
  normalizeFigmaNode,
  validateUiToController,
  type ControllerHost,
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
import { makeValidPackage } from "./helpers/package.ts";

const PROJECT_ROOT = new URL("../", import.meta.url);

function approvedTimingSource(): string {
  const projectRoot = fileURLToPath(PROJECT_ROOT);
  const commonGitDirectory = execFileSync(
    "git",
    ["rev-parse", "--path-format=absolute", "--git-common-dir"],
    { cwd: projectRoot, encoding: "utf8" }
  ).trim();
  return join(
    dirname(commonGitDirectory),
    "course/videos/001-computer-learning-from-text/after-effects/figma-scenes.json"
  );
}

const config: EmbeddedVideo001Config = {
  source: {
    fileKey: "fFTux3sx2AzVQtoya67f95",
    pageId: "90:2"
  },
  target: { width: 1920, height: 1080, fps: 30 },
  shots: [
    { index: 1, nodeId: "94:2", name: "S001_SH01_Hook_CatWord", duration: 8 },
    { index: 32, nodeId: "95:44", name: "S001_SH32_Repo_PreparationNotLearning", duration: 28 }
  ]
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

interface HostHarness {
  host: ControllerHost;
  messages: unknown[];
  requests: Array<{ input: string; init?: RequestInit }>;
  storage: Map<string, unknown>;
  setSelection(nodes: FigmaNodeLike[]): void;
}

function hostHarness(fetchResponses: Response[] = []): HostHarness {
  const page = { id: "90:2", selection: [] as FigmaNodeLike[] };
  const messages: unknown[] = [];
  const requests: Array<{ input: string; init?: RequestInit }> = [];
  const storage = new Map<string, unknown>();
  return {
    messages,
    requests,
    storage,
    setSelection(nodes): void {
      page.selection = nodes;
      for (const node of nodes) node.parent = page;
    },
    host: {
      fileKey: "fFTux3sx2AzVQtoya67f95",
      getCurrentPage: () => page,
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

function lastFailure(messages: unknown[]): { type: string; code: string; message: string } {
  const value = messages.at(-1);
  assert.equal(typeof value, "object");
  return value as { type: string; code: string; message: string };
}

test("selection refresh reports empty, non-frame, nested, unknown, and over-limit selections safely", async () => {
  const harness = hostHarness();
  const controller = createController(harness.host, config);

  await controller.handleMessage({ type: "refresh-selection" });
  assert.equal(lastFailure(harness.messages).code, "NO_FRAME_SELECTED");

  harness.setSelection([sceneNode({ type: "RECTANGLE" })]);
  await controller.handleMessage({ type: "refresh-selection" });
  assert.equal(lastFailure(harness.messages).code, "SELECTION_NOT_FRAME");

  const nested = sceneNode();
  nested.parent = { id: "nested-parent", selection: [] };
  harness.host.getCurrentPage().selection = [nested];
  await controller.handleMessage({ type: "refresh-selection" });
  assert.equal(lastFailure(harness.messages).code, "SELECTION_NOT_TOP_LEVEL");

  harness.setSelection([sceneNode({ id: "999:999" })]);
  await controller.handleMessage({ type: "refresh-selection" });
  assert.equal(lastFailure(harness.messages).code, "SHOT_TIMING_NOT_FOUND");

  harness.setSelection(Array.from({ length: 49 }, (_, index) => sceneNode({ id: index === 0 ? "94:2" : `94:${index + 2}` })));
  await controller.handleMessage({ type: "refresh-selection" });
  assert.equal(lastFailure(harness.messages).code, "TOO_MANY_FRAMES");
});

test("Shot 32 maps node 95:44 to the exact frame name and 28-frame duration", async () => {
  const harness = hostHarness();
  harness.setSelection([sceneNode()]);
  const controller = createController(harness.host, config);
  await controller.handleMessage({ type: "refresh-selection" });
  assert.deepEqual(harness.messages.at(-1), {
    type: "selection",
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

test("both protocol boundaries reject unknown keys, invalid types, and exotic prototypes", () => {
  assert.throws(() => validateUiToController({ type: "send-live", token: "secret" }), /unknown field/i);
  assert.throws(() => validateUiToController({ type: "pair", code: "12345" }), /pairing code/i);
  const inherited = Object.create({ polluted: true }) as Record<string, unknown>;
  inherited.type = "close";
  assert.throws(() => validateUiToController(inherited), /plain object/i);

  assert.throws(() => validateControllerToUi({ type: "selection", frames: [], token: "secret" }), /unknown field/i);
  assert.throws(() => validateControllerToUi({ type: "bridge-result", status: -1, code: "X", message: "bad" }), /status/i);
});

async function hashedPackage(): Promise<ExporterPackage> {
  const value = makeValidPackage();
  value.contentHash = "";
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(contentFingerprintInput(value)));
  value.contentHash = Buffer.from(digest).toString("hex");
  return validatePackage(value);
}

test("UI hashes with Web Crypto parity, returns only package-ready, exposes counts, and downloads exact UTF-8 vendor bytes", async () => {
  const posted: unknown[] = [];
  const views: UiViewModel[] = [];
  const downloads: Array<{ bytes: Uint8Array; filename: string; mimeType: string }> = [];
  const ui = createUiController({
    postMessage: (message) => posted.push(structuredClone(message)),
    render: (view) => views.push(structuredClone(view)),
    digest: (algorithm, bytes) => crypto.subtle.digest(algorithm, bytes),
    download: (value) => downloads.push(value)
  });
  const unhashed = makeValidPackage();
  unhashed.contentHash = "";
  await ui.handleMessage({ type: "package-unhashed", value: unhashed });
  const ready = posted.at(-1) as { type: string; value: ExporterPackage };
  assert.equal(ready.type, "package-ready");
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
    new Response(JSON.stringify({ token }), { status: 200, headers: { "content-type": "application/json" } }),
    new Response(JSON.stringify({ error: { code: "UNAUTHORIZED", message: "Expired" } }), {
      status: 401,
      headers: { "content-type": "application/json" }
    })
  ]);
  harness.setSelection([sceneNode()]);
  const controller = createController(harness.host, config);

  await controller.handleMessage({ type: "package-ready", value: await hashedPackage() });
  assert.equal(lastFailure(harness.messages).code, "PACKAGE_NOT_PENDING");

  await controller.handleMessage({ type: "build-package" });
  const pending = (harness.messages.at(-1) as { value: ExporterPackage }).value;
  const finalValue = structuredClone(pending);
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(contentFingerprintInput(finalValue)));
  finalValue.contentHash = Buffer.from(digest).toString("hex");
  await controller.handleMessage({ type: "package-ready", value: finalValue });

  await controller.handleMessage({ type: "pair", code: "123456" });
  assert.equal(harness.requests[0]?.input, `${BRIDGE_BASE_URL}/v1/pair`);
  assert.equal(harness.requests[0]?.init?.method, "POST");
  assert.deepEqual(harness.requests[0]?.init?.headers, { "Content-Type": "application/json" });
  assert.equal(harness.requests[0]?.init?.body, JSON.stringify({ code: "123456" }));
  assert.equal(harness.storage.get(BRIDGE_TOKEN_KEY), token);
  assert.equal(JSON.stringify(harness.messages).includes(token), false);

  await controller.handleMessage({ type: "send-live" });
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
    status: 401,
    code: "UNAUTHORIZED",
    message: "Expired"
  });
  assert.equal(JSON.stringify(harness.messages).includes(token), false);
});

test("pairing accepts only the bridge's exact 200 response and canonical 32-byte base64url token", async () => {
  const invalidToken = hostHarness([
    new Response(JSON.stringify({ token: "bridge-token-not-for-ui" }), {
      status: 200,
      headers: { "content-type": "application/json" }
    })
  ]);
  const first = createController(invalidToken.host, config);
  await first.handleMessage({ type: "pair", code: "123456" });
  assert.equal(lastFailure(invalidToken.messages).code, "INVALID_BRIDGE_RESPONSE");
  assert.equal(invalidToken.storage.has(BRIDGE_TOKEN_KEY), false);

  const wrongStatus = hostHarness([
    new Response(JSON.stringify({ token: "A".repeat(43) }), {
      status: 201,
      headers: { "content-type": "application/json" }
    })
  ]);
  const second = createController(wrongStatus.host, config);
  await second.handleMessage({ type: "pair", code: "123456" });
  assert.equal(lastFailure(wrongStatus.messages).code, "INVALID_BRIDGE_RESPONSE");
  assert.equal(wrongStatus.storage.has(BRIDGE_TOKEN_KEY), false);
});

async function makeControllerReady(harness: HostHarness): Promise<ReturnType<typeof createController>> {
  harness.setSelection([sceneNode()]);
  const controller = createController(harness.host, config);
  await controller.handleMessage({ type: "build-package" });
  const pending = (harness.messages.at(-1) as { value: ExporterPackage }).value;
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(contentFingerprintInput(pending)));
  const ready = { ...pending, contentHash: Buffer.from(digest).toString("hex") };
  await controller.handleMessage({ type: "package-ready", value: ready });
  harness.storage.set(BRIDGE_TOKEN_KEY, "A".repeat(43));
  return controller;
}

test("live send accepts only the bridge's exact 202 envelope for the retained content hash", async () => {
  const wrongStatus = hostHarness([
    new Response(JSON.stringify({ status: "accepted", contentHash: "a".repeat(64) }), {
      status: 200,
      headers: { "content-type": "application/json" }
    })
  ]);
  const first = await makeControllerReady(wrongStatus);
  await first.handleMessage({ type: "send-live" });
  assert.equal(lastFailure(wrongStatus.messages).code, "INVALID_BRIDGE_RESPONSE");

  const wrongHash = hostHarness([
    new Response(JSON.stringify({ status: "accepted", contentHash: "b".repeat(64) }), {
      status: 202,
      headers: { "content-type": "application/json" }
    })
  ]);
  const second = await makeControllerReady(wrongHash);
  await second.handleMessage({ type: "send-live" });
  assert.equal(lastFailure(wrongHash.messages).code, "INVALID_BRIDGE_RESPONSE");
});

test("bridge outage reports a structured result and leaves UI manual download enabled", async () => {
  const harness = hostHarness();
  harness.setSelection([sceneNode()]);
  const controller = createController(harness.host, config);
  await controller.handleMessage({ type: "pair", code: "123456" });
  assert.deepEqual(harness.messages.at(-1), {
    type: "bridge-result",
    status: 0,
    code: "BRIDGE_UNAVAILABLE",
    message: "The local After Effects bridge is unavailable. Download the package instead."
  });

  const views: UiViewModel[] = [];
  const ui = createUiController({
    postMessage: () => undefined,
    render: (view) => views.push(structuredClone(view)),
    digest: (algorithm, bytes) => crypto.subtle.digest(algorithm, bytes),
    download: () => undefined
  });
  const value = makeValidPackage();
  value.contentHash = "";
  await ui.handleMessage({ type: "package-unhashed", value });
  await ui.handleMessage(harness.messages.at(-1));
  assert.equal(views.at(-1)?.downloadDisabled, false);
  assert.equal(views.at(-1)?.bridgeCode, "BRIDGE_UNAVAILABLE");
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
      networkAccess: {
        allowedDomains: ["none"],
        devAllowedDomains: ["http://127.0.0.1:3456"],
        reasoning: "Transfers selected lesson frames to the local After Effects bridge."
      }
    });
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
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
    assert.match(code, /95:44/);
    assert.match(code, /S001_SH32_Repo_PreparationNotLearning/);
    assert.match(code, /duration:28|"duration":28/);
    assert.match(html, /Send to After Effects/);
    assert.match(html, /Download package/);
    assert.doesNotMatch(
      `${code}\n${html}`,
      /node:(?:fs|path|crypto|http|https|net|tls|child_process)|require\(|process\.|Buffer\b|child_process/
    );
    assert.doesNotMatch(html, /https?:\/\//);
    assert.doesNotMatch(html, /clientStorage|Authorization|Bearer\s/);
    assert.doesNotMatch(`${code}\n${html}`, /console\.(?:log|debug|info)\s*\(/);
    assert.doesNotMatch(`${code}\n${html}`, /1661000000000000000/);
    assert.doesNotMatch(code, /TextEncoder|crypto\.subtle|globalThis\.crypto/);
    assert.match(manifest, /987654321012345678/);
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
    const currentPage = { id: "90:2", selection: [] as unknown[] };
    const sandbox = {
      __html__: "<!doctype html><title>fixture</title>",
      crypto: undefined,
      TextEncoder: undefined,
      fetch: async () => { throw new Error("network not expected"); },
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
          getAsync: async () => undefined,
          setAsync: async () => undefined,
          deleteAsync: async () => undefined
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
      frame.parent = figma.currentPage;
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
    );
    assert.ok(packageMessage, JSON.stringify(messages));
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});
