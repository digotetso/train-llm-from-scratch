# Final-review fix report

Date: 2026-08-09

Branch: `codex/telco-tokenizer-local-prep-20260809`

Starting head: `3a3aea5`

Implementation commit: `91817f3` (`fix: bind tokenizer workflow evidence`)

## Outcome

All final-review findings were addressed without starting a real 200M build,
network download, Drive publication, tokenizer migration, or model pretraining.
The final implementation suite passes completely: **487 passed, 14 skipped**.

## Changes by finding

### Critical: current sample provenance was unbound

- Sample manifests produced by this workflow are now version 3 and persist a
  deterministic build-provenance envelope binding the exact 200M target, exact
  role quotas, plan, canonical recipe/config file identities, source registry,
  quality policy, current Lite/Full contamination manifests and config files,
  and output format.
- Candidate, comparison, and selection recompute that envelope from the current
  checked repository configs and canonical work-root contamination evidence.
- Old v2, missing, foreign, self-consistent stale, and otherwise non-current
  manifests fail closed in the new workflow. Direct legacy sample requests that
  do not opt into provenance retain their v2/resume identity, while tokenizer
  consumers for this new workflow require v3.

### Critical: managed descendants could escape through symlinks

- Added a shared managed-path validator that checks every existing descendant
  with `lstat`, rejects symlinks/non-directory ancestors/resolved escapes, and
  uses `O_EXCL | O_NOFOLLOW` for new evidence/chunk files where practical.
- Added preflight coverage for local sample, fit, holdout, state DB and SQLite
  sidecars; candidate namespace and files; canonical pilot recipe/tokenizer and
  evidence; comparison; and selection paths.
- Negative tests prove sample/split/state/candidate/publish/selection symlinks
  fail before writes or deletes can affect the outside target.

### Important: sampler dedup memory growth

- Preserved generic `QualityFilter` exact-dedup behavior by default.
- The resumable local sampler disables only the filter's unbounded seen set and
  relies on SQLite for committed hashes plus a bounded per-window pending set.
- Scaling coverage confirms retained in-memory hashes do not grow with accepted
  document count; existing byte-identical resume tests remain green.

### Important: fingerprints were separate from consumed bytes

- Tokenizer count, train, and score passes now hash/count the raw bytes actually
  consumed, compare every pass, and compare the final consumption to verified
  manifest artifacts before saving tokenizer or report files.
- Evaluation hashes/counts the holdout stream actually scored, compares it with
  manifest-approved artifacts, and binds tokenizer/probe bytes before and after
  their use.
- Deterministic mutation tests cover changes between training passes, after
  manifest verification, and during tokenizer/probe evaluation consumption.
- Candidate publication validates the persisted report against the current
  manifest and actual tokenizer SHA; selection independently revalidates it.

### Important: pilot baseline provenance was unbound

- Comparison requires explicit canonical pilot provenance at
  `recipes/<recipe-id>/evidence/pilot/tokenizer_provenance.json` and the
  canonical preserved tokenizer at
  `recipes/<recipe-id>/prepared/pilot/tokenizer`.
- Evidence binds the pilot stage, canonical recipe SHA/ID, canonical pilot
  sample manifest file/internal SHA, canonical tokenizer location, and actual
  tokenizer SHA. The comparison records this identity.
- Valid canonical and arbitrary/wrong-pilot negative tests were added.
- The runbook documents a fail-closed, operator-reviewed migration evidence
  workflow for older artifacts. No evidence was fabricated in this change.

### Important: selection accepted arbitrary/stale comparison evidence

- Selection accepts only `<drive-root>/comparison.json`.
- It revalidates current labels, sample/build provenance, candidate recipe,
  candidate report/sample binding, baseline provenance, and actual tokenizer
  hashes before exclusive record creation.
- Negative tests cover noncanonical paths, stale recipe, wrong labels, rebound
  stale candidate reports, and tokenizer mutation after comparison.

### Important: failure handling could approve an invalid baseline

- Comparison now tracks shared, baseline-side, and candidate-side fatal gates.
- Shared evidence invalid or both sides invalid yields no recommendation.
- Exactly one independently valid side is recommended; selection refuses an
  invalid selected side even with an explicit override.
- Added baseline-invalid, candidate-invalid, both-invalid, and shared-evidence
  regression tests.

### Minor: unused storage limits

- The candidate config now declares `local.enforcement: advisory` and validates
  it both through YAML loading and direct config construction.
- Every CLI invocation emits a `storage_advisory` event containing both limits
  and `enforced: false`; the notebook and runbook state the operator obligation.

## TDD evidence

### Clean baseline

Command:

```text
uv run --extra test pytest -o addopts= -q
```

Output before fixes:

```text
453 passed, 14 skipped in 30.13s
```

### First RED: sample provenance, managed paths, bounded dedup, consumed bytes

Command:

```text
uv run --extra test pytest -o addopts= -q tests/test_local_tokenizer_sample.py tests/test_data_quality.py tests/test_tokenizer.py tests/test_tokenizer_candidate.py -k 'persists_the_supplied_build_provenance or does_not_retain_every_accepted_hash or symlinked_managed_descendants or generic_quality_filter_keeps or missing_build_provenance or mutation_between_consumption_passes or mutation_after_manifest_verification or unbound_or_foreign_sample_provenance or symlinked_candidate_publish'
```

RED output:

```text
11 failed, 1 passed, 80 deselected in 2.74s
```

Focused GREEN output after implementation:

```text
12 passed, 80 deselected in 2.60s
```

Adjacent output:

```text
101 passed in 5.71s
```

### Second RED: side gates and pilot provenance

Command:

```text
uv run --extra test pytest -o addopts= -q tests/test_tokenizer_candidate.py -k 'recommends_candidate_when_only_baseline or recommends_baseline_when_only_candidate or recommends_no_winner_when_both or recommends_no_winner_when_shared or refuses_invalid_baseline or binds_the_canonical_pilot or rejects_an_arbitrary_tokenizer'
```

RED output:

```text
7 failed, 57 deselected in 0.55s
```

Focused GREEN output:

```text
7 passed, 58 deselected in 0.78s
```

### Additional self-review RED/GREEN cycles

Actual tokenizer/probe consumption identity:

```text
uv run --extra test pytest -o addopts= -q tests/test_tokenizer.py -k 'tokenizer_or_probe_mutation_during_consumption'
RED:   2 failed, 20 deselected in 0.70s
GREEN: 2 passed, 20 deselected in 0.56s
```

Direct advisory validation and explicit pilot evidence:

```text
uv run --extra test pytest -o addopts= -q tests/test_tokenizer_candidate.py -k 'direct_construction_rejects_non_advisory or requires_explicit_pilot_provenance'
RED:   2 failed, 74 deselected in 0.39s
GREEN: 2 passed, 74 deselected in 0.14s
```

Selection rebound to a stale candidate report:

```text
uv run --extra test pytest -o addopts= -q tests/test_tokenizer_candidate.py -k 'rebound_stale_candidate_report'
RED:   1 failed, 76 deselected in 0.25s
GREEN: 1 passed, 76 deselected in 0.31s
```

## Final verification

Focused workflow suite:

```text
python3 -m json.tool notebooks/prepare_matgpt_telco_300m_local.ipynb >/dev/null
uv run --extra test pytest -o addopts= -q tests/test_local_build_state.py tests/test_local_tokenizer_sample.py tests/test_data_quality.py tests/test_tokenizer.py tests/test_tokenizer_candidate.py tests/test_telco_notebook_local.py

128 passed in 5.72s
```

Mandatory complete suite at the final implementation tree:

```text
uv run --extra test pytest -o addopts= -q --junitxml=/private/tmp/telco-tokenizer-final.xml

487 passed, 14 skipped in 27.76s
```

Static/artifact checks:

```text
git diff --check
python3 -m json.tool notebooks/prepare_matgpt_telco_300m_local.ipynb >/dev/null
python3 -m py_compile matgpt/utils/paths.py matgpt/data/quality.py matgpt/data/local_state.py matgpt/data/local_sample.py matgpt/tokenizer/train.py matgpt/tokenizer/candidate.py scripts/prepare_telco_local.py tests/test_data_quality.py tests/test_local_tokenizer_sample.py tests/test_tokenizer.py tests/test_tokenizer_candidate.py tests/test_telco_notebook_local.py

All completed with exit code 0 and no output.
```

## Self-review

- Correctness: inspected the complete diff and traced sample creation through
  candidate, comparison, and selection. Each downstream claim is now checked
  against current canonical evidence, not merely against another supplied
  self-consistent claim.
- Security: checked every managed mutation/read boundary for descendant
  symlinks and lexical/resolved escapes; exclusive no-follow creation is used
  for new managed files. Tests verify outside targets are preserved.
- Performance: the 200M data path remains streaming; exact long-lived dedup is
  SQLite-backed, while the only in-memory exact tracker is bounded by a source
  window. Consumption audits retain one small record per chunk, not per
  document.
- Compatibility: generic `QualityFilter` behavior is unchanged; legacy sample
  requests can retain v2 resume identity. The new canonical tokenizer workflow
  intentionally rejects old/unbound manifests and older comparison records.
- Operations/docs: notebook commands, runbook migration instructions, storage
  advisory semantics, and fail-closed operator behavior were updated.

## Residual concerns and deferred items

- Filesystem validation is fail-closed and uses no-follow/exclusive primitives
  where the existing architecture permits. As with ordinary path-based APIs,
  an adversary able to race directory replacement at syscall granularity would
  require a larger dirfd/openat redesign; no such redesign was introduced in
  this bounded fix wave.
- Existing pilot artifacts must be reviewed by an operator and supplied with
  the documented canonical evidence file. The workflow correctly remains
  blocked until that evidence exists.
- The intentionally deferred notebook clickable `FileLink` and notebook
  `Path.home()`/default-path mismatch remain ledgered for the pre-operator-run
  pass and were not expanded here.
