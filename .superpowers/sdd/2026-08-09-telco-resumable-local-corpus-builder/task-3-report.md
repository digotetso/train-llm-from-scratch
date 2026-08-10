# Task 3 report — resumable exact local corpus builder

## Handoff and commit

This task started from an incomplete, uncommitted handoff. I retained its
additive `units.state_json` migration after inspection, replaced the placeholder
corpus test with deterministic end-to-end coverage, and completed the builder.

- `1b95e15 feat: build resumable exact telco corpus`

## Changed files

- `matgpt/data/local_corpus.py`: strict approved-tokenizer validation, exact
  batch tokenization, journal-backed global deduplication, quota processing,
  deterministic window resume, raw/token unit sealing and publication, retry,
  calibration/clean-stop status, capacity preflight, and atomic progress output.
- `matgpt/data/local_state.py`: additive `UnitCommit.state` persistence and
  SQLite migration for per-unit resume state.
- `tests/test_local_corpus.py`: deterministic source fixture plus one-pass,
  dedup, resume, calibration, retry, source/schema/license, strict selection,
  progress, clean-stop, stale-partial, and storage tests.

## TDD evidence

Initial end-to-end RED:

```text
$ uv run --extra test pytest tests/test_local_corpus.py -q
FFFFF.
FAILED test_builder_counts_once_and_deduplicates_across_stages
FAILED test_forced_interruption_resumes_byte_identically
FAILED test_calibration_stop_resumes_same_identity
FAILED test_transient_loader_failure_retries_from_committed_cursor
FAILED test_unknown_telco_collection_and_missing_license_fail_without_manifest
ValueError: Source 'common_pile_github_archive' exhausted before quota
```

The failure exposed the inherited implementation's invalid behavior of dropping
a whole document when it overshot the remaining quota.

Progress evidence RED:

```text
$ uv run --extra test pytest tests/test_local_corpus.py -q
........F
FAILED test_builder_writes_atomic_progress_evidence
FileNotFoundError: .../local/progress.json
```

Storage-boundary RED:

```text
$ uv run --extra test pytest tests/test_local_corpus.py -q
...........F
FAILED test_builder_checks_storage_before_sealing_a_unit
Failed: DID NOT RAISE StoragePressure
```

GREEN evidence:

```text
$ uv run --extra test pytest tests/test_local_corpus.py tests/test_local_build_state.py tests/test_data_quality.py -q
.........................                                                [100%]

$ uv run --extra test pytest tests/test_local_corpus.py::test_forced_interruption_resumes_byte_identically -vv -s
PASSED
============================== 1 passed in 14.68s ==============================

$ uv run --extra test pytest tests/test_local_corpus.py::test_builder_checks_storage_before_sealing_a_unit -vv -s
PASSED
============================== 1 passed in 0.47s ===============================

$ uv run --extra test pytest tests/test_local_build_state.py tests/test_data_quality.py tests/test_local_tokens.py tests/test_local_publish.py tests/test_local_tokenizer_sample.py tests/test_telco_prepare.py -q
........................................................................ [ 97%]
..                                                                       [100%]
```

`uv run --extra test python -m compileall -q matgpt`, `git diff --check`, and
`git show --check --stat --oneline 1b95e15` exited with status 0.

## Self-review

- Selection is rejected before state creation unless it uses the canonical
  filename, complete v1 approval schema, an approved known winner, a valid
  comparison hash, an operator provenance field, and the exact current tokenizer
  SHA plus tokenizer metadata SHA.
- Only quality-accepted, planned, under-quota documents enter `encode_batch`;
  the configured batch ceiling is enforced. Quota IDs are counted before EOS,
  while a final accepted document may overshoot an item quota.
- Global exact dedup comes from the persisted journal and a window-local pending
  set, so no complete-corpus hash set is materialized in memory. Journal cursors
  are committed after a complete deterministic source window and artifacts are
  published before callbacks/calibration returns.
- Unknown collections, empty document-level licenses, source exhaustion,
  selection failures, and capacity pressure fail before a complete manifest.
  Retry is limited to `TimeoutError` and `ConnectionError`.
- Startup removes only managed uncommitted `.partial` files after identity
  validation. Progress and manifest finalization are atomic, fsynced writes.

## Residual concerns

- The tests use a local filesystem and synthetic streams only; the existing
  publisher preflight remains required for a real Drive mount.
- No real corpus data was read and no training/evaluation job was started.

## Fix Round 1

### Commit

- `20a79dd fix: harden provisional corpus build safety`

### RED evidence

```text
$ uv run --extra test pytest tests/test_local_corpus.py -k 'matching_sibling or only_first_encoded or counts_once' -q
FFF
FAILED test_builder_counts_once_and_deduplicates_across_stages
AssertionError: 'complete' != 'provisional_complete'
FAILED test_builder_rejects_selection_without_matching_sibling_comparison
Failed: DID NOT RAISE ValueError
FAILED test_only_first_encoded_document_that_reaches_item_quota_is_committed
assert 3 == 1

$ uv run --extra test pytest tests/test_local_corpus.py::test_builder_requires_enabled_dedup_and_contamination_controls -q
Failed: DID NOT RAISE ValueError

$ uv run --extra test pytest tests/test_local_corpus.py::test_startup_removes_uncommitted_sealed_artifacts_before_resume -q
FAILED ...
assert not orphan.exists()

$ uv run --extra test pytest tests/test_local_corpus.py::test_raw_records_preserve_upstream_source_split -q
KeyError: 'source_split'
```

### GREEN evidence

```text
$ uv run --extra test pytest tests/test_local_corpus.py -k 'matching_sibling or only_first_encoded or counts_once' -q
...                                                                      [100%]

$ uv run --extra test pytest tests/test_local_corpus.py::test_builder_requires_enabled_dedup_and_contamination_controls -q
.                                                                        [100%]

$ uv run --extra test pytest tests/test_local_corpus.py::test_sigint_request_stops_cleanly_at_a_committed_window_boundary -q
.                                                                        [100%]

$ uv run --extra test pytest tests/test_local_corpus.py::test_startup_removes_uncommitted_sealed_artifacts_before_resume -q
.                                                                        [100%]

$ uv run --extra test pytest tests/test_local_corpus.py::test_raw_records_preserve_upstream_source_split -q
.                                                                        [100%]
```

`python -m compileall -q matgpt`, `git diff --check`, and `git show --check`
for `20a79dd` exited with status 0.

### Fix review

- Consumption now invokes a shared, authoritative tokenizer-selection validator
  against a canonical sibling comparison report. The selection and comparison
  file hashes are part of the journal build identity, so changing either
  evidence file refuses a resume.
- Task 3 returns only `provisional_complete`; its evidence is `complete=false`
  and it no longer writes a destination `manifest.json`. Task 4 remains the
  only owner of final audit and eligibility publication.
- A second quota check occurs while consuming encoded results. The first
  document that reaches/crosses quota is kept; later same-item encodings are
  discarded without accepted hashes or output. Source consumption breaks after
  a completed source boundary.
- Mandatory quality controls now require enabled filtering, exact deduplication,
  and non-empty contamination evidence. The policy fingerprint remains in the
  journal identity.
- Startup journal reconciliation removes only unreferenced files under managed
  unit directories, including sealed pre-commit artifacts and partials; journal
  referenced artifacts are preserved. Corpus records retain the original
  upstream split in `source_split` before assigning corpus `fit`/`holdout`.
- SIGINT handling is now scoped in a context manager and restores the prior
  handler on both success and failure.

### Fix Round 1 continuation

Commit: `9120d89 fix: persist corpus unit recovery evidence`

#### RED evidence

```text
$ uv run pytest tests/test_local_corpus.py::test_unit_commit_persists_cumulative_evidence_and_progress_schema -q
FAILED ... KeyError: 'cumulative'
```

#### GREEN evidence

```text
$ uv run pytest tests/test_local_corpus.py tests/test_local_build_state.py tests/test_local_publish.py tests/test_data_quality.py tests/test_local_tokens.py tests/test_telco_prepare.py tests/test_local_tokenizer_sample.py -q
........................................................................ [ 75%]
........................                                                 [100%]
96 passed

$ python3 -m compileall -q matgpt && git diff --check
exit 0
```

#### Continuation review

- Each committed corpus unit now includes a JSON-atomic cumulative state:
  read/accepted/holdout/rejection and quality reports, license counters,
  validation digest, fit counts, item quotas, source cursors, packed byte and
  shard counts, plus last-document/unit evidence. Resume restores this state
  and the quality counters from the journal rather than an in-memory corpus set.
- Pending fit/holdout records and token hashes accumulate across deterministic
  windows, then seal only at a bounded completed-window threshold, item quota,
  calibration, or clean-stop boundary. Capacity reserves raw/token output plus
  conservative journal overhead.
- Retry now covers exceptions raised while iterating a stream. It reopens at
  the exact consumed raw offset and accepts only timeout, connection, HTTP 408,
  HTTP 429, and HTTP 5xx failures.
- Progress is atomic and directory-fsynced, interval-aware for running updates,
  and includes quotas, quality categories, throughput placeholders, RSS,
  storage, Drive/journal status, and last-unit evidence. Task 3 remains
  provisional-only and verifies every unit is published before returning.
- Fresh-process crash tests cover after-seal/pre-commit, post-commit/pre-
  publish, and after-mark/release boundaries. Destination mappings are journaled
  before the first publish copy; restart reconciliation retains referenced work
  and completes byte-identically. A spawned subprocess delivers SIGINT after a
  committed window and proves both clean stop and previous-handler restoration.

## Fix Round 2 (increment 1)

### RED / GREEN

The prior corpus build accepted the legacy sibling name
`tokenizer_comparison.json` and added destination mappings after unit commit;
the new `test_evidence_root_and_atomic_destination_mapping_are_canonical`
would fail those behaviors.  It is green with:

```text
$ uv run pytest tests/test_local_corpus.py tests/test_local_build_state.py tests/test_local_publish.py tests/test_data_quality.py tests/test_local_tokens.py tests/test_telco_prepare.py tests/test_local_tokenizer_sample.py -q
........................................................................ [ 74%]
.........................                                                [100%]
97 passed

$ python3 -m compileall -q matgpt && git diff --check
exit 0
```

### Implemented in this increment

- Explicit `evidence_root` enforces canonical `tokenizer_selection.json` and
  sibling `comparison.json`, selected tokenizer containment, and corpus
  destination containment; selection/comparison hashes remain build-identity
  inputs.
- Corpus `UnitCommit` artifact metadata includes the deterministic destination
  path and `BuildJournal.commit_unit` records it within its atomic transaction.
  Legacy generic journal callers retain their intentionally unmapped behavior.
- Removed the cross-stage `discarded_after_quota` cache. Only committed accepted
  and current pending hashes suppress later work, so unaccepted quota-discarded
  docs may be considered by a subsequent stage.

### Fix Round 2 increment 2

Commit: `b3ee85c fix: seal corpus units at item quota boundaries`.

`uv run pytest tests/test_local_corpus.py -q` completed with `23 passed`.
Pending raw/token accounting is now incremental at window boundaries and a
unit seals at the first completed window where any planned item newly reaches
its quota. Raw input cursor accounting is separated from normalized records.

## Fix Round 2 final continuation

Implementation commit: `9e71b77 fix: complete truthful corpus recovery evidence`.

### RED evidence

The focused test run was executed before the cumulative/progress implementation:

```text
$ uv run pytest -q tests/test_local_build_state.py::test_artifactless_unit_is_durably_published tests/test_local_corpus.py::test_atomic_unit_state_contains_truthful_streaming_cumulative_evidence tests/test_local_corpus.py::test_interval_progress_reports_truthful_unsealed_window_state tests/test_local_corpus.py::test_two_stage_calibration_resume_matches_uninterrupted_content_and_bytes
.FF.                                                                     [100%]
FAILED test_atomic_unit_state_contains_truthful_streaming_cumulative_evidence
KeyError: 'raw'
FAILED test_interval_progress_reports_truthful_unsealed_window_state
TypeError: build_local_corpus() got an unexpected keyword argument 'monotonic_clock'
```

The artifactless journal/reconcile test and the inherited two-stage calibration
byte-equivalence test were already green, confirming that the handed-off atomic
publication change and earlier discard-cache removal were intact.

### GREEN evidence

```text
$ uv run pytest -o addopts='' -q tests/test_local_corpus.py tests/test_local_build_state.py tests/test_local_publish.py tests/test_data_quality.py tests/test_local_tokens.py tests/test_telco_prepare.py tests/test_local_tokenizer_sample.py tests/test_telco_notebook_local.py tests/test_tokenizer_candidate.py
........................................................................ [ 39%]
........................................................................ [ 78%]
........................................                                 [100%]
184 passed in 18.10s

$ uv run python -m compileall -q matgpt tests
exit 0

$ git diff --check
exit 0
```

### Implemented behavior

- Artifactless units are marked published in the same SQLite transaction as
  their counters, hashes, cursor, and state. Reopen, exact-identity validation,
  fresh publisher reconciliation, and provisional publication verification all
  accept the durable artifactless checkpoint without inventing an artifact.
- Evidence schema v2 is bound into build identity. Each atomic unit snapshot now
  persists exact canonical raw-row counts/characters/bytes (including empty
  rows), normalized counts/characters/bytes, quality accepted/rejection
  categories, corpus accepted and encoded/unencoded quota-discard evidence,
  fit/validation quota and packed tokens, characters, text bytes, exact JSONL
  bytes, license counts, source cursors, artifact totals, and per-item last
  document token count plus overshoot.
- Validation evidence uses bounded, restartable order-sensitive SHA-256 chains
  for document identity/order and content order. Tests compare restored and
  uninterrupted cumulative evidence and every destination JSONL/bin byte.
- Progress is attempted after every completed deterministic window and gated by
  an injected monotonic clock. Atomic file+directory-fsynced payloads report the
  live stage/source/bucket/item, requested/actual item and stage quotas, all
  rejection categories, pending and last units, elapsed/rolling/overall rate and
  ETA, RSS, active/free/unpublished/published bytes, and publication-backed Drive
  verification. The committed snapshot carries the elapsed/token baseline used
  by a fresh-process resume.
- Calibration remains a stop condition only. A two-stage stop/resume produces
  the same provisional content identity and byte-for-byte destination raw and
  packed artifacts as an uninterrupted build; no process-local quota-discard
  cache participates in selection.

### Seven-finding self-audit

1. Canonical selection/comparison/operator provenance remains validated before
   state creation and bound into identity; evidence schema v2 is now also bound.
2. Destination mappings remain part of the atomic unit artifact transaction;
   publication/reconciliation uses the persisted mapping.
3. Cumulative evidence is exact, bounded, atomic, restorable, and covered by
   clean-versus-resume equality tests, including heldout digest state.
4. Units seal at completed-window item boundaries; per-item actual/requested,
   last-document tokens, overshoot, and encoded/unencoded quota discards are
   explicit, and quota-discarded rows never gain accepted hashes.
5. Interval progress now measures live unsealed windows with a fake monotonic
   clock test and resumes elapsed/token baselines from committed state.
6. Cross-stage quota discards are not cached; the two-stage calibration
   stop/resume regression proves exact provisional identity and artifact bytes.
7. Artifactless checkpoints are atomically published and survive identity-
   checked reopen plus fresh publisher reconciliation.

No real corpus data was read, no Drive provider was mutated, and no training or
evaluation process was started. A real mounted destination still requires the
existing provider preflight before production use.

## Fix Round 3

Implementation commit: `0244539 fix: bind corpus journal operational identity`.

### RED evidence

```text
$ uv run pytest -o addopts='' -q tests/test_local_corpus.py::test_operational_identity_refuses_changed_destination_or_evidence_root_before_reconcile tests/test_local_corpus.py::test_builder_rejects_symlinked_canonical_evidence_file tests/test_local_corpus.py::test_builder_rejects_copied_selection_outside_root_and_symlink_destination tests/test_local_corpus.py::test_resumed_rolling_rate_uses_only_new_process_tokens_and_interval
FFF.F                                                                    [100%]
FAILED test_operational_identity_refuses_changed_destination_or_evidence_root_before_reconcile
AssertionError: identity must fail before destination reconciliation
FAILED test_builder_rejects_symlinked_canonical_evidence_file[tokenizer_selection.json]
Failed: DID NOT RAISE ValueError
FAILED test_builder_rejects_symlinked_canonical_evidence_file[comparison.json]
Failed: DID NOT RAISE ValueError
FAILED test_resumed_rolling_rate_uses_only_new_process_tokens_and_interval
assert 1.3333333333333333 == 4.0 ± 4.0e-06
4 failed, 1 passed
```

### GREEN evidence

```text
$ uv run pytest -o addopts='' -q tests/test_local_corpus.py tests/test_local_build_state.py tests/test_local_publish.py tests/test_data_quality.py tests/test_local_tokens.py tests/test_telco_prepare.py tests/test_local_tokenizer_sample.py tests/test_telco_notebook_local.py tests/test_tokenizer_candidate.py
........................................................................ [ 37%]
........................................................................ [ 75%]
..............................................                           [100%]
190 passed in 20.94s

$ uv run python -m compileall -q matgpt tests
exit 0

$ git diff --check
exit 0
```

### Finding resolution and self-review

1. `evidence_root` is now a mandatory request field. The builder requires the
   root itself, canonical `tokenizer_selection.json`, canonical
   `comparison.json`, selected tokenizer directory, `tokenizer.json`, and
   `special_tokens.json` to be exact managed non-symlink paths. The destination
   is a managed non-symlink descendant. Copied selection paths, symlinked
   canonical evidence, and symlinked destinations fail before journal creation.
   The resolved evidence root and destination-relative namespace are stored in
   `BuildIdentity.operational` and hashed by the journal identity, so a changed
   root or empty alternate destination refuses before publisher reconciliation.
2. `BuildIdentity.content_sha256` excludes operational machine paths, while the
   journal SHA includes them. Corpus results and provisional manifests use the
   content identity; cross-root clean/resume tests therefore retain identical
   content identity and artifact bytes. Generic sample identities with no
   operational payload retain their prior hash/metadata representation.
3. Progress restores committed elapsed and accepted-token baselines but always
   starts a new monotonic process anchor. The first resumed rolling rate divides
   only new tokens by new-process elapsed; overall rate uses total tokens over
   cumulative elapsed, and ETA uses the current rolling rate. The fake-clock
   regression stops with real remaining work, advances both time and tokens,
   and asserts rolling, overall, elapsed, and ETA relationships.

No real data, Drive publication, training, or evaluation was performed.

## Fix Round 4

Implementation commit: `1c98dac fix: reject aliased corpus evidence roots`.

### RED evidence

```text
$ uv run pytest -o addopts='' -q tests/test_local_corpus.py::test_fresh_build_rejects_symlinked_evidence_root_ancestor_before_state_hooks tests/test_local_corpus.py::test_resume_rejects_symlinked_evidence_root_ancestor_before_journal_open
FF                                                                       [100%]
FAILED test_fresh_build_rejects_symlinked_evidence_root_ancestor_before_state_hooks
AssertionError: path preflight must run before evidence/state hooks
FAILED test_resume_rejects_symlinked_evidence_root_ancestor_before_journal_open
AssertionError: resume alias must fail before evidence/state hooks
2 failed
```

Both failures occurred at `Path.read_text`, proving the inherited validation
followed a symlinked root ancestor and read approval evidence before refusing the
path later in the pipeline.

### GREEN evidence

```text
$ uv run pytest -o addopts='' -q tests/test_local_corpus.py tests/test_local_build_state.py tests/test_local_publish.py tests/test_data_quality.py tests/test_local_tokens.py tests/test_telco_prepare.py tests/test_local_tokenizer_sample.py tests/test_telco_notebook_local.py tests/test_tokenizer_candidate.py
........................................................................ [ 37%]
........................................................................ [ 74%]
.................................................                        [100%]
193 passed in 20.56s

$ uv run python -m compileall -q matgpt tests
exit 0

$ git diff --check
exit 0
```

### Finding resolution and self-review

- Before any evidence read, cleanup, journal creation/open, or publisher
  reconciliation, the builder now computes each supplied path's lexical absolute
  form and requires it to equal its non-strict resolved form. This covers the
  evidence root, canonical selection/comparison, selected tokenizer directory
  and required files, destination root, and local journal root. A symlink in any
  ancestor therefore fails closed rather than being canonicalized into an
  equivalent approved path.
- The evidence root must then pass managed-path validation as an existing real
  directory. All evidence/tokenizer files must be real managed files, while the
  destination remains a managed non-symlink descendant that may be created by
  the publisher.
- Fresh-build and resume tests route every request path through a symlinked
  ancestor and replace evidence reads, journal open, cleanup, and reconciliation
  with failure hooks. Both now reject before any hook; the fresh test proves no
  journal is created and the resume test proves the existing journal's size and
  modification time do not change. A separate lexical `..` regression proves
  aliases are rejected rather than normalized into equivalence.
- Round 3's path-independent content identity and path-bound operational journal
  identity are unchanged; their cross-root and resume regressions remain green.

No real data, Drive publication, training, or evaluation was performed.

## Fix Round 5

Implementation commit: `937c181 test: cover corpus path aliases independently`.

### RED evidence

After replacing the aggregate alias setup with independent fresh/resume cases,
the corrected matrix isolated one implementation gap:

```text
$ uv run pytest -o addopts='' -q tests/test_local_corpus.py -k 'each_symlinked_corpus_path or each_lexically_aliased_corpus_path'
................FF..........                                             [100%]
FAILED ...[journal_file-fresh]
AssertionError: path must fail before evidence, journal, or publisher hooks
FAILED ...[journal_file-resume]
AssertionError: path must fail before evidence, journal, or publisher hooks
2 failed, 26 passed, 30 deselected
```

Both failures occurred at the guarded selection evidence read: the derived
`corpus.sqlite3` path was not yet part of the pre-evidence validation set.

### GREEN evidence

```text
$ uv run pytest -o addopts='' -q tests/test_local_corpus.py -k 'each_symlinked_corpus_path or each_lexically_aliased_corpus_path'
............................                                             [100%]
28 passed, 30 deselected

$ uv run pytest -o addopts='' -q tests/test_local_corpus.py tests/test_local_build_state.py tests/test_local_publish.py tests/test_data_quality.py tests/test_local_tokens.py tests/test_telco_prepare.py tests/test_local_tokenizer_sample.py tests/test_telco_notebook_local.py tests/test_tokenizer_candidate.py
........................................................................ [ 33%]
........................................................................ [ 66%]
........................................................................ [ 99%]
..                                                                       [100%]
218 passed in 21.08s

$ uv run python -m compileall -q matgpt tests
exit 0

$ git diff --check
exit 0
```

### Coverage completeness and self-review

- Every case mutates one path only. Fresh and resume variants independently
  exercise a symlinked evidence-root ancestor, selection file, comparison file,
  tokenizer-directory ancestor, tokenizer JSON, special-token metadata,
  destination-root ancestor, local-root ancestor, and journal file.
- Fresh and resume variants independently exercise lexical aliases for every
  supplied path where an alias can be expressed: evidence root, selection,
  tokenizer directory, destination root, and local root. Canonical root-level
  comparison and tokenizer files are derived rather than supplied, so their
  independent final-component symlink cases are the applicable fail-closed
  coverage. The journal path is likewise derived from the independently aliased
  local root.
- Every matrix case replaces evidence reads, journal open, cleanup, publisher
  construction, and reconciliation with failure hooks. Fresh cases prove no
  journal creation; resume cases compare the existing physical journal bytes and
  modification timestamp before and after refusal.
- The exposed gap is closed by validating `corpus.sqlite3` plus its `-wal`,
  `-shm`, and `-journal` sidecars before evidence reads. This is the only
  production change in the round.
- Existing positive canonical-path builds, named direct selection/comparison
  symlink tests, operational identity refusal, root-independent content identity,
  resume/calibration equality, progress, publication, and state tests remain
  green. No path is canonicalized into equivalence.

No real data, Drive publication, training, or evaluation was performed.
