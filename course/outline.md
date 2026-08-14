# Pretrain an LLM From Scratch: Theory, Code, and a Real Colab Run

## Audience

This course is for a learner who can read a little Python but cannot yet explain how text becomes language-model training data or how a Transformer learns from it.

## Prerequisites

- Run a Python file from a terminal.
- Read Python strings, lists, slices, function calls, and printed output.
- Bring curiosity; no machine-learning, tensor, token, or Transformer knowledge is assumed.

## Course Promise

By the end of the course, a learner will be able to explain, inspect, run, and evaluate this repository's complete small-language-model pretraining pipeline. They will also produce a trained checkpoint on a Colab T4 or a comparable CUDA GPU, subject to the runtime and quota available to them.

Each concept begins with an observable question, moves through a hand-checkable example, and only then receives its technical name. Claims about this repository are tied to code, tests, commands, or observed artifacts.

## What the Learner Ships

- A trained model checkpoint and run summary.
- A tokenizer and a traceable sharded dataset.
- Evaluation results and generated samples.
- A model card explaining the model's data, intended use, limits, and known risks.

## Design Rules

**See the complete journey early.** Module 1 starts with one next-token training example, shows how token IDs enter the model, maps the full project, and runs a tiny end-to-end pipeline. Later modules open each part of that already-visible system.

**Preview first, then open the mechanism.** Lesson 2 shows the embedding lookup with simple lists of numbers. Modules 6 and 7 later explain tensors, parameters, training, and the deeper mathematics behind that first model step.

**Teach machinery when it becomes necessary.** Production corpus engineering appears when the learner's small in-memory path no longer scales.

**Earn vocabulary.** Observable behavior and a tiny example come before a new term. Later terminology may be named briefly as a boundary, but it cannot carry an explanation before its own lesson.

**Every module ends in something inspectable.** A learner predicts, runs, traces, measures, or produces an artifact in every module.

**Foundations before Transformers.** Learners meet parameters, linear layers, and a complete training step before embeddings and attention.

## Production Rule

Lessons are completed and reviewed one at a time. Lesson 1 is the current learner-facing package; Lessons 2–75 remain outline entries until the preceding lesson has been taught, checked for beginner language, and approved.

Every completed lesson uses six teaching documents: `script.md`, `lesson.md`, `lab.md`, `quiz.md`, `answer-key.md`, and `evidence.md`. It may also include runnable code.

The checked-in Manim and After Effects files under Lesson 1 were built for the superseded lesson. They are preserved as recovery artifacts, not as the production source for the new script. Rebuild them only after the new script is locked.

## Module 1: Orientation

**Outcome:** Build one training example, turn token IDs into the model's first numeric representation, see the complete project, and run its smallest end-to-end path.

1. From a Sentence to a Training Example
2. Turning Token IDs Into Embeddings
3. What You Will Build: The Model, Budget, and Training Roadmap
4. Run the Whole Pipeline Once Before Understanding It

## Module 2: Text Into Numbers

**Outcome:** Turn human-readable text into consistent data and defend every change made to it.

5. How Computers Store Characters as Agreed Numbers
6. Unicode Code Points and UTF-8 Bytes
7. Why Visually Similar Text Needs Normalization
8. Inspecting Real Text: Invisible Characters and Cleaning Decisions

## Module 3: Tokens and BPE

**Outcome:** Explain how text is divided into reusable units with numeric identifiers.

9. Tokens and Token IDs
10. Why Byte-Level Tokenization Works
11. How BPE Learns Frequent Merges
12. Vocabulary Size and Special Tokens

## Module 4: Training a Robust Tokenizer

**Outcome:** Train and audit the repository's tokenizer across ordinary and unfamiliar text.

13. Training the Repository Tokenizer
14. Unicode Round Trips and the Complete Byte Alphabet
15. Tokenizer Reports, Compression, and Failure Tests

## Module 5: From Tokens to Batches

**Outcome:** Turn a stream of token IDs into the exact input and target arrays consumed by the model.

16. EOS Tokens and Packed Document Streams
17. Context Windows, Shifted Targets, and Batches

## Module 6: Neural Network Foundations

**Outcome:** Build and train a complete tiny neural network before opening how language-model components learn.

18. Tensors and Shapes Without Fear
19. What a Parameter Is: Fitting a Line by Hand
20. Linear Layers, Matrix Multiplication, and Nonlinearity
21. One Training Step: Forward, Loss, Backward, Update

## Module 7: A First Language Model

**Outcome:** Train a working language model without attention and identify exactly what it cannot do.

22. Logits and Next-Token Probabilities
23. Cross-Entropy Loss With Small Numbers
24. Training a Model Without Attention, and Where It Fails
25. Training Loss, Validation Loss, and Overfitting

## Module 8: Attention From First Principles

**Outcome:** Build the core attention calculation from small, inspectable operations.

26. Why Tokens Need to Look at Other Tokens
27. Queries, Keys, and Values
28. Dot Products, Scaling, and Attention Softmax
29. Causal Masks and Weighted Value Mixing

## Module 9: Multi-Head Attention and Position

**Outcome:** Explain how several attention views combine and how the model represents order.

30. Heads, Reshaping, Transposing, and the Output Projection
31. Why Tokens Need Position Information
32. RoPE Rotations and Relative Position Math

## Module 10: The Transformer Block

**Outcome:** Trace information through one complete block, then through the stack, and account for every parameter.

33. Residual Connections and RMSNorm
34. MLPs, Activations, and SwiGLU Gates
35. One Complete Block and a Stack of Blocks
36. Weight Initialization and Tied Embeddings
37. Tracing Shapes and Counting Parameters Through the Whole Model

## Module 11: Learning Through Gradients

**Outcome:** Explain how measured error leads to controlled updates of the model's internal numbers.

38. Computation Graphs, Gradients, and the Chain Rule
39. SGD and Learning Rate
40. Momentum, Adam, and AdamW
41. Weight Decay and Optimizer Parameter Groups
42. Warmup, Cosine Decay, and Gradient Accumulation

## Module 12: Numerical Stability on a T4

**Outcome:** Recognize number-range failures and justify the precision and safeguards used for this hardware.

43. FP32, FP16, and BF16: Choosing Precision for a T4
44. Autocast and Gradient Scaling
45. Clipping, Inf, NaN, and Skipped Updates

## Module 13: Real Data at Scale

**Outcome:** Build a traceable corpus that no longer fits in memory and prove what entered it.

46. Documents, Corpora, JSON, and JSONL
47. Choosing a Dataset: License, Provenance, and a Pinned Revision
48. Data-Quality Filters and Rejection Reasons
49. Exact Deduplication and Benchmark Contamination
50. Stable Dataset Splits, Manifests, and Fingerprints
51. Binary Shards, Dtypes, Memory Mapping, and Shard Sampling

## Module 14: Checkpoints and Reproducibility

**Outcome:** Save enough state to continue a run safely and explain its limits.

52. What a Complete Checkpoint Saves
53. Seeds, RNG State, and Reproducibility
54. Safe Resume and Artifact Compatibility

## Module 15: Google Colab T4 Preparation

**Outcome:** Prepare a persistent, checked Colab environment before spending training time.

55. Setting Up Colab, CUDA, and Persistent Drive Storage
56. Estimating Memory and Benchmarking the Batch
57. Running the Preflight and Reading Its Report
58. Tracking a Run: Logs, Metrics, and Experiment Records

## Module 16: The Real Training Run

**Outcome:** Run the verified smoke, pilot, review, and full-training gates in order.

59. The Twenty-Step Smoke Test
60. The Ten-Million-Token Pilot and Go/No-Go Review
61. Training to the Configured Token Budget and Surviving Disconnects

## Module 17: Making the Model Talk

**Outcome:** Turn a trained checkpoint into generated text and control how each continuation is selected.

62. Greedy Decoding and Why It Repeats
63. Temperature, Top-k, and Top-p Sampling
64. Running the Chat Script and Why Generation Is Slow

## Module 18: Evaluation and Debugging

**Outcome:** Judge a run with several forms of evidence and diagnose common failures.

65. Evaluating Loss, Perplexity, and Fixed Prompts
66. Multiple-Choice Tasks and Accuracy
67. Reading Samples Without Fooling Yourself
68. Debugging Loss, NaNs, OOM, Repetition, and Resume Failures

## Module 19: Limits and What Comes Next

**Outcome:** State honestly what the trained model is and what larger scale or later training stages could add.

69. What a 59M-Parameter Model Can and Cannot Do
70. Token Budgets, Scaling Laws, and Being Under-Trained
71. Scaling Width, Depth, Data, Context, and Compute
72. What Post-Training Would Add: SFT and Chat Templates

## Module 20: Capstone

**Outcome:** Turn verified technical work into a published model and a clear explanation.

73. Designing Your Own Experiment
74. Writing a Model Card and Publishing Your Run
75. Explaining Technical Ideas Without Hidden Jargon
