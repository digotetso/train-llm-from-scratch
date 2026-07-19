# T4 Base Training Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full-quality T4 base-pretraining framework for MatGPT-Mini 8M on TinyStories and MatGPT-Tiny 59M on BabyLM-2026-Strict.

**Architecture:** Create an importable `matgpt` package with focused modules for config, data preparation, tokenization, sharding, model definition, training, checkpoints, generation, and evaluation. CLI scripts stay thin and delegate to package functions. Tests use local synthetic fixtures so core behavior is verifiable without internet access.

**Tech Stack:** Python 3.10+, PyTorch, Hugging Face `datasets`, Hugging Face `tokenizers`, PyYAML, NumPy, safetensors, pytest, optional bitsandbytes on Colab.

---

### Task 1: Project Scaffold and Configs

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `configs/matgpt_mini_8m.yaml`
- Create: `configs/matgpt_tiny_59m.yaml`
- Create: `matgpt/__init__.py`
- Create: package subdirectory `__init__.py` files

- [ ] Create dependency metadata with runtime and test dependencies.
- [ ] Add model and training configs matching the approved design.
- [ ] Add a concise README with the 8M and 59M command sequence.
- [ ] Verify config files load as YAML.

### Task 2: Config and Utility Modules

**Files:**
- Create: `matgpt/config.py`
- Create: `matgpt/utils/seed.py`
- Create: `matgpt/utils/hashing.py`
- Create: `matgpt/utils/logging.py`
- Create: `tests/test_config.py`

- [ ] Write tests for config loading and validation.
- [ ] Implement dataclass-backed config loading from YAML.
- [ ] Implement deterministic seeding and SHA-256 helpers.
- [ ] Run config tests.

### Task 3: Data Preparation

**Files:**
- Create: `matgpt/data/normalize.py`
- Create: `matgpt/data/prepare.py`
- Create: `scripts/prepare_dataset.py`
- Create: `tests/test_data.py`

- [ ] Write tests for normalization determinism and document records.
- [ ] Implement Unicode NFKC normalization, line ending cleanup, control-character removal, and blank-line collapse.
- [ ] Implement Hugging Face dataset loading, text field detection, official split preservation, JSONL writing, and manifest writing.
- [ ] Add CLI wrapper.
- [ ] Run data tests.

### Task 4: Tokenizer Training and Validation

**Files:**
- Create: `matgpt/tokenizer/train.py`
- Create: `matgpt/tokenizer/io.py`
- Create: `scripts/train_tokenizer.py`
- Create: `tests/test_tokenizer.py`

- [ ] Write tests using a tiny local training corpus.
- [ ] Implement byte-level BPE tokenizer training with reserved control tokens.
- [ ] Save `tokenizer.json`, `special_tokens.json`, and `tokenizer_report.json`.
- [ ] Validate encode-decode round trip and special-token IDs.
- [ ] Add CLI wrapper.
- [ ] Run tokenizer tests.

### Task 5: Tokenization and Sharding

**Files:**
- Create: `matgpt/data/shard.py`
- Create: `scripts/tokenize_and_shard.py`
- Create: `tests/test_shards.py`

- [ ] Write tests for packed EOS streams, `uint16` shards, metadata, and deterministic shard hashes.
- [ ] Implement JSONL-to-token shard conversion using the trained tokenizer.
- [ ] Write split-level shard files and `metadata.json`.
- [ ] Add CLI wrapper.
- [ ] Run shard tests.

### Task 6: Transformer Model

**Files:**
- Create: `matgpt/model/gpt.py`
- Create: `matgpt/model/generation.py`
- Create: `tests/test_model.py`

- [ ] Write tests for forward shape, finite loss, generation stopping, and approximate parameter count.
- [ ] Implement RMSNorm, RoPE, causal self-attention using PyTorch SDPA, SwiGLU MLP, tied embeddings, and GPT forward loss.
- [ ] Implement top-k/top-p/temperature generation.
- [ ] Run model tests.

### Task 7: Training Dataset, Optimizer, and Checkpoints

**Files:**
- Create: `matgpt/training/dataset.py`
- Create: `matgpt/training/optim.py`
- Create: `matgpt/training/checkpoint.py`
- Create: `tests/test_training_core.py`

- [ ] Write tests for packed-shard batch sampling, checkpoint round trip, and resume metadata.
- [ ] Implement memmap-backed random window sampling.
- [ ] Implement AdamW parameter grouping and optional bitsandbytes optimizer selection.
- [ ] Implement atomic full checkpoint save/load with RNG state capture.
- [ ] Run training-core tests.

### Task 8: Pretraining and Evaluation

**Files:**
- Create: `matgpt/training/pretrain.py`
- Create: `matgpt/eval/lm.py`
- Create: `scripts/pretrain.py`
- Create: `scripts/evaluate.py`
- Create: `scripts/chat.py`
- Create: `tests/test_pretrain_smoke.py`

- [ ] Write a tiny overfit smoke test proving loss decreases on a fixed synthetic shard.
- [ ] Implement token-count driven pretraining loop with FP16 AMP, GradScaler, gradient accumulation, warmup/cosine LR, clipping, validation, metrics CSV, samples, and checkpointing.
- [ ] Implement validation loss, perplexity, and prompt sample evaluation.
- [ ] Add CLI wrappers.
- [ ] Run smoke and full test suite.

### Task 9: Verification and Handoff

**Files:**
- Modify: `README.md`

- [ ] Run `pytest`.
- [ ] Run any import/config smoke commands possible without network.
- [ ] Document Colab command sequence for 8M and 59M.
- [ ] Report any commands that could not run locally because datasets require network access.

## Self-Review

Spec coverage: The plan covers repository scaffold, configs, data prep, tokenizer training, sharding, model, pretraining, evaluation, checkpointing, and tests.

Placeholder scan: No implementation placeholder is intentionally left in the plan. Post-training stages are explicitly out of scope for this first base-pretraining pass.

Type consistency: The plan consistently uses YAML configs, JSONL normalized documents, `uint16` shards, `metadata.json`, and PyTorch checkpoint dictionaries.
