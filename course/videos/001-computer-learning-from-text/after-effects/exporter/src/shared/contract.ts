import { canonicalJson } from "./canonical-json.ts";
import { LIMITS } from "./limits.ts";
import { utf8ByteLength } from "./utf8.ts";

export interface BaseNode {
  id: string;
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  opacity: number;
}

export interface TextRun {
  start: number;
  end: number;
  fontFamily: string;
  fontStyle: string;
  fontSize: number;
  color: string;
}

export interface TextNode extends BaseNode {
  kind: "text";
  text: string;
  textBox: { width: number; height: number };
  paragraph: { align: "LEFT" | "CENTER" | "RIGHT"; lineHeightPx: number; letterSpacingPx: number };
  runs: TextRun[];
}

export interface ShapeNode extends BaseNode {
  kind: "rect" | "ellipse";
  fill: string | null;
  stroke: string | null;
  strokeWidth: number;
  radius: number;
}

export interface GroupNode extends BaseNode {
  kind: "group";
  children: ExportNode[];
}

export interface RasterNode extends BaseNode {
  kind: "raster";
  assetHash: string;
}

export type ExportNode = TextNode | ShapeNode | GroupNode | RasterNode;

export interface ExportFrame {
  nodeId: string;
  name: string;
  width: number;
  height: number;
  duration: number;
  children: ExportNode[];
  warnings: Array<{ nodeId: string; nodeName: string; property: string; fallback: "png" }>;
}

export interface AssetDescriptor {
  hash: string;
  mimeType: "image/png";
  byteLength: number;
  dataBase64: string;
}

export const EXTERNAL_ASSET_DATA: unique symbol = Symbol("external-asset-data");

export interface VerifiedAssetEvidence {
  byteLength: number;
  hash: string;
}

export type ExternalAssetDescriptor = Omit<AssetDescriptor, "dataBase64">;

export interface ExternalExporterPackage extends Omit<ExporterPackage, "assets"> {
  assets: ExternalAssetDescriptor[];
}

export interface PackageByteCounts {
  bodyBytes: number;
  manifestBytes: number;
}

export interface ExporterPackage {
  schemaVersion: "2.0.0";
  exporterVersion: string;
  exportedAt: string;
  contentHash: string;
  source: { fileKey: string; pageId: string };
  target: { width: number; height: number; fps: number; timeUnit: "seconds" };
  frames: ExportFrame[];
  assets: AssetDescriptor[];
}

type UnknownRecord = Record<string, unknown>;

const HASH_PATTERN = /^[0-9a-f]{64}$/;
const COLOR_PATTERN = /^#[0-9A-Fa-f]{6}$/;
const BASE64_PATTERN = /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/;
const BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
const UNSAFE_NAME_PATTERN = /[\u0000-\u001f\u007f/\\]/;

export function isSafeExporterName(name: string): boolean {
  return name.length > 0 && name !== "." && name !== ".." && !UNSAFE_NAME_PATTERN.test(name);
}

function invalid(path: string, message: string): never {
  throw new TypeError(`Invalid exporter package at ${path}: ${message}`);
}

function recordAt(value: unknown, path: string): UnknownRecord {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    invalid(path, "expected an object");
  }
  return value as UnknownRecord;
}

function exactKeys(record: UnknownRecord, keys: readonly string[], path: string): void {
  const allowed = new Set(keys);
  for (const key of Object.keys(record)) {
    if (!allowed.has(key)) invalid(`${path}.${key}`, "unknown field");
  }
  for (const key of keys) {
    if (!Object.prototype.hasOwnProperty.call(record, key)) invalid(`${path}.${key}`, "missing required field");
  }
}

function stringAt(value: unknown, path: string, allowEmpty = false): string {
  if (typeof value !== "string" || (!allowEmpty && value.length === 0)) {
    invalid(path, allowEmpty ? "expected a string" : "expected a non-empty string");
  }
  return value;
}

function arrayAt(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) invalid(path, "expected an array");
  return value;
}

function numberAt(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) invalid(path, "expected a finite number");
  return value;
}

function positiveNumberAt(value: unknown, path: string): number {
  const number = numberAt(value, path);
  if (number <= 0) invalid(path, "expected a positive number");
  return number;
}

function nonNegativeNumberAt(value: unknown, path: string): number {
  const number = numberAt(value, path);
  if (number < 0) invalid(path, "expected a non-negative number");
  return number;
}

function safeIntegerAt(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    invalid(path, "expected a non-negative safe integer");
  }
  return value;
}

function safeNameAt(value: unknown, path: string): string {
  const name = stringAt(value, path);
  if (!isSafeExporterName(name)) invalid(path, "unsafe name");
  return name;
}

function hashAt(value: unknown, path: string, allowEmpty = false): string {
  const hash = stringAt(value, path, allowEmpty);
  if (!(allowEmpty && hash === "") && !HASH_PATTERN.test(hash)) {
    invalid(path, "expected 64 lowercase hexadecimal characters");
  }
  return hash;
}

function colorAt(value: unknown, path: string): string {
  const color = stringAt(value, path);
  if (!COLOR_PATTERN.test(color)) invalid(path, "invalid color; expected #RRGGBB");
  return color;
}

function nullableColorAt(value: unknown, path: string): string | null {
  return value === null ? null : colorAt(value, path);
}

function decodedBase64Length(value: unknown, path: string): { dataBase64: string; byteLength: number } {
  const dataBase64 = stringAt(value, path, true);
  if (dataBase64.length % 4 !== 0 || !BASE64_PATTERN.test(dataBase64)) {
    invalid(path, "expected canonical base64 data");
  }
  if (dataBase64.endsWith("==")) {
    const finalSymbol = BASE64_ALPHABET.indexOf(dataBase64.charAt(dataBase64.length - 3));
    if ((finalSymbol & 0b1111) !== 0) invalid(path, "expected canonical base64 data");
  } else if (dataBase64.endsWith("=")) {
    const finalSymbol = BASE64_ALPHABET.indexOf(dataBase64.charAt(dataBase64.length - 2));
    if ((finalSymbol & 0b11) !== 0) invalid(path, "expected canonical base64 data");
  }
  const padding = dataBase64.endsWith("==") ? 2 : dataBase64.endsWith("=") ? 1 : 0;
  return { dataBase64, byteLength: (dataBase64.length / 4) * 3 - padding };
}

function preflightAssetByteLengths(values: unknown[]): void {
  let aggregateAssetBytes = 0;
  for (let index = 0; index < values.length; index += 1) {
    const path = `$.assets[${index}]`;
    const record = recordAt(values[index], path);
    const byteLength = safeIntegerAt(record.byteLength, `${path}.byteLength`);
    if (byteLength > LIMITS.maxAssetBytes) invalid(`${path}.byteLength`, "asset exceeds the per-asset limit");
    aggregateAssetBytes += byteLength;
    if (aggregateAssetBytes > LIMITS.maxAggregateAssetBytes) {
      invalid("$.assets", "assets exceed the aggregate decoded-byte limit");
    }
  }
}

function registerNodeId(value: unknown, path: string, nodeIds: Set<string>): string {
  const id = stringAt(value, path);
  if (nodeIds.has(id)) invalid(path, `duplicate node ID ${JSON.stringify(id)}`);
  nodeIds.add(id);
  return id;
}

function baseNodeAt(
  record: UnknownRecord,
  path: string,
  nodeIds: Set<string>,
  keys: readonly string[]
): BaseNode {
  exactKeys(record, ["id", "kind", "name", "x", "y", "width", "height", "rotation", "opacity", ...keys], path);
  const opacity = numberAt(record.opacity, `${path}.opacity`);
  if (opacity < 0 || opacity > 1) invalid(`${path}.opacity`, "expected a number between 0 and 1");
  return {
    id: registerNodeId(record.id, `${path}.id`, nodeIds),
    name: safeNameAt(record.name, `${path}.name`),
    x: numberAt(record.x, `${path}.x`),
    y: numberAt(record.y, `${path}.y`),
    width: positiveNumberAt(record.width, `${path}.width`),
    height: positiveNumberAt(record.height, `${path}.height`),
    rotation: numberAt(record.rotation, `${path}.rotation`),
    opacity
  };
}

function textRunAt(value: unknown, path: string, textLength: number): TextRun {
  const record = recordAt(value, path);
  exactKeys(record, ["start", "end", "fontFamily", "fontStyle", "fontSize", "color"], path);
  const start = safeIntegerAt(record.start, `${path}.start`);
  const end = safeIntegerAt(record.end, `${path}.end`);
  if (end <= start || end > textLength) invalid(path, "text run range is outside the source text");
  return {
    start,
    end,
    fontFamily: stringAt(record.fontFamily, `${path}.fontFamily`),
    fontStyle: stringAt(record.fontStyle, `${path}.fontStyle`),
    fontSize: positiveNumberAt(record.fontSize, `${path}.fontSize`),
    color: colorAt(record.color, `${path}.color`)
  };
}

function nodeAt(
  value: unknown,
  path: string,
  nodeIds: Set<string>,
  rasterAssetHashes: Set<string>
): ExportNode {
  const record = recordAt(value, path);
  const kind = stringAt(record.kind, `${path}.kind`);

  if (kind === "text") {
    const base = baseNodeAt(record, path, nodeIds, ["text", "textBox", "paragraph", "runs"]);
    const text = stringAt(record.text, `${path}.text`, true);
    const textBox = recordAt(record.textBox, `${path}.textBox`);
    exactKeys(textBox, ["width", "height"], `${path}.textBox`);
    const paragraph = recordAt(record.paragraph, `${path}.paragraph`);
    exactKeys(paragraph, ["align", "lineHeightPx", "letterSpacingPx"], `${path}.paragraph`);
    const align = stringAt(paragraph.align, `${path}.paragraph.align`);
    if (align !== "LEFT" && align !== "CENTER" && align !== "RIGHT") {
      invalid(`${path}.paragraph.align`, "expected LEFT, CENTER, or RIGHT");
    }
    const runs = arrayAt(record.runs, `${path}.runs`).map((run, index) =>
      textRunAt(run, `${path}.runs[${index}]`, text.length)
    );
    return {
      ...base,
      kind,
      text,
      textBox: {
        width: positiveNumberAt(textBox.width, `${path}.textBox.width`),
        height: positiveNumberAt(textBox.height, `${path}.textBox.height`)
      },
      paragraph: {
        align,
        lineHeightPx: positiveNumberAt(paragraph.lineHeightPx, `${path}.paragraph.lineHeightPx`),
        letterSpacingPx: numberAt(paragraph.letterSpacingPx, `${path}.paragraph.letterSpacingPx`)
      },
      runs
    };
  }

  if (kind === "rect" || kind === "ellipse") {
    const base = baseNodeAt(record, path, nodeIds, ["fill", "stroke", "strokeWidth", "radius"]);
    return {
      ...base,
      kind,
      fill: nullableColorAt(record.fill, `${path}.fill`),
      stroke: nullableColorAt(record.stroke, `${path}.stroke`),
      strokeWidth: nonNegativeNumberAt(record.strokeWidth, `${path}.strokeWidth`),
      radius: nonNegativeNumberAt(record.radius, `${path}.radius`)
    };
  }

  if (kind === "group") {
    const base = baseNodeAt(record, path, nodeIds, ["children"]);
    return {
      ...base,
      kind,
      children: arrayAt(record.children, `${path}.children`).map((child, index) =>
        nodeAt(child, `${path}.children[${index}]`, nodeIds, rasterAssetHashes)
      )
    };
  }

  if (kind === "raster") {
    const base = baseNodeAt(record, path, nodeIds, ["assetHash"]);
    const assetHash = hashAt(record.assetHash, `${path}.assetHash`);
    rasterAssetHashes.add(assetHash);
    return { ...base, kind, assetHash };
  }

  invalid(`${path}.kind`, `unsupported node kind ${JSON.stringify(kind)}`);
}

function warningAt(value: unknown, path: string): ExportFrame["warnings"][number] {
  const record = recordAt(value, path);
  exactKeys(record, ["nodeId", "nodeName", "property", "fallback"], path);
  if (record.fallback !== "png") invalid(`${path}.fallback`, "expected png");
  return {
    nodeId: stringAt(record.nodeId, `${path}.nodeId`),
    nodeName: safeNameAt(record.nodeName, `${path}.nodeName`),
    property: stringAt(record.property, `${path}.property`),
    fallback: "png"
  };
}

function frameAt(
  value: unknown,
  path: string,
  nodeIds: Set<string>,
  rasterAssetHashes: Set<string>
): ExportFrame {
  const record = recordAt(value, path);
  exactKeys(record, ["nodeId", "name", "width", "height", "duration", "children", "warnings"], path);
  const children = arrayAt(record.children, `${path}.children`);
  if (children.length === 0) invalid(`${path}.children`, "empty frames are not supported");
  return {
    nodeId: registerNodeId(record.nodeId, `${path}.nodeId`, nodeIds),
    name: safeNameAt(record.name, `${path}.name`),
    width: positiveNumberAt(record.width, `${path}.width`),
    height: positiveNumberAt(record.height, `${path}.height`),
    duration: positiveNumberAt(record.duration, `${path}.duration`),
    children: children.map((child, index) => nodeAt(child, `${path}.children[${index}]`, nodeIds, rasterAssetHashes)),
    warnings: arrayAt(record.warnings, `${path}.warnings`).map((warning, index) =>
      warningAt(warning, `${path}.warnings[${index}]`)
    )
  };
}

function assetAt(
  value: unknown,
  path: string,
  verifiedEvidence?: VerifiedAssetEvidence
): AssetDescriptor {
  const record = recordAt(value, path);
  exactKeys(record, ["hash", "mimeType", "byteLength", "dataBase64"], path);
  if (record.mimeType !== "image/png") invalid(`${path}.mimeType`, "expected image/png");
  const declaredByteLength = safeIntegerAt(record.byteLength, `${path}.byteLength`);
  let dataBase64: string;
  if (verifiedEvidence === undefined) {
    const decoded = decodedBase64Length(record.dataBase64, `${path}.dataBase64`);
    if (declaredByteLength !== decoded.byteLength) {
      invalid(`${path}.byteLength`, `declared ${declaredByteLength} bytes but base64 decodes to ${decoded.byteLength}`);
    }
    dataBase64 = decoded.dataBase64;
  } else {
    if (record.dataBase64 !== EXTERNAL_ASSET_DATA) {
      invalid(`${path}.dataBase64`, "expected verified external asset data");
    }
    if (declaredByteLength !== verifiedEvidence.byteLength) {
      invalid(
        `${path}.byteLength`,
        `declared ${declaredByteLength} bytes but verified data contains ${verifiedEvidence.byteLength}`
      );
    }
    hashAt(verifiedEvidence.hash, `${path}.verifiedHash`);
    dataBase64 = "";
  }
  if (declaredByteLength > LIMITS.maxAssetBytes) invalid(`${path}.byteLength`, "asset exceeds the per-asset limit");
  return {
    hash: hashAt(record.hash, `${path}.hash`),
    mimeType: "image/png",
    byteLength: declaredByteLength,
    dataBase64
  };
}

function isoTimestampAt(value: unknown, path: string): string {
  const timestamp = stringAt(value, path);
  const parsed = new Date(timestamp);
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString() !== timestamp) {
    invalid(path, "expected an ISO 8601 UTC timestamp");
  }
  return timestamp;
}

export function assertJsonContainerDepth(value: unknown): void {
  type Entry = { depth: number; exit: boolean; value: unknown };
  const ancestors = new Set<object>();
  const stack: Entry[] = [{ depth: 1, exit: false, value }];
  while (stack.length > 0) {
    const entry = stack.pop();
    if (entry === undefined || entry.value === null || typeof entry.value !== "object") continue;
    const container = entry.value;
    if (entry.exit) {
      ancestors.delete(container);
      continue;
    }
    if (entry.depth > LIMITS.maxJsonContainerDepth) {
      invalid("$", `JSON container nesting exceeds the ${LIMITS.maxJsonContainerDepth}-level limit`);
    }
    if (ancestors.has(container)) invalid("$", "JSON containers must not contain a cycle");
    ancestors.add(container);
    stack.push({ depth: entry.depth, exit: true, value: container });
    const children = Array.isArray(container)
      ? container
      : Object.keys(container).map((key) => (container as UnknownRecord)[key]);
    for (let index = children.length - 1; index >= 0; index -= 1) {
      const child = children[index];
      if (child !== null && typeof child === "object") {
        stack.push({ depth: entry.depth + 1, exit: false, value: child });
      }
    }
  }
}

function validatePackageInternal(
  value: unknown,
  allowEmptyContentHash: boolean,
  verifiedAssets?: { byteCounts: PackageByteCounts; evidence: readonly VerifiedAssetEvidence[] }
): ExporterPackage {
  assertJsonContainerDepth(value);
  const record = recordAt(value, "$");
  exactKeys(record, ["schemaVersion", "exporterVersion", "exportedAt", "contentHash", "source", "target", "frames", "assets"], "$");

  const schemaVersion = stringAt(record.schemaVersion, "$.schemaVersion");
  const schemaMatch = /^(\d+)\.(\d+)\.(\d+)$/.exec(schemaVersion);
  if (schemaMatch?.[1] !== "2") {
    invalid(
      "$.schemaVersion",
      `unsupported schema major in ${JSON.stringify(schemaVersion)}; exporter requires "2.0.0"`
    );
  }
  if (schemaVersion !== "2.0.0") {
    invalid(
      "$.schemaVersion",
      `unsupported schema version ${JSON.stringify(schemaVersion)}; exporter requires "2.0.0"`
    );
  }

  const source = recordAt(record.source, "$.source");
  exactKeys(source, ["fileKey", "pageId"], "$.source");
  const target = recordAt(record.target, "$.target");
  exactKeys(target, ["width", "height", "fps", "timeUnit"], "$.target");
  if (target.timeUnit !== "seconds") invalid("$.target.timeUnit", "expected \"seconds\"");

  const frameValues = arrayAt(record.frames, "$.frames");
  if (frameValues.length === 0) invalid("$.frames", "expected at least one frame");
  if (frameValues.length > LIMITS.maxFrames) invalid("$.frames", `exceeds the ${LIMITS.maxFrames}-frame limit`);

  const assetValues = arrayAt(record.assets, "$.assets");
  if (assetValues.length > LIMITS.maxAssets) invalid("$.assets", `exceeds the ${LIMITS.maxAssets}-asset limit`);
  if (verifiedAssets !== undefined && verifiedAssets.evidence.length !== assetValues.length) {
    invalid("$.assets", "verified asset evidence count does not match the asset array");
  }
  preflightAssetByteLengths(assetValues);

  const nodeIds = new Set<string>();
  const rasterAssetHashes = new Set<string>();
  const frames = frameValues.map((frame, index) => frameAt(frame, `$.frames[${index}]`, nodeIds, rasterAssetHashes));
  const assets = assetValues.map((asset, index) =>
    assetAt(asset, `$.assets[${index}]`, verifiedAssets?.evidence[index])
  );

  const assetHashes = new Set<string>();
  let aggregateAssetBytes = 0;
  for (let index = 0; index < assets.length; index += 1) {
    const asset = assets[index];
    if (asset === undefined) continue;
    if (assetHashes.has(asset.hash)) invalid(`$.assets[${index}].hash`, `duplicate asset hash ${JSON.stringify(asset.hash)}`);
    assetHashes.add(asset.hash);
    aggregateAssetBytes += asset.byteLength;
    if (aggregateAssetBytes > LIMITS.maxAggregateAssetBytes) {
      invalid("$.assets", "assets exceed the aggregate decoded-byte limit");
    }
  }
  for (const assetHash of rasterAssetHashes) {
    if (!assetHashes.has(assetHash)) invalid("$.frames", `raster node references missing asset ${JSON.stringify(assetHash)}`);
  }

  const result: ExporterPackage = {
    schemaVersion: "2.0.0",
    exporterVersion: stringAt(record.exporterVersion, "$.exporterVersion"),
    exportedAt: isoTimestampAt(record.exportedAt, "$.exportedAt"),
    contentHash: hashAt(record.contentHash, "$.contentHash", allowEmptyContentHash),
    source: {
      fileKey: stringAt(source.fileKey, "$.source.fileKey"),
      pageId: stringAt(source.pageId, "$.source.pageId")
    },
    target: {
      width: positiveNumberAt(target.width, "$.target.width"),
      height: positiveNumberAt(target.height, "$.target.height"),
      fps: positiveNumberAt(target.fps, "$.target.fps"),
      timeUnit: "seconds"
    },
    frames,
    assets
  };

  for (let index = 0; index < result.frames.length; index += 1) {
    const frame = result.frames[index]!;
    const frameCount = frame.duration * result.target.fps;
    const nearestFrame = Math.round(frameCount);
    if (!Number.isSafeInteger(nearestFrame) || Math.abs(frameCount - nearestFrame) > 1e-9) {
      invalid(
        `$.frames[${index}].duration`,
        "frame duration in seconds must align to a whole frame at the target fps"
      );
    }
  }

  if (verifiedAssets === undefined) {
    const manifestWithoutAssetData: ExporterPackage = {
      ...result,
      assets: result.assets.map((asset) => ({ ...asset, dataBase64: "" }))
    };
    if (utf8ByteLength(JSON.stringify(manifestWithoutAssetData)) > LIMITS.maxManifestBytes) {
      invalid("$", "manifest exceeds the manifest-byte limit");
    }
    if (utf8ByteLength(JSON.stringify(result)) > LIMITS.maxBodyBytes) {
      invalid("$", "package exceeds the complete-body limit");
    }
  } else {
    const { bodyBytes, manifestBytes } = verifiedAssets.byteCounts;
    if (!Number.isSafeInteger(manifestBytes) || manifestBytes < 0) invalid("$", "manifest byte count is invalid");
    if (!Number.isSafeInteger(bodyBytes) || bodyBytes < manifestBytes) invalid("$", "body byte count is invalid");
    if (manifestBytes > LIMITS.maxManifestBytes) invalid("$", "manifest exceeds the manifest-byte limit");
    if (bodyBytes > LIMITS.maxBodyBytes) invalid("$", "package exceeds the complete-body limit");
  }

  return result;
}

export function validatePackage(value: unknown): ExporterPackage {
  return validatePackageInternal(value, false);
}

export function validatePackageWithVerifiedAssets(
  value: unknown,
  evidence: readonly VerifiedAssetEvidence[],
  byteCounts: PackageByteCounts
): ExternalExporterPackage {
  const result = validatePackageInternal(value, false, { byteCounts, evidence });
  return {
    ...result,
    assets: result.assets.map(({ dataBase64: _dataBase64, ...asset }) => asset)
  };
}

export function contentFingerprintInput(value: ExporterPackage): string {
  const result = validatePackageInternal(value, true);
  result.exportedAt = "";
  result.contentHash = "";
  return canonicalJson(result);
}

export { canonicalJson } from "./canonical-json.ts";
