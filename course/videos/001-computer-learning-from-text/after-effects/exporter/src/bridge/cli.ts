import { randomBytes, randomUUID } from "node:crypto";
import {
  chmodSync,
  closeSync,
  constants,
  fsyncSync,
  lstatSync,
  mkdirSync,
  openSync
} from "node:fs";
import {
  lstat,
  mkdir,
  open,
  readdir,
  rename,
  rmdir,
  unlink
} from "node:fs/promises";
import { basename, dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { LIMITS } from "../shared/limits.ts";
import { AuthStore, type DirectorySync as AuthDirectorySync } from "./auth.ts";
import {
  parseBridgeOwner,
  parseOwnedHttpTemporaryFilename,
  sameBridgeOwner,
  serializeBridgeOwner,
  type BridgeOwner
} from "./ownership.ts";
import { QueueStore } from "./queue.ts";
import { createBridgeServer, type BridgeServer } from "./server.ts";

export type { BridgeOwner } from "./ownership.ts";

const LIFECYCLE_FILE = ".bridge-lifecycle.json";
const STARTUP_GUARD = ".bridge-startup";
const STARTUP_GUARD_OWNER = "owner.json";
const AUTH_LOCK = "auth.json.lock";
const STATE_FILE = "state.json";
const ENQUEUE_LOCK_PATTERN = /^\.[0-9a-f]{64}\.enqueue\.lock$/;

type DirectorySync = (path: string) => void | Promise<void>;
export type ProcessStatus = "alive" | "dead" | "ambiguous";
export type ProcessProbe = (pid: number) => ProcessStatus;

export interface BridgeState {
  pid: number;
  port: number;
  pairingCode: string;
  pairingExpiresAt: number;
}

export interface BridgeLifecycle {
  owner: BridgeOwner;
  release(): Promise<void>;
}

export interface RunningBridgeCli {
  bridge: BridgeServer;
  state: BridgeState;
  shutdown(): Promise<void>;
}

export interface StartBridgeCliDependencies {
  stateDirectorySync?: DirectorySync;
}

export class StatePublicationCleanupError extends Error {
  constructor(publicationError: unknown, cleanupError: unknown) {
    super("Bridge state publication failed and its durable cleanup could not be confirmed", {
      cause: new AggregateError([publicationError, cleanupError])
    });
    this.name = "StatePublicationCleanupError";
  }
}

function syncDirectorySync(path: string): void {
  const descriptor = openSync(path, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    fsyncSync(descriptor);
  } finally {
    closeSync(descriptor);
  }
}

async function syncDirectory(path: string): Promise<void> {
  const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    await handle.sync();
  } finally {
    await handle.close();
  }
}

function ensurePrivateRoot(root: string): string {
  if (!isAbsolute(root)) throw new TypeError("Exporter root must be an absolute path");
  const canonicalRoot = resolve(root);
  mkdirSync(canonicalRoot, { recursive: true, mode: 0o700 });
  const details = lstatSync(canonicalRoot);
  if (!details.isDirectory() || details.isSymbolicLink()) {
    throw new Error("Exporter root must be a private directory, not a symbolic link");
  }
  chmodSync(canonicalRoot, 0o700);
  return canonicalRoot;
}

async function exists(path: string): Promise<boolean> {
  try {
    await lstat(path);
    return true;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
    throw error;
  }
}

async function readNoFollow(path: string): Promise<{ bytes: string; device: number; inode: number }> {
  const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const details = await handle.stat();
    if (!details.isFile()) throw new Error("Bridge ownership path is not a regular file");
    return { bytes: await handle.readFile("utf8"), device: details.dev, inode: details.ino };
  } finally {
    await handle.close();
  }
}

async function readOwner(path: string): Promise<BridgeOwner> {
  const value = await readNoFollow(path);
  return parseBridgeOwner(JSON.parse(value.bytes) as unknown);
}

async function unlinkUnchanged(path: string, expectedDevice: number, expectedInode: number): Promise<void> {
  const current = await lstat(path);
  if (!current.isFile() || current.isSymbolicLink() || current.dev !== expectedDevice || current.ino !== expectedInode) {
    throw new Error("Bridge ownership changed during cleanup");
  }
  await unlink(path);
}

function validateState(value: unknown): BridgeState {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError("Bridge state must be an object");
  }
  const record = value as Record<string, unknown>;
  const expected = ["pid", "port", "pairingCode", "pairingExpiresAt"];
  const keys = Object.keys(record);
  if (keys.length !== expected.length || keys.some((key) => !expected.includes(key))) {
    throw new TypeError("Bridge state has unexpected fields");
  }
  if (!Number.isSafeInteger(record.pid) || (record.pid as number) <= 0) throw new TypeError("Bridge state PID is invalid");
  if (!Number.isSafeInteger(record.port) || (record.port as number) < 0 || (record.port as number) > 65_535) {
    throw new TypeError("Bridge state port is invalid");
  }
  if (typeof record.pairingCode !== "string" || !/^\d{6}$/.test(record.pairingCode)) {
    throw new TypeError("Bridge state pairing code is invalid");
  }
  if (!Number.isSafeInteger(record.pairingExpiresAt) || (record.pairingExpiresAt as number) < 0) {
    throw new TypeError("Bridge state pairing expiry is invalid");
  }
  return {
    pid: record.pid as number,
    port: record.port as number,
    pairingCode: record.pairingCode,
    pairingExpiresAt: record.pairingExpiresAt as number
  };
}

function defaultProbeProcess(pid: number): ProcessStatus {
  try {
    process.kill(pid, 0);
    return "alive";
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ESRCH") return "dead";
    return "ambiguous";
  }
}

async function writeExclusiveOwner(path: string, owner: BridgeOwner): Promise<void> {
  const handle = await open(
    path,
    constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW,
    0o600
  );
  try {
    await handle.writeFile(serializeBridgeOwner(owner), "utf8");
    await handle.sync();
  } finally {
    await handle.close();
  }
}

async function acquireStartupGuard(root: string, owner: BridgeOwner): Promise<() => Promise<void>> {
  const guard = join(root, STARTUP_GUARD);
  try {
    await mkdir(guard, { mode: 0o700 });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "EEXIST") {
      throw new Error("Bridge startup is guarded; use the explicit owner-scoped recovery flow if its owner is dead");
    }
    throw error;
  }
  const guardOwnerPath = join(guard, STARTUP_GUARD_OWNER);
  try {
    await writeExclusiveOwner(guardOwnerPath, owner);
    await syncDirectory(guard);
    await syncDirectory(root);
  } catch (error) {
    try { await unlink(guardOwnerPath); } catch { /* preserve the original failure */ }
    try { await rmdir(guard); } catch { /* preserve the original failure */ }
    throw error;
  }

  return async (): Promise<void> => {
    const persisted = await readOwner(guardOwnerPath);
    if (!sameBridgeOwner(persisted, owner)) throw new Error("Bridge startup guard changed ownership");
    await unlink(guardOwnerPath);
    await syncDirectory(guard);
    await rmdir(guard);
    await syncDirectory(root);
  };
}

async function staleLockPaths(root: string): Promise<string[]> {
  const paths: string[] = [];
  const authLock = join(root, AUTH_LOCK);
  if (await exists(authLock)) paths.push(authLock);
  const tmp = join(root, "tmp");
  if (await exists(tmp)) {
    const details = await lstat(tmp);
    if (!details.isDirectory() || details.isSymbolicLink() || (details.mode & 0o077) !== 0) {
      throw new Error("Exporter tmp path is not a private directory or is a symlink");
    }
    for (const name of await readdir(tmp)) {
      if (name.endsWith(".enqueue.lock")) {
        if (!ENQUEUE_LOCK_PATTERN.test(name)) throw new Error("Ambiguous enqueue lock filename");
        paths.push(join(tmp, name));
      }
    }
  }
  return paths;
}

async function staleHttpTemporaryPaths(root: string): Promise<string[]> {
  const tmp = join(root, "tmp");
  if (!(await exists(tmp))) return [];
  const details = await lstat(tmp);
  if (!details.isDirectory() || details.isSymbolicLink() || (details.mode & 0o077) !== 0) {
    throw new Error("Exporter tmp path is not a private directory or is a symlink");
  }
  return (await readdir(tmp))
    .filter((name) => name.startsWith(".http-body.") || name.startsWith(".http-asset."))
    .map((name) => join(tmp, name));
}

async function validateOwnedHttpTemporaries(
  paths: readonly string[],
  owner: BridgeOwner
): Promise<Array<{ device: number; inode: number; path: string }>> {
  const result: Array<{ device: number; inode: number; path: string }> = [];
  for (const path of paths) {
    let parsed: ReturnType<typeof parseOwnedHttpTemporaryFilename>;
    try {
      parsed = parseOwnedHttpTemporaryFilename(basename(path));
    } catch {
      throw new Error("HTTP temporary ownership is malformed");
    }
    if (!sameBridgeOwner(parsed.owner, owner)) throw new Error("HTTP temporary owner mismatch");
    const details = await lstat(path);
    if (!details.isFile() || details.isSymbolicLink() || (details.mode & 0o077) !== 0) {
      throw new Error("HTTP temporary is not an owner-only regular file or is a symlink");
    }
    result.push({ device: details.dev, inode: details.ino, path });
  }
  return result;
}

async function assertLocksOwned(paths: readonly string[], owner: BridgeOwner): Promise<void> {
  for (const path of paths) {
    let persisted: BridgeOwner;
    try {
      persisted = await readOwner(path);
    } catch {
      throw new Error("Ambiguous or malformed bridge lock owner");
    }
    if (!sameBridgeOwner(persisted, owner)) throw new Error("Bridge lock owner mismatch");
  }
}

async function removeOwnedFile(path: string, owner: BridgeOwner): Promise<void> {
  const value = await readNoFollow(path);
  let persisted: BridgeOwner;
  try {
    persisted = parseBridgeOwner(JSON.parse(value.bytes) as unknown);
  } catch {
    throw new Error("Ambiguous or malformed bridge owner");
  }
  if (!sameBridgeOwner(persisted, owner)) throw new Error("Bridge owner mismatch");
  await unlinkUnchanged(path, value.device, value.inode);
}

export async function acquireBridgeLifecycle(
  requestedRoot: string,
  options: { owner?: BridgeOwner; probeProcess?: ProcessProbe } = {}
): Promise<BridgeLifecycle> {
  const root = ensurePrivateRoot(requestedRoot);
  const owner = parseBridgeOwner(options.owner ?? { version: 1, pid: process.pid, instanceId: randomUUID() });
  const probeProcess = options.probeProcess ?? defaultProbeProcess;
  const releaseGuard = await acquireStartupGuard(root, owner);
  const lifecyclePath = join(root, LIFECYCLE_FILE);
  let lifecyclePublished = false;
  try {
    const locks = await staleLockPaths(root);
    const httpTemporaryPaths = await staleHttpTemporaryPaths(root);
    const statePath = join(root, STATE_FILE);
    const stateExists = await exists(statePath);
    if (await exists(lifecyclePath)) {
      let previousOwner: BridgeOwner;
      try {
        previousOwner = await readOwner(lifecyclePath);
      } catch {
        throw new Error("Bridge lifecycle ownership is malformed or ambiguous");
      }
      const status = probeProcess(previousOwner.pid);
      if (status === "alive") throw new Error("A live bridge owner is already running");
      if (status !== "dead") throw new Error("Bridge lifecycle ownership is ambiguous");

      await assertLocksOwned(locks, previousOwner);
      const ownedHttpTemporaries = await validateOwnedHttpTemporaries(httpTemporaryPaths, previousOwner);
      if (stateExists) {
        const persistedStateFile = await readNoFollow(statePath);
        const persistedState = validateState(JSON.parse(persistedStateFile.bytes) as unknown);
        if (persistedState.pid !== previousOwner.pid) throw new Error("Bridge state owner mismatch");
      }
      for (const path of locks) {
        await removeOwnedFile(path, previousOwner);
        await syncDirectory(dirname(path));
      }
      for (const temporary of ownedHttpTemporaries) {
        await unlinkUnchanged(temporary.path, temporary.device, temporary.inode);
      }
      if (ownedHttpTemporaries.length > 0) await syncDirectory(join(root, "tmp"));
      if (stateExists) await removeBridgeState(root, previousOwner.pid);
      await removeOwnedFile(lifecyclePath, previousOwner);
      await syncDirectory(root);
    } else if (locks.length > 0 || httpTemporaryPaths.length > 0 || stateExists) {
      throw new Error("Bridge locks, HTTP temporaries, or state have ambiguous ownership without a lifecycle marker");
    }

    await writeExclusiveOwner(lifecyclePath, owner);
    await syncDirectory(root);
    lifecyclePublished = true;
  } finally {
    try {
      await releaseGuard();
    } catch (guardError) {
      if (lifecyclePublished) {
        try { await removeOwnedFile(lifecyclePath, owner); } catch { /* fail closed with the guard error */ }
      }
      throw guardError;
    }
  }

  let released = false;
  return {
    owner,
    async release(): Promise<void> {
      if (released) return;
      await removeOwnedFile(lifecyclePath, owner);
      await syncDirectory(root);
      released = true;
    }
  };
}

export async function recoverBridgeStartupGuard(
  requestedRoot: string,
  expectedInstanceId: string,
  probeProcess: ProcessProbe = defaultProbeProcess
): Promise<void> {
  const root = ensurePrivateRoot(requestedRoot);
  const guard = join(root, STARTUP_GUARD);
  const guardDetails = await lstat(guard);
  if (!guardDetails.isDirectory() || guardDetails.isSymbolicLink() || (guardDetails.mode & 0o077) !== 0) {
    throw new Error("Startup guard is not a private directory or is a symlink");
  }
  const guardOwnerPath = join(guard, STARTUP_GUARD_OWNER);
  const persisted = await readOwner(guardOwnerPath);
  if (persisted.instanceId !== expectedInstanceId) {
    throw new Error("Startup guard instance does not match the explicitly requested owner");
  }
  const status = probeProcess(persisted.pid);
  if (status === "alive") throw new Error("Startup guard owner is still live");
  if (status !== "dead") throw new Error("Startup guard ownership is ambiguous");
  await removeOwnedFile(guardOwnerPath, persisted);
  await syncDirectory(guard);
  await rmdir(guard);
  await syncDirectory(root);
}

export function parseCliArgs(argv: readonly string[]): { root: string; port: number } {
  if (argv.length !== 4) throw new TypeError("Expected exactly --root <absolute-path> --port <0..65535>");
  let root: string | undefined;
  let port: number | undefined;
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (value === undefined) throw new TypeError("CLI argument value is missing");
    if (flag === "--root" && root === undefined) {
      if (!isAbsolute(value)) throw new TypeError("--root must be an absolute path");
      root = resolve(value);
    } else if (flag === "--port" && port === undefined) {
      if (!/^(?:0|[1-9]\d*)$/.test(value)) throw new TypeError("--port must be an integer from 0 through 65535");
      port = Number(value);
      if (!Number.isSafeInteger(port) || port > 65_535) throw new TypeError("--port must be an integer from 0 through 65535");
    } else {
      throw new TypeError(`Unknown or duplicate CLI argument: ${flag ?? "<missing>"}`);
    }
  }
  if (root === undefined || port === undefined) throw new TypeError("Both --root and --port are required");
  return { root, port };
}

export async function publishBridgeState(
  requestedRoot: string,
  stateValue: BridgeState,
  directorySync: DirectorySync = syncDirectory
): Promise<void> {
  const root = ensurePrivateRoot(requestedRoot);
  const state = validateState(stateValue);
  const destination = join(root, STATE_FILE);
  const temporaryPath = join(root, `.state.json.${process.pid}.${randomUUID()}.tmp`);
  let handle: Awaited<ReturnType<typeof open>> | undefined;
  let temporaryIdentity: { device: number; inode: number } | undefined;
  let renamed = false;
  try {
    handle = await open(
      temporaryPath,
      constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW,
      0o600
    );
    const opened = await handle.stat();
    if (!opened.isFile()) throw new Error("Bridge state temporary path is not a regular file");
    temporaryIdentity = { device: opened.dev, inode: opened.ino };
    await handle.writeFile(JSON.stringify(state), "utf8");
    await handle.sync();
    await handle.close();
    handle = undefined;
    await rename(temporaryPath, destination);
    renamed = true;
    await directorySync(root);
  } catch (error) {
    if (handle !== undefined) {
      try { await handle.close(); } catch { /* preserve the publication failure */ }
    }
    if (renamed && temporaryIdentity !== undefined) {
      try {
        const persisted = await readNoFollow(destination);
        const persistedState = validateState(JSON.parse(persisted.bytes) as unknown);
        if (
          persisted.device !== temporaryIdentity.device ||
          persisted.inode !== temporaryIdentity.inode ||
          persistedState.pid !== state.pid ||
          persistedState.port !== state.port ||
          persistedState.pairingCode !== state.pairingCode ||
          persistedState.pairingExpiresAt !== state.pairingExpiresAt
        ) {
          throw new Error("Bridge state changed identity or contents during publication cleanup");
        }
        await unlinkUnchanged(destination, persisted.device, persisted.inode);
        await directorySync(root);
      } catch (cleanupError) {
        throw new StatePublicationCleanupError(error, cleanupError);
      }
    } else if (temporaryIdentity !== undefined) {
      try {
        await unlinkUnchanged(temporaryPath, temporaryIdentity.device, temporaryIdentity.inode);
      } catch {
        // Preserve the publication failure and never unlink a changed temporary path.
      }
    }
    throw error;
  }
}

export async function removeBridgeState(
  requestedRoot: string,
  expectedPid: number,
  directorySync: DirectorySync = syncDirectory
): Promise<void> {
  const root = ensurePrivateRoot(requestedRoot);
  const statePath = join(root, STATE_FILE);
  const persisted = await readNoFollow(statePath);
  const state = validateState(JSON.parse(persisted.bytes) as unknown);
  if (state.pid !== expectedPid) throw new Error("Bridge state belongs to a different process");
  await unlinkUnchanged(statePath, persisted.device, persisted.inode);
  await directorySync(root);
}

export async function startBridgeCli(
  argv: readonly string[],
  dependencies: StartBridgeCliDependencies = {}
): Promise<RunningBridgeCli> {
  const { root, port } = parseCliArgs(argv);
  const lifecycle = await acquireBridgeLifecycle(root);
  let bridge: BridgeServer | undefined;
  let statePublished = false;
  try {
    const authDirectorySync: AuthDirectorySync = syncDirectorySync;
    const auth = await AuthStore.open(
      join(root, "auth.json"),
      Date.now,
      randomBytes,
      authDirectorySync,
      lifecycle.owner
    );
    const queue = new QueueStore(root, lifecycle.owner);
    const pairingCreatedAt = Date.now();
    const pairingCode = auth.createPairingCode();
    bridge = createBridgeServer({ auth, queue, host: "127.0.0.1", port });
    const address = await bridge.start();
    const state: BridgeState = {
      pid: process.pid,
      port: address.port,
      pairingCode,
      pairingExpiresAt: pairingCreatedAt + LIMITS.pairingTtlMs
    };
    await publishBridgeState(root, state, dependencies.stateDirectorySync ?? syncDirectory);
    statePublished = true;
    let shutdownPromise: Promise<void> | undefined;
    return {
      bridge,
      state,
      shutdown(): Promise<void> {
        if (shutdownPromise !== undefined) return shutdownPromise;
        shutdownPromise = (async () => {
          await bridge?.close();
          await removeBridgeState(root, process.pid);
          statePublished = false;
          await lifecycle.release();
        })();
        return shutdownPromise;
      }
    };
  } catch (error) {
    try { await bridge?.close(); } catch { /* preserve the startup failure */ }
    if (statePublished) {
      try { await removeBridgeState(root, process.pid); } catch { /* preserve the startup failure */ }
    }
    if (!(error instanceof StatePublicationCleanupError)) {
      try { await lifecycle.release(); } catch { /* preserve the startup failure */ }
    }
    throw error;
  }
}

async function main(): Promise<void> {
  let running: RunningBridgeCli | undefined;
  let stopRequested = false;
  let stopping = false;
  let resolveStopped: (() => void) | undefined;
  let rejectStopped: ((error: unknown) => void) | undefined;
  const stopped = new Promise<void>((resolve, reject) => {
    resolveStopped = resolve;
    rejectStopped = reject;
  });
  const stop = (): void => {
    stopRequested = true;
    if (running === undefined || stopping) return;
    stopping = true;
    void running.shutdown().then(resolveStopped, rejectStopped);
  };
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
  try {
    running = await startBridgeCli(process.argv.slice(2));
    if (stopRequested) stop();
    await stopped;
  } finally {
    process.off("SIGINT", stop);
    process.off("SIGTERM", stop);
  }
}

const invokedPath = process.argv[1] === undefined ? undefined : resolve(process.argv[1]);
if (invokedPath !== undefined && fileURLToPath(import.meta.url) === invokedPath) {
  void main().catch(() => {
    process.stderr.write('{"event":"bridge_failed","code":"BRIDGE_FAILURE"}\n');
    process.exitCode = 1;
  });
}
