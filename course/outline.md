# Pretrain an LLM From Scratch: Theory, Code, and a Real Colab Run

## Audience

This course is for a beginner who can read a little Python but does not yet know how machine learning, text representation, or language models work.

## Prerequisites

- Run a Python file from a terminal.
- Read basic Python values, lists, function calls, and printed output.
- Bring curiosity; no machine-learning, tensor, token, or Transformer knowledge is assumed.

## Course Promise

By the end of the course, a learner will be able to explain, inspect, run, and evaluate this repository's complete small-language-model pretraining pipeline. Each idea begins with plain-language intuition, moves through a small example, and only then receives its technical name. Claims about the repository are tied to code, tests, commands, or observed artifacts.

## Production Rule

Videos are completed and reviewed one at a time. Video 1 is the only fully produced video in this foundation; Videos 2-64 remain outline entries until the preceding video has been taught, checked for beginner language, and approved.

Every completed video uses six teaching documents: `script.md`, `lesson.md`, `lab.md`, `quiz.md`, `answer-key.md`, and `evidence.md`. A video may also include runnable standard-library code such as `lab.py`.

## Module 1: Computers And Text

**Outcome:** Explain how human-readable text becomes consistent data that a program can use.

1. What Does It Mean for a Computer to Learn From Text?
2. How Computers Store Characters as Agreed Numbers
3. From a Sentence to a Learning Example

## Module 2: Unicode And Text Cleaning

**Outcome:** Recognize common text representations and make raw text consistent before later processing.

4. Unicode Code Points and UTF-8 Bytes
5. Why Visually Similar Text Needs Normalization
6. Spaces, Control Characters, and Practical Cleaning

## Module 3: Building A Trustworthy Corpus

**Outcome:** Build a traceable text collection and check what enters or leaves it.

7. Documents, Corpora, JSON, and JSONL
8. Data-Quality Filters and Rejection Reasons
9. Exact Deduplication and Benchmark Contamination
10. Stable Dataset Splits, Manifests, and Fingerprints

## Module 4: Tokens And BPE

**Outcome:** Explain how text is divided into reusable units with numeric identifiers.

11. Tokens and Token IDs
12. Why Byte-Level Tokenization Works
13. How BPE Learns Frequent Merges
14. Vocabulary Size and Special Tokens

## Module 5: Training A Robust Tokenizer

**Outcome:** Train and audit the repository's tokenizer across ordinary and unfamiliar text.

15. Training the Repository Tokenizer
16. Unicode Round Trips and the Complete Byte Alphabet
17. Tokenizer Reports, Compression, and Failure Tests

## Module 6: From Documents To Batches

**Outcome:** Trace prepared documents into stored sequences and learning batches.

18. EOS Tokens and Packed Document Streams
19. Binary Shards, Dtypes, and Metadata
20. Memory Mapping and Weighted Shard Sampling
21. Context Windows, Shifted Targets, and Batches

## Module 7: Tensors And Embeddings

**Outcome:** Read the shapes and learned number tables that carry data through the model.

22. Tensors and Shapes Without Fear
23. Turning Token IDs Into Embeddings
24. Why Tokens Need Position Information
25. Tracing Shapes Through the Model

## Module 8: Attention From First Principles

**Outcome:** Build the core attention calculation from small, inspectable operations.

26. Why Tokens Need to Look at Other Tokens
27. Queries, Keys, and Values
28. Dot Products, Scaling, and Attention Softmax
29. Causal Masks and Weighted Value Mixing

## Module 9: Multi-Head Attention And RoPE

**Outcome:** Explain how multiple attention views and rotated positions are combined.

30. Heads, Reshaping, Transposing, and Joining
31. RoPE Rotations and Relative Position Math
32. Attention Output Projection

## Module 10: The Transformer Block

**Outcome:** Trace information through one complete block and then through a stack.

33. Residual Connections
34. RMSNorm
35. MLPs, Activations, and SwiGLU Gates
36. One Complete Block and a Stack of Blocks

## Module 11: Predictions And Loss

**Outcome:** Turn model outputs into next-unit guesses and measure how wrong they are.

37. Logits and Next-Token Probabilities
38. Cross-Entropy Loss With Small Numbers
39. Validation Loss and Perplexity

## Module 12: Learning Through Gradients

**Outcome:** Explain how measured error leads to controlled updates of the model's internal numbers.

40. Computation Graphs, Gradients, and the Chain Rule
41. SGD and Learning Rate
42. Momentum, Adam, and AdamW
43. Weight Decay and Optimizer Parameter Groups
44. Warmup, Cosine Decay, and Gradient Accumulation

## Module 13: Numerical Stability

**Outcome:** Recognize number-range failures and the safeguards used during training.

45. FP32, FP16, and BF16
46. Autocast and Gradient Scaling
47. Gradient Clipping, Underflow, Overflow, Inf, and NaN
48. Skipped Updates and Stability Metrics

## Module 14: Checkpoints And Reproducibility

**Outcome:** Save enough state to continue a run safely and explain its limits.

49. What a Complete Checkpoint Saves
50. Seeds, RNG State, and Reproducibility
51. Safe Resume and Artifact Compatibility

## Module 15: Google Colab T4 Preparation

**Outcome:** Prepare a persistent, checked Colab environment before spending training time.

52. Setting Up Colab, CUDA, and Persistent Drive Storage
53. Estimating Memory and Benchmarking the Batch
54. Running the Preflight and Reading Its Report

## Module 16: The Real Training Run

**Outcome:** Run the verified smoke, pilot, review, and full-training gates in order.

55. The Twenty-Step Smoke Test
56. The Ten-Million-Token Pilot and Go/No-Go Review
57. Continuing to 200M Tokens and Surviving Disconnects

## Module 17: Evaluation And Debugging

**Outcome:** Judge a run with several forms of evidence and diagnose common failures.

58. Evaluating Loss, Perplexity, and Fixed Prompts
59. Reading Samples Without Fooling Yourself
60. Debugging Loss, NaNs, OOM, Repetition, and Resume Failures

## Module 18: Scaling The Experiment

**Outcome:** Reason about larger experiments without losing the safeguards learned earlier.

61. Scaling Width, Depth, Data, Context, and Compute
62. Designing the 59M-Parameter Experiment

## Module 19: Teaching Capstone

**Outcome:** Turn verified technical work into a clear, evidence-backed lesson of your own.

63. Explaining Technical Ideas Without Hidden Jargon
64. Building and Teaching Your Own LLM Pretraining Course
