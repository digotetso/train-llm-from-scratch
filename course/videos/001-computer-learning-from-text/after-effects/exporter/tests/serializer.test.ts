import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import type { ExportFrame, ExportNode } from "../src/shared/contract.ts";
import { LIMITS } from "../src/shared/limits.ts";
import {
  classifyNode,
  serializeFrame,
  type FigmaNodeSnapshot,
  type RasterExportRequest
} from "../src/figma/serializer.ts";

interface FixtureEnvelope extends FigmaNodeSnapshot {
  fixtureProvenance: {
    lesson: string;
    shot: number;
    figmaNodeId: string;
    purpose: string;
  };
}

function fixture(name: "unicode-frame" | "nested-frame"): FixtureEnvelope {
  const path = new URL(`./fixtures/${name}.json`, import.meta.url);
  return JSON.parse(readFileSync(path, "utf8")) as FixtureEnvelope;
}

function findNode(frame: ExportFrame, name: string): ExportNode {
  const pending = [...frame.children];
  while (pending.length > 0) {
    const node = pending.shift();
    if (node === undefined) break;
    if (node.name === name) return node;
    if (node.kind === "group") pending.unshift(...node.children);
  }
  throw new Error(`missing exported node ${name}`);
}

function matrix(x: number, y: number, rotation = 0): [[number, number, number], [number, number, number]] {
  const radians = rotation * Math.PI / 180;
  const cosine = Math.cos(radians);
  const sine = Math.sin(radians);
  return [[cosine, -sine, x], [sine, cosine, y]];
}

function solid(r = 0.25, g = 0.5, b = 0.75): { type: "SOLID"; color: { r: number; g: number; b: number } } {
  return { type: "SOLID", color: { r, g, b } };
}

function shape(overrides: Partial<FigmaNodeSnapshot> = {}): FigmaNodeSnapshot {
  return {
    id: "shape-1",
    name: "Shape_One",
    type: "RECTANGLE",
    width: 100,
    height: 50,
    opacity: 1,
    absoluteTransform: matrix(10, 20),
    fills: [solid()],
    strokes: [],
    strokeWeight: 0,
    cornerRadius: 0,
    effects: [],
    blendMode: "NORMAL",
    isMask: false,
    ...overrides
  };
}

function root(children: FigmaNodeSnapshot[]): FigmaNodeSnapshot {
  return {
    id: "frame-root",
    name: "S001_SH32_TestFrame",
    type: "FRAME",
    width: 1920,
    height: 1080,
    opacity: 1,
    absoluteTransform: matrix(0, 0),
    fills: [],
    strokes: [],
    effects: [],
    blendMode: "NORMAL",
    isMask: false,
    children
  };
}

function rasterAsset(label: string): { hash: string; bytes: Uint8Array } {
  const bytes = new TextEncoder().encode(label);
  return { hash: createHash("sha256").update(bytes).digest("hex"), bytes };
}

test("preserves Shot 32 Unicode, exact paragraph boxes, alignment, style boundaries, and z-order", async () => {
  const source = fixture("unicode-frame");
  assert.equal(source.fixtureProvenance.shot, 32);
  const original = structuredClone(source);

  const frame = await serializeFrame(source, { duration: 28 }, { rasterScale: 1 });
  const theta = findNode(frame, "MODEL_Parameters");
  assert.equal(theta.kind, "text");
  if (theta.kind !== "text") throw new Error("expected text");
  assert.equal(theta.text, "θ");
  assert.deepEqual(theta.textBox, { width: 104, height: 112 });

  const title = findNode(frame, "TXT_Title");
  assert.equal(title.kind, "text");
  if (title.kind !== "text") throw new Error("expected text");
  const sourceTitle = source.children?.find((node) => node.name === "TXT_Title");
  assert.ok(sourceTitle);
  assert.equal(title.textBox.width, sourceTitle.width);
  assert.equal(title.text.includes("\n"), sourceTitle.characters?.includes("\n"));
  assert.equal(title.text, sourceTitle.characters);
  assert.deepEqual(title.runs.map(({ start, end }) => ({ start, end })), [
    { start: 0, end: 22 },
    { start: 22, end: 38 }
  ]);
  assert.equal(title.runs[1]?.fontStyle, "SemiBold");

  const dot = findNode(frame, "TXT_MiddleDot");
  const arrow = findNode(frame, "TXT_Arrow");
  assert.equal(dot.kind === "text" ? dot.text : undefined, "·");
  assert.equal(arrow.kind === "text" ? arrow.text : undefined, "→");

  const right = findNode(frame, "TXT_RightAligned");
  assert.equal(right.kind, "text");
  if (right.kind !== "text") throw new Error("expected text");
  assert.deepEqual(right.textBox, { width: 420, height: 120 });
  assert.deepEqual(right.paragraph, { align: "RIGHT", lineHeightPx: 58, letterSpacingPx: 1.25 });
  assert.deepEqual(frame.children.map((node) => node.name), source.children?.map((node) => node.name));
  assert.deepEqual(source, original, "serialization must not mutate normalized snapshots");
});

test("derives deterministic transforms relative to a translated and rotated selected frame", async () => {
  const frame = await serializeFrame(fixture("unicode-frame"), { duration: 28 }, { rasterScale: 1 });
  const title = findNode(frame, "TXT_Title");
  assert.equal(title.x, 180);
  assert.equal(title.y, 90);
  assert.equal(title.rotation, 0);

  const rotated = findNode(frame, "TXT_Rotated");
  assert.equal(rotated.x, 1120);
  assert.equal(rotated.y, 240);
  assert.equal(rotated.rotation, 17);
  assert.equal(rotated.opacity, 0.75);
});

test("keeps supported groups and solid shapes native while rasterizing a gradient", async () => {
  const source = fixture("nested-frame");
  const frame = await serializeFrame(source, { duration: 28 }, { rasterScale: 1 });

  assert.equal(findNode(frame, "DATA_Node_01").kind, "group");
  const rectangle = findNode(frame, "DATA_SolidRect");
  assert.equal(rectangle.kind, "rect");
  if (rectangle.kind !== "rect") throw new Error("expected rectangle");
  assert.equal(rectangle.fill, "#1E8FFF");
  assert.equal(rectangle.stroke, "#F5F7FB");
  assert.equal(rectangle.strokeWidth, 3);
  assert.equal(rectangle.radius, 18);
  assert.equal(findNode(frame, "DATA_StatusDot").kind, "ellipse");
  assert.equal(findNode(frame, "FX_GradientRect").kind, "raster");
  assert.equal(findNode(frame, "FX_ImageRect").kind, "raster");
  assert.equal(findNode(frame, "FX_EffectEllipse").kind, "raster");
  assert.equal(findNode(frame, "MASK_Subtree").kind, "raster");
  assert.throws(() => findNode(frame, "Hidden_MaskedContent"), /missing exported node/);
  assert.equal(findNode(frame, "FX_BlendRect").kind, "raster");
  assert.equal(findNode(frame, "FX_Vector").kind, "raster");
  assert.equal(findNode(frame, "FX_UnsupportedSubtreeFixture").kind, "raster");
  assert.throws(() => findNode(frame, "Hidden_NativeChild"), /missing exported node/);
  assert.deepEqual(frame.children.map((node) => node.name), [
    "DATA_Backplate",
    "DATA_Node_01",
    "FX_GradientRect",
    "FX_ImageRect",
    "FX_EffectEllipse",
    "MASK_Subtree",
    "FX_BlendRect",
    "FX_Vector",
    "FX_UnsupportedSubtreeFixture"
  ]);
  assert.deepEqual(frame.warnings, [
    { nodeId: "96:5", nodeName: "FX_GradientRect", property: "fills", fallback: "png" },
    { nodeId: "96:6", nodeName: "FX_ImageRect", property: "fills", fallback: "png" },
    { nodeId: "96:7", nodeName: "FX_EffectEllipse", property: "effects", fallback: "png" },
    { nodeId: "96:8", nodeName: "MASK_Subtree", property: "children[0].isMask", fallback: "png" },
    { nodeId: "96:9", nodeName: "FX_BlendRect", property: "blendMode", fallback: "png" },
    { nodeId: "96:10", nodeName: "FX_Vector", property: "type", fallback: "png" },
    {
      nodeId: "96:11",
      nodeName: "FX_UnsupportedSubtreeFixture",
      property: "children[1].fills",
      fallback: "png"
    }
  ]);
});

test("injects pure raster export with deterministic PNG scale and verifies the returned hash", async () => {
  const gradient = shape({
    id: "96:5",
    name: "FX_GradientRect",
    fills: [{ type: "GRADIENT_LINEAR" }]
  });
  const source = root([gradient]);
  const exported = rasterAsset("gradient-png");
  const calls: Array<{ id: string; request: RasterExportRequest }> = [];

  const frame = await serializeFrame(source, { duration: 28 }, {
    rasterScale: 2,
    exportRaster: async (node, request) => {
      calls.push({ id: node.id, request });
      return exported;
    }
  });

  const raster = findNode(frame, "FX_GradientRect");
  assert.equal(raster.kind, "raster");
  if (raster.kind !== "raster") throw new Error("expected raster");
  assert.equal(raster.assetHash, exported.hash);
  assert.deepEqual(calls, [{ id: "96:5", request: { format: "PNG", scale: 2 } }]);

  await assert.rejects(
    serializeFrame(source, { duration: 28 }, {
      rasterScale: 1,
      exportRaster: async () => ({ ...exported, hash: "0".repeat(64) })
    }),
    /children\[0\].*hash.*bytes/i
  );
});

test("adds the source path and node identity when injected raster export fails", async () => {
  const gradient = shape({
    id: "failed-raster",
    name: "FX_FailedRaster",
    fills: [{ type: "GRADIENT_LINEAR" }]
  });

  await assert.rejects(
    serializeFrame(root([gradient]), { duration: 28 }, {
      rasterScale: 1,
      exportRaster: async () => {
        throw new Error("renderer unavailable");
      }
    }),
    /\$\.children\[0\].*failed-raster.*FX_FailedRaster.*renderer unavailable/i
  );
});

test("classifies every explicitly supported node and conservatively rasterizes unsupported properties", () => {
  const nativeRect = shape();
  const nativeEllipse = shape({ type: "ELLIPSE" });
  const text = fixture("unicode-frame").children?.[0];
  assert.ok(text);
  assert.equal(classifyNode(text), "native");
  assert.equal(classifyNode(nativeRect), "native");
  assert.equal(classifyNode(nativeEllipse), "native");

  const unsupported: Array<[string, FigmaNodeSnapshot]> = [
    ["gradient", shape({ fills: [{ type: "GRADIENT_LINEAR" }] })],
    ["image", shape({ fills: [{ type: "IMAGE", imageHash: "asset" }] })],
    ["mixed fills", shape({ fills: [solid(), solid()] })],
    ["mixed strokes", shape({ strokes: [solid(), solid()] })],
    ["effect", shape({ effects: [{ type: "DROP_SHADOW", visible: true }] })],
    ["mask", shape({ isMask: true })],
    ["blend", shape({ blendMode: "MULTIPLY" })],
    ["vector", shape({ type: "VECTOR" })],
    ["boolean", shape({ type: "BOOLEAN_OPERATION" })],
    ["star", shape({ type: "STAR" })],
    ["polygon", shape({ type: "POLYGON" })],
    ["line", shape({ type: "LINE" })]
  ];
  for (const [label, node] of unsupported) assert.equal(classifyNode(node), "raster", label);

  const supportedGroup = shape({ type: "GROUP", fills: [], children: [nativeRect] });
  const unsupportedGroup = shape({
    type: "GROUP",
    fills: [],
    children: [nativeRect, shape({ id: "gradient", fills: [{ type: "GRADIENT_LINEAR" }] })]
  });
  assert.equal(classifyNode(supportedGroup), "group");
  assert.equal(classifyNode(unsupportedGroup), "raster");
});

test("rasterizes an unsupported group subtree once without serializing hidden child duplicates", async () => {
  const vector = shape({ id: "vector-child", name: "Vector_Child", type: "VECTOR" });
  const group = shape({
    id: "unsupported-group",
    name: "FX_UnsupportedSubtree",
    type: "GROUP",
    fills: [],
    children: [shape({ id: "native-child", name: "Native_Child" }), vector]
  });
  const exported = rasterAsset("unsupported-subtree-png");
  const exportedIds: string[] = [];

  const frame = await serializeFrame(root([group]), { duration: 28 }, {
    rasterScale: 1,
    exportRaster: async (node) => {
      exportedIds.push(node.id);
      return exported;
    }
  });

  assert.deepEqual(exportedIds, ["unsupported-group"]);
  assert.equal(frame.children.length, 1);
  assert.equal(frame.children[0]?.kind, "raster");
  assert.throws(() => findNode(frame, "Native_Child"), /missing exported node/);
  assert.deepEqual(frame.warnings, [{
    nodeId: "unsupported-group",
    nodeName: "FX_UnsupportedSubtree",
    property: "children[1].type",
    fallback: "png"
  }]);
});

test("fails actionably instead of emitting output outside shared asset and nesting limits", async () => {
  const tooManyRasters = Array.from({ length: LIMITS.maxAssets + 1 }, (_, index) => shape({
    id: `vector-${index}`,
    name: `Vector_${index}`,
    type: "VECTOR",
    rasterAsset: {
      hash: "91b7dd04852a6066e94c10823e37d0f843cfa6e6699e4573733d8183f34fae1e",
      bytesBase64: "dmVjdG9yLXBuZw=="
    }
  }));
  await assert.rejects(
    serializeFrame(root(tooManyRasters), { duration: 28 }, { rasterScale: 1 }),
    /children\[2048\].*2,048-asset limit/i
  );

  let nested = shape({ id: "leaf", name: "Leaf" });
  for (let depth = 29; depth >= 0; depth -= 1) {
    nested = shape({
      id: `group-${depth}`,
      name: `Group_${depth}`,
      type: "GROUP",
      fills: [],
      children: [nested]
    });
  }
  await assert.rejects(
    serializeFrame(root([nested]), { duration: 28 }, { rasterScale: 1 }),
    /children\[0\].*nesting.*64-level limit/i
  );
});

test("rejects a serialized frame above the shared manifest-byte limit", { concurrency: false }, async () => {
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
    await assert.rejects(
      serializeFrame(root([shape()]), { duration: 28 }, { rasterScale: 1 }),
      /manifest-byte limit/i
    );
  } finally {
    Object.defineProperty(globalThis, "TextEncoder", {
      configurable: true,
      value: OriginalTextEncoder,
      writable: true
    });
  }
});

test("rejects invalid frame data with source paths rather than mutating or silently dropping it", async () => {
  await assert.rejects(
    serializeFrame(root([shape({ name: "unsafe/name" })]), { duration: 28 }, { rasterScale: 1 }),
    /\$\.children\[0\]\.name.*unsafe/i
  );
  await assert.rejects(
    serializeFrame(root([shape({ width: Number.NaN })]), { duration: 28 }, { rasterScale: 1 }),
    /\$\.children\[0\]\.width.*finite/i
  );
  await assert.rejects(
    serializeFrame(root([shape({ id: "duplicate" }), shape({ id: "duplicate" })]), { duration: 28 }, { rasterScale: 1 }),
    /\$\.children\[1\]\.id.*duplicate/i
  );
});
