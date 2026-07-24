import { constants } from "node:fs";
import type { Stats } from "node:fs";
import * as nodeFs from "node:fs/promises";
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

/** Non-public filesystem boundary for deterministic registry tests. */
export interface ProfileRegistryFilesystem {
  link: typeof nodeFs.link;
  lstat: (path: string) => Promise<Stats>;
  mkdir: typeof nodeFs.mkdir;
  open: typeof nodeFs.open;
  readdir: typeof nodeFs.readdir;
  rmdir: typeof nodeFs.rmdir;
  unlink: typeof nodeFs.unlink;
}

export const realProfileRegistryFilesystem: Readonly<ProfileRegistryFilesystem> = Object.freeze({
  link: nodeFs.link,
  lstat: nodeFs.lstat,
  mkdir: nodeFs.mkdir,
  open: nodeFs.open,
  readdir: nodeFs.readdir,
  rmdir: nodeFs.rmdir,
  unlink: nodeFs.unlink
});

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

export interface ProfileRegistryCoreOptions {
  now?: () => number;
  record?: (event: ProfileRegistryEvent) => void;
}

interface HeldInstallLock {
  path: string;
  identity: FileIdentity;
}

interface FileIdentity {
  device: number;
  inode: number;
}

interface CreatedDirectory {
  path: string;
  identity: FileIdentity;
  parentPath: string;
  parentIdentity: FileIdentity;
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

async function lstatDirectory(filesystem: Readonly<ProfileRegistryFilesystem>, path: string, requirePrivate = true): Promise<FileIdentity> {
  const details = await filesystem.lstat(path);
  if (!details.isDirectory() || details.isSymbolicLink()) throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
  if (requirePrivate) assertPrivateMode(details.mode, 0o700);
  return asFileIdentity(details);
}

async function lstatFile(filesystem: Readonly<ProfileRegistryFilesystem>, path: string, requirePrivate = true): Promise<FileIdentity> {
  const details = await filesystem.lstat(path);
  if (!details.isFile() || details.isSymbolicLink()) throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
  if (requirePrivate) assertPrivateMode(details.mode, 0o600);
  return asFileIdentity(details);
}

async function ensurePrivateDirectory(
  filesystem: Readonly<ProfileRegistryFilesystem>,
  path: string,
  onCreated?: (directory: CreatedDirectory) => void,
): Promise<FileIdentity> {
  const resolved = resolve(path);
  const segments = resolved.split(sep).filter(Boolean);
  let current = resolved.startsWith(sep) ? sep : "";
  for (const segment of segments) {
    current = current === sep ? join(current, segment) : current === "" ? segment : join(current, segment);
    try {
      await lstatDirectory(filesystem, current, current === resolved);
    } catch (error) {
      if (!isNotFound(error)) throw error;
      const parent = dirname(current);
      const parentIdentity = await lstatDirectory(filesystem, parent, false);
      let created = false;
      try {
        await filesystem.mkdir(current, { mode: 0o700 });
        created = true;
      } catch (mkdirError) {
        if (!isAlreadyExists(mkdirError)) throw mkdirError;
      }
      const identity = await lstatDirectory(filesystem, current, true);
      await syncDirectory(filesystem, parent, parentIdentity, false);
      if (created) onCreated?.({ path: current, identity, parentPath: parent, parentIdentity });
    }
  }
  return lstatDirectory(filesystem, resolved);
}

async function assertSafeExistingDirectoryAncestors(filesystem: Readonly<ProfileRegistryFilesystem>, path: string, requirePrivateFinal = true): Promise<void> {
  const resolved = resolve(path);
  const segments = resolved.split(sep).filter(Boolean);
  let current = resolved.startsWith(sep) ? sep : "";
  for (const segment of segments) {
    current = current === sep ? join(current, segment) : current === "" ? segment : join(current, segment);
    await lstatDirectory(filesystem, current, current === resolved && requirePrivateFinal);
  }
}

async function syncDirectory(filesystem: Readonly<ProfileRegistryFilesystem>, path: string, expected?: FileIdentity, requirePrivate = true): Promise<void> {
  await assertSafeExistingDirectoryAncestors(filesystem, path, requirePrivate);
  const handle = await filesystem.open(path, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const details = await handle.stat();
    if (!details.isDirectory() || (expected !== undefined && !sameIdentity(asFileIdentity(details), expected))) {
      throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
    }
    await handle.sync();
  } finally {
    await handle.close();
  }
  await assertSafeExistingDirectoryAncestors(filesystem, path, requirePrivate);
}

async function readRegularFile(filesystem: Readonly<ProfileRegistryFilesystem>, path: string, requirePrivate = true): Promise<Buffer> {
  await assertSafeExistingDirectoryAncestors(filesystem, dirname(path), requirePrivate);
  const before = await lstatFile(filesystem, path, requirePrivate);
  const handle = await filesystem.open(path, constants.O_RDONLY | constants.O_NOFOLLOW);
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

async function readInstalled(filesystem: Readonly<ProfileRegistryFilesystem>, path: string, expected: ProfileReference): Promise<InstalledProfile> {
  let parsed: unknown;
  try {
    parsed = JSON.parse((await readRegularFile(filesystem, path)).toString("utf8")) as unknown;
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
  const persisted = await readRegularFile(filesystem, path);
  if (!persisted.equals(canonical)) throw registryError("PROFILE_REGISTRY_CORRUPT");
  return installed;
}

export class ProfileRegistryCore {
  private readonly paths: GenericExporterPaths;
  private readonly filesystem: Readonly<ProfileRegistryFilesystem>;
  private readonly now: () => number;
  private readonly record: ((event: ProfileRegistryEvent) => void) | undefined;

  constructor(paths: GenericExporterPaths, filesystem: Readonly<ProfileRegistryFilesystem>, options: ProfileRegistryCoreOptions = {}) {
    this.paths = validatePaths(paths);
    this.filesystem = filesystem;
    this.now = options.now ?? Date.now;
    this.record = options.record;
  }

  async installFile(sourcePath: string): Promise<InstalledProfile> {
    return this.withInstallEvent(async () => {
      if (!isAbsolute(sourcePath)) throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
      const canonicalSourcePath = resolve(sourcePath);
      let value: unknown;
      try {
        value = JSON.parse((await readRegularFile(this.filesystem, canonicalSourcePath, false)).toString("utf8")) as unknown;
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
    return this.withEvent("list", undefined, () => this.withInstallLock(async () => {
      const entries = await this.entries();
      const summaries: ProfileSummary[] = [];
      for (const entry of entries) summaries.push(profileSummary(await readInstalled(this.filesystem, entry.path, entry.reference)));
      return summaries;
    }));
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
        const installed = await readInstalled(this.filesystem, path, safeReference);
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
        return readInstalled(this.filesystem, destination, reference);
      }
      if (existing.length >= PROFILE_LIMITS.maxInstalledProfiles) throw registryError("PROFILE_REGISTRY_CAPACITY");
      const createdDirectories: CreatedDirectory[] = [];
      try {
        const directory = await this.ensureRevisionDirectory(reference.projectId, reference.profileRevision, true, createdDirectories);
        const bytes = Buffer.from(canonicalProfileJson(installed.profile), "utf8");
        await this.publish(directory, destination, bytes);
        return readInstalled(this.filesystem, destination, reference);
      } catch (error) {
        await this.cleanupCreatedDirectories(createdDirectories);
        throw error;
      }
    });
  }

  private async withInstallLock<T>(action: () => Promise<T>): Promise<T> {
    const lock = await this.acquireInstallLock();
    try {
      return await action();
    } finally {
      await this.releaseInstallLock(lock);
    }
  }

  private async acquireInstallLock(): Promise<HeldInstallLock> {
    await ensurePrivateDirectory(this.filesystem, this.paths.root);
    const profilesIdentity = await ensurePrivateDirectory(this.filesystem, this.paths.profiles);
    const lockPath = join(this.paths.profiles, INSTALL_LOCK_FILENAME);
    assertContained(this.paths.profiles, lockPath);
    for (let attempt = 0; attempt < LOCK_RETRY_LIMIT; attempt += 1) {
      let handle: Awaited<ReturnType<typeof nodeFs.open>> | undefined;
      let acquired: HeldInstallLock | undefined;
      try {
        await assertSafeExistingDirectoryAncestors(this.filesystem, this.paths.profiles);
        handle = await this.filesystem.open(
          lockPath,
          constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW,
          0o600
        );
        const details = await handle.stat();
        if (!details.isFile()) throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
        acquired = { path: lockPath, identity: asFileIdentity(details) };
        await handle.sync();
        await handle.close();
        handle = undefined;
        const current = await lstatFile(this.filesystem, lockPath);
        if (!sameIdentity(current, acquired.identity)) throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
        await syncDirectory(this.filesystem, this.paths.profiles, profilesIdentity);
        return acquired;
      } catch (error) {
        if (handle !== undefined) {
          try { await handle.close(); } catch { /* cleanup below keeps the original failure */ }
        }
        if (acquired !== undefined) {
          await this.cleanupKnownLock(acquired, profilesIdentity);
          throw error;
        }
        // A first handle.stat() failure leaves us without an inode identity.
        // Do not unlink by pathname in that case: retaining a stale lock is the
        // safe, fail-closed outcome rather than risking an unrelated lock file.
        if (!isAlreadyExists(error)) throw error;
        try {
          await lstatFile(this.filesystem, lockPath);
        } catch (lstatError) {
          if (isNotFound(lstatError)) continue;
          throw lstatError;
        }
        await new Promise<void>((complete) => setTimeout(complete, LOCK_RETRY_DELAY_MS));
      }
    }
    throw registryError("PROFILE_REGISTRY_LOCKED");
  }

  private async releaseInstallLock(lock: HeldInstallLock): Promise<void> {
    const profilesIdentity = await lstatDirectory(this.filesystem, this.paths.profiles);
    await this.cleanupKnownLock(lock, profilesIdentity);
  }

  private async cleanupKnownLock(lock: HeldInstallLock, profilesIdentity: FileIdentity): Promise<void> {
    let current: FileIdentity | undefined;
    let lastError: unknown;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        current = await lstatFile(this.filesystem, lock.path);
        break;
      } catch (error) {
        lastError = error;
      }
    }
    if (current === undefined) throw lastError;
    if (!sameIdentity(current, lock.identity)) throw registryError("PROFILE_REGISTRY_UNSAFE_PATH");
    await this.filesystem.unlink(lock.path);
    await syncDirectory(this.filesystem, this.paths.profiles, profilesIdentity);
  }

  /**
   * Removes only directories this installation created, in reverse order.  Every
   * removal is identity-checked and limited to an empty directory, so a failed
   * publish cannot remove a pre-existing project directory or its contents.
   */
  private async cleanupCreatedDirectories(createdDirectories: readonly CreatedDirectory[]): Promise<void> {
    for (const directory of [...createdDirectories].reverse()) {
      try {
        const current = await lstatDirectory(this.filesystem, directory.path);
        const parent = await lstatDirectory(this.filesystem, directory.parentPath, false);
        if (!sameIdentity(current, directory.identity) || !sameIdentity(parent, directory.parentIdentity)) continue;
        if ((await this.filesystem.readdir(directory.path)).length !== 0) continue;
        await this.filesystem.rmdir(directory.path);
        await syncDirectory(this.filesystem, directory.parentPath, directory.parentIdentity, false);
      } catch {
        // Preserve the publication failure. A later operation will fail closed if cleanup was unsafe.
      }
    }
  }

  private async ensureRevisionDirectory(
    projectId: string,
    revision: number,
    create: boolean,
    createdDirectories: CreatedDirectory[] = []
  ): Promise<FileIdentity> {
    const profiles = this.paths.profiles;
    assertContained(this.paths.root, profiles);
    if (create) {
      await ensurePrivateDirectory(this.filesystem, this.paths.root);
      await ensurePrivateDirectory(this.filesystem, profiles);
    } else {
      await assertSafeExistingDirectoryAncestors(this.filesystem, this.paths.root);
      await lstatDirectory(this.filesystem, profiles);
    }
    const project = join(profiles, projectId);
    assertContained(profiles, project);
    if (create) {
      await ensurePrivateDirectory(this.filesystem, project, (directory) => {
        if (directory.path === project) createdDirectories.push(directory);
      });
    }
    else await lstatDirectory(this.filesystem, project);
    const revisionPath = join(project, String(revision));
    assertContained(project, revisionPath);
    if (create) {
      return ensurePrivateDirectory(this.filesystem, revisionPath, (directory) => {
        if (directory.path === revisionPath) createdDirectories.push(directory);
      });
    }
    return lstatDirectory(this.filesystem, revisionPath);
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
      await assertSafeExistingDirectoryAncestors(this.filesystem, this.paths.root);
      await lstatDirectory(this.filesystem, this.paths.profiles);
      projectNames = await this.filesystem.readdir(this.paths.profiles);
    } catch (error) {
      if (isNotFound(error)) return [];
      throw error;
    }
    const entries: Array<{ path: string; reference: ProfileReference }> = [];
    for (const projectId of projectNames.sort()) {
      if (projectId === INSTALL_LOCK_FILENAME) {
        await lstatFile(this.filesystem, join(this.paths.profiles, projectId));
        continue;
      }
      validateRegistryProjectId(projectId);
      const project = join(this.paths.profiles, projectId);
      assertContained(this.paths.profiles, project);
      await lstatDirectory(this.filesystem, project);
      for (const revisionName of (await this.filesystem.readdir(project)).sort()) {
        if (!REVISION_PATTERN.test(revisionName)) throw registryError("PROFILE_REGISTRY_CORRUPT");
        const revision = Number(revisionName);
        if (!Number.isSafeInteger(revision) || String(revision) !== revisionName) throw registryError("PROFILE_REGISTRY_CORRUPT");
        const revisionPath = join(project, revisionName);
        assertContained(project, revisionPath);
        await lstatDirectory(this.filesystem, revisionPath);
        const files = await this.filesystem.readdir(revisionPath);
        if (files.length !== 1) throw registryError("PROFILE_REGISTRY_CORRUPT");
        const file = files[0]!;
        const match = PROFILE_FILE_PATTERN.exec(file);
        if (match === null) throw registryError("PROFILE_REGISTRY_CORRUPT");
        const profileSha256 = match[1]!;
        const path = join(revisionPath, file);
        assertContained(revisionPath, path);
        await lstatFile(this.filesystem, path);
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
    let handle: Awaited<ReturnType<typeof nodeFs.open>> | undefined;
    try {
      await lstatDirectory(this.filesystem, dirname(destination));
      handle = await this.filesystem.open(
        temporary,
        constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW,
        0o600
      );
      await handle.writeFile(bytes);
      await handle.sync();
      await handle.close();
      handle = undefined;
      await lstatFile(this.filesystem, temporary);
      await lstatDirectory(this.filesystem, dirname(destination));
      // link(2) publishes the completed file atomically and fails with EEXIST, unlike rename(2)'s replacement semantics.
      await this.filesystem.link(temporary, destination);
      await syncDirectory(this.filesystem, dirname(destination), directory);
      await this.filesystem.unlink(temporary);
      await syncDirectory(this.filesystem, dirname(destination), directory);
    } catch (error) {
      if (handle !== undefined) await handle.close();
      let temporaryRemoved = false;
      try {
        const current = await this.filesystem.lstat(temporary);
        if (current.isFile() && !current.isSymbolicLink()) {
          await this.filesystem.unlink(temporary);
          temporaryRemoved = true;
        }
      } catch {
        // The original publication failure is more useful than a cleanup failure.
      }
      if (temporaryRemoved) {
        try {
          await syncDirectory(this.filesystem, dirname(destination), directory);
        } catch {
          // The original publication failure is more useful than a cleanup failure.
        }
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
