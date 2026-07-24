import assert from "node:assert/strict";
import { createHook } from "node:async_hooks";
import { createHash, randomUUID } from "node:crypto";
import { mkdtemp, readFile, readdir, rename, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { performance } from "node:perf_hooks";
import test from "node:test";
import { QueueStore } from "../src/bridge/queue.ts";
import { BridgeWorkDeadlineError, type BridgeWorkContext, type BridgeWorkPhase } from "../src/bridge/work-control.ts";
import {
  cleanupStreamedAssets,
  fingerprintStreamingPackage,
  readStreamingPackage,
  StreamingPackageLimitError,
  StreamingPackageValidationError,
  type OwnedTemporaryFile,
  type StreamingPackageLimits
} from "../src/bridge/streaming-package.ts";
import {
  contentFingerprintInput,
  type ExporterPackage,
  type GroupNode,
  type RasterNode,
  validatePackage
} from "../src/shared/contract.ts";
import { LIMITS } from "../src/shared/limits.ts";
import { canonicalJson } from "../src/shared/contract.ts";
import { finalizeLegacyVideo001Package, legacyVideo001ExportMediaType } from "../src/shared/legacy-video001.ts";
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
    project: value.project,
    contentHash: value.contentHash,
    exportedAt: value.exportedAt,
    exporterVersion: value.exporterVersion,
    schemaVersion: value.schemaVersion
  };
}

function defineProtoKey(record: Record<string, unknown>): void {
  Object.defineProperty(record, "__proto__", {
    configurable: true,
    enumerable: true,
    value: { reviewFinding: true },
    writable: true
  });
}

function wrapFrameChildrenInGroups(value: ExporterPackage, count: number): void {
  let children = value.frames[0]!.children;
  for (let index = 0; index < count; index += 1) {
    const group: GroupNode = {
      id: `depth-group-${index}`,
      kind: "group",
      name: `Depth_Group_${index}`,
      x: 0,
      y: 0,
      width: 100,
      height: 100,
      rotation: 0,
      opacity: 1,
      children
    };
    children = [group];
  }
  value.frames[0]!.children = children;
}

function abortAtPhase(phase: BridgeWorkPhase): { context: BridgeWorkContext; controller: AbortController } {
  const controller = new AbortController();
  return {
    controller,
    context: {
      deadlineSignal: controller.signal,
      checkpoint: (progress) => {
        if (progress.phase === phase) controller.abort();
      }
    }
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
    maxAggregateAssetBytes: Math.max(
      value.assets.reduce((total, asset) => total + asset.byteLength, 0),
      1
    ),
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

test("streaming asset parsing creates promises per chunk rather than per encoded byte", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "video001-streaming-promise-budget-"));
  const queue = new QueueStore(root, OWNER);
  const value = makeValidPackage();
  const bytes = Buffer.allocUnsafe(49_157);
  for (let index = 0; index < bytes.byteLength; index += 1) bytes[index] = (index * 19 + 7) & 0xff;
  addAsset(value, bytes, "raster-promise-budget");
  const body = JSON.stringify(reverseWireOrder(value));
  const temporary = await spool(queue, body);
  let promiseCount = 0;
  const hook = createHook({
    init(_asyncId, type): void {
      if (type === "PROMISE") promiseCount += 1;
    }
  });

  hook.enable();
  let result: Awaited<ReturnType<typeof readStreamingPackage>>;
  try {
    result = await readStreamingPackage(temporary, queue, OWNER, {
      chunkBytes: 64 * 1024,
      limits: limits(body, value)
    });
  } finally {
    hook.disable();
  }

  t.diagnostic(`${promiseCount} promises while parsing ${bytes.byteLength} decoded asset bytes`);
  assert.ok(promiseCount < 20_000, `created ${promiseCount} promises while parsing ${bytes.byteLength} bytes`);
  await cleanupStreamedAssets(result.assets, queue);
});

test("streaming parser sustains production-headroom throughput on four MiB of encoded asset data", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "video001-streaming-throughput-"));
  const queue = new QueueStore(root, OWNER);
  const value = makeValidPackage();
  const bytes = Buffer.allocUnsafe(3 * 1024 * 1024 + 64);
  for (let index = 0; index < bytes.byteLength; index += 1) bytes[index] = (index * 13 + 29) & 0xff;
  addAsset(value, bytes, "raster-throughput");
  assert.ok(value.assets[0]!.dataBase64.length > 4 * 1024 * 1024);
  const body = JSON.stringify(reverseWireOrder(value));
  const temporary = await spool(queue, body);
  let parseCheckpoints = 0;
  const chunkBytes = 64 * 1024;

  const startedAt = performance.now();
  const result = await readStreamingPackage(temporary, queue, OWNER, {
    chunkBytes,
    limits: limits(body, value),
    work: {
      checkpoint: ({ phase }) => {
        if (phase === "parse") parseCheckpoints += 1;
      }
    }
  });
  const elapsedMs = performance.now() - startedAt;
  const encodedMiB = value.assets[0]!.dataBase64.length / (1024 * 1024);
  const throughputMiBPerSecond = encodedMiB / (elapsedMs / 1_000);

  t.diagnostic(
    `${encodedMiB.toFixed(3)} MiB encoded in ${elapsedMs.toFixed(3)} ms (${throughputMiBPerSecond.toFixed(1)} MiB/s), ${parseCheckpoints} parse checkpoints`
  );
  assert.ok(
    throughputMiBPerSecond >= 30,
    `streaming parse throughput ${throughputMiBPerSecond.toFixed(1)} MiB/s is below the 30 MiB/s budget`
  );
  const inputChunks = Math.ceil(Buffer.byteLength(body) / chunkBytes);
  assert.ok(parseCheckpoints >= inputChunks);
  assert.ok(parseCheckpoints <= inputChunks * 2 + 4);
  await cleanupStreamedAssets(result.assets, queue);
});

test("streaming parse stops at an injected deadline checkpoint", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-streaming-parse-deadline-"));
  const queue = new QueueStore(root, OWNER);
  const value = makeValidPackage();
  addAsset(value, Buffer.from("parse deadline"), "raster-parse-deadline");
  const body = JSON.stringify(reverseWireOrder(value));
  const { context } = abortAtPhase("parse");

  await assert.rejects(
    readStreamingPackage(await spool(queue, body), queue, OWNER, {
      chunkBytes: 3,
      limits: limits(body, value),
      work: context
    }),
    (error: unknown) => error instanceof BridgeWorkDeadlineError
  );
  assert.deepEqual((await readdir(queue.paths.tmp)).filter((name) => name.startsWith(".http-asset.")), []);
});

test("streaming fingerprint stops at an injected deadline checkpoint", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-streaming-fingerprint-deadline-"));
  const queue = new QueueStore(root, OWNER);
  const value = makeValidPackage();
  addAsset(value, Buffer.from("fingerprint deadline"), "raster-fingerprint-deadline");
  const body = JSON.stringify(reverseWireOrder(value));
  const parsed = await readStreamingPackage(await spool(queue, body), queue, OWNER, {
    chunkBytes: 3,
    limits: limits(body, value)
  });
  const { context } = abortAtPhase("fingerprint");

  try {
    await assert.rejects(
      fingerprintStreamingPackage(parsed.package, parsed.assets, queue, { chunkBytes: 3, work: context }),
      (error: unknown) => error instanceof BridgeWorkDeadlineError
    );
  } finally {
    await cleanupStreamedAssets(parsed.assets, queue);
  }
});

test("verified queue copy stops at an injected deadline checkpoint", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-streaming-copy-deadline-"));
  const queue = new QueueStore(root, OWNER);
  const value = makeValidPackage();
  const bytes = Buffer.from("verified copy deadline");
  addAsset(value, bytes, "raster-copy-deadline");
  value.contentHash = createHash("sha256").update(contentFingerprintInput(value)).digest("hex");
  const body = JSON.stringify(reverseWireOrder(value));
  const parsed = await readStreamingPackage(await spool(queue, body), queue, OWNER, {
    chunkBytes: 3,
    limits: limits(body, value)
  });
  const { context } = abortAtPhase("copy");

  try {
    await assert.rejects(
      queue.enqueueVerified(parsed.package, parsed.assets, { work: context }),
      (error: unknown) => error instanceof BridgeWorkDeadlineError
    );
    assert.deepEqual(await readdir(queue.paths.incoming), []);
    assert.deepEqual(await readdir(queue.paths.assets), []);
  } finally {
    await cleanupStreamedAssets(parsed.assets, queue);
  }
});

test("streaming objects preserve prototype-named keys for exact-key validation", async () => {
  for (const boundary of ["package", "node", "asset"] as const) {
    const root = await mkdtemp(join(tmpdir(), `video001-streaming-proto-${boundary}-`));
    const queue = new QueueStore(root, OWNER);
    const value = makeValidPackage();
    if (boundary === "asset") addAsset(value, Buffer.from("proto asset"), "raster-proto");
    const wire = reverseWireOrder(value);
    if (boundary === "package") {
      defineProtoKey(wire);
    } else if (boundary === "node") {
      const frames = wire.frames as Array<{ children: Array<Record<string, unknown>> }>;
      defineProtoKey(frames[0]!.children[0]!);
    } else {
      defineProtoKey((wire.assets as Array<Record<string, unknown>>)[0]!);
    }
    const body = JSON.stringify(wire);
    const parsed = JSON.parse(body) as unknown;
    assert.throws(() => validatePackage(parsed), /unexpected|unknown field/i, boundary);

    await assert.rejects(
      readStreamingPackage(await spool(queue, body), queue, OWNER, {
        chunkBytes: 3,
        limits: limits(body, value)
      }),
      /unexpected|unknown field/i,
      boundary
    );
  }
});

test("normal and streaming validation share the same JSON container-depth limit", async () => {
  assert.equal(LIMITS.maxJsonContainerDepth, 64);
  const cases = [
    { groups: 28, accepted: true },
    { groups: 29, accepted: false }
  ];
  for (const entry of cases) {
    const root = await mkdtemp(join(tmpdir(), `video001-streaming-depth-${entry.groups}-`));
    const queue = new QueueStore(root, OWNER);
    const value = makeValidPackage();
    wrapFrameChildrenInGroups(value, entry.groups);
    const body = JSON.stringify(reverseWireOrder(value));
    const parsed = JSON.parse(body) as unknown;
    if (entry.accepted) {
      assert.doesNotThrow(() => validatePackage(parsed));
      await readStreamingPackage(await spool(queue, body), queue, OWNER, {
        chunkBytes: 3,
        limits: limits(body, value)
      });
    } else {
      assert.throws(() => validatePackage(parsed), /nesting|depth/i);
      await assert.rejects(
        readStreamingPackage(await spool(queue, body), queue, OWNER, {
          chunkBytes: 3,
          limits: limits(body, value)
        }),
        /nesting|depth/i
      );
    }
  }
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

test("legacy controller wire payload keeps its schema-2 content hash and media semantics through streaming and queue publication", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-legacy-streaming-queue-"));
  const queue = new QueueStore(root, OWNER);
  const generic = makeValidPackage();
  const { project: _project, ...legacyInput } = generic;
  const legacy = finalizeLegacyVideo001Package({ ...legacyInput, schemaVersion: "2.0.0", contentHash: "" });
  const body = JSON.stringify(legacy);
  assert.equal(legacyVideo001ExportMediaType, "application/vnd.video001.figma-ae+json");
  const parsed = await readStreamingPackage(await spool(queue, body), queue, OWNER, {
    chunkBytes: 3,
    limits: limits(body, generic)
  });
  assert.equal(parsed.package.schemaVersion, "2.0.0");
  assert.equal(parsed.package.contentHash, legacy.contentHash);
  const queued = await queue.enqueueVerified(parsed.package, parsed.assets);
  const persisted = JSON.parse(await readFile(queued.path, "utf8"));
  assert.deepEqual(persisted, legacy);
  assert.equal(queued.filename, `${legacy.contentHash}.video001-ae.json`);
});

test("legacy streaming rejects a canonically hashed 49-frame package before it queues anything", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-legacy-49-streaming-"));
  const queue = new QueueStore(root, OWNER);
  const generic = makeValidPackage();
  const { project: _project, ...legacyInput } = generic;
  const legacy = finalizeLegacyVideo001Package({ ...legacyInput, schemaVersion: "2.0.0", contentHash: "" });
  const frame = legacy.frames[0]!;
  const oversized = {
    ...legacy,
    frames: Array.from({ length: 49 }, (_, index) => {
      const next = structuredClone(frame);
      next.nodeId = `legacy-stream-${index}`;
      next.children[0]!.id = `legacy-stream-node-${index}`;
      return next;
    })
  };
  oversized.contentHash = createHash("sha256").update(canonicalJson({ ...oversized, exportedAt: "", contentHash: "" })).digest("hex");
  const body = JSON.stringify(oversized);

  await assert.rejects(
    readStreamingPackage(await spool(queue, body), queue, OWNER, { chunkBytes: 3, limits: limits(body, generic) }),
    /48-frame limit/i
  );
  assert.deepEqual(await readdir(queue.paths.incoming), []);
});

test("legacy verified streaming rejects changed identities, tampered bytes, and declared SHA-256 mismatches", async () => {
  const createLegacyAssetPackage = () => {
    const generic = makeValidPackage();
    addAsset(generic, Buffer.from("legacy verified asset"), "legacy-asset");
    const { project: _project, ...legacyInput } = generic;
    return finalizeLegacyVideo001Package({ ...legacyInput, schemaVersion: "2.0.0", contentHash: "" });
  };
  const legacy = createLegacyAssetPackage();
  const body = JSON.stringify(legacy);
  const legacyLimits = (candidateBody: string, assets = legacy.assets) =>
    limits(candidateBody, { ...makeValidPackage(), assets });

  const tamperRoot = await mkdtemp(join(tmpdir(), "video001-legacy-tamper-"));
  const tamperQueue = new QueueStore(tamperRoot, OWNER);
  const tampered = await readStreamingPackage(await spool(tamperQueue, body), tamperQueue, OWNER, {
    chunkBytes: 3,
    limits: legacyLimits(body)
  });
  await writeFile(tampered.assets[0]!.path, "tampered", { mode: 0o600 });
  await assert.rejects(
    tamperQueue.enqueueVerified(tampered.package, tampered.assets),
    /changed|hash|identity/i
  );
  assert.deepEqual(await readdir(tamperQueue.paths.incoming), []);

  const identityRoot = await mkdtemp(join(tmpdir(), "video001-legacy-identity-"));
  const identityQueue = new QueueStore(identityRoot, OWNER);
  const identity = await readStreamingPackage(await spool(identityQueue, body), identityQueue, OWNER, {
    chunkBytes: 3,
    limits: legacyLimits(body)
  });
  const movedPath = join(identityQueue.paths.tmp, ".untrusted-legacy-asset.tmp");
  await rename(identity.assets[0]!.path, movedPath);
  await assert.rejects(
    identityQueue.enqueueVerified(identity.package, [{ ...identity.assets[0]!, path: movedPath }]),
    /owner-stamped|owner|temporary/i
  );
  assert.deepEqual(await readdir(identityQueue.paths.incoming), []);
  await rename(movedPath, identity.assets[0]!.path);
  await cleanupStreamedAssets(identity.assets, identityQueue);

  const hashRoot = await mkdtemp(join(tmpdir(), "video001-legacy-sha-"));
  const hashQueue = new QueueStore(hashRoot, OWNER);
  const wrongHash = structuredClone(legacy);
  wrongHash.assets[0]!.hash = "f".repeat(64);
  const wrongHashRaster = wrongHash.frames[0]!.children.find((node) => node.kind === "raster");
  if (wrongHashRaster?.kind !== "raster") throw new Error("expected the legacy fixture to include a raster node");
  wrongHashRaster.assetHash = wrongHash.assets[0]!.hash;
  wrongHash.contentHash = createHash("sha256")
    .update(canonicalJson({ ...wrongHash, exportedAt: "", contentHash: "" }))
    .digest("hex");
  const wrongHashBody = JSON.stringify(wrongHash);
  const hashMismatch = await readStreamingPackage(await spool(hashQueue, wrongHashBody), hashQueue, OWNER, {
    chunkBytes: 3,
    limits: legacyLimits(wrongHashBody, wrongHash.assets)
  });
  await assert.rejects(
    hashQueue.enqueueVerified(hashMismatch.package, hashMismatch.assets),
    /hash|verified/i
  );
  assert.deepEqual(await readdir(hashQueue.paths.incoming), []);
  await cleanupStreamedAssets(hashMismatch.assets, hashQueue);
});
