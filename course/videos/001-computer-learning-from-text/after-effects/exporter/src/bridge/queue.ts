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
  open,
  rename,
  unlink
} from "node:fs/promises";
import { basename, dirname, join } from "node:path";
import {
  canonicalJson,
  type AssetDescriptor,
  type ExporterPackage,
  validatePackage
} from "../shared/contract.ts";
import { serializeBridgeOwner, type BridgeOwner } from "./ownership.ts";
import { exporterPaths, type ExporterPaths } from "./paths.ts";

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

export class QueueStore {
  readonly paths: ExporterPaths;
  private readonly directoryIdentities: DirectoryIdentity[];
  private readonly lockOwner: BridgeOwner | undefined;

  constructor(root?: string, lockOwner?: BridgeOwner) {
    this.paths = exporterPaths(root);
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
    const validated = validatePackage(value);
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
      for (const asset of validated.assets) {
        const bytes = Buffer.from(asset.dataBase64, "base64");
        const path = await this.writeAsset(asset.hash, bytes, asset.byteLength);
        assets.push({
          hash: asset.hash,
          mimeType: asset.mimeType,
          byteLength: asset.byteLength,
          path
        });
      }

      const queuedPackage: QueuedPackage = { ...validated, assets };
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
