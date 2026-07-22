import assert from "node:assert/strict";
import { createHash, randomUUID } from "node:crypto";
import { mkdtemp, readFile, readdir, rename, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { QueueStore } from "../src/bridge/queue.ts";
import {
  cleanupStreamedAssets,
  fingerprintStreamingPackage,
  readStreamingPackage,
  StreamingPackageLimitError,
  StreamingPackageValidationError,
  type OwnedTemporaryFile,
  type StreamingPackageLimits
} from "../src/bridge/streaming-package.ts";
import { contentFingerprintInput, type ExporterPackage, type RasterNode } from "../src/shared/contract.ts";
import { makeValidPackage } from "./helpers/package.ts";

const OWNER = {
  version: 1 as const,
  pid: 8_101,
  instanceId: "81018101-8101-4101-8101-810181018101"
};

function addAsset(value: ExporterPackage, bytes: Buffer, id: string): void {
  const hash = createHash("sha256").update(bytes).digest("hex");
  value.assets.push({ hash, mimeType: "image/png", byteLength: bytes.byteLength, dataBase64: bytes.toString("base64") });
  const raster: RasterNode = {
    id,
    kind: "raster",
    name: `Raster_${id}`,
    x: 0,
    y: 0,
    width: 10,
    height: 10,
    rotation: 0,
    opacity: 1,
    assetHash: hash
  };
  value.frames[0]!.children.push(raster);
}

function reverseWireOrder(value: ExporterPackage): Record<string, unknown> {
  return {
    assets: value.assets.map((asset) => ({
      dataBase64: asset.dataBase64,
      byteLength: asset.byteLength,
      mimeType: asset.mimeType,
      hash: asset.hash
    })),
    frames: value.frames,
    target: value.target,
    source: value.source,
    contentHash: value.contentHash,
    exportedAt: value.exportedAt,
    exporterVersion: value.exporterVersion,
    schemaVersion: value.schemaVersion
  };
}

async function spool(queue: QueueStore, body: string): Promise<OwnedTemporaryFile> {
  const path = join(
    queue.paths.tmp,
    `.http-body.${OWNER.pid}.${OWNER.instanceId}.${randomUUID()}.tmp`
  );
  await writeFile(path, body, { mode: 0o600 });
  const details = await stat(path);
  return {
    device: details.dev,
    inode: details.ino,
    kind: "http-body",
    owner: OWNER,
    path,
    size: details.size
  };
}

function limits(body: string, value: ExporterPackage): StreamingPackageLimits {
  const encodedBytes = value.assets.reduce((total, asset) => total + asset.dataBase64.length, 0);
  return {
    maxAggregateAssetBytes: value.assets.reduce((total, asset) => total + asset.byteLength, 0),
    maxAssetBytes: Math.max(...value.assets.map((asset) => asset.byteLength), 1),
    maxBodyBytes: Buffer.byteLength(body),
    maxManifestBytes: Buffer.byteLength(body) - encodedBytes
  };
}

test("streaming reader excludes asset string contents from the manifest and preserves canonical fingerprints", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-streaming-package-"));
  const queue = new QueueStore(root, OWNER);
  const value = makeValidPackage();
  value.exporterVersion = "stream\nreader";
  addAsset(value, Buffer.from("asset bytes spanning base64 quartets"), "raster-streamed");
  value.contentHash = createHash("sha256").update(contentFingerprintInput(value)).digest("hex");
  const body = ` \n ${JSON.stringify(reverseWireOrder(value), null, 1)} \t`;
  const temporary = await spool(queue, body);

  const result = await readStreamingPackage(temporary, queue, OWNER, {
    chunkBytes: 3,
    limits: limits(body, value)
  });

  assert.equal(result.manifestBytes, Buffer.byteLength(body) - value.assets[0]!.dataBase64.length);
  assert.ok(Buffer.byteLength(body) > result.manifestBytes);
  assert.equal(result.assets.length, 1);
  assert.equal(result.assets[0]!.hash, value.assets[0]!.hash);
  assert.equal(result.assets[0]!.size, value.assets[0]!.byteLength);
  assert.equal(
    await fingerprintStreamingPackage(result.package, result.assets, queue, { chunkBytes: 2 }),
    value.contentHash
  );
  assert.equal((await stat(result.assets[0]!.path)).mode & 0o777, 0o600);

  await cleanupStreamedAssets(result.assets, queue);
  assert.deepEqual((await readdir(queue.paths.tmp)).filter((name) => name.startsWith(".http-asset.")), []);
});

test("streaming base64 decode and fingerprint encoding cross internal buffer boundaries", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-streaming-boundary-"));
  const queue = new QueueStore(root, OWNER);
  const value = makeValidPackage();
  const bytes = Buffer.allocUnsafe(49_157);
  for (let index = 0; index < bytes.byteLength; index += 1) bytes[index] = (index * 37 + 11) & 0xff;
  addAsset(value, bytes, "raster-boundary");
  value.contentHash = createHash("sha256").update(contentFingerprintInput(value)).digest("hex");
  const body = JSON.stringify(reverseWireOrder(value));

  const result = await readStreamingPackage(await spool(queue, body), queue, OWNER, {
    chunkBytes: 1_021,
    limits: limits(body, value)
  });

  assert.deepEqual(await readFile(result.assets[0]!.path), bytes);
  assert.equal(
    await fingerprintStreamingPackage(result.package, result.assets, queue, { chunkBytes: 1_019 }),
    value.contentHash
  );
  await cleanupStreamedAssets(result.assets, queue);
});

test("streaming reader rejects raw, manifest, per-asset, and aggregate byte excesses", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-streaming-limits-"));
  const queue = new QueueStore(root, OWNER);
  const value = makeValidPackage();
  addAsset(value, Buffer.from("first"), "raster-first");
  addAsset(value, Buffer.from("second"), "raster-second");
  const body = JSON.stringify(reverseWireOrder(value));
  const base = limits(body, value);

  for (const entry of [
    { changed: { ...base, maxBodyBytes: Buffer.byteLength(body) - 1 }, error: StreamingPackageLimitError },
    { changed: { ...base, maxManifestBytes: base.maxManifestBytes - 1 }, error: StreamingPackageLimitError },
    {
      changed: { ...base, maxAssetBytes: value.assets[1]!.byteLength - 1 },
      error: StreamingPackageValidationError
    },
    {
      changed: {
        ...base,
        maxAggregateAssetBytes: value.assets[0]!.byteLength + value.assets[1]!.byteLength - 1
      },
      error: StreamingPackageValidationError
    }
  ]) {
    const temporary = await spool(queue, body);
    await assert.rejects(
      readStreamingPackage(temporary, queue, OWNER, { chunkBytes: 1, limits: entry.changed }),
      (error: unknown) => error instanceof entry.error
    );
    assert.deepEqual((await readdir(queue.paths.tmp)).filter((name) => name.startsWith(".http-asset.")), []);
  }
});

test("streaming reader rejects escaped and noncanonical asset base64 across tiny chunks", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-streaming-base64-"));
  const queue = new QueueStore(root, OWNER);
  const value = makeValidPackage();
  addAsset(value, Buffer.from("f"), "raster-base64");
  const validBody = JSON.stringify(reverseWireOrder(value));
  const encoded = value.assets[0]!.dataBase64;

  for (const replacement of ["Zg\\u003d\\u003d", "Zh==", "Zg=+"]) {
    const body = validBody.replace(encoded, replacement);
    const temporary = await spool(queue, body);
    await assert.rejects(
      readStreamingPackage(temporary, queue, OWNER, {
        chunkBytes: 1,
        limits: { ...limits(validBody, value), maxBodyBytes: Buffer.byteLength(body) }
      }),
      (error: unknown) => error instanceof StreamingPackageValidationError
    );
    assert.deepEqual((await readdir(queue.paths.tmp)).filter((name) => name.startsWith(".http-asset.")), []);
  }
});

test("verified queue enqueue rechecks streamed files and publishes the same slim package", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-streaming-queue-"));
  const queue = new QueueStore(root, OWNER);
  const value = makeValidPackage();
  const bytes = Buffer.from("queue adoption bytes");
  addAsset(value, bytes, "raster-queue");
  value.contentHash = createHash("sha256").update(contentFingerprintInput(value)).digest("hex");
  const body = JSON.stringify(reverseWireOrder(value));
  const parsed = await readStreamingPackage(await spool(queue, body), queue, OWNER, {
    chunkBytes: 2,
    limits: limits(body, value)
  });

  const queued = await queue.enqueueVerified(parsed.package, parsed.assets);
  const persisted = JSON.parse(await readFile(queued.path, "utf8")) as {
    assets: Array<{ dataBase64?: string; path: string }>;
  };
  assert.equal(Object.hasOwn(persisted.assets[0] ?? {}, "dataBase64"), false);
  assert.deepEqual(await readFile(persisted.assets[0]!.path), bytes);
  assert.equal((await stat(persisted.assets[0]!.path)).mode & 0o777, 0o600);

  await cleanupStreamedAssets(parsed.assets, queue);

  const tamperRoot = await mkdtemp(join(tmpdir(), "video001-streaming-queue-tamper-"));
  const tamperQueue = new QueueStore(tamperRoot, OWNER);
  const tamperParsed = await readStreamingPackage(await spool(tamperQueue, body), tamperQueue, OWNER, {
    chunkBytes: 2,
    limits: limits(body, value)
  });
  await writeFile(tamperParsed.assets[0]!.path, "tampered", { mode: 0o600 });
  await assert.rejects(
    tamperQueue.enqueueVerified(tamperParsed.package, tamperParsed.assets),
    /verified|identity|size|hash|changed/i
  );
  assert.deepEqual(await readdir(tamperQueue.paths.incoming), []);

  const unstampedRoot = await mkdtemp(join(tmpdir(), "video001-streaming-queue-unstamped-"));
  const unstampedQueue = new QueueStore(unstampedRoot, OWNER);
  const unstampedParsed = await readStreamingPackage(await spool(unstampedQueue, body), unstampedQueue, OWNER, {
    chunkBytes: 2,
    limits: limits(body, value)
  });
  const originalPath = unstampedParsed.assets[0]!.path;
  const clientSelectedPath = join(unstampedQueue.paths.tmp, ".client-selected.tmp");
  await rename(originalPath, clientSelectedPath);
  const changedSource = { ...unstampedParsed.assets[0]!, path: clientSelectedPath };
  await assert.rejects(
    unstampedQueue.enqueueVerified(unstampedParsed.package, [changedSource]),
    /owner-stamped|owner|temporary/i
  );
  assert.deepEqual(await readdir(unstampedQueue.paths.incoming), []);
  await rename(clientSelectedPath, originalPath);
  await cleanupStreamedAssets(unstampedParsed.assets, unstampedQueue);

  const ownerlessRoot = await mkdtemp(join(tmpdir(), "video001-streaming-queue-ownerless-"));
  const ownerlessQueue = new QueueStore(ownerlessRoot);
  await assert.rejects(
    ownerlessQueue.enqueueVerified(parsed.package, parsed.assets),
    /lifecycle owner/i
  );
});
