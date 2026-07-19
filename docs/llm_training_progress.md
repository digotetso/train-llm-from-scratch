# LLM Training Course Progress

Updated: 2026-07-19

This document tracks the beginner-to-advanced path for understanding this repository well enough to pretrain an LLM from scratch, debug it, evaluate it, and teach the material to others.

Primary repository: `train-llm-from-scratch`

## Current Status

- Theory completed through Lesson 100, including positional encoding and RoPE rotation lessons before the build-first transition.
- Numerical-stability theory completed: gradient clipping, underflow and overflow, `Inf`/`NaN`, BF16, skipped updates, and stability metrics.
- Current phase: repository hardening and the first real 8M TinyStories T4 run.
- Tasks 1-8 are completed through commit `eedb862`: byte-alphabet tokenizer coverage, schedule preservation, training observability and stability stops, artifact preflight, evaluation and summary artifacts, stage-gated Colab operations, and the course foundation through Video 1.
- Controller verification immediately before Task 9 observed 153 passing local tests. Task 9 does not rerun that suite because these edits do not change a tested README or course contract.
- Real Colab data preparation: not started. No TinyStories or BabyLM prepared artifacts have been inspected.
- Real T4 training: not started. Smoke, pilot, full training, runtime evaluation, and runtime summaries remain unobserved.
- Course production is build-first and one video at a time. Video 1 is complete; later videos remain outline entries until their predecessor is taught, checked, and approved.

No percentage is used. Local tests establish local behavior only; they do not establish T4 allocation, prepared-artifact integrity, benchmark results, or training quality.

## Canonical References

- [Approved integrated design](superpowers/specs/2026-07-19-integrated-training-course-design.md)
- [Implementation plan](superpowers/plans/2026-07-19-integrated-training-course-readiness.md)
- [Colab T4 first-run runbook](runbooks/colab-t4-first-run.md)
- [64-video course outline](../course/outline.md)
- [Video 1 lesson package](../course/videos/001-computer-learning-from-text/lesson.md)

## First Real 8M Run: Operator Gate

**Prerequisites:** select an NVIDIA T4 runtime in the [Colab notebook](../notebooks/train_matgpt_t4_base_colab.ipynb), mount writable Drive storage, provide the required dataset access, and keep one unchanged Mini config and run lineage. The Mini config pins `roneneldan/TinyStories` to `f54c09fd23315a6f9c86f9dc80f725de7d8f9c64`; the tokenizer is configured and tested for complete byte coverage.

**Prepare and collect gate evidence:** set `RUN_STAGE = "prepare"` on a T4 and run the notebook. It prepares normalized JSONL, trains the tokenizer, creates shards, validates their snapshots, and then runs:

```bash
python scripts/preflight_t4.py \
  --config "$CONFIG" \
  --require-t4 \
  --min-free-disk-gb 20

python scripts/benchmark_t4.py \
  --config "$CONFIG" \
  --batch-sizes 8,16,24,32 \
  --steps 5
```

Expected evidence is a passing `run/preflight.json`, finite configured-batch fields in `run/benchmark.json`, and the prepared manifest, tokenizer, and shard metadata. The benchmark uses a temporary model but the `prepare` stage does not run pretraining or create a checkpoint. Stop and review both reports before selecting `smoke`; do not start smoke if preparation is incomplete, preflight fails, the benchmark has a non-finite value or non-positive throughput, or the T4/storage gate fails. See the runbook for the complete gate criteria and recovery rules.

**Training sequence:** `smoke` performs 20 successful updates followed by a five-update resume check. `--max-steps` limits the current invocation and preserves the configured full learning-rate schedule. `pilot` stops at global step 306. Run `evaluate` and review the persisted evidence; only explicit user and Codex approval permits manually selecting `full`.

**Outputs:** `scripts/evaluate.py` writes an evaluation JSON artifact, and `scripts/summarize_run.py` writes `run_summary.md`. Stop and preserve evidence for any non-finite training or validation value, repeated skipped updates, incompatible artifacts, unexpected checkpoint lineage, missing required evidence, or a failed pilot review.

## Historical Answer Review

Lesson 92: Gradient Scaling. This retained review records an earlier learning checkpoint; it is not the current course boundary.

- Correctly explained that gradient scaling protects tiny gradients during FP16 calculations.
- Correctly explained underflow as a value becoming zero because it is too small for the numerical format.
- Correctly calculated `0.000002 * 1,000 = 0.002` and unscaled it back to `0.000002`.
- Correctly ordered the operations: scaled backward, unscale, clip, optimizer step, scaler update.
- Completed correction: the repo enables `GradScaler` only when the device is CUDA and the configured precision is FP16.

## Completed Topics

### Lessons 1-12: Text, Tokens, And Tensors

- What it means for a computer to learn from text
- Characters, Unicode code points, and normalization
- Tokens and token IDs
- EOS and ordered token sequences
- Next-token prediction with shifted `x` and `y`
- Context length, batches, shapes, and tensors
- Embedding lookup and embedding output shape

### Lessons 13-33: Transformer Foundations

- Layers and repeated Transformer blocks
- Attention intuition and causal attention
- Attention scores, weights, and weighted sums
- Queries, keys, and values
- Multiple attention heads and `head_dim`
- Reshape, transpose, separated heads, and concatenation
- Attention output projection
- Residual connections and RMSNorm
- Per-token MLP processing, `d_ff`, activations, and gates
- Shape preservation through one block and many blocks

### Lessons 34-50: Predictions And Training Mechanics

- Logits, softmax, and next-token probabilities
- Loss and negative-log-probability intuition
- Parameters, gradients, `backward()`, and optimizer updates
- Learning rate, schedules, warmup, and decay
- The five parts of one training step
- Gradient accumulation and effective batch size
- Tokens per optimizer step and maximum training tokens
- Validation loss and overfitting

### Lessons 51-61: Evaluation, Checkpoints, And Reproducibility

- Perplexity and generated samples
- `latest.pt` versus `best.pt`
- Resume training and restored optimizer state
- Random dataset sampling, seeds, and RNG state
- Separate training and validation RNG states
- Reproducibility versus exact determinism
- Checkpoint compatibility and config, tokenizer, and dataset fingerprints

### Lessons 62-84: Complete Data Pipeline

- Documents, corpora, JSON, and JSONL
- Normalization, quality filtering, and minimum length
- Exact deduplication and benchmark contamination
- Stable hash-based training and validation splits
- Dataset manifests and split statistics
- BPE tokenizer training on training data only
- Bytes, byte-level BPE, merge frequency, and vocabulary size
- Special tokens and EOS insertion
- Binary token shards, `uint16`, and `uint32`
- Memory mapping and weighted shard sampling
- Packed document streams and cross-document windows
- Shard metadata
- Characters per token and encode-decode round trips
- Complete 256-symbol byte alphabet requirements
- Full pipeline order: prepared JSONL, tokenizer, shards, then `x` and `y`

### Lessons 85-100: Starting And Running Training

- Smoke tests and `--max-steps`
- CPU, CUDA GPU, and PyTorch devices
- Training from scratch and weight initialization
- Symmetry breaking with small random weights
- Parameter counting and the repo's actual 8,391,936-parameter Mini model
- FP32 and FP16 numerical precision
- Automatic mixed precision and autocast boundaries
- FP16 underflow and gradient scaling
- Gradient clipping and gradient norm
- Overflow, `Inf`, `NaN`, unsafe skipped updates, and stability metrics
- BF16 compared with FP16 and FP32
- Why token order needs representation and how RoPE rotations encode it

## Build-First Transition

The next work is evidence-led implementation and training, not a claimed completed runtime. Remaining theory is learned just in time while inspecting the relevant code, operating the gates, and reviewing real artifacts. The [course outline](../course/outline.md) remains the canonical sequence for later lessons on checkpoints, Colab preparation, training, evaluation, debugging, scaling, and teaching.

The local implementation record includes complete byte-alphabet tokenizer coverage, a preserved full schedule under `--max-steps`, training stability metrics, artifact preflight, evaluation JSON, a Markdown run summary, the stage-gated notebook and runbook, and the course foundation through Video 1. Those are repository capabilities and local-test evidence, not proof that a real TinyStories or BabyLM run has happened.

## Mastery Milestones

The course is complete when the learner can independently:

1. Explain the text-to-loss-to-update path using plain language and math.
2. Derive the important tensor shapes through the Transformer.
3. Explain and calculate attention, loss, gradients, and optimizer updates.
4. Audit tokenizer, dataset, model, and training configuration compatibility.
5. Prepare data and verify tokenizer and shard integrity.
6. Run, monitor, stop, checkpoint, and resume a smoke pretraining job.
7. Evaluate a checkpoint quantitatively and qualitatively.
8. Diagnose common data, numerical, memory, and learning failures.
9. Design a realistic full pretraining experiment with resource limits.
10. Teach the complete journey to another beginner accurately.

## Learning Rules For Future Lessons

Each lesson must:

1. Start with the simplest possible explanation.
2. Use a real-world analogy.
3. Introduce the technical term only after the intuition is clear.
4. Show where the concept appears in the repository.
5. Explain the relevant code slowly, with comments.
6. Give a tiny example using simple numbers or text.
7. Ask beginner-friendly questions.
8. Give one small practical exercise.
9. Wait for the learner's answer and correct gaps before moving on.
