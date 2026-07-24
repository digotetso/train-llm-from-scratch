import assert from "node:assert/strict";
import { chmod, lstat, mkdtemp, mkdir, readFile, readdir, rename, symlink, writeFile } from "node:fs/promises";
import test from "node:test";
import { join, relative } from "node:path";
import { ProfileRegistry } from "../src/bridge/profile-registry.ts";
import { exporterPaths, projectPaths } from "../src/bridge/paths.ts";
import { PROFILE_LIMITS } from "../src/shared/limits.ts";
import { canonicalProfileJson, profileReference } from "../src/shared/project-profile.ts";
import { makeFixtureProfile, makeVideo001Profile } from "./helpers/profile.ts";

async function registryFixture(): Promise<{ root: string; registry: ProfileRegistry }> {
  const root = await mkdtemp("/private/tmp/video001-profile-registry-");
  return { root, registry: new ProfileRegistry(exporterPaths(root)) };
}

function revisionPath(root: string, projectId: string, revision: number): string {
  return join(root, "profiles", projectId, String(revision));
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

  const second = await registryFixture();
  const safe = await second.registry.installValue(makeFixtureProfile());
  const safePath = join(revisionPath(second.root, "fixture-two", 2), `${safe.profileSha256}.figma-ae-project.json`);
  const outside = join(second.root, "outside.json");
  await writeFile(outside, "{}", { mode: 0o600 });
  await chmod(safePath, 0o600);
  await rename(safePath, `${safePath}.real`);
  await symlink(outside, safePath);
  await assert.rejects(second.registry.resolve(profileReference(safe)), /PROFILE_REGISTRY_UNSAFE_PATH/);
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

test("cleans temporary files after an atomic publication failure", async () => {
  const { root, registry } = await registryFixture();
  const profile = makeFixtureProfile();
  await mkdir(revisionPath(root, "fixture-two", 2), { recursive: true, mode: 0o700 });
  const path = join(revisionPath(root, "fixture-two", 2), "f".repeat(64) + ".figma-ae-project.json");
  await symlink(join(root, "missing-target"), path);

  await assert.rejects(registry.installValue(profile), /PROFILE_REGISTRY_UNSAFE_PATH/);
  assert.deepEqual((await readdir(revisionPath(root, "fixture-two", 2))).filter((name) => name.includes(".tmp")), []);
});

test("enforces the maximum installed immutable profile count", async () => {
  const { registry } = await registryFixture();
  const value = makeFixtureProfile();
  for (let revision = 1; revision <= PROFILE_LIMITS.maxInstalledProfiles; revision += 1) {
    (value.project as Record<string, unknown>).revision = revision;
    await registry.installValue(structuredClone(value));
  }
  (value.project as Record<string, unknown>).revision = PROFILE_LIMITS.maxInstalledProfiles + 1;
  await assert.rejects(registry.installValue(value), /PROFILE_REGISTRY_CAPACITY/);
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
