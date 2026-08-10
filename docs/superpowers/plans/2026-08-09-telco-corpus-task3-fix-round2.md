# Telco Corpus Task 3 Fix Round 2 Implementation Plan

**Goal:** Make Task 3's durable evidence and operator progress truthful across unsealed windows, interruption, calibration, and restart while preserving byte-identical output.

**Architecture:** Keep the SQLite unit commit as the only durable corpus-state boundary. Accumulate raw/normalized/quality/corpus/quota evidence in memory while a unit is open, snapshot it atomically with the unit, and restore the newest committed snapshot. Emit progress from the same live snapshot on a monotonic interval without advancing durable cursors. Keep calibration as a stop condition only, so restart uses journal state and produces the same artifacts as an uninterrupted build.

**Tech Stack:** Python, SQLite, pytest, Hugging Face tokenizer bindings, JSONL and uint16 shard artifacts.

---

### Task 1: Lock down artifactless unit publication

**Files:**
- Modify: `matgpt/data/local_state.py`
- Test: `tests/test_local_build_state.py`
- Test: `tests/test_local_corpus.py`

1. Preserve the handed-off atomic `published=1` transaction behavior for units with no artifacts.
2. Extend tests through journal reopen, identity validation, reconciliation, and provisional verification.
3. Run the focused state tests.

### Task 2: Persist truthful cumulative corpus evidence

**Files:**
- Modify: `matgpt/data/local_corpus.py`
- Test: `tests/test_local_corpus.py`

1. Add failing tests for exact raw/normalized/quality/corpus/quota counts, split token/character/raw-byte counts, license counts, rejection categories, heldout identity/content chains, and per-item overshoot evidence.
2. Track raw rows before normalization, including empty rows, without changing source cursors.
3. Persist bounded streaming validation digests and cumulative counters in each atomic unit state.
4. Restore the newest committed snapshot deterministically and prove resume/clean equivalence.

### Task 3: Emit truthful interval progress for unsealed windows

**Files:**
- Modify: `matgpt/data/local_corpus.py`
- Test: `tests/test_local_corpus.py`

1. Add a fake-monotonic-clock test whose unit spans multiple deterministic windows.
2. Invoke progress after every window; interval-gate with monotonic time and always emit terminal states.
3. Include stage/source/bucket/item, item/stage quota requested and actual, rejection evidence, pending/last unit, elapsed/rolling/overall throughput and ETA, RSS, storage, publication, and Drive verification.
4. Preserve atomic write, file and directory fsync, and a readable operator line; restore timing from committed state.

### Task 4: Prove calibration stop/resume equivalence and verify

**Files:**
- Test: `tests/test_local_corpus.py`
- Modify: `.superpowers/sdd/2026-08-09-telco-resumable-local-corpus-builder/task-3-report.md`

1. Add a two-stage calibration stop/resume test comparing provisional manifest identity and every destination JSONL/bin byte with an uninterrupted build.
2. Run focused RED/GREEN tests, the requested Task 3/state/publish/quality/tokens/telco_prepare/sample suite, and static checks.
3. Review the complete scoped diff, append exact commands/results and the seven-finding audit to the report, and commit all remaining Task 3 changes.
