# MatGPT GPU Base Training Framework

This repository contains the base-pretraining framework for validating the MatGPT course models before recording the course:

- `MatGPT-Mini 8M` on `roneneldan/TinyStories`
- `MatGPT-Tiny 59M` on `BabyLM-community/BabyLM-2026-Strict`

The goal is not a toy training loop. The framework is built around quality-critical small-model decisions: deterministic data preparation, exact deduplication and contamination hooks, training-tokenizer-only fitting, packed token streams, mixed-precision NVIDIA GPU training, gradient accumulation, warmup/cosine scheduling, checkpoint resume, validation loss, perplexity, task evaluation, and fixed prompt samples.

## Big-Lab Discipline In This Repo

The repo cannot copy big-lab compute, but it now copies more of the training discipline:

- data quality filtering is configured under `dataset.quality`;
- checkpoints refuse unsafe resumes when the config, tokenizer, or data manifest hash changes;
- dataset sampler RNG state is saved so interrupted runs can resume deterministically;
- model size labels can be checked against actual parameter counts;
- full-run token targets are larger than the original smoke-oriented defaults;
- local multiple-choice JSONL tasks can be evaluated alongside validation loss.

Before a serious run, inspect the model size:

```bash
python scripts/model_report.py --config configs/matgpt_tiny_59m.yaml
```

## Install

```bash
python -m pip install -e ".[test]"
```

For a Colab GPU runtime with optional 8-bit AdamW support:

```bash
python -m pip install -e ".[test,colab]"
```

## Recommended Colab Notebook

Use [the Colab notebook](notebooks/train_matgpt_t4_base_colab.ipynb) together
with the [first-run GPU runbook](docs/runbooks/colab-t4-first-run.md). The
notebook is stage-gated; it never promotes a pilot to the full run by itself.

The notebook walks through:

- keeping active prepared data under fast, ephemeral `/content`;
- synchronizing normalized data, tokenizer files, and shards to Google Drive;
- writing checkpoints and run evidence directly to Google Drive;
- connecting Hugging Face for dataset access;
- connecting Weights & Biases for live experiment tracking;
- running `prepare`, `smoke`, `pilot`, `full`, and `evaluate` stages;
- requiring preflight and finite benchmark evidence during `prepare` and before every training stage;
- stopping smoke after 20 successful updates, checking a 5-update resume, and
  stopping the pilot at global step 306;
- requiring explicit user and Codex review before `full` is manually selected;
- evaluating checkpoints and displaying the persisted review evidence.

The strict preflight command used during `prepare` and before each training stage is:

```bash
python scripts/preflight_t4.py \
  --config /content/matgpt_work/<run-name>/config/<model>.yaml \
  --require-supported-gpu \
  --min-free-disk-gb 20
```

The notebook uses `/content/matgpt_work/<run-name>/` for active normalized
data, tokenizer files, and shards. Durable copies and run evidence live under
`/content/drive/MyDrive/matgpt_artifacts/<run-name>/`, including
`run/preflight.json`, `run/benchmark.json`, `run/metrics.csv`, checkpoints,
evaluations, `run/resume_verification.json`, samples, and
`run/run_summary.md`.

For W&B logging, set `ENABLE_WANDB = True` in the notebook. The YAML configs keep W&B disabled by default so local runs do not require an account.

## Telco 300M Training Track

The dedicated [Telco 300M Colab notebook](notebooks/train_matgpt_telco_300m_colab.ipynb)
and [operator runbook](docs/runbooks/colab-telco-300m.md) implement the guarded
from-scratch `306,226,176`-parameter English + telecom track. It uses an
immutable source registry, separates pretraining/post-training/RAG/evaluation
roles, plans a 10B-token main phase plus 2B-token cooldown, audits actual
tokenizer quotas before sharding, and isolates Open Telco Lite/Full from
training.

Start with the notebook defaults (`RUN_STAGE = "prepare_data"`,
`DATA_PLAN = "pilot"`). The 20M-token pilot, resume check, evidence review, full
data authorization, and full training authorization are separate manual gates.
Evaluation creates 50 blinded LLM reviews per checkpoint for this Codex task;
human review remains optional. The runbook includes data-rights cautions,
storage sizing, throughput-based time estimates, exact Drive paths, resume, and
rollback instructions.

## Operator Semantics And Gates

The 8M config pins `roneneldan/TinyStories` to commit `f54c09fd23315a6f9c86f9dc80f725de7d8f9c64`. The byte-level tokenizer starts with the complete byte alphabet; configuration rejects a vocabulary that cannot hold that alphabet and the configured special tokens.

For a first real run, use only [the stage-gated Colab notebook](notebooks/train_matgpt_t4_base_colab.ipynb) with the [first-run GPU runbook](docs/runbooks/colab-t4-first-run.md). Do not begin a first run from standalone CLI commands in this README.

The required notebook order is: `prepare` validates the normalized data, tokenizer, and shards, then runs supported-GPU preflight and the configured-batch benchmark; stop and review both JSON reports before selecting `smoke`. The benchmark uses a temporary model, while `prepare` runs no pretraining command and creates no checkpoint. `smoke` runs 20 updates followed by a five-update resume check; `pilot` stops at global step 306; `evaluate` requires both checkpoints, evaluates them, and verifies complete resume state without taking an update; and `full` is manually selected only after explicit user and Codex pilot approval. The full stage must finish at its configured schedule step. `--max-steps` means additional successful updates in the current invocation and does not rewrite the configured full learning-rate schedule.

The notebook runs evaluation, read-only resume verification, and summary generation: `scripts/evaluate.py` writes evaluation JSON artifacts, `scripts/pretrain.py --verify-only` loads complete resume state without an optimizer update, the notebook persists the result as `resume_verification.json`, and `scripts/summarize_run.py` writes `run_summary.md`. Local tests use synthetic fixtures and cannot, by themselves, prove GPU allocation, prepared-artifact integrity, benchmark results, or training quality.

## Configured Training Runs

The Mini configuration targets `200M` training tokens, and the Tiny configuration targets `1B`. These are configured schedule targets, not observed runtime results. The stage-gated notebook and runbook are the only documented procedure for a first real GPU run; its commands preserve the schedule and prevent a pilot from promoting itself.

The Mini configuration is the first real-run model. The Tiny configuration remains a later, separate experiment; the BabyLM deterministic validation split is configured by `validation_fraction: 0.01` in `configs/matgpt_tiny_59m.yaml`.

After an approved run, use the runbook `evaluate` stage for checkpoint evaluation and samples. Local multiple-choice task evaluation and interactive generation are advanced/debug workflows, not first-run promotion commands.

## Outputs

Each run writes:

- normalized JSONL files and corpus manifest
- data-quality filter counts in the corpus manifest
- tokenizer artifacts and tokenizer report
- packed binary token shards and metadata
- persisted `preflight.json` and `benchmark.json` gate evidence
- `runs/<name>/metrics.csv`
- fixed prompt samples under `runs/<name>/samples/`
- resumable checkpoints under `runs/<name>/checkpoints/`
- checkpoint evaluations, `resume_verification.json`, and `run_summary.md`

## Compare Preserved Checkpoints

Use the comparison suite after mounting or downloading the preserved checkpoints,
the run's config snapshot, tokenizer, and prepared shards. Keep the same validation dataset
and choose every seed before inspecting the results. The command below
compares the 100M, 150M, 170M, and 200M checkpoints with ten matched validation
samples and five matched story-generation runs:

```bash
python scripts/compare_checkpoints.py \
  --config /path/to/run/config.snapshot.yaml \
  --checkpoint 100m=/path/to/checkpoint-100m.pt \
  --checkpoint 150m=/path/to/checkpoint-150m.pt \
  --checkpoint 170m=/path/to/checkpoint-170m.pt \
  --checkpoint 200m=/path/to/checkpoint-200m.pt \
  --validation-seeds 1001,1002,1003,1004,1005,1006,1007,1008,1009,1010 \
  --generation-seeds 2001,2002,2003,2004,2005 \
  --prompts evals/story_prompts.jsonl \
  --task evals/story_consistency.jsonl \
  --review-per-checkpoint 50 \
  --review-seed 3001 \
  --output-dir /path/to/checkpoint-comparison
```

The validation seed changes only which windows are sampled from the unchanged
validation shards. Every checkpoint receives the same seed-matched windows. A
generation seed changes sampling randomness for all 50 fixed prompts, producing
250 stories per checkpoint. The suite measures repeated words, phrases, and
sentences automatically; it also runs 100 fixed character, object/attribute,
location/state, and cause/effect continuation checks.

The output contains complete evidence in `checkpoints/<label>.json`, paired loss
and aggregate results in `comparison_summary.json`, and blinded review material
under `llm_judge/`. Existing output directories are refused so an earlier run
cannot be overwritten accidentally.

### Blinded LLM Story Review

For qualitative review, this conversation's LLM is the primary judge; no
external model API or API key is required. The comparison command selects exactly 50 stories per
checkpoint, mixes them under opaque review IDs, and creates batches of at most
20 stories. Use this workflow:

1. Give `llm_judge/judge_prompt.md` and one
   `llm_judge/batches/judge_batch_<NN>.jsonl` file at a time to this
   conversation's LLM.
2. Do not provide `llm_judge/review_key.json` until every judgment is complete.
3. Save each returned JSONL response under `llm_judge/results/`, preserving one
   result for every review ID.
4. Score all completed batches together, repeating `--judgments` for each file:

```bash
python scripts/score_story_judgments.py \
  --key /path/to/checkpoint-comparison/llm_judge/review_key.json \
  --judgments /path/to/checkpoint-comparison/llm_judge/results/batch-01.jsonl \
  --judgments /path/to/checkpoint-comparison/llm_judge/results/batch-02.jsonl \
  --reviewer llm \
  --output /path/to/checkpoint-comparison/llm_judge/llm_scores.json
```

The scoring command rejects missing, duplicate, unknown, malformed, or
out-of-range judgments before revealing per-checkpoint means, score
distributions, flags, and row-level evidence. Human review is optional; use the
same blinded files with `--reviewer human` and a separate output path so human
and LLM evidence are never silently mixed.

Treat the ten validation seeds as an initial paired sample, not statistical
certainty. Validation loss remains the main model-quality evidence. Consistency
tasks, repetition rates, and blinded LLM judgments show different failure modes;
do not collapse them into one unexplained score or change seeds after seeing
which checkpoint wins.

## Tests

The test suite uses synthetic local fixtures and does not download datasets:

```bash
pytest
```

Current coverage includes config validation, normalization, data-quality filtering, tokenizer round trip, sharding, GPT forward/causality, checkpoint equivalence, deterministic batch sampling resume, optimizer setup, task eval scoring, model-size reporting, and tiny fixed-batch overfit.
