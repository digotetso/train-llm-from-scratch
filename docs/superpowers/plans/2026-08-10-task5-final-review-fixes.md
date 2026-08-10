# Task 5 Final Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make preserved pilot reuse prove real producer quota semantics, immutable checkpoint provenance, and mutation-free failure for legacy publication state.

**Architecture:** Keep validation fail-closed at the Task 5 CLI boundary while adding a small shared checkpoint-binding producer helper used by evaluation scripts and notebook evidence writers. Journal publication recovery checks legacy destination state before recording a mapping. Tests invoke the real metadata/evidence producers with local synthetic files only.

**Tech Stack:** Python 3.12, pytest, JSON, NumPy shard metadata, SQLite journal, Jupyter notebook JSON.

## Global Constraints

- Strict TDD: every production behavior starts with an observed failing test.
- No real source, network, Drive, corpus build, GPU, training, or evaluation operation.
- Preserve authoritative preflight check IDs and 4 MiB/depth-64/count-256 evidence bounds.
- Existing path-only checkpoint evidence must fail closed; no retrospective fingerprints.
- Smoke and pilot checkpoint snapshots are immutable, distinct, positive-sized, and no-overwrite.

---

### Task 1: Producer-Accurate Pilot Quota and EOS Accounting

**Files:**
- Modify: `scripts/prepare_telco_local.py`
- Modify: `tests/test_tokenizer_candidate.py`

**Interfaces:**
- Consumes: `build_split_metadata(...)` output and `telco_prepare` v1 manifest fields.
- Produces: `_validated_pilot_manifest(...)` and legacy evidence validation that reconcile pre-EOS quota plus one EOS per document.

- [ ] **Step 1: Write failing producer-schema tests**

  Replace the sparse exact-20M shard fixture with nonempty `uint16` shard files built through `build_split_metadata`. Use literal manifest relationships: `requested_tokens=20_000_000`, `quota_tokens>=requested_tokens`, and `metadata.total_tokens=quota_tokens+documents`. Add independent wrong/missing pilot and validation quota/document/EOS mutations.

- [ ] **Step 2: Verify RED**

  Run the focused legacy producer tests and confirm the legal whole-document overshoot fixture is rejected by the old `total_tokens == requested_tokens` check while at least one wrong relationship is accepted.

- [ ] **Step 3: Implement exact accounting**

  Require bool-safe nonnegative integer `requested_tokens`, `quota_tokens`, and `documents`; exact 20M pilot request; quota at least request; append-EOS metadata totals equal quota plus documents for pilot and validation; document totals and actual/requested accounting reconcile. Retain split, dtype, safe shard, byte, SHA, sum, and vocabulary checks.

- [ ] **Step 4: Verify GREEN**

  Run the focused producer positive and mutation matrix; all must pass without allocating or processing a real 20M-token corpus.

---

### Task 2: Immutable Checkpoint Provenance Across Evidence Producers

**Files:**
- Create or modify: `matgpt/training/checkpoint_provenance.py`
- Modify: `scripts/evaluate.py`
- Modify: `scripts/evaluate_tasks.py`
- Modify: `scripts/compare_checkpoints.py`
- Modify: `scripts/score_story_judgments.py`
- Modify: `scripts/prepare_telco_local.py`
- Modify: `notebooks/train_matgpt_telco_300m_colab.ipynb`
- Modify: relevant evaluation, comparison, scorer, notebook, and candidate tests.

**Interfaces:**
- Produces: `checkpoint_binding(path)` returning `{path, size, sha256}` after rejecting missing/zero-sized files, and immutable snapshot creation that uses a content-SHA filename, `O_EXCL`/equivalent no-overwrite semantics, and verifies an existing identical snapshot.
- Consumers: every smoke, pilot, base evaluation, task evaluation, comparison detail/summary, and scored review artifact; Task 5 gate validator cross-reconciles identical path/size/SHA records.

- [ ] **Step 1: Write failing producer and validator tests**

  Invoke producer functions with tiny local checkpoint bytes and assert emitted bindings. Add REDs for path-only evidence, zero bytes, pilot bytes replaced followed by scorer-only refresh, mismatched role size/SHA, and smoke/pilot snapshot overwrite or aliasing.

- [ ] **Step 2: Verify RED**

  Run exact producer and gate probes and record failures caused by missing binding fields, mutable `latest.pt`, or journal-time rehashing.

- [ ] **Step 3: Add shared binding and snapshot behavior**

  Normalize each checkpoint path at creation, reject zero size, hash bytes once for evidence, copy+fsync to a SHA-named snapshot without overwriting divergent content, and return its binding. Update notebook smoke and pilot gates to create separate snapshots and evaluate only the pilot snapshot.

- [ ] **Step 4: Propagate and cross-reconcile bindings**

  Emit the binding from `evaluate.py`, `evaluate_tasks.py`, each comparison detail, comparison summary, and scored output. Validate every role against the same current immutable binding and the relevant config/tokenizer/build identity; reject path-only legacy evidence with a rerun-gates message.

- [ ] **Step 5: Verify GREEN**

  Run focused producer positives and stale/zero/path-only/snapshot negatives, followed by all evaluate/tasks/compare/scorer/notebook tests.

---

### Task 3: Mutation-Free Legacy Publication Refusal

**Files:**
- Modify: `matgpt/data/local_publish.py`
- Modify: `tests/test_local_publish.py`

**Interfaces:**
- Consumes: `LocalBuildJournal.artifact(...)`, destination existence, and `prepared_publication(...)`.
- Produces: a preflight guard used by `publish()` and fresh `reconcile()` before `record_destination()` or filesystem mutation.

- [ ] **Step 1: Write failing byte-for-byte state tests**

  Snapshot source/final bytes and mtimes plus the complete artifact row, counters, and units before direct publish and fresh reconcile. Assert a final-without-receipt raises and every snapshot remains exactly identical, including `destination_relative_path is None`.

- [ ] **Step 2: Verify RED**

  Confirm current code mutates `destination_relative_path` before raising.

- [ ] **Step 3: Move the integrity guard before mutation**

  Resolve the destination candidate read-only, and when it exists for an unpublished artifact without a prepared receipt, raise before `record_destination`, temporary-file cleanup, destination writes, source release, or metric updates. Leave destination-absent and receipt-bearing flows unchanged.

- [ ] **Step 4: Verify GREEN**

  Run the direct/fresh-reconcile state tests and the full publication/state suites, including the prepared-receipt crash matrix.

---

### Task 4: Full Verification, Self-Review, Report, and Commit

**Files:**
- Modify: `.superpowers/sdd/2026-08-09-telco-resumable-local-corpus-builder/task-5-report.md` (ignored local evidence log)

**Interfaces:**
- Consumes: all prior GREEN behavior.
- Produces: one clean Task 5 round-5 commit with exact test totals and explicit deferred items.

- [ ] **Step 1: Run all requested suites**

  Run Task5, Task3, publication/state, preflight, evaluate, evaluate_tasks, comparison, scorer, both notebook, and producer tests with no operational providers.

- [ ] **Step 2: Run static checks**

  Compile modified Python files, parse both notebook JSON files, and run `git diff --check`.

- [ ] **Step 3: Self-review**

  Trace each producer schema into the validator and verify checkpoint bytes cannot change between roles. Trace publication crash ordering and prove the legacy guard precedes every database or filesystem mutation.

- [ ] **Step 4: Append evidence and commit**

  Record exact RED/GREEN/final outputs, no-real-ops statement, residual risk, and the separately deferred invalid legacy-SHA fixture. Stage only Task 5 round-5 files and commit.
