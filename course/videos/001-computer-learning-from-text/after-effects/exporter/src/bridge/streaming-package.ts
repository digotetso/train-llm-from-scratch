import { createHash, randomUUID, type Hash } from "node:crypto";
import { constants } from "node:fs";
import { lstat, open, unlink, type FileHandle } from "node:fs/promises";
import { basename, dirname, join } from "node:path";
import {
  EXTERNAL_ASSET_DATA,
  validatePackageWithVerifiedAssets,
  type ExternalExporterPackage,
  type VerifiedAssetEvidence
} from "../shared/contract.ts";
import { LIMITS } from "../shared/limits.ts";
import {
  ownedHttpTemporaryFilename,
  parseBridgeOwner,
  parseOwnedHttpTemporaryFilename,
  type BridgeOwner,
  type OwnedHttpTemporaryKind
} from "./ownership.ts";
import type { QueueStore } from "./queue.ts";

const BASE64_BUFFER_BYTES = 64 * 1024;
const BASE64_ALPHABET_BYTES = Buffer.from("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/", "ascii");
const DEFAULT_FILE_CHUNK_BYTES = 64 * 1024;
const MAX_JSON_DEPTH = 256;
const HASH_PATTERN = /^[0-9a-f]{64}$/;

export type OwnedTemporaryKind = OwnedHttpTemporaryKind;

export interface OwnedTemporaryFile {
  device: number;
  inode: number;
  kind: OwnedTemporaryKind;
  owner: BridgeOwner;
  path: string;
  size: number;
}

export interface StreamedAssetFile extends OwnedTemporaryFile {
  hash: string;
  kind: "http-asset";
}

export interface StreamingPackageLimits {
  maxAggregateAssetBytes: number;
  maxAssetBytes: number;
  maxBodyBytes: number;
  maxManifestBytes: number;
}

export interface StreamingPackageResult {
  assets: StreamedAssetFile[];
  bodyBytes: number;
  manifestBytes: number;
  package: ExternalExporterPackage;
}

export interface StreamingReadOptions {
  chunkBytes?: number;
  limits?: StreamingPackageLimits;
}

export class StreamingPackageSyntaxError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StreamingPackageSyntaxError";
  }
}

export class StreamingPackageValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StreamingPackageValidationError";
  }
}

export class StreamingPackageLimitError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StreamingPackageLimitError";
  }
}

function positiveInteger(name: string, value: number): number {
  if (!Number.isSafeInteger(value) || value < 1) throw new TypeError(`${name} must be a positive safe integer`);
  return value;
}

function configuredLimits(value?: StreamingPackageLimits): StreamingPackageLimits {
  const limits = value ?? {
    maxAggregateAssetBytes: LIMITS.maxAggregateAssetBytes,
    maxAssetBytes: LIMITS.maxAssetBytes,
    maxBodyBytes: LIMITS.maxBodyBytes,
    maxManifestBytes: LIMITS.maxManifestBytes
  };
  return {
    maxAggregateAssetBytes: positiveInteger("maxAggregateAssetBytes", limits.maxAggregateAssetBytes),
    maxAssetBytes: positiveInteger("maxAssetBytes", limits.maxAssetBytes),
    maxBodyBytes: positiveInteger("maxBodyBytes", limits.maxBodyBytes),
    maxManifestBytes: positiveInteger("maxManifestBytes", limits.maxManifestBytes)
  };
}

function sameOwner(first: BridgeOwner, second: BridgeOwner): boolean {
  return first.pid === second.pid && first.instanceId === second.instanceId && first.version === second.version;
}

function temporaryPath(queue: QueueStore, kind: OwnedTemporaryKind, owner: BridgeOwner): string {
  return join(queue.paths.tmp, ownedHttpTemporaryFilename(kind, owner, randomUUID()));
}

function assertOwnedTemporaryLocation(file: OwnedTemporaryFile, queue: QueueStore): void {
  let filename: ReturnType<typeof parseOwnedHttpTemporaryFilename>;
  try {
    filename = parseOwnedHttpTemporaryFilename(basename(file.path));
  } catch {
    throw new Error("Owned temporary filename is malformed");
  }
  if (
    dirname(file.path) !== queue.paths.tmp ||
    filename.kind !== file.kind ||
    !sameOwner(filename.owner, file.owner) ||
    (queue.owner !== undefined && !sameOwner(file.owner, queue.owner))
  ) {
    throw new Error("Owned temporary path, kind, or lifecycle owner does not match the queue");
  }
}

async function removeTemporary(file: OwnedTemporaryFile, queue: QueueStore, sync: boolean): Promise<void> {
  queue.assertHealthy();
  assertOwnedTemporaryLocation(file, queue);
  const current = await lstat(file.path);
  if (
    !current.isFile() ||
    current.isSymbolicLink() ||
    current.dev !== file.device ||
    current.ino !== file.inode
  ) {
    throw new Error("Owned temporary file changed identity before cleanup");
  }
  await unlink(file.path);
  queue.assertHealthy();
  if (sync) await queue.syncTemporaryDirectory();
}

export async function cleanupStreamedAssets(
  files: readonly StreamedAssetFile[],
  queue: QueueStore
): Promise<void> {
  if (files.length === 0) return;
  for (const file of files) await removeTemporary(file, queue, false);
  await queue.syncTemporaryDirectory();
}

class JsonFileReader {
  private readonly buffer: Buffer;
  private bufferEnd = 0;
  private bufferPosition = 0;
  private filePosition = 0;
  manifestBytes = 0;

  constructor(
    private readonly handle: FileHandle,
    chunkBytes: number,
    private readonly maxManifestBytes: number
  ) {
    this.buffer = Buffer.allocUnsafe(chunkBytes);
  }

  async peek(): Promise<number | undefined> {
    if (this.bufferPosition >= this.bufferEnd) await this.fill();
    return this.bufferPosition >= this.bufferEnd ? undefined : this.buffer[this.bufferPosition];
  }

  async read(countManifest = true): Promise<number | undefined> {
    const value = await this.peek();
    if (value === undefined) return undefined;
    this.bufferPosition += 1;
    if (countManifest) {
      this.manifestBytes += 1;
      if (this.manifestBytes > this.maxManifestBytes) {
        throw new StreamingPackageLimitError("Package manifest exceeds its byte limit");
      }
    }
    return value;
  }

  get bytesRead(): number {
    return this.filePosition - (this.bufferEnd - this.bufferPosition);
  }

  private async fill(): Promise<void> {
    const result = await this.handle.read(this.buffer, 0, this.buffer.byteLength, this.filePosition);
    this.bufferPosition = 0;
    this.bufferEnd = result.bytesRead;
    this.filePosition += result.bytesRead;
  }
}

function isWhitespace(byte: number): boolean {
  return byte === 0x20 || byte === 0x09 || byte === 0x0a || byte === 0x0d;
}

function isNumberByte(byte: number): boolean {
  return (
    (byte >= 0x30 && byte <= 0x39) ||
    byte === 0x2d ||
    byte === 0x2b ||
    byte === 0x2e ||
    byte === 0x45 ||
    byte === 0x65
  );
}

function base64Value(byte: number): number {
  if (byte >= 0x41 && byte <= 0x5a) return byte - 0x41;
  if (byte >= 0x61 && byte <= 0x7a) return byte - 0x61 + 26;
  if (byte >= 0x30 && byte <= 0x39) return byte - 0x30 + 52;
  if (byte === 0x2b) return 62;
  if (byte === 0x2f) return 63;
  return -1;
}

function decodeBase64Bytes(encoded: Uint8Array): Buffer {
  const padding = encoded.byteLength === 0
    ? 0
    : encoded[encoded.byteLength - 2] === 0x3d
      ? 2
      : encoded[encoded.byteLength - 1] === 0x3d
        ? 1
        : 0;
  const decoded = Buffer.allocUnsafe((encoded.byteLength / 4) * 3 - padding);
  let output = 0;
  for (let input = 0; input < encoded.byteLength; input += 4) {
    const first = base64Value(encoded[input]!);
    const second = base64Value(encoded[input + 1]!);
    const third = encoded[input + 2] === 0x3d ? 0 : base64Value(encoded[input + 2]!);
    const fourth = encoded[input + 3] === 0x3d ? 0 : base64Value(encoded[input + 3]!);
    decoded[output] = (first << 2) | (second >> 4);
    output += 1;
    if (output < decoded.byteLength) {
      decoded[output] = ((second & 0x0f) << 4) | (third >> 2);
      output += 1;
    }
    if (output < decoded.byteLength) {
      decoded[output] = ((third & 0x03) << 6) | fourth;
      output += 1;
    }
  }
  return decoded;
}

function encodeBase64Bytes(decoded: Uint8Array): Buffer {
  const encoded = Buffer.allocUnsafe(Math.ceil(decoded.byteLength / 3) * 4);
  let output = 0;
  for (let input = 0; input < decoded.byteLength; input += 3) {
    const remaining = decoded.byteLength - input;
    const first = decoded[input]!;
    const second = remaining > 1 ? decoded[input + 1]! : 0;
    const third = remaining > 2 ? decoded[input + 2]! : 0;
    encoded[output] = BASE64_ALPHABET_BYTES[first >> 2]!;
    encoded[output + 1] = BASE64_ALPHABET_BYTES[((first & 0x03) << 4) | (second >> 4)]!;
    encoded[output + 2] = remaining > 1
      ? BASE64_ALPHABET_BYTES[((second & 0x0f) << 2) | (third >> 6)]!
      : 0x3d;
    encoded[output + 3] = remaining > 2 ? BASE64_ALPHABET_BYTES[third & 0x3f]! : 0x3d;
    output += 4;
  }
  return encoded;
}

async function writeAll(handle: FileHandle, value: Uint8Array): Promise<void> {
  let offset = 0;
  while (offset < value.byteLength) {
    const result = await handle.write(value, offset, value.byteLength - offset, null);
    if (result.bytesWritten === 0) throw new Error("Temporary file write made no progress");
    offset += result.bytesWritten;
  }
}

class StreamingJsonParser {
  readonly assets: StreamedAssetFile[] = [];
  private readonly evidence: VerifiedAssetEvidence[] = [];
  private aggregateAssetBytes = 0;

  constructor(
    private readonly reader: JsonFileReader,
    private readonly queue: QueueStore,
    private readonly owner: BridgeOwner,
    private readonly limits: StreamingPackageLimits
  ) {}

  async parse(): Promise<unknown> {
    await this.skipWhitespace();
    const value = await this.parseValue("$", 0);
    await this.skipWhitespace();
    if (await this.reader.peek() !== undefined) throw new StreamingPackageSyntaxError("Unexpected trailing JSON data");
    return value;
  }

  get verifiedEvidence(): readonly VerifiedAssetEvidence[] {
    return this.evidence;
  }

  private async parseValue(path: string, depth: number): Promise<unknown> {
    if (depth > MAX_JSON_DEPTH) throw new StreamingPackageValidationError("JSON nesting exceeds the bridge limit");
    await this.skipWhitespace();
    const byte = await this.reader.peek();
    if (byte === undefined) throw new StreamingPackageSyntaxError("Unexpected end of JSON input");
    if (byte === 0x7b) return this.parseObject(path, depth + 1);
    if (byte === 0x5b) return this.parseArray(path, depth + 1);
    if (byte === 0x22) return this.parseString();
    if (byte === 0x74) return this.parseLiteral("true", true);
    if (byte === 0x66) return this.parseLiteral("false", false);
    if (byte === 0x6e) return this.parseLiteral("null", null);
    if (byte === 0x2d || (byte >= 0x30 && byte <= 0x39)) return this.parseNumber();
    throw new StreamingPackageSyntaxError("Unexpected JSON token");
  }

  private async parseObject(path: string, depth: number): Promise<Record<string, unknown>> {
    await this.expect(0x7b);
    const result: Record<string, unknown> = {};
    await this.skipWhitespace();
    if (await this.consumeIf(0x7d)) return result;
    while (true) {
      if (await this.reader.peek() !== 0x22) throw new StreamingPackageSyntaxError("JSON object key must be a string");
      const key = await this.parseString();
      await this.skipWhitespace();
      await this.expect(0x3a);
      await this.skipWhitespace();
      if (path === "$" && key === "assets" && await this.reader.peek() === 0x5b) {
        if (this.assets.length > 0) {
          await cleanupStreamedAssets([...this.assets], this.queue);
          this.assets.length = 0;
          this.evidence.length = 0;
          this.aggregateAssetBytes = 0;
        }
        result[key] = await this.parseAssets(depth + 1);
      } else {
        result[key] = await this.parseValue(`${path}.${key}`, depth + 1);
      }
      await this.skipWhitespace();
      if (await this.consumeIf(0x7d)) return result;
      await this.expect(0x2c);
      await this.skipWhitespace();
    }
  }

  private async parseArray(path: string, depth: number): Promise<unknown[]> {
    await this.expect(0x5b);
    const result: unknown[] = [];
    await this.skipWhitespace();
    if (await this.consumeIf(0x5d)) return result;
    while (true) {
      result.push(await this.parseValue(`${path}[${result.length}]`, depth + 1));
      await this.skipWhitespace();
      if (await this.consumeIf(0x5d)) return result;
      await this.expect(0x2c);
      await this.skipWhitespace();
    }
  }

  private async parseAssets(depth: number): Promise<unknown[]> {
    await this.expect(0x5b);
    const result: unknown[] = [];
    await this.skipWhitespace();
    if (await this.consumeIf(0x5d)) return result;
    while (true) {
      const index = result.length;
      if (index >= LIMITS.maxAssets) throw new StreamingPackageValidationError("Asset count exceeds its limit");
      await this.skipWhitespace();
      if (await this.reader.peek() === 0x7b) result.push(await this.parseAssetObject(index, depth + 1));
      else {
        result.push(await this.parseValue(`$.assets[${index}]`, depth + 1));
        this.evidence[index] = { byteLength: -1, hash: "" };
      }
      await this.skipWhitespace();
      if (await this.consumeIf(0x5d)) return result;
      await this.expect(0x2c);
      await this.skipWhitespace();
    }
  }

  private async parseAssetObject(index: number, depth: number): Promise<Record<string, unknown>> {
    await this.expect(0x7b);
    const result: Record<string, unknown> = {};
    let currentFile: StreamedAssetFile | undefined;
    await this.skipWhitespace();
    if (await this.consumeIf(0x7d)) {
      this.evidence[index] = { byteLength: -1, hash: "" };
      return result;
    }
    while (true) {
      if (await this.reader.peek() !== 0x22) throw new StreamingPackageSyntaxError("JSON object key must be a string");
      const key = await this.parseString();
      await this.skipWhitespace();
      await this.expect(0x3a);
      await this.skipWhitespace();
      if (key === "dataBase64" && await this.reader.peek() === 0x22) {
        if (currentFile !== undefined) {
          await cleanupStreamedAssets([currentFile], this.queue);
          const existing = this.assets.indexOf(currentFile);
          if (existing >= 0) this.assets.splice(existing, 1);
          this.aggregateAssetBytes -= currentFile.size;
        }
        currentFile = await this.parseBase64Asset();
        if (this.aggregateAssetBytes + currentFile.size > this.limits.maxAggregateAssetBytes) {
          await cleanupStreamedAssets([currentFile], this.queue);
          throw new StreamingPackageValidationError("Assets exceed the aggregate decoded-byte limit");
        }
        this.aggregateAssetBytes += currentFile.size;
        this.assets.push(currentFile);
        this.evidence[index] = { byteLength: currentFile.size, hash: currentFile.hash };
        result[key] = EXTERNAL_ASSET_DATA;
      } else {
        result[key] = await this.parseValue(`$.assets[${index}].${key}`, depth + 1);
      }
      await this.skipWhitespace();
      if (await this.consumeIf(0x7d)) {
        if (currentFile === undefined) this.evidence[index] = { byteLength: -1, hash: "" };
        return result;
      }
      await this.expect(0x2c);
      await this.skipWhitespace();
    }
  }

  private async parseBase64Asset(): Promise<StreamedAssetFile> {
    await this.expect(0x22);
    const path = temporaryPath(this.queue, "http-asset", this.owner);
    let handle: FileHandle | undefined;
    let file: OwnedTemporaryFile | undefined;
    try {
      this.queue.assertHealthy();
      handle = await open(
        path,
        constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW,
        0o600
      );
      await handle.chmod(0o600);
      const opened = await handle.stat();
      if (!opened.isFile()) throw new Error("Streamed asset temporary is not a regular file");
      file = {
        device: opened.dev,
        inode: opened.ino,
        kind: "http-asset",
        owner: this.owner,
        path,
        size: 0
      };
      this.queue.assertHealthy();

      const encoded = Buffer.allocUnsafe(BASE64_BUFFER_BYTES);
      let encodedLength = 0;
      let encodedTotal = 0;
      let decodedTotal = 0;
      let sawPadding = false;
      let padding = 0;
      const finalQuartet: number[] = [];
      const digest = createHash("sha256");

      const flush = async (): Promise<void> => {
        if (encodedLength === 0) return;
        const decoded = decodeBase64Bytes(encoded.subarray(0, encodedLength));
        decodedTotal += decoded.byteLength;
        if (decodedTotal > this.limits.maxAssetBytes) {
          throw new StreamingPackageValidationError("Asset exceeds the per-asset decoded-byte limit");
        }
        digest.update(decoded);
        if (handle === undefined) throw new Error("Streamed asset temporary handle is unavailable");
        await writeAll(handle, decoded);
        encodedLength = 0;
      };

      while (true) {
        const next = await this.reader.peek();
        if (next === undefined) throw new StreamingPackageSyntaxError("Unterminated asset data string");
        if (next === 0x22) {
          await this.reader.read(true);
          break;
        }
        const byte = await this.reader.read(false);
        if (byte === undefined) throw new StreamingPackageSyntaxError("Unterminated asset data string");
        const symbol = base64Value(byte);
        if (byte === 0x3d) {
          sawPadding = true;
          padding += 1;
          if (padding > 2) throw new StreamingPackageValidationError("Asset data is not canonical base64");
        } else if (symbol < 0 || sawPadding) {
          throw new StreamingPackageValidationError("Asset data is not unescaped canonical base64");
        }
        encoded[encodedLength] = byte;
        encodedLength += 1;
        encodedTotal += 1;
        finalQuartet.push(byte);
        if (finalQuartet.length > 4) finalQuartet.shift();
        if (encodedLength === encoded.byteLength && !sawPadding) await flush();
      }

      if (encodedTotal % 4 !== 0 || finalQuartet.length !== Math.min(encodedTotal, 4)) {
        throw new StreamingPackageValidationError("Asset data is not canonical base64");
      }
      if (padding > 0) {
        if (finalQuartet.length !== 4 || finalQuartet[3] !== 0x3d) {
          throw new StreamingPackageValidationError("Asset data is not canonical base64");
        }
        if (padding === 2) {
          if (finalQuartet[2] !== 0x3d || (base64Value(finalQuartet[1]!) & 0b1111) !== 0) {
            throw new StreamingPackageValidationError("Asset data is not canonical base64");
          }
        } else if ((base64Value(finalQuartet[2]!) & 0b11) !== 0) {
          throw new StreamingPackageValidationError("Asset data is not canonical base64");
        }
      }
      await flush();
      await handle.sync();
      const completed = await handle.stat();
      if (
        completed.dev !== file.device ||
        completed.ino !== file.inode ||
        completed.size !== decodedTotal ||
        !completed.isFile()
      ) {
        throw new Error("Streamed asset temporary changed identity or size");
      }
      await handle.close();
      handle = undefined;
      return { ...file, hash: digest.digest("hex"), size: decodedTotal, kind: "http-asset" };
    } catch (error) {
      if (handle !== undefined) {
        try { await handle.close(); } catch { /* preserve the parser failure */ }
      }
      if (file !== undefined) {
        try { await removeTemporary(file, this.queue, true); } catch { /* preserve the parser failure */ }
      }
      throw error;
    }
  }

  private async parseString(): Promise<string> {
    await this.expect(0x22);
    const chunks: Buffer[] = [];
    let current = Buffer.allocUnsafe(4 * 1024);
    let currentLength = 0;
    let escaped = false;
    let total = 0;
    while (true) {
      const byte = await this.reader.read(true);
      if (byte === undefined) throw new StreamingPackageSyntaxError("Unterminated JSON string");
      if (!escaped && byte === 0x22) break;
      current[currentLength] = byte;
      currentLength += 1;
      total += 1;
      if (currentLength === current.byteLength) {
        chunks.push(current);
        current = Buffer.allocUnsafe(4 * 1024);
        currentLength = 0;
      }
      if (escaped) escaped = false;
      else if (byte === 0x5c) escaped = true;
    }
    if (currentLength > 0) chunks.push(current.subarray(0, currentLength));
    let raw: string;
    try {
      raw = new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks, total));
      return JSON.parse(`"${raw}"`) as string;
    } catch {
      throw new StreamingPackageSyntaxError("Invalid JSON string encoding or escape");
    }
  }

  private async parseNumber(): Promise<number> {
    let token = "";
    while (true) {
      const byte = await this.reader.peek();
      if (byte === undefined || !isNumberByte(byte)) break;
      await this.reader.read(true);
      token += String.fromCharCode(byte);
      if (token.length > this.limits.maxManifestBytes) {
        throw new StreamingPackageLimitError("JSON number exceeds the manifest limit");
      }
    }
    try {
      const value = JSON.parse(token) as unknown;
      if (typeof value !== "number") throw new Error("not a number");
      return value;
    } catch {
      throw new StreamingPackageSyntaxError("Invalid JSON number");
    }
  }

  private async parseLiteral<T>(literal: string, value: T): Promise<T> {
    for (const character of literal) {
      if (await this.reader.read(true) !== character.charCodeAt(0)) {
        throw new StreamingPackageSyntaxError("Invalid JSON literal");
      }
    }
    return value;
  }

  private async skipWhitespace(): Promise<void> {
    while (true) {
      const byte = await this.reader.peek();
      if (byte === undefined || !isWhitespace(byte)) return;
      await this.reader.read(true);
    }
  }

  private async consumeIf(expected: number): Promise<boolean> {
    if (await this.reader.peek() !== expected) return false;
    await this.reader.read(true);
    return true;
  }

  private async expect(expected: number): Promise<void> {
    if (await this.reader.read(true) !== expected) throw new StreamingPackageSyntaxError("Unexpected JSON punctuation");
  }
}

export async function readStreamingPackage(
  spool: OwnedTemporaryFile,
  queue: QueueStore,
  expectedOwner: BridgeOwner,
  options: StreamingReadOptions = {}
): Promise<StreamingPackageResult> {
  const owner = parseBridgeOwner(expectedOwner);
  assertOwnedTemporaryLocation(spool, queue);
  if (
    queue.owner === undefined ||
    spool.kind !== "http-body" ||
    !sameOwner(spool.owner, owner) ||
    !sameOwner(queue.owner, owner)
  ) {
    throw new Error("HTTP body spool owner does not match the bridge lifecycle");
  }
  const limits = configuredLimits(options.limits);
  if (spool.size > limits.maxBodyBytes) throw new StreamingPackageLimitError("Package exceeds the raw body limit");
  const chunkBytes = positiveInteger("chunkBytes", options.chunkBytes ?? DEFAULT_FILE_CHUNK_BYTES);
  queue.assertHealthy();
  const handle = await open(spool.path, constants.O_RDONLY | constants.O_NOFOLLOW);
  let parser: StreamingJsonParser | undefined;
  try {
    const before = await handle.stat();
    if (
      !before.isFile() ||
      before.dev !== spool.device ||
      before.ino !== spool.inode ||
      before.size !== spool.size
    ) {
      throw new Error("HTTP body spool changed before streaming parse");
    }
    const reader = new JsonFileReader(handle, chunkBytes, limits.maxManifestBytes);
    parser = new StreamingJsonParser(reader, queue, owner, limits);
    const value = await parser.parse();
    if (reader.bytesRead !== spool.size) throw new Error("HTTP body spool read count changed");
    const after = await handle.stat();
    if (after.dev !== spool.device || after.ino !== spool.inode || after.size !== spool.size) {
      throw new Error("HTTP body spool changed during streaming parse");
    }
    const packageValue = validatePackageWithVerifiedAssets(
      value,
      parser.verifiedEvidence,
      { bodyBytes: spool.size, manifestBytes: reader.manifestBytes }
    );
    return {
      assets: [...parser.assets],
      bodyBytes: spool.size,
      manifestBytes: reader.manifestBytes,
      package: packageValue
    };
  } catch (error) {
    if (parser !== undefined) await cleanupStreamedAssets([...parser.assets], queue);
    throw error;
  } finally {
    await handle.close();
  }
}

class ExternalCanonicalBase64 {
  constructor(readonly file: StreamedAssetFile) {}
}

async function updateCanonicalHash(
  hash: Hash,
  value: unknown,
  queue: QueueStore,
  chunkBytes: number
): Promise<void> {
  if (value instanceof ExternalCanonicalBase64) {
    await updateBase64Hash(hash, value.file, queue, chunkBytes);
    return;
  }
  if (value === null || typeof value !== "object") {
    const serialized = JSON.stringify(value);
    if (serialized === undefined) throw new TypeError("Cannot canonicalize a non-JSON value");
    hash.update(serialized);
    return;
  }
  if (Array.isArray(value)) {
    hash.update("[");
    for (let index = 0; index < value.length; index += 1) {
      if (index > 0) hash.update(",");
      await updateCanonicalHash(hash, value[index], queue, chunkBytes);
    }
    hash.update("]");
    return;
  }
  const record = value as Record<string, unknown>;
  hash.update("{");
  const keys = Object.keys(record).sort();
  for (let index = 0; index < keys.length; index += 1) {
    const key = keys[index]!;
    if (index > 0) hash.update(",");
    hash.update(`${JSON.stringify(key)}:`);
    await updateCanonicalHash(hash, record[key], queue, chunkBytes);
  }
  hash.update("}");
}

async function updateBase64Hash(
  outputHash: Hash,
  file: StreamedAssetFile,
  queue: QueueStore,
  chunkBytes: number
): Promise<void> {
  if (!HASH_PATTERN.test(file.hash)) throw new Error("Streamed asset hash is invalid");
  queue.assertHealthy();
  const handle = await open(file.path, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const before = await handle.stat();
    if (!before.isFile() || before.dev !== file.device || before.ino !== file.inode || before.size !== file.size) {
      throw new Error("Streamed asset changed before fingerprinting");
    }
    const decodedHash = createHash("sha256");
    const buffer = Buffer.allocUnsafe(chunkBytes);
    let position = 0;
    let carry = Buffer.alloc(0);
    outputHash.update('"');
    while (position < file.size) {
      const result = await handle.read(buffer, 0, Math.min(buffer.byteLength, file.size - position), position);
      if (result.bytesRead === 0) throw new Error("Streamed asset ended before its recorded size");
      const bytes = buffer.subarray(0, result.bytesRead);
      decodedHash.update(bytes);
      const combined = carry.byteLength === 0 ? bytes : Buffer.concat([carry, bytes]);
      const complete = combined.byteLength - (combined.byteLength % 3);
      if (complete > 0) outputHash.update(encodeBase64Bytes(combined.subarray(0, complete)));
      carry = Buffer.from(combined.subarray(complete));
      position += result.bytesRead;
    }
    if (carry.byteLength > 0) outputHash.update(encodeBase64Bytes(carry));
    outputHash.update('"');
    const after = await handle.stat();
    if (
      after.dev !== file.device ||
      after.ino !== file.inode ||
      after.size !== file.size ||
      decodedHash.digest("hex") !== file.hash
    ) {
      throw new Error("Streamed asset changed while fingerprinting");
    }
  } finally {
    await handle.close();
  }
}

export async function fingerprintStreamingPackage(
  value: ExternalExporterPackage,
  assets: readonly StreamedAssetFile[],
  queue: QueueStore,
  options: { chunkBytes?: number } = {}
): Promise<string> {
  if (value.assets.length !== assets.length) throw new Error("Streamed asset count does not match the package");
  const chunkBytes = positiveInteger("chunkBytes", options.chunkBytes ?? DEFAULT_FILE_CHUNK_BYTES);
  const canonicalValue = {
    ...value,
    contentHash: "",
    exportedAt: "",
    assets: value.assets.map((asset, index) => ({
      ...asset,
      dataBase64: new ExternalCanonicalBase64(assets[index]!)
    }))
  };
  const hash = createHash("sha256");
  await updateCanonicalHash(hash, canonicalValue, queue, chunkBytes);
  return hash.digest("hex");
}
