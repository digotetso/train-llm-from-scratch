import assert from "node:assert/strict";
import test from "node:test";
import {
  canonicalJson,
  contentFingerprintInput,
  type ExporterPackage,
  type RasterNode,
  type TextNode,
  validatePackage
} from "../src/shared/contract.ts";
import { LIMITS } from "../src/shared/limits.ts";
import { makeValidPackage } from "./helpers/package.ts";

function firstTextNode(value: ExporterPackage): TextNode {
  const node = value.frames[0]?.children[0];
  if (node?.kind !== "text") throw new Error("expected first child to be text");
  return node;
}

function rasterNode(assetHash: string): RasterNode {
  return {
    id: "raster-1",
    kind: "raster",
    name: "Raster_Fallback",
    x: 0,
    y: 0,
    width: 100,
    height: 100,
    rotation: 0,
    opacity: 1,
    assetHash
  };
}

function addAsset(
  value: ExporterPackage,
  dataBase64: string,
  byteLength: number,
  hash = "b".repeat(64)
): void {
  value.assets.push({ hash, mimeType: "image/png", byteLength, dataBase64 });
}

test("accepts UTF-8 text without changing paragraph geometry", () => {
  const result = validatePackage(makeValidPackage());
  const node = firstTextNode(result);
  assert.equal(node.text, "θ · →");
  assert.deepEqual(node.textBox, { width: 300, height: 200 });
});

test("returns a deeply isolated clone", () => {
  const input = makeValidPackage();
  const result = validatePackage(input);

  assert.notStrictEqual(result, input);
  assert.notStrictEqual(result.frames, input.frames);
  assert.notStrictEqual(firstTextNode(result).textBox, firstTextNode(input).textBox);

  firstTextNode(result).textBox.width = 999;
  firstTextNode(input).name = "Input_Was_Mutated";
  assert.equal(firstTextNode(input).textBox.width, 300);
  assert.equal(firstTextNode(result).name, "MODEL_Parameters");
});

test("rejects an unknown schema major version", () => {
  assert.throws(
    () => validatePackage({ ...makeValidPackage(), schemaVersion: "2.0.0" }),
    /schema major/i
  );
});

test("rejects unknown keys at every object boundary", () => {
  const cases: Array<[string, (value: ExporterPackage) => unknown]> = [
    ["package", (value) => ({ ...value, unexpected: true })],
    ["source", (value) => ({ ...value, source: { ...value.source, unexpected: true } })],
    ["frame", (value) => ({ ...value, frames: [{ ...value.frames[0], unexpected: true }] })],
    ["node", (value) => {
      const node = firstTextNode(value);
      return { ...value, frames: [{ ...value.frames[0], children: [{ ...node, unexpected: true }] }] };
    }]
  ];

  for (const [label, mutate] of cases) {
    assert.throws(() => validatePackage(mutate(makeValidPackage())), /unknown field/, label);
  }
});

test("rejects non-finite geometry", () => {
  const cases: Array<[string, (value: ExporterPackage) => void]> = [
    ["node x", (value) => { firstTextNode(value).x = Number.NaN; }],
    ["frame duration", (value) => { value.frames[0]!.duration = Number.POSITIVE_INFINITY; }],
    ["target fps", (value) => { value.target.fps = Number.NEGATIVE_INFINITY; }]
  ];

  for (const [label, mutate] of cases) {
    const value = makeValidPackage();
    mutate(value);
    assert.throws(() => validatePackage(value), /finite number/, label);
  }
});

test("rejects duplicate node IDs across a package", () => {
  const value = makeValidPackage();
  value.frames[0]!.children.push(structuredClone(firstTextNode(value)));
  assert.throws(() => validatePackage(value), /duplicate node ID/);
});

test("rejects invalid hashes and colors", () => {
  const cases: Array<[string, (value: ExporterPackage) => void, RegExp]> = [
    ["uppercase content hash", (value) => { value.contentHash = "A".repeat(64); }, /lowercase hexadecimal/],
    ["short asset hash", (value) => { addAsset(value, "Zg==", 1, "b".repeat(63)); }, /lowercase hexadecimal/],
    ["non-hex text color", (value) => { firstTextNode(value).runs[0]!.color = "#GGGGGG"; }, /invalid color/]
  ];

  for (const [label, mutate, expected] of cases) {
    const value = makeValidPackage();
    mutate(value);
    assert.throws(() => validatePackage(value), expected, label);
  }
});

test("accepts canonical padded base64", () => {
  const cases: Array<[string, number]> = [["Zg==", 1], ["Zm8=", 2]];
  for (const [dataBase64, byteLength] of cases) {
    const value = makeValidPackage();
    addAsset(value, dataBase64, byteLength);
    assert.doesNotThrow(() => validatePackage(value), dataBase64);
  }
});

test("rejects base64 with non-zero pad bits", () => {
  const cases: Array<[string, number]> = [["Zh==", 1], ["Zm9=", 2]];
  for (const [dataBase64, byteLength] of cases) {
    const value = makeValidPackage();
    addAsset(value, dataBase64, byteLength);
    assert.throws(() => validatePackage(value), /canonical base64/, dataBase64);
  }
});

test("rejects a declared asset byte length that does not match decoded data", () => {
  const value = makeValidPackage();
  addAsset(value, "Zg==", 2);
  assert.throws(() => validatePackage(value), /base64 decodes to 1/);
});

test("rejects raster nodes whose asset is missing", () => {
  const value = makeValidPackage();
  value.frames[0]!.children.push(rasterNode("b".repeat(64)));
  assert.throws(() => validatePackage(value), /references missing asset/);
});

test("rejects frame and asset counts above configured limits", () => {
  const tooManyFrames = makeValidPackage();
  tooManyFrames.frames = Array.from(
    { length: LIMITS.maxFrames + 1 },
    () => structuredClone(tooManyFrames.frames[0]!)
  );
  assert.throws(() => validatePackage(tooManyFrames), /frame limit/);

  const tooManyAssets = makeValidPackage();
  const asset = { hash: "b".repeat(64), mimeType: "image/png" as const, byteLength: 1, dataBase64: "Zg==" };
  tooManyAssets.assets = Array.from({ length: LIMITS.maxAssets + 1 }, () => structuredClone(asset));
  assert.throws(() => validatePackage(tooManyAssets), /asset limit/);
});

test("preflights declared per-asset and aggregate byte limits without large payloads", () => {
  const oversizedAsset = makeValidPackage();
  addAsset(oversizedAsset, "", LIMITS.maxAssetBytes + 1);
  assert.throws(() => validatePackage(oversizedAsset), /per-asset limit/);

  const oversizedAggregate = makeValidPackage();
  oversizedAggregate.assets = Array.from({ length: 17 }, (_, index) => ({
    hash: index.toString(16).padStart(64, "0"),
    mimeType: "image/png" as const,
    byteLength: LIMITS.maxAssetBytes,
    dataBase64: ""
  }));
  assert.throws(() => validatePackage(oversizedAggregate), /aggregate decoded-byte limit/);
});

test("rejects a manifest above its byte limit without allocating 32 MiB", { concurrency: false }, () => {
  const OriginalTextEncoder = globalThis.TextEncoder;
  class OverLimitTextEncoder {
    encode(): { byteLength: number } {
      return { byteLength: LIMITS.maxManifestBytes + 1 };
    }
  }

  Object.defineProperty(globalThis, "TextEncoder", {
    configurable: true,
    value: OverLimitTextEncoder,
    writable: true
  });
  try {
    assert.throws(() => validatePackage(makeValidPackage()), /manifest-byte limit/);
  } finally {
    Object.defineProperty(globalThis, "TextEncoder", {
      configurable: true,
      value: OriginalTextEncoder,
      writable: true
    });
  }
});

test("canonical JSON sorts object keys but preserves array order", () => {
  assert.equal(canonicalJson({ z: 1, a: [3, 2, 1] }), '{"a":[3,2,1],"z":1}');
});

test("content fingerprints ignore export time and the fingerprint field", () => {
  const valid = makeValidPackage();
  const first = contentFingerprintInput(valid);
  const second = contentFingerprintInput({
    ...valid,
    exportedAt: "2026-07-23T00:00:00.000Z",
    contentHash: "b".repeat(64)
  });
  assert.equal(first, second);
});

test("content fingerprints change when manifest content changes", () => {
  const baseline = contentFingerprintInput(makeValidPackage());
  const cases: Array<[string, (value: ExporterPackage) => void]> = [
    ["exporterVersion", (value) => { value.exporterVersion = "0.1.1"; }],
    ["source.fileKey", (value) => { value.source.fileKey = "another-file"; }],
    ["source.pageId", (value) => { value.source.pageId = "91:2"; }],
    ["target.width", (value) => { value.target.width = 1280; }],
    ["target.height", (value) => { value.target.height = 720; }],
    ["target.fps", (value) => { value.target.fps = 24; }],
    ["frame.nodeId", (value) => { value.frames[0]!.nodeId = "95:45"; }],
    ["frame.name", (value) => { value.frames[0]!.name = "S001_SH32_Changed"; }],
    ["frame.width", (value) => { value.frames[0]!.width = 1280; }],
    ["frame.height", (value) => { value.frames[0]!.height = 720; }],
    ["frame.duration", (value) => { value.frames[0]!.duration = 29; }],
    ["node.id", (value) => { firstTextNode(value).id = "text-2"; }],
    ["node.name", (value) => { firstTextNode(value).name = "MODEL_Changed"; }],
    ["node.x", (value) => { firstTextNode(value).x = 101; }],
    ["node.y", (value) => { firstTextNode(value).y = 101; }],
    ["node.width", (value) => { firstTextNode(value).width = 301; }],
    ["node.height", (value) => { firstTextNode(value).height = 201; }],
    ["node.rotation", (value) => { firstTextNode(value).rotation = 1; }],
    ["node.opacity", (value) => { firstTextNode(value).opacity = 0.5; }],
    ["text", (value) => { firstTextNode(value).text = "θ · →!"; }],
    ["textBox.width", (value) => { firstTextNode(value).textBox.width = 301; }],
    ["textBox.height", (value) => { firstTextNode(value).textBox.height = 201; }],
    ["paragraph.align", (value) => { firstTextNode(value).paragraph.align = "CENTER"; }],
    ["paragraph.lineHeightPx", (value) => { firstTextNode(value).paragraph.lineHeightPx = 77; }],
    ["paragraph.letterSpacingPx", (value) => { firstTextNode(value).paragraph.letterSpacingPx = 1; }],
    ["run.start", (value) => { firstTextNode(value).runs[0]!.start = 1; }],
    ["run.end", (value) => { firstTextNode(value).runs[0]!.end = 4; }],
    ["run.fontFamily", (value) => { firstTextNode(value).runs[0]!.fontFamily = "Inter"; }],
    ["run.fontStyle", (value) => { firstTextNode(value).runs[0]!.fontStyle = "Regular"; }],
    ["run.fontSize", (value) => { firstTextNode(value).runs[0]!.fontSize = 63; }],
    ["run.color", (value) => { firstTextNode(value).runs[0]!.color = "#FFFFFF"; }],
    ["warnings", (value) => {
      value.frames[0]!.warnings.push({
        nodeId: "text-1",
        nodeName: "MODEL_Parameters",
        property: "effect",
        fallback: "png"
      });
    }],
    ["assets", (value) => { addAsset(value, "Zg==", 1); }]
  ];

  for (const [label, mutate] of cases) {
    const value = makeValidPackage();
    mutate(value);
    assert.notEqual(contentFingerprintInput(value), baseline, label);
  }
});
