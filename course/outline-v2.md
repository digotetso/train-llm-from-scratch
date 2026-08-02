# Pretrain an LLM From Scratch: Theory, Code, and a Real Colab Run

## Audience

This course is for a beginner who can read a little Python but does not yet know how machine learning, text representation, or language models work.

## Prerequisites

- Run a Python file from a terminal.
- Read basic Python values, lists, function calls, and printed output.
- Bring curiosity; no machine-learning, tensor, token, or Transformer knowledge is assumed.

## Course Promise

By the end of the course, a learner will be able to explain, inspect, run, and evaluate this repository's complete small-language-model pretraining pipeline, and will have trained a model of their own. Each idea begins with plain-language intuition, moves through a small example, and only then receives its technical name. Claims about the repository are tied to code, tests, commands, or observed artifacts.

## What the Learner Ships

- A trained model checkpoint produced on a free Colab T4.
- A tokenizer, a sharded dataset, and a run summary they can explain line by line.
- A model card stating what their model can do, what it cannot, and what it was trained on.

## Design Rules

**See it before you build it.** Module 1 runs the entire pipeline end to end on a tiny model. The learner watches loss fall and text appear before understanding any stage. Every later module explains a part of a machine they have already seen working.

**Teach machinery when it is needed.** Corpus filtering, deduplication, sharding, and memory mapping are production data engineering. They appear at Module 13, when the small in-memory path the learner already understands stops fitting on the machine, and not before.

**No unexplained jargon.** A video introduces at most two new terms. A term is used in plain language first, given a small example second, and named third.

**Every module ends in something that runs.** No module is theory only.

**Foundations before Transformers.** A learner with no machine-learning background meets parameters, linear layers, and a full training step on a toy problem before meeting an embedding or an attention head.

## Production Rule

Videos are completed and reviewed one at a time. Video 1 is the only fully produced video in this foundation; the remaining videos stay outline entries until the preceding video has been taught, checked for beginner language, and approved.

Every completed video uses six teaching documents: `script.md`, `lesson.md`, `lab.md`, `quiz.md`, `answer-key.md`, and `evidence.md`. A video may also include runnable standard-library code such as `lab.py`.

## Module 1: Orientation

**Outcome:** See what a single training example is, watch the whole pipeline work once, and know what it will cost.

1. From a Sentence to a Training Example
2. What You Will Build: The Spec, the Cost, and the Nine Stages
3. Run the Whole Pipeline Once Before Understanding It

## Module 2: Text Into Numbers

**Outcome:** Turn human-readable text into consistent data, and defend every change made to it.

4. How Computers Store Characters as Agreed Numbers
5. Unicode Code Points and UTF-8 Bytes
6. Why Visually Similar Text Needs Normalization
7. Inspecting Real Text: Invisible Characters and Cleaning Decisions

## Module 3: Tokens and BPE

**Outcome:** Explain how text is divided into reusable units with numeric identifiers.

8. Tokens and Token IDs
9. Why Byte-Level Tokenization Works
10. How BPE Learns Frequent Merges
11. Vocabulary Size and Special Tokens

## Module 4: Training a Robust Tokenizer

**Outcome:** Train and audit the repository's tokenizer across ordinary and unfamiliar text.

12. Training the Repository Tokenizer
13. Unicode Round Trips and the Complete Byte Alphabet
14. Tokenizer Reports, Compression, and Failure Tests

## Module 5: From Tokens to Batches

**Outcome:** Turn a stream of token IDs into the exact input and target arrays a model consumes.

15. EOS Tokens and Packed Document Streams
16. Context Windows, Shifted Targets, and Batches

## Module 6: Neural Network Foundations

**Outcome:** Build and train a complete tiny neural network before meeting any language-model component.

17. Tensors and Shapes Without Fear
18. What a Parameter Is: Fitting a Line by Hand
19. Linear Layers, Matrix Multiplication, and Nonlinearity
20. One Training Step: Forward, Loss, Backward, Update

## Module 7: A First Language Model

**Outcome:** Train a working language model with no attention, and feel exactly what it cannot do.

21. Turning Token IDs Into Embeddings
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

**Outcome:** Explain how several attention views combine, and how the model learns word order.

30. Heads, Reshaping, Transposing, and the Output Projection
31. Why Tokens Need Position Information
32. RoPE Rotations and Relative Position Math

## Module 10: The Transformer Block

**Outcome:** Trace information through one complete block, then through the full stack, and account for every parameter.

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

**Outcome:** Recognize number-range failures and the safeguards this hardware actually requires.

43. FP32, FP16, and BF16, and Why a T4 Must Use FP16
44. Autocast and Gradient Scaling
45. Clipping, Inf, NaN, and Skipped Updates

## Module 13: Real Data at Scale

**Outcome:** Build a traceable corpus that no longer fits in memory, and prove what entered it.

46. Documents, Corpora, JSON, and JSONL
47. Choosing a Dataset: Licence, Provenance, and a Pinned Revision
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
61. Training to the Full Token Budget and Surviving Disconnects

## Module 17: Making the Model Talk

**Outcome:** Turn a trained checkpoint into generated text, and control how that text is chosen.

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

**Outcome:** State honestly what the trained model is, and what a larger or later stage would add.

69. What a 59M-Parameter Model Can and Cannot Do
70. Token Budgets, Scaling Laws, and Being Under-Trained
71. Scaling Width, Depth, Data, Context, and Compute
72. What Post-Training Would Add: SFT and Chat Templates

## Module 20: Capstone

**Outcome:** Turn verified technical work into a published model and a clear explanation.

73. Designing Your Own Experiment
74. Writing a Model Card and Publishing Your Run
75. Explaining Technical Ideas Without Hidden Jargon
