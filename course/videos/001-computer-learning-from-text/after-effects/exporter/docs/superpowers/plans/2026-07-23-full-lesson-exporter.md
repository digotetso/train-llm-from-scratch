# Full-Lesson Exporter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-click, production-ready 48-shot Figma export that creates editable After Effects shot comps and an exact 14-minute master timeline, then package and verify a downloadable source release.

**Architecture:** The Figma controller resolves the 48 embedded approved node IDs through a narrow host adapter and sends them through the existing serializer, hashing, and bridge path. The AE importer recognizes only an exact canonical 48-frame package, imports all shots transactionally, and creates one versioned master comp from canonical starts and durations. Read-only audits and a deterministic release builder make the full workflow reproducible without touching the production AEP.

**Tech Stack:** TypeScript 7, Node.js 20+, Figma Plugin API typings 1.131.0, ExtendScript ES3, After Effects 25.2.2, Node test runner through `tsx`, pytest.

## Global Constraints

- Wire schema remains exactly `2.0.0` with `target.timeUnit: "seconds"`.
- Canonical target remains 1920×1080, 30 fps, 840 seconds.
- The package contains exactly the 48 configured shots in configured order for a full-lesson build.
- Existing selected-frame exports and partial AE imports remain behaviorally unchanged.
- No Creative Cloud, Adobe Media Encoder, hosted service, or new runtime dependency.
- The bridge remains authenticated and bound only to `127.0.0.1`.
- No Figma document mutation; full-lesson lookup must not change selection.
- All AE live validation occurs in `/private/tmp`.
- The production AEP SHA-256 must remain `ffbb3daa7b1cc225cdacc1ed4e490da083c85c9e3877162293993cd6306a3881`.
- No credential, authorization header, mutable `/Users/` path, or live user-data file enters evidence or release artifacts.

---

### Task 1: One-click full-lesson package generation

**Files:**
- Modify: `src/figma/controller.ts`
- Modify: `src/figma/ui.ts`
- Modify: `src/figma/ui.html`
- Modify: `tests/ui-protocol.test.ts`
- Modify: `../../../../../tests/test_video_001_exporter.py`

**Interfaces:**
- Consumes: `EmbeddedVideo001Config.shots`, `selectedFrames(...)`, `serializeFrame(...)`.
- Produces: `ControllerHost.getNodeByIdAsync(nodeId: string): Promise<FigmaNodeLike | null>`.
- Produces: `UiToController` message `{ type: "build-full-lesson" }`.
- Produces: `UiController.buildFullLesson(): void`.
- Produces: a normal schema-2 `ExporterPackage`; no second package format.

- [ ] **Step 1: Write failing protocol and controller tests**

Add a 48-shot config fixture and node map to `tests/ui-protocol.test.ts`. The tests must assert:

```ts
await controller.handleMessage({ type: "build-full-lesson" });
const selection = harness.messages.find((value) =>
  (value as { type?: string }).type === "selection"
) as { frames: Array<{ nodeId: string }> };
assert.deepEqual(selection.frames.map((frame) => frame.nodeId), fullConfig.shots.map((shot) => shot.nodeId));
assert.equal(harness.host.getCurrentPage().selection.length, 1, "full build changed the user's selection");
```

Add separate failures for a missing node, wrong direct SECTION parent, wrong PAGE parent, wrong name, wrong dimensions, a stale generation during raster export, and a 49-shot config.

- [ ] **Step 2: Run the focused tests and verify red**

Run:

```bash
npx tsx --test --test-concurrency=1 tests/ui-protocol.test.ts
```

Expected: FAIL because `build-full-lesson` and `getNodeByIdAsync` are not defined.

- [ ] **Step 3: Extend the exact-key message and host contracts**

In `src/figma/controller.ts`, add:

```ts
export type UiToController =
  | { type: "refresh-selection" }
  | { type: "build-package" }
  | { type: "build-full-lesson" }
  | { type: "package-ready"; generation: number; value: ExporterPackage }
  | { type: "pair"; operation: number; code: string }
  | { type: "send-live"; operation: number }
  | { type: "close" };

export interface ControllerHost {
  fileKey: string | undefined;
  getCurrentPage(): ControllerPage;
  getNodeByIdAsync(nodeId: string): Promise<FigmaNodeLike | null>;
  // retain existing members unchanged
}
```

Map the production adapter exactly:

```ts
getNodeByIdAsync: async (nodeId) =>
  await figma.getNodeByIdAsync(nodeId) as unknown as FigmaNodeLike | null,
```

Update `validateUiToController` so `{ type: "build-full-lesson" }` accepts no additional keys.

- [ ] **Step 4: Converge selected and full builds before serialization**

Extract the existing selected-node validation into:

```ts
function validateApprovedFrame(
  node: FigmaNodeLike,
  timing: EmbeddedVideo001Config["shots"][number],
  page: ControllerPage,
  host: ControllerHost,
  config: EmbeddedVideo001Config
): void {
  // Apply the existing exact file/page/section/name/type/dimension checks.
}
```

Then extract the existing serializer loop into:

```ts
type ApprovedFrame = { node: FigmaNodeLike; timing: EmbeddedVideo001Config["shots"][number] };

const buildApprovedFrames = async (
  generation: number,
  selected: readonly ApprovedFrame[]
): Promise<void> => {
  // post selection, serialize sequentially, dedupe assets, build schema-2 package,
  // invalidate stale generations, and post package-unhashed exactly as today
};
```

Implement:

```ts
const resolveFullLessonFrames = async (
  generation: number
): Promise<ApprovedFrame[] | undefined> => {
  const page = host.getCurrentPage();
  const resolved: ApprovedFrame[] = [];
  for (const timing of config.shots) {
    const node = await host.getNodeByIdAsync(timing.nodeId);
    if (generation !== packageGeneration) return undefined;
    if (node === null) {
      throw controllerFailure("SHOT_NODE_NOT_FOUND", `Shot ${timing.index} node ${timing.nodeId} is unavailable.`);
    }
    validateApprovedFrame(node, timing, page, host, config);
    resolved.push({ node, timing });
  }
  return resolved;
};
```

The selection path begins one generation and calls `buildApprovedFrames(generation, selectedFrames(...))`. The full path begins one generation, calls `resolveFullLessonFrames(generation)`, returns quietly for `undefined`, and otherwise calls `buildApprovedFrames(generation, resolved)`. A request must never increment the generation twice.

- [ ] **Step 5: Add the full-lesson UI control**

Add to `UiController`:

```ts
buildFullLesson(): void;
```

Implement it with the same invalidation state as `build()`, posting `{ type: "build-full-lesson" }`. Add an accessible secondary button:

```html
<button id="build-full-lesson" type="button">Build full lesson (48 shots)</button>
```

Disable both build buttons while busy. Keep selected-frame build disabled when selection is empty; full-lesson build remains available unless busy.

- [ ] **Step 6: Run focused and full checks**

Run:

```bash
npx tsx --test --test-concurrency=1 tests/ui-protocol.test.ts
npm run typecheck
npm run typecheck:controller
npm test
```

Expected: all tests pass and the suite count increases beyond 204.

- [ ] **Step 7: Commit Task 1**

```bash
git add src/figma/controller.ts src/figma/ui.ts src/figma/ui.html tests/ui-protocol.test.ts ../../../../../tests/test_video_001_exporter.py
git commit -m "feat: build the complete lesson from Figma"
```

---

### Task 2: Transactional 14-minute AE master composition

**Files:**
- Modify: `src/ae/import-core.jsxinc`
- Modify: `src/ae/importer.jsxinc`
- Modify: `src/ae/audit-export.jsx`
- Modify: `tests/ae-core.test.ts`
- Modify: `tests/ae-host-runtime.test.ts`
- Modify: `../../../../../tests/test_video_001_exporter.py`

**Interfaces:**
- Consumes: timing `shots[]` with `index`, `nodeId`, `name`, `start`, and `duration`.
- Produces: validated internal `packageObject.isFullLesson: boolean`.
- Produces: import report field `createdMasterCompName: string | null`.
- Produces: master comment `Video001Export sha256:<64 lowercase hex>`.

- [ ] **Step 1: Write failing AE host tests**

Extend the AE harness so mock `CompItem` layers expose `startTime`, `inPoint`, and `outPoint`. Build a 48-frame package from canonical timing with one simple native rectangle per frame.

Assert:

```ts
assert.equal(result.status, "IMPORTED");
assert.equal(result.report.createdCompNames.length, 48);
assert.equal(result.report.createdMasterCompName, "VIDEO001_MASTER_v001");
assert.equal(master.duration, 840);
assert.equal(master.frameRate, 30);
assert.equal(master.numLayers, 48);
assert.deepEqual(master.layersInTimelineOrder.map((layer) => ({
  source: layer.source.name,
  startTime: layer.startTime,
  inPoint: layer.inPoint,
  outPoint: layer.outPoint
})), canonicalShots.map((shot) => ({
  source: `${shot.name}_v001`,
  startTime: shot.start,
  inPoint: shot.start,
  outPoint: shot.start + shot.duration
})));
```

Add failures for reordered full input, duplicated node ID, missing shot, master creation failure rollback, unchanged resend, and partial package import with `createdMasterCompName === null`.

- [ ] **Step 2: Run focused AE tests and verify red**

Run:

```bash
npx tsx --test --test-concurrency=1 tests/ae-core.test.ts tests/ae-host-runtime.test.ts
```

Expected: FAIL because full-set detection and master creation do not exist.

- [ ] **Step 3: Retain ordered timing metadata**

In `loadTiming`, retain:

```js
shot = {
    index: index + 1,
    nodeId: requireString(value.figmaNodeId, "Video 001 shot node ID", false),
    name: requireString(value.name, "Video 001 shot name", false),
    start: requireNumber(value.start, "Video 001 shot start", 0),
    duration: requirePositiveNumber(value.duration, "Video 001 shot duration")
};
```

Return both `shots` in canonical order and `shotsByNodeId`.

- [ ] **Step 4: Detect an exact full package before mutation**

After package/schema/assets/timing validation and before `app.beginUndoGroup`, compute:

```js
packageObject.isFullLesson = frames.length === timing.shots.length;
if (packageObject.isFullLesson) {
    for (index = 0; index < timing.shots.length; index += 1) {
        if (frames[index].nodeId !== timing.shots[index].nodeId) {
            throw new Error("Full-lesson package frames must preserve canonical shot order");
        }
    }
}
```

A partial package remains valid. A 48-frame package that is not the exact configured set fails before item creation.

- [ ] **Step 5: Create the master inside the import transaction**

Return the root `CompItem` from `importFrame` and retain it with its timing. Add:

```js
function createFullLessonMaster(importedFrames, timing, packageObject, target, rootFolder, state, transactionItems) {
    var masterName = core.nextVersionName(allProjectItemNames(), "VIDEO001_MASTER");
    var master = rememberItem(
        transactionItems,
        app.project.items.addComp(masterName, target.width, target.height, 1, 840, target.fps)
    );
    master.parentFolder = rootFolder;
    master.comment = "Video001Export sha256:" + packageObject.contentHash;
    for (var index = importedFrames.length - 1; index >= 0; index -= 1) {
        var shot = timing.shots[index];
        var layer = master.layers.add(importedFrames[index]);
        layer.name = importedFrames[index].name;
        layer.startTime = shot.start;
        layer.inPoint = shot.start;
        layer.outPoint = shot.start + shot.duration;
    }
    state.createdMasterCompName = masterName;
    return master;
}
```

Initialize `createdMasterCompName: null`, include it in `core.makeImportReport`, and create the master only after all 48 roots succeed.

- [ ] **Step 6: Extend the read-only audit**

Add `startTime`, `inPoint`, and `outPoint` only for precomp layers to `auditLayer`. Preserve the audit's item-count and read-only state checks.

- [ ] **Step 7: Run focused and full checks**

Run:

```bash
npx tsx --test --test-concurrency=1 tests/ae-core.test.ts tests/ae-host-runtime.test.ts
npm test
npm run typecheck
npm run typecheck:controller
npm run build
uv run pytest -q ../../../../../tests/test_video_001_exporter.py
```

Expected: all exporter checks pass.

- [ ] **Step 8: Commit Task 2**

```bash
git add src/ae/import-core.jsxinc src/ae/importer.jsxinc src/ae/audit-export.jsx tests/ae-core.test.ts tests/ae-host-runtime.test.ts ../../../../../tests/test_video_001_exporter.py
git commit -m "feat: assemble the full lesson timeline in AE"
```

---

### Task 3: Full-lesson read-only audit and deterministic evidence

**Files:**
- Create: `src/ae/audit-full-lesson.jsx`
- Create: `scripts/assemble-full-lesson-evidence.mjs`
- Create: `evidence/full-lesson/.gitkeep`
- Modify: `scripts/build.mjs`
- Modify: `tests/ae-host-runtime.test.ts`
- Modify: `tests/ui-protocol.test.ts`
- Modify: `../../../../../tests/test_video_001_exporter.py`

**Interfaces:**
- Consumes: active `VIDEO001_MASTER_vNNN` and canonical `dist/ae/figma-scenes.json`.
- Produces: `dist/ae/audit-full-lesson.jsx`.
- Produces: `dist/ae/full-lesson-audit.json` at runtime.
- Produces: deterministic `evidence/full-lesson/audit.json`, `summary.json`, and `manifest.json`.

- [ ] **Step 1: Write failing audit source/runtime tests**

Add an AE mock project containing 48 root comps, recursive precomps, and one master. Assert the full audit:

```ts
assert.equal(audit.master.durationSeconds, 840);
assert.equal(audit.master.durationFrames, 25_200);
assert.equal(audit.master.layers.length, 48);
assert.equal(audit.shots.length, 48);
assert.ok(audit.shots.every((shot) => shot.durationSeconds === timingById.get(shot.nodeId)!.duration));
assert.equal(audit.itemCountBefore, audit.itemCountAfter);
```

Add failures for a gap, overlap, wrong source comp, wrong hash, wrong recursive duration, unexpected raster fallback, and project mutation during audit.

- [ ] **Step 2: Run focused tests and verify red**

Run:

```bash
npx tsx --test --test-concurrency=1 tests/ae-host-runtime.test.ts tests/ui-protocol.test.ts
```

Expected: FAIL because `audit-full-lesson.jsx` is absent.

- [ ] **Step 3: Implement the read-only full audit**

Use ES3-compatible helpers and AE match-name access. Parse exact exporter comments to identify content hash and shot node IDs. Audit:

```js
report.master = {
    name: master.name,
    width: master.width,
    height: master.height,
    fps: master.frameRate,
    durationSeconds: master.duration,
    durationFrames: Math.round(master.duration * master.frameRate),
    layers: auditMasterLayers(master)
};
```

Traverse each shot recursively with cycle detection. Do not call `save`, `close`, `remove`, `undo`, or any mutating property setter.

- [ ] **Step 4: Package the audit runtime**

Update `buildAfterEffects` to validate and copy `audit-full-lesson.jsx` beside the existing panel and Shot 32 audit. Extend build tests to assert byte identity and ES3 safety.

- [ ] **Step 5: Implement deterministic evidence derivation**

`assemble-full-lesson-evidence.mjs` must independently:

- recompute the package canonical content hash;
- require schema 2.0 and seconds;
- require all 48 configured node IDs in order;
- require package durations and starts to cover exactly 840 seconds;
- require master duration 840 seconds / 25,200 frames;
- require 48 master layers with exact source, start, in, and out values;
- require every recursive precomp to match its shot duration;
- reject credentials and `/Users/` paths;
- generate all derived JSON and a SHA-256 manifest;
- support `--write`, `--verify`, and `--root`.

- [ ] **Step 6: Add Python falsification and redaction tests**

Clone only the evidence tree into `tmp_path`, verify it, mutate one master out-point, and assert verification fails. Add credential/path scans identical to the Shot 32 gate.

- [ ] **Step 7: Run focused and full checks**

Run:

```bash
npm test
npm run typecheck
npm run typecheck:controller
npm run build
uv run pytest -q ../../../../../tests/test_video_001_exporter.py
```

Expected: all checks pass before live evidence exists by using committed synthetic full-package fixtures; live files remain a separate gate.

- [ ] **Step 8: Commit Task 3**

```bash
git add src/ae/audit-full-lesson.jsx scripts/assemble-full-lesson-evidence.mjs evidence/full-lesson/.gitkeep scripts/build.mjs tests/ae-host-runtime.test.ts tests/ui-protocol.test.ts ../../../../../tests/test_video_001_exporter.py
git commit -m "test: audit the complete AE lesson export"
```

---

### Task 4: Reproducible source release and operator documentation

**Files:**
- Create: `README.md`
- Create: `scripts/build-release.mjs`
- Create: `scripts/verify-release.mjs`
- Create: `tests/release.test.ts`
- Modify: `package.json`
- Modify: `PROVENANCE.md`
- Modify: `../../../../../tests/test_video_001_exporter.py`

**Interfaces:**
- Produces: `release/video001-figma-ae-exporter-0.2.0.tar.gz`.
- Produces: `release/video001-figma-ae-exporter-0.2.0.sha256`.
- Consumes only committed source plus fresh `dist` output.

- [ ] **Step 1: Write failing release tests**

Assert two builds in separate temporary directories have identical archive SHA-256. Open the archive and require:

```ts
const required = [
  "README.md",
  "LICENSE",
  "PROVENANCE.md",
  "package.json",
  "package-lock.json",
  "config/video001-figma-scenes.json",
  "dist/figma/manifest.json",
  "dist/figma/code.js",
  "dist/figma/ui.html",
  "dist/bridge/video001-bridge.mjs",
  "dist/ae/Video001-Figma-AE-Exporter.jsx",
  "dist/ae/audit-export.jsx",
  "dist/ae/audit-full-lesson.jsx",
  "dist/ae/figma-scenes.json"
];
```

Reject symlinks, absolute paths, `..`, credentials, `.figma-plugin-id`, evidence, `.aep`, and mutable user paths.

- [ ] **Step 2: Run the release test and verify red**

Run:

```bash
npx tsx --test --test-concurrency=1 tests/release.test.ts
```

Expected: FAIL because release scripts and README do not exist.

- [ ] **Step 3: Implement a deterministic archive**

`build-release.mjs` must:

- require a clean `npm run build` output;
- stage an explicit allowlist;
- normalize archive paths to POSIX separators;
- use fixed file modes, UID/GID 0, owner/group `root`, and mtime `2026-07-23T00:00:00Z`;
- emit deterministic ustar bytes and gzip with a zero timestamp;
- write the archive through a temporary file and atomic rename;
- write a lowercase SHA-256 checksum line.

Do not shell out to `tar`, `zip`, or platform-specific tools.

- [ ] **Step 4: Write operator documentation**

`README.md` must put prerequisites first:

- macOS with Figma desktop and After Effects 25+;
- Node.js 20+ only for building/running the bridge;
- no Creative Cloud requirement;
- install with `npm ci`;
- create local `.figma-plugin-id`;
- `npm run build`;
- import `dist/figma/manifest.json` as a development plugin;
- run `dist/ae/Video001-Figma-AE-Exporter.jsx` in AE;
- start/pair/build/send/import;
- use `Build full lesson (48 shots)`;
- duplicate/version behavior;
- font/raster warnings;
- troubleshooting and recovery;
- source/release license and verification.

- [ ] **Step 5: Add package scripts and provenance**

Set exporter version to `0.2.0` consistently and add:

```json
"release:build": "node scripts/build-release.mjs",
"release:verify": "node scripts/verify-release.mjs"
```

Update `PROVENANCE.md` with the official `figma.getNodeByIdAsync` documentation access date and the full-lesson adapter boundary.

- [ ] **Step 6: Run release and clean-clone checks**

Run:

```bash
npm test
npm run typecheck
npm run typecheck:controller
npm run build
npm run release:build
npm run release:verify
npm audit
uv run pytest -q ../../../../../tests/test_video_001_exporter.py
```

Expected: all checks pass and `npm audit` reports zero vulnerabilities.

- [ ] **Step 7: Commit Task 4**

```bash
git add README.md PROVENANCE.md package.json package-lock.json scripts/build-release.mjs scripts/verify-release.mjs tests/release.test.ts ../../../../../tests/test_video_001_exporter.py
git commit -m "build: package the exporter source release"
```

---

### Task 5: Live 48-shot Figma → bridge → AE release gate

**Files:**
- Create: `evidence/full-lesson/raw/full-lesson-package.video001-ae.json`
- Create: `evidence/full-lesson/raw/full-lesson-import-report.json`
- Create: `evidence/full-lesson/raw/full-lesson-ae-audit.json`
- Create: `evidence/full-lesson/raw/full-lesson-live-session.json`
- Create: `evidence/full-lesson/raw/full-lesson-bridge-log.jsonl`
- Generate: `evidence/full-lesson/audit.json`
- Generate: `evidence/full-lesson/summary.json`
- Generate: `evidence/full-lesson/manifest.json`
- Modify: `../../../../../tests/test_video_001_exporter.py`

**Interfaces:**
- Consumes: built `0.2.0` plugin, bridge, AE panel, full audit, and canonical timing.
- Produces: immutable proof tied by one content hash across Figma, bridge, AE import report, shot comps, and master.

- [ ] **Step 1: Record safety baselines**

Run:

```bash
shasum -a 256 ../video-001-what-ai-models-actually-do.aep
git status --short
```

Expected AEP hash: `ffbb3daa7b1cc225cdacc1ed4e490da083c85c9e3877162293993cd6306a3881`. Expected worktree: clean.

- [ ] **Step 2: Create a new isolated AE proof project**

Use a guarded ExtendScript that refuses any target except:

```text
/private/tmp/Video001-Exporter-Full-Lesson.aep
```

The new project must be empty before the import. Start the built panel and local bridge. Do not open or save the production AEP.

- [ ] **Step 3: Build and send the full lesson from Figma**

Reload the development plugin, click `Build full lesson (48 shots)`, and require:

- 48 listed frames;
- total package duration 840 seconds;
- schema 2.0 and seconds;
- package-ready status;
- bridge response `EXPORT_ACCEPTED`.

Capture the queued package through a validating repository script before AE consumes it.

- [ ] **Step 4: Import and run the full audit**

Use the normal `Import next` path. Require:

- 48 created shot root comps;
- `VIDEO001_MASTER_v001`;
- 840 seconds / 25,200 frames;
- continuous exact master layer coverage;
- explicit font/raster fallbacks;
- no missing assets;
- queue count zero.

Run `audit-full-lesson.jsx`, save the temporary AEP, and capture only redacted raw output.

- [ ] **Step 5: Prove unchanged resend idempotency**

Send the same Figma package again and import through `Import next`. Require `DUPLICATE_CONTENT`, unchanged project item count, no `_v002`, and empty queue.

- [ ] **Step 6: Assemble and verify evidence**

Run:

```bash
node scripts/assemble-full-lesson-evidence.mjs --write
node scripts/assemble-full-lesson-evidence.mjs --verify
```

Then scan every evidence file for credentials, authorization headers, `/Users/`, and token-like strings.

- [ ] **Step 7: Run final clean-clone verification**

In a standalone temporary clone with no `.figma-plugin-id`, run the exporter
commands from `course/videos/001-computer-learning-from-text/after-effects/exporter`:

```bash
npm ci
npm test
npm run typecheck
npm run typecheck:controller
npm run build -- --plugin-id-file /private/tmp/video001-review-plugin-id
npm run release:build
npm run release:verify
npm audit
```

Then run the repository integration test from the clone root:

```bash
uv run pytest -q tests/test_video_001_exporter.py
```

Expected: all checks pass; `npm audit` reports zero vulnerabilities.

- [ ] **Step 8: Recheck production AEP and commit evidence**

Run:

```bash
shasum -a 256 ../video-001-what-ai-models-actually-do.aep
```

Expected hash remains exactly `ffbb3daa7b1cc225cdacc1ed4e490da083c85c9e3877162293993cd6306a3881`.

Commit:

```bash
git add evidence/full-lesson ../../../../../tests/test_video_001_exporter.py
git commit -m "test: prove the complete Figma AE lesson export"
```

- [ ] **Step 9: Independent review**

Review the complete range from `a88a6aa` through the evidence commit. The verdict must be `APPROVED` before the animation increment starts.

---

## Critical Path and Rollback

Task 1 → Task 2 → Task 3 → Task 4 → Task 5 is serialized because each later task consumes the prior public interface. Tests within a task may run in parallel.

Rollback is commit-scoped. Each task is independently revertible. Live evidence uses a disposable temporary AEP, and the production AEP is protected by an exact pre/post SHA-256 gate.

## Completion Gate

The exporter increment is complete only when:

- the full package is produced by the live Figma plugin;
- the bridge accepts it;
- AE creates 48 editable shots plus one exact master;
- duplicate resend is a no-op;
- deterministic full evidence verifies;
- clean-clone checks and release checks pass;
- independent review returns `APPROVED`;
- the production AEP hash is unchanged.
