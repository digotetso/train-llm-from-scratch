# Streaming Asset Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream embedded base64 assets through the loopback bridge while preserving the existing 768 MiB wire and canonical fingerprint contracts.

**Architecture:** A dependency-free JSON reader externalizes only top-level asset data strings to verified files. Shared contract validation accepts file evidence through a narrow adapter, canonical hashing streams those files back as base64, and QueueStore publishes reverified files plus the existing slim manifest.

**Tech Stack:** TypeScript, Node.js 20 standard library, `node:test`, no runtime dependencies.

## Global Constraints

- Preserve the exact vendor JSON schema and fingerprint contract.
- Enforce 32 MiB raw non-asset manifest, 32 MiB decoded per asset, 512 MiB decoded aggregate, and 768 MiB raw body limits.
- Never retain encoded asset strings in JavaScript memory.
- Use strict RED-GREEN-REFACTOR cycles and existing private-directory/identity/fsync patterns.

---

### Task 1: Shared external-asset validation

**Files:** `tests/contract.test.ts`, `src/shared/contract.ts`

**Interfaces:** Produce `validatePackageWithVerifiedAssets(value, evidence, byteCounts)` and `ExternalExporterPackage`; preserve `validatePackage` and `contentFingerprintInput`.

- [ ] Add failing tests proving external evidence receives identical schema, exact-key, length, asset-limit, duplicate-hash, and raster-reference validation.
- [ ] Run `./node_modules/.bin/tsx --test --test-name-pattern='verified external assets' tests/contract.test.ts`; expect the missing export failure.
- [ ] Refactor `validatePackageInternal` to select resident-base64 or verified-file asset validation without duplicating frame/node logic.
- [ ] Run the focused contract tests and then `npm run typecheck`; expect success.

### Task 2: Streaming reader and canonical fingerprint

**Files:** `tests/streaming-package.test.ts`, `src/bridge/streaming-package.ts`, `src/bridge/temporary-files.ts`

**Interfaces:** Produce `readStreamingPackage(spool, options)`, `fingerprintStreamingPackage(package, files)`, and identity-bound temporary-file cleanup helpers.

- [ ] Add failing tests with tiny reader chunks for arbitrary key order/whitespace, base64 quartet boundaries, escaped and noncanonical base64 rejection, non-asset manifest accounting, and raw/per-asset/aggregate ceilings.
- [ ] Run `./node_modules/.bin/tsx --test tests/streaming-package.test.ts`; expect module-not-found.
- [ ] Implement a bounded file reader, recursive JSON parser, strict streaming base64 decoder, owner-stamped file writer, and typed syntax/validation/limit failures.
- [ ] Add a failing equality test comparing the streamed fingerprint with SHA-256 of `contentFingerprintInput` for the same small package.
- [ ] Implement an async canonical walker and carry-aware decoded-bytes-to-base64 hash stream; recheck source identity/size/hash before and after reading.
- [ ] Run the focused tests and typecheck; expect success.

### Task 3: Verified queue publication

**Files:** `tests/bridge.test.ts`, `src/bridge/queue.ts`

**Interfaces:** Produce `QueueStore.enqueueVerified(value, sources)` using only identity-bound server sources.

- [ ] Add failing tests proving the same slim queued manifest/assets, source tamper rejection, hash/size recheck, private permissions, and cleanup-compatible source handling.
- [ ] Run the queue-focused test pattern; expect `enqueueVerified` missing.
- [ ] Extract the existing package lock/publication flow, copy each open verified source through a rehashing private temporary, publish with exclusive-link semantics, and reuse slim manifest serialization.
- [ ] Run focused queue tests and all existing queue tests; expect success.

### Task 4: Owner-scoped crash recovery

**Files:** `tests/bridge.test.ts`, `src/bridge/cli.ts`, `src/bridge/temporary-files.ts`

**Interfaces:** Strictly parse owner-stamped `.http-body.*.tmp` and `.http-asset.*.tmp` names and recover them only for the exact dead lifecycle owner.

- [ ] Add failing dead/live/ambiguous/malformed/mismatched/symlink recovery tests.
- [ ] Run the lifecycle-focused pattern; expect dead-owner files to remain.
- [ ] Discover temporary candidates without following them; after exact lifecycle/dead-owner validation, unlink unchanged matching files and fsync `tmp`; fail closed otherwise.
- [ ] Run focused lifecycle tests; expect success.

### Task 5: HTTP integration

**Files:** `tests/bridge.test.ts`, `src/bridge/server.ts`, `src/bridge/cli.ts`

**Interfaces:** Replace the 32 MiB whole-body read with the streaming package pipeline while preserving endpoint/status/log/concurrency contracts.

- [ ] Add failing HTTP tests using injected small limits for a raw body larger than the manifest limit because of valid asset data, all four byte ceilings, cleanup, and fingerprint/asset mismatch mappings.
- [ ] Run the bridge-focused pattern; expect valid asset-heavy input to return `413`.
- [ ] Owner-stamp the body spool, invoke the streaming reader and fingerprint, call `enqueueVerified`, and clean body/asset temporaries in `finally`; keep one active plus one waiter and the shared deadline.
- [ ] Run focused bridge tests; expect success.

### Task 6: Verification and delivery

**Files:** `.superpowers/sdd/task-3-report.md`

- [ ] Run `npm test`; require zero failures and no hanging handles.
- [ ] Run `npm run typecheck`, `git diff --check`, and `git diff --cached --check`; require zero diagnostics.
- [ ] Review auth ordering, bounds, cleanup/fsync, owner recovery, error redaction, schema parity, and canonical hash parity.
- [ ] Append exact RED/GREEN evidence and residual risk to the Task 3 report.
- [ ] Commit only focused implementation, tests, and design artifacts.
