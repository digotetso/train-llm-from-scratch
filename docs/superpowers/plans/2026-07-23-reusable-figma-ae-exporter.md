# Reusable Figma to After Effects Exporter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Video 001-specific runtime with one portable, private,
profile-driven Figma-to-After-Effects plugin while preserving Video 001
fidelity, compatibility, and non-destructive behavior.

**Architecture:** A strict shared TypeScript profile contract feeds an immutable
local profile registry owned by the Node bridge. One Figma plugin discovers
authenticated profiles at runtime, and one ES3 After Effects palette installs
profiles and imports packages that reference an exact profile ID, revision, and
SHA-256. A compatibility adapter maps legacy Video 001 packages to the bundled
Video 001 profile.

**Tech Stack:** TypeScript 7, Node.js 20 ESM, Node test runner through `tsx`,
esbuild 0.28.1, Figma Plugin API typings 1.131.0, After Effects ES3
ExtendScript, Python/pytest repository integration checks, POSIX ustar/gzip
release tooling.

## Global Constraints

- Work only in the existing `feat/figma-ae-exporter` worktree.
- Preserve every pre-existing tracked and untracked change; never reset,
  checkout, or overwrite unrelated work.
- Use test-driven development: demonstrate the focused test failing for the
  intended reason before production edits, then make it pass.
- Use path-scoped staging and inspect every staged diff before committing.
- Runtime targets are macOS, Figma Desktop, After Effects 25.2 or newer, and
  Node.js 20 or newer.
- The release is private and portable; it is not a Figma Community plugin.
- The runtime remains loopback-only and adds no remote telemetry or service.
- Project profiles are declarative data only and cannot contain paths, URLs,
  scripts, commands, ports, credentials, or permission changes.
- Profile schema 1.0.0 accepts only seconds as the time unit.
- Generic package schema is 3.0.0 with media type
  `application/vnd.figma-ae+json` and suffix `.figma-ae.json`.
- Legacy `.video001-ae.json` support is isolated to the Video 001 compatibility
  adapter.
- Profiles cannot exceed 256 frames, 2,048 assets, 32 MiB per decoded asset,
  512 MiB aggregate decoded assets, 32 MiB manifest JSON, 768 MiB request body,
  or 120 seconds request time.
- The importer never closes, replaces, or saves the user's After Effects
  project.
- The deterministic archive excludes the recipient Figma plugin ID and
  generated recipient manifest.

---

## Planned File Structure

### New focused units

- `src/shared/project-profile.ts` — profile types, exact schema validation,
  public projection, summary, canonical hash input, and global ceilings.
- `src/bridge/profile-registry.ts` — immutable profile filesystem registry,
  secure install, list, resolve, and collision handling.
- `src/cli/profile-cli.ts` — `profile init|validate|inspect|install|list`
  command behavior with injected I/O for deterministic tests.
- `src/shared/legacy-video001.ts` — legacy package detection and conversion to
  an exact generic profile reference.
- `config/profiles/video-001.figma-ae-project.json` — ordinary bundled Video
  001 profile.
- `tests/fixtures/profiles/fixture-two.figma-ae-project.json` — non-Video 001
  project proving generic dimensions, frame rate, timing, frame count, and
  naming.
- `tests/project-profile.test.ts` — profile contract tests.
- `tests/profile-registry.test.ts` — registry security and immutability tests.
- `tests/profile-cli.test.ts` — CLI parser, wizard, and output tests.
- `tests/legacy-video001.test.ts` — compatibility adapter tests.

### Existing units to modify

- `src/shared/limits.ts` — generic global ceilings.
- `src/shared/contract.ts` — generic schema 3 package and profile reference.
- `src/bridge/paths.ts` — generic root and project-namespaced paths.
- `src/bridge/queue.ts` — generic package suffix and project-scoped queue.
- `src/bridge/server.ts` — authenticated profile routes and profile-aware
  export validation.
- `src/bridge/cli.ts` — generic lifecycle root and profile-registry injection.
- `src/figma/controller.ts` — runtime profile discovery and selection.
- `src/figma/ui.ts` and `src/figma/ui.html` — profile selector and generic copy.
- `src/ae/import-core.jsxinc` — generic version and duplicate markers.
- `src/ae/importer.jsxinc` — profile loading, validation, generic timing and
  naming, and legacy adaptation.
- `src/ae/panel.jsx` — profile install/list/select controls and project-scoped
  queue actions.
- `scripts/build.mjs` — generic builds, bundled profiles, CLI output, and no
  embedded Video 001 config.
- `scripts/generate-figma-manifest.mjs` — generic plugin name and local manifest.
- `scripts/build-release.mjs` and `scripts/verify-release.mjs` — 1.0.0 generic
  package allowlist and recipient-independent verification.
- `package.json` and `package-lock.json` — generic name/version and profile CLI
  scripts.
- `README.md`, `PROVENANCE.md`, and new operator/migration docs — packaged
  installation and workflow.

---

### Task 0: Verify and checkpoint the existing Video 001 fidelity work

**Files:**
- Review only:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/`
- Review only: `tests/test_video_001_exporter.py`

**Interfaces:**
- Consumes: the current dirty worktree, including glyph-aware fallback,
  animation/audit work, and manual validation scripts.
- Produces: a reviewed baseline commit or a documented list of intentionally
  uncommitted files that later path-scoped commits must preserve.

- [ ] **Step 1: Record the exact current state**

Run:

```bash
git status --short
git diff --stat
git diff --check
git diff -- course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/importer.jsxinc
```

Expected: no whitespace errors; the importer diff contains the validated
glyph-level fallback behavior and no unrelated project save/close operation.

- [ ] **Step 2: Run the existing exporter gates before changing architecture**

Run:

```bash
cd course/videos/001-computer-learning-from-text/after-effects/exporter
npm test
npm run typecheck
npm run typecheck:controller
cd ../../../../..
uv run pytest tests/test_video_001_exporter.py -q
```

Expected: every exporter and repository integration test passes. If an existing
test fails, diagnose it before continuing; do not generalize on a red baseline.

- [ ] **Step 3: Review untracked files before any baseline commit**

Run:

```bash
git status --short
git diff --no-index /dev/null course/videos/001-computer-learning-from-text/after-effects/exporter/tests/animation-script.test.ts
git diff --no-index /dev/null course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/capture-full-lesson-duplicate-evidence.jsx
```

Expected: each untracked file is either directly related to the exporter
fidelity proof or remains unstaged and recorded as user work.

- [ ] **Step 4: Commit only the verified baseline exporter changes**

Stage only files proven to belong to the existing Video 001 exporter work:

```bash
git add -- \
  course/videos/001-computer-learning-from-text/after-effects/exporter/scripts/assemble-full-lesson-evidence.mjs \
  course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/importer.jsxinc \
  course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/capture-full-lesson-duplicate-evidence.jsx \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/ae-host-runtime.test.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/ui-protocol.test.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/animation-script.test.ts \
  course/videos/001-computer-learning-from-text/after-effects/docs/video-001-motion-spec.md \
  course/videos/001-computer-learning-from-text/after-effects/scripts/animate-full-lesson.jsx \
  course/videos/001-computer-learning-from-text/after-effects/scripts/audit-animated-full-lesson.jsx \
  course/videos/001-computer-learning-from-text/after-effects/scripts/import-full-lesson-validation.jsx \
  course/videos/001-computer-learning-from-text/after-effects/scripts/lib/video001-motion-provenance.jsxinc \
  tests/test_video_001_exporter.py
git diff --cached --check
git diff --cached --stat
git commit -m "fix: preserve Video 001 exporter fidelity"
```

Expected: the commit contains no unrelated course script or production AEP
change. If review shows mixed user work, leave those paths unstaged and record
them in the execution notes instead of committing them.

---

### Task 1: Add the strict reusable project-profile contract

**Files:**
- Create:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/shared/project-profile.ts`
- Create:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/project-profile.test.ts`
- Create:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/helpers/profile.ts`
- Create:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/config/profiles/video-001.figma-ae-project.json`
- Create:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/fixtures/profiles/fixture-two.figma-ae-project.json`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/shared/limits.ts`

**Interfaces:**
- Produces:

```ts
export interface ProjectProfile {
  schemaVersion: "1.0.0";
  project: { id: string; displayName: string; revision: number };
  source: { fileKey: string; pageId: string; pageName: string };
  target: { width: number; height: number; fps: number; timeUnit: "seconds" };
  naming: { shotPrefix: string; masterCompBase: string; importFolder: string };
  timeline: { sections: ProfileSection[]; shots: ProfileShot[] };
  fontPolicy: { required: FontIdentity[]; fallbacks: FontFallback[] };
  limits: { maxFrames: number; maxAssets: number };
}

export interface ProfileSection {
  id: string;
  name: string;
  firstShot: number;
  lastShot: number;
}

export interface ProfileShot {
  index: number;
  nodeId: string;
  compName: string;
  start: number;
  duration: number;
  sectionId?: string;
  sectionParentNodeId?: string;
}

export interface FontIdentity {
  family: string;
  style: string;
}

export interface FontFallback {
  source: FontIdentity;
  fallback: FontIdentity;
}

export interface InstalledProfile {
  profile: ProjectProfile;
  profileSha256: string;
}

export interface ProfileReference {
  projectId: string;
  profileRevision: number;
  profileSha256: string;
}

export interface ProfileSummary {
  projectId: string;
  displayName: string;
  revision: number;
  profileSha256: string;
  sourcePageName: string;
  target: { width: number; height: number; fps: number };
}

export interface ProfileProjection {
  reference: ProfileReference;
  source: ProjectProfile["source"];
  target: ProjectProfile["target"];
  naming: ProjectProfile["naming"];
  timeline: ProjectProfile["timeline"];
  fontPolicy: ProjectProfile["fontPolicy"];
  limits: ProjectProfile["limits"];
}

export function validateProjectProfile(value: unknown): ProjectProfile;
export function canonicalProfileJson(value: unknown): string;
export function hashProjectProfile(value: unknown): InstalledProfile;
export function profileReference(value: InstalledProfile): ProfileReference;
export function profileSummary(value: InstalledProfile): ProfileSummary;
export function publicProfileProjection(value: InstalledProfile): ProfileProjection;
```

- Consumes: `canonicalJson`, `sha256Hex`, and UTF-8 helpers already present in
  `src/shared`.

- [ ] **Step 1: Write failing profile-contract tests**

Add tests covering Video 001, the second fixture, exact-key rejection, unsafe
project IDs, revision bounds, mismatched sections, duplicate node IDs, timing
gaps, fractional frames, excessive limits, forbidden URL/path/script fields,
canonical hash stability, summary redaction, and public projection.

Representative test:

```ts
test("hashes a validated profile canonically and independently of key order", () => {
  const first = makeVideo001Profile();
  const reordered = reorderKeysDeep(first);
  const left = hashProjectProfile(first);
  const right = hashProjectProfile(reordered);
  assert.equal(left.profileSha256, right.profileSha256);
  assert.deepEqual(left.profile, right.profile);
});

test("rejects a timing gap before returning a profile", () => {
  const value = makeFixtureProfile();
  value.timeline.shots[1]!.start += 1 / value.target.fps;
  assert.throws(
    () => validateProjectProfile(value),
    /Invalid project profile at \\$\\.timeline\\.shots\\[1\\]\\.start: expected continuous timing/
  );
});
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```bash
cd course/videos/001-computer-learning-from-text/after-effects/exporter
./node_modules/.bin/tsx --test tests/project-profile.test.ts
```

Expected: FAIL because `src/shared/project-profile.ts` does not exist.

- [ ] **Step 3: Implement the contract and generic ceilings**

Implement exact validation with these exported ceiling values:

```ts
export const PROFILE_LIMITS = Object.freeze({
  maxProfileBytes: 1 * 1024 * 1024,
  maxInstalledProfiles: 256,
  maxFrames: 256,
  maxAssets: 2_048,
  maxDimension: 16_384,
  maxFps: 120,
  maxDurationSeconds: 6 * 60 * 60,
  maxNameCharacters: 120,
  maxRequiredFonts: 256,
  maxFontFallbacks: 512
});
```

Use one field-path error prefix:

```ts
function invalid(path: string, message: string): never {
  throw new TypeError(`Invalid project profile at ${path}: ${message}`);
}
```

Hash only the validated canonical profile:

```ts
export function hashProjectProfile(value: unknown): InstalledProfile {
  const profile = validateProjectProfile(value);
  const bytes = new TextEncoder().encode(canonicalJson(profile));
  return { profile, profileSha256: sha256Hex(bytes) };
}
```

Convert the current Video 001 timing source into the declared ordinary profile.
The second fixture must use a different project ID, file/page identity,
1280×720 target, 24 fps, three shots, a different master base, and a continuous
six-second timeline.

- [ ] **Step 4: Run focused and shared tests**

Run:

```bash
./node_modules/.bin/tsx --test tests/project-profile.test.ts
npm run typecheck
```

Expected: PASS with no type errors.

- [ ] **Step 5: Commit the profile contract**

```bash
git add -- \
  course/videos/001-computer-learning-from-text/after-effects/exporter/src/shared/project-profile.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/src/shared/limits.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/config/profiles \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/project-profile.test.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/helpers/profile.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/fixtures/profiles
git diff --cached --check
git commit -m "feat: define reusable exporter profiles"
```

---

### Task 2: Build the immutable profile registry and generic paths

**Files:**
- Create:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/bridge/profile-registry.ts`
- Create:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/profile-registry.test.ts`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/bridge/paths.ts`

**Interfaces:**
- Consumes: `InstalledProfile`, `ProfileSummary`, `ProfileProjection`, and
  `hashProjectProfile` from Task 1.
- Produces:

```ts
export interface GenericExporterPaths {
  root: string;
  auth: string;
  profiles: string;
  projects: string;
  tmp: string;
}

export interface ProjectPaths {
  root: string;
  incoming: string;
  quarantine: string;
  assets: string;
  logs: string;
  tmp: string;
}

export function exporterRoot(): string;
export function exporterPaths(root?: string): GenericExporterPaths;
export function projectPaths(paths: GenericExporterPaths, projectId: string): ProjectPaths;

export class ProfileRegistry {
  constructor(paths: GenericExporterPaths, options?: {
    now?: () => number;
    record?: (event: ProfileRegistryEvent) => void;
  });
  installFile(sourcePath: string): Promise<InstalledProfile>;
  installValue(value: unknown): Promise<InstalledProfile>;
  list(): Promise<ProfileSummary[]>;
  resolve(ref: ProfileReference): Promise<InstalledProfile>;
  projection(ref: ProfileReference): Promise<ProfileProjection>;
}

export interface ProfileRegistryEvent {
  operation: "install" | "list" | "resolve";
  status: "ok" | "error";
  projectId?: string;
  revision?: number;
  profileSha256?: string;
  elapsedMs: number;
}
```

- [ ] **Step 1: Write failing registry tests**

Tests must cover fresh install, idempotent identical reinstall, same-revision
hash collision, sorted derived listing, exact resolve, missing profile,
corrupt/symlinked files, unsafe project IDs, atomic failure cleanup, permissions,
project path containment, and redacted install/list/resolve events containing no
source path or profile body.

```ts
test("rejects different bytes at an installed project revision", async () => {
  const registry = new ProfileRegistry(exporterPaths(root));
  const installed = await registry.installValue(makeVideo001Profile());
  const changed = makeVideo001Profile();
  changed.project.displayName += " changed";
  await assert.rejects(
    registry.installValue(changed),
    /PROFILE_REVISION_CONFLICT/
  );
  assert.deepEqual(await registry.resolve(profileReference(installed)), installed);
});
```

- [ ] **Step 2: Run the focused test and confirm RED**

```bash
./node_modules/.bin/tsx --test tests/profile-registry.test.ts
```

Expected: FAIL because `ProfileRegistry` is missing.

- [ ] **Step 3: Implement secure generic paths and registry writes**

Use:

```ts
export function projectPaths(paths: GenericExporterPaths, projectId: string): ProjectPaths {
  const id = validateProjectId(projectId);
  const root = join(paths.projects, id);
  return {
    root,
    incoming: join(root, "incoming"),
    quarantine: join(root, "quarantine"),
    assets: join(root, "assets"),
    logs: join(root, "logs"),
    tmp: join(root, "tmp")
  };
}
```

The final profile path is:

```ts
join(paths.profiles, project.id, String(project.revision),
  `${profileSha256}.figma-ae-project.json`)
```

Installation must use `O_NOFOLLOW`, private modes, byte/identity rechecks,
`FileHandle.sync()`, parent-directory sync, and atomic rename. Listing derives
from immutable files and never trusts a mutable index.

- [ ] **Step 4: Run registry, path, and security tests**

```bash
./node_modules/.bin/tsx --test tests/profile-registry.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit the registry**

```bash
git add -- \
  course/videos/001-computer-learning-from-text/after-effects/exporter/src/bridge/profile-registry.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/src/bridge/paths.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/profile-registry.test.ts
git diff --cached --check
git commit -m "feat: add immutable exporter profile registry"
```

---

### Task 3: Add the profile CLI and build output

**Files:**
- Create:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/cli/profile-cli.ts`
- Create:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/profile-cli.test.ts`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/scripts/build.mjs`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/package.json`

**Interfaces:**
- Consumes: `validateProjectProfile`, `hashProjectProfile`, `ProfileRegistry`.
- Produces:

```ts
export interface ProfileCliIo {
  readLine(prompt: string): Promise<string>;
  stdout(value: string): void;
  stderr(value: string): void;
  readJson(path: string): Promise<unknown>;
  writeNewJson(path: string, value: unknown): Promise<void>;
}

export type ProfileCommand =
  | { kind: "init"; output: string }
  | { kind: "validate"; file: string; json: boolean }
  | { kind: "inspect"; file: string; json: boolean }
  | { kind: "install"; file: string; json: boolean }
  | { kind: "list"; json: boolean };

export function parseProfileCli(argv: readonly string[]): ProfileCommand;
export function runProfileCli(
  command: ProfileCommand,
  dependencies: { io: ProfileCliIo; registry: ProfileRegistry }
): Promise<number>;
```

Build output: `dist/cli/figma-ae.mjs`.

- [ ] **Step 1: Write failing CLI tests**

Cover exact command parsing, unknown/missing args, non-mutating validate and
inspect, machine-readable JSON result, install/list, refusal to overwrite an
existing init output, and a deterministic wizard session.

```ts
test("creates a validated starter profile from explicit wizard answers", async () => {
  const io = scriptedIo([
    "fixture-project", "Fixture Project", "1", "FILE_KEY", "12:34",
    "AE Assets", "1280", "720", "24", "FX", "FIXTURE_MASTER",
    "Fixture Imports", "0", "1", "12:35", "FX_SH01_Intro", "0", "6", "", ""
  ]);
  const exitCode = await runProfileCli({ kind: "init", output: profilePath }, { io, registry });
  assert.equal(exitCode, 0);
  assert.equal(validateProjectProfile(await io.readJson(profilePath)).project.id, "fixture-project");
});
```

- [ ] **Step 2: Run the focused test and confirm RED**

```bash
./node_modules/.bin/tsx --test tests/profile-cli.test.ts
```

Expected: FAIL because the CLI module is missing.

- [ ] **Step 3: Implement commands and build the generic CLI**

The command grammar is:

```text
figma-ae profile init --output <new-file>
figma-ae profile validate <file> [--json]
figma-ae profile inspect <file> [--json]
figma-ae profile install <file> [--json]
figma-ae profile list [--json]
```

Human output must exclude registry paths. JSON output uses:

```ts
interface CliResult {
  status: "ok" | "error";
  code: string;
  project?: { id: string; displayName: string; revision: number; profileSha256: string };
  message: string;
}
```

Add `buildProfileCli()` to `scripts/build.mjs` and include it in
`buildExporter()`. Add package scripts:

```json
{
  "profile": "node dist/cli/figma-ae.mjs profile",
  "profile:validate": "node dist/cli/figma-ae.mjs profile validate"
}
```

- [ ] **Step 4: Run CLI tests and build**

```bash
./node_modules/.bin/tsx --test tests/profile-cli.test.ts
npm run typecheck
npm run build
node dist/cli/figma-ae.mjs profile validate config/profiles/video-001.figma-ae-project.json
```

Expected: PASS and one `status=ok` validation result.

- [ ] **Step 5: Commit the CLI**

```bash
git add -- \
  course/videos/001-computer-learning-from-text/after-effects/exporter/src/cli \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/profile-cli.test.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/scripts/build.mjs \
  course/videos/001-computer-learning-from-text/after-effects/exporter/package.json
git diff --cached --check
git commit -m "feat: add exporter profile CLI"
```

---

### Task 4: Generalize the package contract and isolate legacy Video 001

**Files:**
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/shared/contract.ts`
- Create:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/shared/legacy-video001.ts`
- Create:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/legacy-video001.test.ts`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/contract.test.ts`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/helpers/package.ts`

**Interfaces:**
- Consumes: exact `ProfileReference` and `ProjectProfile` from Task 1.
- Produces:

```ts
export interface ExporterPackage {
  schemaVersion: "3.0.0";
  exporterVersion: string;
  exportedAt: string;
  contentHash: string;
  project: ProfileReference;
  source: { fileKey: string; pageId: string };
  target: { width: number; height: number; fps: number; timeUnit: "seconds" };
  frames: ExportFrame[];
  assets: AssetDescriptor[];
}

export function validatePackage(value: unknown): ExporterPackage;
export function validatePackageAgainstProfile(
  value: unknown,
  installed: InstalledProfile
): ExporterPackage;
export function adaptLegacyVideo001Package(
  value: unknown,
  installedVideo001: InstalledProfile
): ExporterPackage;
```

- [ ] **Step 1: Write failing generic and legacy contract tests**

Add cases for exact profile reference, wrong file/page, wrong target, unknown
shot, wrong shot name/duration/order, full-timeline order, generic suffix and
media type, legacy conversion, and rejection of legacy data under another
profile.

```ts
test("rejects a package whose profile hash is not installed", () => {
  const value = makeValidPackage();
  value.project.profileSha256 = "b".repeat(64);
  assert.throws(
    () => validatePackageAgainstProfile(value, installedVideo001()),
    /profile reference does not match the installed profile/
  );
});
```

- [ ] **Step 2: Run focused tests and confirm RED**

```bash
./node_modules/.bin/tsx --test tests/contract.test.ts tests/legacy-video001.test.ts
```

Expected: FAIL because schema 3 and the adapter do not exist.

- [ ] **Step 3: Implement schema 3 and the isolated adapter**

Change only generic validation in `contract.ts`. Put every literal legacy
suffix, media type, schema version, package marker, Video 001 identity, and
conversion rule in `legacy-video001.ts`.

The adapter must:

```ts
export function adaptLegacyVideo001Package(
  value: unknown,
  installed: InstalledProfile
): ExporterPackage {
  assertBundledVideo001Profile(installed);
  const legacy = validateLegacyPackage(value);
  assertLegacyMatchesProfile(legacy, installed.profile);
  return validatePackageAgainstProfile({
    ...legacy,
    schemaVersion: "3.0.0",
    project: profileReference(installed)
  }, installed);
}
```

Do not weaken exact-key or fingerprint validation for generic packages.

- [ ] **Step 4: Run contract and type tests**

```bash
./node_modules/.bin/tsx --test tests/contract.test.ts tests/legacy-video001.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit the generic package contract**

```bash
git add -- \
  course/videos/001-computer-learning-from-text/after-effects/exporter/src/shared/contract.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/src/shared/legacy-video001.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/contract.test.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/legacy-video001.test.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/helpers/package.ts
git diff --cached --check
git commit -m "feat: generalize exporter package contract"
```

---

### Task 5: Add authenticated profile discovery and project-scoped bridge queues

**Files:**
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/bridge/server.ts`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/bridge/queue.ts`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/bridge/cli.ts`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/bridge.test.ts`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/streaming-package.test.ts`

**Interfaces:**
- Consumes: `ProfileRegistry`, `projectPaths`, schema 3 package validation.
- Produces authenticated routes:

```text
GET /v1/profiles
GET /v1/profiles/<project-id>/<revision>/<profile-sha256>
POST /v1/export
```

`CreateBridgeServerOptions` gains:

```ts
profiles: ProfileRegistry;
queueForProject(projectId: string): QueueStore;
```

- [ ] **Step 1: Write failing bridge tests**

Cover unauthenticated 401 with no profile data, sorted summaries, exact
projection, missing profile 404, malformed ref 400, generic media type,
profile-aware export validation, queue namespace isolation, and no package
publication after profile mismatch.

```ts
test("does not disclose installed profiles without bearer authentication", async () => {
  const response = await request(server, { method: "GET", path: "/v1/profiles" });
  assert.equal(response.status, 401);
  assert.deepEqual(response.json, {
    error: { code: "UNAUTHORIZED", message: "Authentication is required" }
  });
  assert.equal(response.text.includes("video-001"), false);
});
```

- [ ] **Step 2: Run focused tests and confirm RED**

```bash
./node_modules/.bin/tsx --test tests/bridge.test.ts tests/streaming-package.test.ts
```

Expected: FAIL because profile routes and project queue selection are absent.

- [ ] **Step 3: Implement authenticated routes and namespaced queues**

Extend route parsing to structured route values rather than a Video 001 route
union:

```ts
type BridgeRoute =
  | { kind: "health" }
  | { kind: "pair" }
  | { kind: "reset" }
  | { kind: "profiles" }
  | { kind: "profile"; ref: ProfileReference }
  | { kind: "export" }
  | { kind: "unknown" };
```

Authenticate before calling `profiles.list()` or `profiles.projection()`.
During export, parse the manifest/profile reference within existing body bounds,
resolve the profile, validate the package against it, then choose
`queueForProject(projectId)`.

Change the queue suffix to `.figma-ae.json`. Preserve legacy queue behavior only
through an explicit manual compatibility path; do not scan the legacy root.

- [ ] **Step 4: Run bridge, auth, queue, and type tests**

```bash
./node_modules/.bin/tsx --test \
  tests/auth.test.ts \
  tests/bridge.test.ts \
  tests/streaming-package.test.ts \
  tests/work-control.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit bridge generalization**

```bash
git add -- \
  course/videos/001-computer-learning-from-text/after-effects/exporter/src/bridge \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/bridge.test.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/streaming-package.test.ts
git diff --cached --check
git commit -m "feat: add profile-aware exporter bridge"
```

---

### Task 6: Make the single Figma plugin profile-driven at runtime

**Files:**
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/figma/controller.ts`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/figma/ui.ts`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/figma/ui.html`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/scripts/generate-figma-manifest.mjs`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/ui-protocol.test.ts`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/serializer.test.ts`

**Interfaces:**
- Consumes: authenticated profile summary/projection routes and schema 3 package.
- Produces UI/controller messages:

```ts
type ControllerToUi =
  | { type: "profiles"; profiles: ProfileSummary[]; selected?: ProfileReference }
  | { type: "profile-selected"; profile: ProfileProjection }
  | { type: "selection"; generation: number; frames: FrameSummary[] }
  | { type: "package-unhashed"; generation: number; value: ExporterPackage }
  | { type: "bridge-result"; operation: number; status: number; code: string; message: string }
  | { type: "failure"; operation?: number; code: string; message: string };

type UiToController =
  | { type: "refresh-profiles" }
  | { type: "select-profile"; ref: ProfileReference }
  | { type: "refresh-selection" }
  | { type: "build-selection" }
  | { type: "build-complete-project" }
  | { type: "pair"; code: string }
  | { type: "send"; value: ExporterPackage }
  | { type: "close" };
```

- [ ] **Step 1: Write failing UI/controller protocol tests**

Cover profile list validation, selection, refresh, stale selection after registry
change, source mismatch, no export without profile, selected-frame build,
full-timeline build, generic filename/media type, and unchanged download/send
bytes.

```ts
test("disables build when the selected profile does not match the open page", async () => {
  const controller = createController(hostFor("other-file", "90:2"), bridgeWithProfiles());
  await controller.selectProfile(video001Reference);
  assert.deepEqual(lastUiFailure(), {
    type: "failure",
    code: "PROJECT_SOURCE_MISMATCH",
    message: "Open the configured Figma file and page for Video 001 - What AI Models Actually Do."
  });
});
```

- [ ] **Step 2: Run focused tests and confirm RED**

```bash
./node_modules/.bin/tsx --test tests/ui-protocol.test.ts tests/serializer.test.ts
```

Expected: FAIL because the profile protocol does not exist.

- [ ] **Step 3: Remove embedded Video 001 config and implement profile selection**

Delete the `__VIDEO001_CONFIG__` build define. The controller keeps only the
selected `ProfileProjection` in memory and always refreshes it by exact
reference after pairing or a registry-change response.

The UI model gains:

```ts
profiles: ProfileSummary[];
selectedProfile?: ProfileReference;
profileDisabled: boolean;
```

Generic copy uses “Figma → After Effects Exporter”, “Select a project profile”,
“Build selected frames”, and “Build complete project”. `packageFilename`
returns:

```ts
`${projectId}-${contentHash.slice(0, 12)}.figma-ae.json`
```

Generate the manifest name `Figma → After Effects Exporter` and preserve the
loopback-only development origin.

- [ ] **Step 4: Run UI, serializer, browser-boundary, and controller type tests**

```bash
./node_modules/.bin/tsx --test tests/ui-protocol.test.ts tests/serializer.test.ts
npm run typecheck
npm run typecheck:controller
npm run build
```

Expected: PASS; built controller contains no `__VIDEO001_CONFIG__`, Video 001
file key, or Video 001 UI copy.

- [ ] **Step 5: Commit the generic Figma plugin**

```bash
git add -- \
  course/videos/001-computer-learning-from-text/after-effects/exporter/src/figma \
  course/videos/001-computer-learning-from-text/after-effects/exporter/scripts/generate-figma-manifest.mjs \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/ui-protocol.test.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/serializer.test.ts
git diff --cached --check
git commit -m "feat: make Figma exporter profile-driven"
```

---

### Task 7: Generalize the After Effects importer and preserve legacy fidelity

**Files:**
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/import-core.jsxinc`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/importer.jsxinc`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/audit-export.jsx`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/audit-full-lesson.jsx`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/ae-core.test.ts`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/ae-host-runtime.test.ts`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/timing-units.test.ts`

**Interfaces:**
- Consumes: profile registry layout, schema 3 package, legacy Video 001 profile.
- Produces ES3 global:

```js
var FigmaAEExporterImporter = {
    importPackageFile: function (packageFile, options) {},
    loadInstalledProfile: function (reference, options) {},
    listQueuedProjects: function (options) {}
};
```

- [ ] **Step 1: Write failing AE host tests**

Add runtime-harness cases for:

- Video 001 through the generic profile;
- the 1280×720, 24 fps, three-shot fixture;
- generic folder/master/shot naming;
- exact profile hash resolution;
- missing/mismatched/corrupt profile before mutation;
- `_v001`/`_v002` immutability and `_v999` bound;
- generic and legacy duplicate markers;
- legacy package adaptation only for bundled Video 001;
- Unicode, mixed runs, paragraph boxes, glyph-level fallback, raster fallback;
- rollback and no save/close calls.

```ts
test("imports the second profile without Video 001 dimensions or naming", () => {
  const result = harness.importPackage(fixturePackage(), fixtureInstalledProfile());
  assert.equal(result.master.name, "FIXTURE_MASTER_v001");
  assert.equal(result.master.width, 1280);
  assert.equal(result.master.height, 720);
  assert.equal(result.master.frameRate, 24);
  assert.equal(result.master.layers.length, 3);
});
```

- [ ] **Step 2: Run focused AE tests and confirm RED**

```bash
./node_modules/.bin/tsx --test \
  tests/ae-core.test.ts \
  tests/ae-host-runtime.test.ts \
  tests/timing-units.test.ts
```

Expected: FAIL because the generic importer/global does not exist.

- [ ] **Step 3: Implement ES3 profile and package validation**

Keep the file ES3-only. Add profile functions with `var`, function
declarations, plain objects, and loops. Derive the profile path from the fixed
generic root plus validated project ID, revision, and hash. Recompute the
profile SHA-256 before use.

Use generic comments:

```js
function exportComment(projectId, profileHash, contentHash) {
    return "FigmaAEExport project=" + projectId +
        " profile=" + profileHash +
        " content=" + contentHash;
}
```

Load dimensions, fps, shot timings, comp names, import folder, master base,
font policy, and project limits from the profile. Preserve the existing
glyph-run splitting fix exactly: unsupported glyphs receive only a glyph-level
fallback and never switch the complete text run.

Legacy literals remain inside one clearly delimited compatibility function and
are accepted only when the installed profile hash equals the bundled Video 001
profile hash.

- [ ] **Step 4: Run AE host, build-boundary, and full exporter tests**

```bash
./node_modules/.bin/tsx --test \
  tests/ae-core.test.ts \
  tests/ae-host-runtime.test.ts \
  tests/timing-units.test.ts
npm run build
npm test
```

Expected: PASS; built AE script passes the ES3 prohibition scan and contains no
project save/close call.

- [ ] **Step 5: Commit the generic AE importer**

```bash
git add -- \
  course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/import-core.jsxinc \
  course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/importer.jsxinc \
  course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/audit-export.jsx \
  course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/audit-full-lesson.jsx \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/ae-core.test.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/ae-host-runtime.test.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/timing-units.test.ts
git diff --cached --check
git commit -m "feat: generalize After Effects package import"
```

---

### Task 8: Add profile installation and project selection to the AE palette

**Files:**
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/panel.jsx`
- Create:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/ae-panel-profile.test.ts`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/scripts/build.mjs`

**Interfaces:**
- Consumes: built `dist/cli/figma-ae.mjs`, profile registry, generic importer.
- Produces palette actions:

```text
Install project profile...
Refresh profiles
Select project
Start bridge
Stop bridge
Reset pairing
Import next
Import package...
Import duplicate...
```

- [ ] **Step 1: Write failing panel tests**

Use the existing ScriptUI harness to assert controls, quoted CLI invocation,
valid JSON result parsing, selected-project persistence by exact reference,
project-scoped queue count, missing-profile recovery, and no shell injection
from selected paths.

```ts
test("installs a selected profile through the bounded CLI operation", () => {
  const panel = createPanelHarness();
  panel.chooseProfileFile("/tmp/fixture.figma-ae-project.json");
  panel.click("Install project profile...");
  assert.equal(panel.systemCalls[0], [
    quoteShellArgument(panel.nodePath),
    quoteShellArgument(panel.cliPath),
    "profile",
    "install",
    quoteShellArgument("/tmp/fixture.figma-ae-project.json"),
    "--json"
  ].join(" "));
});
```

- [ ] **Step 2: Run the focused panel test and confirm RED**

```bash
./node_modules/.bin/tsx --test tests/ae-panel-profile.test.ts
```

Expected: FAIL because the controls and bounded CLI operation are absent.

- [ ] **Step 3: Implement palette profile operations**

Do not construct an unbounded shell string from Figma/profile content. Reuse the
existing strict quoting helper for the user-selected local file and fixed
runtime paths. Require CLI JSON with exact keys before updating UI state.

The selected project is a `projectId/revision/profileSha256` value, never a
registry path. Queue actions derive paths only through the generic importer.

Build output becomes:

```text
dist/ae/Figma-AE-Exporter.jsx
dist/ae/audit-export.jsx
dist/ae/audit-project.jsx
```

- [ ] **Step 4: Run panel, AE, and build tests**

```bash
./node_modules/.bin/tsx --test tests/ae-panel-profile.test.ts tests/ae-host-runtime.test.ts
npm run build
npm run typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit the AE palette**

```bash
git add -- \
  course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/panel.jsx \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/ae-panel-profile.test.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/scripts/build.mjs
git diff --cached --check
git commit -m "feat: manage exporter profiles from After Effects"
```

---

### Task 9: Package the portable private 1.0.0 release

**Files:**
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/package.json`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/package-lock.json`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/scripts/build.mjs`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/scripts/build-release.mjs`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/scripts/verify-release.mjs`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/release.test.ts`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/README.md`
- Create:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/docs/INSTALL.md`
- Create:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/docs/PROJECT_PROFILES.md`
- Create:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/docs/MIGRATION.md`

**Interfaces:**
- Consumes: all generic runtime builds and bundled profiles.
- Produces:

```text
release/figma-ae-exporter-1.0.0.tar.gz
release/figma-ae-exporter-1.0.0.sha256
```

- [ ] **Step 1: Write failing release tests**

Assert generic package metadata/version, allowlisted runtime/profile/docs/tests,
absence of `.figma-plugin-id`, recipient manifest, Video 001 evidence/AEPs,
credentials, mutable paths, and old runtime filenames. Verify setup can generate
two different valid manifests from two local IDs without changing archive
bytes.

```ts
test("release bytes do not depend on the recipient Figma plugin ID", async () => {
  const first = await buildReleaseWithLocalPluginId("1111111111111111111");
  const second = await buildReleaseWithLocalPluginId("2222222222222222222");
  assert.deepEqual(first.archiveBytes, second.archiveBytes);
  assert.notEqual(first.generatedManifest.id, second.generatedManifest.id);
});
```

- [ ] **Step 2: Run focused release tests and confirm RED**

```bash
./node_modules/.bin/tsx --test tests/release.test.ts
```

Expected: FAIL because release 0.2.0 and Video 001 paths are still hard-coded.

- [ ] **Step 3: Implement generic build, setup, archive, and verification**

Set package and lockfile name/version:

```json
{
  "name": "figma-ae-exporter",
  "version": "1.0.0",
  "private": true
}
```

The release allowlist includes source, tests, built generic Figma code/UI,
bridge, CLI, AE palette/audits, profile schema, bundled profiles, docs, license,
notice, provenance, and build/verify scripts. It excludes
`dist/figma/manifest.json`.

Add setup:

```text
node dist/cli/figma-ae.mjs setup --plugin-id-file .figma-plugin-id
```

Setup writes only the recipient manifest and verifies generic runtime version
agreement. Update the archive basename, fixed release timestamp, ownership
marker, source/dist file names, secret scan, and clean-extraction rebuild.

- [ ] **Step 4: Write exact operator documentation**

`INSTALL.md` covers prerequisites, extraction, `npm ci`, local plugin ID,
setup, Figma manifest import, AE script launch, and uninstall.

`PROJECT_PROFILES.md` covers CLI creation, schema fields, revision rules,
installation through AE, project switching, validation errors, and the bundled
examples.

`MIGRATION.md` covers legacy Video 001 plugin coexistence, bundled profile,
manual legacy package import, old queue drain, rollout, and rollback.

- [ ] **Step 5: Run build, package, and independent verifier**

```bash
npm test
npm run typecheck
npm run typecheck:controller
npm run build
npm run release:build
npm run release:verify
```

Expected: all commands pass and produce the 1.0.0 archive plus checksum.

- [ ] **Step 6: Commit the portable release**

```bash
git add -- \
  course/videos/001-computer-learning-from-text/after-effects/exporter/package.json \
  course/videos/001-computer-learning-from-text/after-effects/exporter/package-lock.json \
  course/videos/001-computer-learning-from-text/after-effects/exporter/scripts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/release.test.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/README.md \
  course/videos/001-computer-learning-from-text/after-effects/exporter/docs
git diff --cached --check
git commit -m "build: package reusable Figma AE exporter"
```

---

### Task 10: Prove two-profile operation and complete release preflight

**Files:**
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/ae-host-runtime.test.ts`
- Modify:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/bridge.test.ts`
- Modify:
  `tests/test_video_001_exporter.py`
- Create:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/scripts/audit-generic-runtime.mjs`
- Create:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/docs/SMOKE_TEST.md`
- Create only after real-host execution:
  `course/videos/001-computer-learning-from-text/after-effects/exporter/evidence/generic-release/summary.json`

**Interfaces:**
- Consumes: packaged 1.0.0 runtime and both bundled profiles.
- Produces: automated equivalence evidence, real-host smoke instructions, and a
  redacted real-host summary after the user-assisted Figma/AE gate.

- [ ] **Step 1: Write failing end-to-end acceptance tests**

Add one test per acceptance criterion from the approved specification,
including a source scan that permits Video 001 literals only in the bundled
profile, legacy adapter, legacy fixtures, migration docs, and tests.

```python
def test_generic_runtime_has_no_video001_assumptions():
    forbidden_runtime = [
        EXPORTER / "src/bridge/paths.ts",
        EXPORTER / "src/bridge/queue.ts",
        EXPORTER / "src/figma/controller.ts",
        EXPORTER / "src/figma/ui.ts",
        EXPORTER / "src/ae/import-core.jsxinc",
    ]
    for path in forbidden_runtime:
        source = path.read_text(encoding="utf-8")
        assert "Video001" not in source
        assert "video001-ae" not in source
        assert "fFTux3sx2AzVQtoya67f95" not in source
```

- [ ] **Step 2: Run the acceptance tests and confirm RED**

```bash
uv run pytest tests/test_video_001_exporter.py -q
```

Expected: FAIL on remaining hard-coded runtime assumptions or missing generic
evidence script.

- [ ] **Step 3: Implement the generic audit and close acceptance gaps**

`audit-generic-runtime.mjs` must load built runtime metadata, both profiles,
their expected package fixtures, and AE-host reports; it emits a deterministic
JSON summary with:

```json
{
  "status": "complete",
  "releaseVersion": "1.0.0",
  "profiles": [],
  "video001Compatible": true,
  "secondProfileGeneric": true,
  "runtimeHardCodingViolations": [],
  "tests": {}
}
```

It must fail before writing `complete` if either profile, schema, runtime build,
or acceptance result is missing.

- [ ] **Step 4: Run the complete automated gate**

```bash
cd course/videos/001-computer-learning-from-text/after-effects/exporter
npm test
npm run typecheck
npm run typecheck:controller
npm run build
npm run release:build
npm run release:verify
node scripts/audit-generic-runtime.mjs
cd ../../../../..
uv run pytest tests/test_video_001_exporter.py -q
```

Expected: all commands pass with zero warnings from the verifier.

- [ ] **Step 5: Perform real Figma and After Effects smoke tests**

Follow `docs/SMOKE_TEST.md`:

1. extract the release into a new temporary directory;
2. run `npm ci`;
3. supply a fresh local development-plugin ID;
4. generate and import the recipient Figma manifest;
5. run `dist/ae/Figma-AE-Exporter.jsx`;
6. install the bundled Video 001 and fixture profiles through AE;
7. pair Figma;
8. verify both profiles appear without a rebuild;
9. export/import Video 001 into a disposable fresh AE project;
10. switch profiles without restarting the plugin;
11. export/import the fixture profile into the same disposable project;
12. run the bundled AE audit;
13. write only the redacted summary evidence.

Expected: the Video 001 result contains 48 versioned shots plus
`VIDEO001_MASTER_v001`; the fixture result contains three 1280×720, 24 fps
versioned shots plus `FIXTURE_MASTER_v001`; no production AEP is opened or
modified.

- [ ] **Step 6: Run final release preflight**

Run:

```bash
git status --short
git diff --check
git log --oneline --decorate -12
/usr/bin/shasum -a 256 \
  course/videos/001-computer-learning-from-text/after-effects/exporter/release/figma-ae-exporter-1.0.0.tar.gz
cat \
  course/videos/001-computer-learning-from-text/after-effects/exporter/release/figma-ae-exporter-1.0.0.sha256
```

Expected: archive hash matches the checksum file exactly; only intentional
evidence or unrelated pre-existing user changes remain uncommitted.

- [ ] **Step 7: Commit acceptance evidence and documentation**

```bash
git add -- \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/ae-host-runtime.test.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/tests/bridge.test.ts \
  course/videos/001-computer-learning-from-text/after-effects/exporter/scripts/audit-generic-runtime.mjs \
  course/videos/001-computer-learning-from-text/after-effects/exporter/docs/SMOKE_TEST.md \
  course/videos/001-computer-learning-from-text/after-effects/exporter/evidence/generic-release/summary.json \
  tests/test_video_001_exporter.py
git diff --cached --check
git commit -m "test: prove reusable exporter release"
```

---

## Final Verification Checklist

- [ ] One Figma plugin lists and switches between two installed profiles.
- [ ] Profile registry install/list/resolve is immutable and atomic.
- [ ] Generic package/profile references are validated at plugin, bridge, and AE
      boundaries.
- [ ] Video 001 legacy packages remain isolated to the compatibility adapter.
- [ ] Video 001 48-shot/master structure and glyph fallback remain unchanged.
- [ ] The second profile proves non-Video 001 dimensions, fps, timing, count,
      names, and queues.
- [ ] Figma plugin build contains no embedded project profile.
- [ ] Generic runtime source scan finds no Video 001 assumptions.
- [ ] AE importer remains ES3-compatible and never saves/closes the project.
- [ ] Automated tests, typechecks, builds, release build, and verifier pass.
- [ ] Real Figma/AE smoke evidence is complete and redacted.
- [ ] Release archive hash matches the packaged checksum.
- [ ] Recipient plugin ID and generated manifest are absent from the archive.
- [ ] Installation, profile authoring, migration, troubleshooting, and rollback
      documentation are complete.
