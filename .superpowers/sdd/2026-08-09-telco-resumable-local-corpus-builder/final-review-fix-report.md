# Whole-plan final-review remediation report

Date: 2026-08-10

Branch: `codex/telco-tokenizer-local-prep-20260809`

Starting head: `70c36bc9d58aaef1f9220535c38309e2085ec7e8`

## Outcome

The consolidated final-review remediation is complete. It performed no real
dataset download, corpus preparation, Drive operation, tokenizer training,
model training, GPU work, or evaluation. The exact cache-disabled repository
suite passes: **719 passed, 14 skipped**.

## Critical: bounded 12B journal and finalization

- Added hash-free SQLite control APIs for unit existence, latest cumulative
  state, commit-order state streaming, publication completeness, publication
  aggregates, and artifact streaming.
- Resume reads only the latest cumulative counters/cursors. Progress uses SQL
  aggregates and the latest cumulative state. Reconciliation and finalization
  stream lightweight rows and never hydrate accepted-document hashes.
- The publisher retains only the latest in-process publication record; durable
  cumulative publication evidence remains in SQLite.
- A 128-unit query-scaling test proves four control queries remain four SELECTs
  while `_hashes_for_unit` is forbidden. End-to-end calibration, resume,
  progress, finalization, and already-complete restart also pass with
  `_hashes_for_unit` patched to raise.
- Hash lookup remains explicit only where necessary: window dedup and the
  tokenizer-sample artifact/hash integrity reconstruction path.

## Producer, identity, and preflight closure

- Normalized raw JSONL no longer serializes `token_ids`; uint16 shard IDs remain
  ephemeral. The raw schema is bound into the build identity and logical
  manifest, while re-encoding tests prove packed IDs and EOS bytes are unchanged.
- New shard metadata omits machine-specific `input_path` and `tokenizer_dir`;
  legacy metadata remains readable. The previously invalid absolute-metadata SHA
  fixture now uses its real SHA, with a separate wrong-SHA rejection.
- Preserved-pilot reuse consumes actual sharder metadata, validates uint16 IDs in
  bounded blocks, counts frozen-tokenizer EOS values, and reconciles exact split
  document totals without invented per-shard document fields.
- `quota_audit.json` is mandatory, internally hashed, manifest/plan/tokenizer
  bound, artifact-fingerprinted, and checked for exact stage/item coverage,
  totals, legal overshoot, and the minimal last-document boundary.
- Smoke and pilot snapshots must differ by content SHA. Colab evaluation uses
  exactly the immutable bindings declared by current `pilot_complete.json` and
  ignores historical checkpoint globs.
- Chunked preflight now requires `builder == "local_corpus"`; named missing-audit
  coverage proves fail-closed behavior. Optional raw-schema verification retains
  compatibility with legacy v2 manifests.

## Operational closure

- Status/progress use bounded publication aggregates; RSS uses the configured
  reader. The local notebook resolves progress only in the currently selected
  tokenizer namespace.
- Default capacity probing walks to the nearest existing ancestor of a missing
  configured local root. The local notebook probes that configured filesystem
  and renders result links only when guarded IPython `FileLink` support exists.
- Independent fresh/resume tests cover symlink rejection for `corpus.sqlite3`,
  `corpus.sqlite3-wal`, `corpus.sqlite3-shm`, and
  `corpus.sqlite3-journal`, before evidence reads, cleanup, journal open, or
  publisher/reconcile hooks. Existing journal bytes and mtimes remain unchanged.

## TDD evidence

- Journal control RED: **2 failed** (missing `has_units`; resume called
  `_hashes_for_unit`). Focused GREEN: **2 passed**; adjacent local
  state/publish/corpus: **114 passed**.
- Token-free raw/portable shard RED: **2 failed, 2 passed**. GREEN: **4 passed**.
- Pilot audit/content-distinct RED: **7 failed**. GREEN with positive real
  producer schema: **8 passed**.
- Rehashed foreign-builder RED: **1 failed, 1 passed**. GREEN: **2 passed**.
- Local notebook configured-filesystem/current-progress/FileLink RED:
  **2 failed**. GREEN: **2 passed**.
- Bounded publisher history RED: **1 failed**. GREEN with crash-ordering
  adjacency: **2 passed**.
- Broad integration found a genuine verifier regression: **4 failed,
  182 passed** because Colab's independent logical-content verifier omitted the
  new raw schema. After binding it conditionally, candidate and notebook suites
  passed: **186 passed**.

## Final verification

Exact required suite:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -o addopts='' -p no:cacheprovider
719 passed, 14 skipped in 156.60s
```

Adjacent suites:

```text
Task 3/state/publish/quality/tokens/telco_prepare/sample/shards: 172 passed
Candidate plus local and Colab notebooks: 186 passed
```

Static and artifact checks:

- `git diff --check`: clean.
- Six changed Python modules compiled in memory.
- All three notebook files parsed as JSON; 31 Python code cells parsed as AST.
  Two unchanged explicit IPython magic lines (`%pip`, `!nvidia-smi`) were
  intentionally excluded from plain-Python AST parsing.

## Self-review and residual risk

All parked Critical/Important and named closure items in the two ledgers are
addressed. Content identity remains free of machine paths; operational identity
continues to bind canonical evidence and destination namespaces. Legacy reads
remain supported where required, while new producer output is portable.

The only accepted residual is syscall-granularity replacement of a validated
ancestor after the check and before a later path operation. Eliminating that
race requires a broader dirfd/openat redesign. It is documented, unchanged,
and outside this bounded remediation.
