import {
  contentFingerprintInput,
  validatePackage,
  type AssetDescriptor,
  type ExporterPackage
} from "../shared/contract.ts";
import {
  serializeFrame,
  type FigmaNodeSnapshot,
  type FigmaPaintSnapshot,
  type StyledTextSegmentSnapshot,
  type TransformMatrix
} from "./serializer.ts";
import { sha256Hex } from "../shared/sha256.ts";
import { decodeUtf8 } from "../shared/utf8.ts";

export const BRIDGE_BASE_URL = "http://127.0.0.1:3456";
export const BRIDGE_TOKEN_KEY = "video001-ae-bridge-token";
export const EXPORT_MEDIA_TYPE = "application/vnd.video001.figma-ae+json";

const EXPORTER_VERSION = "0.1.0";
const FRAME_LIKE_TYPES = new Set(["FRAME", "COMPONENT", "INSTANCE"]);
const MAX_FRAMES = 48;
const PAIRING_CODE_PATTERN = /^\d{6}$/;
const BASE64URL_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
const DEFAULT_BRIDGE_TIMEOUT_MS = 10_000;
const MAX_BRIDGE_RESPONSE_BYTES = 16 * 1024;

export interface FrameSummary {
  nodeId: string;
  name: string;
  duration: number;
}

export type ControllerToUi =
  | { type: "selection"; generation: number; frames: FrameSummary[] }
  | { type: "package-unhashed"; generation: number; value: ExporterPackage }
  | { type: "bridge-result"; operation: number; status: number; code: string; message: string }
  | { type: "failure"; operation?: number; code: string; message: string };

export type UiToController =
  | { type: "refresh-selection" }
  | { type: "build-package" }
  | { type: "package-ready"; generation: number; value: ExporterPackage }
  | { type: "pair"; operation: number; code: string }
  | { type: "send-live"; operation: number }
  | { type: "close" };

export interface EmbeddedVideo001Config {
  source: { fileKey: string; pageId: string };
  target: { width: number; height: number; fps: number };
  shots: Array<{ index: number; nodeId: string; name: string; duration: number }>;
}

export interface FigmaNodeLike {
  id: string;
  name: string;
  type: string;
  parent?: unknown;
  width: number;
  height: number;
  opacity?: number;
  visible?: boolean;
  absoluteTransform: TransformMatrix;
  fills?: unknown;
  strokes?: unknown;
  strokeWeight?: unknown;
  cornerRadius?: unknown;
  effects?: unknown;
  blendMode?: unknown;
  isMask?: unknown;
  children?: readonly FigmaNodeLike[] | undefined;
  characters?: unknown;
  textAlignHorizontal?: unknown;
  lineHeight?: unknown;
  letterSpacing?: unknown;
  fontSize?: unknown;
  getStyledTextSegments?: (fields: readonly string[]) => readonly unknown[];
  exportAsync?: (settings: {
    format: "PNG";
    constraint: { type: "SCALE"; value: 1 };
  }) => Promise<Uint8Array>;
}

export interface ControllerPage {
  id: string;
  selection: FigmaNodeLike[] | readonly FigmaNodeLike[];
}

export interface ControllerFetchOptions {
  method?: string;
  headers?: { [name: string]: string };
  headersObject?: { [name: string]: string };
  body?: Uint8Array | string;
  credentials?: string;
  cache?: string;
  redirect?: string;
  referrer?: string;
  integrity?: string;
}

export interface ControllerFetchResponse {
  headersObject: { [name: string]: string };
  ok: boolean;
  redirected: boolean;
  status: number;
  statusText: string;
  type: string;
  url: string;
  arrayBuffer(): Promise<ArrayBuffer>;
  text(): Promise<string>;
  json(): Promise<unknown>;
}

type FigmaSandboxFetch = (url: string, options?: FetchOptions) => Promise<FetchResponse>;

export interface ControllerHost {
  fileKey: string | undefined;
  getCurrentPage(): ControllerPage;
  mixed: unknown;
  postMessage(message: ControllerToUi): void;
  closePlugin(): void;
  now(): Date;
  clientStorage: {
    getAsync(key: string): Promise<unknown>;
    setAsync(key: string, value: unknown): Promise<void>;
    deleteAsync(key: string): Promise<void>;
  };
  fetch(input: string, init?: ControllerFetchOptions): Promise<ControllerFetchResponse>;
  bridgeTimeoutMs?: number;
}

export interface Controller {
  handleMessage(value: unknown): Promise<void>;
  refreshSelection(): Promise<void>;
}

type UnknownRecord = Record<string, unknown>;

function invalidMessage(path: string, message: string): never {
  throw new TypeError(`Invalid plugin message at ${path}: ${message}`);
}

function plainRecord(value: unknown, path: string): UnknownRecord {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    invalidMessage(path, "expected a plain object");
  }
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) {
    invalidMessage(path, "expected a plain object");
  }
  return value as UnknownRecord;
}

function exactKeys(record: UnknownRecord, keys: readonly string[], path: string): void {
  const allowed = new Set(keys);
  for (const key of Object.keys(record)) {
    if (!allowed.has(key)) invalidMessage(`${path}.${key}`, "unknown field");
  }
  for (const key of keys) {
    if (!Object.prototype.hasOwnProperty.call(record, key)) {
      invalidMessage(`${path}.${key}`, "missing required field");
    }
  }
}

function operationGeneration(value: unknown, path: string): number {
  if (!Number.isSafeInteger(value) || (value as number) < 1) {
    invalidMessage(path, "expected a positive safe integer");
  }
  return value as number;
}

export function validateUiToController(value: unknown): UiToController {
  const record = plainRecord(value, "$");
  if (typeof record.type !== "string") invalidMessage("$.type", "expected a message type");
  switch (record.type) {
    case "refresh-selection":
    case "build-package":
    case "close":
      exactKeys(record, ["type"], "$");
      return { type: record.type };
    case "send-live":
      exactKeys(record, ["type", "operation"], "$");
      return { type: "send-live", operation: operationGeneration(record.operation, "$.operation") };
    case "pair":
      exactKeys(record, ["type", "operation", "code"], "$");
      if (typeof record.code !== "string" || !PAIRING_CODE_PATTERN.test(record.code)) {
        invalidMessage("$.code", "expected a six-digit pairing code");
      }
      return {
        type: "pair",
        operation: operationGeneration(record.operation, "$.operation"),
        code: record.code
      };
    case "package-ready":
      exactKeys(record, ["type", "generation", "value"], "$");
      if (!Number.isSafeInteger(record.generation) || (record.generation as number) < 1) {
        invalidMessage("$.generation", "expected a positive safe integer");
      }
      return {
        type: "package-ready",
        generation: record.generation as number,
        value: validatePackage(record.value)
      };
    default:
      invalidMessage("$.type", `unsupported message type ${JSON.stringify(record.type)}`);
  }
}

function optionalBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function optionalNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function normalizePaint(value: unknown): FigmaPaintSnapshot | undefined {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return undefined;
  const paint = value as UnknownRecord;
  if (typeof paint.type !== "string") return undefined;
  const result: FigmaPaintSnapshot = { type: paint.type };
  if (typeof paint.visible === "boolean") result.visible = paint.visible;
  if (typeof paint.opacity === "number" && Number.isFinite(paint.opacity)) result.opacity = paint.opacity;
  if (typeof paint.imageHash === "string") result.imageHash = paint.imageHash;
  if (paint.color !== null && typeof paint.color === "object" && !Array.isArray(paint.color)) {
    const color = paint.color as UnknownRecord;
    if ([color.r, color.g, color.b].every((channel) => typeof channel === "number" && Number.isFinite(channel))) {
      result.color = { r: color.r as number, g: color.g as number, b: color.b as number };
    }
  }
  return result;
}

function normalizePaints(value: unknown): readonly FigmaPaintSnapshot[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const paints: FigmaPaintSnapshot[] = [];
  for (const item of value) {
    const paint = normalizePaint(item);
    if (paint === undefined) return undefined;
    paints.push(paint);
  }
  return paints;
}

function normalizeEffects(value: unknown): readonly { type: string; visible?: boolean }[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const effects: Array<{ type: string; visible?: boolean }> = [];
  for (const item of value) {
    if (item === null || typeof item !== "object" || Array.isArray(item)) return undefined;
    const effect = item as UnknownRecord;
    if (typeof effect.type !== "string") return undefined;
    effects.push({ type: effect.type, ...(typeof effect.visible === "boolean" ? { visible: effect.visible } : {}) });
  }
  return effects;
}

function absolutePixels(value: unknown, fontSize: unknown, mixed: unknown): number | undefined {
  if (value === mixed || value === null || typeof value !== "object" || Array.isArray(value)) return undefined;
  const metric = value as UnknownRecord;
  if (metric.unit === "PIXELS") return optionalNumber(metric.value);
  if (metric.unit === "PERCENT") {
    const percentage = optionalNumber(metric.value);
    const size = optionalNumber(fontSize);
    if (percentage !== undefined && size !== undefined) return size * percentage / 100;
  }
  return undefined;
}

function normalizeStyledSegments(node: FigmaNodeLike): readonly StyledTextSegmentSnapshot[] | undefined {
  if (node.type !== "TEXT" || node.getStyledTextSegments === undefined) return undefined;
  const rawSegments = node.getStyledTextSegments(["fontName", "fontSize", "fills"]);
  const segments: StyledTextSegmentSnapshot[] = [];
  for (const item of rawSegments) {
    if (item === null || typeof item !== "object" || Array.isArray(item)) return undefined;
    const segment = item as UnknownRecord;
    const fontName = segment.fontName;
    if (fontName === null || typeof fontName !== "object" || Array.isArray(fontName)) return undefined;
    const font = fontName as UnknownRecord;
    if (
      typeof segment.start !== "number" ||
      typeof segment.end !== "number" ||
      typeof segment.fontSize !== "number" ||
      typeof font.family !== "string" ||
      typeof font.style !== "string"
    ) return undefined;
    const fills = normalizePaints(segment.fills);
    if (fills === undefined) return undefined;
    segments.push({
      start: segment.start,
      end: segment.end,
      fontName: { family: font.family, style: font.style },
      fontSize: segment.fontSize,
      fills
    });
  }
  return segments;
}

export function normalizeFigmaNode(
  node: FigmaNodeLike,
  mixed: unknown,
  byId: Map<string, FigmaNodeLike> = new Map()
): FigmaNodeSnapshot {
  byId.set(node.id, node);
  const fills = normalizePaints(node.fills);
  const strokes = normalizePaints(node.strokes);
  const effects = normalizeEffects(node.effects);
  const opacity = optionalNumber(node.opacity);
  const visible = optionalBoolean(node.visible);
  const strokeWeight = optionalNumber(node.strokeWeight);
  const snapshot: FigmaNodeSnapshot = {
    id: node.id,
    name: node.name,
    type: node.type,
    width: node.width,
    height: node.height,
    absoluteTransform: node.absoluteTransform
  };
  if (opacity !== undefined) snapshot.opacity = opacity;
  if (visible !== undefined) snapshot.visible = visible;
  if (fills !== undefined) snapshot.fills = fills;
  if (strokes !== undefined) snapshot.strokes = strokes;
  if (strokeWeight !== undefined) snapshot.strokeWeight = strokeWeight;
  if (typeof node.cornerRadius === "number" && Number.isFinite(node.cornerRadius)) {
    snapshot.cornerRadius = node.cornerRadius;
  } else if (node.cornerRadius === mixed) {
    snapshot.cornerRadius = "MIXED";
  }
  if (effects !== undefined) snapshot.effects = effects;
  if (typeof node.blendMode === "string") snapshot.blendMode = node.blendMode;
  if (typeof node.isMask === "boolean") snapshot.isMask = node.isMask;

  if (node.type === "TEXT") {
    if (typeof node.characters === "string") snapshot.characters = node.characters;
    if (typeof node.textAlignHorizontal === "string") snapshot.textAlignHorizontal = node.textAlignHorizontal;
    const lineHeightPx = absolutePixels(node.lineHeight, node.fontSize, mixed);
    const letterSpacingPx = absolutePixels(node.letterSpacing, node.fontSize, mixed);
    if (lineHeightPx !== undefined) snapshot.lineHeightPx = lineHeightPx;
    if (letterSpacingPx !== undefined) snapshot.letterSpacingPx = letterSpacingPx;
    const segments = normalizeStyledSegments(node);
    if (segments !== undefined) snapshot.styledTextSegments = segments;
  }
  if (Array.isArray(node.children)) {
    snapshot.children = node.children.map((child) => normalizeFigmaNode(child, mixed, byId));
  }
  return snapshot;
}

function bytesToBase64(bytes: Uint8Array): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  let result = "";
  for (let index = 0; index < bytes.length; index += 3) {
    const first = bytes[index] ?? 0;
    const second = bytes[index + 1] ?? 0;
    const third = bytes[index + 2] ?? 0;
    const packed = (first << 16) | (second << 8) | third;
    result += alphabet[(packed >> 18) & 63];
    result += alphabet[(packed >> 12) & 63];
    result += index + 1 < bytes.length ? alphabet[(packed >> 6) & 63] : "=";
    result += index + 2 < bytes.length ? alphabet[packed & 63] : "=";
  }
  return result;
}

function controllerFailure(code: string, message: string): Error & { code: string } {
  return Object.assign(new Error(message), { code });
}

function failureFrom(error: unknown): { code: string; message: string } {
  if (error !== null && typeof error === "object" && "code" in error && typeof error.code === "string") {
    return { code: error.code, message: error instanceof Error ? error.message : "The plugin operation failed." };
  }
  return {
    code: "EXPORT_FAILED",
    message: error instanceof Error ? error.message : "The plugin operation failed."
  };
}

function validateConfig(config: EmbeddedVideo001Config): Map<string, EmbeddedVideo001Config["shots"][number]> {
  const timings = new Map<string, EmbeddedVideo001Config["shots"][number]>();
  for (const shot of config.shots) {
    if (timings.has(shot.nodeId)) throw new TypeError(`Duplicate embedded timing ID ${shot.nodeId}`);
    timings.set(shot.nodeId, shot);
  }
  return timings;
}

function selectedFrames(
  host: ControllerHost,
  config: EmbeddedVideo001Config,
  timings: Map<string, EmbeddedVideo001Config["shots"][number]>
): Array<{ node: FigmaNodeLike; timing: EmbeddedVideo001Config["shots"][number] }> {
  const page = host.getCurrentPage();
  const selection = Array.from(page.selection);
  if (selection.length === 0) throw controllerFailure("NO_FRAME_SELECTED", "Select at least one Video 001 frame.");
  if (selection.length > MAX_FRAMES) {
    throw controllerFailure("TOO_MANY_FRAMES", `Select no more than ${MAX_FRAMES} frames.`);
  }
  if (host.fileKey !== config.source.fileKey || page.id !== config.source.pageId) {
    throw controllerFailure("WRONG_LESSON_SOURCE", "Open the configured Video 001 Figma page before exporting.");
  }
  return selection.map((node) => {
    if (!FRAME_LIKE_TYPES.has(node.type)) {
      throw controllerFailure("SELECTION_NOT_FRAME", `Selected node ${node.id} is not a frame-like node.`);
    }
    if (node.parent !== page) {
      throw controllerFailure("SELECTION_NOT_TOP_LEVEL", `Selected frame ${node.id} must be top-level on the current page.`);
    }
    const timing = timings.get(node.id);
    if (timing === undefined) {
      throw controllerFailure("SHOT_TIMING_NOT_FOUND", `No Video 001 timing exists for selected frame ${node.id}.`);
    }
    if (node.name !== timing.name) {
      throw controllerFailure(
        "SHOT_NAME_MISMATCH",
        `Selected frame ${node.id} must be named ${timing.name} before export.`
      );
    }
    return { node, timing };
  });
}

function safeBridgeError(value: unknown, status: number): { code: string; message: string } {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    const outer = value as UnknownRecord;
    if (Object.keys(outer).length === 1 && outer.error !== null && typeof outer.error === "object" && !Array.isArray(outer.error)) {
      const error = outer.error as UnknownRecord;
      if (
        Object.keys(error).length === 2 &&
        typeof error.code === "string" &&
        typeof error.message === "string" &&
        error.code.length > 0 &&
        error.message.length > 0
      ) return { code: error.code, message: error.message };
    }
  }
  return { code: `BRIDGE_HTTP_${status}`, message: `The local bridge returned HTTP ${status}.` };
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(controllerFailure("BRIDGE_TIMEOUT", "The local bridge did not respond in time."));
    }, timeoutMs);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error: unknown) => {
        clearTimeout(timer);
        reject(error);
      }
    );
  });
}

function responseHeader(response: ControllerFetchResponse, name: string): string | undefined {
  const expected = name.toLowerCase();
  for (const key of Object.keys(response.headersObject)) {
    if (key.toLowerCase() === expected) return response.headersObject[key];
  }
  return undefined;
}

async function responseJson(response: ControllerFetchResponse, timeoutMs: number): Promise<unknown> {
  const declaredLength = responseHeader(response, "content-length");
  if (declaredLength !== undefined) {
    const parsedLength = Number(declaredLength);
    if (!Number.isSafeInteger(parsedLength) || parsedLength < 0 || parsedLength > MAX_BRIDGE_RESPONSE_BYTES) {
      throw controllerFailure("INVALID_BRIDGE_RESPONSE", "The bridge response exceeded the allowed size.");
    }
  }

  const buffer = await withTimeout(response.arrayBuffer(), timeoutMs);
  let bytes: Uint8Array;
  try {
    bytes = new Uint8Array(buffer);
  } catch {
    throw controllerFailure("INVALID_BRIDGE_RESPONSE", "The bridge returned an invalid response body.");
  }
  if (bytes.byteLength > MAX_BRIDGE_RESPONSE_BYTES) {
    throw controllerFailure("INVALID_BRIDGE_RESPONSE", "The bridge response exceeded the allowed size.");
  }
  try {
    return JSON.parse(decodeUtf8(bytes));
  } catch (error) {
    if (error !== null && typeof error === "object" && "code" in error) throw error;
    return undefined;
  }
}

function isCanonicalBridgeToken(value: unknown): value is string {
  if (typeof value !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(value)) return false;
  const finalSymbol = BASE64URL_ALPHABET.indexOf(value.charAt(42));
  return finalSymbol >= 0 && (finalSymbol & 0b11) === 0;
}

export function createController(host: ControllerHost, config: EmbeddedVideo001Config): Controller {
  const timings = validateConfig(config);
  let packageGeneration = 0;
  let pendingPackage: { generation: number; value: ExporterPackage } | undefined;
  let readyPackage: { generation: number; value: ExporterPackage } | undefined;
  let activeBridgeOperation: number | undefined;
  let lastBridgeOperation = 0;
  const bridgeTimeoutMs = host.bridgeTimeoutMs ?? DEFAULT_BRIDGE_TIMEOUT_MS;
  if (!Number.isSafeInteger(bridgeTimeoutMs) || bridgeTimeoutMs < 1) {
    throw new TypeError("bridgeTimeoutMs must be a positive safe integer");
  }

  const beginPackageGeneration = (): number => {
    packageGeneration += 1;
    pendingPackage = undefined;
    readyPackage = undefined;
    return packageGeneration;
  };

  const postFailure = (error: unknown, operation?: number): void => {
    const failure = failureFrom(error);
    host.postMessage(operation === undefined
      ? { type: "failure", code: failure.code, message: failure.message }
      : { type: "failure", operation, code: failure.code, message: failure.message });
  };

  const refreshSelection = async (): Promise<void> => {
    const generation = beginPackageGeneration();
    try {
      const frames = selectedFrames(host, config, timings).map(({ timing }) => ({
        nodeId: timing.nodeId,
        name: timing.name,
        duration: timing.duration
      }));
      host.postMessage({ type: "selection", generation, frames });
    } catch (error) {
      postFailure(error);
    }
  };

  const buildPackage = async (): Promise<void> => {
    const generation = beginPackageGeneration();
    const selected = selectedFrames(host, config, timings);
    host.postMessage({
      type: "selection",
      generation,
      frames: selected.map(({ timing }) => ({
        nodeId: timing.nodeId,
        name: timing.name,
        duration: timing.duration
      }))
    });
    const assets = new Map<string, Uint8Array>();
    const frames = [];
    for (const { node, timing } of selected) {
      const nodesById = new Map<string, FigmaNodeLike>();
      const snapshot = normalizeFigmaNode(node, host.mixed, nodesById);
      const frame = await serializeFrame(snapshot, { duration: timing.duration }, {
        rasterScale: 1,
        exportRaster: async (rasterSnapshot, request) => {
          if (request.format !== "PNG" || request.scale !== 1 || request.appearance !== "BAKED") {
            throw new Error(`Unsupported raster request for node ${rasterSnapshot.id}`);
          }
          const source = nodesById.get(rasterSnapshot.id);
          if (source?.exportAsync === undefined) {
            throw new Error(`Figma node ${rasterSnapshot.id} does not support PNG export`);
          }
          const bytes = await source.exportAsync({
            format: "PNG",
            constraint: { type: "SCALE", value: 1 }
          });
          if (!(bytes instanceof Uint8Array)) throw new TypeError(`Figma node ${source.id} returned invalid PNG bytes`);
          const hash = sha256Hex(bytes);
          const retained = assets.get(hash);
          if (retained === undefined) {
            assets.set(hash, bytes);
          } else if (
            retained.byteLength !== bytes.byteLength ||
            retained.some((byte, index) => byte !== bytes[index])
          ) {
            throw new Error("A raster SHA-256 collision was detected");
          }
          return { hash, bytes };
        }
      });
      if (generation !== packageGeneration) return;
      frames.push(frame);
    }

    const descriptors: AssetDescriptor[] = Array.from(assets, ([hash, bytes]) => ({
      hash,
      mimeType: "image/png",
      byteLength: bytes.byteLength,
      dataBase64: bytesToBase64(bytes)
    }));
    const page = host.getCurrentPage();
    const value: ExporterPackage = {
      schemaVersion: "1.0.0",
      exporterVersion: EXPORTER_VERSION,
      exportedAt: host.now().toISOString(),
      contentHash: "",
      source: { fileKey: host.fileKey!, pageId: page.id },
      target: { ...config.target },
      frames,
      assets: descriptors
    };
    contentFingerprintInput(value);
    if (generation !== packageGeneration) return;
    pendingPackage = { generation, value };
    host.postMessage({ type: "package-unhashed", generation, value });
  };

  const acceptPackage = (generation: number, value: ExporterPackage): void => {
    if (generation !== packageGeneration) return;
    if (pendingPackage === undefined) {
      throw controllerFailure("PACKAGE_NOT_PENDING", "Build a package before returning its content hash.");
    }
    if (pendingPackage.generation !== generation) return;
    const validated = validatePackage(value);
    if (contentFingerprintInput(validated) !== contentFingerprintInput(pendingPackage.value)) {
      throw controllerFailure("PACKAGE_CONTENT_CHANGED", "The UI returned a package whose content changed during hashing.");
    }
    readyPackage = { generation, value: validated };
  };

  const deleteStoredTokenIfUnchanged = async (tokenSnapshot: unknown): Promise<void> => {
    if (tokenSnapshot === undefined) return;
    const retainedToken = await host.clientStorage.getAsync(BRIDGE_TOKEN_KEY);
    if (retainedToken === tokenSnapshot) await host.clientStorage.deleteAsync(BRIDGE_TOKEN_KEY);
  };

  const pair = async (operation: number, code: string): Promise<void> => {
    const tokenAtRequestStart = await host.clientStorage.getAsync(BRIDGE_TOKEN_KEY);
    let response: ControllerFetchResponse;
    try {
      response = await withTimeout(host.fetch(BRIDGE_BASE_URL + "/v1/pair", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code })
      }), bridgeTimeoutMs);
    } catch (error) {
      if (failureFrom(error).code === "BRIDGE_TIMEOUT") throw error;
      host.postMessage({
        type: "bridge-result",
        operation,
        status: 0,
        code: "BRIDGE_UNAVAILABLE",
        message: "The local After Effects bridge is unavailable. Download the package instead."
      });
      return;
    }
    if (response.status === 401) await deleteStoredTokenIfUnchanged(tokenAtRequestStart);
    const body = await responseJson(response, bridgeTimeoutMs);
    if (response.status === 200) {
      let token: unknown;
      try {
        const record = plainRecord(body, "$.bridge");
        exactKeys(record, ["token"], "$.bridge");
        token = record.token;
      } catch {
        throw controllerFailure("INVALID_BRIDGE_RESPONSE", "The bridge returned an invalid pairing token.");
      }
      if (!isCanonicalBridgeToken(token)) {
        throw controllerFailure("INVALID_BRIDGE_RESPONSE", "The bridge returned an invalid pairing token.");
      }
      await host.clientStorage.setAsync(BRIDGE_TOKEN_KEY, token);
      host.postMessage({
        type: "bridge-result",
        operation,
        status: response.status,
        code: "PAIRED",
        message: "Paired with After Effects."
      });
      return;
    }
    if (response.ok) {
      throw controllerFailure("INVALID_BRIDGE_RESPONSE", "The bridge returned an unexpected pairing status.");
    }
    const error = safeBridgeError(body, response.status);
    host.postMessage({ type: "bridge-result", operation, status: response.status, ...error });
  };

  const sendLive = async (operation: number): Promise<void> => {
    if (readyPackage === undefined) {
      throw controllerFailure("PACKAGE_NOT_READY", "Build and hash a package before sending it.");
    }
    const packageToSend = readyPackage.value;
    const token = await host.clientStorage.getAsync(BRIDGE_TOKEN_KEY);
    if (!isCanonicalBridgeToken(token)) {
      if (token !== undefined) await host.clientStorage.deleteAsync(BRIDGE_TOKEN_KEY);
      throw controllerFailure("NOT_PAIRED", "Pair with the local After Effects bridge before sending.");
    }
    let response: ControllerFetchResponse;
    try {
      response = await withTimeout(host.fetch(BRIDGE_BASE_URL + "/v1/export", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": EXPORT_MEDIA_TYPE
        },
        body: JSON.stringify(packageToSend)
      }), bridgeTimeoutMs);
    } catch (error) {
      if (failureFrom(error).code === "BRIDGE_TIMEOUT") throw error;
      host.postMessage({
        type: "bridge-result",
        operation,
        status: 0,
        code: "BRIDGE_UNAVAILABLE",
        message: "The local After Effects bridge is unavailable. Download the package instead."
      });
      return;
    }
    if (response.status === 401) await deleteStoredTokenIfUnchanged(token);
    const body = await responseJson(response, bridgeTimeoutMs);
    if (response.status === 202) {
      const record = plainRecord(body, "$.bridge");
      exactKeys(record, ["status", "contentHash"], "$.bridge");
      if (record.status !== "accepted" || record.contentHash !== packageToSend.contentHash) {
        throw controllerFailure(
          "INVALID_BRIDGE_RESPONSE",
          "The bridge returned an invalid export acknowledgement."
        );
      }
      host.postMessage({
        type: "bridge-result",
        operation,
        status: response.status,
        code: "EXPORT_ACCEPTED",
        message: "The package was sent to After Effects."
      });
      return;
    }
    if (response.ok) {
      throw controllerFailure("INVALID_BRIDGE_RESPONSE", "The bridge returned an unexpected export status.");
    }
    const error = safeBridgeError(body, response.status);
    host.postMessage({ type: "bridge-result", operation, status: response.status, ...error });
  };

  const runBridgeOperation = async (operation: number, action: () => Promise<void>): Promise<void> => {
    if (activeBridgeOperation !== undefined) {
      postFailure(
        controllerFailure("BRIDGE_BUSY", "Wait for the active bridge operation to finish."),
        operation
      );
      return;
    }
    if (operation <= lastBridgeOperation) return;
    lastBridgeOperation = operation;
    activeBridgeOperation = operation;
    try {
      await action();
    } catch (error) {
      postFailure(error, operation);
    } finally {
      if (activeBridgeOperation === operation) activeBridgeOperation = undefined;
    }
  };

  const handleMessage = async (value: unknown): Promise<void> => {
    let message: UiToController;
    try {
      message = validateUiToController(value);
    } catch (error) {
      postFailure(controllerFailure("INVALID_UI_MESSAGE", error instanceof Error ? error.message : "Invalid UI message."));
      return;
    }
    try {
      switch (message.type) {
        case "refresh-selection":
          await refreshSelection();
          break;
        case "build-package":
          await buildPackage();
          break;
        case "package-ready":
          acceptPackage(message.generation, message.value);
          break;
        case "pair":
          await runBridgeOperation(message.operation, () => pair(message.operation, message.code));
          break;
        case "send-live":
          await runBridgeOperation(message.operation, () => sendLive(message.operation));
          break;
        case "close":
          host.closePlugin();
          break;
      }
    } catch (error) {
      postFailure(error);
    }
  };

  return { handleMessage, refreshSelection };
}

declare const __html__: string;
declare const __VIDEO001_CONFIG__: EmbeddedVideo001Config;

function startRuntime(): void {
  figma.showUI(__html__, {
    width: 420,
    height: 640,
    themeColors: true,
    title: "Video 001 → After Effects"
  });
  const controller = createController({
    fileKey: figma.fileKey,
    getCurrentPage: () => figma.currentPage as unknown as ControllerPage,
    mixed: figma.mixed,
    postMessage: (message) => figma.ui.postMessage(message),
    closePlugin: () => figma.closePlugin(),
    now: () => new Date(),
    clientStorage: figma.clientStorage,
    fetch: (input, init) => (fetch as unknown as FigmaSandboxFetch)(input, init)
  }, __VIDEO001_CONFIG__);
  figma.ui.onmessage = (message: unknown) => {
    void controller.handleMessage(message);
  };
  figma.on("selectionchange", () => {
    void controller.refreshSelection();
  });
  void controller.refreshSelection();
}

if (typeof figma !== "undefined" && typeof __VIDEO001_CONFIG__ !== "undefined" && typeof __html__ !== "undefined") {
  startRuntime();
}
