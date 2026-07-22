import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { chmod, mkdir, mkdtemp, readFile, readdir, rename, stat, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { isAbsolute, join } from "node:path";
import test from "node:test";
import type { ExporterPackage, RasterNode } from "../src/shared/contract.ts";
import { QueueStore } from "../src/bridge/queue.ts";
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
