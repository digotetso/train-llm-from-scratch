# Exact Telco Token Quotas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Telco corpus preparation satisfy the checked mixture quotas using the frozen project tokenizer before quota audit and sharding.

**Architecture:** Keep the first 20M pilot build as a bounded bootstrap sample for tokenizer fitting, then freeze that tokenizer and atomically rebuild the pilot with exact tokenizer-ID counts. Record the counting method and tokenizer fingerprint in the corpus manifest. Reuse the same frozen pilot tokenizer when building the 12B full corpus so full preparation needs one source pass instead of an estimated pass followed by a second 12B pass.

**Tech Stack:** Python 3.10+, Hugging Face `tokenizers`, streamed Hugging Face datasets, JSONL, pytest, Jupyter notebook JSON, Google Colab/Drive.

## Global Constraints

- Keep `origin/main` canonical and perform all changes on a fresh `codex/` branch.
- Preserve deterministic source order, validation splitting, exact deduplication, contamination filtering, staging promotion, and recoverable `--force` backups.
- Count document tokens without EOS, matching `audit_token_quotas`; sharding remains responsible for EOS insertion.
- Never include evaluation, post-training, or RAG-only sources in base pretraining.
- Do not contact Hugging Face or download the 20M/12B corpora in local tests.
- The notebook must never start training from `prepare_data` or `prepare`.

---

### Task 1: Exact tokenizer quota collection

**Files:**
- Modify: `matgpt/data/telco_prepare.py`
- Modify: `scripts/prepare_telco_corpus.py`
- Test: `tests/test_telco_prepare.py`

**Interfaces:**
- Consumes: a tokenizer directory containing `tokenizer.json` and `special_tokens.json`.
- Produces: `prepare_telco_corpora(..., tokenizer_dir: str | Path | None = None)` and `corpus_has_exact_token_quotas(corpus_dir, tokenizer_dir, plans) -> bool`.

- [ ] **Step 1: Write a failing exact-selection test**

```python
def test_builder_uses_frozen_tokenizer_counts_to_reach_quotas(...):
    manifest = prepare_telco_corpora(..., tokenizer_dir=tokenizer_dir)
    report = audit_token_quotas([...], tokenizer_dir, [plan], tolerance=0.0)
    assert report["passed"] is True
    assert manifest["quota_counting"] == {
        "method": "tokenizer_exact",
        "tokenizer_sha256": tokenizer_sha256,
    }
```

Use a real small tokenizer artifact and fixture rows whose character estimates under-count tokenizer IDs. The test catches reverting the stop condition to `estimated_tokens`.

- [ ] **Step 2: Run the focused test and confirm the API is missing**

Run: `uv run pytest tests/test_telco_prepare.py -k frozen_tokenizer -v`

Expected: FAIL because `prepare_telco_corpora` does not accept `tokenizer_dir`.

- [ ] **Step 3: Implement exact quota counting and manifest provenance**

```python
def prepare_telco_corpora(..., tokenizer_dir: str | Path | None = None) -> dict[str, Any]:
    quota_token_counter, quota_counting = _quota_counter(tokenizer_dir)
    # _write_stage increments quota_tokens with len(tokenizer.encode(text).ids)
    # when frozen, otherwise with the existing source estimate.
```

Validate the tokenizer file against `special_tokens.json`, expose both `estimated_tokens` and `quota_tokens`, and use `quota_tokens` for completion/exhaustion checks.

- [ ] **Step 4: Add and test the corpus/tokenizer compatibility gate**

```python
assert corpus_has_exact_token_quotas(output, tokenizer_dir, [plan]) is True
assert corpus_has_exact_token_quotas(output, other_tokenizer_dir, [plan]) is False
```

The helper must verify `complete`, `tokenizer_exact`, actual tokenizer SHA, exact stage set, and each stage plan hash.

- [ ] **Step 5: Expose exact mode through the CLI**

```python
parser.add_argument(
    "--tokenizer-dir",
    help="Frozen tokenizer used for exact quota collection.",
)
```

Pass the value unchanged to `prepare_telco_corpora` and preserve the default estimate-based bootstrap mode.

- [ ] **Step 6: Verify focused data tests**

Run: `uv run pytest tests/test_telco_prepare.py -v`

Expected: PASS, including legacy estimate-mode, atomic replacement, contamination, validation, exact selection, and exact audit tests.

### Task 2: Retry-safe pilot bootstrap and one-pass full preparation

**Files:**
- Modify: `notebooks/train_matgpt_telco_300m_colab.ipynb`
- Modify: `tests/test_telco_notebook_colab.py`

**Interfaces:**
- Consumes: `prepared/pilot/tokenizer`, provisional `corpora/pilot`, exact plan JSON, and isolated benchmark JSONL.
- Produces: an exact pilot corpus bound to the frozen tokenizer; a full corpus built with that same tokenizer; unchanged stage gates for sharding and training.

- [ ] **Step 1: Write failing notebook contract tests**

```python
def test_prepare_freezes_tokenizer_then_rebuilds_exact_pilot_before_audit():
    source = _code_after_heading("## 8. Prepare tokenizer and shards")
    assert source.index("atomic_snapshot(TOKENIZER_DIR") < source.index("corpus_has_exact_token_quotas")
    assert source.index("--tokenizer-dir") < source.index("scripts/audit_telco_corpus.py")

def test_full_data_uses_frozen_pilot_tokenizer():
    source = _code_after_heading("## 7. Prepare isolated evaluation and training data")
    assert "PILOT_TOKENIZER_DRIVE_DIR" in source
    assert "--tokenizer-dir" in source
```

These tests catch a retry retraining the tokenizer from a changed corpus and a wasteful estimate-first 12B build.

- [ ] **Step 2: Run notebook tests and confirm the missing workflow**

Run: `uv run pytest tests/test_telco_notebook_colab.py -v`

Expected: FAIL because neither exact rebuild nor pilot-tokenizer reuse exists.

- [ ] **Step 3: Implement the pilot bootstrap flow**

```python
if frozen pilot tokenizer exists:
    restore and validate it
elif local tokenizer is valid:
    snapshot it immediately
else:
    train once, validate, and snapshot immediately

if not corpus_has_exact_token_quotas(CORPUS_DIR, TOKENIZER_DIR, plans):
    rerun prepare_telco_corpus.py with --tokenizer-dir TOKENIZER_DIR --force
```

Only audit and shard after the exact manifest matches both tokenizer SHA and plan hashes. Keep the previous provisional corpus as the builder's timestamped backup.

- [ ] **Step 4: Implement one-pass full preparation**

Require `prepared/pilot/tokenizer` before full data preparation and pass it to `prepare_telco_corpus.py --tokenizer-dir`. Restore that tokenizer locally during full `prepare`; do not train a second vocabulary.

- [ ] **Step 5: Validate notebook JSON, syntax, and stage tests**

Run: `uv run pytest tests/test_telco_notebook_colab.py tests/test_notebook_colab.py -v`

Expected: PASS; `prepare` still orders exact rebalance/audit before sharding and contains no pretraining invocation.

### Task 3: Operator documentation and release verification

**Files:**
- Modify: `docs/runbooks/colab-telco-300m.md`
- Modify: `README.md`
- Test: existing full pytest suite

**Interfaces:**
- Consumes: the exact-quota manifest and notebook behavior from Tasks 1–2.
- Produces: a retry procedure for the user's current failed `prepare` run and accurate pilot/full tokenizer provenance guidance.

- [ ] **Step 1: Document the two-pass pilot and frozen full tokenizer**

State that the first pilot corpus is only a tokenizer bootstrap sample, `prepare` freezes/snapshots the tokenizer, rebuilds pilot quotas exactly, and then audits/shards. State that full preparation requires and reuses that tokenizer, while config and corpus fingerprints still prevent resuming pilot weights into full training.

- [ ] **Step 2: Document recovery from the observed quota failure**

Tell operators to pull the merged fix, keep the existing Drive corpus and tokenizer artifacts, select `RUN_STAGE="prepare"`, and rerun all cells. The notebook should reuse a valid frozen/local tokenizer and atomically replace the provisional corpus.

- [ ] **Step 3: Run focused and complete verification**

Run:

```bash
uv run pytest tests/test_telco_prepare.py tests/test_telco_notebook_colab.py tests/test_notebook_colab.py -v
uv run pytest -q
```

Expected: all tests pass with no Hugging Face or GPU access.

- [ ] **Step 4: Review the complete diff**

Run: `git diff --check && git diff --stat origin/main...HEAD && git diff origin/main...HEAD`

Confirm no training command was added to preparation, no evaluation source can enter training, no user files were touched, and exact mode remains bounded and deterministic.
