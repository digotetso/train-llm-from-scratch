import { constants } from "node:fs";
import { link, lstat, mkdir, open, readdir, unlink } from "node:fs/promises";
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { randomUUID } from "node:crypto";
import { PROFILE_LIMITS } from "../shared/limits.ts";
import {
  canonicalProfileJson,
  hashProjectProfile,
  profileSummary,
  publicProfileProjection,
  profileReference,
  type InstalledProfile,
  type ProfileProjection,
  type ProfileReference,
  type ProfileSummary
} from "../shared/project-profile.ts";
import type { GenericExporterPaths } from "./paths.ts";

const PROFILE_FILE_SUFFIX = ".figma-ae-project.json";
const PROFILE_FILE_PATTERN = /^([0-9a-f]{64})\.figma-ae-project\.json$/;
const PROFILE_SHA256_PATTERN = /^[0-9a-f]{64}$/;
const REVISION_PATTERN = /^[1-9][0-9]*$/;
const PROJECT_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]{1,62}[a-z0-9])?$/;
const INSTALL_LOCK_FILENAME = ".profile-registry.install.lock";
const LOCK_RETRY_LIMIT = 100;
const LOCK_RETRY_DELAY_MS = 10;

export interface ProfileRegistryEvent {
  operation: "install" | "list" | "resolve";
  status: "ok" | "error";
  projectId?: string;
  revision?: number;
  profileSha256?: string;
  elapsedMs: number;
}

interface RegistryOptions {
  now?: () => number;
  record?: (event: ProfileRegistryEvent) => void;
  /** @internal Test-only observable hooks for failure and durability coverage. */
  testHooks?: {
    afterInstallLockAcquired?: () => Promise<void>;
    afterTemporaryCreated?: () => Promise<void>;
    afterDirectorySynced?: (path: string) => Promise<void>;
  };
}

interface HeldInstallLock {
  path: string;
  identity: FileIdentity;
}

interface FileIdentity {
  device: number;
  inode: number;
}

function registryError(code: string): Error {
  return new Error(code);
}

function isNotFound(error: unknown): boolean {
  return (error as NodeJS.ErrnoException).code === "ENOENT";
}

function isAlreadyExists(error: unknown): boolean {
  return (error as NodeJS.ErrnoException).code === "EEXIST";
}

function sameIdentity(left: FileIdentity, right: FileIdentity): boolean {
  return left.device === right.device && left.inode === right.inode;
}

function asFileIdentity(value: { dev: number; ino: number }): FileIdentity {
  return { device: value.dev, inode: value.ino };
}

function assertPrivateMode(mode: number, expected: number): void {
  if ((mode & 0o777) !== expected) throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
}

function validateRegistryProjectId(value: unknown): string {
  if (typeof value !== "string" || !PROJECT_ID_PATTERN.test(value)) {
    throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
  }
  return value;
}

function validateReference(reference: ProfileReference): ProfileReference {
  const projectId = validateRegistryProjectId(reference.projectId);
  if (!Number.isSafeInteger(reference.profileRevision) || reference.profileRevision <= 0) {
    throw registryError("PROFILE_NOT_FOUND");
  }
  if (!PROFILE_SHA256_PATTERN.test(reference.profileSha256)) throw registryError("PROFILE_NOT_FOUND");
  return { projectId, profileRevision: reference.profileRevision, profileSha256: reference.profileSha256 };
}

function validatePaths(paths: GenericExporterPaths): GenericExporterPaths {
  if (!isAbsolute(paths.root)) throw new TypeError("Exporter root must be an absolute path");
  const root = resolve(paths.root);
  const expected = {
    root,
    auth: join(root, "auth"),
    profiles: join(root, "profiles"),
    projects: join(root, "projects"),
    tmp: join(root, "tmp")
  };
  if (
    paths.root !== expected.root ||
    paths.auth !== expected.auth ||
    paths.profiles !== expected.profiles ||
    paths.projects !== expected.projects ||
    paths.tmp !== expected.tmp
  ) throw new TypeError("Exporter paths must be derived from one absolute root");
  return expected;
}

function assertContained(root: string, path: string): void {
  const result = relative(root, path);
  if (result === "" || result === ".." || result.startsWith(`..${sep}`) || isAbsolute(result)) {
    throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
  }
}

async function lstatDirectory(path: string, requirePrivate = true): Promise<FileIdentity> {
  const details = await lstat(path);
  if (!details.isDirectory() || details.isSymbolicLink()) throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
  if (requirePrivate) assertPrivateMode(details.mode, 0o700);
  return asFileIdentity(details);
}

async function lstatFile(path: string, requirePrivate = true): Promise<FileIdentity> {
  const details = await lstat(path);
  if (!details.isFile() || details.isSymbolicLink()) throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
  if (requirePrivate) assertPrivateMode(details.mode, 0o600);
  return asFileIdentity(details);
}

async function ensurePrivateDirectory(
  path: string,
  onDirectorySynced?: (path: string) => Promise<void>
): Promise<FileIdentity> {
  const resolved = resolve(path);
  const segments = resolved.split(sep).filter(Boolean);
  let current = resolved.startsWith(sep) ? sep : "";
  for (const segment of segments) {
    current = current === sep ? join(current, segment) : current === "" ? segment : join(current, segment);
    try {
      await lstatDirectory(current, current === resolved);
    } catch (error) {
      if (!isNotFound(error)) throw error;
      const parent = dirname(current);
      const parentIdentity = await lstatDirectory(parent, false);
      try {
        await mkdir(current, { mode: 0o700 });
      } catch (mkdirError) {
        if (!isAlreadyExists(mkdirError)) throw mkdirError;
      }
      await lstatDirectory(current, true);
      await syncDirectory(parent, parentIdentity, false);
      await onDirectorySynced?.(current);
    }
  }
  return lstatDirectory(resolved);
}

async function assertSafeExistingDirectoryAncestors(path: string, requirePrivateFinal = true): Promise<void> {
  const resolved = resolve(path);
  const segments = resolved.split(sep).filter(Boolean);
  let current = resolved.startsWith(sep) ? sep : "";
  for (const segment of segments) {
    current = current === sep ? join(current, segment) : current === "" ? segment : join(current, segment);
    await lstatDirectory(current, current === resolved && requirePrivateFinal);
  }
}

async function syncDirectory(path: string, expected?: FileIdentity, requirePrivate = true): Promise<void> {
  await assertSafeExistingDirectoryAncestors(path, requirePrivate);
  const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const details = await handle.stat();
    if (!details.isDirectory() || (expected !== undefined && !sameIdentity(asFileIdentity(details), expected))) {
      throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
    }
    await handle.sync();
  } finally {
    await handle.close();
  }
  await assertSafeExistingDirectoryAncestors(path, requirePrivate);
}

async function readRegularFile(path: string, requirePrivate = true): Promise<Buffer> {
  await assertSafeExistingDirectoryAncestors(dirname(path), requirePrivate);
  const before = await lstatFile(path, requirePrivate);
  const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const opened = await handle.stat();
    if (!opened.isFile() || !sameIdentity(before, asFileIdentity(opened)) || opened.size > PROFILE_LIMITS.maxProfileBytes) {
      throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
    }
    const bytes = await handle.readFile();
    const after = await handle.stat();
    if (!sameIdentity(before, asFileIdentity(after)) || after.size !== bytes.byteLength) {
      throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
    }
    return bytes;
  } finally {
    await handle.close();
  }
}

async function readInstalled(path: string, expected: ProfileReference): Promise<InstalledProfile> {
  let parsed: unknown;
  try {
    parsed = JSON.parse((await readRegularFile(path)).toString("utf8")) as unknown;
  } catch (error) {
    if (isNotFound(error)) throw error;
    if ((error as Error).message.startsWith("PROFILE_REGISTRY_")) throw error;
    throw registryError("PROFILE_REGISTRY_CORRUPT");
  }
  let installed: InstalledProfile;
  try {
    installed = hashProjectProfile(parsed);
  } catch {
    throw registryError("PROFILE_REGISTRY_CORRUPT");
  }
  if (
    installed.profile.project.id !== expected.projectId ||
    installed.profile.project.revision !== expected.profileRevision ||
    installed.profileSha256 !== expected.profileSha256
  ) throw registryError("PROFILE_REGISTRY_CORRUPT");
  const canonical = Buffer.from(canonicalProfileJson(installed.profile), "utf8");
  const persisted = await readRegularFile(path);
  if (!persisted.equals(canonical)) throw registryError("PROFILE_REGISTRY_CORRUPT");
  return installed;
}

export class ProfileRegistry {
  private readonly paths: GenericExporterPaths;
  private readonly now: () => number;
  private readonly record: ((event: ProfileRegistryEvent) => void) | undefined;
  private readonly testHooks: RegistryOptions["testHooks"];

  constructor(paths: GenericExporterPaths, options: RegistryOptions = {}) {
    this.paths = validatePaths(paths);
    this.now = options.now ?? Date.now;
    this.record = options.record;
    this.testHooks = options.testHooks;
  }

  async installFile(sourcePath: string): Promise<InstalledProfile> {
    return this.withInstallEvent(async () => {
      if (!isAbsolute(sourcePath)) throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
      const canonicalSourcePath = resolve(sourcePath);
      let value: unknown;
      try {
        value = JSON.parse((await readRegularFile(canonicalSourcePath, false)).toString("utf8")) as unknown;
      } catch (error) {
        if ((error as Error).message.startsWith("PROFILE_REGISTRY_")) throw error;
        throw registryError("PROFILE_REGISTRY_CORRUPT");
      }
      return this.install(value);
    });
  }

  async installValue(value: unknown): Promise<InstalledProfile> {
    return this.withInstallEvent(() => this.install(value));
  }

  async list(): Promise<ProfileSummary[]> {
    return this.withEvent("list", undefined, async () => {
      const entries = await this.entries();
      const summaries: ProfileSummary[] = [];
      for (const entry of entries) summaries.push(profileSummary(await readInstalled(entry.path, entry.reference)));
      return summaries;
    });
  }

  async resolve(reference: ProfileReference): Promise<InstalledProfile> {
    const started = this.now();
    let safeReference: ProfileReference | undefined;
    try {
      safeReference = validateReference(reference);
      const path = this.profilePath(safeReference);
      try {
        await this.ensureRevisionDirectory(safeReference.projectId, safeReference.profileRevision, false);
      } catch (error) {
        if (isNotFound(error)) throw registryError("PROFILE_NOT_FOUND");
        throw error;
      }
      try {
        const installed = await readInstalled(path, safeReference);
        this.emit("resolve", "ok", safeReference, started);
        return installed;
      } catch (error) {
        if (isNotFound(error)) throw registryError("PROFILE_NOT_FOUND");
        throw error;
      }
    } catch (error) {
      this.emit("resolve", "error", safeReference, started);
      throw error;
    }
  }

  async projection(reference: ProfileReference): Promise<ProfileProjection> {
    return publicProfileProjection(await this.resolve(reference));
  }

  private async install(value: unknown): Promise<InstalledProfile> {
    const installed = hashProjectProfile(value);
    const reference: ProfileReference = {
      projectId: installed.profile.project.id,
      profileRevision: installed.profile.project.revision,
      profileSha256: installed.profileSha256
    };
    const destination = this.profilePath(reference);
    return this.withInstallLock(async () => {
      const existing = await this.entries();
      const sameRevision = existing.filter((entry) =>
        entry.reference.projectId === reference.projectId && entry.reference.profileRevision === reference.profileRevision
      );
      if (sameRevision.length > 0) {
        if (sameRevision.length !== 1 || sameRevision[0]!.reference.profileSha256 !== reference.profileSha256) {
          throw registryError("PROFILE_REVISION_CONFLICT");
        }
        return readInstalled(destination, reference);
      }
      if (existing.length >= PROFILE_LIMITS.maxInstalledProfiles) throw registryError("PROFILE_REGISTRY_CAPACITY");
      const directory = await this.ensureRevisionDirectory(reference.projectId, reference.profileRevision, true);
      const bytes = Buffer.from(canonicalProfileJson(installed.profile), "utf8");
      await this.publish(directory, destination, bytes);
      return readInstalled(destination, reference);
    });
  }

  private async withInstallLock<T>(action: () => Promise<T>): Promise<T> {
    const lock = await this.acquireInstallLock();
    try {
      await this.testHooks?.afterInstallLockAcquired?.();
      return await action();
    } finally {
      await this.releaseInstallLock(lock);
    }
  }

  private async acquireInstallLock(): Promise<HeldInstallLock> {
    await ensurePrivateDirectory(this.paths.root, this.testHooks?.afterDirectorySynced);
    const profilesIdentity = await ensurePrivateDirectory(this.paths.profiles, this.testHooks?.afterDirectorySynced);
    const lockPath = join(this.paths.profiles, INSTALL_LOCK_FILENAME);
    assertContained(this.paths.profiles, lockPath);
    for (let attempt = 0; attempt < LOCK_RETRY_LIMIT; attempt += 1) {
      let handle: Awaited<ReturnType<typeof open>> | undefined;
      try {
        await assertSafeExistingDirectoryAncestors(this.paths.profiles);
        handle = await open(
          lockPath,
          constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW,
          0o600
        );
        const details = await handle.stat();
        if (!details.isFile()) throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
        await handle.sync();
        const identity = asFileIdentity(details);
        await handle.close();
        handle = undefined;
        const current = await lstatFile(lockPath);
        if (!sameIdentity(current, identity)) throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
        await syncDirectory(this.paths.profiles, profilesIdentity);
        return { path: lockPath, identity };
      } catch (error) {
        if (handle !== undefined) await handle.close();
        if (!isAlreadyExists(error)) throw error;
        await lstatFile(lockPath);
        await new Promise<void>((complete) => setTimeout(complete, LOCK_RETRY_DELAY_MS));
      }
    }
    throw registryError("PROFILE_REGISTRY_LOCKED");
  }

  private async releaseInstallLock(lock: HeldInstallLock): Promise<void> {
    const profilesIdentity = await lstatDirectory(this.paths.profiles);
    const current = await lstatFile(lock.path);
    if (!sameIdentity(current, lock.identity)) throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
    await unlink(lock.path);
    await syncDirectory(this.paths.profiles, profilesIdentity);
  }

  private async ensureRevisionDirectory(projectId: string, revision: number, create: boolean): Promise<FileIdentity> {
    const profiles = this.paths.profiles;
    assertContained(this.paths.root, profiles);
    if (create) {
      await ensurePrivateDirectory(this.paths.root, this.testHooks?.afterDirectorySynced);
      await ensurePrivateDirectory(profiles, this.testHooks?.afterDirectorySynced);
    } else {
      await assertSafeExistingDirectoryAncestors(this.paths.root);
      await lstatDirectory(profiles);
    }
    const project = join(profiles, projectId);
    assertContained(profiles, project);
    if (create) await ensurePrivateDirectory(project, this.testHooks?.afterDirectorySynced);
    else await lstatDirectory(project);
    const revisionPath = join(project, String(revision));
    assertContained(project, revisionPath);
    if (create) return ensurePrivateDirectory(revisionPath, this.testHooks?.afterDirectorySynced);
    return lstatDirectory(revisionPath);
  }

  private profilePath(reference: ProfileReference): string {
    const revision = join(this.paths.profiles, reference.projectId, String(reference.profileRevision));
    const path = join(revision, `${reference.profileSha256}${PROFILE_FILE_SUFFIX}`);
    assertContained(revision, path);
    return path;
  }

  private async entries(): Promise<Array<{ path: string; reference: ProfileReference }>> {
    let projectNames: string[];
    try {
      await assertSafeExistingDirectoryAncestors(this.paths.root);
      await lstatDirectory(this.paths.profiles);
      projectNames = await readdir(this.paths.profiles);
    } catch (error) {
      if (isNotFound(error)) return [];
      throw error;
    }
    const entries: Array<{ path: string; reference: ProfileReference }> = [];
    for (const projectId of projectNames.sort()) {
      if (projectId === INSTALL_LOCK_FILENAME) {
        await lstatFile(join(this.paths.profiles, projectId));
        continue;
      }
      validateRegistryProjectId(projectId);
      const project = join(this.paths.profiles, projectId);
      assertContained(this.paths.profiles, project);
      await lstatDirectory(project);
      for (const revisionName of (await readdir(project)).sort()) {
        if (!REVISION_PATTERN.test(revisionName)) throw registryError("PROFILE_REGISTRY_CORRUPT");
        const revision = Number(revisionName);
        if (!Number.isSafeInteger(revision) || String(revision) !== revisionName) throw registryError("PROFILE_REGISTRY_CORRUPT");
        const revisionPath = join(project, revisionName);
        assertContained(project, revisionPath);
        await lstatDirectory(revisionPath);
        const files = await readdir(revisionPath);
        if (files.length !== 1) throw registryError("PROFILE_REGISTRY_CORRUPT");
        const file = files[0]!;
        const match = PROFILE_FILE_PATTERN.exec(file);
        if (match === null) throw registryError("PROFILE_REGISTRY_CORRUPT");
        const profileSha256 = match[1]!;
        const path = join(revisionPath, file);
        assertContained(revisionPath, path);
        await lstatFile(path);
        entries.push({ path, reference: { projectId, profileRevision: revision, profileSha256 } });
      }
    }
    return entries.sort((left, right) =>
      left.reference.projectId.localeCompare(right.reference.projectId) ||
      left.reference.profileRevision - right.reference.profileRevision ||
      left.reference.profileSha256.localeCompare(right.reference.profileSha256)
    );
  }

  private async publish(directory: FileIdentity, destination: string, bytes: Buffer): Promise<void> {
    const temporary = join(dirname(destination), `.${basename(destination)}.${process.pid}.${randomUUID()}.tmp`);
    let handle: Awaited<ReturnType<typeof open>> | undefined;
    try {
      await lstatDirectory(dirname(destination));
      handle = await open(
        temporary,
        constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW,
        0o600
      );
      await handle.writeFile(bytes);
      await handle.sync();
      await handle.close();
      handle = undefined;
      await lstatFile(temporary);
      await this.testHooks?.afterTemporaryCreated?.();
      await lstatDirectory(dirname(destination));
      // link(2) publishes the completed file atomically and fails with EEXIST, unlike rename(2)'s replacement semantics.
      await link(temporary, destination);
      await syncDirectory(dirname(destination), directory);
      await unlink(temporary);
      await syncDirectory(dirname(destination), directory);
    } catch (error) {
      if (handle !== undefined) await handle.close();
      try {
        const current = await lstat(temporary);
        if (current.isFile() && !current.isSymbolicLink()) await unlink(temporary);
      } catch {
        // The original publication failure is more useful than a cleanup failure.
      }
      if (isAlreadyExists(error)) throw registryError("PROFILE_REVISION_CONFLICT");
      throw error;
    }
  }

  private async withEvent<T>(
    operation: ProfileRegistryEvent["operation"],
    reference: ProfileReference | undefined,
    action: () => Promise<T>
  ): Promise<T> {
    const started = this.now();
    try {
      const result = await action();
      this.emit(operation, "ok", reference, started);
      return result;
    } catch (error) {
      this.emit(operation, "error", reference, started);
      throw error;
    }
  }

  private async withInstallEvent(action: () => Promise<InstalledProfile>): Promise<InstalledProfile> {
    const started = this.now();
    try {
      const result = await action();
      this.emit("install", "ok", profileReference(result), started);
      return result;
    } catch (error) {
      this.emit("install", "error", undefined, started);
      throw error;
    }
  }

  private emit(
    operation: ProfileRegistryEvent["operation"],
    status: ProfileRegistryEvent["status"],
    reference: ProfileReference | undefined,
    started: number
  ): void {
    try {
      this.record?.({
        operation,
        status,
        ...(reference === undefined ? {} : {
          projectId: reference.projectId,
          revision: reference.profileRevision,
          profileSha256: reference.profileSha256
        }),
        elapsedMs: Math.max(0, this.now() - started)
      });
    } catch {
      // Observability must not change registry behavior.
    }
  }
}
