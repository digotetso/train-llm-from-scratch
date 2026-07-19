# MatGPT T4 Base Training Framework

This repository contains the base-pretraining framework for validating the MatGPT course models before recording the course:

- `MatGPT-Mini 8M` on `roneneldan/TinyStories`
- `MatGPT-Tiny 59M` on `BabyLM-community/BabyLM-2026-Strict`

The goal is not a toy training loop. The framework is built around quality-critical small-model decisions: deterministic data preparation, training-tokenizer-only fitting, packed token streams, FP16 T4 training, gradient accumulation, warmup/cosine scheduling, checkpoint resume, validation loss, perplexity, and fixed prompt samples.

## Install

```bash
python -m pip install -e ".[test]"
```

For Colab T4 with optional 8-bit AdamW support:

```bash
python -m pip install -e ".[test,colab]"
```

## Recommended Colab Notebook

Use [the Colab notebook](notebooks/train_matgpt_t4_base_colab.ipynb) together
with the [first-run T4 runbook](docs/runbooks/colab-t4-first-run.md). The
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
  --require-t4 \
  --min-free-disk-gb 20
```

The notebook uses `/content/matgpt_work/<run-name>/` for active normalized
data, tokenizer files, and shards. Durable copies and run evidence live under
`/content/drive/MyDrive/matgpt_artifacts/<run-name>/`, including
`run/preflight.json`, `run/benchmark.json`, `run/metrics.csv`, checkpoints,
evaluations, samples, and `run/run_summary.md`.

For W&B logging, set `ENABLE_WANDB = True` in the notebook. The YAML configs keep W&B disabled by default so local runs do not require an account.

## Operator Semantics And Gates

The 8M config pins `roneneldan/TinyStories` to commit `f54c09fd23315a6f9c86f9dc80f725de7d8f9c64`. The byte-level tokenizer starts with the complete byte alphabet; configuration rejects a vocabulary that cannot hold that alphabet and the configured special tokens.

For a first real run, use only [the stage-gated Colab notebook](notebooks/train_matgpt_t4_base_colab.ipynb) with the [first-run T4 runbook](docs/runbooks/colab-t4-first-run.md). Do not begin a first run from standalone CLI commands in this README.

The required notebook order is: `prepare` validates the normalized data, tokenizer, and shards, then runs T4 preflight and the configured-batch benchmark; stop and review both JSON reports before selecting `smoke`. The benchmark uses a temporary model, while `prepare` runs no pretraining command and creates no checkpoint. `smoke` runs 20 updates followed by a five-update resume check; `pilot` stops at global step 306; `evaluate` records and reviews the evidence; and `full` is manually selected only after explicit user and Codex pilot approval. `--max-steps` means additional successful updates in the current invocation and does not rewrite the configured full learning-rate schedule.

The notebook runs evaluation and summary generation: `scripts/evaluate.py` writes evaluation JSON artifacts, and `scripts/summarize_run.py` writes `run_summary.md`. Local tests use synthetic fixtures and cannot, by themselves, prove T4 allocation, prepared-artifact integrity, benchmark results, or training quality.

## Configured Training Runs

The Mini configuration targets `200M` training tokens, and the Tiny configuration targets `1B`. These are configured schedule targets, not observed runtime results. The stage-gated notebook and runbook are the only documented procedure for a first real T4 run; its commands preserve the schedule and prevent a pilot from promoting itself.

The Mini configuration is the first real-run model. The Tiny configuration remains a later, separate experiment; the BabyLM deterministic validation split is configured by `validation_fraction: 0.01` in `configs/matgpt_tiny_59m.yaml`.

After an approved run, use the runbook `evaluate` stage for checkpoint evaluation and samples. Local multiple-choice task evaluation and interactive generation are advanced/debug workflows, not first-run promotion commands.

## Outputs

Each run writes:

- normalized JSONL files and corpus manifest
- tokenizer artifacts and tokenizer report
- packed binary token shards and metadata
- persisted `preflight.json` and `benchmark.json` gate evidence
- `runs/<name>/metrics.csv`
- fixed prompt samples under `runs/<name>/samples/`
- resumable checkpoints under `runs/<name>/checkpoints/`
- checkpoint evaluations and `run_summary.md`

## Tests

The test suite uses synthetic local fixtures and does not download datasets:

```bash
pytest
```

Current coverage includes config validation, normalization, tokenizer round trip, sharding, GPT forward/causality, checkpoint equivalence, batch sampling, optimizer setup, and tiny fixed-batch overfit.
