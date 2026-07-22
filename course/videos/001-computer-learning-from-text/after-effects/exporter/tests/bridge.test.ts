import assert from "node:assert/strict";
import { createHash, randomBytes } from "node:crypto";
import { spawn } from "node:child_process";
import { chmod, mkdir, mkdtemp, readFile, readdir, rename, stat, symlink, utimes, writeFile } from "node:fs/promises";
import { createServer as createHttpServer, request as httpRequest } from "node:http";
import { tmpdir } from "node:os";
import { isAbsolute, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { AuthStore } from "../src/bridge/auth.ts";
import {
  acquireBridgeLifecycle,
  parseCliArgs,
  publishBridgeState,
  recoverBridgeStartupGuard,
  removeBridgeState,
  startBridgeCli,
  StatePublicationCleanupError,
  type BridgeOwner
} from "../src/bridge/cli.ts";
import { QueueStore } from "../src/bridge/queue.ts";
import { createBridgeServer, type BridgeServer } from "../src/bridge/server.ts";
import { contentFingerprintInput, type ExporterPackage, type RasterNode } from "../src/shared/contract.ts";
import { LIMITS } from "../src/shared/limits.ts";
import { makeValidPackage } from "./helpers/package.ts";

function pngAsset(value: ExporterPackage, bytes: Buffer): string {
  const hash = createHash("sha256").update(bytes).digest("hex");
  value.assets.push({
    hash,
    mimeType: "image/png",
    byteLength: bytes.byteLength,
    dataBase64: bytes.toString("base64")
  });
  const raster: RasterNode = {
    id: "raster-1",
    kind: "raster",
    name: "Raster_Fallback",
    x: 0,
    y: 0,
    width: 100,
    height: 100,
    rotation: 0,
    opacity: 1,
    assetHash: hash
  };
  value.frames[0]!.children.push(raster);
  return hash;
}

function fingerprint(value: ExporterPackage): ExporterPackage {
  value.contentHash = createHash("sha256").update(contentFingerprintInput(value)).digest("hex");
  return value;
}

interface StartedBridge {
  auth: AuthStore;
  base: string;
  bridge: BridgeServer;
  code: string;
  queue: QueueStore;
  root: string;
}

async function startBridge(
  t: test.TestContext,
  options: {
    maxBodyBytes?: number;
    maxJsonParseBytes?: number;
    maxLogBytes?: number;
    now?: () => number;
    requestTimeoutMs?: number;
  } = {}
): Promise<StartedBridge> {
  const root = await mkdtemp(join(tmpdir(), "video001-http-"));
  const now = options.now ?? Date.now;
  const auth = new AuthStore(now, randomBytes);
  const code = auth.createPairingCode();
  const queue = new QueueStore(root);
  const bridge = createBridgeServer({
    auth,
    queue,
    host: "127.0.0.1",
    port: 0,
    now,
    limits: {
      ...(options.maxBodyBytes === undefined ? {} : { maxBodyBytes: options.maxBodyBytes }),
      ...(options.maxJsonParseBytes === undefined ? {} : { maxJsonParseBytes: options.maxJsonParseBytes }),
      ...(options.maxLogBytes === undefined ? {} : { maxLogBytes: options.maxLogBytes }),
      ...(options.requestTimeoutMs === undefined ? {} : { requestTimeoutMs: options.requestTimeoutMs })
    }
  });
  const address = await bridge.start();
  t.after(async () => bridge.close());
  return { auth, base: `http://127.0.0.1:${address.port}`, bridge, code, queue, root };
}

async function pair(base: string, code: string): Promise<string> {
  const response = await fetch(`${base}/v1/pair`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ code })
  });
  assert.equal(response.status, 200);
  const body = await response.json() as { token: string };
  return body.token;
}

function assertSecurityHeaders(response: Response): void {
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  for (const name of response.headers.keys()) {
    assert.equal(name.startsWith("access-control-"), false, name);
  }
}

async function waitForPath(path: string, timeoutMs = 5_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      await stat(path);
      return;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    }
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  throw new Error(`Timed out waiting for ${path}`);
}

async function childExit(child: ReturnType<typeof spawn>): Promise<{ code: number | null; signal: NodeJS.Signals | null }> {
  return new Promise((resolve, reject) => {
    child.once("error", reject);
    child.once("exit", (code, signal) => resolve({ code, signal }));
  });
}

test("queue filenames derive only from hashes and become atomically visible", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-exporter-"));
  const queue = new QueueStore(root);
  const value = makeValidPackage();
  value.contentHash = "b".repeat(64);

  const result = await queue.enqueue(value);

  assert.equal(result.filename, `${"b".repeat(64)}.video001-ae.json`);
  assert.equal(result.path, join(root, "incoming", result.filename));
  assert.deepEqual(await readdir(join(root, "incoming")), [result.filename]);
  assert.deepEqual(await readdir(join(root, "tmp")), []);
  assert.match(await readFile(result.path, "utf8"), /"schemaVersion":"1.0.0"/);
});

test("queue directories and files are owner-only", async () => {
  const parent = await mkdtemp(join(tmpdir(), "video001-exporter-mode-"));
  const root = join(parent, "queue");
  const queue = new QueueStore(root);
  const result = await queue.enqueue(makeValidPackage());

  for (const directory of [root, "tmp", "incoming", "quarantine", "assets", "logs"].map((name) =>
    name === root ? root : join(root, name)
  )) {
    assert.equal((await stat(directory)).mode & 0o777, 0o700, directory);
  }
  assert.equal((await stat(result.path)).mode & 0o777, 0o600);
});

test("failed owner-record serialization cleans up newly acquired auth and enqueue locks", async () => {
  const invalidOwner = {
    version: 1,
    pid: process.pid,
    instanceId: "not-a-valid-instance-id"
  } as BridgeOwner;
  const authRoot = await mkdtemp(join(tmpdir(), "video001-invalid-auth-owner-"));
  await assert.rejects(
    AuthStore.open(join(authRoot, "auth.json"), Date.now, randomBytes, undefined, invalidOwner),
    /instance/i
  );
  assert.deepEqual(await readdir(authRoot), []);

  const queueRoot = await mkdtemp(join(tmpdir(), "video001-invalid-queue-owner-"));
  const queue = new QueueStore(queueRoot, invalidOwner);
  await assert.rejects(queue.enqueue(makeValidPackage()), /instance/i);
  assert.deepEqual(await readdir(join(queueRoot, "tmp")), []);
});

test("client-controlled names and malformed hashes cannot escape the queue root", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-exporter-path-"));
  const queue = new QueueStore(root);

  for (const hash of ["../escape", "A".repeat(64), "a".repeat(63), `${"a".repeat(64)}.png`]) {
    await assert.rejects(queue.writeAsset(hash, new Uint8Array([1])), /hash/i, hash);
  }
  assert.deepEqual((await readdir(root)).sort(), ["assets", "incoming", "logs", "quarantine", "tmp"]);
});

test("assets are verified, content-addressed, and stripped from queued JSON", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-exporter-asset-"));
  const queue = new QueueStore(root);
  const value = makeValidPackage();
  const bytes = Buffer.from("verified png bytes");
  const hash = pngAsset(value, bytes);

  const result = await queue.enqueue(value);
  const queued = JSON.parse(await readFile(result.path, "utf8")) as {
    assets: Array<Record<string, unknown>>;
  };
  const asset = queued.assets[0];

  assert.equal(Object.hasOwn(asset ?? {}, "dataBase64"), false);
  assert.equal(asset?.path, join(root, "assets", `${hash}.png`));
  assert.equal(isAbsolute(String(asset?.path)), true);
  assert.deepEqual(await readFile(String(asset?.path)), bytes);
  assert.equal((await stat(String(asset?.path))).mode & 0o777, 0o600);
  assert.deepEqual(await readdir(join(root, "tmp")), []);
});

test("asset byte lengths and SHA-256 hashes are verified before queue publication", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-exporter-invalid-asset-"));
  const queue = new QueueStore(root);
  const value = makeValidPackage();
  const bytes = Buffer.from("not the declared hash");
  pngAsset(value, bytes);
  value.assets[0]!.hash = "c".repeat(64);
  (value.frames[0]!.children.at(-1) as RasterNode).assetHash = "c".repeat(64);

  await assert.rejects(queue.enqueue(value), /sha-?256|hash/i);
  assert.deepEqual(await readdir(join(root, "incoming")), []);
  assert.deepEqual(await readdir(join(root, "assets")), []);
  assert.deepEqual(await readdir(join(root, "tmp")), []);

  const correctHash = createHash("sha256").update(bytes).digest("hex");
  await assert.rejects(queue.writeAsset(correctHash, bytes, bytes.byteLength + 1), /length/i);
  assert.deepEqual(await readdir(join(root, "assets")), []);
});

test("existing asset symlinks are rejected without touching their targets", async () => {
  const parent = await mkdtemp(join(tmpdir(), "video001-exporter-symlink-"));
  const root = join(parent, "queue");
  const queue = new QueueStore(root);
  const bytes = Buffer.from("external target");
  const hash = createHash("sha256").update(bytes).digest("hex");
  const external = join(parent, "external.png");
  await writeFile(external, bytes);
  await chmod(external, 0o644);
  await symlink(external, join(root, "assets", `${hash}.png`));

  await assert.rejects(queue.writeAsset(hash, bytes), /regular file|symbolic link/i);
  assert.equal((await stat(external)).mode & 0o777, 0o644);
  assert.deepEqual(await readFile(external), bytes);
});

test("replacing the assets directory with a symlink fails closed", async () => {
  const parent = await mkdtemp(join(tmpdir(), "video001-exporter-assets-swap-"));
  const root = join(parent, "queue");
  const outside = join(parent, "outside");
  const queue = new QueueStore(root);
  await mkdir(outside, { mode: 0o700 });
  await rename(join(root, "assets"), join(root, "assets-original"));
  await symlink(outside, join(root, "assets"), "dir");
  const bytes = Buffer.from("must remain inside queue root");
  const hash = createHash("sha256").update(bytes).digest("hex");

  await assert.rejects(queue.writeAsset(hash, bytes), /directory|identity|symlink|changed/i);
  assert.deepEqual(await readdir(outside), []);
});

test("replacing the queue root with a symlink fails closed", async () => {
  const parent = await mkdtemp(join(tmpdir(), "video001-exporter-root-swap-"));
  const root = join(parent, "queue");
  const outside = join(parent, "outside");
  const queue = new QueueStore(root);
  new QueueStore(outside);
  await rename(root, join(parent, "queue-original"));
  await symlink(outside, root, "dir");
  const bytes = Buffer.from("must not reach replacement root");
  const hash = createHash("sha256").update(bytes).digest("hex");

  await assert.rejects(queue.writeAsset(hash, bytes), /directory|identity|symlink|changed/i);
  assert.deepEqual(await readdir(join(outside, "assets")), []);
  assert.deepEqual(await readdir(join(outside, "tmp")), []);
});

test("duplicate package hashes are rejected without replacing the queued file", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-exporter-duplicate-"));
  const queue = new QueueStore(root);
  const value = makeValidPackage();
  const first = await queue.enqueue(value);
  const before = await readFile(first.path);

  value.exporterVersion = "different-content-same-hash";
  await assert.rejects(queue.enqueue(value), /already queued|duplicate/i);
  assert.deepEqual(await readFile(first.path), before);
  assert.deepEqual(await readdir(join(root, "tmp")), []);
});

test("concurrent duplicate enqueues publish exactly one package", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-exporter-concurrent-"));
  const queue = new QueueStore(root);
  const first = makeValidPackage();
  const second = makeValidPackage();
  second.exporterVersion = "different-content-same-hash";

  const results = await Promise.allSettled([queue.enqueue(first), queue.enqueue(second)]);

  assert.equal(results.filter((result) => result.status === "fulfilled").length, 1);
  const rejection = results.find((result) => result.status === "rejected");
  assert.match(String(rejection?.status === "rejected" ? rejection.reason : ""), /already queued|duplicate/i);
  assert.deepEqual(await readdir(join(root, "incoming")), [
    `${makeValidPackage().contentHash}.video001-ae.json`
  ]);
  assert.deepEqual(await readdir(join(root, "tmp")), []);
});

test("quarantine moves only hash-addressed packages and writes a redacted report", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-exporter-quarantine-"));
  const queue = new QueueStore(root);
  const result = await queue.enqueue(makeValidPackage());
  const secret = "Bearer highly-sensitive-token";
  const assetData = Buffer.from("embedded secret bytes").toString("base64");

  const quarantined = await queue.quarantine(
    makeValidPackage().contentHash,
    new Error(`Importer rejected ${secret} ${assetData}`)
  );

  assert.deepEqual(await readdir(join(root, "incoming")), []);
  assert.deepEqual(
    (await readdir(join(root, "quarantine"))).sort(),
    [quarantined.filename, quarantined.reportFilename].sort()
  );
  const report = await readFile(quarantined.reportPath, "utf8");
  assert.equal(report.includes(secret), false);
  assert.equal(report.includes(assetData), false);
  assert.equal(report.includes("stack"), false);
  assert.match(report, /PACKAGE_REJECTED/);
  assert.equal((await stat(quarantined.path)).mode & 0o777, 0o600);
  assert.equal((await stat(quarantined.reportPath)).mode & 0o777, 0o600);
  assert.deepEqual(await readdir(join(root, "tmp")), []);

  await assert.rejects(queue.quarantine("../escape", new Error(secret)), /hash/i);
});

test("bridge binds to IPv4 loopback and implements the authenticated export lifecycle", async (t) => {
  const { auth, base, bridge, code, root } = await startBridge(t);
  const address = bridge.address();
  assert.equal(address.address, "127.0.0.1");
  assert.equal(address.family, "IPv4");

  const health = await fetch(`${base}/health`);
  assert.equal(health.status, 200);
  assert.equal(health.headers.get("content-type"), "application/json; charset=utf-8");
  assert.deepEqual(await health.json(), { status: "ok", schemaMajor: 1 });
  assertSecurityHeaders(health);

  const value = fingerprint(makeValidPackage());
  const unauthorized = await fetch(`${base}/v1/export`, {
    method: "POST",
    headers: { "content-type": "application/vnd.video001.figma-ae+json" },
    body: JSON.stringify(value)
  });
  assert.equal(unauthorized.status, 401);
  assert.deepEqual(await unauthorized.json(), {
    error: { code: "UNAUTHORIZED", message: "A valid bearer token is required" }
  });
  assertSecurityHeaders(unauthorized);

  const token = await pair(base, code);
  const accepted = await fetch(`${base}/v1/export`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/vnd.video001.figma-ae+json"
    },
    body: JSON.stringify(value)
  });
  assert.equal(accepted.status, 202);
  assert.equal(accepted.headers.get("content-type"), "application/json; charset=utf-8");
  assert.deepEqual(await accepted.json(), { status: "accepted", contentHash: value.contentHash });
  assert.deepEqual(await readdir(join(root, "incoming")), [
    `${value.contentHash}.video001-ae.json`
  ]);

  const reset = await fetch(`${base}/v1/reset`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}` }
  });
  assert.equal(reset.status, 204);
  assert.equal(reset.headers.get("content-type"), null);
  assertSecurityHeaders(reset);
  assert.equal(auth.authenticateBearer(`Bearer ${token}`), false);
});

test("bridge rejects non-loopback hosts and ports outside the TCP range", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-host-"));
  const auth = new AuthStore();
  const queue = new QueueStore(root);
  for (const host of ["localhost", "::1", "0.0.0.0", "127.0.0.2"]) {
    assert.throws(() => createBridgeServer({ auth, queue, host, port: 0 }), /127\.0\.0\.1|loopback/i, host);
  }
  for (const port of [-1, 65_536, 1.5, Number.NaN]) {
    assert.throws(() => createBridgeServer({ auth, queue, host: "127.0.0.1", port }), /port/i, String(port));
  }
});

test("bridge uses exact routes, methods, media types, and JSON error envelopes", async (t) => {
  const { base, code } = await startBridge(t);
  const token = await pair(base, code);
  const cases: Array<{
    code: string;
    init?: RequestInit;
    path: string;
    status: number;
  }> = [
    { path: "/health/", status: 404, code: "NOT_FOUND" },
    { path: "/health?details=1", status: 404, code: "NOT_FOUND" },
    { path: "/v1/missing", status: 404, code: "NOT_FOUND" },
    { path: "/health", init: { method: "POST" }, status: 405, code: "METHOD_NOT_ALLOWED" },
    { path: "/v1/export", init: { method: "GET" }, status: 405, code: "METHOD_NOT_ALLOWED" },
    {
      path: "/v1/pair",
      init: { method: "POST", headers: { "content-type": "text/plain" }, body: "{}" },
      status: 415,
      code: "UNSUPPORTED_MEDIA_TYPE"
    },
    {
      path: "/v1/export",
      init: {
        method: "POST",
        headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
        body: JSON.stringify(fingerprint(makeValidPackage()))
      },
      status: 415,
      code: "UNSUPPORTED_MEDIA_TYPE"
    }
  ];

  for (const entry of cases) {
    const response = await fetch(`${base}${entry.path}`, entry.init);
    assert.equal(response.status, entry.status, entry.path);
    const body = await response.json() as { error?: { code?: string; message?: string } };
    assert.deepEqual(Object.keys(body), ["error"]);
    assert.equal(body.error?.code, entry.code);
    assert.equal(typeof body.error?.message, "string");
    assertSecurityHeaders(response);
  }
});

test("bridge enforces streaming body limits before waiting for a slow sender", async (t) => {
  const { base, code } = await startBridge(t, { maxBodyBytes: 1_024 });
  const token = await pair(base, code);
  const unauthorized = await fetch(`${base}/v1/export`, {
    method: "POST",
    headers: {
      "content-length": "2048",
      "content-type": "application/vnd.video001.figma-ae+json"
    },
    body: "x".repeat(2_048)
  });
  assert.equal(unauthorized.status, 401);
  const startedAt = Date.now();
  const status = await new Promise<number>((resolve, reject) => {
    const request = httpRequest(`${base}/v1/export`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${token}`,
        "content-length": "2048",
        "content-type": "application/vnd.video001.figma-ae+json"
      }
    }, (response) => {
      response.resume();
      response.once("end", () => resolve(response.statusCode ?? 0));
    });
    request.once("error", reject);
    request.write("{");
  });
  assert.equal(status, 413);
  assert.ok(Date.now() - startedAt < 1_000, "server waited for the oversized body");

  const response = await fetch(`${base}/v1/pair`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: "x".repeat(1_025)
  });
  assert.equal(response.status, 413);
  assert.deepEqual(await response.json(), {
    error: { code: "PAYLOAD_TOO_LARGE", message: "The request body exceeds the configured limit" }
  });
});

test("bridge times out slow bodies and survives client-aborted bodies", async (t) => {
  const { base, code, root } = await startBridge(t, { requestTimeoutMs: 50 });
  const timeoutStatus = await new Promise<number>((resolve, reject) => {
    const request = httpRequest(`${base}/v1/pair`, {
      method: "POST",
      headers: { "content-type": "application/json", "transfer-encoding": "chunked" }
    }, (response) => {
      response.resume();
      response.once("end", () => resolve(response.statusCode ?? 0));
    });
    request.once("error", reject);
    request.write("{");
  });
  assert.equal(timeoutStatus, 408);

  const token = await pair(base, code);
  const exportTimeoutStatus = await new Promise<number>((resolve, reject) => {
    const request = httpRequest(`${base}/v1/export`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${token}`,
        "content-type": "application/vnd.video001.figma-ae+json",
        "transfer-encoding": "chunked"
      }
    }, (response) => {
      response.resume();
      response.once("end", () => resolve(response.statusCode ?? 0));
    });
    request.once("error", reject);
    request.write("{");
  });
  assert.equal(exportTimeoutStatus, 408);
  assert.deepEqual(await readdir(join(root, "tmp")), []);

  await new Promise<void>((resolve) => {
    const request = httpRequest(`${base}/v1/pair`, {
      method: "POST",
      headers: { "content-type": "application/json", "transfer-encoding": "chunked" }
    });
    request.once("error", () => resolve());
    request.write("{\"code\":\"");
    request.destroy();
    setTimeout(resolve, 100);
  });
  const health = await fetch(`${base}/health`);
  assert.equal(health.status, 200);
});

test("graceful close waits for an accepted export handler to finish", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-graceful-close-"));
  const auth = new AuthStore(Date.now, randomBytes);
  const code = auth.createPairingCode();
  const queue = new QueueStore(root);
  const enqueue = queue.enqueue.bind(queue);
  let markEntered: (() => void) | undefined;
  let releaseEnqueue: (() => void) | undefined;
  const entered = new Promise<void>((resolve) => { markEntered = resolve; });
  const released = new Promise<void>((resolve) => { releaseEnqueue = resolve; });
  queue.enqueue = async (value: unknown) => {
    markEntered?.();
    await released;
    return enqueue(value);
  };
  const bridge = createBridgeServer({ auth, queue, host: "127.0.0.1", port: 0 });
  const address = await bridge.start();
  const base = `http://127.0.0.1:${address.port}`;
  const token = await pair(base, code);
  const request = fetch(`${base}/v1/export`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/vnd.video001.figma-ae+json"
    },
    body: JSON.stringify(fingerprint(makeValidPackage()))
  }).catch(() => undefined);
  await entered;
  let closed = false;
  const closing = bridge.close().then(() => { closed = true; });
  await new Promise((resolve) => setTimeout(resolve, 25));
  assert.equal(closed, false);
  releaseEnqueue?.();
  await closing;
  await request;
  assert.equal((await readdir(join(root, "incoming"))).length, 1);
});

test("bridge returns distinct validation, fingerprint, asset, and duplicate failures", async (t) => {
  const { base, code } = await startBridge(t);
  const token = await pair(base, code);
  const send = async (value: unknown): Promise<Response> => fetch(`${base}/v1/export`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/vnd.video001.figma-ae+json"
    },
    body: JSON.stringify(value)
  });

  const malformed = await fetch(`${base}/v1/export`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/vnd.video001.figma-ae+json"
    },
    body: "{"
  });
  assert.equal(malformed.status, 400);
  assert.equal((await malformed.json() as { error: { code: string } }).error.code, "INVALID_JSON");

  const invalid = await send({ ...makeValidPackage(), schemaVersion: "2.0.0" });
  assert.equal(invalid.status, 422);
  assert.equal((await invalid.json() as { error: { code: string } }).error.code, "INVALID_PACKAGE");

  const mismatch = await send(makeValidPackage());
  assert.equal(mismatch.status, 422);
  assert.equal((await mismatch.json() as { error: { code: string } }).error.code, "CONTENT_HASH_MISMATCH");

  const badAsset = makeValidPackage();
  pngAsset(badAsset, Buffer.from("verified body"));
  badAsset.assets[0]!.hash = "c".repeat(64);
  (badAsset.frames[0]!.children.at(-1) as RasterNode).assetHash = "c".repeat(64);
  fingerprint(badAsset);
  const assetMismatch = await send(badAsset);
  assert.equal(assetMismatch.status, 422);
  assert.equal((await assetMismatch.json() as { error: { code: string } }).error.code, "ASSET_HASH_MISMATCH");

  const valid = fingerprint(makeValidPackage());
  assert.equal((await send(valid)).status, 202);
  const duplicate = await send(valid);
  assert.equal(duplicate.status, 409);
  assert.deepEqual(await duplicate.json(), {
    error: { code: "QUEUE_DUPLICATE", message: "This package is already queued" }
  });
});

test("pairing rate limit is global, rolling, and resets after success", async (t) => {
  let now = 100_000;
  const { auth, base, code } = await startBridge(t, { now: () => now });
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const response = await fetch(`${base}/v1/pair`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ code: "999999" })
    });
    assert.equal(response.status, 401, `failure ${attempt + 1}`);
  }
  const limited = await fetch(`${base}/v1/pair`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ code })
  });
  assert.equal(limited.status, 429);
  assert.deepEqual(await limited.json(), {
    error: { code: "PAIRING_RATE_LIMITED", message: "Too many failed pairing attempts" }
  });

  now += 60_001;
  assert.equal(Buffer.from(await pair(base, code), "base64url").byteLength, 32);
  const nextCode = auth.createPairingCode();
  void nextCode;
  const afterReset = await fetch(`${base}/v1/pair`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ code: "999999" })
  });
  assert.equal(afterReset.status, 401);
});

test("parallel slow pairing requests reserve the global failure budget", async (t) => {
  let now = 200_000;
  const { base, code } = await startBridge(t, { now: () => now });
  const requests: Array<ReturnType<typeof httpRequest>> = [];
  const responses = Array.from({ length: 6 }, () => new Promise<number>((resolve, reject) => {
    const request = httpRequest(`${base}/v1/pair`, {
      method: "POST",
      headers: { "content-type": "application/json", "transfer-encoding": "chunked" }
    }, (response) => {
      response.resume();
      response.once("end", () => resolve(response.statusCode ?? 0));
    });
    request.once("error", reject);
    request.write('{"code":"999');
    requests.push(request);
  }));
  await new Promise((resolve) => setTimeout(resolve, 25));
  for (const request of requests) request.end('999"}');

  const statuses = await Promise.all(responses);
  assert.equal(statuses.filter((status) => status === 401).length, 5, statuses.join(","));
  assert.equal(statuses.filter((status) => status === 429).length, 1, statuses.join(","));

  now += 60_001;
  await pair(base, code);
  const afterSuccess = await fetch(`${base}/v1/pair`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ code: "999999" })
  });
  assert.equal(afterSuccess.status, 401);
});

test("pairing bodies use a tiny cap independent from the export body limit", async (t) => {
  const { base } = await startBridge(t, { maxBodyBytes: 64 * 1024 });
  const response = await fetch(`${base}/v1/pair`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: "x".repeat(1_025)
  });

  assert.equal(response.status, 413);
  assert.equal((await response.json() as { error: { code: string } }).error.code, "PAYLOAD_TOO_LARGE");
});

test("pairing operational failures map to generic 500 without leaking the failure", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "video001-pair-operational-failure-"));
  const secret = "Bearer operational-secret-in-error";
  let randomCalls = 0;
  const auth = new AuthStore(Date.now, () => {
    randomCalls += 1;
    if (randomCalls === 1) return Buffer.alloc(32, 91);
    throw new Error(`random source unavailable ${secret}`);
  });
  const code = auth.createPairingCode();
  const queue = new QueueStore(root);
  const bridge = createBridgeServer({ auth, queue, host: "127.0.0.1", port: 0 });
  const address = await bridge.start();
  t.after(async () => bridge.close());
  const base = `http://127.0.0.1:${address.port}`;

  const attempt = async (): Promise<Response> => fetch(`${base}/v1/pair`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ code })
  });

  const response = await attempt();
  assert.equal(response.status, 500);
  assert.deepEqual(await response.json(), {
    error: { code: "INTERNAL_ERROR", message: "The bridge could not process the request" }
  });
  const consumed = await attempt();
  assert.equal(consumed.status, 401);
  assert.deepEqual(await consumed.json(), {
    error: { code: "PAIRING_FAILED", message: "The pairing code is invalid or expired" }
  });
  await bridge.flushLogs();
  const contents = await Promise.all(
    (await readdir(join(root, "logs"))).filter((name) => name.startsWith("bridge")).map((name) =>
      readFile(join(root, "logs", name), "utf8")
    )
  );
  assert.equal(contents.join("\n").includes(secret), false);
});

test("unexpected pairing storage failures are never downgraded to authentication failures", async (t) => {
  const { auth, base, code } = await startBridge(t);
  auth.exchangePairingCode = () => {
    throw new Error("injected auth lock/write/fsync failure");
  };

  const response = await fetch(`${base}/v1/pair`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ code })
  });
  assert.equal(response.status, 500);
  assert.deepEqual(await response.json(), {
    error: { code: "INTERNAL_ERROR", message: "The bridge could not process the request" }
  });
});

test("reset consumes an empty body before revoking and rejects oversized chunked input", async (t) => {
  const { auth, base, code } = await startBridge(t);
  const token = await pair(base, code);
  const status = await new Promise<number>((resolve, reject) => {
    const request = httpRequest(`${base}/v1/reset`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${token}`,
        "content-type": "application/octet-stream",
        "transfer-encoding": "chunked"
      }
    }, (response) => {
      response.resume();
      response.once("end", () => resolve(response.statusCode ?? 0));
    });
    request.once("error", reject);
    request.end("x".repeat(1_025));
  });

  assert.equal(status, 413);
  assert.equal(auth.authenticateBearer(`Bearer ${token}`), true);

  const nonEmpty = await fetch(`${base}/v1/reset`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}` },
    body: "x"
  });
  assert.equal(nonEmpty.status, 400);
  assert.equal(auth.authenticateBearer(`Bearer ${token}`), true);

  const reset = await fetch(`${base}/v1/reset`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}` },
    body: ""
  });
  assert.equal(reset.status, 204);
  assert.equal(auth.authenticateBearer(`Bearer ${token}`), false);
});

test("authenticated exports spool privately, parse below a hard cap, and clean temporary bodies", async (t) => {
  const value = fingerprint(makeValidPackage());
  const body = JSON.stringify(value);
  const { base, code, root } = await startBridge(t, {
    maxBodyBytes: Buffer.byteLength(body) + 1_024,
    maxJsonParseBytes: Buffer.byteLength(body) - 1
  });
  const token = await pair(base, code);

  const result = await new Promise<{ body: unknown; status: number }>((resolve, reject) => {
    const request = httpRequest(`${base}/v1/export`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${token}`,
        "content-type": "application/vnd.video001.figma-ae+json",
        "transfer-encoding": "chunked"
      }
    }, (response) => {
      let responseBody = "";
      response.setEncoding("utf8");
      response.on("data", (chunk: string) => { responseBody += chunk; });
      response.once("end", () => resolve({
        body: JSON.parse(responseBody) as unknown,
        status: response.statusCode ?? 0
      }));
    });
    request.once("error", reject);
    request.end(body);
  });

  assert.equal(result.status, 413);
  assert.deepEqual(result.body, {
    error: { code: "PAYLOAD_TOO_LARGE", message: "The request body exceeds the safe JSON parsing limit" }
  });
  assert.deepEqual(await readdir(join(root, "tmp")), []);
  assert.deepEqual(await readdir(join(root, "incoming")), []);
});

test("export body processing is globally single-flight and uses a mode-0600 spool", async (t) => {
  const { auth, base, code, root } = await startBridge(t);
  const token = await pair(base, code);
  const first = fingerprint(makeValidPackage());
  const second = makeValidPackage();
  second.exporterVersion = "second-concurrent-export";
  fingerprint(second);
  const third = makeValidPackage();
  third.exporterVersion = "third-concurrent-export";
  fingerprint(third);
  const send = (value: ExporterPackage): Promise<Response> => fetch(`${base}/v1/export`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/vnd.video001.figma-ae+json"
    },
    body: JSON.stringify(value)
  });

  const firstBody = JSON.stringify(first);
  let resolveFirstResponse: ((status: number) => void) | undefined;
  let rejectFirstResponse: ((error: unknown) => void) | undefined;
  const firstResponse = new Promise<number>((resolve, reject) => {
    resolveFirstResponse = resolve;
    rejectFirstResponse = reject;
  });
  const firstRequest = httpRequest(`${base}/v1/export`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/vnd.video001.figma-ae+json",
      "transfer-encoding": "chunked"
    }
  }, (response) => {
    response.resume();
    response.once("end", () => resolveFirstResponse?.(response.statusCode ?? 0));
  });
  firstRequest.once("error", (error) => rejectFirstResponse?.(error));
  t.after(() => { if (!firstRequest.destroyed) firstRequest.destroy(); });
  const split = Math.floor(firstBody.length / 2);
  firstRequest.write(firstBody.slice(0, split));

  const spoolDeadline = Date.now() + 2_000;
  let names: string[] = [];
  do {
    names = await readdir(join(root, "tmp"));
    if (names.some((name) => name.startsWith(".http-body."))) break;
    await new Promise((resolve) => setTimeout(resolve, 5));
  } while (Date.now() < spoolDeadline);
  const spools = names.filter((name) => name.startsWith(".http-body.") && name.endsWith(".tmp"));
  assert.equal(spools.length, 1, names.join(","));
  assert.equal((await stat(join(root, "tmp", spools[0]!))).mode & 0o777, 0o600);

  let secondAuthenticated = false;
  const authenticate = auth.authenticateBearer.bind(auth);
  auth.authenticateBearer = (authorization: string | undefined) => {
    const result = authenticate(authorization);
    if (result) secondAuthenticated = true;
    return result;
  };
  const secondRequest = send(second);
  const deadline = Date.now() + 2_000;
  while (!secondAuthenticated && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  assert.equal(secondAuthenticated, true);
  await new Promise((resolve) => setTimeout(resolve, 25));
  assert.equal((await readdir(join(root, "tmp"))).filter((name) => name.startsWith(".http-body.")).length, 1);

  const busy = await send(third);
  assert.equal(busy.status, 503);
  assert.equal((await busy.json() as { error: { code: string } }).error.code, "EXPORT_BUSY");

  firstRequest.end(firstBody.slice(split));
  const secondResponse = await secondRequest;
  assert.deepEqual([await firstResponse, secondResponse.status], [202, 202]);
  assert.deepEqual(await readdir(join(root, "tmp")), []);
  assert.equal((await readdir(join(root, "incoming"))).length, 2);
});

test("a queued export body deadline frees its bounded waiter", async (t) => {
  const { base, code, queue } = await startBridge(t, { requestTimeoutMs: 75 });
  const token = await pair(base, code);
  const enqueue = queue.enqueue.bind(queue);
  let entered = 0;
  let markFirstEntered: (() => void) | undefined;
  let releaseFirst: (() => void) | undefined;
  const firstEntered = new Promise<void>((resolve) => { markFirstEntered = resolve; });
  const firstReleased = new Promise<void>((resolve) => { releaseFirst = resolve; });
  t.after(() => releaseFirst?.());
  queue.enqueue = async (value: unknown) => {
    entered += 1;
    if (entered === 1) {
      markFirstEntered?.();
      await firstReleased;
    }
    return enqueue(value);
  };
  const send = (label: string): Promise<Response> => {
    const value = makeValidPackage();
    value.exporterVersion = label;
    fingerprint(value);
    return fetch(`${base}/v1/export`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${token}`,
        "content-type": "application/vnd.video001.figma-ae+json"
      },
      body: JSON.stringify(value)
    });
  };

  const first = send("deadline-first");
  await firstEntered;
  const second = send("deadline-second");
  const secondStatus = await Promise.race([
    second.then((response) => response.status),
    new Promise<number>((resolve) => setTimeout(() => resolve(0), 500))
  ]);
  if (secondStatus !== 408) {
    releaseFirst?.();
    await Promise.allSettled([first, second]);
  }
  assert.equal(secondStatus, 408);

  const third = send("deadline-third");
  await new Promise((resolve) => setTimeout(resolve, 25));
  releaseFirst?.();
  assert.deepEqual((await Promise.all([first, third])).map((response) => response.status), [202, 202]);
});

test("bridge body readers use Node 20-compatible abort composition", async () => {
  const source = await readFile(fileURLToPath(new URL("../src/bridge/server.ts", import.meta.url)), "utf8");
  assert.equal(source.includes("AbortSignal.any"), false);
});

test("startup retention and structured log rotation are deterministic and redacted", async (t) => {
  let now = Date.UTC(2026, 6, 22, 12);
  const root = await mkdtemp(join(tmpdir(), "video001-retention-"));
  const queue = new QueueStore(root);
  const oldQuarantine = join(root, "quarantine", "old.error.json");
  const freshQuarantine = join(root, "quarantine", "fresh.error.json");
  const oldLog = join(root, "logs", "old.log");
  const freshLog = join(root, "logs", "fresh.log");
  for (const path of [oldQuarantine, freshQuarantine, oldLog, freshLog]) await writeFile(path, "fixture", { mode: 0o600 });
  const oldSeconds = (now - 7 * 24 * 60 * 60_000 - 1) / 1_000;
  const freshSeconds = (now - 7 * 24 * 60 * 60_000 + 1) / 1_000;
  await utimes(oldQuarantine, oldSeconds, oldSeconds);
  await utimes(oldLog, oldSeconds, oldSeconds);
  await utimes(freshQuarantine, freshSeconds, freshSeconds);
  await utimes(freshLog, freshSeconds, freshSeconds);

  const auth = new AuthStore(() => now, randomBytes);
  const code = auth.createPairingCode();
  const bridge = createBridgeServer({
    auth,
    queue,
    host: "127.0.0.1",
    port: 0,
    now: () => now,
    limits: { maxLogBytes: 256 }
  });
  const address = await bridge.start();
  t.after(async () => bridge.close());
  assert.deepEqual((await readdir(join(root, "quarantine"))).sort(), ["fresh.error.json"]);
  const afterPrune = await readdir(join(root, "logs"));
  assert.equal(afterPrune.includes("old.log"), false);
  assert.equal(afterPrune.includes("fresh.log"), true);

  const base = `http://127.0.0.1:${address.port}`;
  const secret = `Bearer ${"s".repeat(43)}`;
  for (let index = 0; index < 8; index += 1) {
    now += 1;
    const response = await fetch(`${base}/v1/export`, {
      method: "POST",
      headers: {
        authorization: secret,
        "content-type": "application/vnd.video001.figma-ae+json"
      },
      body: JSON.stringify({ token: secret, dataBase64: Buffer.from("asset secret").toString("base64") })
    });
    assert.equal(response.status, 401);
  }
  void code;
  await bridge.flushLogs();
  const logFiles = (await readdir(join(root, "logs"))).filter((name) => name.startsWith("bridge"));
  assert.ok(logFiles.length >= 2, logFiles.join(", "));
  for (const filename of logFiles) {
    const path = join(root, "logs", filename);
    assert.ok((await stat(path)).size <= 256, filename);
    const contents = await readFile(path, "utf8");
    assert.equal(contents.includes(secret), false);
    assert.equal(contents.includes("dataBase64"), false);
    assert.equal(contents.includes("asset secret"), false);
    for (const line of contents.trim().split("\n")) {
      if (line.length > 0) assert.doesNotThrow(() => JSON.parse(line));
    }
  }
});

test("retention fails closed without deleting through a swapped log-directory symlink", async () => {
  const parent = await mkdtemp(join(tmpdir(), "video001-retention-swap-"));
  const root = join(parent, "queue");
  const outside = join(parent, "outside");
  const queue = new QueueStore(root);
  await mkdir(outside, { mode: 0o700 });
  const external = join(outside, "external.log");
  await writeFile(external, "must survive", { mode: 0o600 });
  await utimes(external, 1, 1);
  await rename(join(root, "logs"), join(root, "logs-original"));
  await symlink(outside, join(root, "logs"), "dir");
  const auth = new AuthStore();
  const bridge = createBridgeServer({ auth, queue, host: "127.0.0.1", port: 0 });

  await assert.rejects(bridge.start(), /directory|identity|symlink|changed/i);
  assert.equal(await readFile(external, "utf8"), "must survive");
});

test("CLI arguments are strict and state publication/removal is durable and owner-only", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-cli-state-"));
  assert.deepEqual(parseCliArgs(["--root", root, "--port", "0"]), { root, port: 0 });
  for (const argv of [
    ["--root", "relative", "--port", "1234"],
    ["--root", root],
    ["--port", "1234"],
    ["--root", root, "--port", "-1"],
    ["--root", root, "--port", "65536"],
    ["--root", root, "--port", "1.5"],
    ["--root", root, "--port", "0", "--host", "127.0.0.1"],
    ["--root", root, "--root", root, "--port", "0"]
  ]) assert.throws(() => parseCliArgs(argv), /argument|root|port/i, argv.join(" "));

  const syncs: string[] = [];
  const state = {
    pid: 4321,
    port: 54321,
    pairingCode: "123456",
    pairingExpiresAt: 999_999
  };
  await publishBridgeState(root, state, (path) => { syncs.push(path); });
  const statePath = join(root, "state.json");
  assert.deepEqual(JSON.parse(await readFile(statePath, "utf8")), state);
  assert.equal((await stat(statePath)).mode & 0o777, 0o600);
  assert.deepEqual(syncs, [root]);

  await removeBridgeState(root, state.pid, (path) => { syncs.push(path); });
  await assert.rejects(readFile(statePath), /ENOENT/);
  assert.deepEqual(syncs, [root, root]);
});

test("failed state-directory fsync removes the renamed state before a restart", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-cli-state-fsync-failure-"));
  const firstOwner = owner(9_101, "91019101-9101-4101-8101-910191019101");
  const lifecycle = await acquireBridgeLifecycle(root, { owner: firstOwner });
  let syncCalls = 0;
  try {
    await assert.rejects(
      publishBridgeState(root, {
        pid: firstOwner.pid,
        port: 54_321,
        pairingCode: "123456",
        pairingExpiresAt: 999_999
      }, () => {
        syncCalls += 1;
        if (syncCalls === 1) throw new Error("injected state parent fsync failure");
      }),
      /injected state parent fsync failure/
    );
  } finally {
    await lifecycle.release();
  }

  assert.equal(syncCalls, 2);
  await assert.rejects(readFile(join(root, "state.json")), /ENOENT/);
  const restarted = await acquireBridgeLifecycle(root, {
    owner: owner(9_102, "91029102-9102-4102-8102-910291029102")
  });
  await restarted.release();
});

test("state cleanup never unlinks a replacement and reports lifecycle retention", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-cli-state-replacement-"));
  const statePath = join(root, "state.json");
  const displacedPath = join(root, "displaced-state.json");
  const replacement = JSON.stringify({ replacement: true });
  let firstSync = true;
  await assert.rejects(
    publishBridgeState(root, {
      pid: 9_201,
      port: 54_321,
      pairingCode: "123456",
      pairingExpiresAt: 999_999
    }, async () => {
      if (!firstSync) return;
      firstSync = false;
      await rename(statePath, displacedPath);
      await writeFile(statePath, replacement, { mode: 0o600 });
      throw new Error("injected replacement race");
    }),
    (error: unknown) => error instanceof StatePublicationCleanupError
  );
  assert.equal(await readFile(statePath, "utf8"), replacement);
  assert.equal((await stat(displacedPath)).isFile(), true);

  const retainedRoot = await mkdtemp(join(tmpdir(), "video001-cli-state-retained-lifecycle-"));
  let syncCalls = 0;
  await assert.rejects(
    startBridgeCli(["--root", retainedRoot, "--port", "0"], {
      stateDirectorySync: () => {
        syncCalls += 1;
        throw new Error("injected repeated directory fsync failure");
      }
    }),
    (error: unknown) => error instanceof StatePublicationCleanupError
  );
  assert.equal(syncCalls, 2);
  const retained = JSON.parse(await readFile(join(retainedRoot, ".bridge-lifecycle.json"), "utf8")) as BridgeOwner;
  assert.equal(retained.pid, process.pid);
  const recovered = await acquireBridgeLifecycle(retainedRoot, {
    owner: owner(9_202, "92029202-9202-4202-8202-920292029202"),
    probeProcess: (pid) => pid === retained.pid ? "dead" : "ambiguous"
  });
  await recovered.release();
});

test("CLI handles SIGTERM cleanly and reports bind failures without secrets or stacks", async (t) => {
  const cliPath = fileURLToPath(new URL("../src/bridge/cli.ts", import.meta.url));
  const root = await mkdtemp(join(tmpdir(), "video001-cli-signal-"));
  const child = spawn(process.execPath, ["--import", "tsx", cliPath, "--root", root, "--port", "0"], {
    cwd: process.cwd(),
    stdio: ["ignore", "pipe", "pipe"]
  });
  let standardError = "";
  child.stderr?.setEncoding("utf8");
  child.stderr?.on("data", (chunk: string) => { standardError += chunk; });
  const exit = childExit(child);
  await waitForPath(join(root, "state.json"));
  assert.equal(child.kill("SIGTERM"), true);
  assert.deepEqual(await exit, { code: 0, signal: null });
  assert.equal(standardError, "");
  await assert.rejects(stat(join(root, "state.json")), /ENOENT/);
  await assert.rejects(stat(join(root, ".bridge-lifecycle.json")), /ENOENT/);

  const blocker = createHttpServer();
  await new Promise<void>((resolve, reject) => {
    blocker.once("error", reject);
    blocker.listen(0, "127.0.0.1", resolve);
  });
  t.after(() => new Promise<void>((resolve, reject) => blocker.close((error) => error === undefined ? resolve() : reject(error))));
  const blockerAddress = blocker.address();
  if (blockerAddress === null || typeof blockerAddress === "string") throw new Error("expected TCP blocker address");
  const failedRoot = await mkdtemp(join(tmpdir(), "video001-cli-bind-"));
  const failed = spawn(
    process.execPath,
    ["--import", "tsx", cliPath, "--root", failedRoot, "--port", String(blockerAddress.port)],
    { cwd: process.cwd(), stdio: ["ignore", "pipe", "pipe"] }
  );
  let failureOutput = "";
  failed.stderr?.setEncoding("utf8");
  failed.stderr?.on("data", (chunk: string) => { failureOutput += chunk; });
  assert.deepEqual(await childExit(failed), { code: 1, signal: null });
  assert.equal(failureOutput, '{"event":"bridge_failed","code":"BRIDGE_FAILURE"}\n');
  assert.equal(failureOutput.includes(failedRoot), false);
  assert.equal(failureOutput.toLowerCase().includes("stack"), false);
  await assert.rejects(stat(join(failedRoot, "state.json")), /ENOENT/);
  await assert.rejects(stat(join(failedRoot, ".bridge-lifecycle.json")), /ENOENT/);
});

function owner(pid: number, instanceId: string): BridgeOwner {
  return { version: 1, pid, instanceId };
}

test("bridge lifecycle preserves a live owner's state and locks", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-live-owner-"));
  const live = owner(1111, "11111111-1111-4111-8111-111111111111");
  const lifecyclePath = join(root, ".bridge-lifecycle.json");
  const authLock = join(root, "auth.json.lock");
  await writeFile(lifecyclePath, JSON.stringify(live), { mode: 0o600 });
  await writeFile(authLock, JSON.stringify(live), { mode: 0o600 });

  await assert.rejects(
    acquireBridgeLifecycle(root, {
      owner: owner(2222, "22222222-2222-4222-8222-222222222222"),
      probeProcess: () => "alive"
    }),
    /already running|live|owned/i
  );
  assert.deepEqual(JSON.parse(await readFile(lifecyclePath, "utf8")), live);
  assert.deepEqual(JSON.parse(await readFile(authLock, "utf8")), live);
});

test("bridge lifecycle removes only dead-owner stale auth and enqueue locks", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-dead-owner-"));
  await mkdir(join(root, "tmp"), { mode: 0o700 });
  const dead = owner(3333, "33333333-3333-4333-8333-333333333333");
  const next = owner(4444, "44444444-4444-4444-8444-444444444444");
  const lifecyclePath = join(root, ".bridge-lifecycle.json");
  const authLock = join(root, "auth.json.lock");
  const enqueueLock = join(root, "tmp", `.${"a".repeat(64)}.enqueue.lock`);
  await writeFile(lifecyclePath, JSON.stringify(dead), { mode: 0o600 });
  await writeFile(authLock, JSON.stringify(dead), { mode: 0o600 });
  await writeFile(enqueueLock, JSON.stringify(dead), { mode: 0o600 });

  const lifecycle = await acquireBridgeLifecycle(root, {
    owner: next,
    probeProcess: () => "dead"
  });
  assert.deepEqual(JSON.parse(await readFile(lifecyclePath, "utf8")), next);
  await assert.rejects(readFile(authLock), /ENOENT/);
  await assert.rejects(readFile(enqueueLock), /ENOENT/);
  await lifecycle.release();
  await assert.rejects(readFile(lifecyclePath), /ENOENT/);
});

test("bridge lifecycle fails closed for ambiguous or mismatched lock ownership", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-ambiguous-owner-"));
  const dead = owner(5555, "55555555-5555-4555-8555-555555555555");
  const other = owner(6666, "66666666-6666-4666-8666-666666666666");
  const lifecyclePath = join(root, ".bridge-lifecycle.json");
  const authLock = join(root, "auth.json.lock");
  await writeFile(lifecyclePath, JSON.stringify(dead), { mode: 0o600 });
  await writeFile(authLock, JSON.stringify(other), { mode: 0o600 });

  await assert.rejects(
    acquireBridgeLifecycle(root, { owner: other, probeProcess: () => "ambiguous" }),
    /ambiguous|owned|running/i
  );
  assert.deepEqual(JSON.parse(await readFile(lifecyclePath, "utf8")), dead);
  assert.deepEqual(JSON.parse(await readFile(authLock, "utf8")), other);

  await assert.rejects(
    acquireBridgeLifecycle(root, { owner: other, probeProcess: () => "dead" }),
    /lock owner|ambiguous|mismatch/i
  );
  assert.deepEqual(JSON.parse(await readFile(authLock, "utf8")), other);
});

test("dead-owner recovery never follows a symlinked tmp directory to delete a lock", async () => {
  const parent = await mkdtemp(join(tmpdir(), "video001-lifecycle-tmp-symlink-"));
  const root = join(parent, "root");
  const outside = join(parent, "outside");
  await mkdir(root, { mode: 0o700 });
  await mkdir(outside, { mode: 0o700 });
  const dead = owner(6767, "67676767-6767-4676-8676-676767676767");
  const externalLock = join(outside, `.${"a".repeat(64)}.enqueue.lock`);
  await writeFile(join(root, ".bridge-lifecycle.json"), JSON.stringify(dead), { mode: 0o600 });
  await writeFile(externalLock, JSON.stringify(dead), { mode: 0o600 });
  await symlink(outside, join(root, "tmp"), "dir");

  await assert.rejects(
    acquireBridgeLifecycle(root, {
      owner: owner(6868, "68686868-6868-4686-8686-686868686868"),
      probeProcess: () => "dead"
    }),
    /tmp|directory|symlink|ambiguous/i
  );
  assert.deepEqual(JSON.parse(await readFile(externalLock, "utf8")), dead);
  assert.deepEqual(JSON.parse(await readFile(join(root, ".bridge-lifecycle.json"), "utf8")), dead);
});

test("startup-guard recovery is explicit, owner-scoped, and dead-process-only", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-startup-recovery-"));
  const stale = owner(7777, "77777777-7777-4777-8777-777777777777");
  const guard = join(root, ".bridge-startup");
  await mkdir(guard, { mode: 0o700 });
  await writeFile(join(guard, "owner.json"), JSON.stringify(stale), { mode: 0o600 });

  await assert.rejects(
    recoverBridgeStartupGuard(root, "88888888-8888-4888-8888-888888888888", () => "dead"),
    /instance|owner|match/i
  );
  await assert.rejects(
    recoverBridgeStartupGuard(root, stale.instanceId, () => "alive"),
    /live|running/i
  );
  assert.deepEqual(JSON.parse(await readFile(join(guard, "owner.json"), "utf8")), stale);

  await recoverBridgeStartupGuard(root, stale.instanceId, () => "dead");
  await assert.rejects(stat(guard), /ENOENT/);
});

test("configured production limits remain 120 seconds, seven days, and ten MiB", () => {
  assert.equal(LIMITS.requestTimeoutMs, 120_000);
});
