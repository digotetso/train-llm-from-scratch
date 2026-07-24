import { randomUUID } from "node:crypto";
import { constants } from "node:fs";
import { lstat, open, readdir, rename, unlink, type FileHandle } from "node:fs/promises";
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";
import { join } from "node:path";
import { LIMITS } from "../shared/limits.ts";
import { legacyVideo001ExportMediaType } from "../shared/legacy-video001.ts";
import { PairingCodeError, type AuthStore } from "./auth.ts";
import { ownedHttpTemporaryFilename, type BridgeOwner } from "./ownership.ts";
import { QueueConflictError, type QueueStore } from "./queue.ts";
import {
  cleanupStreamedAssets,
  fingerprintStreamingPackage,
  readStreamingPackage,
  StreamingPackageLimitError,
  StreamingPackageSyntaxError,
  StreamingPackageValidationError,
  type OwnedTemporaryFile,
  type StreamedAssetFile
} from "./streaming-package.ts";
import {
  BridgeWorkDeadlineError,
  BridgeWorkShutdownError,
  type BridgeWorkContext
} from "./work-control.ts";

const JSON_MEDIA_TYPE = "application/json";
const EXPORT_MEDIA_TYPE = legacyVideo001ExportMediaType;
const RETENTION_MS = 7 * 24 * 60 * 60_000;
const MAX_LOG_BYTES = 10 * 1024 * 1024;
const PAIRING_WINDOW_MS = 60_000;
const MAX_PAIRING_FAILURES = 5;
const MAX_CONTROL_BODY_BYTES = 1_024;
const MAX_CONCURRENT_EXPORT_BODY_WORK = 1;
const MAX_QUEUED_EXPORT_BODY_WORK = 1;

interface BridgeLimits {
  maxAggregateAssetBytes: number;
  maxAssetBytes: number;
  maxBodyBytes: number;
  maxControlBodyBytes: number;
  maxManifestBytes: number;
  maxLogBytes: number;
  requestTimeoutMs: number;
  retentionMs: number;
}

export interface CreateBridgeServerOptions {
  auth: AuthStore;
  createExportDeadlineSignal?: () => AbortSignal;
  host: string;
  limits?: Partial<BridgeLimits>;
  now?: () => number;
  port: number;
  queue: QueueStore;
  workCheckpoint?: BridgeWorkContext["checkpoint"];
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

type GateAcquisition = (() => void) | "busy" | "shutdown" | "timeout";

interface GateWaiter {
  cleanup(): void;
  resolve(result: GateAcquisition): void;
}

class BoundedWorkGate {
  private active = 0;
  private readonly waiters: GateWaiter[] = [];

  constructor(
    private readonly concurrency: number,
    private readonly maximumQueued: number
  ) {}

  acquire(timeoutSignal: AbortSignal, shutdownSignal: AbortSignal): Promise<GateAcquisition> {
    if (shutdownSignal.aborted) return Promise.resolve("shutdown");
    if (timeoutSignal.aborted) return Promise.resolve("timeout");
    if (this.active < this.concurrency) {
      this.active += 1;
      return Promise.resolve(this.releaseFunction());
    }
    if (this.waiters.length >= this.maximumQueued) return Promise.resolve("busy");
    return new Promise((resolve) => {
      let settled = false;
      const finish = (result: GateAcquisition): void => {
        if (settled) return;
        settled = true;
        const index = this.waiters.indexOf(waiter);
        if (index >= 0) this.waiters.splice(index, 1);
        waiter.cleanup();
        resolve(result);
      };
      const onTimeout = (): void => finish("timeout");
      const onShutdown = (): void => finish("shutdown");
      const waiter: GateWaiter = {
        cleanup(): void {
          timeoutSignal.removeEventListener("abort", onTimeout);
          shutdownSignal.removeEventListener("abort", onShutdown);
        },
        resolve: finish
      };
      this.waiters.push(waiter);
      timeoutSignal.addEventListener("abort", onTimeout, { once: true });
      shutdownSignal.addEventListener("abort", onShutdown, { once: true });
      if (shutdownSignal.aborted) onShutdown();
      else if (timeoutSignal.aborted) onTimeout();
    });
  }

  private releaseFunction(): () => void {
    let released = false;
    return (): void => {
      if (released) return;
      released = true;
      const next = this.waiters.shift();
      if (next === undefined) {
        this.active -= 1;
      } else {
        next.resolve(this.releaseFunction());
      }
    };
  }
}

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
    "access-control-allow-origin": "*",
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

  return new Promise<Buffer>((resolve, reject) => {
    const chunks: Buffer[] = [];
    let received = 0;
    let settled = false;

    const cleanup = (): void => {
      request.off("data", onData);
      request.off("end", onEnd);
      request.off("aborted", onAborted);
      request.off("error", onAborted);
      timeoutSignal.removeEventListener("abort", onTimeout);
      shutdownSignal.removeEventListener("abort", onShutdown);
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
      settle(() => reject(new BodyTimeoutError()));
    };
    const onShutdown = (): void => {
      request.pause();
      settle(() => reject(new BodyAbortedError()));
    };

    request.on("data", onData);
    request.once("end", onEnd);
    request.once("aborted", onAborted);
    request.once("error", onAborted);
    timeoutSignal.addEventListener("abort", onTimeout, { once: true });
    shutdownSignal.addEventListener("abort", onShutdown, { once: true });
    if (shutdownSignal.aborted) onShutdown();
    else if (timeoutSignal.aborted) onTimeout();
  });
}

async function streamRequestToFile(
  request: IncomingMessage,
  handle: FileHandle,
  maxBytes: number,
  timeoutSignal: AbortSignal,
  shutdownSignal: AbortSignal
): Promise<number> {
  const declaredLength = request.headers["content-length"];
  if (typeof declaredLength === "string") {
    if (!/^(?:0|[1-9]\d*)$/.test(declaredLength)) throw new BodyAbortedError();
    const parsedLength = Number(declaredLength);
    if (!Number.isSafeInteger(parsedLength) || parsedLength > maxBytes) throw new BodyTooLargeError();
  }
  if (request.aborted || request.destroyed) throw new BodyAbortedError();

  return new Promise<number>((resolve, reject) => {
    let received = 0;
    let settled = false;
    let requestedError: Error | undefined;
    let pendingWrite: Promise<void> = Promise.resolve();

    const cleanup = (): void => {
      request.off("data", onData);
      request.off("end", onEnd);
      request.off("aborted", onAborted);
      request.off("error", onAborted);
      timeoutSignal.removeEventListener("abort", onTimeout);
      shutdownSignal.removeEventListener("abort", onShutdown);
    };
    const settle = (operation: () => void): void => {
      if (settled) return;
      settled = true;
      cleanup();
      operation();
    };
    const rejectAfterPendingWrite = (error: Error): void => {
      if (requestedError !== undefined || settled) return;
      requestedError = error;
      request.pause();
      void pendingWrite.then(
        () => settle(() => reject(error)),
        (writeError: unknown) => settle(() => reject(writeError))
      );
    };
    const onData = (chunk: Buffer | string): void => {
      request.pause();
      const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
      received += bytes.byteLength;
      if (received > maxBytes) {
        rejectAfterPendingWrite(new BodyTooLargeError());
        return;
      }
      pendingWrite = pendingWrite.then(async () => {
        let offset = 0;
        while (offset < bytes.byteLength) {
          const result = await handle.write(bytes, offset, bytes.byteLength - offset, null);
          if (result.bytesWritten === 0) throw new Error("Export body spool write made no progress");
          offset += result.bytesWritten;
        }
      });
      void pendingWrite.then(
        () => {
          if (!settled && requestedError === undefined) request.resume();
        },
        (error: unknown) => settle(() => reject(error))
      );
    };
    const onEnd = (): void => {
      void pendingWrite.then(
        () => settle(() => resolve(received)),
        (error: unknown) => settle(() => reject(error))
      );
    };
    const onAborted = (): void => rejectAfterPendingWrite(new BodyAbortedError());
    const onTimeout = (): void => rejectAfterPendingWrite(new BodyTimeoutError());
    const onShutdown = (): void => rejectAfterPendingWrite(new BodyAbortedError());

    request.on("data", onData);
    request.once("end", onEnd);
    request.once("aborted", onAborted);
    request.once("error", onAborted);
    timeoutSignal.addEventListener("abort", onTimeout, { once: true });
    shutdownSignal.addEventListener("abort", onShutdown, { once: true });
    if (shutdownSignal.aborted) onShutdown();
    else if (timeoutSignal.aborted) onTimeout();
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

  recordExportAccepted(value: {
    contentHash: string;
    method: "POST";
    remoteAddress: "127.0.0.1";
    remoteFamily: "IPv4";
    requestId: string;
    route: "export";
  }): void {
    const line = Buffer.from(`${JSON.stringify({
      timestamp: new Date(this.now()).toISOString(),
      event: "export_accepted",
      requestId: value.requestId,
      method: value.method,
      route: value.route,
      status: 202,
      remoteAddress: value.remoteAddress,
      remoteFamily: value.remoteFamily,
      authenticated: true,
      contentHash: value.contentHash
    })}\n`, "utf8");
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
  private readonly createExportDeadlineSignal: () => AbortSignal;
  private readonly host: string;
  private readonly limits: BridgeLimits;
  private readonly log: StructuredLog;
  private readonly now: () => number;
  private readonly owner: BridgeOwner;
  private readonly port: number;
  private readonly queue: QueueStore;
  private readonly server: Server;
  private readonly workCheckpoint: BridgeWorkContext["checkpoint"];
  private readonly shutdownController = new AbortController();
  private readonly activeHandlers = new Set<Promise<void>>();
  private readonly exportBodyGate = new BoundedWorkGate(
    MAX_CONCURRENT_EXPORT_BODY_WORK,
    MAX_QUEUED_EXPORT_BODY_WORK
  );
  private activePairingReservations = 0;
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
      maxAggregateAssetBytes: validateIntegerLimit(
        "maxAggregateAssetBytes",
        configured.maxAggregateAssetBytes ?? LIMITS.maxAggregateAssetBytes
      ),
      maxAssetBytes: validateIntegerLimit(
        "maxAssetBytes",
        configured.maxAssetBytes ?? LIMITS.maxAssetBytes
      ),
      maxBodyBytes: validateIntegerLimit("maxBodyBytes", configured.maxBodyBytes ?? LIMITS.maxBodyBytes),
      maxControlBodyBytes: validateIntegerLimit(
        "maxControlBodyBytes",
        configured.maxControlBodyBytes ?? MAX_CONTROL_BODY_BYTES
      ),
      maxManifestBytes: validateIntegerLimit(
        "maxManifestBytes",
        configured.maxManifestBytes ?? LIMITS.maxManifestBytes
      ),
      maxLogBytes: validateIntegerLimit("maxLogBytes", configured.maxLogBytes ?? MAX_LOG_BYTES),
      requestTimeoutMs: validateIntegerLimit("requestTimeoutMs", configured.requestTimeoutMs ?? LIMITS.requestTimeoutMs),
      retentionMs: validateIntegerLimit("retentionMs", configured.retentionMs ?? RETENTION_MS)
    };
    this.auth = options.auth;
    this.createExportDeadlineSignal = options.createExportDeadlineSignal
      ?? (() => AbortSignal.timeout(this.limits.requestTimeoutMs));
    this.host = options.host;
    this.now = options.now ?? Date.now;
    this.port = options.port;
    this.queue = options.queue;
    this.workCheckpoint = options.workCheckpoint;
    if (this.queue.owner === undefined) throw new TypeError("Bridge queue requires lifecycle ownership");
    this.owner = this.queue.owner;
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
    if (request.method === "OPTIONS") {
      response.setHeader("access-control-allow-methods", allowedMethod ?? "");
      response.setHeader("access-control-allow-headers", "authorization, content-type");
      response.setHeader("access-control-max-age", "600");
      sendEmpty(response, 204);
      this.log.record(route, 204);
      return;
    }
    if (request.method !== allowedMethod) {
      response.setHeader("allow", allowedMethod ?? "");
      this.respondError(response, route, 405, "METHOD_NOT_ALLOWED", "The request method is not allowed for this route");
      return;
    }
    if (
      request.method === "POST" &&
      (route === "pair" || route === "reset") &&
      declaredBodyIsOversized(request, this.limits.maxControlBodyBytes)
    ) {
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
      const body = await this.readBodyOrRespond(
        request,
        response,
        route,
        this.limits.maxControlBodyBytes
      );
      if (body === undefined) return;
      if (body.byteLength !== 0) {
        this.respondError(response, route, 400, "RESET_BODY_NOT_EMPTY", "The reset request body must be empty");
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
    if (this.failedPairings.length + this.activePairingReservations >= MAX_PAIRING_FAILURES) {
      this.respondError(response, route, 429, "PAIRING_RATE_LIMITED", "Too many failed pairing attempts");
      terminateRequestAfterResponse(request, response);
      return;
    }
    this.activePairingReservations += 1;
    try {
      const body = await this.readBodyOrRespond(
        request,
        response,
        route,
        this.limits.maxControlBodyBytes
      );
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
      } catch (error) {
        if (!(error instanceof PairingCodeError)) throw error;
        this.failedPairings.push(this.now());
        this.respondError(response, route, 401, "PAIRING_FAILED", "The pairing code is invalid or expired");
      }
    } finally {
      this.activePairingReservations -= 1;
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
    if (
      request.method !== "POST" ||
      request.socket.remoteAddress !== "127.0.0.1" ||
      request.socket.remoteFamily !== "IPv4"
    ) {
      this.respondError(
        response,
        route,
        403,
        "LOOPBACK_REQUIRED",
        "The export request must use authenticated IPv4 loopback"
      );
      return;
    }
    const requestId = randomUUID();
    if (declaredBodyIsOversized(request, this.limits.maxBodyBytes)) {
      this.respondError(response, route, 413, "PAYLOAD_TOO_LARGE", "The request body exceeds the configured limit");
      terminateRequestAfterResponse(request, response);
      return;
    }
    const bodyDeadline = this.createExportDeadlineSignal();
    if (!(bodyDeadline instanceof AbortSignal)) {
      throw new TypeError("Export deadline factory must return an AbortSignal");
    }
    const bodyWork = await this.exportBodyGate.acquire(bodyDeadline, this.shutdownController.signal);
    if (bodyWork === "busy") {
      this.respondError(response, route, 503, "EXPORT_BUSY", "The export body processor is busy");
      terminateRequestAfterResponse(request, response);
      return;
    }
    if (bodyWork === "timeout") {
      this.respondError(response, route, 408, "REQUEST_TIMEOUT", "The request body was not received in time");
      terminateRequestAfterResponse(request, response);
      return;
    }
    if (bodyWork === "shutdown") {
      if (!request.destroyed) request.destroy();
      return;
    }
    const releaseBodyWork = bodyWork;
    const work: BridgeWorkContext = {
      deadlineSignal: bodyDeadline,
      onCancellation: releaseBodyWork,
      shutdownSignal: this.shutdownController.signal,
      ...(this.workCheckpoint === undefined ? {} : { checkpoint: this.workCheckpoint })
    };
    let observesProcessingCancellation = false;
    const releaseOnProcessingCancellation = (): void => releaseBodyWork();
    const observeProcessingCancellation = (): void => {
      if (observesProcessingCancellation) return;
      observesProcessingCancellation = true;
      bodyDeadline.addEventListener("abort", releaseOnProcessingCancellation, { once: true });
      this.shutdownController.signal.addEventListener("abort", releaseOnProcessingCancellation, { once: true });
      if (bodyDeadline.aborted || this.shutdownController.signal.aborted) releaseBodyWork();
    };
    const stopObservingProcessingCancellation = (): void => {
      if (!observesProcessingCancellation) return;
      observesProcessingCancellation = false;
      bodyDeadline.removeEventListener("abort", releaseOnProcessingCancellation);
      this.shutdownController.signal.removeEventListener("abort", releaseOnProcessingCancellation);
    };
    let spool: OwnedTemporaryFile | undefined;
    let streamedAssets: StreamedAssetFile[] = [];
    try {
      spool = await this.spoolBodyOrRespond(
        request,
        response,
        route,
        this.limits.maxBodyBytes,
        bodyDeadline,
        "The request body exceeds the configured limit"
      );
      if (spool === undefined) return;
      observeProcessingCancellation();
      let parsed: Awaited<ReturnType<typeof readStreamingPackage>>;
      try {
        parsed = await readStreamingPackage(spool, this.queue, this.owner, {
          limits: {
            maxAggregateAssetBytes: this.limits.maxAggregateAssetBytes,
            maxAssetBytes: this.limits.maxAssetBytes,
            maxBodyBytes: this.limits.maxBodyBytes,
            maxManifestBytes: this.limits.maxManifestBytes
          },
          work
        });
      } catch (error) {
        await this.removeSpooledBody(spool);
        spool = undefined;
        if (error instanceof StreamingPackageSyntaxError) {
          this.respondError(response, route, 400, "INVALID_JSON", "The request body must be valid JSON");
          return;
        }
        if (error instanceof StreamingPackageLimitError) {
          this.respondError(response, route, 413, "PAYLOAD_TOO_LARGE", "The request body exceeds the configured limit");
          return;
        }
        if (error instanceof StreamingPackageValidationError || error instanceof TypeError) {
          this.respondError(response, route, 422, "INVALID_PACKAGE", "The export package is invalid");
          return;
        }
        throw error;
      }
      streamedAssets = [...parsed.assets];
      await this.removeSpooledBody(spool);
      spool = undefined;
      const actualContentHash = await fingerprintStreamingPackage(
        parsed.package,
        streamedAssets,
        this.queue,
        { work }
      );
      if (actualContentHash !== parsed.package.contentHash) {
        await cleanupStreamedAssets(streamedAssets, this.queue, work);
        streamedAssets = [];
        this.respondError(response, route, 422, "CONTENT_HASH_MISMATCH", "The package fingerprint does not match its contents");
        return;
      }
      if (parsed.package.assets.some((asset, index) => asset.hash !== streamedAssets[index]?.hash)) {
        await cleanupStreamedAssets(streamedAssets, this.queue, work);
        streamedAssets = [];
        this.respondError(response, route, 422, "ASSET_HASH_MISMATCH", "An asset hash does not match its decoded bytes");
        return;
      }
      try {
        await this.queue.enqueueVerified(parsed.package, streamedAssets, { work });
      } catch (error) {
        if (error instanceof QueueConflictError) {
          await cleanupStreamedAssets(streamedAssets, this.queue, work);
          streamedAssets = [];
          this.respondError(response, route, 409, "QUEUE_DUPLICATE", "This package is already queued");
          return;
        }
        throw error;
      }
      await cleanupStreamedAssets(streamedAssets, this.queue, work);
      streamedAssets = [];
      sendJson(response, 202, { status: "accepted", contentHash: parsed.package.contentHash });
      this.log.recordExportAccepted({
        requestId,
        method: "POST",
        route,
        remoteAddress: "127.0.0.1",
        remoteFamily: "IPv4",
        contentHash: parsed.package.contentHash
      });
      this.log.record(route, 202);
    } catch (error) {
      if (error instanceof BridgeWorkDeadlineError || error instanceof BridgeWorkShutdownError) {
        releaseBodyWork();
        if (streamedAssets.length > 0) {
          await cleanupStreamedAssets(streamedAssets, this.queue, work);
          streamedAssets = [];
        }
        if (spool !== undefined) {
          await this.removeSpooledBody(spool);
          spool = undefined;
        }
        if (error instanceof BridgeWorkDeadlineError) {
          this.respondError(response, route, 408, "REQUEST_TIMEOUT", "The export request exceeded its processing deadline");
          terminateRequestAfterResponse(request, response);
        } else if (!request.destroyed) {
          request.destroy();
        }
        return;
      }
      throw error;
    } finally {
      try {
        if (streamedAssets.length > 0) await cleanupStreamedAssets(streamedAssets, this.queue, work);
      } finally {
        try {
          if (spool !== undefined) await this.removeSpooledBody(spool);
        } finally {
          stopObservingProcessingCancellation();
          releaseBodyWork();
        }
      }
    }
  }

  private async spoolBodyOrRespond(
    request: IncomingMessage,
    response: ServerResponse,
    route: string,
    maxBytes: number,
    timeoutSignal: AbortSignal,
    tooLargeMessage: string
  ): Promise<OwnedTemporaryFile | undefined> {
    try {
      return await this.spoolBody(request, maxBytes, timeoutSignal);
    } catch (error) {
      if (error instanceof BodyTooLargeError) {
        this.respondError(response, route, 413, "PAYLOAD_TOO_LARGE", tooLargeMessage);
        terminateRequestAfterResponse(request, response);
      } else if (error instanceof BodyTimeoutError) {
        this.respondError(response, route, 408, "REQUEST_TIMEOUT", "The request body was not received in time");
        terminateRequestAfterResponse(request, response);
      } else if (error instanceof BodyAbortedError) {
        if (!request.destroyed) request.destroy();
      } else {
        throw error;
      }
      return undefined;
    }
  }

  private async spoolBody(
    request: IncomingMessage,
    maxBytes: number,
    timeoutSignal: AbortSignal
  ): Promise<OwnedTemporaryFile> {
    const path = join(
      this.queue.paths.tmp,
      ownedHttpTemporaryFilename("http-body", this.owner, randomUUID())
    );
    let handle: FileHandle | undefined;
    let identity: Omit<OwnedTemporaryFile, "size"> | undefined;
    try {
      this.queue.assertHealthy();
      handle = await open(
        path,
        constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW,
        0o600
      );
      await handle.chmod(0o600);
      const opened = await handle.stat();
      if (!opened.isFile()) throw new Error("Export body spool is not a regular file");
      identity = {
        device: opened.dev,
        inode: opened.ino,
        kind: "http-body",
        owner: this.owner,
        path
      };
      this.queue.assertHealthy();
      const size = await streamRequestToFile(
        request,
        handle,
        maxBytes,
        timeoutSignal,
        this.shutdownController.signal
      );
      await handle.sync();
      const completed = await handle.stat();
      if (
        !completed.isFile() ||
        completed.dev !== identity.device ||
        completed.ino !== identity.inode ||
        completed.size !== size
      ) {
        throw new Error("Export body spool changed identity or size");
      }
      await handle.close();
      handle = undefined;
      return { ...identity, size };
    } catch (error) {
      const cleanupFailures: unknown[] = [];
      if (handle !== undefined) {
        if (identity === undefined) {
          try {
            const opened = await handle.stat();
            if (opened.isFile()) {
              identity = {
                device: opened.dev,
                inode: opened.ino,
                kind: "http-body",
                owner: this.owner,
                path
              };
            }
          } catch (identityError) {
            cleanupFailures.push(identityError);
            // Without a stable identity, retain the path rather than unlinking an unknown replacement.
          }
        }
        try {
          await handle.close();
        } catch (closeError) {
          cleanupFailures.push(closeError);
        }
      }
      if (identity !== undefined) {
        try {
          await this.removeSpooledBody({ ...identity, size: 0 });
        } catch (removeError) {
          cleanupFailures.push(removeError);
        }
      }
      if (cleanupFailures.length > 0) {
        throw new Error("Export body spool cleanup failed", {
          cause: new AggregateError([error, ...cleanupFailures])
        });
      }
      throw error;
    }
  }

  private async removeSpooledBody(spool: OwnedTemporaryFile): Promise<void> {
    this.queue.assertHealthy();
    let current: Awaited<ReturnType<typeof lstat>>;
    try {
      current = await lstat(spool.path);
    } catch (error) {
      throw error;
    }
    if (
      !current.isFile() ||
      current.isSymbolicLink() ||
      current.dev !== spool.device ||
      current.ino !== spool.inode
    ) {
      throw new Error("Export body spool changed before cleanup");
    }
    await unlink(spool.path);
    this.queue.assertHealthy();
    await this.queue.syncTemporaryDirectory();
  }

  private async readBodyOrRespond(
    request: IncomingMessage,
    response: ServerResponse,
    route: string,
    maxBytes = this.limits.maxBodyBytes
  ): Promise<Buffer | undefined> {
    try {
      return await readBoundedBody(
        request,
        maxBytes,
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
