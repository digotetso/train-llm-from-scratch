import assert from "node:assert/strict";
import { chmod, lstat, mkdtemp, mkdir, readFile, readdir, rename, symlink, unlink, writeFile } from "node:fs/promises";
import test from "node:test";
import { join, relative } from "node:path";
import { ProfileRegistry } from "../src/bridge/profile-registry.ts";
import { ProfileRegistryCore, realProfileRegistryFilesystem, type ProfileRegistryFilesystem } from "../src/bridge/profile-registry-internal.ts";
import { exporterPaths, legacyExporterPaths, projectPaths } from "../src/bridge/paths.ts";
import { QueueStore } from "../src/bridge/queue.ts";
import { PROFILE_LIMITS } from "../src/shared/limits.ts";
import { canonicalProfileJson, profileReference } from "../src/shared/project-profile.ts";
import { makeFixtureProfile, makeVideo001Profile } from "./helpers/profile.ts";

async function registryFixture(): Promise<{ root: string; registry: ProfileRegistry }> {
  const root = await mkdtemp("/private/tmp/video001-profile-registry-");
  return { root, registry: new ProfileRegistry(exporterPaths(root)) };
}

async function typescriptFiles(root: string): Promise<string[]> {
  const files: string[] = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const path = join(root, entry.name);
    if (entry.isDirectory()) files.push(...await typescriptFiles(path));
    else if (entry.isFile() && entry.name.endsWith(".ts")) files.push(path);
  }
  return files;
}

function revisionPath(root: string, projectId: string, revision: number): string {
  return join(root, "profiles", projectId, String(revision));
}

function deferred<T = void>(): { promise: Promise<T>; resolve(value: T): void } {
  let resolve!: (value: T) => void;
  return { promise: new Promise<T>((complete) => { resolve = complete; }), resolve };
}

function coreRegistry(root: string, filesystem: Readonly<ProfileRegistryFilesystem> = realProfileRegistryFilesystem): ProfileRegistryCore {
  return new ProfileRegistryCore(exporterPaths(root), filesystem);
}

test("installs a canonical immutable profile with private permissions", async () => {
  const { root, registry } = await registryFixture();
  const installed = await registry.installValue(makeVideo001Profile());
  const path = join(revisionPath(root, "video-001", 1), `${installed.profileSha256}.figma-ae-project.json`);

  assert.deepEqual(await registry.resolve(profileReference(installed)), installed);
  assert.equal(await readFile(path, "utf8"), canonicalProfileJson(installed.profile));
  assert.equal((await lstat(path)).mode & 0o777, 0o600);
  assert.equal((await lstat(join(root, "profiles"))).mode & 0o777, 0o700);
});

test("reinstalls identical immutable profile idempotently", async () => {
  const { root, registry } = await registryFixture();
  const first = await registry.installValue(makeVideo001Profile());
  const second = await registry.installValue(makeVideo001Profile());

  assert.deepEqual(second, first);
  assert.deepEqual(await readdir(revisionPath(root, "video-001", 1)), [`${first.profileSha256}.figma-ae-project.json`]);
});

test("rejects different bytes at an installed project revision", async () => {
  const { registry } = await registryFixture();
  const installed = await registry.installValue(makeVideo001Profile());
  const changed = makeVideo001Profile();
  (changed.project as Record<string, unknown>).displayName += " changed";

  await assert.rejects(registry.installValue(changed), /PROFILE_REVISION_CONFLICT/);
  assert.deepEqual(await registry.resolve(profileReference(installed)), installed);
});

test("derives a sorted listing from immutable profile files", async () => {
  const { registry } = await registryFixture();
  const video = makeVideo001Profile();
  const fixture = makeFixtureProfile();
  await registry.installValue(video);
  await registry.installValue(fixture);

  assert.deepEqual(
    (await registry.list()).map((summary) => `${summary.projectId}:${summary.revision}`),
    ["fixture-two:2", "video-001:1"]
  );
});

test("resolves only the exact immutable project revision and hash", async () => {
  const { registry } = await registryFixture();
  const installed = await registry.installValue(makeFixtureProfile());

  await assert.rejects(
    registry.resolve({ ...profileReference(installed), profileSha256: "a".repeat(64) }),
    /PROFILE_NOT_FOUND/
  );
  await assert.rejects(
    registry.resolve({ ...profileReference(installed), profileRevision: installed.profile.project.revision + 1 }),
    /PROFILE_NOT_FOUND/
  );
  assert.deepEqual(await registry.resolve(profileReference(installed)), installed);
  assert.deepEqual((await registry.projection(profileReference(installed))).reference, profileReference(installed));
});

test("rejects corrupt or symlinked registry entries", async () => {
  const { root, registry } = await registryFixture();
  const installed = await registry.installValue(makeFixtureProfile());
  const path = join(revisionPath(root, "fixture-two", 2), `${installed.profileSha256}.figma-ae-project.json`);
  await writeFile(path, "{}", { mode: 0o600 });
  await assert.rejects(registry.resolve(profileReference(installed)), /PROFILE_REGISTRY_CORRUPT/);
  await assert.rejects(registry.list(), /PROFILE_REGISTRY_CORRUPT/);

  const second = await registryFixture();
  const safe = await second.registry.installValue(makeFixtureProfile());
  const safePath = join(revisionPath(second.root, "fixture-two", 2), `${safe.profileSha256}.figma-ae-project.json`);
  const outside = join(second.root, "outside.json");
  await writeFile(outside, "{}", { mode: 0o600 });
  await chmod(safePath, 0o600);
  await rename(safePath, `${safePath}.real`);
  await symlink(outside, safePath);
  await assert.rejects(second.registry.resolve(profileReference(safe)), /PROFILE_REGISTRY_UNSAFE_PATH/);
  await unlink(`${safePath}.real`);
  await assert.rejects(second.registry.list(), /PROFILE_REGISTRY_UNSAFE_PATH/);
});

test("rejects a symlink in every registry-root ancestor", async () => {
  const base = await mkdtemp("/private/tmp/video001-profile-registry-ancestor-");
  const root = join(base, "root");
  await mkdir(root, { mode: 0o700 });
  const direct = new ProfileRegistry(exporterPaths(root));
  await direct.installValue(makeFixtureProfile());
  const alias = join(base, "alias");
  await symlink(base, alias);
  const throughSymlink = new ProfileRegistry(exporterPaths(join(alias, "root")));

  await assert.rejects(throughSymlink.list(), /PROFILE_REGISTRY_UNSAFE_PATH/);
});

test("rejects unsafe project identifiers before deriving project paths", () => {
  const paths = exporterPaths("/tmp/video001-profile-paths");
  for (const projectId of ["../escape", "video/001", "VIDEO-001", "a".repeat(65)]) {
    assert.throws(() => projectPaths(paths, projectId), /unsafe project ID/);
  }
});

test("derives contained project-scoped paths", () => {
  const paths = exporterPaths("/tmp/video001-profile-paths");
  const project = projectPaths(paths, "video-001");
  assert.deepEqual(project, {
    root: join(paths.projects, "video-001"),
    incoming: join(paths.projects, "video-001", "incoming"),
    quarantine: join(paths.projects, "video-001", "quarantine"),
    assets: join(paths.projects, "video-001", "assets"),
    logs: join(paths.projects, "video-001", "logs"),
    tmp: join(paths.projects, "video-001", "tmp")
  });
  for (const path of Object.values(project)) assert.equal(relative(paths.projects, path).startsWith(".."), false);
});

test("exposes only generic own path keys and an explicit legacy queue adapter", async () => {
  const root = await mkdtemp("/private/tmp/video001-profile-paths-");
  const generic = exporterPaths(root);
  assert.deepEqual(Object.getOwnPropertyNames(generic).sort(), ["auth", "profiles", "projects", "root", "tmp"]);
  const legacy = legacyExporterPaths(root);
  assert.deepEqual(Object.keys(legacy).sort(), ["assets", "incoming", "logs", "quarantine", "root", "tmp"]);
  assert.deepEqual(new QueueStore(root).paths, legacy);
});

test("keeps the internal registry core package-private by import convention", async () => {
  const importers: string[] = [];
  for (const path of [...await typescriptFiles("src"), ...await typescriptFiles("tests")]) {
    if ((await readFile(path, "utf8")).includes("profile-registry-internal.ts")) importers.push(path);
  }
  assert.deepEqual(importers.sort(), ["src/bridge/profile-registry.ts", "tests/profile-registry.test.ts"]);
});

test("recovers failed publication by removing its temporary file and created empty directories", async () => {
  const { root } = await registryFixture();
  let failOnce = true;
  const registry = coreRegistry(root, {
    ...realProfileRegistryFilesystem,
    link: async (...args) => {
      if (failOnce) { failOnce = false; throw new Error("INJECTED_TEMP_FAILURE"); }
      return realProfileRegistryFilesystem.link(...args);
    }
  });
  await assert.rejects(registry.installValue(makeFixtureProfile()), /INJECTED_TEMP_FAILURE/);
  await assert.rejects(lstat(revisionPath(root, "fixture-two", 2)), { code: "ENOENT" });
  await assert.rejects(lstat(join(root, "profiles", "fixture-two")), { code: "ENOENT" });
  assert.equal((await registry.installValue(makeFixtureProfile())).profile.project.id, "fixture-two");
});

test("recovers a directory created before its parent fsync fails", async () => {
  const { root } = await registryFixture();
  const project = join(root, "profiles", "fixture-two");
  let failProjectParentSync = true;
  const registry = coreRegistry(root, {
    ...realProfileRegistryFilesystem,
    open: async (...args) => {
      const handle = await realProfileRegistryFilesystem.open(...args);
      if (failProjectParentSync && String(args[0]) === project) {
        return new Proxy(handle, {
          get(target, property) {
            if (property === "sync") return async () => {
              failProjectParentSync = false;
              throw new Error("INJECTED_PROJECT_PARENT_FSYNC_FAILURE");
            };
            const value = Reflect.get(target, property, target);
            return typeof value === "function" ? value.bind(target) : value;
          }
        });
      }
      return handle;
    }
  });

  await assert.rejects(registry.installValue(makeFixtureProfile()), /INJECTED_PROJECT_PARENT_FSYNC_FAILURE/);
  assert.deepEqual(await registry.list(), []);
  assert.equal((await registry.installValue(makeFixtureProfile())).profile.project.id, "fixture-two");
});

test("list releases its snapshot lock before validating immutable profile content", async () => {
  const { root, registry } = await registryFixture();
  const installed = await registry.installValue(makeFixtureProfile());
  const profilePath = join(revisionPath(root, "fixture-two", 2), `${installed.profileSha256}.figma-ae-project.json`);
  const reading = deferred();
  const releaseRead = deferred();
  let pauseRead = true;
  const reader = coreRegistry(root, {
    ...realProfileRegistryFilesystem,
    open: async (...args) => {
      if (pauseRead && String(args[0]) === profilePath) {
        pauseRead = false;
        reading.resolve();
        await releaseRead.promise;
      }
      return realProfileRegistryFilesystem.open(...args);
    }
  });
  const next = makeFixtureProfile();
  (next.project as Record<string, unknown>).revision = 3;
  let listingSettled = false;
  const listing = reader.list().then((result) => { listingSettled = true; return result; });
  await reading.promise;
  let writerFinished = false;
  const writer = coreRegistry(root).installValue(next).then(() => { writerFinished = true; });

  try {
    await Promise.race([
      writer,
      new Promise<void>((_resolve, reject) => setTimeout(() => reject(new Error("writer blocked by list content read")), 250))
    ]);
    assert.equal(writerFinished, true);
    assert.equal(listingSettled, false);
  } finally {
    releaseRead.resolve();
  }
  await writer;
  assert.deepEqual((await listing).map((summary) => `${summary.projectId}:${summary.revision}`), ["fixture-two:2"]);
});

test("cleans an acquired lock after a later lock fsync failure", async () => {
  const { root } = await registryFixture();
  let failLockSync = true;
  let failIdentityCheck = false;
  const registry = coreRegistry(root, {
    ...realProfileRegistryFilesystem,
    open: async (...args) => {
      const handle = await realProfileRegistryFilesystem.open(...args);
      if (failLockSync && String(args[0]).endsWith(".profile-registry.install.lock")) {
        return new Proxy(handle, {
          get(target, property) {
            if (property === "sync") return async () => {
              failLockSync = false;
              failIdentityCheck = true;
              throw new Error("INJECTED_LOCK_FSYNC_FAILURE");
            };
            const value = Reflect.get(target, property, target);
            return typeof value === "function" ? value.bind(target) : value;
          }
        });
      }
      return handle;
    },
    lstat: async (path) => {
      if (failIdentityCheck && String(path).endsWith(".profile-registry.install.lock")) {
        failIdentityCheck = false;
        throw new Error("INJECTED_LOCK_IDENTITY_FAILURE");
      }
      return realProfileRegistryFilesystem.lstat(path);
    }
  });

  await assert.rejects(registry.installValue(makeFixtureProfile()), /INJECTED_LOCK_FSYNC_FAILURE/);
  await assert.rejects(lstat(join(root, "profiles", ".profile-registry.install.lock")), { code: "ENOENT" });
  assert.equal((await registry.installValue(makeFixtureProfile())).profile.project.id, "fixture-two");
});

test("fails closed when the first lock fstat cannot establish an inode identity", async () => {
  const { root } = await registryFixture();
  let failFirstLockStat = true;
  const registry = coreRegistry(root, {
    ...realProfileRegistryFilesystem,
    open: async (...args) => {
      const handle = await realProfileRegistryFilesystem.open(...args);
      if (failFirstLockStat && String(args[0]).endsWith(".profile-registry.install.lock")) {
        return new Proxy(handle, {
          get(target, property) {
            if (property === "stat") return async () => {
              failFirstLockStat = false;
              throw new Error("INJECTED_FIRST_LOCK_FSTAT_FAILURE");
            };
            const value = Reflect.get(target, property, target);
            return typeof value === "function" ? value.bind(target) : value;
          }
        });
      }
      return handle;
    }
  });

  await assert.rejects(registry.installValue(makeFixtureProfile()), /INJECTED_FIRST_LOCK_FSTAT_FAILURE/);
  assert.equal((await lstat(join(root, "profiles", ".profile-registry.install.lock"))).isFile(), true);
});

test("fails with a bounded timeout while a stale lock remains", async () => {
  const { root } = await registryFixture();
  const profiles = join(root, "profiles");
  await mkdir(profiles, { mode: 0o700 });
  await writeFile(join(profiles, ".profile-registry.install.lock"), "", { mode: 0o600 });

  const started = performance.now();
  await assert.rejects(coreRegistry(root).installValue(makeFixtureProfile()), /PROFILE_REGISTRY_LOCKED/);
  assert.equal(performance.now() - started < 2_500, true);
});

test("retries an EEXIST lock race when the lock vanishes before inspection", async () => {
  const { root } = await registryFixture();
  let injectAlreadyExists = true;
  let injectNotFound = false;
  const registry = coreRegistry(root, {
    ...realProfileRegistryFilesystem,
    open: async (...args) => {
      if (injectAlreadyExists && String(args[0]).endsWith(".profile-registry.install.lock")) {
        injectAlreadyExists = false;
        injectNotFound = true;
        throw Object.assign(new Error("synthetic lock race"), { code: "EEXIST" });
      }
      return realProfileRegistryFilesystem.open(...args);
    },
    lstat: async (path) => {
      if (injectNotFound && String(path).endsWith(".profile-registry.install.lock")) {
        injectNotFound = false;
        throw Object.assign(new Error("synthetic vanished lock"), { code: "ENOENT" });
      }
      return realProfileRegistryFilesystem.lstat(path);
    }
  });

  assert.equal((await registry.installValue(makeFixtureProfile())).profile.project.id, "fixture-two");
});

test("list waits for a staging installation and observes only the completed immutable profile", async () => {
  const { root } = await registryFixture();
  const staged = deferred();
  const release = deferred();
  let pausePublication = true;
  const writer = coreRegistry(root, {
    ...realProfileRegistryFilesystem,
    link: async (...args) => {
      if (pausePublication) {
        pausePublication = false;
        staged.resolve();
        await release.promise;
      }
      return realProfileRegistryFilesystem.link(...args);
    }
  });
  const listAttempted = deferred();
  let listSettled = false;
  const reader = coreRegistry(root, {
    ...realProfileRegistryFilesystem,
    open: async (...args) => {
      if (String(args[0]).endsWith(".profile-registry.install.lock")) listAttempted.resolve();
      return realProfileRegistryFilesystem.open(...args);
    }
  });

  const installation = writer.installValue(makeFixtureProfile());
  await staged.promise;
  const listing = reader.list().then((result) => { listSettled = true; return result; });
  await listAttempted.promise;
  assert.equal(listSettled, false);
  release.resolve();
  assert.equal((await installation).profile.project.id, "fixture-two");
  assert.deepEqual((await listing).map((summary) => `${summary.projectId}:${summary.revision}`), ["fixture-two:2"]);
});

test("serializes concurrent identical and conflicting revisions across registry instances", async () => {
  const { root } = await registryFixture();
  const acquired = deferred();
  const release = deferred();
  let pauseFirstLock = true;
  const first = coreRegistry(root, {
    ...realProfileRegistryFilesystem,
    open: async (...args) => {
      const handle = await realProfileRegistryFilesystem.open(...args);
      if (pauseFirstLock && String(args[0]).endsWith(".profile-registry.install.lock")) {
        pauseFirstLock = false;
        acquired.resolve();
        await release.promise;
      }
      return handle;
    }
  });
  const second = coreRegistry(root);
  const install = first.installValue(makeFixtureProfile());
  await acquired.promise;
  const same = second.installValue(makeFixtureProfile());
  release.resolve();
  assert.deepEqual(await install, await same);

  const changed = makeFixtureProfile();
  (changed.project as Record<string, unknown>).revision = 3;
  const conflicting = structuredClone(changed);
  (conflicting.project as Record<string, unknown>).displayName = "Fixture Three";
  const outcomes = await Promise.allSettled([first.installValue(changed), second.installValue(conflicting)]);
  assert.equal(outcomes.filter((outcome) => outcome.status === "fulfilled").length, 1);
  assert.equal(outcomes.filter((outcome) => outcome.status === "rejected").length, 1);
  assert.match((outcomes.find((outcome) => outcome.status === "rejected") as PromiseRejectedResult).reason.message, /PROFILE_REVISION_CONFLICT/);
});

test("serializes the installed-profile capacity limit across registry instances", async () => {
  const { root, registry } = await registryFixture();
  const value = makeFixtureProfile();
  for (let revision = 1; revision < PROFILE_LIMITS.maxInstalledProfiles; revision += 1) {
    (value.project as Record<string, unknown>).revision = revision;
    await registry.installValue(structuredClone(value));
  }
  const acquired = deferred();
  const release = deferred();
  let pauseFirstLock = true;
  const first = coreRegistry(root, {
    ...realProfileRegistryFilesystem,
    open: async (...args) => {
      const handle = await realProfileRegistryFilesystem.open(...args);
      if (pauseFirstLock && String(args[0]).endsWith(".profile-registry.install.lock")) {
        pauseFirstLock = false;
        acquired.resolve();
        await release.promise;
      }
      return handle;
    }
  });
  const second = coreRegistry(root);
  (value.project as Record<string, unknown>).revision = PROFILE_LIMITS.maxInstalledProfiles;
  const last = first.installValue(structuredClone(value));
  await acquired.promise;
  (value.project as Record<string, unknown>).revision = PROFILE_LIMITS.maxInstalledProfiles + 1;
  const over = second.installValue(structuredClone(value));
  release.resolve();
  await last;
  await assert.rejects(over, /PROFILE_REGISTRY_CAPACITY/);
  assert.equal((await registry.list()).length, PROFILE_LIMITS.maxInstalledProfiles);
});

test("fsyncs each new registry directory's parent before installing", async () => {
  const { root } = await registryFixture();
  const synced: string[] = [];
  const registry = coreRegistry(root, {
    ...realProfileRegistryFilesystem,
    open: async (...args) => {
      const handle = await realProfileRegistryFilesystem.open(...args);
      const path = String(args[0]);
      return new Proxy(handle, {
        get(target, property) {
          if (property === "sync") return async () => { synced.push(path); return target.sync(); };
          const value = Reflect.get(target, property, target);
          return typeof value === "function" ? value.bind(target) : value;
        }
      });
    }
  });
  await registry.installValue(makeFixtureProfile());
  for (const parent of [root, join(root, "profiles"), join(root, "profiles", "fixture-two")]) {
    assert.equal(synced.includes(parent), true, parent);
  }
});

test("normalizes a source path before opening it and permits ordinary source directories", async () => {
  const base = await mkdtemp("/private/tmp/video001-profile-source-");
  const root = join(base, "registry");
  const source = join(base, "profile.json");
  await mkdir(root, { mode: 0o700 });
  await writeFile(source, JSON.stringify(makeFixtureProfile()));
  await chmod(base, 0o755);
  const link = join(base, "link");
  await symlink("/private/tmp", link);
  const installed = await new ProfileRegistry(exporterPaths(root)).installFile(`${base}/link/../profile.json`);
  assert.equal(installed.profile.project.id, "fixture-two");
});

test("emits redacted install, list, and resolve events", async () => {
  const events: unknown[] = [];
  let now = 10;
  const { root } = await registryFixture();
  const registry = new ProfileRegistry(exporterPaths(root), {
    now: () => now++,
    record: (event) => events.push(event)
  });
  const source = join(root, "source-profile.json");
  await writeFile(source, JSON.stringify(makeFixtureProfile()));
  const installed = await registry.installFile(source);
  await registry.list();
  await registry.resolve(profileReference(installed));

  assert.deepEqual((events as Array<{ operation: string; status: string }>).map(({ operation, status }) => `${operation}:${status}`), [
    "install:ok", "list:ok", "resolve:ok"
  ]);
  assert.deepEqual((events[0] as Record<string, unknown>), {
    operation: "install",
    status: "ok",
    projectId: installed.profile.project.id,
    revision: installed.profile.project.revision,
    profileSha256: installed.profileSha256,
    elapsedMs: 1
  });
  const serialized = JSON.stringify(events);
  assert.equal(serialized.includes(source), false);
  assert.equal(serialized.includes(JSON.stringify(installed.profile)), false);
  assert.equal(serialized.includes(installed.profile.source.fileKey), false);
});

test("records malformed resolve references as redacted errors", async () => {
  const events: unknown[] = [];
  const { root } = await registryFixture();
  const registry = new ProfileRegistry(exporterPaths(root), { record: (event) => events.push(event) });
  await assert.rejects(
    registry.resolve({ projectId: "../escape", profileRevision: 1, profileSha256: "a".repeat(64) }),
    /PROFILE_REGISTRY_UNSAFE_PATH/
  );
  assert.deepEqual(events, [{ operation: "resolve", status: "error", elapsedMs: events[0] instanceof Object ? (events[0] as { elapsedMs: number }).elapsedMs : 0 }]);
  assert.equal(JSON.stringify(events).includes("../escape"), false);
});
