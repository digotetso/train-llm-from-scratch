import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import { validatePackage } from "../src/shared/contract.ts";
import type { ExportFrame, ExportNode, GroupNode } from "../src/shared/contract.ts";
import { LIMITS } from "../src/shared/limits.ts";
import { makeValidPackage } from "./helpers/package.ts";
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

function textSnapshot(overrides: Partial<FigmaNodeSnapshot> = {}): FigmaNodeSnapshot {
  return {
    id: "text-leaf",
    name: "Text_Leaf",
    type: "TEXT",
    width: 104,
    height: 112,
    opacity: 1,
    absoluteTransform: matrix(0, 0),
    fills: [solid()],
    strokes: [],
    effects: [],
    blendMode: "NORMAL",
    isMask: false,
    characters: "θ",
    textAlignHorizontal: "LEFT",
    lineHeightPx: 112,
    letterSpacingPx: 0,
    styledTextSegments: [{
      start: 0,
      end: 1,
      fontFamily: "Sora",
      fontStyle: "Bold",
      fontSize: 96,
      fill: solid()
    }],
    ...overrides
  };
}

function rootWithNestedText(groupCount: number): FigmaNodeSnapshot {
  let nested = textSnapshot();
  for (let depth = groupCount - 1; depth >= 0; depth -= 1) {
    nested = shape({
      id: `text-depth-group-${depth}`,
      name: `Text_Depth_Group_${depth}`,
      type: "GROUP",
      fills: [],
      children: [nested]
    });
  }
  return root([nested]);
}

function root(
  children: FigmaNodeSnapshot[],
  overrides: Partial<FigmaNodeSnapshot> = {}
): FigmaNodeSnapshot {
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
    children,
    ...overrides
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

test("rejects scale, reflection, and shear that the shared transform cannot express", async () => {
  const cases: Array<[string, FigmaNodeSnapshot["absoluteTransform"]]> = [
    ["scale", [[2, 0, 10], [0, 2, 20]]],
    ["reflection", [[-1, 0, 10], [0, 1, 20]]],
    ["shear", [[1, 0.25, 10], [0, 1, 20]]]
  ];
  for (const [label, absoluteTransform] of cases) {
    await assert.rejects(
      serializeFrame(root([shape({ absoluteTransform })]), { duration: 28 }, { rasterScale: 1 }),
      /\$\.children\[0\]\.absoluteTransform.*scale, reflection, or shear/i,
      label
    );
  }
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
  const gradient = findNode(frame, "FX_GradientRect");
  assert.equal(gradient.kind, "raster");
  assert.equal(gradient.opacity, 1, "raster bytes bake node opacity and must not be dimmed twice");
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

test("keeps a PASS_THROUGH selected frame editable instead of rasterizing its root", async () => {
  const rasterized: string[] = [];
  const frame = await serializeFrame(
    root([
      shape({ id: "native-root-child", name: "Native_Root_Child" })
    ], { blendMode: "PASS_THROUGH" }),
    { duration: 28 },
    {
      rasterScale: 1,
      exportRaster: async (node) => {
        rasterized.push(node.id);
        return rasterAsset(node.id);
      }
    }
  );

  assert.deepEqual(rasterized, []);
  assert.equal(findNode(frame, "Native_Root_Child").kind, "rect");
  assert.deepEqual(frame.warnings, []);
});

test("keeps nested PASS_THROUGH groups and instances editable", async () => {
  const instance = shape({
    id: "pass-through-instance",
    name: "Pass_Through_Instance",
    type: "INSTANCE",
    fills: [],
    blendMode: "PASS_THROUGH",
    children: [shape({ id: "instance-leaf", name: "Instance_Leaf" })]
  });
  const group = shape({
    id: "pass-through-group",
    name: "Pass_Through_Group",
    type: "GROUP",
    fills: [],
    blendMode: "PASS_THROUGH",
    children: [instance]
  });
  const rasterized: string[] = [];

  const frame = await serializeFrame(root([group]), { duration: 28 }, {
    rasterScale: 1,
    exportRaster: async (node) => {
      rasterized.push(node.id);
      return rasterAsset(node.id);
    }
  });

  assert.deepEqual(rasterized, []);
  assert.equal(findNode(frame, "Pass_Through_Group").kind, "group");
  assert.equal(findNode(frame, "Pass_Through_Instance").kind, "group");
  assert.equal(findNode(frame, "Instance_Leaf").kind, "rect");
  assert.deepEqual(frame.warnings, []);
});

test("rasterizes nonstandard container blends and PASS_THROUGH non-containers", async () => {
  const multiplyGroup = shape({
    id: "multiply-group",
    name: "Multiply_Group",
    type: "GROUP",
    fills: [],
    blendMode: "MULTIPLY",
    children: [shape({ id: "multiply-child", name: "Multiply_Child" })]
  });
  const passThroughShape = shape({
    id: "pass-through-shape",
    name: "Pass_Through_Shape",
    blendMode: "PASS_THROUGH"
  });
  const rasterized: string[] = [];

  const frame = await serializeFrame(root([multiplyGroup, passThroughShape]), { duration: 28 }, {
    rasterScale: 1,
    exportRaster: async (node) => {
      rasterized.push(node.id);
      return rasterAsset(node.id);
    }
  });

  assert.deepEqual(rasterized, ["multiply-group", "pass-through-shape"]);
  assert.equal(findNode(frame, "Multiply_Group").kind, "raster");
  assert.equal(findNode(frame, "Pass_Through_Shape").kind, "raster");
  assert.deepEqual(frame.warnings, [
    { nodeId: "multiply-group", nodeName: "Multiply_Group", property: "blendMode", fallback: "png" },
    { nodeId: "pass-through-shape", nodeName: "Pass_Through_Shape", property: "blendMode", fallback: "png" }
  ]);
});

test("serializes one opaque root fill as an editable full-frame background behind children", async () => {
  const rasterized: string[] = [];
  const frame = await serializeFrame(
    root([shape({ id: "foreground", name: "Foreground" })], {
      fills: [solid()],
      blendMode: "PASS_THROUGH"
    }),
    { duration: 28 },
    {
      rasterScale: 1,
      exportRaster: async (node) => {
        rasterized.push(node.id);
        return rasterAsset(node.id);
      }
    }
  );

  assert.deepEqual(rasterized, []);
  assert.deepEqual(frame.children.map((node) => node.name), [
    "S001_SH32_TestFrame__ROOT_SOLID_BACKGROUND",
    "Foreground"
  ]);
  assert.deepEqual(frame.children[0], {
    id: "frame-root::root-solid-background",
    name: "S001_SH32_TestFrame__ROOT_SOLID_BACKGROUND",
    kind: "rect",
    x: 0,
    y: 0,
    width: 1920,
    height: 1080,
    rotation: 0,
    opacity: 1,
    fill: "#4080BF",
    stroke: null,
    strokeWidth: 0,
    radius: 0
  });
  assert.equal(frame.children[1]?.kind, "rect");
  assert.deepEqual(frame.warnings, []);

  const packageValue = makeValidPackage();
  packageValue.frames = [frame];
  assert.deepEqual(validatePackage(packageValue).frames[0], frame);
});

test("serializes a supported root fill and border as one editable surface", async () => {
  const rasterized: string[] = [];
  const frame = await serializeFrame(root([
    shape({ id: "bordered-foreground", name: "Bordered_Foreground" })
  ], {
    fills: [solid()],
    strokes: [solid(0.1, 0.2, 0.3)],
    strokeWeight: 6,
    cornerRadius: 24,
    blendMode: "PASS_THROUGH"
  }), { duration: 28 }, {
    rasterScale: 1,
    exportRaster: async (node) => {
      rasterized.push(node.id);
      return rasterAsset(node.id);
    }
  });

  assert.deepEqual(rasterized, []);
  assert.deepEqual(frame.children[0], {
    id: "frame-root::root-solid-background",
    name: "S001_SH32_TestFrame__ROOT_SOLID_BACKGROUND",
    kind: "rect",
    x: 0,
    y: 0,
    width: 1920,
    height: 1080,
    rotation: 0,
    opacity: 1,
    fill: "#4080BF",
    stroke: "#1A334D",
    strokeWidth: 6,
    radius: 24
  });
  assert.equal(frame.children[1]?.name, "Bordered_Foreground");
  assert.deepEqual(frame.warnings, []);
});

test("reserves a collision-safe synthetic root background identity", async () => {
  const reservedId = "frame-root::root-solid-background";
  const frame = await serializeFrame(root([
    shape({ id: reservedId, name: "Existing_Reserved_Id" })
  ], { fills: [solid()] }), { duration: 28 }, { rasterScale: 1 });

  assert.equal(frame.children[0]?.id, `${reservedId}:2`);
  assert.equal(frame.children[0]?.name, "S001_SH32_TestFrame__ROOT_SOLID_BACKGROUND");
  assert.equal(frame.children[1]?.id, reservedId);
  assert.equal(new Set([frame.nodeId, ...frame.children.map((node) => node.id)]).size, 3);

  const packageValue = makeValidPackage();
  packageValue.frames = [frame];
  assert.deepEqual(validatePackage(packageValue).frames[0], frame);
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
  assert.deepEqual(calls, [{
    id: "96:5",
    request: { format: "PNG", scale: 2, appearance: "BAKED" }
  }]);

  await assert.rejects(
    serializeFrame(source, { duration: 28 }, {
      rasterScale: 1,
      exportRaster: async () => ({ ...exported, hash: "0".repeat(64) })
    }),
    /children\[0\].*hash.*bytes/i
  );
});

test("rasterizes the selected frame once when its direct appearance cannot be represented", async () => {
  const baked = rasterAsset("full-selected-frame-baked-appearance");
  const cases: Array<[string, string, Partial<FigmaNodeSnapshot>]> = [
    ["gradient fill", "fills", { fills: [{ type: "GRADIENT_LINEAR" }] }],
    ["image fill", "fills", { fills: [{ type: "IMAGE", imageHash: "root-image" }] }],
    ["multiple fills", "fills", { fills: [solid(), solid(0.1, 0.2, 0.3)] }],
    ["transparent fill", "fills", { fills: [{ ...solid(), opacity: 0.5 }] }],
    ["stroke without fill", "strokes", { fills: [], strokes: [solid()], strokeWeight: 2 }],
    ["gradient stroke", "strokes", { fills: [solid()], strokes: [{ type: "GRADIENT_LINEAR" }], strokeWeight: 2 }],
    ["image stroke", "strokes", { fills: [solid()], strokes: [{ type: "IMAGE", imageHash: "root-stroke" }], strokeWeight: 2 }],
    ["transparent stroke", "strokes", { fills: [solid()], strokes: [{ ...solid(), opacity: 0.5 }], strokeWeight: 2 }],
    ["multiple strokes", "strokes", { fills: [solid()], strokes: [solid(), solid()], strokeWeight: 2 }],
    ["missing stroke weight", "strokeWeight", { fills: [solid()], strokes: [solid()] }],
    ["negative stroke weight", "strokeWeight", { fills: [solid()], strokes: [solid()], strokeWeight: -1 }],
    ["nonfinite stroke weight", "strokeWeight", { fills: [solid()], strokes: [solid()], strokeWeight: Number.NaN }],
    ["mixed corner radius", "cornerRadius", { fills: [solid()], cornerRadius: "MIXED" }],
    ["negative corner radius", "cornerRadius", { fills: [solid()], cornerRadius: -1 }],
    ["nonfinite corner radius", "cornerRadius", { fills: [solid()], cornerRadius: Number.NaN }],
    ["effects", "effects", { effects: [{ type: "DROP_SHADOW", visible: true }] }],
    ["isMask", "isMask", { isMask: true }],
    ["blendMode", "blendMode", { blendMode: "MULTIPLY" }],
    ["opacity", "opacity", { opacity: 0.4 }],
    ["visible", "visible", { visible: false }]
  ];

  for (const [label, property, appearance] of cases) {
    const source = root([
      shape({ id: `${label}-child`, name: `${label}_Child` }),
      shape({ id: `${label}-hidden`, name: `${label}_Hidden` })
    ], appearance);
    const calls: Array<{ id: string; request: RasterExportRequest }> = [];
    const frame = await serializeFrame(source, { duration: 28 }, {
      rasterScale: 2,
      exportRaster: async (node, request) => {
        calls.push({ id: node.id, request });
        return baked;
      }
    });

    assert.deepEqual(calls, [{
      id: "frame-root",
      request: { format: "PNG", scale: 2, appearance: "BAKED" }
    }], label);
    assert.equal(frame.children.length, 1, label);
    assert.deepEqual(frame.children[0], {
      id: "frame-root::root-raster-fallback",
      name: "S001_SH32_TestFrame__ROOT_RASTER_FALLBACK",
      kind: "raster",
      x: 0,
      y: 0,
      width: 1920,
      height: 1080,
      rotation: 0,
      opacity: 1,
      assetHash: baked.hash
    }, label);
    assert.deepEqual(frame.warnings, [{
      nodeId: "frame-root",
      nodeName: "S001_SH32_TestFrame",
      property,
      fallback: "png"
    }], label);
    assert.throws(() => findNode(frame, `${label}_Child`), /missing exported node/, label);
  }
});

test("does not collapse a neutral selected frame merely because one child needs fallback", async () => {
  const gradient = shape({
    id: "gradient-child",
    name: "Gradient_Child",
    fills: [{ type: "GRADIENT_LINEAR" }]
  });
  const native = shape({ id: "native-child", name: "Native_Child" });
  const exported = rasterAsset("gradient-child-baked");
  const calls: string[] = [];

  const frame = await serializeFrame(root([native, gradient]), { duration: 28 }, {
    rasterScale: 1,
    exportRaster: async (node) => {
      calls.push(node.id);
      return exported;
    }
  });

  assert.deepEqual(calls, ["gradient-child"]);
  assert.deepEqual(frame.children.map((node) => [node.name, node.kind]), [
    ["Native_Child", "rect"],
    ["Gradient_Child", "raster"]
  ]);
});

test("fails root rasterization actionably when faithful baked appearance is unavailable", async () => {
  const source = root([shape()], { fills: [{ type: "GRADIENT_LINEAR" }] });
  await assert.rejects(
    serializeFrame(source, { duration: 28 }, { rasterScale: 1 }),
    /\$.*frame-root.*root raster|raster fallback/i
  );
  await assert.rejects(
    serializeFrame(source, { duration: 28 }, {
      rasterScale: 1,
      exportRaster: async () => {
        throw new Error("root renderer unavailable");
      }
    }),
    /\$.*frame-root.*S001_SH32_TestFrame.*root renderer unavailable/i
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

test("allows more raster nodes than the asset limit when they dedupe to one verified hash", async () => {
  const deduplicatedRasters = Array.from({ length: LIMITS.maxAssets + 1 }, (_, index) => shape({
    id: `vector-${index}`,
    name: `Vector_${index}`,
    type: "VECTOR",
    rasterAsset: {
      hash: "91b7dd04852a6066e94c10823e37d0f843cfa6e6699e4573733d8183f34fae1e",
      bytesBase64: "dmVjdG9yLXBuZw=="
    }
  }));
  const frame = await serializeFrame(
    root(deduplicatedRasters),
    { duration: 28 },
    { rasterScale: 1 }
  );
  assert.equal(frame.children.length, LIMITS.maxAssets + 1);
  assert.equal(frame.warnings.length, LIMITS.maxAssets + 1);
  assert.equal(new Set(frame.children.map((node) => node.kind === "raster" ? node.assetHash : "")).size, 1);
});

test("rejects a new verified hash only when the configured unique-asset limit is exceeded", async () => {
  const rasters = ["asset-a", "asset-b", "asset-c"].map((id) => shape({
    id,
    name: id.replace("-", "_"),
    type: "VECTOR"
  }));
  await assert.rejects(
    serializeFrame(root(rasters), { duration: 28 }, {
      rasterScale: 1,
      limits: { maxAssets: 2 },
      exportRaster: async (node) => rasterAsset(node.id)
    }),
    /children\[2\].*unique.*2-asset limit/i
  );
});

test("enforces decoded per-asset and unique aggregate byte limits using real bytes", async () => {
  const first = shape({ id: "asset-first", name: "Asset_First", type: "VECTOR" });
  const second = shape({ id: "asset-second", name: "Asset_Second", type: "VECTOR" });

  await assert.rejects(
    serializeFrame(root([first]), { duration: 28 }, {
      rasterScale: 1,
      limits: { maxAssetBytes: 3 },
      exportRaster: async () => rasterAsset("four")
    }),
    /children\[0\].*per-asset limit/i
  );
  await assert.rejects(
    serializeFrame(root([first, second]), { duration: 28 }, {
      rasterScale: 1,
      limits: { maxAssetBytes: 4, maxAggregateAssetBytes: 7 },
      exportRaster: async (node) => rasterAsset(node.id === "asset-first" ? "aaaa" : "bbbb")
    }),
    /children\[1\].*aggregate decoded-byte limit/i
  );

  const deduped = await serializeFrame(root([first, second]), { duration: 28 }, {
    rasterScale: 1,
    limits: { maxAssetBytes: 4, maxAggregateAssetBytes: 4 },
    exportRaster: async () => rasterAsset("same")
  });
  assert.equal(deduped.children.length, 2);
});

test("rejects noncanonical embedded raster base64 before accepting its hash", async () => {
  const invalid = shape({
    id: "bad-base64",
    name: "Bad_Base64",
    type: "VECTOR",
    rasterAsset: {
      hash: rasterAsset("f").hash,
      bytesBase64: "Zh=="
    }
  });
  await assert.rejects(
    serializeFrame(root([invalid]), { duration: 28 }, { rasterScale: 1 }),
    /children\[0\].*canonical base64/i
  );
});

test("matches shared container-depth validation at the nested text-leaf boundary", async () => {
  const accepted = await serializeFrame(
    rootWithNestedText(28),
    { duration: 28 },
    { rasterScale: 1 }
  );
  const acceptedPackage = makeValidPackage();
  acceptedPackage.frames = [accepted];
  assert.doesNotThrow(() => validatePackage(acceptedPackage));

  const extraGroup: GroupNode = {
    id: "shared-depth-extra-group",
    name: "Shared_Depth_Extra_Group",
    kind: "group",
    x: 0,
    y: 0,
    width: 100,
    height: 50,
    rotation: 0,
    opacity: 1,
    children: accepted.children
  };
  const rejectedByShared = makeValidPackage();
  rejectedByShared.frames = [{ ...accepted, children: [extraGroup] }];
  assert.throws(() => validatePackage(rejectedByShared), /nesting.*64-level limit/i);

  await assert.rejects(
    serializeFrame(rootWithNestedText(29), { duration: 28 }, { rasterScale: 1 }),
    /nesting.*64-level limit/i
  );
});

test("rejects a real serialized frame above a lower non-raisable manifest seam", async () => {
  await assert.rejects(
    serializeFrame(root([shape()]), { duration: 28 }, {
      rasterScale: 1,
      limits: { maxManifestBytes: 1 }
    }),
    /manifest-byte limit/i
  );
  await assert.rejects(
    serializeFrame(root([shape()]), { duration: 28 }, {
      rasterScale: 1,
      limits: { maxManifestBytes: LIMITS.maxManifestBytes + 1 }
    }),
    /maxManifestBytes.*shared ceiling/i
  );
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

test("rejects dot-segment frame and nested names exactly like the shared contract", async () => {
  for (const name of [".", ".."]) {
    await assert.rejects(
      serializeFrame(root([shape()], { name }), { duration: 28 }, { rasterScale: 1 }),
      /\$\.name.*unsafe/i,
      `frame ${name}`
    );
    await assert.rejects(
      serializeFrame(root([shape({ name })]), { duration: 28 }, { rasterScale: 1 }),
      /\$\.children\[0\]\.name.*unsafe/i,
      `nested ${name}`
    );
  }
});
