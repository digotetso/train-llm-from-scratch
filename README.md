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

Use [notebooks/train_matgpt_t4_base_colab.ipynb](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/notebooks/train_matgpt_t4_base_colab.ipynb) for Google Colab T4 runs.

The notebook walks through:

- mounting Google Drive for persistent checkpoints;
- connecting Hugging Face for dataset access;
- connecting Weights & Biases for live experiment tracking;
- preparing normalized corpus files;
- training the tokenizer;
- creating packed token shards;
- benchmarking safe T4 micro-batch sizes;
- smoke training, full training, and checkpoint resume;
- evaluation and text generation.

For W&B logging, set `ENABLE_WANDB = True` in the notebook. The YAML configs keep W&B disabled by default so local runs do not require an account.

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
- `runs/<name>/metrics.csv`
- fixed prompt samples under `runs/<name>/samples/`
- resumable checkpoints under `runs/<name>/checkpoints/`

## Tests

The test suite uses synthetic local fixtures and does not download datasets:

```bash
pytest
```

Current coverage includes config validation, normalization, tokenizer round trip, sharding, GPT forward/causality, checkpoint equivalence, batch sampling, optimizer setup, and tiny fixed-batch overfit.
