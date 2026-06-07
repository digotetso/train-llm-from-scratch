# T4 Base Training Framework Design

## Goal

Build a production-quality validation framework for training MatGPT-Mini 8M on TinyStories and MatGPT-Tiny 46M on BabyLM-2026-Strict from random weights on a Google Colab T4. The framework prioritizes the best achievable model quality at these sizes: careful corpus handling, strong tokenizer validation, packed token streams, stable optimization, robust checkpoint resume, and honest evaluation.

## Scope

The first implementation covers base pretraining only. It creates extension points for continued pretraining, SFT, DPO, chat evaluation, and A100 scaling, but does not implement those post-training stages yet.

In scope:

- Repository scaffold under `matgpt/`, `scripts/`, `configs/`, and `tests/`.
- T4-ready configs for `matgpt_mini_8m` and `matgpt_tiny_46m`.
- Dataset acquisition through Hugging Face `datasets`.
- Deterministic normalization, manifesting, official split preservation, and optional capped token/document sampling for smoke tests.
- Tokenizer training and validation with reserved special tokens.
- Packed `uint16` token shards with metadata and manifest hashes.
- Decoder-only Transformer with RoPE, RMSNorm, SwiGLU MLP, tied embeddings, causal self-attention via PyTorch SDPA, and dropout control.
- Pretraining loop with FP16 AMP, gradient accumulation, AdamW parameter grouping, optional bitsandbytes 8-bit AdamW, warmup plus cosine schedule, gradient clipping, validation, fixed prompt sampling, CSV metrics, and checkpoint/resume.
- Evaluation script for validation loss, perplexity, fixed sample prompts, and tokenizer reports.
- Tests for core data, tokenizer, model, checkpoint, and training behavior.

Out of scope for this pass:

- SFT, DPO, ORPO, PPO, RLHF, and Gradio UI.
- Distributed training.
- Custom CUDA kernels.
- Claims that the resulting 46M model is competitive with large pretrained assistants.

## Architecture

The framework is an importable Python package plus thin CLI scripts:

```text
configs/
  matgpt_mini_8m.yaml
  matgpt_tiny_46m.yaml
matgpt/
  config.py
  utils/
  data/
  tokenizer/
  model/
  training/
  eval/
scripts/
  prepare_dataset.py
  train_tokenizer.py
  tokenize_and_shard.py
  pretrain.py
  evaluate.py
  chat.py
tests/
```

The data flow is:

```text
HF dataset
-> normalized JSONL documents and manifest
-> tokenizer trained on train split only
-> packed token shards with EOS between documents
-> pretraining windows sampled from memory-mapped shards
-> resumable checkpoints and fixed evaluations
```

## Quality Decisions

Use official dataset splits when present. TinyStories and BabyLM are baseline corpora, so the framework preserves official splits rather than applying aggressive custom filters. Custom normalization removes only encoding/control-character noise and normalizes Unicode to NFKC.

Train tokenizers only on training documents. This avoids validation leakage and makes tokenizer reports meaningful.

Use packed token streams. Each document is encoded, followed by EOS, then concatenated. Training samples fixed-length contiguous windows, which uses context efficiently and avoids padding waste.

Use `uint16` shard storage for 8K and 16K vocabularies. This cuts disk and memory bandwidth in half compared with `int32` while safely covering vocab sizes below 65,536.

Optimize for T4 stability. The loop uses FP16 autocast with GradScaler, gradient accumulation, token-count stopping, periodic checkpoints, and resume metadata. It avoids memory-expensive features unless explicitly enabled.

Use strong small-model architecture defaults. RMSNorm, RoPE, SwiGLU, tied embeddings, and PyTorch scaled-dot-product attention are included because they improve stability and quality without turning the code into a research framework.

Use honest evaluation. Primary metrics are train loss, validation loss, perplexity, token throughput, gradient norm, peak memory, and fixed prompt generations. Qualitative samples are tracked at milestones, but not over-claimed.

## Configs

`matgpt_mini_8m.yaml`:

- Dataset: `roneneldan/TinyStories`
- Vocab: 8,192
- Layers: 6
- Width: 256
- Heads: 8
- FFN: 1,024
- Context: 256 by default, 512 allowed
- Peak LR: 5e-4
- FP16
- Initial run target: configurable, default smoke target kept small for local testing and overridden in Colab to 50M-100M tokens

`matgpt_tiny_46m.yaml`:

- Dataset: `BabyLM-community/BabyLM-2026-Strict`
- Vocab: 16,384
- Layers: 12
- Width: 512
- Heads: 8
- FFN: 2,048
- Context: 512
- Peak LR: 3e-4
- FP16
- Initial serious target: 100M tokens
- Optional 8-bit AdamW when bitsandbytes is installed

## Checkpoint Contract

Each full checkpoint stores:

- model weights
- optimizer state
- scheduler state
- gradient scaler state
- global step
- tokens processed
- best validation loss
- RNG states for Python, NumPy, CPU torch, and CUDA torch
- config snapshot
- tokenizer hash
- dataset manifest hash
- source commit hash if git is available
- latest validation metrics and sample generations

The framework keeps:

- `latest.pt`
- `best.pt`
- milestone checkpoints by token count
- optional model-only `safetensors` export

## Testing

Minimum automated tests:

- config loading and validation
- text normalization determinism
- tokenizer special-token and round-trip behavior using a tiny local corpus
- shard metadata and packed token loading
- model forward shape and finite loss
- causal mask behavior through a no-future-leak check
- checkpoint save/load equivalence
- resume-training state restoration
- tiny overfit step reduces loss on a fixed batch
- generation stops at EOS

Tests use synthetic local fixtures so they do not require downloading datasets.

## Risks

Dataset download APIs can change. Scripts should surface clear errors and write manifests with dataset revisions when available.

BabyLM dataset field names may differ from TinyStories. Dataset preparation must support configurable text fields and auto-detect common text columns.

Colab sessions are interruptible. Training must write checkpoints atomically and keep enough resume metadata to continue safely.

Small models can collapse with poor sampling or overly high learning rates. Configs include conservative defaults, gradient clipping, validation, and fixed samples to catch this early.

## Approval State

The user approved the full-framework direction on 2026-06-07 and emphasized that all decisions should optimize for the best possible results from the 8M and 46M T4 models, not toy examples.
