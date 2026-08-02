# Lesson-Local Figma to After Effects Exporter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a private, production-ready direct exporter that sends Video 001 Figma frames into After Effects 25.2.2 as non-destructive, versioned, editable comps.

**Architecture:** A current Figma development plugin serializes selected lesson frames into a versioned UTF-8 package. A dependency-free Node bridge authenticates loopback requests, validates limits, and atomically queues packages. An ES3-compatible ScriptUI panel imports queued packages into new `_v###` comps using the repository’s proven native text and shape construction patterns; manual package download remains the fallback.

**Tech Stack:** TypeScript 7.0.2, esbuild 0.28.1, tsx 4.23.1, `@figma/plugin-typings` 1.131.0, Node 20+ standard library, Node test runner, Python 3.10+/pytest, Adobe ExtendScript/ScriptUI, After Effects 25.2.2, Figma Desktop 126.6.14.

## Global Constraints

- Keep all exporter files under `course/videos/001-computer-learning-from-text/after-effects/exporter/` except repository-level pytest coverage under `tests/`.
- Do not modify or open the existing animated `video-001-what-ai-models-actually-do.aep` during exporter validation.
- Do not copy DISKO Beam code. Reuse only AEUX material permitted by Apache 2.0 and record provenance from upstream commit `573d07d63b13059c6ebeb02561c89b39bb829180`.
- Bind the bridge only to `127.0.0.1`; require a one-time pairing code and a bearer token with at least 128 bits of randomness.
- Pairing codes expire after five minutes. Tokens expire after 30 days without a successful request.
- Enforce: 48 frames/request, 2,048 assets/request, 32 MiB manifest JSON, 32 MiB/decoded asset, 512 MiB aggregate decoded assets, 768 MiB HTTP body, and 120-second request timeout.
- Default output is 1920×1080 at 30 fps; shot duration comes from `figma-scenes.json`.
- Never widen Figma text boxes. Preserve UTF-8, including `θ`, `·`, and `→`.
- An unchanged content hash is idempotent. Changed content creates the next `_v###` comp and never alters an earlier version.
- Runtime Node code has no third-party dependencies. Development dependencies are pinned exactly.
- Every behavior change follows RED → verify RED → GREEN → verify GREEN → refactor.
- Preserve the user’s unrelated dirty worktree changes and stage only files named by each task.

---

## Planned File Structure

```text
course/videos/001-computer-learning-from-text/after-effects/exporter/
├── .gitignore
├── LICENSE
├── NOTICE
├── PROVENANCE.md
├── README.md
├── package.json
├── package-lock.json
├── tsconfig.json
├── scripts/
│   ├── build.mjs
│   └── generate-figma-manifest.mjs
├── src/
│   ├── shared/
│   │   ├── canonical-json.ts
│   │   ├── contract.ts
│   │   └── limits.ts
│   ├── bridge/
│   │   ├── auth.ts
│   │   ├── paths.ts
│   │   ├── queue.ts
│   │   ├── server.ts
│   │   └── cli.ts
│   ├── figma/
│   │   ├── controller.ts
│   │   ├── serializer.ts
│   │   ├── ui.ts
│   │   └── ui.html
│   └── ae/
│       ├── import-core.jsxinc
│       ├── importer.jsxinc
│       ├── panel.jsx
│       └── audit-export.jsx
├── tests/
│   ├── contract.test.ts
│   ├── auth.test.ts
│   ├── bridge.test.ts
│   ├── serializer.test.ts
│   ├── ui-protocol.test.ts
│   ├── ae-core.test.ts
│   ├── helpers/
│   │   └── package.ts
│   └── fixtures/
│       ├── unicode-frame.json
│       ├── nested-frame.json
│       └── shot-32-reference.json
└── dist/                       # generated, ignored except release archives
tests/
└── test_video_001_exporter.py
```

---

### Task 1: Reproducible Toolchain, Apache Provenance, and Shared Contract

**Files:**
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/package.json`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/package-lock.json`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/tsconfig.json`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/.gitignore`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/LICENSE`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/NOTICE`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/PROVENANCE.md`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/src/shared/limits.ts`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/src/shared/canonical-json.ts`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/src/shared/contract.ts`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/helpers/package.ts`
- Test: `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/contract.test.ts`

**Interfaces:**
- Produces: `LIMITS`, `ExporterPackage`, `validatePackage(value)`, `canonicalJson(value)`, and `contentFingerprintInput(value)`.
- Consumes: Video 001 shot timing from `../figma-scenes.json` only at integration time; the shared contract has no repository I/O.

- [ ] **Step 1: Write the failing contract test**

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { canonicalJson, contentFingerprintInput, validatePackage } from "../src/shared/contract.ts";

const valid = {
  schemaVersion: "1.0.0",
  exporterVersion: "0.1.0",
  exportedAt: "2026-07-22T00:00:00.000Z",
  contentHash: "a".repeat(64),
  source: { fileKey: "fFTux3sx2AzVQtoya67f95", pageId: "90:2" },
  target: { width: 1920, height: 1080, fps: 30 },
  frames: [{
    nodeId: "95:44",
    name: "S001_SH32_Repo_PreparationNotLearning",
    width: 1920,
    height: 1080,
    duration: 28,
    children: [{
      id: "text-1",
      kind: "text",
      name: "MODEL_Parameters",
      x: 100,
      y: 100,
      width: 300,
      height: 200,
      rotation: 0,
      opacity: 1,
      text: "θ · →",
      textBox: { width: 300, height: 200 },
      paragraph: { align: "LEFT", lineHeightPx: 76, letterSpacingPx: 0 },
      runs: [{ start: 0, end: 5, fontFamily: "Sora", fontStyle: "Bold", fontSize: 64, color: "#F5F7FB" }]
    }],
    warnings: []
  }],
  assets: []
};

test("accepts UTF-8 text without changing paragraph geometry", () => {
  const result = validatePackage(valid);
  const node = result.frames[0].children[0];
  assert.equal(node.kind, "text");
  if (node.kind !== "text") throw new Error("expected text");
  assert.equal(node.text, "θ · →");
  assert.deepEqual(node.textBox, { width: 300, height: 200 });
});

test("rejects an unknown schema major version", () => {
  assert.throws(() => validatePackage({ ...valid, schemaVersion: "2.0.0" }), /schema major/i);
});

test("canonical JSON sorts object keys but preserves array order", () => {
  assert.equal(canonicalJson({ z: 1, a: [3, 2, 1] }), '{"a":[3,2,1],"z":1}');
});

test("content fingerprints ignore export time and the fingerprint field", () => {
  const first = contentFingerprintInput(valid);
  const second = contentFingerprintInput({
    ...valid,
    exportedAt: "2026-07-23T00:00:00.000Z",
    contentHash: "b".repeat(64)
  });
  assert.equal(first, second);
});
```

- [ ] **Step 2: Add only the test toolchain and verify RED**

Create `package.json` with exact versions:

```json
{
  "name": "video-001-figma-ae-exporter",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "engines": { "node": ">=20" },
  "scripts": {
    "test": "tsx --test tests/*.test.ts",
    "typecheck": "tsc --noEmit",
    "build": "node scripts/build.mjs"
  },
  "devDependencies": {
    "@figma/plugin-typings": "1.131.0",
    "@types/node": "26.1.1",
    "esbuild": "0.28.1",
    "tsx": "4.23.1",
    "typescript": "7.0.2"
  }
}
```

Create `tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "types": ["node", "@figma/plugin-typings"],
    "skipLibCheck": false,
    "noEmit": true
  },
  "include": ["src/**/*.ts", "tests/**/*.ts", "scripts/**/*.mjs"]
}
```

Create `.gitignore`:

```gitignore
node_modules/
dist/
.figma-plugin-id
```

Run:

```bash
cd course/videos/001-computer-learning-from-text/after-effects/exporter
npm install
npm test -- tests/contract.test.ts
```

Expected: FAIL because `src/shared/contract.ts` does not exist.

- [ ] **Step 3: Implement the minimal shared contract**

Create `limits.ts`:

```ts
export const LIMITS = Object.freeze({
  maxFrames: 48,
  maxAssets: 2_048,
  maxManifestBytes: 32 * 1024 * 1024,
  maxAssetBytes: 32 * 1024 * 1024,
  maxAggregateAssetBytes: 512 * 1024 * 1024,
  maxBodyBytes: 768 * 1024 * 1024,
  requestTimeoutMs: 120_000,
  pairingTtlMs: 5 * 60_000,
  tokenIdleTtlMs: 30 * 24 * 60 * 60_000
});
```

Create `canonical-json.ts`:

```ts
export function canonicalJson(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  const record = value as Record<string, unknown>;
  return `{${Object.keys(record).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`).join(",")}}`;
}
```

Create `contract.ts` with discriminated `text`, `rect`, `ellipse`, `group`, and `raster` node interfaces; export `canonicalJson`; validate exact schema major `1`; reject non-finite geometry, unsafe names, duplicate node IDs, invalid hashes, invalid colors, empty frames, and values exceeding `LIMITS`. Preserve strings without normalization. Return a deeply cloned package so callers cannot mutate the validated input. Each asset has `{ hash, mimeType: "image/png", byteLength, dataBase64 }`; validation decodes base64 length, checks the declared byte length, and enforces per-asset and aggregate limits.

`contentFingerprintInput(value)` must validate and clone the package while allowing `contentHash` to be either empty or 64 lowercase hex characters, replace `exportedAt` and `contentHash` with empty strings, and return canonical JSON. Normal `validatePackage` still requires 64 lowercase hex characters. The SHA-256 content hash is computed over the fingerprint input by the Figma UI and recomputed by the bridge, so exporting unchanged art at a later time remains idempotent.

The exported signature must be:

```ts
export interface BaseNode {
  id: string;
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  opacity: number;
}
export interface TextRun {
  start: number;
  end: number;
  fontFamily: string;
  fontStyle: string;
  fontSize: number;
  color: string;
}
export interface TextNode extends BaseNode {
  kind: "text";
  text: string;
  textBox: { width: number; height: number };
  paragraph: { align: "LEFT" | "CENTER" | "RIGHT"; lineHeightPx: number; letterSpacingPx: number };
  runs: TextRun[];
}
export interface ShapeNode extends BaseNode {
  kind: "rect" | "ellipse";
  fill: string | null;
  stroke: string | null;
  strokeWidth: number;
  radius: number;
}
export interface GroupNode extends BaseNode { kind: "group"; children: ExportNode[] }
export interface RasterNode extends BaseNode { kind: "raster"; assetHash: string }
export type ExportNode = TextNode | ShapeNode | GroupNode | RasterNode;
export interface ExportFrame {
  nodeId: string;
  name: string;
  width: number;
  height: number;
  duration: number;
  children: ExportNode[];
  warnings: Array<{ nodeId: string; nodeName: string; property: string; fallback: "png" }>;
}
export interface AssetDescriptor {
  hash: string;
  mimeType: "image/png";
  byteLength: number;
  dataBase64: string;
}
export interface ExporterPackage {
  schemaVersion: "1.0.0";
  exporterVersion: string;
  exportedAt: string;
  contentHash: string;
  source: { fileKey: string; pageId: string };
  target: { width: number; height: number; fps: number };
  frames: ExportFrame[];
  assets: AssetDescriptor[];
}
export function validatePackage(value: unknown): ExporterPackage;
export function contentFingerprintInput(value: ExporterPackage): string;
export { canonicalJson } from "./canonical-json.ts";
```

Create `tests/helpers/package.ts` with `makeValidPackage()` returning a fresh deep clone of the exact `valid` fixture above. Later bridge and UI tests import this helper instead of relying on hidden test state.

- [ ] **Step 4: Verify GREEN and type safety**

```bash
npm test -- tests/contract.test.ts
npm run typecheck
```

Expected: 4 tests pass; TypeScript exits 0 with no diagnostics.

- [ ] **Step 5: Add exact upstream license provenance**

Copy the unmodified Apache 2.0 text from AEUX `LICENSE.md` into `LICENSE`. Create `NOTICE`:

```text
Video 001 Figma to After Effects Exporter
Copyright 2026

Includes concepts and selected derivative material from AEUX:
Copyright 2017 Google Inc.
https://github.com/google/AEUX
Licensed under the Apache License, Version 2.0.
```

Create `PROVENANCE.md` recording upstream URL, commit `573d07d63b13059c6ebeb02561c89b39bb829180`, files consulted (`Figma/AEUX/src/code.ts`, `Figma/AEUX/src/aeux.js`, `Ae/AEUX/src/host/AEFT/host.ts`), and a rule that every copied or adapted file carries a prominent modification notice.

- [ ] **Step 6: Commit the independently testable contract**

```bash
git add course/videos/001-computer-learning-from-text/after-effects/exporter
git commit -m "feat: define Figma AE exporter contract"
```

---

### Task 2: Pairing, Token Authentication, and Atomic Queue

**Files:**
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/src/bridge/auth.ts`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/src/bridge/paths.ts`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/src/bridge/queue.ts`
- Test: `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/auth.test.ts`
- Test: `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/bridge.test.ts`

**Interfaces:**
- Consumes: `ExporterPackage`, `validatePackage`, `canonicalJson`, and `LIMITS` from Task 1.
- Produces: `AuthStore`, `createPairingCode()`, `exchangePairingCode()`, `authenticateBearer()`, `QueueStore.enqueue()`, `QueueStore.quarantine()`, and a slim `QueuedPackage` whose assets reference verified content-addressed files instead of inline base64.

- [ ] **Step 1: Write failing authentication tests**

```ts
import assert from "node:assert/strict";
import { mkdtemp, readFile, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { AuthStore } from "../src/bridge/auth.ts";

test("pairing codes are one-time and expire after five minutes", () => {
  let now = 1_000;
  const auth = new AuthStore(() => now, () => Buffer.alloc(32, 7));
  const code = auth.createPairingCode();
  const token = auth.exchangePairingCode(code);
  assert.equal(Buffer.from(token, "base64url").byteLength, 32);
  assert.throws(() => auth.exchangePairingCode(code), /used|invalid/i);
  const expired = auth.createPairingCode();
  now += 5 * 60_000 + 1;
  assert.throws(() => auth.exchangePairingCode(expired), /expired/i);
});

test("bearer tokens expire after thirty idle days and can be revoked", () => {
  let now = 1_000;
  const auth = new AuthStore(() => now, () => Buffer.alloc(32, 9));
  const token = auth.exchangePairingCode(auth.createPairingCode());
  assert.equal(auth.authenticateBearer(`Bearer ${token}`), true);
  now += 30 * 24 * 60 * 60_000 + 1;
  assert.equal(auth.authenticateBearer(`Bearer ${token}`), false);
  const fresh = auth.exchangePairingCode(auth.createPairingCode());
  auth.revokeAll();
  assert.equal(auth.authenticateBearer(`Bearer ${fresh}`), false);
});

test("only token digests persist with owner-only permissions", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-auth-"));
  const auth = await AuthStore.open(join(root, "auth.json"));
  const token = auth.exchangePairingCode(auth.createPairingCode());
  const persisted = await readFile(join(root, "auth.json"), "utf8");
  assert.equal(persisted.includes(token), false);
  assert.match(persisted, /"tokenDigest":"[0-9a-f]{64}"/);
  assert.equal((await stat(join(root, "auth.json"))).mode & 0o777, 0o600);
});
```

- [ ] **Step 2: Verify authentication RED**

```bash
npm test -- tests/auth.test.ts
```

Expected: FAIL because `AuthStore` does not exist.

- [ ] **Step 3: Implement authentication with timing-safe comparison**

`AuthStore` stores only SHA-256 token digests, never raw tokens. `createPairingCode()` returns a six-digit string and stores its digest with `createdAt` and `used: false`. `exchangePairingCode(code)` verifies TTL, marks the code used before returning, generates 32 random bytes, stores the token digest and `lastUsedAt`, and returns base64url. `authenticateBearer(header)` parses exactly one `Bearer` value, compares digests with `crypto.timingSafeEqual`, refreshes `lastUsedAt` on success, and returns `false` for malformed, revoked, or idle-expired tokens. `AuthStore.open(path)` loads and atomically persists digest records to an owner-only `auth.json` file with mode `0600`, allowing the 30-day token lifetime to survive bridge restarts.

- [ ] **Step 4: Verify authentication GREEN**

```bash
npm test -- tests/auth.test.ts
```

Expected: 3 tests pass.

- [ ] **Step 5: Write failing atomic queue and path-safety tests**

```ts
import assert from "node:assert/strict";
import { mkdtemp, readFile, readdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { QueueStore } from "../src/bridge/queue.ts";

test("queue filenames derive from hashes and are atomically visible", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-exporter-"));
  const queue = new QueueStore(root);
  const result = await queue.enqueue({ contentHash: "b".repeat(64), manifest: { schemaVersion: "1.0.0" }, assets: [] });
  assert.equal(result.filename, `${"b".repeat(64)}.video001-ae.json`);
  assert.deepEqual(await readdir(join(root, "incoming")), [result.filename]);
  assert.equal((await readdir(join(root, "tmp"))).length, 0);
  assert.match(await readFile(result.path, "utf8"), /"schemaVersion":"1.0.0"/);
});

test("client names cannot escape the queue root", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-exporter-"));
  const queue = new QueueStore(root);
  await assert.rejects(queue.writeAsset("../escape.png", new Uint8Array([1])), /hash/i);
});
```

- [ ] **Step 6: Verify queue RED, then implement queue and paths**

Run `npm test -- tests/bridge.test.ts`; expect module-not-found failure. Implement `exporterRoot()` using `~/Library/Application Support/Video001FigmaAEExporter` on macOS and an injected root in tests. `QueueStore` creates `tmp`, `incoming`, `quarantine`, `assets`, and `logs` with owner-only permissions; accepts only lowercase 64-character SHA-256 filenames; opens temporary files with exclusive creation; writes UTF-8; fsyncs; closes; and renames into `incoming`. It decodes each validated asset to persistent `assets/<sha256>.png`, verifies byte length and SHA-256 before rename, and replaces `dataBase64` in the queued manifest with the absolute verified asset path. `quarantine()` writes a redacted JSON error next to the rejected package. No method accepts a caller-supplied directory.

- [ ] **Step 7: Verify queue GREEN and commit**

```bash
npm test -- tests/auth.test.ts tests/bridge.test.ts
npm run typecheck
git add course/videos/001-computer-learning-from-text/after-effects/exporter/src/bridge course/videos/001-computer-learning-from-text/after-effects/exporter/tests
git commit -m "feat: secure exporter pairing and queue"
```

Expected: 5 tests pass; typecheck exits 0.

---

### Task 3: Loopback HTTP Bridge and Operational Controls

**Files:**
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/src/bridge/server.ts`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/src/bridge/cli.ts`
- Modify: `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/bridge.test.ts`

**Interfaces:**
- Consumes: `AuthStore`, `QueueStore`, `validatePackage`, and `LIMITS`.
- Produces: `createBridgeServer({ auth, queue, host, port })`, health/pair/export endpoints, graceful shutdown, redacted structured logs.

- [ ] **Step 1: Add failing end-to-end HTTP tests**

Add tests that start the server on `127.0.0.1` with port `0`, then assert:

```ts
import { makeValidPackage } from "./helpers/package.ts";

const validPackage = makeValidPackage();
const health = await fetch(`${base}/health`);
assert.equal(health.status, 200);
assert.deepEqual(await health.json(), { status: "ok", schemaMajor: 1 });

const unauthorized = await fetch(`${base}/v1/export`, {
  method: "POST",
  headers: { "content-type": "application/vnd.video001.figma-ae+json" },
  body: JSON.stringify(validPackage)
});
assert.equal(unauthorized.status, 401);

const paired = await fetch(`${base}/v1/pair`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ code })
});
const { token } = await paired.json();
assert.equal(paired.status, 200);

const accepted = await fetch(`${base}/v1/export`, {
  method: "POST",
  headers: {
    authorization: `Bearer ${token}`,
    "content-type": "application/vnd.video001.figma-ae+json"
  },
  body: JSON.stringify(validPackage)
});
assert.equal(accepted.status, 202);
```

Also assert `413` for a body above an injected 1 KiB test limit, `415` for the wrong media type, `422` for invalid schema, `409` for a queued duplicate hash, no CORS response headers, and listener address `127.0.0.1`. Assert five failed pairing attempts in 60 seconds cause `429 PAIRING_RATE_LIMITED` until the window expires. Add deterministic retention tests showing quarantine/log files older than seven days are deleted, fresh files remain, and a log rotates before exceeding 10 MiB.

- [ ] **Step 2: Verify HTTP RED**

```bash
npm test -- tests/bridge.test.ts
```

Expected: FAIL because `createBridgeServer` does not exist.

- [ ] **Step 3: Implement the minimal HTTP server**

Use `node:http`, `AbortSignal.timeout`, and streaming byte accounting. Routes are exact:

```text
GET  /health    -> unauthenticated status only
POST /v1/pair   -> JSON pairing-code exchange
POST /v1/export -> authenticated vendor JSON package
POST /v1/reset  -> authenticated token revocation
```

Return JSON errors as `{ "error": { "code": "...", "message": "..." } }`. Never echo tokens, request bodies, stack traces, or asset data. Set `cache-control: no-store` and `x-content-type-options: nosniff`; do not add CORS response headers because network requests originate in the privileged Figma plugin controller, not its UI iframe. Destroy oversized request streams immediately. Rate-limit pairing globally to five failed attempts per rolling 60 seconds and reset the failure count after a successful exchange. Recompute SHA-256 from `contentFingerprintInput`, reject a mismatched `contentHash`, decode and verify every asset hash before enqueue, prune quarantine/log files older than seven days at startup, and rotate a log before its next write would exceed 10 MiB.

`cli.ts` accepts only `--root <absolute-path>` and `--port <0..65535>`, creates the pairing code, writes `state.json` atomically with mode `0600` and `{ pid, port, pairingCode, pairingExpiresAt }`, handles `SIGINT`/`SIGTERM`, removes `state.json` on clean exit, and exits nonzero on bind/config errors.

- [ ] **Step 4: Verify HTTP GREEN and operational shutdown**

```bash
npm test -- tests/bridge.test.ts
npm run typecheck
```

Expected: all bridge tests pass; no open-handle warning remains.

- [ ] **Step 5: Commit the bridge**

```bash
git add course/videos/001-computer-learning-from-text/after-effects/exporter/src/bridge course/videos/001-computer-learning-from-text/after-effects/exporter/tests/bridge.test.ts
git commit -m "feat: add authenticated loopback export bridge"
```

---

### Task 4: Pure Figma Serializer and Raster-Fallback Decisions

**Files:**
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/src/figma/serializer.ts`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/serializer.test.ts`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/fixtures/unicode-frame.json`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/fixtures/nested-frame.json`

**Interfaces:**
- Consumes: normalized Figma-like node snapshots and the shared contract.
- Produces: `serializeFrame(node, timing, options): Promise<ExportFrame>` and `classifyNode(node): "native" | "group" | "raster"`.

- [ ] **Step 1: Write failing serializer tests from real lesson edge cases**

Fixtures must include Shot 32’s title, `θ`, and `·`; a right-aligned text box; a nested group; a simple solid rectangle; a gradient rectangle; and a rotated child. Tests assert:

```ts
const frame = await serializeFrame(fixture, { duration: 28 }, { rasterScale: 1 });
const theta = findNode(frame, "MODEL_Parameters");
assert.equal(theta.kind, "text");
if (theta.kind !== "text") throw new Error("expected text");
assert.equal(theta.text, "θ");
assert.deepEqual(theta.textBox, { width: 104, height: 112 });

const title = findNode(frame, "TXT_Title");
assert.equal(title.kind, "text");
if (title.kind !== "text") throw new Error("expected text");
assert.equal(title.textBox.width, fixtureTitle.width);
assert.equal(title.text.includes("\n"), fixtureTitle.characters.includes("\n"));

assert.equal(findNode(frame, "DATA_Node_01").kind, "group");
assert.equal(findNode(frame, "DATA_SolidRect").kind, "rect");
assert.equal(findNode(frame, "FX_GradientRect").kind, "raster");
assert.equal(findNode(frame, "TXT_Rotated").rotation, 17);
```

- [ ] **Step 2: Verify serializer RED**

```bash
npm test -- tests/serializer.test.ts
```

Expected: FAIL because `serializeFrame` does not exist.

- [ ] **Step 3: Implement classification and serialization**

Rules are deterministic:

```text
TEXT with solid fills and no unsupported effect -> native text
RECTANGLE/ELLIPSE with one solid fill and optional solid stroke -> native shape
FRAME/GROUP/COMPONENT/INSTANCE whose children can be represented -> group
image fills, gradients, masks, blend modes other than NORMAL, blur/shadow/effects,
boolean/vector/star/polygon/line, or any unsupported mixed property -> raster
```

Use `absoluteTransform` relative to the selected frame, not viewport coordinates. Preserve rotation, opacity, z-order, exact node name, exact `characters`, paragraph box width/height, alignment, line height, letter spacing, and styled text segments. Never Unicode-normalize. Record a structured warning for every raster decision with `nodeId`, `nodeName`, `property`, and `fallback: "png"`.

- [ ] **Step 4: Verify serializer GREEN and commit**

```bash
npm test -- tests/serializer.test.ts
npm run typecheck
git add course/videos/001-computer-learning-from-text/after-effects/exporter/src/figma/serializer.ts course/videos/001-computer-learning-from-text/after-effects/exporter/tests
git commit -m "feat: serialize lesson frames with safe fallbacks"
```

Expected: serializer tests pass and no string/geometry mutation occurs.

---

### Task 5: Current Figma Plugin, Pairing UI, Live Send, and Manual Fallback

**Files:**
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/src/figma/controller.ts`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/src/figma/ui.ts`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/src/figma/ui.html`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/scripts/generate-figma-manifest.mjs`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/scripts/build.mjs`
- Test: `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/ui-protocol.test.ts`

**Interfaces:**
- Consumes: `serializeFrame`, shared contract, bridge HTTP routes, `figma.currentPage.selection`, `figma.clientStorage`, `SceneNode.exportAsync`.
- Produces: bundled Figma `code.js`, `ui.html`, and a local manifest generated with a Figma-assigned ID.

- [ ] **Step 1: Consult current Figma API documentation before coding**

Use Context7 for `@figma/plugin-typings` 1.131.0 if available. If Context7 is unavailable in the execution environment, use only Figma’s official plugin manifest, dynamic-page loading, text styled-segment, exportAsync, clientStorage, and network-access documentation. Record the exact documentation URLs and access date in `PROVENANCE.md`.

- [ ] **Step 2: Write failing controller/UI protocol tests**

Test these exact messages:

```ts
type ControllerToUi =
  | { type: "selection"; frames: FrameSummary[] }
  | { type: "package-unhashed"; value: ExporterPackage }
  | { type: "bridge-result"; status: number; code: string; message: string }
  | { type: "failure"; code: string; message: string };

type UiToController =
  | { type: "refresh-selection" }
  | { type: "build-package" }
  | { type: "package-ready"; value: ExporterPackage }
  | { type: "pair"; code: string }
  | { type: "send-live" }
  | { type: "close" };
```

Assert zero selection produces `NO_FRAME_SELECTED`, non-frame selection produces `SELECTION_NOT_FRAME`, an unknown frame ID produces `SHOT_TIMING_NOT_FOUND`, and Shot 32 maps node `95:44` to duration `28` from `figma-scenes.json`. Assert only the controller accesses `figma.clientStorage` and sends network requests; the UI never receives a bearer token. Assert the controller sends the vendor media type, neither bundle logs the token, and the UI exposes both “Send to After Effects” and “Download package.”

- [ ] **Step 3: Verify plugin RED**

```bash
npm test -- tests/ui-protocol.test.ts
```

Expected: FAIL because controller/UI modules do not exist.

- [ ] **Step 4: Implement controller and raster asset export**

`controller.ts` accepts only top-level Video 001 frames on `figma.currentPage` with node IDs present in `figma-scenes.json`, serializes each frame, calls `exportAsync({ format: "PNG", constraint: { type: "SCALE", value: 1 } })` only for nodes classified as raster, and posts an unhashed package to the UI. After the UI returns `package-ready`, the controller validates and retains it. Pairing and live-send requests execute in the controller’s privileged plugin context. The bearer token is stored only with `figma.clientStorage` and is never posted to the UI iframe.

- [ ] **Step 5: Implement paired UI and manual download**

`ui.ts` owns display, SHA-256 computation with Web Crypto, and manual download. On `package-unhashed`, it hashes `contentFingerprintInput(value)`, sets `contentHash`, posts `package-ready` to the controller, and retains the same validated value for download. It displays bridge status, pairing-code field, selected frames, native/raster counts, structured warnings, and send/download buttons. Pairing and send buttons post commands to the controller. A `401` bridge result makes the controller clear client storage. An unavailable bridge leaves manual download enabled. The manual filename is `<frame-name>-<first-12-hash>.video001-ae.json` and content is UTF-8 `application/vnd.video001.figma-ae+json`.

- [ ] **Step 6: Generate a valid development manifest without committing a fake ID**

`generate-figma-manifest.mjs` reads `.figma-plugin-id`, requires its trimmed contents to match `/^[0-9]{10,30}$/`, and exits nonzero otherwise. It writes `dist/figma/manifest.json` with:

```json
{
  "name": "Video 001 → After Effects",
  "id": "1661000000000000000",
  "api": "1.0.0",
  "main": "code.js",
  "ui": "ui.html",
  "editorType": ["figma"],
  "documentAccess": "dynamic-page",
  "networkAccess": {
    "allowedDomains": ["none"],
    "devAllowedDomains": ["http://127.0.0.1:3456"],
    "reasoning": "Transfers selected lesson frames to the local After Effects bridge."
  }
}
```

The numeric ID above is a test example only. The implementation replaces it with the validated numeric contents of `.figma-plugin-id`; the generated manifest never contains the example value unless Figma actually assigned that value.

- [ ] **Step 7: Verify plugin GREEN, build, and commit**

```bash
npm test -- tests/ui-protocol.test.ts tests/serializer.test.ts
npm run typecheck
npm run build
test -f dist/figma/manifest.json
test -f dist/figma/code.js
test -f dist/figma/ui.html
git add course/videos/001-computer-learning-from-text/after-effects/exporter
git commit -m "feat: add direct Figma lesson exporter"
```

Before running the build, use Figma’s “Create new plugin” flow to create `Video 001 → After Effects`, then write exactly its assigned numeric ID and one trailing newline to ignored file `.figma-plugin-id`. Expected: tests pass; build artifacts exist; the generated manifest contains that assigned ID. Never reuse the DISKO Beam scaffold’s ID or an ID registered to another plugin.

---

### Task 6: Testable AE Core and Non-Destructive Versioning

**Files:**
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/import-core.jsxinc`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/ae-core.test.ts`
- Create: `tests/test_video_001_exporter.py`

**Interfaces:**
- Consumes: validated package values represented as ES3 objects.
- Produces: `Video001ExporterCore.nextVersionName()`, `scaleRect()`, `sanitizeAeName()`, `isDuplicateHash()`, and `makeImportReport()`.

- [ ] **Step 1: Write failing pure-core tests**

Load `import-core.jsxinc` with `node:vm` and assert:

```ts
assert.equal(core.nextVersionName([], "S001_SH32_Repo_PreparationNotLearning"), "S001_SH32_Repo_PreparationNotLearning_v001");
assert.equal(core.nextVersionName([
  "S001_SH32_Repo_PreparationNotLearning_v001",
  "S001_SH32_Repo_PreparationNotLearning_v009"
], "S001_SH32_Repo_PreparationNotLearning"), "S001_SH32_Repo_PreparationNotLearning_v010");
assert.deepEqual(core.scaleRect({ x: 10, y: 20, width: 30, height: 40 }, 1920, 1080, 3840, 2160), { x: 20, y: 40, width: 60, height: 80 });
assert.equal(core.sanitizeAeName("../bad:name"), "bad_name");
assert.equal(core.isDuplicateHash([{ comment: "Video001Export sha256:" + "a".repeat(64) }], "a".repeat(64)), true);
```

- [ ] **Step 2: Verify core RED**

```bash
npm test -- tests/ae-core.test.ts
```

Expected: FAIL because `import-core.jsxinc` does not exist.

- [ ] **Step 3: Implement ES3-compatible core**

Use `var`, function declarations, plain objects, and loops only—no `let`, `const`, arrow functions, classes, template literals, `Array.prototype` additions, or Node globals. Export through one global `Video001ExporterCore`. Version detection must match only `^<escaped-base>_v([0-9]{3})$`, cap at `_v999`, and throw a descriptive error beyond it. Sanitization permits letters, digits, spaces, `_`, `-`, and `.`; removes path segments; and caps names at 120 characters.

- [ ] **Step 4: Add repository-level static safety tests**

`tests/test_video_001_exporter.py` must assert that exporter AE sources:

- never contain `WRAP_SLACK`, `width * 1.5`, or `CloseOptions.DO_NOT_SAVE_CHANGES`;
- contain no project close, project save, or process-wide destructive calls;
- keep `import-core.jsxinc` ES3-compatible;
- implement exact `_v###` matching and the `_v999` ceiling;
- contain no DISKO source identifiers;
- retain AEUX Apache attribution.

- [ ] **Step 5: Verify core GREEN and commit**

```bash
npm test -- tests/ae-core.test.ts
uv run pytest tests/test_video_001_exporter.py -q
git add course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/import-core.jsxinc course/videos/001-computer-learning-from-text/after-effects/exporter/tests/ae-core.test.ts tests/test_video_001_exporter.py
git commit -m "feat: add non-destructive AE import core"
```

Expected: Node core tests and pytest safety tests pass.

---

### Task 7: Native AE Importer, ScriptUI Panel, and Audit Report

**Files:**
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/importer.jsxinc`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/panel.jsx`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/src/ae/audit-export.jsx`
- Modify: `course/videos/001-computer-learning-from-text/after-effects/exporter/scripts/build.mjs`
- Modify: `tests/test_video_001_exporter.py`

**Interfaces:**
- Consumes: `Video001ExporterCore`, queue packages, `figma-scenes.json`, and AE project APIs.
- Produces: `dist/ae/Video001-Figma-AE-Exporter.jsx`, versioned comps, `import-report-<hash>.json`, and `audit-report.json`.

- [ ] **Step 1: Write failing importer-structure tests**

Extend pytest to require these exact match names and behaviors:

```python
for required in [
    'app.beginUndoGroup("Import Video 001 Figma Frame")',
    'app.project.items.addFolder("01_Exporter_Imports")',
    'comp.layers.addBoxText([textBox.width, textBox.height]',
    'property("ADBE Text Document")',
    'contents.addProperty("ADBE Vector Shape - Rect")',
    'contents.addProperty("ADBE Vector Shape - Ellipse")',
    'File.encoding = "UTF-8"',
    'Video001Export sha256:',
]:
    assert required in bundled_panel
```

Also require cleanup of only transaction-created `Item` references and prohibit project close/save calls.

- [ ] **Step 2: Verify importer RED**

```bash
uv run pytest tests/test_video_001_exporter.py -q
```

Expected: FAIL because importer/panel code is absent.

- [ ] **Step 3: Implement native import transaction**

Adapt the repository’s existing `hexToRgb`, `fontCandidates`, `addText`, and `addShape` behavior into focused importer functions. Preserve exact text box dimensions; set `TextDocument.text`, `fontObject`, `fontSize`, `leading`, `tracking`, `justification`, fill, and styled runs supported by AE 25.2.2. Use text animators only for mixed runs that differ from the dominant style. Use installed PostScript font `Inter-Regular` as the explicit fallback and report every substituted run. Shapes remain native for supported rectangles and ellipses. Groups import recursively as precomps. Raster assets import from the queue’s hash paths. Every created item is appended to `transactionItems`; on failure, remove those items in reverse order and leave pre-existing items untouched.

- [ ] **Step 4: Implement ScriptUI controls and bridge lifecycle**

The panel contains: status, pairing code and expiry, “Start bridge,” “Stop bridge,” “Reset pairing,” “Import next,” “Import file,” “Import duplicate,” and a scrollable redacted report. Starting invokes the bundled Node CLI using a fully quoted absolute path and polls `state.json`; stopping targets only the PID recorded in state after verifying its command path contains the exporter bridge. Queue polling uses `app.scheduleTask` no faster than once per second and cancels the task when the panel closes.

- [ ] **Step 5: Implement the AE audit script**

`audit-export.jsx` writes UTF-8 JSON containing project path, item count before/after, comp name/dimensions/fps/duration, every layer name/type/comment, text string/font/fontSize/box dimensions, shape match names, precomp hierarchy, content hash, missing fonts, raster fallbacks, and warnings. It never mutates the project.

- [ ] **Step 6: Bundle and verify GREEN**

`build.mjs` bundles the bridge and Figma plugin, concatenates `import-core.jsxinc`, `importer.jsxinc`, and `panel.jsx` in that order, copies `audit-export.jsx`, and fails if generated AE output contains modern syntax forbidden by Task 6.

```bash
npm run build
npm test
npm run typecheck
uv run pytest tests/test_video_001_exporter.py -q
```

Expected: all exporter tests pass; bundled AE panel is created; no prohibited syntax or project-destructive call is present.

- [ ] **Step 7: Commit importer and panel**

```bash
git add course/videos/001-computer-learning-from-text/after-effects/exporter tests/test_video_001_exporter.py
git commit -m "feat: import versioned Figma comps into After Effects"
```

---

### Task 8: Shot 32 End-to-End Proof and Fidelity Gate

**Files:**
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/tests/fixtures/shot-32-reference.json`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/evidence/shot-32-audit.json`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/evidence/shot-32-figma.png`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/evidence/shot-32-ae.png`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/evidence/shot-32-comparison.json`
- Modify: `tests/test_video_001_exporter.py`

**Interfaces:**
- Consumes: built Figma plugin, bridge, AE panel, node `95:44`, and a fresh temporary AE project.
- Produces: objective Shot 32 structural and visual evidence; establishes whether Milestone 1 passes.

- [ ] **Step 1: Capture the expected Shot 32 fixture before import**

Export the selected Figma node through the new plugin’s manual-file path. Store a redacted fixture containing exact text strings, paragraph boxes, frame geometry, node names, timing, and content hash. Capture the Figma reference screenshot at 1920×1080.

- [ ] **Step 2: Add the failing Shot 32 evidence test**

```python
def test_shot_32_evidence_preserves_unicode_wrapping_and_versioning():
    audit = json.loads((EXPORTER / "evidence/shot-32-audit.json").read_text("utf-8"))
    assert audit["comp"]["name"] == "S001_SH32_Repo_PreparationNotLearning_v001"
    assert audit["comp"]["width"] == 1920
    assert audit["comp"]["height"] == 1080
    assert audit["comp"]["fps"] == 30
    assert audit["comp"]["duration"] == 28
    texts = {layer["name"]: layer["text"] for layer in audit["layers"] if layer["type"] == "text"}
    assert texts["MODEL_Parameters"] == "θ"
    assert "·" in texts["TXT_Caveat"]
    assert audit["textChecks"]["TXT_Title"]["lineCount"] == audit["reference"]["TXT_Title"]["lineCount"]
    assert audit["mutatedPreexistingItems"] == []
```

- [ ] **Step 3: Verify evidence RED**

```bash
uv run pytest tests/test_video_001_exporter.py::test_shot_32_evidence_preserves_unicode_wrapping_and_versioning -q
```

Expected: FAIL because Shot 32 evidence is not yet present.

- [ ] **Step 4: Run the real direct export in a fresh AE project**

Install the generated Figma manifest through Figma Development plugins. Run the built ScriptUI panel in AE 25.2.2, start the bridge, pair, select node `95:44`, and send live. Run `audit-export.jsx`, save the temporary project under `/private/tmp/Video001-Exporter-Shot32.aep`, and render a settled PNG at 1920×1080. Do not open the existing animated AEP.

- [ ] **Step 5: Test duplicate and version behavior**

Send the unchanged package again and assert the panel reports `DUPLICATE_CONTENT` with no new comp. Change a harmless source property in a test duplicate of the frame, send again, and assert `_v002` is created while the audit snapshot of `_v001` remains identical.

- [ ] **Step 6: Compare fidelity and fix only through regression tests**

Compute RMSE, PSNR, and SSIM for the Figma and AE frames; record metrics in `shot-32-comparison.json`. Treat metrics as diagnostics. The hard gate is: exact Unicode, same title line count, no clipping, no missing visible content, correct geometry, supported text/shapes editable, and no mutation of prior project items. Any defect discovered here first gets a failing fixture/unit test, then the minimal correction, then the entire suite is rerun.

- [ ] **Step 7: Verify Shot 32 GREEN and commit evidence**

```bash
npm test
npm run typecheck
uv run pytest tests/test_video_001_exporter.py -q
git add course/videos/001-computer-learning-from-text/after-effects/exporter/evidence course/videos/001-computer-learning-from-text/after-effects/exporter/tests tests/test_video_001_exporter.py
git commit -m "test: prove Shot 32 Figma AE fidelity"
```

Expected: all tests pass and Milestone 1 has objective evidence. Stop here if the hard gate fails.

---

### Task 9: Representative Frames, Full 48-Shot Validation, Documentation, and Release

**Files:**
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/README.md`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/evidence/representative-audit.json`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/evidence/full-lesson-audit.json`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/evidence/security-audit.json`
- Create: `course/videos/001-computer-learning-from-text/after-effects/exporter/evidence/release-manifest.json`
- Modify: `tests/test_video_001_exporter.py`

**Interfaces:**
- Consumes: all prior artifacts and the 48 source frames.
- Produces: validated project-local release archive, install/run/rollback documentation, and complete Milestone 2/3 evidence.

- [ ] **Step 1: Add failing release-evidence tests**

Require:

```python
def test_full_lesson_export_evidence():
    evidence = json.loads((EXPORTER / "evidence/full-lesson-audit.json").read_text("utf-8"))
    assert evidence["freshProject"] is True
    assert evidence["frameCount"] == 48
    assert evidence["createdCompCount"] == 48
    assert evidence["mutatedPreexistingItems"] == []
    assert evidence["missingFonts"] == []
    assert evidence["failedFrames"] == []
    assert all(comp["name"].endswith("_v001") for comp in evidence["comps"])

def test_release_manifest_hashes_every_artifact():
    release = json.loads((EXPORTER / "evidence/release-manifest.json").read_text("utf-8"))
    assert release["schemaVersion"] == "1.0.0"
    assert release["aeuxUpstreamCommit"] == "573d07d63b13059c6ebeb02561c89b39bb829180"
    assert all(re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) for item in release["artifacts"])
```

- [ ] **Step 2: Verify release RED**

```bash
uv run pytest tests/test_video_001_exporter.py -q
```

Expected: FAIL because release evidence is absent.

- [ ] **Step 3: Run representative frame validation**

Export at least: Shot 1 (simple), Shot 4 (middle dot), Shot 6 (arrow), Shot 32 (nested/Unicode), one rotated fixture, one image-heavy fixture, and one forced raster fallback. Run structural audits and visual comparisons. Exercise expired pairing, revoked token, wrong media type, oversized body using injected test limits, path traversal name, invalid schema, partial queue file, missing font, and interrupted import. Record exact expected error codes and confirm no existing project mutation.

- [ ] **Step 4: Run all 48 frames into a fresh AE project**

Select/export all prepared frames in batches within the 48-frame limit. Import into a fresh temporary AE project. Run the audit script and assert each source node has one `_v001` comp with matching width, height, fps, duration, semantic names, native/raster counts, and import report. Do not open the animated lesson AEP.

- [ ] **Step 5: Write installation, operation, and rollback documentation**

`README.md` must document prerequisites, creating/using the Figma development plugin ID, `npm ci`, build, ScriptUI panel installation, AE scripting/network preference, pairing, live send, manual fallback, version semantics, duplicate behavior, reports, limitations, stopping the bridge, clearing local config, uninstall, rollback, and exact troubleshooting for missing fonts, bridge unavailable, invalid token, payload rejected, raster fallback, and failed import.

- [ ] **Step 6: Build the reproducible release and manifest**

Run `npm ci`, tests, typecheck, and build from a clean exporter directory. Package only `dist/figma`, `dist/bridge`, `dist/ae`, `LICENSE`, `NOTICE`, `PROVENANCE.md`, and `README.md`. Generate `release-manifest.json` with SHA-256, byte size, relative path, schema/exporter version, Node/AE/Figma versions, AEUX commit, test commands, test counts, and evidence paths.

- [ ] **Step 7: Run final verification**

```bash
cd course/videos/001-computer-learning-from-text/after-effects/exporter
npm ci
npm test
npm run typecheck
npm run build
cd ../../../../..
uv run pytest tests/test_video_001_exporter.py tests/test_video_001_after_effects.py tests/test_video_001_animation.py tests/test_course_structure.py -q
git diff --check
```

Expected: all commands exit 0; no warning/error output; 48-shot evidence passes; current Video 001 tests remain green.

- [ ] **Step 8: Review security, correctness, and project isolation**

Inspect the final diff for: loopback binding, token redaction, size enforcement, atomic writes, path containment, UTF-8 reads/writes, exact paragraph boxes, ES3 syntax, transaction cleanup, version idempotence, license notices, generated-artifact hashes, and absence of changes to the animated AEP/renders.

- [ ] **Step 9: Commit the project-local release**

```bash
git add course/videos/001-computer-learning-from-text/after-effects/exporter tests/test_video_001_exporter.py
git commit -m "feat: release lesson-local Figma AE exporter"
```

---

## Plan Self-Review Mapping

- Contract, UTF-8, limits, hashing: Tasks 1 and 4.
- Pairing, authentication, loopback, queue, retention foundations: Tasks 2 and 3.
- Current Figma plugin and valid assigned ID: Task 5.
- Exact text boxes, native layers, nested precomps, raster fallback: Tasks 4 and 7.
- Versioning, duplicate detection, transaction rollback: Tasks 6 and 7.
- Shot 32 kill criterion: Task 8.
- Representative security/fidelity validation and all 48 shots: Task 9.
- Licensing, install, reports, rollback, release hashes: Tasks 1 and 9.
