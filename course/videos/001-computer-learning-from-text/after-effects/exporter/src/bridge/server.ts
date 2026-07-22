import { createHash } from "node:crypto";
import { constants } from "node:fs";
import { lstat, open, readdir, rename, unlink } from "node:fs/promises";
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";
import { join } from "node:path";
import { contentFingerprintInput, type ExporterPackage, validatePackage } from "../shared/contract.ts";
import { LIMITS } from "../shared/limits.ts";
import type { AuthStore } from "./auth.ts";
import { QueueConflictError, type QueueStore } from "./queue.ts";

const JSON_MEDIA_TYPE = "application/json";
const EXPORT_MEDIA_TYPE = "application/vnd.video001.figma-ae+json";
const RETENTION_MS = 7 * 24 * 60 * 60_000;
const MAX_LOG_BYTES = 10 * 1024 * 1024;
const PAIRING_WINDOW_MS = 60_000;
const MAX_PAIRING_FAILURES = 5;

interface BridgeLimits {
  maxBodyBytes: number;
  maxLogBytes: number;
  requestTimeoutMs: number;
  retentionMs: number;
}

export interface CreateBridgeServerOptions {
  auth: AuthStore;
  host: string;
  limits?: Partial<BridgeLimits>;
  now?: () => number;
  port: number;
  queue: QueueStore;
}

export interface BridgeServer {
  address(): AddressInfo;
  close(): Promise<void>;
  flushLogs(): Promise<void>;
  start(): Promise<AddressInfo>;
}

interface ErrorBody {
  error: {
    code: string;
    message: string;
  };
}

class BodyTooLargeError extends Error {}
class BodyTimeoutError extends Error {}
class BodyAbortedError extends Error {}

function validateIntegerLimit(name: string, value: number, allowZero = false): number {
  if (!Number.isSafeInteger(value) || value < (allowZero ? 0 : 1)) {
    throw new TypeError(`${name} must be ${allowZero ? "a non-negative" : "a positive"} safe integer`);
  }
  return value;
}

function hasMediaType(request: IncomingMessage, expected: string): boolean {
  const value = request.headers["content-type"];
  return typeof value === "string" && value.trim().toLowerCase() === expected;
}

function baseHeaders(): Record<string, string> {
  return {
    "cache-control": "no-store",
    "x-content-type-options": "nosniff"
  };
}

function sendJson(response: ServerResponse, status: number, value: unknown): void {
  if (response.destroyed || response.writableEnded) return;
  const body = Buffer.from(JSON.stringify(value), "utf8");
  response.writeHead(status, {
    ...baseHeaders(),
    "content-length": String(body.byteLength),
    "content-type": "application/json; charset=utf-8"
  });
  response.end(body);
}

function sendEmpty(response: ServerResponse, status: number): void {
  if (response.destroyed || response.writableEnded) return;
  response.writeHead(status, baseHeaders());
  response.end();
}

function errorBody(code: string, message: string): ErrorBody {
  return { error: { code, message } };
}

function terminateRequestAfterResponse(request: IncomingMessage, response: ServerResponse): void {
  request.pause();
  const destroy = (): void => {
    if (!request.destroyed) request.destroy();
  };
  if (response.writableFinished) destroy();
  else response.once("finish", destroy);
}

function declaredBodyIsOversized(request: IncomingMessage, maxBytes: number): boolean {
  const value = request.headers["content-length"];
  if (typeof value !== "string" || !/^(?:0|[1-9]\d*)$/.test(value)) return false;
  const length = Number(value);
  return !Number.isSafeInteger(length) || length > maxBytes;
}

async function readBoundedBody(
  request: IncomingMessage,
  maxBytes: number,
  timeoutSignal: AbortSignal,
  shutdownSignal: AbortSignal
): Promise<Buffer> {
  const declaredLength = request.headers["content-length"];
  if (typeof declaredLength === "string") {
    if (!/^(?:0|[1-9]\d*)$/.test(declaredLength)) throw new BodyAbortedError();
    const parsedLength = Number(declaredLength);
    if (!Number.isSafeInteger(parsedLength)) throw new BodyTooLargeError();
    if (parsedLength > maxBytes) throw new BodyTooLargeError();
  }

  const signal = AbortSignal.any([timeoutSignal, shutdownSignal]);
  return new Promise<Buffer>((resolve, reject) => {
    const chunks: Buffer[] = [];
    let received = 0;
    let settled = false;

    const cleanup = (): void => {
      request.off("data", onData);
      request.off("end", onEnd);
      request.off("aborted", onAborted);
      request.off("error", onAborted);
      signal.removeEventListener("abort", onTimeout);
    };
    const settle = (operation: () => void): void => {
      if (settled) return;
      settled = true;
      cleanup();
      operation();
    };
    const onData = (chunk: Buffer | string): void => {
      const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
      received += bytes.byteLength;
      if (received > maxBytes) {
        request.pause();
        settle(() => reject(new BodyTooLargeError()));
        return;
      }
      chunks.push(bytes);
    };
    const onEnd = (): void => settle(() => resolve(Buffer.concat(chunks, received)));
    const onAborted = (): void => settle(() => reject(new BodyAbortedError()));
    const onTimeout = (): void => {
      request.pause();
      settle(() => reject(shutdownSignal.aborted ? new BodyAbortedError() : new BodyTimeoutError()));
    };

    request.on("data", onData);
    request.once("end", onEnd);
    request.once("aborted", onAborted);
    request.once("error", onAborted);
    signal.addEventListener("abort", onTimeout, { once: true });
    if (signal.aborted) onTimeout();
  });
}

function parseJson(body: Buffer): unknown {
  return JSON.parse(body.toString("utf8")) as unknown;
}

function isPairRequest(value: unknown): value is { code: string } {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  return Object.keys(record).length === 1 && typeof record.code === "string" && /^\d{6}$/.test(record.code);
}

function verifyAssets(value: ExporterPackage): boolean {
  for (const asset of value.assets) {
    const bytes = Buffer.from(asset.dataBase64, "base64");
    if (bytes.byteLength !== asset.byteLength) return false;
    if (createHash("sha256").update(bytes).digest("hex") !== asset.hash) return false;
  }
  return true;
}

async function syncDirectory(path: string): Promise<void> {
  const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    await handle.sync();
  } finally {
    await handle.close();
  }
}

async function pathExists(path: string): Promise<boolean> {
  try {
    await lstat(path);
    return true;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
    throw error;
  }
}

class StructuredLog {
  private chain: Promise<void> = Promise.resolve();
  private failure: unknown;
  private rotationSequence = 0;

  constructor(
    private readonly directory: string,
    private readonly maxBytes: number,
    private readonly now: () => number,
    private readonly assertDirectories: () => void
  ) {}

  async prune(directories: readonly string[], retentionMs: number): Promise<void> {
    const cutoff = this.now() - retentionMs;
    for (const directory of directories) {
      this.assertDirectories();
      for (const name of await readdir(directory)) {
        this.assertDirectories();
        const path = join(directory, name);
        const details = await lstat(path);
        if (details.isFile() && !details.isSymbolicLink() && details.mtimeMs < cutoff) {
          this.assertDirectories();
          await unlink(path);
        }
      }
      this.assertDirectories();
      await syncDirectory(directory);
    }
  }

  record(route: string, status: number, code?: string): void {
    const entry: Record<string, unknown> = {
      timestamp: new Date(this.now()).toISOString(),
      event: "http_request",
      route,
      status
    };
    if (code !== undefined) entry.code = code;
    const line = Buffer.from(`${JSON.stringify(entry)}\n`, "utf8");
    this.chain = this.chain.then(() => this.write(line)).catch((error: unknown) => {
      this.failure = error;
    });
  }

  async flush(): Promise<void> {
    await this.chain;
    if (this.failure !== undefined) throw new Error("Bridge log write failed", { cause: this.failure });
  }

  private async write(line: Buffer): Promise<void> {
    const currentPath = join(this.directory, "bridge.log");
    this.assertDirectories();
    let handle = await open(
      currentPath,
      constants.O_WRONLY | constants.O_CREAT | constants.O_APPEND | constants.O_NOFOLLOW,
      0o600
    );
    try {
      const details = await handle.stat();
      if (!details.isFile()) throw new Error("Bridge log path is not a regular file");
      await handle.chmod(0o600);
      if (details.size > 0 && details.size + line.byteLength > this.maxBytes) {
        await handle.close();
        handle = undefined as never;
        this.assertDirectories();
        await this.rotate(currentPath);
        this.assertDirectories();
        handle = await open(
          currentPath,
          constants.O_WRONLY | constants.O_CREAT | constants.O_APPEND | constants.O_NOFOLLOW,
          0o600
        );
      }
      await handle.write(line);
      await handle.sync();
    } finally {
      if (handle !== undefined) await handle.close();
    }
  }

  private async rotate(currentPath: string): Promise<void> {
    let destination: string;
    do {
      this.rotationSequence += 1;
      destination = join(this.directory, `bridge.${this.now()}.${this.rotationSequence}.log`);
    } while (await pathExists(destination));
    this.assertDirectories();
    await rename(currentPath, destination);
    this.assertDirectories();
    await syncDirectory(this.directory);
  }
}

class NodeBridgeServer implements BridgeServer {
  private readonly auth: AuthStore;
  private readonly host: string;
  private readonly limits: BridgeLimits;
  private readonly log: StructuredLog;
  private readonly now: () => number;
  private readonly port: number;
  private readonly queue: QueueStore;
  private readonly server: Server;
  private readonly shutdownController = new AbortController();
  private readonly activeHandlers = new Set<Promise<void>>();
  private failedPairings: number[] = [];
  private started = false;
  private closing: Promise<void> | undefined;

  constructor(options: CreateBridgeServerOptions) {
    if (options.host !== "127.0.0.1") {
      throw new TypeError("Bridge host must be exactly 127.0.0.1 (IPv4 loopback)");
    }
    if (!Number.isSafeInteger(options.port) || options.port < 0 || options.port > 65_535) {
      throw new TypeError("Bridge port must be an integer from 0 through 65535");
    }
    const configured = options.limits ?? {};
    this.limits = {
      maxBodyBytes: validateIntegerLimit("maxBodyBytes", configured.maxBodyBytes ?? LIMITS.maxBodyBytes),
      maxLogBytes: validateIntegerLimit("maxLogBytes", configured.maxLogBytes ?? MAX_LOG_BYTES),
      requestTimeoutMs: validateIntegerLimit("requestTimeoutMs", configured.requestTimeoutMs ?? LIMITS.requestTimeoutMs),
      retentionMs: validateIntegerLimit("retentionMs", configured.retentionMs ?? RETENTION_MS)
    };
    this.auth = options.auth;
    this.host = options.host;
    this.now = options.now ?? Date.now;
    this.port = options.port;
    this.queue = options.queue;
    this.log = new StructuredLog(
      this.queue.paths.logs,
      this.limits.maxLogBytes,
      this.now,
      () => this.queue.assertHealthy()
    );
    this.server = createServer((request, response) => {
      const handler = this.handle(request, response).catch(() => {
        this.respondError(response, "internal", 500, "INTERNAL_ERROR", "The bridge could not process the request");
      });
      this.activeHandlers.add(handler);
      void handler.finally(() => this.activeHandlers.delete(handler));
    });
    this.server.requestTimeout = this.limits.requestTimeoutMs;
    this.server.on("clientError", (_error, socket) => socket.destroy());
  }

  async start(): Promise<AddressInfo> {
    if (this.started) return this.address();
    this.queue.assertHealthy();
    await this.log.prune(
      [this.queue.paths.quarantine, this.queue.paths.logs],
      this.limits.retentionMs
    );
    await new Promise<void>((resolve, reject) => {
      const onError = (error: Error): void => {
        this.server.off("listening", onListening);
        reject(error);
      };
      const onListening = (): void => {
        this.server.off("error", onError);
        resolve();
      };
      this.server.once("error", onError);
      this.server.once("listening", onListening);
      this.server.listen({ host: this.host, port: this.port, exclusive: true });
    });
    this.started = true;
    return this.address();
  }

  address(): AddressInfo {
    const value = this.server.address();
    if (value === null || typeof value === "string") throw new Error("Bridge is not listening");
    return value;
  }

  async close(): Promise<void> {
    if (this.closing !== undefined) return this.closing;
    this.closing = (async () => {
      this.shutdownController.abort();
      if (this.started) {
        await new Promise<void>((resolve, reject) => {
          this.server.close((error) => error === undefined ? resolve() : reject(error));
          this.server.closeIdleConnections();
          this.server.closeAllConnections();
        });
        this.started = false;
      }
      await Promise.allSettled([...this.activeHandlers]);
      await this.log.flush();
    })();
    return this.closing;
  }

  async flushLogs(): Promise<void> {
    await this.log.flush();
  }

  private async handle(request: IncomingMessage, response: ServerResponse): Promise<void> {
    const route = this.routeName(request.url);
    const allowedMethod = route === "health" ? "GET" : route === "unknown" ? undefined : "POST";
    if (route === "unknown") {
      this.respondError(response, route, 404, "NOT_FOUND", "The requested route does not exist");
      return;
    }
    if (request.method !== allowedMethod) {
      response.setHeader("allow", allowedMethod ?? "");
      this.respondError(response, route, 405, "METHOD_NOT_ALLOWED", "The request method is not allowed for this route");
      return;
    }
    if (request.method === "POST" && declaredBodyIsOversized(request, this.limits.maxBodyBytes)) {
      this.respondError(response, route, 413, "PAYLOAD_TOO_LARGE", "The request body exceeds the configured limit");
      terminateRequestAfterResponse(request, response);
      return;
    }
    if (route === "health") {
      sendJson(response, 200, { status: "ok", schemaMajor: 1 });
      this.log.record(route, 200);
      return;
    }
    if (route === "pair") {
      await this.handlePair(request, response);
      return;
    }
    if (route === "reset") {
      if (!this.auth.authenticateBearer(request.headers.authorization)) {
        this.respondError(response, route, 401, "UNAUTHORIZED", "A valid bearer token is required");
        return;
      }
      this.auth.revokeAll();
      sendEmpty(response, 204);
      this.log.record(route, 204);
      return;
    }
    await this.handleExport(request, response);
  }

  private async handlePair(request: IncomingMessage, response: ServerResponse): Promise<void> {
    const route = "pair";
    if (!hasMediaType(request, JSON_MEDIA_TYPE)) {
      this.respondError(response, route, 415, "UNSUPPORTED_MEDIA_TYPE", "The request content type is not supported");
      return;
    }
    this.prunePairingFailures();
    if (this.failedPairings.length >= MAX_PAIRING_FAILURES) {
      this.respondError(response, route, 429, "PAIRING_RATE_LIMITED", "Too many failed pairing attempts");
      terminateRequestAfterResponse(request, response);
      return;
    }
    const body = await this.readBodyOrRespond(request, response, route);
    if (body === undefined) return;
    let value: unknown;
    try {
      value = parseJson(body);
    } catch {
      this.respondError(response, route, 400, "INVALID_JSON", "The request body must be valid JSON");
      return;
    }
    if (!isPairRequest(value)) {
      this.respondError(response, route, 422, "INVALID_PAIRING_REQUEST", "The pairing request is invalid");
      return;
    }
    try {
      const token = this.auth.exchangePairingCode(value.code);
      this.failedPairings = [];
      sendJson(response, 200, { token });
      this.log.record(route, 200);
    } catch {
      this.failedPairings.push(this.now());
      this.respondError(response, route, 401, "PAIRING_FAILED", "The pairing code is invalid or expired");
    }
  }

  private async handleExport(request: IncomingMessage, response: ServerResponse): Promise<void> {
    const route = "export";
    if (!hasMediaType(request, EXPORT_MEDIA_TYPE)) {
      this.respondError(response, route, 415, "UNSUPPORTED_MEDIA_TYPE", "The request content type is not supported");
      return;
    }
    if (!this.auth.authenticateBearer(request.headers.authorization)) {
      this.respondError(response, route, 401, "UNAUTHORIZED", "A valid bearer token is required");
      return;
    }
    const body = await this.readBodyOrRespond(request, response, route);
    if (body === undefined) return;
    let parsed: unknown;
    try {
      parsed = parseJson(body);
    } catch {
      this.respondError(response, route, 400, "INVALID_JSON", "The request body must be valid JSON");
      return;
    }
    let value: ExporterPackage;
    try {
      value = validatePackage(parsed);
    } catch {
      this.respondError(response, route, 422, "INVALID_PACKAGE", "The export package is invalid");
      return;
    }
    const actualContentHash = createHash("sha256").update(contentFingerprintInput(value)).digest("hex");
    if (actualContentHash !== value.contentHash) {
      this.respondError(response, route, 422, "CONTENT_HASH_MISMATCH", "The package fingerprint does not match its contents");
      return;
    }
    if (!verifyAssets(value)) {
      this.respondError(response, route, 422, "ASSET_HASH_MISMATCH", "An asset hash does not match its decoded bytes");
      return;
    }
    try {
      await this.queue.enqueue(value);
    } catch (error) {
      if (error instanceof QueueConflictError) {
        this.respondError(response, route, 409, "QUEUE_DUPLICATE", "This package is already queued");
        return;
      }
      throw error;
    }
    sendJson(response, 202, { status: "accepted", contentHash: value.contentHash });
    this.log.record(route, 202);
  }

  private async readBodyOrRespond(
    request: IncomingMessage,
    response: ServerResponse,
    route: string
  ): Promise<Buffer | undefined> {
    try {
      return await readBoundedBody(
        request,
        this.limits.maxBodyBytes,
        AbortSignal.timeout(this.limits.requestTimeoutMs),
        this.shutdownController.signal
      );
    } catch (error) {
      if (error instanceof BodyTooLargeError) {
        this.respondError(response, route, 413, "PAYLOAD_TOO_LARGE", "The request body exceeds the configured limit");
        terminateRequestAfterResponse(request, response);
      } else if (error instanceof BodyTimeoutError) {
        this.respondError(response, route, 408, "REQUEST_TIMEOUT", "The request body was not received in time");
        terminateRequestAfterResponse(request, response);
      } else {
        if (!request.destroyed) request.destroy();
      }
      return undefined;
    }
  }

  private prunePairingFailures(): void {
    const now = this.now();
    this.failedPairings = this.failedPairings.filter((timestamp) => now - timestamp < PAIRING_WINDOW_MS);
  }

  private respondError(
    response: ServerResponse,
    route: string,
    status: number,
    code: string,
    message: string
  ): void {
    sendJson(response, status, errorBody(code, message));
    this.log.record(route, status, code);
  }

  private routeName(url: string | undefined): "export" | "health" | "pair" | "reset" | "unknown" {
    if (url === "/health") return "health";
    if (url === "/v1/pair") return "pair";
    if (url === "/v1/export") return "export";
    if (url === "/v1/reset") return "reset";
    return "unknown";
  }
}

export function createBridgeServer(options: CreateBridgeServerOptions): BridgeServer {
  return new NodeBridgeServer(options);
}
