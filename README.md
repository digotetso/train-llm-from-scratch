# MatGPT T4 Base Training Framework

This repository contains the base-pretraining framework for validating the MatGPT course models before recording the course:

- `MatGPT-Mini 8M` on `roneneldan/TinyStories`
- `MatGPT-Tiny 46M` on `BabyLM-community/BabyLM-2026-Strict`

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
- requiring preflight and finite benchmark evidence before every training stage;
- stopping smoke after 20 successful updates, checking a 5-update resume, and
  stopping the pilot at global step 306;
- requiring explicit user and Codex review before `full` is manually selected;
- evaluating checkpoints and displaying the persisted review evidence.

The strict preflight command used before each training stage is:

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

Run `prepare` before any training-stage preflight. Preparation creates and validates the normalized data, tokenizer, and shards; `preflight_t4.py` then verifies those artifacts, persistent storage, CUDA, and the required T4 before `smoke`, `pilot`, or `full` can proceed. See the [first-run T4 runbook](docs/runbooks/colab-t4-first-run.md) for prerequisites, exact evidence, and stop conditions.

`--max-steps` means additional successful updates in the current invocation; it does not rewrite the configured full learning-rate schedule. `smoke` runs 20 updates followed by a five-update resume check. `pilot` stops at global step 306, then `evaluate` records the evidence. `full` is selected manually only after explicit user and Codex pilot approval.

`scripts/evaluate.py` writes an evaluation JSON artifact, while `scripts/summarize_run.py` writes `run_summary.md`. Local tests use synthetic fixtures and cannot, by themselves, prove T4 allocation, prepared-artifact integrity, benchmark results, or training quality.

## 8M TinyStories Base Run

Prepare normalized data:

```bash
python scripts/prepare_dataset.py --config configs/matgpt_mini_8m.yaml
```

Train the 8K byte-level BPE tokenizer on the TinyStories training split:

```bash
python scripts/train_tokenizer.py --config configs/matgpt_mini_8m.yaml
```

Tokenize once and create packed `uint16` shards:

```bash
python scripts/tokenize_and_shard.py --config configs/matgpt_mini_8m.yaml
```

Run a short smoke train:

```bash
python scripts/pretrain.py --config configs/matgpt_mini_8m.yaml --max-steps 20
```

Benchmark safe micro-batch sizes on the current T4:

```bash
python scripts/benchmark_t4.py \
  --config configs/matgpt_mini_8m.yaml \
  --batch-sizes 8,16,24,32
```

Run the full configured target:

```bash
python scripts/pretrain.py --config configs/matgpt_mini_8m.yaml
```

Resume after Colab interruption:

```bash
python scripts/pretrain.py \
  --config configs/matgpt_mini_8m.yaml \
  --resume-from runs/matgpt_mini_8m/checkpoints/latest.pt
```

## 46M BabyLM Base Run

BabyLM-2026-Strict currently exposes a training split. The framework therefore creates a deterministic hash-based validation split using `validation_fraction: 0.01` in `configs/matgpt_tiny_46m.yaml`.

```bash
python scripts/prepare_dataset.py --config configs/matgpt_tiny_46m.yaml
python scripts/train_tokenizer.py --config configs/matgpt_tiny_46m.yaml
python scripts/tokenize_and_shard.py --config configs/matgpt_tiny_46m.yaml
python scripts/pretrain.py --config configs/matgpt_tiny_46m.yaml --max-steps 20
python scripts/benchmark_t4.py --config configs/matgpt_tiny_46m.yaml --batch-sizes 2,4,6,8
python scripts/pretrain.py --config configs/matgpt_tiny_46m.yaml
```

Resume:

```bash
python scripts/pretrain.py \
  --config configs/matgpt_tiny_46m.yaml \
  --resume-from runs/matgpt_tiny_46m/checkpoints/latest.pt
```

## Evaluate and Sample

```bash
python scripts/evaluate.py \
  --config configs/matgpt_tiny_46m.yaml \
  --checkpoint runs/matgpt_tiny_46m/checkpoints/best.pt
```

Generate from a base checkpoint:

```bash
python scripts/chat.py \
  --config configs/matgpt_tiny_46m.yaml \
  --checkpoint runs/matgpt_tiny_46m/checkpoints/best.pt \
  --prompt "A token is"
```

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
