import type {
  ExportFrame,
  ExportNode,
  GroupNode,
  ShapeNode,
  TextNode,
  TextRun
} from "../shared/contract.ts";
import { assertJsonContainerDepth, isSafeExporterName } from "../shared/contract.ts";
import { LIMITS } from "../shared/limits.ts";
import { sha256Hex } from "../shared/sha256.ts";
import { utf8ByteLength } from "../shared/utf8.ts";

export type TransformMatrix = readonly [
  readonly [number, number, number],
  readonly [number, number, number]
];

export interface FigmaColorSnapshot {
  r: number;
  g: number;
  b: number;
}

export interface FigmaPaintSnapshot {
  type: string;
  color?: FigmaColorSnapshot;
  opacity?: number;
  visible?: boolean;
  imageHash?: string;
}

export interface StyledTextSegmentSnapshot {
  start: number;
  end: number;
  fontFamily?: string;
  fontStyle?: string;
  fontName?: { family: string; style: string };
  fontSize: number;
  fill?: FigmaPaintSnapshot;
  fills?: readonly FigmaPaintSnapshot[];
}

export interface EmbeddedRasterAsset {
  hash: string;
  bytesBase64: string;
}

/**
 * A JSON-safe, normalized subset of Figma scene-node data. Adapters own all
 * Figma API access; this serializer only consumes snapshots.
 */
export interface FigmaNodeSnapshot {
  id: string;
  name: string;
  type: string;
  width: number;
  height: number;
  opacity?: number;
  visible?: boolean;
  absoluteTransform: TransformMatrix;
  fills?: readonly FigmaPaintSnapshot[];
  strokes?: readonly FigmaPaintSnapshot[];
  strokeWeight?: number;
  cornerRadius?: number | "MIXED";
  effects?: readonly { type: string; visible?: boolean }[];
  blendMode?: string;
  isMask?: boolean;
  children?: readonly FigmaNodeSnapshot[];
  characters?: string;
  textAlignHorizontal?: string;
  lineHeightPx?: number;
  letterSpacingPx?: number;
  styledTextSegments?: readonly StyledTextSegmentSnapshot[];
  rasterAsset?: EmbeddedRasterAsset;
}

export interface RasterExportRequest {
  format: "PNG";
  scale: number;
  /** The returned PNG must include the node's rendered opacity and effects. */
  appearance: "BAKED";
}

export interface RasterExportResult {
  hash: string;
  bytes: Uint8Array;
}

export interface SerializeFrameOptions {
  rasterScale: number;
  exportRaster?: (
    node: FigmaNodeSnapshot,
    request: RasterExportRequest
  ) => Promise<RasterExportResult>;
  /** Test/host seams may lower, but never raise, shared package ceilings. */
  limits?: Partial<SerializerLimits>;
}

export interface SerializerLimits {
  maxAssets: number;
  maxAssetBytes: number;
  maxAggregateAssetBytes: number;
  maxManifestBytes: number;
}

export interface FrameTiming {
  duration: number;
}

type Classification = "native" | "group" | "raster";
type MutableMatrix = [[number, number, number], [number, number, number]];

interface SerializationContext {
  rootInverse: MutableMatrix;
  options: SerializeFrameOptions;
  warnings: ExportFrame["warnings"];
  rasterBytes: number;
  assetHashes: Set<string>;
  limits: SerializerLimits;
}

const GROUP_TYPES = new Set(["FRAME", "GROUP", "COMPONENT", "INSTANCE"]);
const HASH_PATTERN = /^[0-9a-f]{64}$/;
const BASE64_PATTERN = /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/;
const BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
const MATRIX_TOLERANCE = 1e-8;
const ROUNDING_FACTOR = 1e9;

function invalid(path: string, message: string): never {
  throw new TypeError(`Invalid normalized Figma snapshot at ${path}: ${message}`);
}

function finiteNumber(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) invalid(path, "expected a finite number");
  return value;
}

function positiveNumber(value: unknown, path: string): number {
  const number = finiteNumber(value, path);
  if (number <= 0) invalid(path, "expected a positive number");
  return number;
}

function nonNegativeNumber(value: unknown, path: string): number {
  const number = finiteNumber(value, path);
  if (number < 0) invalid(path, "expected a non-negative number");
  return number;
}

function nonEmptyString(value: unknown, path: string): string {
  if (typeof value !== "string" || value.length === 0) invalid(path, "expected a non-empty string");
  return value;
}

function safeName(value: unknown, path: string): string {
  const name = nonEmptyString(value, path);
  if (!isSafeExporterName(name)) invalid(path, "unsafe name");
  return name;
}

function exactInteger(value: unknown, path: string): number {
  const number = finiteNumber(value, path);
  if (!Number.isSafeInteger(number)) invalid(path, "expected a safe integer");
  return number;
}

function effectiveLimit(value: unknown, ceiling: number, path: string): number {
  if (value === undefined) return ceiling;
  const limit = exactInteger(value, path);
  if (limit < 0 || limit > ceiling) {
    invalid(path, `expected a non-negative integer no greater than shared ceiling ${ceiling}`);
  }
  return limit;
}

function rounded(value: number): number {
  const result = Math.round(value * ROUNDING_FACTOR) / ROUNDING_FACTOR;
  return Object.is(result, -0) ? 0 : result;
}

function validateMatrix(value: TransformMatrix, path: string): MutableMatrix {
  if (!Array.isArray(value) || value.length !== 2 ||
      !Array.isArray(value[0]) || value[0].length !== 3 ||
      !Array.isArray(value[1]) || value[1].length !== 3) {
    invalid(path, "expected a 2x3 absoluteTransform matrix");
  }
  return [
    [
      finiteNumber(value[0][0], `${path}[0][0]`),
      finiteNumber(value[0][1], `${path}[0][1]`),
      finiteNumber(value[0][2], `${path}[0][2]`)
    ],
    [
      finiteNumber(value[1][0], `${path}[1][0]`),
      finiteNumber(value[1][1], `${path}[1][1]`),
      finiteNumber(value[1][2], `${path}[1][2]`)
    ]
  ];
}

function invertMatrix(matrix: MutableMatrix, path: string): MutableMatrix {
  const [[a, c, tx], [b, d, ty]] = matrix;
  const determinant = a * d - b * c;
  if (Math.abs(determinant) <= MATRIX_TOLERANCE) invalid(path, "absoluteTransform matrix is singular");
  return [
    [d / determinant, -c / determinant, (c * ty - d * tx) / determinant],
    [-b / determinant, a / determinant, (b * tx - a * ty) / determinant]
  ];
}

function multiplyMatrices(left: MutableMatrix, right: MutableMatrix): MutableMatrix {
  const [[la, lc, ltx], [lb, ld, lty]] = left;
  const [[ra, rc, rtx], [rb, rd, rty]] = right;
  return [
    [la * ra + lc * rb, la * rc + lc * rd, la * rtx + lc * rty + ltx],
    [lb * ra + ld * rb, lb * rc + ld * rd, lb * rtx + ld * rty + lty]
  ];
}

function relativeGeometry(
  node: FigmaNodeSnapshot,
  path: string,
  rootInverse: MutableMatrix
): Pick<ExportNode, "x" | "y" | "width" | "height" | "rotation" | "opacity"> {
  const sourceWidth = positiveNumber(node.width, `${path}.width`);
  const sourceHeight = positiveNumber(node.height, `${path}.height`);
  const relative = multiplyMatrices(rootInverse, validateMatrix(node.absoluteTransform, `${path}.absoluteTransform`));
  const [[a, c, x], [b, d, y]] = relative;
  const scaleX = Math.hypot(a, b);
  const scaleY = Math.hypot(c, d);
  const dot = a * c + b * d;
  const determinant = a * d - b * c;
  if (determinant <= 0 || Math.abs(dot) > MATRIX_TOLERANCE ||
      Math.abs(scaleX - 1) > MATRIX_TOLERANCE || Math.abs(scaleY - 1) > MATRIX_TOLERANCE) {
    invalid(
      `${path}.absoluteTransform`,
      "scale, reflection, or shear cannot be represented by the shared transform contract"
    );
  }
  let rotation = Math.atan2(b, a) * 180 / Math.PI;
  if (rotation <= -180) rotation += 360;
  if (rotation > 180) rotation -= 360;
  const opacity = node.opacity === undefined ? 1 : finiteNumber(node.opacity, `${path}.opacity`);
  if (opacity < 0 || opacity > 1) invalid(`${path}.opacity`, "expected a number between 0 and 1");
  return {
    x: rounded(x),
    y: rounded(y),
    width: sourceWidth,
    height: sourceHeight,
    rotation: rounded(rotation),
    opacity
  };
}

function visibleEffects(node: FigmaNodeSnapshot): readonly { type: string; visible?: boolean }[] {
  return (node.effects ?? []).filter((effect) => effect.visible !== false);
}

function hasRepresentableBlendMode(node: FigmaNodeSnapshot): boolean {
  return node.blendMode === undefined ||
    node.blendMode === "NORMAL" ||
    (node.blendMode === "PASS_THROUGH" && GROUP_TYPES.has(node.type));
}

function rootAppearanceReason(node: FigmaNodeSnapshot): string | null {
  if (node.visible === false) return "visible";
  if (node.isMask === true) return "isMask";
  if (!hasRepresentableBlendMode(node)) return "blendMode";
  if (visibleEffects(node).length > 0) return "effects";
  if ((node.fills ?? []).some((paint) => paint.visible !== false) && rootSolidFill(node) === undefined) return "fills";
  if ((node.strokes ?? []).some((paint) => paint.visible !== false)) return "strokes";
  if (node.opacity !== undefined && node.opacity !== 1) return "opacity";
  return null;
}

function isOpaqueSolid(paint: FigmaPaintSnapshot | undefined): boolean {
  if (paint?.type !== "SOLID" || paint.visible === false || paint.color === undefined) return false;
  if (paint.opacity !== undefined && paint.opacity !== 1) return false;
  const { r, g, b } = paint.color;
  return [r, g, b].every((channel) => typeof channel === "number" && Number.isFinite(channel) && channel >= 0 && channel <= 1);
}

function rootSolidFill(node: FigmaNodeSnapshot): FigmaPaintSnapshot | undefined {
  const fills = node.fills ?? [];
  return fills.length === 1 && isOpaqueSolid(fills[0]) ? fills[0] : undefined;
}

function segmentPaint(segment: StyledTextSegmentSnapshot): FigmaPaintSnapshot | undefined {
  if (segment.fill !== undefined) return segment.fill;
  return segment.fills?.length === 1 ? segment.fills[0] : undefined;
}

function directRasterReason(node: FigmaNodeSnapshot): string | null {
  if (node.visible === false) return "visible";
  if (node.isMask === true) return "isMask";
  if (!hasRepresentableBlendMode(node)) return "blendMode";
  if (visibleEffects(node).length > 0) return "effects";

  if (node.type === "TEXT") {
    if (node.fills?.length !== 1 || !isOpaqueSolid(node.fills[0])) return "fills";
    if ((node.strokes?.length ?? 0) !== 0) return "strokes";
    if (typeof node.characters !== "string") return "characters";
    if (!Array.isArray(node.styledTextSegments) || node.styledTextSegments.length === 0) {
      return "styledTextSegments";
    }
    for (let index = 0; index < node.styledTextSegments.length; index += 1) {
      if (!isOpaqueSolid(segmentPaint(node.styledTextSegments[index]!))) {
        return `styledTextSegments[${index}].fill`;
      }
    }
    if (node.textAlignHorizontal !== "LEFT" &&
        node.textAlignHorizontal !== "CENTER" &&
        node.textAlignHorizontal !== "RIGHT") return "textAlignHorizontal";
    if (typeof node.lineHeightPx !== "number" || !Number.isFinite(node.lineHeightPx) || node.lineHeightPx <= 0) {
      return "lineHeightPx";
    }
    if (typeof node.letterSpacingPx !== "number" || !Number.isFinite(node.letterSpacingPx)) {
      return "letterSpacingPx";
    }
    return null;
  }

  if (node.type === "RECTANGLE" || node.type === "ELLIPSE") {
    if (node.fills?.length !== 1 || !isOpaqueSolid(node.fills[0])) return "fills";
    const strokes = node.strokes ?? [];
    if (strokes.length > 1 || (strokes.length === 1 && !isOpaqueSolid(strokes[0]))) return "strokes";
    if (
      strokes.length === 1 &&
      (typeof node.strokeWeight !== "number" || !Number.isFinite(node.strokeWeight) || node.strokeWeight < 0)
    ) return "strokeWeight";
    if (node.type === "RECTANGLE" && node.cornerRadius === "MIXED") return "cornerRadius";
    return null;
  }

  if (GROUP_TYPES.has(node.type)) {
    if ((node.fills?.length ?? 0) !== 0) return "fills";
    if ((node.strokes?.length ?? 0) !== 0) return "strokes";
    if (!Array.isArray(node.children)) return "children";
    return null;
  }

  return "type";
}

function rasterReason(
  node: FigmaNodeSnapshot,
  path: string,
  ancestors: Set<object>
): string | null {
  if (node === null || typeof node !== "object") invalid(path, "expected a node object");
  if (ancestors.has(node)) invalid(path, "node hierarchy must not contain a cycle");
  const direct = directRasterReason(node);
  if (direct !== null || !GROUP_TYPES.has(node.type)) return direct;
  ancestors.add(node);
  try {
    const children = node.children ?? [];
    for (let index = 0; index < children.length; index += 1) {
      const childReason = rasterReason(children[index]!, `${path}.children[${index}]`, ancestors);
      if (childReason !== null) return `children[${index}].${childReason}`;
    }
    return null;
  } finally {
    ancestors.delete(node);
  }
}

export function classifyNode(node: FigmaNodeSnapshot): Classification {
  const reason = rasterReason(node, "$", new Set());
  if (reason !== null) return "raster";
  return GROUP_TYPES.has(node.type) ? "group" : "native";
}

function colorHex(paint: FigmaPaintSnapshot, path: string): string {
  if (!isOpaqueSolid(paint) || paint.color === undefined) invalid(path, "expected one opaque SOLID paint");
  const channels = [paint.color.r, paint.color.g, paint.color.b]
    .map((channel) => Math.round(channel * 255).toString(16).padStart(2, "0").toUpperCase());
  return `#${channels.join("")}`;
}

function validateNodeIdentity(node: FigmaNodeSnapshot, path: string, ids: Set<string>): void {
  const id = nonEmptyString(node.id, `${path}.id`);
  if (ids.has(id)) invalid(`${path}.id`, `duplicate node ID ${JSON.stringify(id)}`);
  ids.add(id);
  safeName(node.name, `${path}.name`);
  positiveNumber(node.width, `${path}.width`);
  positiveNumber(node.height, `${path}.height`);
  validateMatrix(node.absoluteTransform, `${path}.absoluteTransform`);
  if (node.opacity !== undefined) {
    const opacity = finiteNumber(node.opacity, `${path}.opacity`);
    if (opacity < 0 || opacity > 1) invalid(`${path}.opacity`, "expected a number between 0 and 1");
  }
}

function reserveSyntheticNodeId(frameId: string, suffix: string, ids: Set<string>): string {
  const base = nonEmptyString(`${frameId}::${suffix}`, "$.synthetic.id");
  let candidate = base;
  let collision = 2;
  while (ids.has(candidate)) {
    candidate = `${base}:${collision}`;
    collision += 1;
  }
  ids.add(candidate);
  return candidate;
}

function preflightNode(
  node: FigmaNodeSnapshot,
  path: string,
  ids: Set<string>,
  rootInverse: MutableMatrix
): void {
  validateNodeIdentity(node, path, ids);
  relativeGeometry(node, path, rootInverse);
  const reason = rasterReason(node, path, new Set());
  if (reason !== null) return;

  if (!GROUP_TYPES.has(node.type)) return;
  const children = node.children ?? [];
  for (let index = 0; index < children.length; index += 1) {
    preflightNode(children[index]!, `${path}.children[${index}]`, ids, rootInverse);
  }
}

function validateSerializedFrame(frame: ExportFrame, maxManifestBytes: number): ExportFrame {
  // Match validatePackage's exact container count without fabricating the
  // unrelated package fields: package object -> frames array -> frame object.
  assertJsonContainerDepth({ frames: [frame] });
  if (utf8ByteLength(JSON.stringify(frame)) > maxManifestBytes) {
    invalid("$", "serialized frame exceeds the shared manifest-byte limit");
  }
  return frame;
}

function baseNode(
  node: FigmaNodeSnapshot,
  path: string,
  rootInverse: MutableMatrix
): Pick<ExportNode, "id" | "name" | "x" | "y" | "width" | "height" | "rotation" | "opacity"> {
  return {
    id: nonEmptyString(node.id, `${path}.id`),
    name: safeName(node.name, `${path}.name`),
    ...relativeGeometry(node, path, rootInverse)
  };
}

function serializeRuns(node: FigmaNodeSnapshot, path: string, text: string): TextRun[] {
  const segments = node.styledTextSegments ?? [];
  return segments.map((segment, index) => {
    const segmentPath = `${path}.styledTextSegments[${index}]`;
    const start = exactInteger(segment.start, `${segmentPath}.start`);
    const end = exactInteger(segment.end, `${segmentPath}.end`);
    if (start < 0 || end <= start || end > text.length) {
      invalid(segmentPath, "text run range is outside the exact source text");
    }
    const fontFamily = segment.fontFamily ?? segment.fontName?.family;
    const fontStyle = segment.fontStyle ?? segment.fontName?.style;
    const paint = segmentPaint(segment);
    if (paint === undefined) invalid(`${segmentPath}.fill`, "expected one opaque SOLID paint");
    return {
      start,
      end,
      fontFamily: nonEmptyString(fontFamily, `${segmentPath}.fontFamily`),
      fontStyle: nonEmptyString(fontStyle, `${segmentPath}.fontStyle`),
      fontSize: positiveNumber(segment.fontSize, `${segmentPath}.fontSize`),
      color: colorHex(paint, `${segmentPath}.fill`)
    };
  });
}

function serializeText(node: FigmaNodeSnapshot, path: string, context: SerializationContext): TextNode {
  if (typeof node.characters !== "string") invalid(`${path}.characters`, "expected a string");
  const align = node.textAlignHorizontal;
  if (align !== "LEFT" && align !== "CENTER" && align !== "RIGHT") {
    invalid(`${path}.textAlignHorizontal`, "expected LEFT, CENTER, or RIGHT");
  }
  const width = positiveNumber(node.width, `${path}.width`);
  const height = positiveNumber(node.height, `${path}.height`);
  return {
    ...baseNode(node, path, context.rootInverse),
    kind: "text",
    text: node.characters,
    textBox: { width, height },
    paragraph: {
      align,
      lineHeightPx: positiveNumber(node.lineHeightPx, `${path}.lineHeightPx`),
      letterSpacingPx: finiteNumber(node.letterSpacingPx, `${path}.letterSpacingPx`)
    },
    runs: serializeRuns(node, path, node.characters)
  };
}

function serializeShape(node: FigmaNodeSnapshot, path: string, context: SerializationContext): ShapeNode {
  const fill = node.fills?.[0];
  if (fill === undefined) invalid(`${path}.fills`, "expected one opaque SOLID paint");
  const stroke = node.strokes?.[0];
  const strokeWidth = stroke === undefined
    ? 0
    : nonNegativeNumber(node.strokeWeight, `${path}.strokeWeight`);
  const radius = node.type === "RECTANGLE"
    ? nonNegativeNumber(node.cornerRadius ?? 0, `${path}.cornerRadius`)
    : 0;
  return {
    ...baseNode(node, path, context.rootInverse),
    kind: node.type === "RECTANGLE" ? "rect" : "ellipse",
    fill: colorHex(fill, `${path}.fills[0]`),
    stroke: stroke === undefined ? null : colorHex(stroke, `${path}.strokes[0]`),
    strokeWidth,
    radius
  };
}

function decodeCanonicalBase64(value: unknown, path: string): Uint8Array {
  if (typeof value !== "string" || value.length % 4 !== 0 || !BASE64_PATTERN.test(value)) {
    invalid(path, "expected canonical base64 raster bytes");
  }
  if (value.endsWith("==")) {
    const symbol = BASE64_ALPHABET.indexOf(value.charAt(value.length - 3));
    if ((symbol & 0b1111) !== 0) invalid(path, "expected canonical base64 raster bytes");
  } else if (value.endsWith("=")) {
    const symbol = BASE64_ALPHABET.indexOf(value.charAt(value.length - 2));
    if ((symbol & 0b11) !== 0) invalid(path, "expected canonical base64 raster bytes");
  }
  const padding = value.endsWith("==") ? 2 : value.endsWith("=") ? 1 : 0;
  const bytes = new Uint8Array((value.length / 4) * 3 - padding);
  let outputIndex = 0;
  for (let index = 0; index < value.length; index += 4) {
    const first = BASE64_ALPHABET.indexOf(value[index]!);
    const second = BASE64_ALPHABET.indexOf(value[index + 1]!);
    const third = value[index + 2] === "=" ? 0 : BASE64_ALPHABET.indexOf(value[index + 2]!);
    const fourth = value[index + 3] === "=" ? 0 : BASE64_ALPHABET.indexOf(value[index + 3]!);
    const packed = (first << 18) | (second << 12) | (third << 6) | fourth;
    if (outputIndex < bytes.length) bytes[outputIndex++] = (packed >> 16) & 0xff;
    if (outputIndex < bytes.length) bytes[outputIndex++] = (packed >> 8) & 0xff;
    if (outputIndex < bytes.length) bytes[outputIndex++] = packed & 0xff;
  }
  return bytes;
}

async function rasterResult(
  node: FigmaNodeSnapshot,
  path: string,
  context: SerializationContext
): Promise<RasterExportResult> {
  let result: RasterExportResult;
  if (context.options.exportRaster !== undefined) {
    try {
      result = await context.options.exportRaster(node, {
        format: "PNG",
        scale: context.options.rasterScale,
        appearance: "BAKED"
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      throw new Error(
        `Raster export failed at ${path} for node ${JSON.stringify(node.id)} (${JSON.stringify(node.name)}): ${message}`,
        { cause: error }
      );
    }
  } else if (node.rasterAsset !== undefined) {
    result = {
      hash: node.rasterAsset.hash,
      bytes: decodeCanonicalBase64(node.rasterAsset.bytesBase64, `${path}.rasterAsset.bytesBase64`)
    };
  } else {
    invalid(
      path,
      `raster fallback for node ${JSON.stringify(node.id)} (${JSON.stringify(node.name)}) requires exportRaster or a verified embedded rasterAsset`
    );
  }

  if (result === null || typeof result !== "object") invalid(path, "raster export returned no asset evidence");
  if (!HASH_PATTERN.test(result.hash)) {
    invalid(`${path}.rasterAsset.hash`, "expected 64 lowercase hexadecimal characters");
  }
  if (!(result.bytes instanceof Uint8Array)) {
    invalid(`${path}.rasterAsset.bytes`, "expected Uint8Array raster bytes");
  }
  const bytes = Uint8Array.from(result.bytes);
  if (bytes.byteLength > context.limits.maxAssetBytes) {
    invalid(`${path}.rasterAsset.bytes`, "raster asset exceeds the per-asset limit");
  }
  const actualHash = sha256Hex(bytes);
  if (actualHash !== result.hash) {
    invalid(`${path}.rasterAsset.hash`, "returned hash does not match the raster bytes");
  }
  if (!context.assetHashes.has(result.hash)) {
    if (context.assetHashes.size >= context.limits.maxAssets) {
      invalid(
        `${path}.rasterAsset.hash`,
        `unique raster assets exceed the ${context.limits.maxAssets}-asset limit`
      );
    }
    context.assetHashes.add(result.hash);
    context.rasterBytes += bytes.byteLength;
    if (context.rasterBytes > context.limits.maxAggregateAssetBytes) {
      invalid(`${path}.rasterAsset.bytes`, "raster assets exceed the aggregate decoded-byte limit");
    }
  }
  return { hash: result.hash, bytes };
}

async function serializeNode(
  node: FigmaNodeSnapshot,
  path: string,
  context: SerializationContext
): Promise<ExportNode> {
  const reason = rasterReason(node, path, new Set());
  if (reason !== null) {
    const asset = await rasterResult(node, path, context);
    context.warnings.push({
      nodeId: node.id,
      nodeName: node.name,
      property: reason,
      fallback: "png"
    });
    return {
      ...baseNode(node, path, context.rootInverse),
      kind: "raster",
      // The raster callback contract bakes the node's appearance, including
      // opacity and effects, so AE must not apply source opacity a second time.
      opacity: 1,
      assetHash: asset.hash
    };
  }

  if (node.type === "TEXT") return serializeText(node, path, context);
  if (node.type === "RECTANGLE" || node.type === "ELLIPSE") return serializeShape(node, path, context);

  const children: ExportNode[] = [];
  for (let index = 0; index < (node.children?.length ?? 0); index += 1) {
    children.push(await serializeNode(node.children![index]!, `${path}.children[${index}]`, context));
  }
  const group: GroupNode = {
    ...baseNode(node, path, context.rootInverse),
    kind: "group",
    children
  };
  return group;
}

export async function serializeFrame(
  node: FigmaNodeSnapshot,
  timing: FrameTiming,
  options: SerializeFrameOptions
): Promise<ExportFrame> {
  if (!GROUP_TYPES.has(node.type)) invalid("$.type", "selected export root must be a frame-like node");
  const duration = positiveNumber(timing.duration, "$.duration");
  const rasterScale = positiveNumber(options.rasterScale, "$.options.rasterScale");
  const normalizedOptions: SerializeFrameOptions = options.exportRaster === undefined
    ? { rasterScale }
    : { rasterScale, exportRaster: options.exportRaster };
  const serializerLimits: SerializerLimits = {
    maxAssets: effectiveLimit(options.limits?.maxAssets, LIMITS.maxAssets, "$.options.limits.maxAssets"),
    maxAssetBytes: effectiveLimit(
      options.limits?.maxAssetBytes,
      LIMITS.maxAssetBytes,
      "$.options.limits.maxAssetBytes"
    ),
    maxAggregateAssetBytes: effectiveLimit(
      options.limits?.maxAggregateAssetBytes,
      LIMITS.maxAggregateAssetBytes,
      "$.options.limits.maxAggregateAssetBytes"
    ),
    maxManifestBytes: effectiveLimit(
      options.limits?.maxManifestBytes,
      LIMITS.maxManifestBytes,
      "$.options.limits.maxManifestBytes"
    )
  };
  const rootMatrix = validateMatrix(node.absoluteTransform, "$.absoluteTransform");
  const rootInverse = invertMatrix(rootMatrix, "$.absoluteTransform");
  const frameId = nonEmptyString(node.id, "$.id");
  const frameName = safeName(node.name, "$.name");
  const width = positiveNumber(node.width, "$.width");
  const height = positiveNumber(node.height, "$.height");
  const rootOpacity = node.opacity === undefined ? 1 : finiteNumber(node.opacity, "$.opacity");
  if (rootOpacity < 0 || rootOpacity > 1) invalid("$.opacity", "expected a number between 0 and 1");
  const rootReason = rootAppearanceReason(node);

  const context: SerializationContext = {
    rootInverse,
    options: normalizedOptions,
    warnings: [],
    rasterBytes: 0,
    assetHashes: new Set(),
    limits: serializerLimits
  };
  if (rootReason !== null) {
    const asset = await rasterResult(node, "$", context);
    return validateSerializedFrame({
      nodeId: frameId,
      name: frameName,
      width,
      height,
      duration,
      children: [{
        id: `${frameId}::root-raster-fallback`,
        name: `${frameName}__ROOT_RASTER_FALLBACK`,
        kind: "raster",
        x: 0,
        y: 0,
        width,
        height,
        rotation: 0,
        opacity: 1,
        assetHash: asset.hash
      }],
      warnings: [{
        nodeId: frameId,
        nodeName: frameName,
        property: rootReason,
        fallback: "png"
      }]
    }, serializerLimits.maxManifestBytes);
  }
  if (!Array.isArray(node.children) || node.children.length === 0) {
    invalid("$.children", "empty frames are not supported by the shared contract");
  }

  const ids = new Set<string>([frameId]);
  for (let index = 0; index < node.children.length; index += 1) {
    preflightNode(node.children[index]!, `$.children[${index}]`, ids, rootInverse);
  }

  const children: ExportNode[] = [];
  const solidRootFill = rootSolidFill(node);
  if (solidRootFill !== undefined) {
    children.push({
      id: reserveSyntheticNodeId(frameId, "root-solid-background", ids),
      name: safeName(`${frameName}__ROOT_SOLID_BACKGROUND`, "$.synthetic.name"),
      kind: "rect",
      x: 0,
      y: 0,
      width,
      height,
      rotation: 0,
      opacity: 1,
      fill: colorHex(solidRootFill, "$.fills[0]"),
      stroke: null,
      strokeWidth: 0,
      radius: 0
    });
  }
  for (let index = 0; index < node.children.length; index += 1) {
    children.push(await serializeNode(node.children[index]!, `$.children[${index}]`, context));
  }
  const frame: ExportFrame = {
    nodeId: frameId,
    name: frameName,
    width,
    height,
    duration,
    children,
    warnings: context.warnings
  };
  return validateSerializedFrame(frame, serializerLimits.maxManifestBytes);
}
