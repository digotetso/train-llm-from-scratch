import { createHash, randomUUID } from "node:crypto";
import {
  chmodSync,
  constants,
  lstatSync,
  mkdirSync
} from "node:fs";
import {
  access,
  chmod,
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
import { exporterPaths, type ExporterPaths } from "./paths.ts";

const HASH_PATTERN = /^[0-9a-f]{64}$/;
const PACKAGE_SUFFIX = ".video001-ae.json";
const ERROR_SUFFIX = ".error.json";

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

async function pathExists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
    throw error;
  }
}

async function syncDirectory(path: string): Promise<void> {
  const handle = await open(path, "r");
  try {
    await handle.sync();
  } finally {
    await handle.close();
  }
}

export class QueueStore {
  readonly paths: ExporterPaths;

  constructor(root?: string) {
    this.paths = exporterPaths(root);
    for (const directory of [
      this.paths.root,
      this.paths.tmp,
      this.paths.incoming,
      this.paths.quarantine,
      this.paths.assets,
      this.paths.logs
    ]) {
      ensurePrivateDirectory(directory);
    }
  }

  async enqueue(value: unknown): Promise<EnqueueResult> {
    const validated = validatePackage(value);
    assertHash(validated.contentHash);
    const filename = `${validated.contentHash}${PACKAGE_SUFFIX}`;
    const destination = join(this.paths.incoming, filename);
    const lockPath = join(this.paths.tmp, `.${validated.contentHash}.enqueue.lock`);
    let lock: Awaited<ReturnType<typeof open>>;
    try {
      lock = await open(lockPath, "wx", 0o600);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "EEXIST") {
        throw new QueueConflictError(validated.contentHash);
      }
      throw error;
    }

    try {
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
      await lock.close();
      await unlink(lockPath);
    }
  }

  async writeAsset(hash: string, value: Uint8Array, expectedByteLength = value.byteLength): Promise<string> {
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
    assertHash(contentHash);
    void error;
    const filename = `${contentHash}${PACKAGE_SUFFIX}`;
    const reportFilename = `${contentHash}${ERROR_SUFFIX}`;
    const source = join(this.paths.incoming, filename);
    const destination = join(this.paths.quarantine, filename);
    const reportPath = join(this.paths.quarantine, reportFilename);

    if (!(await pathExists(source))) throw new Error(`Queued package ${contentHash} was not found`);
    if ((await pathExists(destination)) || (await pathExists(reportPath))) {
      throw new QueueConflictError(contentHash);
    }

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
      await syncDirectory(this.paths.quarantine);
    } catch (writeError) {
      await rename(destination, source);
      throw writeError;
    }
    return { filename, path: destination, reportFilename, reportPath };
  }

  private async atomicWrite(destination: string, bytes: Uint8Array): Promise<void> {
    const temporaryName = `.${basename(destination)}.${process.pid}.${randomUUID()}.tmp`;
    const temporaryPath = join(this.paths.tmp, temporaryName);
    let handle: Awaited<ReturnType<typeof open>> | undefined;
    try {
      handle = await open(temporaryPath, "wx", 0o600);
      await handle.writeFile(bytes);
      await handle.sync();
      await handle.close();
      handle = undefined;
      await rename(temporaryPath, destination);
      await chmod(destination, 0o600);
      await syncDirectory(dirname(destination));
    } catch (error) {
      if (handle !== undefined) await handle.close();
      try {
        await unlink(temporaryPath);
      } catch (unlinkError) {
        if ((unlinkError as NodeJS.ErrnoException).code !== "ENOENT") throw unlinkError;
      }
      throw error;
    }
  }
}
