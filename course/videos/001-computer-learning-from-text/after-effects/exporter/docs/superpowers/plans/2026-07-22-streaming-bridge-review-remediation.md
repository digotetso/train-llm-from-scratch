# Streaming Bridge Review Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the promise-per-base64-byte bottleneck and make streaming cancellation, special object keys, and JSON nesting behavior production-safe and identical to the in-memory contract.

**Architecture:** A shared work-control module propagates deadline/shutdown cancellation through parse, fingerprint, and verified queue publication. The JSON reader exposes bounded contiguous slices for synchronous base64 validation/decoding, while null-prototype objects and one shared iterative container-depth preflight preserve validator parity.

**Tech Stack:** TypeScript, Node.js 20 standard library, `node:test`, no runtime dependencies.

## Global Constraints

- Preserve the exact vendor wire schema, canonical fingerprint, and 768/32/32/512 MiB byte limits.
- Keep one active export plus one bounded waiter and the 120-second shared deadline.
- Do not allocate complete encoded asset strings or weaken canonical base64 checks.
- Use strict RED/GREEN cycles and small injected assets, limits, and cancellation checkpoints.
- Do not add runtime dependencies or proceed to Task 4 before re-review approval.

---

### Task 1: Chunk-synchronous base64 parsing

**Files:**
- Modify: `tests/streaming-package.test.ts`
- Modify: `src/bridge/streaming-package.ts`

**Interfaces:**
- Produces: a reader `available()`/`consume()` boundary used by `parseBase64Asset` without an async call per encoded byte.

- [x] Add a regression that parses a moderate patterned asset, counts async promise creation and bounded parse checkpoints, and retains 1-, 2-, and 3-byte reader-boundary canonical-base64 cases.
- [x] Run the focused test and require failure because the old loop creates promises proportional to encoded bytes and has no checkpoints.
- [x] Expose the current reader slice, consume its bytes synchronously, preserve quartet state across slices, and await only per refill/decoded write/checkpoint.
- [x] Rerun the focused streaming tests and record before/after promise counts and elapsed time.

### Task 2: Exact special-key and nesting parity

**Files:**
- Modify: `tests/streaming-package.test.ts`
- Modify: `tests/contract.test.ts`
- Modify: `src/shared/limits.ts`
- Modify: `src/shared/contract.ts`
- Modify: `src/bridge/streaming-package.ts`

**Interfaces:**
- Produces: `LIMITS.maxJsonContainerDepth`; both validators count the root object as depth 1 and increment only for arrays/objects.

- [x] Add top-level, nested-node, and asset `__proto__` tests that require both `validatePackage(JSON.parse(body))` and `readStreamingPackage` to reject the unknown own key.
- [x] Run them and require streaming failures because assignment currently mutates the parsed object's prototype and hides the key.
- [x] Build all parsed objects with `Object.create(null)` and rerun the special-key tests green.
- [x] Add valid nested-group packages immediately below and above a shared 64-container limit; require normal and streaming paths to agree.
- [x] Run them and require failure because normal validation has no preflight and streaming uses divergent double-counting.
- [x] Add an iterative ancestor-aware in-memory preflight and change streaming entry counting to the shared container-only semantics; rerun parity tests green.

### Task 3: End-to-end cancellation and HTTP mapping

**Files:**
- Create: `src/bridge/work-control.ts`
- Modify: `src/bridge/streaming-package.ts`
- Modify: `src/bridge/queue.ts`
- Modify: `src/bridge/server.ts`
- Modify: `tests/streaming-package.test.ts`
- Modify: `tests/bridge.test.ts`

**Interfaces:**
- Produces: `BridgeWorkContext`, `BridgeWorkDeadlineError`, `BridgeWorkShutdownError`, and `checkpointBridgeWork(context, phase, processedBytes)`.
- Changes: `readStreamingPackage`, `fingerprintStreamingPackage`, and `QueueStore.enqueueVerified` accept the shared context through their options.

- [x] Add deterministic parse, fingerprint, and verified-copy tests whose checkpoint aborts a deadline signal and requires the typed deadline error plus private-temp cleanup.
- [x] Run them and require failure because none of the three phases accepts or checks a cancellation context.
- [x] Implement signal-aware checkpoint racing and propagate the context through reader fills, decoded/fingerprint chunks, existing-asset verification, copy chunks, and pre-publication checks.
- [x] Add an HTTP test that injects a blocked parse/fingerprint/copy checkpoint, advances the deadline, requires `408`, and proves the waiting export advances after cancellation while cleanup runs outside the slot.
- [x] Run it and require the current implementation to hang or complete without the required `408`; then pass the context from the server and release the gate from the cancellation callback.
- [x] Add shutdown coverage requiring prompt request termination and owner-safe cleanup without a leaked active slot.

### Task 4: Verification and delivery

**Files:**
- Modify: `docs/superpowers/specs/2026-07-22-streaming-asset-bridge-design.md`
- Modify ignored local report: `.superpowers/sdd/task-3-report.md`

- [x] Run focused parity, performance, cancellation, and bridge suites.
- [x] Run `npm test`, `npm run typecheck`, `git diff --check`, and `git diff --cached --check`.
- [x] Record actual checkpoint/promise/elapsed evidence, timeout mappings, Node runtime, and the existing missing-build-script residual in the report.
- [x] Review cleanup, commit boundary, error mapping, owner recovery, prototype keys, depth semantics, and scope.
- [x] Commit the focused code, tests, and design/plan changes and return the commit hash for re-review.
