# Integrated LLM Pretraining And Course Design

Date: 2026-07-19

Status: Approved design, awaiting written-spec review

## 1. Purpose

This project will make the repository ready for a first real Google Colab T4 pretraining run while turning the verified engineering work into a beginner-first course.

The work has three connected outcomes:

1. Harden the repository so expensive training does not begin with known correctness or observability gaps.
2. Run the 8.39M-parameter TinyStories model through a 20-step smoke test, an approximately 10M-token pilot, and then a 200M-token run only when the evidence passes each gate.
3. Build a complete course outline and produce one verified 10-15 minute video package at a time.

The intended learner starts with no assumed knowledge of machine learning, tensors, tokens, or Transformers. Technical terms appear only after plain-language intuition and a small example.

## 2. Sources Of Truth

The repository remains the primary teaching and execution reference.

- Configuration: `configs/matgpt_mini_8m.yaml`
- Dataset preparation: `matgpt/data/`
- Tokenizer training: `matgpt/tokenizer/`
- Model implementation: `matgpt/model/`
- Training runtime: `matgpt/training/`
- Evaluation: `matgpt/eval/`
- Colab workflow: `notebooks/train_matgpt_t4_base_colab.ipynb`
- Verified tests: `tests/`
- Learning progress: `docs/llm_training_progress.md`
- Run evidence: the immutable configuration snapshot, fingerprints, metrics, checkpoints, samples, and evaluation outputs for a specific run

Course material must describe verified code and observed run behavior. It must not present an expected result as an observed result.

## 3. Verified Starting Point

The 2026-07-19 local audit established the following baseline:

- `uv run pytest` passes 33 tests.
- The Mini configuration defines an 8,391,936-parameter model.
- No prepared TinyStories JSONL, production tokenizer, token shards, or real training outputs are present locally.
- The tokenizer trainer does not provide the complete byte alphabet to `BpeTrainer`.
- A tiny-corpus reproduction showed that an unseen emoji can encode to an empty ID list and decode to an empty string.
- `--max-steps` currently shortens the learning-rate schedule horizon as well as stopping the invocation.
- Training metrics do not record the current FP16 gradient scale or whether an optimizer update was skipped.
- The local machine has no CUDA device, so CUDA behavior must be exercised on the Colab T4.
- The worktree contains existing user changes. Implementation must preserve them and commit only intentional files.

## 4. Goals And Acceptance Criteria

### 4.1 Repository Readiness

Repository readiness is achieved when:

- Byte-level BPE has all 256 byte symbols available before learned merges.
- Non-empty representative Unicode text, including unseen emoji, survives encode-decode round trips.
- Tokenizer configuration rejects a vocabulary too small for the byte alphabet and unique special tokens.
- A step cap stops an invocation without changing the configured full-run learning-rate schedule.
- The learning-rate sequence is equivalent across uninterrupted and resumed execution at the same global steps.
- FP16 metrics expose gradient scale, per-step skipped-update status, and cumulative skipped-update count.
- Non-finite loss aborts before a parameter update or checkpoint save.
- Repeated skipped updates produce a clear failure rather than silently consuming the run budget.
- A Colab preflight validates the environment and required artifacts before training.
- The real-run configuration pins TinyStories to an immutable source revision.
- Existing and new tests pass.

### 4.2 First Real Run

The first run is successful when:

- The same run progresses through smoke, pilot, and full gates without restarting the learning-rate schedule.
- Checkpoint resume restores model, optimizer, scaler, counters, Python/NumPy/PyTorch RNG, and separate training/validation dataset RNG states.
- Metrics remain finite and show sustained learning rather than only one favorable batch.
- Validation loss improves relative to the initial evaluation.
- Checkpoints, samples, evaluation outputs, and run metadata persist in Google Drive.
- Both `latest.pt` and `best.pt` load successfully at the end.

### 4.3 Course Production

Course readiness is achieved when:

- `course/outline.md` contains the complete ordered 64-video curriculum.
- A reusable video template defines the required teaching and evidence sections.
- Video 1 is complete, runnable, and beginner-reviewed before Video 2 begins.
- Every referenced command and expected output is verified where feasible.
- Every code explanation links to the relevant repository file and explains the block rather than only naming a line.

## 5. Non-Goals

This phase will not:

- Start with the 59M model.
- Add distributed or multi-GPU training.
- Replace the repository's PyTorch Transformer with a framework model.
- Build a hosted learning platform or marketing website.
- Produce all 64 videos before reviewing the first one.
- Automatically promote a pilot to the full run.
- Claim exact determinism on CUDA hardware.
- Treat readable samples alone as proof that training is healthy.

## 6. Chosen Delivery Architecture

The chosen approach is an integrated lab-to-course pipeline.

### 6.1 Track A: Repository Engineering

Each behavior change follows test-driven development:

1. Add a focused test that fails for the intended reason.
2. Implement the smallest compatible change.
3. Run the focused test.
4. Run the broader suite.
5. Record the verified behavior for the corresponding course lesson.

### 6.2 Track B: Stage-Gated Colab Training

Training is promoted through explicit gates:

1. Repository readiness
2. Dataset preparation
3. Tokenizer training and audit
4. Shard creation and audit
5. T4 batch benchmark
6. Twenty-step smoke test
7. Approximately 10M-token pilot
8. Human go/no-go review
9. Full 200M-token continuation
10. Final evaluation and resume verification

### 6.3 Track C: Course Production

Every verified gate produces reusable teaching evidence:

- a simple explanation and analogy
- the correct technical term
- practical math with small numbers
- commented repository code
- a live mini-lab
- expected output
- a common failure and debugging path
- beginner questions
- an exercise and instructor answer key

## 7. Data And Evidence Flow

The execution flow is:

```text
TinyStories source
  -> normalized and filtered JSONL + dataset manifest
  -> trained byte-level BPE tokenizer + tokenizer report
  -> packed binary train/validation shards + shard metadata
  -> sampled token windows
  -> shifted x and y tensors
  -> model logits and loss
  -> gradients and optimizer updates
  -> metrics, checkpoints, samples, and evaluations
  -> evidence-backed course lessons
```

Each transformation must have a machine-readable artifact or test. Course claims link back to those artifacts.

## 8. Repository Hardening Design

### 8.1 Complete Byte-Alphabet Tokenizer

`matgpt/tokenizer/train.py` will pass `pre_tokenizers.ByteLevel.alphabet()` as the `initial_alphabet` for `BpeTrainer`.

Before training, configuration validation will require:

```text
requested vocabulary >= 256 byte symbols + number of unique special tokens
```

For the current seven unique special tokens, the minimum is 263 entries. The real configuration requests 8,192.

Tests will cover:

- unseen emoji
- accented text
- non-Latin text
- spaces and punctuation
- special-token availability
- rejection of an undersized vocabulary
- no empty ID list for representative non-empty Unicode input

The real-data tokenizer gate additionally requires an actual vocabulary size of 8,192. If the corpus cannot produce that vocabulary, the gate fails and the configuration is reviewed rather than silently changing the model vocabulary.

### 8.2 Schedule Horizon And Invocation Stop

The training loop will use two distinct values:

- `schedule_total_steps`: derived only from configured `max_tokens`
- `invocation_stop_step`: the earlier of the full schedule end and the current global step plus `--max-steps`

Warmup and cosine decay always use `schedule_total_steps`. `--max-steps N` means at most `N` additional optimizer steps in the current invocation. It does not rewrite the planned experiment.

Tests will compare learning rates at identical global steps for:

- an uninterrupted run
- a 20-step invocation followed by resume
- a smoke-to-pilot-to-full sequence

### 8.3 AMP And Stability Observability

Every logged training row will include:

- `grad_scale`
- `optimizer_step_skipped`
- `optimizer_steps_skipped_total`
- `consecutive_optimizer_steps_skipped`

Skipped updates will be detected through a public optimizer step hook: if `GradScaler.step()` does not invoke the optimizer step, the update was skipped. The design will not depend on private GradScaler fields.

The loop will abort immediately when a micro-batch loss or accumulated step loss is not finite. It will abort after five consecutive skipped optimizer updates. The error will include the global step, loss, gradient norm when available, learning rate, and gradient scale.

### 8.4 Colab T4 Preflight

A preflight command will validate:

- Python, PyTorch, CUDA, and tokenizer-library versions
- CUDA availability and GPU name
- GPU memory capacity and current free memory
- configured precision compatibility
- configuration validity
- a non-null, immutable TinyStories source revision for the real run
- prepared dataset manifest and hash
- tokenizer files, hash, special tokens, and vocabulary size
- train and validation shard metadata
- shard file existence, size, dtype, token totals, and token-ID bounds
- writable output directory
- available persistent disk space
- model parameter count and derived training-step math

The command will produce a readable summary and a machine-readable report. Missing required artifacts fail closed with an actionable message.

### 8.5 Run Artifacts

Each run preserves:

```text
runs/<run-name>/
  config.snapshot.yaml
  environment.json
  fingerprints.json
  preflight.json
  metrics.csv
  checkpoints/
  samples/
  evaluation/
  run_summary.md
```

On Colab, this directory lives in or is synchronized to Google Drive. The notebook must display the final persistent path before training begins.

## 9. T4 Run Design

The current Mini configuration gives:

```text
micro_batch_size              = 16
gradient_accumulation_steps   = 8
context_length                = 256
effective examples per step   = 16 * 8 = 128
tokens per optimizer step     = 16 * 8 * 256 = 32,768
full token target             = 200,000,000
full schedule steps           = ceil(200,000,000 / 32,768) = 6,104
actual tokens at step 6,104   = 200,015,872
warmup steps                  = floor(6,104 * 0.02) = 122
pilot stop step               = 306
actual tokens at step 306     = 10,027,008
```

### Gate 0: Repository Readiness

Pass criteria:

- all local tests pass
- model report returns 8,391,936 trainable parameters
- tokenizer, scheduling, metrics, checkpoint, and preflight tests pass
- the full 200M-token schedule remains 6,104 steps under a smoke cap

### Gate 1: Dataset Preparation

Pass criteria:

- train and validation JSONL files are non-empty
- manifest and split statistics exist
- accepted and rejected document counts reconcile
- exact train/validation overlap is absent
- the immutable dataset source revision and resulting fingerprint are recorded
- persistent disk has enough free space for downstream artifacts

### Gate 2: Tokenizer

Pass criteria:

- full byte alphabet and all special tokens are present
- actual vocabulary size is 8,192
- representative Unicode round trips pass
- non-empty representative text never becomes an empty encoding
- tokenizer hash and compression report are recorded

### Gate 3: Token Shards

Pass criteria:

- train and validation metadata exist
- metadata totals reconcile with shard sizes and dtype
- all token IDs are below 8,192
- EOS counts reconcile with processed document counts
- each split contains enough tokens to sample a complete window

### Gate 4: T4 Batch Benchmark

Pass criteria:

- forward and backward produce finite loss and gradient norm
- peak allocated memory stays below 90% of T4 capacity
- the selected batch leaves enough headroom for evaluation and checkpointing
- tokens-per-second and peak-memory measurements are recorded

If batch 16 fails, reduce the micro-batch size and increase accumulation to preserve the effective batch where practical. Any change creates a new configuration snapshot and updated run math.

### Gate 5: Twenty-Step Smoke Test

Pass criteria:

- a finite step-zero validation loss is recorded before the first parameter update
- steps 0-19 use the first 20 learning rates of the full 6,104-step schedule
- loss, gradient norm, and gradient scale are finite
- skipped-update metrics are present
- `latest.pt` loads and evaluates
- sample generation decodes successfully
- a five-step resume continues counters, RNG, and schedule correctly
- artifact mismatch protection remains active

### Gate 6: Approximately 10M-Token Pilot

Resume the same run to global step 306.

Pass criteria:

- no non-finite metrics
- no five consecutive skipped updates
- the median of the final 20% of logged training-loss rows is lower than the median of the first 20%, with at least five rows in each window
- later validation loss is lower than the first pilot validation loss
- the final 20% median throughput is at least 80% of the first 20% median throughput
- peak allocated GPU memory remains below 90% of capacity and does not grow monotonically across all logged windows
- samples decode and show increasing local structure, without using prose quality as the only gate
- the latest checkpoint survives a load-and-resume check

### Gate 7: Human Go/No-Go Review

The user and Codex inspect the actual pilot metrics, samples, evaluation, throughput, memory, and checkpoint evidence. Full training starts only after explicit approval.

### Gate 8: Full 200M-Token Continuation

Resume the same checkpoint and schedule through step 6,104. Preserve `latest.pt`, `best.pt`, and configured milestones. Stop for non-finite loss, five consecutive skipped updates, artifact incompatibility, unreadable checkpoints, or persistent storage failure.

### Gate 9: Final Evaluation

Pass criteria:

- `latest.pt` and `best.pt` both load
- final validation loss and perplexity are finite
- the best checkpoint improves on the initial baseline
- fixed prompts generate decodable samples
- resume verification succeeds
- `run_summary.md` records configuration identity, dataset/tokenizer fingerprints, best metrics, final metrics, runtime, throughput, peak memory, and known limitations

## 10. Course Design

Course title: **Pretrain an LLM From Scratch: Theory, Code, and a Real Colab Run**

The course contains 64 videos grouped into 19 modules.

### Module 1: Computers And Text

1. What Does It Mean for a Computer to Learn From Text?
2. How Computers Store Characters as Agreed Numbers
3. From a Sentence to a Learning Example

### Module 2: Unicode And Text Cleaning

4. Unicode Code Points and UTF-8 Bytes
5. Why Visually Similar Text Needs Normalization
6. Spaces, Control Characters, and Practical Cleaning

### Module 3: Building A Trustworthy Corpus

7. Documents, Corpora, JSON, and JSONL
8. Data-Quality Filters and Rejection Reasons
9. Exact Deduplication and Benchmark Contamination
10. Stable Dataset Splits, Manifests, and Fingerprints

### Module 4: Tokens And BPE

11. Tokens and Token IDs
12. Why Byte-Level Tokenization Works
13. How BPE Learns Frequent Merges
14. Vocabulary Size and Special Tokens

### Module 5: Training A Robust Tokenizer

15. Training the Repository Tokenizer
16. Unicode Round Trips and the Complete Byte Alphabet
17. Tokenizer Reports, Compression, and Failure Tests

### Module 6: From Documents To Batches

18. EOS Tokens and Packed Document Streams
19. Binary Shards, Dtypes, and Metadata
20. Memory Mapping and Weighted Shard Sampling
21. Context Windows, Shifted Targets, and Batches

### Module 7: Tensors And Embeddings

22. Tensors and Shapes Without Fear
23. Turning Token IDs Into Embeddings
24. Why Tokens Need Position Information
25. Tracing Shapes Through the Model

### Module 8: Attention From First Principles

26. Why Tokens Need to Look at Other Tokens
27. Queries, Keys, and Values
28. Dot Products, Scaling, and Attention Softmax
29. Causal Masks and Weighted Value Mixing

### Module 9: Multi-Head Attention And RoPE

30. Heads, Reshaping, Transposing, and Joining
31. RoPE Rotations and Relative Position Math
32. Attention Output Projection

### Module 10: The Transformer Block

33. Residual Connections
34. RMSNorm
35. MLPs, Activations, and SwiGLU Gates
36. One Complete Block and a Stack of Blocks

### Module 11: Predictions And Loss

37. Logits and Next-Token Probabilities
38. Cross-Entropy Loss With Small Numbers
39. Validation Loss and Perplexity

### Module 12: Learning Through Gradients

40. Computation Graphs, Gradients, and the Chain Rule
41. SGD and Learning Rate
42. Momentum, Adam, and AdamW
43. Weight Decay and Optimizer Parameter Groups
44. Warmup, Cosine Decay, and Gradient Accumulation

### Module 13: Numerical Stability

45. FP32, FP16, and BF16
46. Autocast and Gradient Scaling
47. Gradient Clipping, Underflow, Overflow, Inf, and NaN
48. Skipped Updates and Stability Metrics

### Module 14: Checkpoints And Reproducibility

49. What a Complete Checkpoint Saves
50. Seeds, RNG State, and Reproducibility
51. Safe Resume and Artifact Compatibility

### Module 15: Google Colab T4 Preparation

52. Setting Up Colab, CUDA, and Persistent Drive Storage
53. Estimating Memory and Benchmarking the Batch
54. Running the Preflight and Reading Its Report

### Module 16: The Real Training Run

55. The Twenty-Step Smoke Test
56. The Ten-Million-Token Pilot and Go/No-Go Review
57. Continuing to 200M Tokens and Surviving Disconnects

### Module 17: Evaluation And Debugging

58. Evaluating Loss, Perplexity, and Fixed Prompts
59. Reading Samples Without Fooling Yourself
60. Debugging Loss, NaNs, OOM, Repetition, and Resume Failures

### Module 18: Scaling The Experiment

61. Scaling Width, Depth, Data, Context, and Compute
62. Designing the 59M-Parameter Experiment

### Module 19: Teaching Capstone

63. Explaining Technical Ideas Without Hidden Jargon
64. Building and Teaching Your Own LLM Pretraining Course

## 11. Per-Video Artifact Contract

Course files use this structure:

```text
course/
  outline.md
  glossary.md
  templates/video/
  videos/001-computer-learning-from-text/
    script.md
    lesson.md
    lab.md
    quiz.md
    answer-key.md
    evidence.md
```

Each video lasts 10-15 minutes and follows this pacing:

```text
00:00  Beginner-friendly hook
00:45  Real-world analogy
02:00  Technical term and intuition
04:00  Small-number or small-text example
06:00  Slowly annotated repository code
09:00  Live mini-lab
12:00  Common mistake and debugging path
13:00  Recap, questions, and exercise
```

Required content:

- one small primary concept
- prerequisites and learning objective
- plain-language explanation before terminology
- analogy with its limitations stated when necessary
- math using concrete values
- repository code with explanatory comments
- runnable lab and expected output
- quiz and separate instructor answer key
- evidence links to tests, commands, artifacts, or observed run output
- no unexplained technical term

The complete outline and template are created first. Video 1 is then completed and reviewed before work begins on Video 2. This one-at-a-time review loop continues for the course.

## 12. Testing Strategy

Tests use the cheapest reliable layer.

### Unit Tests

- tokenizer minimum vocabulary and Unicode behavior
- schedule and stop-step calculations
- learning-rate values at selected global steps
- finite-value and skipped-update accounting
- configuration and artifact compatibility validation
- preflight validation functions with controlled fixtures

### Integration Tests

- tokenizer save/load and round trip
- shard metadata against real temporary binary files
- checkpoint save/load with optimizer, scaler, counters, and RNG
- interrupted-versus-resumed learning-rate equivalence
- metrics CSV fields
- evaluation and generation from a smoke checkpoint

### Runtime Tests

- local CPU smoke tests for wiring
- Colab T4 benchmark for CUDA memory and AMP behavior
- 20-step end-to-end smoke run
- 10M-token pilot acceptance review
- final checkpoint load and evaluation

Tests must control randomness and use temporary files. CUDA-only behavior may be skipped locally but must be observed on the T4 before the pilot gate passes.

## 13. Error Handling And Recovery

The pipeline fails closed before expensive work when configuration, hashes, vocabulary, shard metadata, token ranges, disk, CUDA, or checkpoint compatibility are invalid.

Failures must report:

- what failed
- the expected value
- the observed value
- the artifact or step involved
- the safest next action

Training interruptions are recoverable through `latest.pt`. A corrupted or incompatible checkpoint is never silently accepted. `allow_artifact_mismatch` remains an explicit expert escape hatch and is not used in the first real run.

No gate deletes earlier artifacts. Rollback means loading the last verified checkpoint and configuration snapshot, not mutating or replacing evidence from the failed attempt.

## 14. Colab Execution Boundary

Codex will implement and verify CPU-testable behavior locally. The user will execute the Colab cells on the assigned T4. The user and Codex will inspect outputs after each gate.

A T4 gate is not marked complete until its actual report or artifact has been inspected. Notebook instructions will explain each command before it runs and identify the expected output, but expected output remains explicitly labeled until observed.

## 15. Risks And Controls

| Risk | Control |
|---|---|
| Unseen text disappears during tokenization | Complete byte alphabet and Unicode round-trip tests |
| Smoke run changes the intended schedule | Separate schedule horizon from invocation stop |
| Colab disconnect loses work | Persistent Drive run directory and frequent `latest.pt` |
| FP16 silently skips updates | Scale and skipped-update metrics with consecutive-skip abort |
| T4 runs out of memory | Benchmark gate and preserved effective batch when adjusting micro-batch size |
| Incompatible resume corrupts the experiment | Config, tokenizer, and dataset fingerprints |
| Good-looking sample hides poor learning | Validation loss, perplexity, fixed prompts, and metric review |
| Course teaches unverified behavior | Per-video evidence contract |
| Existing user edits are lost | Narrow patches and intentional file-only commits |

## 16. Delivery Sequence

1. Add failing tokenizer robustness tests and implement full byte coverage.
2. Add failing schedule tests and separate schedule horizon from invocation stop.
3. Add failing AMP observability tests and implement skipped-update metrics and stability stops.
4. Build and test the Colab preflight.
5. Update configuration validation, notebook, README, and runbook.
6. Create the complete course outline and reusable template.
7. Produce and review Video 1.
8. Run local verification and Gate 0.
9. Guide the user through Colab Gates 1-5.
10. Review the 20-step evidence and resume to the pilot.
11. Review pilot evidence and make the explicit full-run decision.
12. Complete final evaluation and the evidence-backed training videos.

## 17. Final Definition Of Done

This integrated phase is complete when:

- all repository-readiness acceptance criteria pass
- the Colab T4 run reaches its approved stopping point with preserved artifacts
- the run can be resumed and evaluated from its saved checkpoint
- the complete 64-video outline and template exist
- Video 1 is a finished, reviewed teaching package
- the progress document accurately records completed work and the next lesson or lab
