# MatGPT Telco 300M Training Track Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible, role-safe public-data pipeline, exact 306M model configuration, staged high-memory-GPU notebook, and Open Telco evaluation adapter for training an English telecom/networking model from scratch.

**Architecture:** A checked-in source registry is the trust boundary: only `pretrain_*` sources can enter deterministic mixture plans and streamed JSONL preparation. Preparation produces provenance-rich stage files and manifests consumed by the existing tokenizer, sharding, training, and evaluation code; narrow optional extensions add tokenizer fertility reporting and staged train-split selection without changing the 8M/59M defaults.

**Tech Stack:** Python 3.10+, PyYAML, Hugging Face `datasets` streaming, Hugging Face `tokenizers`, PyTorch, pytest, JSONL, Jupyter notebook JSON, Google Colab.

## Global Constraints

- Preserve all existing 8M and 59M behavior and artifact formats unless the Telco 300M config opts into an additive extension.
- The exact model fields are vocabulary `32768`, context `2048`, layers `20`, heads `16`, hidden size `1024`, feed-forward size `3072`, SwiGLU, RMSNorm, RoPE, tied embeddings, no linear bias, and dropout `0.0`.
- The checked model must instantiate as exactly `306,226,176` trainable parameters.
- The full token plan is main `10,000,000,000` plus cooldown `2,000,000,000`; the aggregate is general `7,700,000,000`, telecom `3,700,000,000`, structured `600,000,000`.
- Telecom weights are 35% 3GPP preparatory, 30% RFC material, 25% open-access research, 8% patents, and 2% semantic material.
- Only `pretrain_general`, `pretrain_telecom`, and `pretrain_structured` may enter tokenizer fitting or base pretraining.
- `posttrain`, `rag_only`, `GSMA/ot-lite`, and `GSMA/ot-full` must fail closed at the training-plan boundary.
- Serious source definitions require an immutable 40-character revision and non-empty license declaration.
- Public-data preparation must use `streaming=True`, bounded buffers, a deterministic seed, staging output, exact deduplication, contamination phrase checks, and fail-closed quota validation.
- The repository will not run the full 12B-token job or download full upstream datasets during local verification.
- The new notebook defaults to `RUN_STAGE = "prepare_data"`; `full` is never selected or promoted automatically.
- The user's private Drive corpus, unpublished OTel 2.0 processed mixture, live network access, and automatic teacher endpoints remain out of scope.

---

## File map

- `configs/data/telco_300m_sources.yaml`: immutable public source identities, roles, field mappings, collection buckets, license status, and benchmark exclusions.
- `configs/data/telco_300m_mixture.yaml`: pilot/main/cooldown budgets, role weights, telecom bucket weights, quota tolerance, and deterministic buffer size.
- `configs/data/telco_tokenizer_probes.yaml`: fixed general-English and telecom fertility probes.
- `configs/matgpt_telco_300m.yaml`: model, tokenizer, shards, staged training splits, and evaluation prompts.
- `matgpt/data/sources.py`: source-registry dataclasses and trust-boundary validation.
- `matgpt/data/mixture.py`: exact integer quota allocation and plan materialization.
- `matgpt/data/telco_prepare.py`: source-row normalization, deterministic buffered ordering, streamed quota collection, staged promotion, manifests, and post-tokenizer quota audit.
- `scripts/plan_telco_mixture.py`: print/write a validated machine-readable mixture plan.
- `scripts/prepare_telco_corpus.py`: build a pilot or approved full stage from streaming sources.
- `matgpt/tokenizer/fertility.py`: fixed-probe round-trip and fertility calculations.
- `matgpt/training/pretrain.py`: optional phase-to-split selection keyed by processed tokens.
- `matgpt/data/shard.py`: opt-in tokenization of named Telco stage splits.
- `matgpt/eval/open_telco.py`: transform supported Open Telco rows to local evaluation JSONL.
- `scripts/prepare_open_telco_evals.py`: stream pinned evaluation configs without touching training manifests.
- `notebooks/train_matgpt_telco_300m_colab.ipynb`: dedicated, stage-gated RTX PRO 6000/A100 workflow.
- `docs/runbooks/colab-telco-300m.md`: data rights, Drive layout, stage gates, evidence, resume, and rollback procedure.

---

### Task 1: Source registry and role boundary

**Files:**
- Create: `configs/data/telco_300m_sources.yaml`
- Create: `matgpt/data/sources.py`
- Create: `tests/test_telco_sources.py`

**Interfaces:**
- Produces: `SourceSpec`, `SourceBucket`, `SourceRegistry`, `load_source_registry(path: str | Path, *, serious: bool = True) -> SourceRegistry`, and `select_pretraining_sources(registry: SourceRegistry, source_ids: Iterable[str]) -> tuple[SourceSpec, ...]`.
- `SourceSpec` exposes `id`, `hf_name`, `hf_config`, `split`, `revision`, `role`, `license`, `license_review`, `text_field`, `document_id_field`, `collection_field`, `token_count_field`, `data_files`, and `buckets`.
- `SourceBucket` exposes `id`, `collections`, and `weight`.

- [ ] **Step 1: Write failing registry tests**

```python
def test_registry_pins_training_and_eval_sources():
    registry = load_source_registry("configs/data/telco_300m_sources.yaml")
    assert registry.by_id["common_pile_general"].revision == "5afc546db324e7f39f297ba757c9a60547151e7c"
    assert registry.by_id["telco_common_corpus"].revision == "c590e4e6224d2cd50cc9403537cff7656d1535ea"
    assert registry.by_id["open_telco_lite"].role == "evaluation_only"
    assert registry.by_id["open_telco_full"].role == "evaluation_only"

def test_training_boundary_rejects_eval_posttrain_and_rag_roles():
    registry = load_source_registry("configs/data/telco_300m_sources.yaml")
    for source_id in ("open_telco_lite", "otel_llm", "gsma_3gpp_mirror"):
        with pytest.raises(ValueError, match="not permitted for pretraining"):
            select_pretraining_sources(registry, [source_id])

def test_serious_registry_requires_revision_and_license(tmp_path):
    path = tmp_path / "sources.yaml"
    path.write_text("version: 1\nsources:\n  - id: bad\n    hf_name: x/y\n    split: train\n    role: pretrain_general\n", encoding="utf-8")
    with pytest.raises(ValueError, match="revision"):
        load_source_registry(path)
```

- [ ] **Step 2: Run the tests and confirm the missing-module failure**

Run: `uv run pytest tests/test_telco_sources.py -v`

Expected: FAIL because `matgpt.data.sources` does not exist.

- [ ] **Step 3: Implement immutable dataclasses and strict validation**

Implement the role constants and YAML parser in `matgpt/data/sources.py`. Reject duplicate IDs, unknown keys, unknown roles, missing licenses, invalid revisions in serious mode, empty text fields, negative bucket weights, duplicate bucket IDs, and bucket definitions without a collection field. Normalize `data_files` and bucket collections to tuples.

The checked registry must contain these pinned sources:

```yaml
version: 1
sources:
  - id: common_pile_general
    hf_name: common-pile/comma_v0.1_training_dataset
    revision: 5afc546db324e7f39f297ba757c9a60547151e7c
    role: pretrain_general
  - id: telco_common_corpus
    hf_name: GSMA/Telco-Common-Corpus
    revision: c590e4e6224d2cd50cc9403537cff7656d1535ea
    role: pretrain_telecom
  - id: common_pile_structured
    hf_name: common-pile/comma_v0.1_training_dataset
    revision: 5afc546db324e7f39f297ba757c9a60547151e7c
    role: pretrain_structured
  - id: open_telco_lite
    hf_name: GSMA/ot-lite
    revision: 1c0f2eac3ad0baa29704b147a95fea283b2906c7
    role: evaluation_only
  - id: open_telco_full
    hf_name: GSMA/ot-full
    revision: 6319806f04783eafe04d9facf755d379c66b7664
    role: evaluation_only
```

Also register pinned `HuggingFaceTB/smol-smoltalk`, `farbodtavakkoli/OTel-LLM`, and `farbodtavakkoli/OTel-Safety` as `posttrain`, and GSMA standards mirrors as `rag_only`. Mark mixed-license sources `license_review: required`; the code must preserve this fact rather than treating registry inclusion as legal clearance.

- [ ] **Step 4: Run registry tests**

Run: `uv run pytest tests/test_telco_sources.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the registry boundary**

```bash
git add configs/data/telco_300m_sources.yaml matgpt/data/sources.py tests/test_telco_sources.py
git commit -m "feat: add role-safe telco source registry"
```

---

### Task 2: Exact deterministic mixture plans

**Files:**
- Create: `configs/data/telco_300m_mixture.yaml`
- Create: `matgpt/data/mixture.py`
- Create: `scripts/plan_telco_mixture.py`
- Create: `tests/test_telco_mixture.py`

**Interfaces:**
- Consumes: `load_source_registry` and source/bucket IDs from Task 1.
- Produces: `allocate_integer_quotas(total: int, weights: Mapping[str, float]) -> dict[str, int]`, `build_mixture_plan(registry: SourceRegistry, mixture: Mapping[str, Any], stage: str, *, total_tokens: int | None = None) -> dict[str, Any]`, and `load_mixture_config(path: str | Path) -> dict[str, Any]`.

- [ ] **Step 1: Write failing arithmetic and exclusion tests**

```python
def test_hamilton_allocation_preserves_total_and_is_stable():
    assert allocate_integer_quotas(11, {"b": 1, "a": 1, "c": 1}) == {"a": 4, "b": 4, "c": 3}

def test_main_and_cooldown_match_approved_token_plan():
    registry = load_source_registry(SOURCES)
    mixture = load_mixture_config(MIXTURE)
    main = build_mixture_plan(registry, mixture, "main")
    cooldown = build_mixture_plan(registry, mixture, "cooldown")
    assert main["total_tokens"] == 10_000_000_000
    assert main["role_quotas"] == {
        "pretrain_general": 6_500_000_000,
        "pretrain_telecom": 3_000_000_000,
        "pretrain_structured": 500_000_000,
    }
    assert cooldown["role_quotas"] == {
        "pretrain_general": 1_200_000_000,
        "pretrain_telecom": 700_000_000,
        "pretrain_structured": 100_000_000,
    }

def test_plan_rejects_evaluation_source():
    mixture = {"stages": {"bad": {"total_tokens": 10, "sources": {"open_telco_lite": 1}}}}
    with pytest.raises(ValueError, match="not permitted for pretraining"):
        build_mixture_plan(load_source_registry(SOURCES), mixture, "bad")
```

- [ ] **Step 2: Run the tests and confirm the missing-module failure**

Run: `uv run pytest tests/test_telco_mixture.py -v`

Expected: FAIL because `matgpt.data.mixture` does not exist.

- [ ] **Step 3: Implement largest-remainder allocation and plan validation**

Sort IDs before assigning equal remainders so plans do not depend on YAML or mapping order. Require positive integer totals, finite non-negative weights, at least one positive weight, exact role sums, and a configured source for every non-zero role. Expand the Telco source buckets to `three_gpp`, `rfc`, `research`, `patents`, and `semantic`, with weights `0.35`, `0.30`, `0.25`, `0.08`, and `0.02`. Reject a patent quota above 8% of the telecom quota.

Return a plan with this stable shape:

```python
{
    "version": 1,
    "stage": "main",
    "seed": 42,
    "total_tokens": 10_000_000_000,
    "role_quotas": {
        "pretrain_general": 6_500_000_000,
        "pretrain_telecom": 3_000_000_000,
        "pretrain_structured": 500_000_000,
    },
    "items": [
        {"id": "telco_common_corpus/three_gpp", "source_id": "telco_common_corpus", "bucket_id": "three_gpp", "role": "pretrain_telecom", "token_quota": 1_050_000_000},
    ],
    "plan_sha256": "64-character SHA-256 computed over the preceding fields",
}
```

- [ ] **Step 4: Add the CLI and checked mixture config**

The CLI accepts `--sources`, `--mixture`, `--stage`, optional `--total-tokens`, and optional `--output`. It prints JSON and writes exactly the same payload when `--output` is supplied. Configure pilot to `20,000,000` tokens with aggregate role weights `0.6416666667`, `0.3083333333`, and `0.05`, preserving the 12B aggregate proportions.

- [ ] **Step 5: Verify the exact plans**

Run: `uv run pytest tests/test_telco_mixture.py -v`

Run: `uv run python scripts/plan_telco_mixture.py --sources configs/data/telco_300m_sources.yaml --mixture configs/data/telco_300m_mixture.yaml --stage pilot`

Expected: tests PASS and CLI reports exactly `20,000,000` planned tokens with no non-pretraining roles.

- [ ] **Step 6: Commit mixture planning**

```bash
git add configs/data/telco_300m_mixture.yaml matgpt/data/mixture.py scripts/plan_telco_mixture.py tests/test_telco_mixture.py
git commit -m "feat: add deterministic telco mixture plans"
```

---

### Task 3: Streamed corpus assembly and provenance

**Files:**
- Create: `matgpt/data/telco_prepare.py`
- Create: `scripts/prepare_telco_corpus.py`
- Create: `tests/test_telco_prepare.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `SourceSpec`, mixture `items`, `normalize_text`, `DataQualityPolicy`, `QualityFilter`, `sha256_json`, and `sha256_text`.
- Produces: `normalize_source_row(source: SourceSpec, row: Mapping[str, Any], index: int, stage: str, bucket_id: str | None) -> dict[str, Any]`, `iter_deterministic_buffered(records: Iterable[dict[str, Any]], *, seed: int, buffer_size: int) -> Iterator[dict[str, Any]]`, `prepare_telco_corpora(registry: SourceRegistry, plans: Sequence[Mapping[str, Any]], output_dir: str | Path, quality_policy: DataQualityPolicy, *, buffer_size: int = 2048, force: bool = False, dataset_loader: Callable[..., Iterable[Mapping[str, Any]]] | None = None) -> dict[str, Any]`, and `audit_token_quotas(input_paths: Sequence[str | Path], tokenizer_dir: str | Path, plans: Sequence[Mapping[str, Any]], *, tolerance: float) -> dict[str, Any]`.

- [ ] **Step 1: Write failing normalization and determinism tests**

```python
def test_normalize_source_row_preserves_required_provenance():
    source = registry.by_id["telco_common_corpus"]
    record = normalize_source_row(source, {
        "identifier": "RFC8202", "collection": "IETF-RFCs",
        "license": "IETF Trust §4.c", "token_count": 710,
        "text": "  Link-state routing.\r\n",
    }, 0, "pilot", "rfc")
    assert record["document_id"] == "RFC8202"
    assert record["source_id"] == "telco_common_corpus"
    assert record["collection"] == "IETF-RFCs"
    assert record["license"] == "IETF Trust §4.c"
    assert record["role"] == "pretrain_telecom"
    assert record["stage"] == "pilot"
    assert record["content_sha256"] == record["text_sha256"]

def test_buffered_order_is_repeatable_and_seeded():
    records = [{"document_id": str(i), "content_sha256": str(i)} for i in range(20)]
    first = list(iter_deterministic_buffered(records, seed=42, buffer_size=5))
    assert first == list(iter_deterministic_buffered(records, seed=42, buffer_size=5))
    assert first != list(iter_deterministic_buffered(records, seed=43, buffer_size=5))
```

- [ ] **Step 2: Run those tests and observe the missing-module failure**

Run: `uv run pytest tests/test_telco_prepare.py -k 'normalize or buffered' -v`

Expected: FAIL because `matgpt.data.telco_prepare` does not exist.

- [ ] **Step 3: Implement row normalization and bounded deterministic ordering**

Use the upstream document ID field when present and otherwise use the normalized content SHA as `document_id`. Use row-level license when configured and non-empty, falling back to the registry license. Reject empty normalized text, unknown bucket collections, and missing license metadata. Buffered ordering may hold at most `buffer_size` records and sorts each buffer by `sha256(f"{seed}:{source_id}:{document_id}")`.

- [ ] **Step 4: Add failing builder tests with a synthetic loader**

```python
def test_builder_streams_only_to_quotas_and_promotes_atomically(tmp_path):
    manifest = prepare_telco_corpora(
        registry=registry, plans=[tiny_plan], output_dir=tmp_path / "corpus",
        quality_policy=DataQualityPolicy(enabled=True, min_chars=2, exact_dedup=True),
        dataset_loader=fake_streaming_loader,
    )
    assert manifest["complete"] is True
    assert (tmp_path / "corpus" / "pilot.jsonl").exists()
    assert not (tmp_path / "corpus.staging").exists()
    assert all(row["role"].startswith("pretrain_") for row in read_jsonl(tmp_path / "corpus" / "pilot.jsonl"))

def test_builder_failure_leaves_existing_output_untouched(tmp_path):
    output = tmp_path / "corpus"
    output.mkdir()
    (output / "sentinel").write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="exhausted before quota"):
        prepare_telco_corpora(
            registry=registry, plans=[too_large_plan], output_dir=output,
            quality_policy=DataQualityPolicy(enabled=True, min_chars=2, exact_dedup=True),
            dataset_loader=too_small_loader,
        )
    assert (output / "sentinel").read_text(encoding="utf-8") == "keep"

def test_builder_rejects_evaluation_plan_before_loading(tmp_path):
    bad_plan = {
        "stage": "pilot", "seed": 42, "total_tokens": 10,
        "items": [{"id": "open_telco_lite", "source_id": "open_telco_lite", "bucket_id": None, "role": "evaluation_only", "token_quota": 10}],
    }
    with pytest.raises(ValueError, match="not permitted for pretraining"):
        prepare_telco_corpora(
            registry=registry, plans=[bad_plan], output_dir=tmp_path / "bad",
            quality_policy=DataQualityPolicy(enabled=True), dataset_loader=fake_streaming_loader,
        )
    assert loader_calls == []
```

- [ ] **Step 5: Run builder tests and observe functional failures**

Run: `uv run pytest tests/test_telco_prepare.py -v`

Expected: normalization tests PASS; builder/promotion tests FAIL because assembly is not implemented.

- [ ] **Step 6: Implement streamed collection and manifests**

Call the injected loader or `datasets.load_dataset` with `streaming=True`, pinned `revision`, split/config, and `data_files` when configured. For each requested plan, scan each upstream source once, route collection rows to bucket quotas, apply one cross-source `QualityFilter`, and write accepted rows to `Path(f"{output_dir}.staging") / f"{stage}.jsonl"`. A pilot therefore produces `pilot.jsonl`; an approved full preparation passes both plans and atomically publishes `main.jsonl` plus `cooldown.jsonl` in one output tree. Estimate tokens from the configured upstream token field, otherwise `ceil(UTF-8 characters / 4)`. Stop only after every item quota is reached; fail if a source exhausts early.

Write `manifest.json` containing plan hash, source revisions, requested/estimated tokens, documents, bytes, per-license counts, quality report, input loader arguments, incomplete quota variance, and `complete: true`. Validate the staging manifest and JSONL before atomic rename. Refuse to replace a non-empty output unless `--force` is explicitly supplied; with force, move the prior output to a timestamped backup rather than deleting it.

- [ ] **Step 7: Add the preparation CLI**

Accept `--sources`, `--mixture`, repeatable `--stage`, `--output-dir`, optional `--total-tokens` for a single-stage pilot, `--contamination-patterns`, `--buffer-size`, and `--force`. Require `--allow-full-data` when either `main` or `cooldown` is selected, and require those two stages together for full preparation; pilot needs no override. The CLI must not import or call pretraining code.

- [ ] **Step 8: Verify builder tests and CLI help**

Run: `uv run pytest tests/test_telco_prepare.py -v`

Run: `uv run python scripts/prepare_telco_corpus.py --help`

Expected: PASS; help clearly labels `--allow-full-data` as a data-download gate, not a training gate.

- [ ] **Step 9: Commit corpus assembly**

```bash
git add .gitignore matgpt/data/telco_prepare.py scripts/prepare_telco_corpus.py tests/test_telco_prepare.py
git commit -m "feat: assemble provenance-rich telco corpus"
```

---

### Task 4: Exact model config and tokenizer fertility audit

**Files:**
- Create: `configs/matgpt_telco_300m.yaml`
- Create: `configs/data/telco_tokenizer_probes.yaml`
- Create: `matgpt/tokenizer/fertility.py`
- Modify: `matgpt/tokenizer/train.py`
- Modify: `tests/test_config.py`
- Modify: `tests/test_model_report.py`
- Modify: `tests/test_tokenizer.py`

**Interfaces:**
- Produces: `load_probe_sets(path: str | Path) -> dict[str, list[str]]`, `measure_tokenizer_fertility(tokenizer, probe_sets: Mapping[str, Sequence[str]]) -> dict[str, Any]`, and optional `probe_sets_path` input to `train_tokenizer_from_jsonl`.

- [ ] **Step 1: Write failing exact-config tests**

```python
def test_telco_config_has_exact_parameter_count():
    cfg = load_config("configs/matgpt_telco_300m.yaml")
    report = build_model_report(cfg)
    assert cfg["model"] == {
        "vocab_size": 32768, "context_length": 2048, "n_layers": 20,
        "n_heads": 16, "d_model": 1024, "d_ff": 3072, "dropout": 0.0,
        "norm_eps": 1.0e-5, "rope_base": 10000.0,
        "tie_embeddings": True, "use_bias": False, "activation": "swiglu",
    }
    assert report["parameter_count"] == 306_226_176
```

- [ ] **Step 2: Run exact-config tests and observe missing-config failure**

Run: `uv run pytest tests/test_config.py tests/test_model_report.py -k telco -v`

Expected: FAIL because `configs/matgpt_telco_300m.yaml` does not exist.

- [ ] **Step 3: Add the 306M configuration**

Use BF16, effective batch `131,072` tokens (`micro_batch_size: 8`, `gradient_accumulation_steps: 8`, context `2048`), AdamW, peak LR `3.0e-4`, minimum LR `3.0e-5`, weight decay `0.1`, betas `0.9/0.95`, grad clip `1.0`, warmup ratio `0.02`, maximum `12,000,000,000` tokens, 50M-token evaluation/sample intervals, and 250M-token checkpoints. Point all artifacts into Telco-specific directories.

- [ ] **Step 4: Add failing fertility tests**

```python
def test_fertility_report_has_general_and_telco_groups(tmp_path):
    tokenizer = train_small_test_tokenizer(tmp_path)
    report = measure_tokenizer_fertility(tokenizer, {
        "general": ["A router forwards packets."],
        "telecom": ["The gNodeB establishes an RRC connection."],
    })
    assert set(report["groups"]) == {"general", "telecom"}
    assert report["groups"]["telecom"]["tokens_per_word"] > 0
    assert report["round_trip_failures"] == []
```

- [ ] **Step 5: Run the fertility test and observe the missing-module failure**

Run: `uv run pytest tests/test_tokenizer.py -k fertility -v`

Expected: FAIL because `matgpt.tokenizer.fertility` does not exist.

- [ ] **Step 6: Implement probe loading and fertility reporting**

For every probe record encoded token count, Unicode word count, tokens per word, characters per token, and round-trip status. Group summaries include text count, token count, word count, tokens per word, and characters per token. Raise on empty groups, empty text, empty encodings, invalid IDs, or any round-trip failure. Add at least 20 fixed general probes and 40 telecom/networking probes covering RAN, core, transport, IP/MPLS, O-RAN, OSS/BSS, security, telemetry, and troubleshooting terminology.

Extend tokenizer training so a configured `tokenizer.probe_sets_path` adds `fertility` to `tokenizer_report.json` after training. Preserve the old report shape when no probe path is configured.

- [ ] **Step 7: Verify config and tokenizer tests**

Run: `uv run pytest tests/test_config.py tests/test_model_report.py tests/test_tokenizer.py -v`

Expected: PASS, including the exact parameter count and old tokenizer tests.

- [ ] **Step 8: Commit model and tokenizer audit**

```bash
git add configs/matgpt_telco_300m.yaml configs/data/telco_tokenizer_probes.yaml matgpt/tokenizer/fertility.py matgpt/tokenizer/train.py tests/test_config.py tests/test_model_report.py tests/test_tokenizer.py
git commit -m "feat: configure 306m telco model and tokenizer audit"
```

---

### Task 5: Stage-aware sharding and training selection

**Files:**
- Modify: `matgpt/config.py`
- Modify: `matgpt/data/shard.py`
- Modify: `matgpt/training/pretrain.py`
- Modify: `scripts/tokenize_and_shard.py`
- Modify: `tests/test_shards.py`
- Modify: `tests/test_pretrain_smoke.py`

**Interfaces:**
- Produces: optional `dataset.training_splits` mapping and optional `training.data_phases` list. Existing configs without them continue to use `dataset.train_split`.
- Produces: `training_split_for_tokens(cfg: Mapping[str, Any], tokens_processed: int) -> str`.

- [ ] **Step 1: Write failing phase-validation and selection tests**

```python
def test_phase_selection_switches_at_main_budget():
    cfg = load_config("configs/matgpt_telco_300m.yaml")
    assert training_split_for_tokens(cfg, 9_999_999_999) == "main"
    assert training_split_for_tokens(cfg, 10_000_000_000) == "cooldown"
    assert training_split_for_tokens(cfg, 11_999_999_999) == "cooldown"

def test_existing_config_keeps_train_split():
    cfg = load_config("configs/matgpt_mini_8m.yaml")
    assert training_split_for_tokens(cfg, 0) == "train"
```

Validation rejects non-increasing `until_tokens`, unknown split names, a final phase boundary unequal to `training.max_tokens`, and phases on a config without named `dataset.training_splits`.

- [ ] **Step 2: Run focused tests and observe missing-function failure**

Run: `uv run pytest tests/test_config.py tests/test_pretrain_smoke.py -k phase -v`

Expected: FAIL because phase selection is not implemented.

- [ ] **Step 3: Implement opt-in phase configuration and named split sharding**

When `dataset.training_splits` exists, `tokenize_splits_from_config` tokenizes each named source JSONL plus validation. The Telco config maps `main` to `main.jsonl` and `cooldown` to `cooldown.jsonl`. Existing configs keep their two-file loop unchanged.

`training_split_for_tokens` chooses the first phase whose exclusive `until_tokens` is greater than `tokens_processed`. At exactly 10B tokens it returns cooldown. Keep one `PackedTokenDataset` per configured phase, sample only from the active phase, and persist each dataset RNG state by split name. Resume validation accepts the configured phase keys while retaining the existing train/validation requirements for legacy configs.

- [ ] **Step 4: Add a synthetic two-phase resume test**

Build tiny `main`, `cooldown`, and validation shards with distinguishable token ranges. Run to the boundary, checkpoint, resume, and assert the next sampled batch uses the cooldown range and matches an uninterrupted reference run. Do not weaken the existing complete-RNG-state checks.

- [ ] **Step 5: Run sharding and pretraining tests**

Run: `uv run pytest tests/test_shards.py tests/test_pretrain_smoke.py tests/test_training_core.py -v`

Expected: PASS for both legacy and staged configs.

- [ ] **Step 6: Commit staged training support**

```bash
git add matgpt/config.py matgpt/data/shard.py matgpt/training/pretrain.py scripts/tokenize_and_shard.py tests/test_shards.py tests/test_pretrain_smoke.py
git commit -m "feat: support main and cooldown data phases"
```

---

### Task 6: Open Telco evaluation materialization

**Files:**
- Create: `matgpt/eval/open_telco.py`
- Create: `scripts/prepare_open_telco_evals.py`
- Create: `tests/test_open_telco.py`

**Interfaces:**
- Consumes: registry evaluation-only entries and existing `load_multiple_choice_examples` JSONL schema.
- Produces: `convert_open_telco_row(dataset_id: str, config: str, index: int, row: Mapping[str, Any]) -> dict[str, Any]` and `prepare_open_telco_evals(registry: SourceRegistry, source_id: str, configs: Sequence[str], output_dir: str | Path, *, dataset_loader: Callable[..., Iterable[Mapping[str, Any]]] | None = None) -> dict[str, Any]`.

- [ ] **Step 1: Write failing conversion tests**

```python
@pytest.mark.parametrize("config", ["teleqna", "oranbench", "srsranbench", "sixg_bench"])
def test_multiple_choice_configs_convert_to_local_schema(config):
    row = {"question": "Which layer?", "choices": ["RRC", "NAS"], "answer": 0, "category": "radio"}
    converted = convert_open_telco_row("GSMA/ot-lite", config, 7, row)
    assert converted["id"] == f"GSMA/ot-lite/{config}/7"
    assert converted["prompt"] == "Which layer?"
    assert converted["choices"] == ["RRC", "NAS"]
    assert converted["answer"] == 0

def test_non_multiple_choice_config_fails_explicitly():
    with pytest.raises(ValueError, match="not supported by the multiple-choice evaluator"):
        convert_open_telco_row("GSMA/ot-lite", "telemath", 0, {"question": "x", "answer": 1.0})
```

- [ ] **Step 2: Run tests and observe missing-module failure**

Run: `uv run pytest tests/test_open_telco.py -v`

Expected: FAIL because `matgpt.eval.open_telco` does not exist.

- [ ] **Step 3: Implement pinned evaluation streaming and JSONL output**

Support the four multiple-choice configs initially: `teleqna`, `oranbench`, `srsranbench`, and `sixg_bench`. Preserve category/subject/task name, dataset revision, source row index, and a content hash. Validate converted files by loading them with `load_multiple_choice_examples`.

The loader must be called with `streaming=True`, pinned revision, explicit config, and `split="test"`. Write files under a staging directory, then promote them with an evaluation manifest. Reject any registry source not marked `evaluation_only`. Never modify the corpus-builder output or its manifest.

- [ ] **Step 4: Add CLI and atomic-materialization tests**

The CLI accepts `--sources`, `--dataset {lite,full}`, repeatable `--config`, and `--output-dir`; defaults are the four supported multiple-choice configs. Synthetic tests assert pinned loader arguments, deterministic IDs, manifest hash, and no files under a supplied training directory.

- [ ] **Step 5: Run evaluation tests and existing task tests**

Run: `uv run pytest tests/test_open_telco.py tests/test_eval_tasks.py -v`

Expected: PASS.

- [ ] **Step 6: Commit the adapter**

```bash
git add matgpt/eval/open_telco.py scripts/prepare_open_telco_evals.py tests/test_open_telco.py
git commit -m "feat: materialize pinned open telco evaluations"
```

---

### Task 7: Dedicated Colab notebook and operating runbook

**Files:**
- Create: `notebooks/train_matgpt_telco_300m_colab.ipynb`
- Create: `tests/test_telco_notebook_colab.py`
- Create: `docs/runbooks/colab-telco-300m.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: the config and CLIs from Tasks 1-6 plus existing preflight, benchmark, pretraining, evaluation, checkpoint comparison, and run-summary scripts.
- Produces: notebook stages `prepare_data`, `prepare`, `smoke`, `pilot`, `full`, and `evaluate`.

- [ ] **Step 1: Write failing notebook contract tests**

```python
def test_telco_notebook_is_valid_and_defaults_to_prepare_data():
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
    assert 'RUN_STAGE = "prepare_data"' in source
    for stage in ("prepare_data", "prepare", "smoke", "pilot", "full", "evaluate"):
        assert stage in source

def test_prepare_stages_cannot_execute_pretraining():
    tree = ast.parse(code_after_heading("## Run the selected stage"))
    calls = pretraining_calls_by_run_stage(tree)
    assert calls["prepare_data"] == []
    assert calls["prepare"] == []

def test_gpu_gate_is_cuda_and_memory_based_not_name_locked():
    source = code_after_heading("## Inspect the runtime")
    assert "torch.cuda.is_available()" in source
    assert "get_device_properties" in source
    assert '"T4" in gpu_name' not in source
```

- [ ] **Step 2: Run the notebook tests and observe missing-file failure**

Run: `uv run pytest tests/test_telco_notebook_colab.py -v`

Expected: FAIL because the notebook does not exist.

- [ ] **Step 3: Create the stage-gated notebook**

Reuse helper patterns from `train_matgpt_t4_base_colab.ipynb`, but use:

```python
RUN_STAGE = "prepare_data"  # @param ["prepare_data", "prepare", "smoke", "pilot", "full", "evaluate"]
RUN_NAME = "matgpt_telco_300m"
DRIVE_ROOT = "/content/drive/MyDrive/matgpt_artifacts"
LOCAL_WORK_ROOT = "/content/matgpt_work"
CONFIG_PATH = "configs/matgpt_telco_300m.yaml"
```

`prepare_data` first materializes pinned Open Telco Lite questions outside the training tree, passes those JSONL files to the contamination filter, then performs only mixture planning and bounded streamed corpus preparation. Pilot preparation publishes `pilot.jsonl`; the notebook writes a temporary one-phase config mapping its `main` phase to that file. Approved full preparation publishes `main.jsonl` and `cooldown.jsonl` together for the checked two-phase config. `prepare` trains/validates the tokenizer, audits exact token quotas, shards the applicable named phases, runs artifact preflight, and executes a temporary batch benchmark. `smoke` performs 20 successful updates plus resume verification. `pilot` has an explicit bounded token/step override. `full` executes the unchanged 12B schedule only when manually selected and after required evidence files exist. `evaluate` reuses the isolated Open Telco assets, evaluates preserved checkpoints, runs repetition/consistency/comparison commands, and writes the summary.

Runtime checks require CUDA for training stages, report device name and VRAM, warn below 40 GiB for the default batch, and accept the observed `NVIDIA RTX PRO 6000 Blackwell Server Edition`. Preparation may run without CUDA; no stage asserts a literal GPU model name.

- [ ] **Step 4: Write the runbook and README entry**

The runbook must include source-role table, unresolved `license_review: required` meaning, expected disk sizing, Drive/local paths, exact cell order, stop points after every stage, evidence files, checkpoint resume, quota failure handling, full-run authorization, evaluation commands, and rollback. Clearly state that local tests do not prove upstream access, GPU throughput, data rights clearance, or model quality.

- [ ] **Step 5: Validate notebook JSON and contract tests**

Run: `python -m json.tool notebooks/train_matgpt_telco_300m_colab.ipynb`

Run: `uv run pytest tests/test_telco_notebook_colab.py tests/test_notebook_colab.py -v`

Expected: valid JSON and all old/new notebook tests PASS.

- [ ] **Step 6: Commit notebook and runbook**

```bash
git add notebooks/train_matgpt_telco_300m_colab.ipynb tests/test_telco_notebook_colab.py docs/runbooks/colab-telco-300m.md README.md
git commit -m "docs: add stage-gated telco 300m colab workflow"
```

---

### Task 8: End-to-end verification and release

**Files:**
- Modify only files required to correct evidence-backed failures.

**Interfaces:**
- Consumes all prior deliverables.
- Produces a clean feature branch, pushed PR, merged `main`, and an operator handoff that starts at `prepare_data` rather than training.

- [ ] **Step 1: Run the narrow Telco suite**

Run:

```bash
uv run pytest tests/test_telco_sources.py tests/test_telco_mixture.py tests/test_telco_prepare.py tests/test_tokenizer.py tests/test_model_report.py tests/test_shards.py tests/test_pretrain_smoke.py tests/test_open_telco.py tests/test_telco_notebook_colab.py -v
```

Expected: PASS.

- [ ] **Step 2: Run all repository tests**

Run: `uv run pytest`

Expected: all tests PASS with no regressions to the 8M/59M tracks.

- [ ] **Step 3: Run static artifact checks**

Run: `python -m json.tool notebooks/train_matgpt_telco_300m_colab.ipynb`

Run: `uv run python scripts/model_report.py --config configs/matgpt_telco_300m.yaml`

Run: `uv run python scripts/plan_telco_mixture.py --sources configs/data/telco_300m_sources.yaml --mixture configs/data/telco_300m_mixture.yaml --stage main`

Run: `uv run python scripts/plan_telco_mixture.py --sources configs/data/telco_300m_sources.yaml --mixture configs/data/telco_300m_mixture.yaml --stage cooldown`

Expected: valid notebook, exact `306,226,176` parameters, exact 10B/2B plans, and no evaluation/post-training/RAG sources in either plan.

- [ ] **Step 4: Run a local synthetic corpus-to-shard smoke path**

Use only pytest fixtures/local JSONL; do not contact Hugging Face. Assert normalized metadata, tokenizer fertility, named phase shard metadata, and a finite one-step CPU training loss.

- [ ] **Step 5: Review the complete diff**

Run: `git diff --check origin/main HEAD`

Run: `git diff --stat origin/main HEAD`

Run: `git status --short --branch`

Review correctness, rights metadata, contamination isolation, quota failure behavior, memory bounds, legacy compatibility, notebook non-promotion, and documentation honesty.

- [ ] **Step 6: Commit any verification fixes**

```bash
git add matgpt configs scripts tests notebooks docs README.md
git commit -m "fix: harden telco training track verification"
```

Skip this commit when no fixes are needed.

- [ ] **Step 7: Push, open the PR, merge, and synchronize local main**

```bash
git push -u origin codex/telco-300m
gh pr create --base main --head codex/telco-300m --title "Add Telco 300M from-scratch training track" --body "Implements the approved Telco 300M public-data, tokenizer, training, evaluation, Colab, and runbook design."
gh pr checks --watch
gh pr merge --squash --delete-branch=false
git fetch --prune origin
git status --short --branch
```

Do not modify the user's dirty/diverged original main worktree. If that worktree cannot fast-forward safely, report the condition and leave it untouched after confirming the remote merge.

- [ ] **Step 8: Hand off the first real action**

Tell the operator to open `notebooks/train_matgpt_telco_300m_colab.ipynb`, attach Drive, select the RTX PRO 6000 or A100, leave `RUN_STAGE = "prepare_data"`, and run only through the data-plan/preparation evidence. The first review artifacts are `mixture_plan.json` and `manifest.json`; no pretraining begins at this gate.
