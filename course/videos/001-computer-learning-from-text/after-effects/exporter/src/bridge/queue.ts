import { createHash, randomUUID } from "node:crypto";
import {
  chmodSync,
  constants,
  lstatSync,
  mkdirSync,
  realpathSync
} from "node:fs";
import {
  access,
  link,
  open,
  rename,
  unlink
} from "node:fs/promises";
import { basename, dirname, join } from "node:path";
import {
  EXTERNAL_ASSET_DATA,
  canonicalJson,
  type AssetDescriptor,
  type ExternalAssetDescriptor,
  type ExternalExporterPackage,
  type ExporterPackage,
  validatePackage,
  validatePackageWithVerifiedAssets
} from "../shared/contract.ts";
import {
  isLegacyVideo001Package,
  validateLegacyVideo001Package,
  validateLegacyVideo001PackageWithVerifiedAssets
} from "../shared/legacy-video001.ts";
import {
  ownedHttpTemporaryFilename,
  parseOwnedHttpTemporaryFilename,
  sameBridgeOwner,
  serializeBridgeOwner,
  type BridgeOwner
} from "./ownership.ts";
import { legacyExporterPaths, type ExporterPaths } from "./paths.ts";
import type { StreamedAssetFile } from "./streaming-package.ts";
import { checkpointBridgeWork, type BridgeWorkContext } from "./work-control.ts";

const HASH_PATTERN = /^[0-9a-f]{64}$/;
const PACKAGE_SUFFIX = ".video001-ae.json";
const ERROR_SUFFIX = ".error.json";

interface DirectoryIdentity {
  path: string;
  realPath: string;
  device: number;
  inode: number;
}

export interface QueuedAsset extends Omit<AssetDescriptor, "dataBase64"> {
  path: string;
}

export interface QueuedPackage extends Omit<ExporterPackage, "assets"> {
  assets: QueuedAsset[];
}

export interface EnqueueResult {
  filename: string;
  path: string;
  package: QueuedPackage;
}

export interface VerifiedEnqueueOptions {
  work?: BridgeWorkContext;
}

export interface QuarantineResult {
  filename: string;
  path: string;
  reportFilename: string;
  reportPath: string;
}

export class QueueConflictError extends Error {
  readonly code = "QUEUE_DUPLICATE";

  constructor(contentHash: string) {
    super(`Package ${contentHash} is already queued`);
    this.name = "QueueConflictError";
  }
}

function assertHash(hash: string): void {
  if (!HASH_PATTERN.test(hash)) {
    throw new TypeError("Queue asset and package hashes must be 64 lowercase hexadecimal characters");
  }
}

function ensurePrivateDirectory(path: string): void {
  mkdirSync(path, { recursive: true, mode: 0o700 });
  const details = lstatSync(path);
  if (!details.isDirectory() || details.isSymbolicLink()) {
    throw new Error(`Exporter path is not a private directory: ${path}`);
  }
  chmodSync(path, 0o700);
}

function captureDirectoryIdentity(path: string): DirectoryIdentity {
  const details = lstatSync(path);
  if (!details.isDirectory() || details.isSymbolicLink() || (details.mode & 0o077) !== 0) {
    throw new Error(`Exporter directory is not private or changed identity: ${path}`);
  }
  return {
    path,
    realPath: realpathSync(path),
    device: details.dev,
    inode: details.ino
  };
}

function assertDirectoryIdentity(identity: DirectoryIdentity): void {
  let current: DirectoryIdentity;
  try {
    current = captureDirectoryIdentity(identity.path);
  } catch {
    throw new Error(`Exporter directory changed identity or became a symlink: ${identity.path}`);
  }
  if (
    current.realPath !== identity.realPath ||
    current.device !== identity.device ||
    current.inode !== identity.inode
  ) {
    throw new Error(`Exporter directory changed identity: ${identity.path}`);
  }
}

async function pathExists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
    throw error;
  }
}

async function writeAll(handle: Awaited<ReturnType<typeof open>>, value: Uint8Array): Promise<void> {
  let offset = 0;
  while (offset < value.byteLength) {
    const result = await handle.write(value, offset, value.byteLength - offset, null);
    if (result.bytesWritten === 0) throw new Error("Verified asset copy made no write progress");
    offset += result.bytesWritten;
  }
}

export class QueueStore {
  readonly owner: BridgeOwner | undefined;
  readonly paths: ExporterPaths;
  private readonly directoryIdentities: DirectoryIdentity[];
  private readonly lockOwner: BridgeOwner | undefined;

  constructor(root?: string, lockOwner?: BridgeOwner) {
    this.paths = legacyExporterPaths(root);
    const directories = [
      this.paths.root,
      this.paths.tmp,
      this.paths.incoming,
      this.paths.quarantine,
      this.paths.assets,
      this.paths.logs
    ];
    for (const directory of directories) {
      ensurePrivateDirectory(directory);
    }
    this.directoryIdentities = directories.map(captureDirectoryIdentity);
    this.lockOwner = lockOwner;
    this.owner = lockOwner;
    const rootIdentity = this.directoryIdentities[0];
    if (
      rootIdentity === undefined ||
      this.directoryIdentities.slice(1).some((identity) => dirname(identity.realPath) !== rootIdentity.realPath)
    ) {
      throw new Error("Exporter subdirectories must resolve directly inside the canonical exporter root");
    }
  }

  async enqueue(value: unknown): Promise<EnqueueResult> {
    this.assertDirectoryIdentities();
    const validated = (isLegacyVideo001Package(value) ? validateLegacyVideo001Package(value) : validatePackage(value)) as ExporterPackage;
    return this.enqueueValidated(validated, async (_index, asset) => {
      if (!("dataBase64" in asset)) throw new Error("In-memory asset data is missing");
      const bytes = Buffer.from(asset.dataBase64, "base64");
      return this.writeAsset(asset.hash, bytes, asset.byteLength);
    });
  }

  async enqueueVerified(
    value: ExternalExporterPackage,
    sources: readonly StreamedAssetFile[],
    options: VerifiedEnqueueOptions = {}
  ): Promise<EnqueueResult> {
    this.assertDirectoryIdentities();
    if (this.lockOwner === undefined) throw new Error("Verified enqueue requires a bridge lifecycle owner");
    if (value.assets.length !== sources.length) throw new Error("Verified asset source count does not match package assets");
    const validationValue = {
      ...value,
      assets: value.assets.map((asset) => ({ ...asset, dataBase64: EXTERNAL_ASSET_DATA }))
    };
    const normalizedManifestBytes = Buffer.byteLength(JSON.stringify({
      ...value,
      assets: value.assets.map((asset) => ({ ...asset, dataBase64: "" }))
    }));
    const evidence = sources.map((source) => ({ byteLength: source.size, hash: source.hash }));
    const byteCounts = { bodyBytes: normalizedManifestBytes, manifestBytes: normalizedManifestBytes };
    const validated = (isLegacyVideo001Package(value)
      ? validateLegacyVideo001PackageWithVerifiedAssets(validationValue, evidence, byteCounts)
      : validatePackageWithVerifiedAssets(validationValue, evidence, byteCounts)) as ExternalExporterPackage;
    return this.enqueueValidated(validated, (index, asset) => {
      const source = sources[index];
      if (source === undefined) throw new Error("Verified asset source is missing");
      return this.copyVerifiedAsset(source, asset, options.work);
    }, options.work);
  }

  private async enqueueValidated(
    validated: ExporterPackage | ExternalExporterPackage,
    materializeAsset: (index: number, asset: AssetDescriptor | ExternalAssetDescriptor) => Promise<string>,
    work?: BridgeWorkContext
  ): Promise<EnqueueResult> {
    assertHash(validated.contentHash);
    const filename = `${validated.contentHash}${PACKAGE_SUFFIX}`;
    const destination = join(this.paths.incoming, filename);
    const lockPath = join(this.paths.tmp, `.${validated.contentHash}.enqueue.lock`);
    let lock: Awaited<ReturnType<typeof open>> | undefined;
    try {
      this.assertDirectoryIdentities();
      lock = await open(
        lockPath,
        constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW,
        0o600
      );
      if (this.lockOwner !== undefined) {
        await lock.writeFile(serializeBridgeOwner(this.lockOwner), "utf8");
        await lock.sync();
      }
    } catch (error) {
      if (lock !== undefined) {
        const acquired = await lock.stat();
        await lock.close();
        try {
          const current = lstatSync(lockPath);
          if (current.isFile() && current.dev === acquired.dev && current.ino === acquired.ino) {
            await unlink(lockPath);
          }
        } catch {
          // Preserve the owner-record failure and never remove a changed lock.
        }
      }
      if ((error as NodeJS.ErrnoException).code === "EEXIST") {
        throw new QueueConflictError(validated.contentHash);
      }
      throw error;
    }
    if (lock === undefined) throw new Error("Queue lock acquisition failed");

    try {
      this.assertDirectoryIdentities();
      if (await pathExists(destination)) throw new QueueConflictError(validated.contentHash);

      const assets: QueuedAsset[] = [];
      for (let index = 0; index < validated.assets.length; index += 1) {
        const asset = validated.assets[index]!;
        const path = await materializeAsset(index, asset);
        assets.push({
          hash: asset.hash,
          mimeType: asset.mimeType,
          byteLength: asset.byteLength,
          path
        });
      }

      const queuedPackage: QueuedPackage = { ...validated, assets };
      await checkpointBridgeWork(work, "copy", assets.reduce((total, asset) => total + asset.byteLength, 0));
      await this.atomicWrite(destination, Buffer.from(canonicalJson(queuedPackage), "utf8"));
      return { filename, path: destination, package: queuedPackage };
    } finally {
      const lockIdentity = await lock.stat();
      await lock.close();
      this.assertDirectoryIdentities();
      const current = lstatSync(lockPath);
      if (current.dev !== lockIdentity.dev || current.ino !== lockIdentity.ino || !current.isFile()) {
        throw new Error("Queue lock changed ownership before release");
      }
      await unlink(lockPath);
    }
  }

  private async copyVerifiedAsset(
    source: StreamedAssetFile,
    asset: ExternalAssetDescriptor,
    work?: BridgeWorkContext
  ): Promise<string> {
    this.assertDirectoryIdentities();
    assertHash(asset.hash);
    if (this.lockOwner === undefined) throw new Error("Verified enqueue requires a bridge lifecycle owner");
    let filenameOwner: ReturnType<typeof parseOwnedHttpTemporaryFilename>;
    try {
      filenameOwner = parseOwnedHttpTemporaryFilename(basename(source.path));
    } catch {
      throw new Error("Verified asset source filename is not owner-stamped");
    }
    if (
      source.kind !== "http-asset" ||
      filenameOwner.kind !== "http-asset" ||
      dirname(source.path) !== this.paths.tmp ||
      source.size !== asset.byteLength ||
      source.hash !== asset.hash ||
      !sameBridgeOwner(source.owner, this.lockOwner) ||
      !sameBridgeOwner(filenameOwner.owner, this.lockOwner)
    ) {
      throw new Error("Verified asset source does not match its package, owner, or temporary directory");
    }

    const destination = join(this.paths.assets, `${asset.hash}.png`);
    const temporaryPath = join(
      this.paths.tmp,
      ownedHttpTemporaryFilename("http-asset", this.lockOwner, randomUUID())
    );
    let sourceHandle: Awaited<ReturnType<typeof open>> | undefined;
    let temporaryHandle: Awaited<ReturnType<typeof open>> | undefined;
    let temporaryIdentity: { device: number; inode: number } | undefined;
    try {
      this.assertDirectoryIdentities();
      sourceHandle = await open(source.path, constants.O_RDONLY | constants.O_NOFOLLOW);
      const sourceBefore = await sourceHandle.stat();
      if (
        !sourceBefore.isFile() ||
        sourceBefore.dev !== source.device ||
        sourceBefore.ino !== source.inode ||
        sourceBefore.size !== source.size
      ) {
        throw new Error("Verified asset source changed before queue publication");
      }
      temporaryHandle = await open(
        temporaryPath,
        constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW,
        0o600
      );
      await temporaryHandle.chmod(0o600);
      const temporaryDetails = await temporaryHandle.stat();
      temporaryIdentity = { device: temporaryDetails.dev, inode: temporaryDetails.ino };
      this.assertDirectoryIdentities();

      const digest = createHash("sha256");
      const buffer = Buffer.allocUnsafe(64 * 1024);
      let position = 0;
      while (position < source.size) {
        const result = await sourceHandle.read(
          buffer,
          0,
          Math.min(buffer.byteLength, source.size - position),
          position
        );
        if (result.bytesRead === 0) throw new Error("Verified asset source ended before its recorded size");
        const bytes = buffer.subarray(0, result.bytesRead);
        digest.update(bytes);
        await writeAll(temporaryHandle, bytes);
        position += result.bytesRead;
        await checkpointBridgeWork(work, "copy", position);
      }
      const sourceAfter = await sourceHandle.stat();
      if (
        sourceAfter.dev !== source.device ||
        sourceAfter.ino !== source.inode ||
        sourceAfter.size !== source.size ||
        digest.digest("hex") !== asset.hash
      ) {
        throw new Error("Verified asset source changed or failed its hash recheck");
      }
      await temporaryHandle.sync();
      const copied = await temporaryHandle.stat();
      if (copied.size !== asset.byteLength) throw new Error("Verified asset copy size mismatch");
      await temporaryHandle.close();
      temporaryHandle = undefined;
      await sourceHandle.close();
      sourceHandle = undefined;

      this.assertDirectoryIdentities();
      try {
        await link(temporaryPath, destination);
        await this.syncKnownDirectory(this.paths.assets);
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
        if (!(await this.verifyExistingAsset(destination, asset.hash, asset.byteLength, work))) throw error;
      }
      return destination;
    } finally {
      if (temporaryHandle !== undefined) await temporaryHandle.close();
      if (sourceHandle !== undefined) await sourceHandle.close();
      if (temporaryIdentity !== undefined) {
        try {
          this.assertDirectoryIdentities();
          const current = lstatSync(temporaryPath);
          if (
            current.isFile() &&
            current.dev === temporaryIdentity.device &&
            current.ino === temporaryIdentity.inode
          ) {
            await unlink(temporaryPath);
            await this.syncKnownDirectory(this.paths.tmp);
          }
        } catch (error) {
          if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
        }
      }
    }
  }

  private async verifyExistingAsset(
    path: string,
    expectedHash: string,
    expectedSize: number,
    work?: BridgeWorkContext
  ): Promise<boolean> {
    let handle: Awaited<ReturnType<typeof open>> | undefined;
    try {
      this.assertDirectoryIdentities();
      handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW);
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code === "ENOENT") return false;
      if (code === "ELOOP") throw new Error("Existing asset path must not be a symbolic link");
      throw error;
    }
    try {
      const before = await handle.stat();
      if (!before.isFile() || before.size !== expectedSize) {
        throw new Error("Existing asset does not match its content address");
      }
      const digest = createHash("sha256");
      const buffer = Buffer.allocUnsafe(64 * 1024);
      let position = 0;
      while (position < before.size) {
        const result = await handle.read(buffer, 0, Math.min(buffer.byteLength, before.size - position), position);
        if (result.bytesRead === 0) throw new Error("Existing asset ended before its recorded size");
        digest.update(buffer.subarray(0, result.bytesRead));
        position += result.bytesRead;
        await checkpointBridgeWork(work, "copy", position);
      }
      const after = await handle.stat();
      if (after.dev !== before.dev || after.ino !== before.ino || after.size !== before.size) {
        throw new Error("Existing asset changed while being verified");
      }
      if (digest.digest("hex") !== expectedHash) throw new Error("Existing asset failed its content hash");
      await handle.chmod(0o600);
      return true;
    } finally {
      await handle.close();
    }
  }

  async writeAsset(hash: string, value: Uint8Array, expectedByteLength = value.byteLength): Promise<string> {
    this.assertDirectoryIdentities();
    assertHash(hash);
    if (!Number.isSafeInteger(expectedByteLength) || expectedByteLength < 0) {
      throw new TypeError("Asset byte length must be a non-negative safe integer");
    }
    const bytes = Buffer.from(value);
    if (bytes.byteLength !== expectedByteLength) {
      throw new Error(`Asset length mismatch: expected ${expectedByteLength}, received ${bytes.byteLength}`);
    }
    const actualHash = createHash("sha256").update(bytes).digest("hex");
    if (actualHash !== hash) throw new Error("Asset SHA-256 hash does not match its descriptor");

    const destination = join(this.paths.assets, `${hash}.png`);
    let existingHandle: Awaited<ReturnType<typeof open>> | undefined;
    try {
      this.assertDirectoryIdentities();
      existingHandle = await open(destination, constants.O_RDONLY | constants.O_NOFOLLOW);
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code === "ELOOP") {
        throw new Error("Existing asset path must be a regular file, not a symbolic link");
      }
      if (code !== "ENOENT") throw error;
    }
    if (existingHandle !== undefined) {
      try {
        const details = await existingHandle.stat();
        if (!details.isFile()) throw new Error("Existing asset path must be a regular file");
        const existing = await existingHandle.readFile();
        const existingHash = createHash("sha256").update(existing).digest("hex");
        if (existing.byteLength === expectedByteLength && existingHash === hash) {
          await existingHandle.chmod(0o600);
          this.assertDirectoryIdentities();
          return destination;
        }
      } finally {
        await existingHandle.close();
      }
    }

    await this.atomicWrite(destination, bytes);
    return destination;
  }

  async quarantine(contentHash: string, error: unknown): Promise<QuarantineResult> {
    this.assertDirectoryIdentities();
    assertHash(contentHash);
    void error;
    const filename = `${contentHash}${PACKAGE_SUFFIX}`;
    const reportFilename = `${contentHash}${ERROR_SUFFIX}`;
    const source = join(this.paths.incoming, filename);
    const destination = join(this.paths.quarantine, filename);
    const reportPath = join(this.paths.quarantine, reportFilename);

    this.assertDirectoryIdentities();
    if (!(await pathExists(source))) throw new Error(`Queued package ${contentHash} was not found`);
    this.assertDirectoryIdentities();
    const destinationExists = await pathExists(destination);
    this.assertDirectoryIdentities();
    const reportExists = await pathExists(reportPath);
    if (destinationExists || reportExists) {
      throw new QueueConflictError(contentHash);
    }

    this.assertDirectoryIdentities();
    await rename(source, destination);
    try {
      const report = {
        contentHash,
        error: {
          code: "PACKAGE_REJECTED",
          message: "The queued package was rejected"
        }
      };
      await this.atomicWrite(reportPath, Buffer.from(canonicalJson(report), "utf8"));
      await this.syncKnownDirectory(this.paths.quarantine);
    } catch (writeError) {
      this.assertDirectoryIdentities();
      await rename(destination, source);
      throw writeError;
    }
    return { filename, path: destination, reportFilename, reportPath };
  }

  assertHealthy(): void {
    this.assertDirectoryIdentities();
  }

  async syncTemporaryDirectory(): Promise<void> {
    await this.syncKnownDirectory(this.paths.tmp);
  }

  private async atomicWrite(destination: string, bytes: Uint8Array): Promise<void> {
    const temporaryName = `.${basename(destination)}.${process.pid}.${randomUUID()}.tmp`;
    const temporaryPath = join(this.paths.tmp, temporaryName);
    let handle: Awaited<ReturnType<typeof open>> | undefined;
    try {
      this.assertDirectoryIdentities();
      handle = await open(
        temporaryPath,
        constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW,
        0o600
      );
      await handle.writeFile(bytes);
      await handle.sync();
      await handle.close();
      handle = undefined;
      this.assertDirectoryIdentities();
      await rename(temporaryPath, destination);
      await this.syncKnownDirectory(dirname(destination));
    } catch (error) {
      if (handle !== undefined) await handle.close();
      try {
        this.assertDirectoryIdentities();
        await unlink(temporaryPath);
      } catch {
        // Preserve the original failure and never follow a changed directory during cleanup.
      }
      throw error;
    }
  }

  private assertDirectoryIdentities(): void {
    for (const identity of this.directoryIdentities) assertDirectoryIdentity(identity);
  }

  private async syncKnownDirectory(path: string): Promise<void> {
    this.assertDirectoryIdentities();
    const identity = this.directoryIdentities.find((candidate) => candidate.path === path);
    if (identity === undefined) throw new Error(`Refusing to fsync an unknown exporter directory: ${path}`);
    const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW);
    try {
      const details = await handle.stat();
      if (!details.isDirectory() || details.dev !== identity.device || details.ino !== identity.inode) {
        throw new Error(`Exporter directory changed identity: ${path}`);
      }
      await handle.sync();
    } finally {
      await handle.close();
    }
  }
}
