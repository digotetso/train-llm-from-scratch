# Train a Language Model from Scratch
## From Raw Text to a Chatbot on a Free Google Colab T4

## Course overview

This course teaches students how to build and train a small GPT-style language model from random weights using the same essential stages used by modern AI labs:

```text
Raw text
   ↓
Dataset preparation
   ↓
Tokenizer training
   ↓
Decoder-only Transformer implementation
   ↓
Base-model pretraining
   ↓
Continued pretraining / domain adaptation
   ↓
Supervised fine-tuning (SFT)
   ↓
Preference tuning (DPO)
   ↓
Evaluation
   ↓
Interactive chatbot
```

Students will not fine-tune an existing pretrained model as their main project. They will train their own tokenizer, initialize a Transformer with random weights, teach it language through next-token prediction, and convert it into a simple chatbot.

The final chatbot will not compete with ChatGPT, Claude, or Gemini. It will be a small educational assistant that can communicate in basic English and explain a narrow set of beginner-level topics.

---

# 0. Pre-course model-validation phase

Before recording or teaching the lessons, train and validate the reference models that students will use throughout the course.

This phase is not optional. It ensures that:

- the tokenizer pipeline works;
- the data loader is deterministic;
- checkpoints can be resumed after Colab interruption;
- the decoder-only implementation trains correctly;
- prepared checkpoints exist for workshop students;
- the course examples show genuine improvements at each stage;
- the final chatbot works before the lessons are published.

## Reference models to validate

| Model | Parameters | Hardware target | Purpose |
|---|---:|---|---|
| MatGPT-Micro | 1M–3M | CPU or T4 | Fast smoke test for the training loop |
| MatGPT-Mini | Approximately 8M | Free Colab T4 | Prove that coherent English emerges on TinyStories |
| MatGPT-Tiny | Approximately 46M | Free Colab T4 across resumable sessions | Main course chatbot |
| MatGPT-A100 | Approximately 360M | One A100 80GB | Optional scaling track with visibly better quality |
| MatGPT-A100-XL | Approximately 1.28B | One A100 80GB | Optional upper-bound feasibility experiment only |

## Validation order

```text
1. Train MatGPT-Micro on a TinyStories subset.
2. Train MatGPT-Mini on TinyStories.
3. Freeze the working tokenizer, data-loader, checkpoint, and evaluation pipeline.
4. Train MatGPT-Tiny on BabyLM-2026-Strict.
5. Continue pretraining MatGPT-Tiny on FineWeb-Edu and reviewed domain text.
6. Perform SFT and DPO on MatGPT-Tiny.
7. Validate interactive chat and the fixed evaluation suite.
8. Scale the same pipeline to MatGPT-A100 on an A100 80GB.
9. Treat MatGPT-A100-XL as an advanced experiment, not a course dependency.
```

## Reference checkpoint policy

Prepare and preserve:

```text
random initialization checkpoint
early pretraining checkpoint
best base-model checkpoint
domain-adapted checkpoint
SFT checkpoint
DPO checkpoint
model-only safetensors export
resumable training checkpoint
```

Every reference run must record:

```text
model configuration
tokenizer hash
dataset-manifest hash
source-code commit hash
random seed
tokens processed
best validation loss
checkpoint path
training hardware
sample generations
```

---

# 1. Target audience

This course is suitable for:

- Python learners who understand functions, classes, and basic NumPy or PyTorch
- Machine-learning beginners who want to understand LLMs practically
- Educators who want to teach how LLMs work
- Developers who want to understand pretraining and post-training
- Students interested in AI research engineering

---

# 2. Prerequisites

Students should understand:

- Python variables, loops, functions, and classes
- Lists, dictionaries, and file handling
- Basic algebra
- Basic probability concepts
- Basic machine-learning ideas such as training data, loss, and optimization

Recommended but not mandatory:

- Beginner PyTorch
- Matrix multiplication
- Neural-network basics
- Familiarity with Google Colab

---

# 3. Learning outcomes

By the end of the course, students will be able to:

1. Explain how autoregressive language models predict the next token.
2. Prepare and clean text corpora for pretraining.
3. Train a custom BPE or SentencePiece tokenizer.
4. Build a decoder-only Transformer from scratch in PyTorch.
5. Explain token embeddings, positional information, attention, causal masking, MLP layers, residual connections, and normalization.
6. Pretrain a small language model from random initialization.
7. Track validation loss, perplexity, tokens processed, and sample quality.
8. Save and resume training checkpoints across Colab sessions.
9. Perform continued pretraining on a narrow domain corpus.
10. Convert a base model into a chatbot using supervised fine-tuning.
11. Improve response quality using preference tuning with DPO.
12. Evaluate a model quantitatively and qualitatively.
13. Build an interactive chat interface.
14. Explain how this educational pipeline maps to large-scale AI-lab workflows.

---

# 4. Final capstone project

## MatGPT-Tiny Tutor

A decoder-only Transformer chatbot trained from scratch to explain beginner-level Python, machine-learning, and LLM concepts in simple English.

### Final flagship configuration

| Component | Value |
|---|---:|
| Model family | Decoder-only causal Transformer |
| Parameters | Approximately 46M |
| Transformer layers | 12 |
| Hidden dimension | 512 |
| Attention heads | 8 |
| Feed-forward dimension | 2,048 |
| Vocabulary size | 16,384 |
| Context length | 512 tokens |
| Positional method | RoPE |
| Precision | FP16 |
| Training hardware | Free Colab T4 when available |
| Checkpoint strategy | Resumable Google Drive checkpoints |

### Supporting and stretch models

| Model | Parameters | Hardware target | Purpose |
|---|---:|---|---|
| MatGPT-Micro | 1M–3M | CPU or T4 | Debugging and fast experiments |
| MatGPT-Mini | Approximately 8M | Free Colab T4 | First coherent TinyStories model |
| MatGPT-Tiny | Approximately 46M | Free Colab T4 | Main chatbot capstone |
| MatGPT-A100 | Approximately 360M | One A100 80GB | Optional higher-quality scaling track |
| MatGPT-A100-XL | Approximately 1.28B | One A100 80GB | Optional upper-bound feasibility experiment |

---

# 5. Course modules

## Module 0 — Orientation: What are we building?

### Topics

- What an LLM actually does
- Next-token prediction
- Why ChatGPT-like systems require multiple training stages
- Pretraining versus post-training
- Why small models are useful for learning
- Why GPU memory is not the only constraint
- Why total tokens processed matter
- What free Colab can and cannot do

### Key idea

A small model can fit into GPU memory but still fail if it does not process enough high-quality training data.

### Demonstration

```text
Random model
→ partially trained base model
→ domain-adapted model
→ instruction-tuned model
→ preference-tuned chatbot
```

### Deliverable

A one-page explanation of why a model that fits into memory may still not learn useful language.

---

## Module 1 — Text, tokens, and language-model datasets

### Topics

- Raw text versus tokens
- Characters, words, and subwords
- Vocabulary size
- Token IDs
- Sequence length
- Training examples
- Data quality
- Deduplication
- Train, validation, and test splits
- Dataset licensing and attribution

### Datasets introduced

```text
roneneldan/TinyStories
BabyLM-2026-Strict-Small
BabyLM-2026-Strict
WikiText-103
HuggingFaceFW/fineweb-edu
```

### Practical lab

```text
raw documents
→ normalize text
→ remove empty rows
→ filter unusually short rows
→ deduplicate
→ split into train and validation sets
```

### Deliverable

A clean corpus and dataset manifest containing the dataset name, source, licence, intended use, number of documents, and number of tokens.

---

## Module 2 — Build a tokenizer from scratch

### Topics

- Why models cannot directly read text
- Character-level tokenization
- Word-level tokenization
- Byte-pair encoding
- SentencePiece
- Compression ratio
- Unknown words
- Special chat tokens
- Vocabulary trade-offs

### Recommended tokenizer

```text
SentencePiece Unigram or byte-level BPE
Vocabulary size: 16,384
```

### Special tokens

```text
<|pad|>
<|bos|>
<|eos|>
<|system|>
<|user|>
<|assistant|>
<|end|>
```

### Practical labs

1. Compare character, word, and subword tokenization.
2. Tokenize words such as `telecommunications`, `tokenization`, `transformer`, `Botswana`, `gradient descent`, and `unbelievable`.
3. Train the final 16K tokenizer.

### Deliverable

```text
tokenizer.model
tokenizer.json
vocab file
special-token configuration
compression report
```

---

## Module 3 — Neural-network foundations for LLMs

### Topics

- Tensors
- Matrix multiplication
- Embeddings
- Logits
- Softmax
- Cross-entropy loss
- Gradient descent
- AdamW
- Training loop
- Validation loop
- Overfitting

### Practical lab

Build a tiny next-character model before building a Transformer.

```text
Input:  hell
Target: ello
```

### Deliverable

A working character-level language model that generates short text.

---

## Module 4 — Understand the decoder-only Transformer

### Topics

- Why decoder-only architectures are used for text generation
- Token embeddings
- Positional encoding and RoPE
- Query, key, and value vectors
- Self-attention
- Multi-head attention
- Causal masking
- Residual connections
- Layer normalization
- Feed-forward network
- Transformer blocks
- LM head
- Weight tying

### Architecture flow

```text
Input text
   ↓
Token IDs
   ↓
Token embeddings + positional information
   ↓
Decoder block × N
   ├── LayerNorm
   ├── Masked multi-head self-attention
   ├── Residual connection
   ├── LayerNorm
   ├── Feed-forward network
   └── Residual connection
   ↓
LM head
   ↓
Next-token probabilities
```

### Key concept

The causal mask prevents the model from seeing future tokens during training.

### Practical labs

1. Visualize the causal mask.
2. Implement one attention head.
3. Extend to multi-head attention.
4. Build one Transformer block.
5. Stack multiple decoder blocks.

### Deliverable

A working decoder-only Transformer implemented in plain PyTorch.

---

## Module 5 — Train MatGPT-Micro

### Purpose

Validate the entire training pipeline using a fast experiment before running expensive training jobs.

### Configuration

| Component | Value |
|---|---:|
| Parameters | 1M–3M |
| Context length | 128–256 |
| Dataset | TinyStories subset |
| Training target | 1M–10M tokens |

### Topics

- Random initialization
- Forward pass
- Loss calculation
- Backpropagation
- Optimizer step
- Learning-rate schedule
- Gradient clipping
- Sampling

### Expected progression

```text
Random characters
→ repeated fragments
→ partial words
→ short grammatical sentences
→ simple stories
```

### Deliverable

A checkpoint, training-loss chart, and sample-generation report.

---

## Module 6 — Train MatGPT-Mini: coherent English at tiny scale

### Purpose

Reproduce the main TinyStories lesson: a small model can generate coherent English when dataset complexity matches model capacity.

### Configuration

| Component | Value |
|---|---:|
| Parameters | Approximately 8M |
| Dataset | TinyStories |
| Context length | 256–512 |
| Token budget | 30M–100M tokens |
| Precision | FP16 |

### Topics

- Why TinyStories works
- Model capacity
- Dataset complexity
- Tokens processed
- Batch size
- Gradient accumulation
- Sampling temperature
- Top-k sampling
- Checkpointing

### Practical lab

Compare generation quality after 1M, 10M, 30M, and 100M tokens.

### Deliverable

A coherent story-generating language model and comparison report.

---

## Module 7 — Design the serious English corpus

### Purpose

Move beyond childlike story generation toward a useful basic chatbot.

### Recommended flagship corpus

```text
BabyLM-2026-Strict
```

### Core data recipe

| Corpus | Token target | Purpose |
|---|---:|---|
| BabyLM-2026-Strict | 100M | Core English language learning |
| Domain textbooks | 5M–20M | Python, ML, and LLM concepts |
| WikiText-103 subset | Optional 25M–50M | Encyclopedic prose |
| FineWeb-Edu slice | Optional 25M–100M | Broader educational English |

### Topics

- Spoken-language data
- Subtitles
- Simple Wikipedia
- Educational prose
- Corpus mixing
- Data weighting
- Licensing trade-offs
- Why random web text is not automatically good training data

### Deliverable

A final corpus recipe and token-count report.

---

## Module 8 — Pretrain MatGPT-Tiny

### Purpose

Train the approximately 46M-parameter flagship model from random weights.

### Configuration

| Component | Value |
|---|---:|
| Layers | 12 |
| Hidden dimension | 512 |
| Heads | 8 |
| FFN dimension | 2,048 |
| Vocabulary | 16,384 |
| Context length | 512 |
| Parameters | Approximately 46M |
| Precision | FP16 |
| Optimizer | AdamW or 8-bit AdamW |
| Learning rate | Approximately 3e-4 peak |
| Warm-up | Approximately 3% |
| Gradient clipping | 1.0 |
| Target tokens | 100M–200M initially |

### Colab practices

- Mount Google Drive immediately.
- Save checkpoints every fixed token interval.
- Save model, optimizer, scheduler, and scaler states.
- Track tokens processed rather than epochs only.
- Use FP16 autocast.
- Use gradient accumulation.
- Use activation checkpointing when useful.
- Resume training after runtime interruption.

### Practical labs

1. Benchmark tokens per second, safe micro-batch size, and peak VRAM usage.
2. Run a 10M-token smoke test.
3. Resume from a checkpoint.
4. Train toward 100M–200M tokens.

### Deliverable

A pretrained base-model checkpoint and training report.

---

## Module 9 — Evaluate the base model

### Topics

- Training loss
- Validation loss
- Perplexity
- Memorization
- Overfitting
- Sampling quality
- Prompt design
- Benchmark limitations

### Base-model prompts

```text
Python is a programming language that
A token is
An embedding is
The purpose of pretraining is
Once upon a time
```

### Expected behavior

The model should complete text reasonably but may not answer questions reliably.

### Deliverable

A report containing loss curves, perplexity results, generated samples, strengths, limitations, and failure examples.

---

## Module 10 — Continued pretraining: teach domain knowledge

### Purpose

Specialize the model before teaching it chatbot behavior.

### Domain

```text
Python fundamentals
machine-learning fundamentals
LLM foundations
tokenization
embeddings
attention
Transformers
pretraining
SFT
DPO
evaluation
```

### Recommended domain corpus

```text
5M–20M tokens
```

### Example training text

```text
A token is a small piece of text. It may be a whole word, part of a word, or punctuation.

An embedding is a list of numbers that represents information. Words with similar meanings often have similar embeddings.

Pretraining teaches a model to predict the next token. During this process, the model gradually learns patterns in language.
```

### Practical lab

Compare the model before and after domain adaptation.

### Deliverable

A domain-adapted base checkpoint.

---

## Module 11 — Supervised fine-tuning: turn the model into a chatbot

### Purpose

Teach the model to respond to instructions instead of merely continuing text.

### Chat format

```text
<|system|>
You are MatGPT-Tiny, a patient tutor. Explain concepts simply.
<|user|>
What is a token?
<|assistant|>
A token is a small piece of text. It may be a word, part of a word, or punctuation.
<|end|>
```

### Topics

- Instruction tuning
- Chat templates
- User and assistant roles
- System prompts
- Assistant-only loss masking
- Single-turn versus multi-turn conversations
- Conversation truncation
- SFT learning rates
- Overfitting during SFT

### Recommended dataset mixture

| Source | Examples | Purpose |
|---|---:|---|
| Custom tutor conversations | 8K–20K | Main domain behavior |
| OASST1 subset | 5K–15K | General assistant conversations |
| Filtered Smol-SmolTalk subset | 5K–15K | Short chat examples |
| Filtered UltraChat subset | Optional 5K–10K | Additional breadth |

### Practical lab

Compare the base model, domain-adapted model, and SFT model.

### Deliverable

A chatbot checkpoint capable of basic instruction following.

---

## Module 12 — Preference tuning with DPO

### Purpose

Teach the model which answers are better.

### Topics

- Why SFT is not enough
- Preferred and rejected answers
- Alignment
- DPO intuition
- DPO versus RLHF
- Reference models
- Preference-pair design
- Style alignment
- Safety and uncertainty

### Preference-pair example

```json
{
  "prompt": "Explain embeddings simply.",
  "chosen": "Embeddings are lists of numbers that represent meaning. Similar words often have similar embeddings.",
  "rejected": "Embeddings are multidimensional latent representations produced within vector spaces through learned mappings."
}
```

### Recommended preference dataset

| Source | Examples |
|---|---:|
| Custom beginner-tutor preference pairs | 1K–3K |
| Filtered UltraFeedback Binarized | 500–2K |
| Total | Approximately 1.5K–5K |

### Practical lab

Run DPO and compare SFT answers against DPO answers.

### Deliverable

A preference-tuned chatbot checkpoint.

---

## Module 13 — Optional reinforcement-learning demonstration

### Purpose

Explain how reinforcement learning fits into modern post-training without making it mandatory for the main course.

### Topics

- Rewards
- Verifiable answers
- Policy optimization
- RLHF concept
- GRPO concept
- Why production RL pipelines are expensive
- Why DPO is more practical on a free T4

### Simple exercise

```text
Prompt: What is 7 + 5?

Candidate A: 12
Reward: 1

Candidate B: 13
Reward: 0
```

### Deliverable

A short notebook demonstrating automated reward assignment.

---

## Module 14 — Model evaluation

### Topics

- Quantitative evaluation
- Qualitative evaluation
- Benchmark limitations
- Human rubrics
- Regression testing
- Hallucination tracking
- Safety evaluation
- Domain-specific evaluation

### Evaluation suite

#### Base language-model checks

```text
validation loss
perplexity
generated text quality
repetition frequency
```

#### Optional benchmark checks

```text
HellaSwag
ARC-Easy
TruthfulQA subset
```

#### Chat-evaluation prompts

```text
Explain a token in one sentence.
Explain embeddings to a 12-year-old.
What is the difference between training and inference?
Give me a simple Python list example.
Explain attention using an analogy.
What should I learn before studying Transformers?
Say when you are unsure.
```

### Human scoring rubric

Score each answer from 1 to 5:

| Dimension | Question |
|---|---|
| Correctness | Is the answer accurate? |
| Relevance | Does it answer the question? |
| Simplicity | Can a beginner understand it? |
| Fluency | Does it read naturally? |
| Conciseness | Is it appropriately brief? |
| Honesty | Does it avoid inventing facts? |
| Safety | Is the answer responsible? |
| Formatting | Did it follow the instruction? |

### Deliverable

A final evaluation report comparing the random model, pretrained model, domain-adapted model, SFT model, and DPO model.

---

## Module 15 — Build the chat interface

### Topics

- Autoregressive generation
- Prompt formatting
- Conversation history
- Context-window limits
- Temperature
- Top-k sampling
- Top-p sampling
- Repetition penalties
- Stopping tokens
- KV caching

### Recommended first interface

Use a notebook REPL:

```python
while True:
    user_input = input("You: ")

    if user_input.lower() in {"exit", "quit"}:
        break

    prompt = format_chat(history, user_input)
    response = generate(model, tokenizer, prompt)

    print("MatGPT:", response)
    history.append((user_input, response))
```

### Optional interface

Build a lightweight Gradio chat UI for demonstration.

### Deliverable

An interactive chatbot running inside Google Colab.

---

## Module 16 — Deployment, documentation, and model cards

### Topics

- Saving model weights
- Saving tokenizer artifacts
- `safetensors`
- Model-only checkpoint versus resumable checkpoint
- Quantized inference
- Publishing to Hugging Face Hub
- Model cards
- Dataset cards
- Licensing
- Known limitations
- Responsible release

### Required model-card sections

```text
Model description
Architecture
Training hardware
Training datasets
Post-training datasets
Licences
Training token count
Evaluation results
Intended uses
Limitations
Safety notes
How to run inference
```

### Deliverable

A publishable model card and repository.

---

## Module 17 — Optional A100 scaling track

### Purpose

Scale the exact same validated training pipeline to a larger decoder-only model on one A100 80GB GPU.

This module is optional and should not block the core course.

### Recommended model

## MatGPT-A100

| Component | Value |
|---|---:|
| Parameters | Approximately 360M |
| Vocabulary size | 32,768 |
| Layers | 26 |
| Hidden dimension | 1,024 |
| Attention heads | 16 |
| Head dimension | 64 |
| Feed-forward dimension | 4,096 |
| Context length | 1,024 initially |
| Positional method | RoPE |
| Precision | BF16 |
| Hardware | One A100 80GB |

### Training targets

```text
Validation run:  approximately 1B tokens
Better-quality run: approximately 3B–7B tokens
```

### Topics

- Scaling model width and depth
- Scaling tokenizer vocabulary
- BF16 training
- Effective batch size
- Fused AdamW
- Activation checkpointing
- Throughput benchmarking
- Comparing model quality at different scales
- Why the largest model that fits is not always the best model to train

### Optional upper-bound experiment

## MatGPT-A100-XL

| Component | Value |
|---|---:|
| Parameters | Approximately 1.28B |
| Vocabulary size | 32,768 |
| Layers | 24 |
| Hidden dimension | 2,048 |
| Attention heads | 16 |
| Feed-forward dimension | 8,192 |
| Context length | 1,024 initially |
| Precision | BF16 |
| Hardware | One A100 80GB with activation checkpointing |

Use this only as an advanced feasibility experiment.

```text
Smoke test: 2B–5B tokens
Serious run: 10B–30B+ tokens
```

### Deliverable

A scaling report comparing:

```text
8M
vs.
46M
vs.
360M
```

The comparison should include:

```text
training throughput
peak GPU memory
tokens processed
validation loss
perplexity
sample quality
chat quality
training cost
```

---

# 6. Suggested teaching schedule

## Option A — 12-week academic course

| Week | Module |
|---|---|
| 1 | Orientation, LLM pipeline, and dataset strategy |
| 2 | Tokenization fundamentals |
| 3 | Neural-network foundations |
| 4 | Decoder-only Transformer architecture |
| 5 | Build the Transformer in PyTorch |
| 6 | Train MatGPT-Micro and MatGPT-Mini |
| 7 | Build the serious English corpus |
| 8 | Pretrain MatGPT-Tiny |
| 9 | Continued pretraining |
| 10 | Supervised fine-tuning |
| 11 | DPO preference tuning and evaluation |
| 12 | Chat interface, documentation, and presentation |
| Optional extension | A100 scaling track: train and compare the 360M model |

## Option B — 8-week intensive course

| Week | Module |
|---|---|
| 1 | Foundations and tokenizer training |
| 2 | Build the decoder-only Transformer |
| 3 | Train the 8M TinyStories model |
| 4 | Build the serious corpus and start 46M pretraining |
| 5 | Resume pretraining and evaluate |
| 6 | Continued pretraining and SFT |
| 7 | DPO and evaluation |
| 8 | Chat interface and final capstone presentation |

## Option C — Workshop format

| Session | Duration | Focus |
|---|---:|---|
| Session 1 | 3 hours | LLM fundamentals and tokenizer |
| Session 2 | 4 hours | Build a decoder-only Transformer |
| Session 3 | 3 hours | Train a tiny TinyStories model |
| Session 4 | 3 hours | Pretraining pipeline and checkpoints |
| Session 5 | 3 hours | SFT and chatbot behavior |
| Session 6 | 3 hours | DPO, evaluation, and chat interface |
| Optional advanced session | 3 hours | A100 scaling, throughput benchmarking, and model comparison |

Students use prepared checkpoints where full training cannot finish during the live workshop.

---

# 7. Notebook sequence

```text
00_course_overview.ipynb
01_environment_and_gpu_check.ipynb
02_dataset_inspection.ipynb
03_character_tokenizer.ipynb
04_train_bpe_tokenizer.ipynb
05_neural_network_basics.ipynb
06_build_attention.ipynb
07_build_decoder_block.ipynb
08_build_gpt_model.ipynb
09_train_matgpt_micro.ipynb
10_train_matgpt_mini_tinystories.ipynb
11_prepare_babylm_corpus.ipynb
12_pretrain_matgpt_tiny.ipynb
13_resume_training_from_checkpoint.ipynb
14_continue_pretraining_on_domain_text.ipynb
15_supervised_fine_tuning.ipynb
16_dpo_preference_tuning.ipynb
17_model_evaluation.ipynb
18_chat_interface.ipynb
19_optional_rl_demo.ipynb
20_publish_model_card.ipynb
21_optional_a100_scaling.ipynb
22_compare_model_scales.ipynb
```

---

# 8. Dataset plan

## Stage 1 — Fast learning demonstration

```text
Dataset: roneneldan/TinyStories
Model: approximately 8M parameters
Purpose: demonstrate coherent English generation at tiny scale
```

## Stage 2 — Serious base-model pretraining

```text
Dataset: BabyLM-2026-Strict
Budget: approximately 100M tokens
Model: approximately 46M parameters
Purpose: learn broader English patterns
```

## Stage 3 — Domain adaptation

```text
Dataset: custom Python, ML, and LLM educational corpus
Budget: 5M–20M tokens
Purpose: specialize the tutor
```

## Stage 4 — Optional breadth upgrade

```text
Dataset: streamed FineWeb-Edu slice
Budget: 25M–100M tokens
Purpose: add educational breadth
```

## Stage 5 — Supervised fine-tuning

```text
Custom tutor conversations
Filtered OASST1
Filtered Smol-SmolTalk
Optional filtered UltraChat
```

## Stage 6 — Preference tuning

```text
Custom tutor preference pairs
Filtered UltraFeedback Binarized
```


## Stage 7 — Optional A100 scaling corpus

```text
Model: MatGPT-A100, approximately 360M parameters
Hardware: one A100 80GB
Validation budget: approximately 1B tokens
Better-quality budget: approximately 3B–7B tokens

Suggested composition:
FineWeb-Edu streamed sample: 750M–6.5B tokens
BabyLM-2026-Strict: 100M tokens
Reviewed educational domain text: 25M–100M tokens
Optional clean expository corpus: licence-audited and reviewed
```

Use the same cleaning, provenance, tokenization, checkpointing, and evaluation pipeline as the 46M model.

---

# 9. Student capstone milestones

1. **Tokenizer:** train and test a custom tokenizer.
2. **Tiny language model:** train a 1M–3M model and produce improving text samples.
3. **Coherent TinyStories model:** train an approximately 8M model capable of simple English story generation.
4. **Serious base model:** pretrain the approximately 46M flagship model.
5. **Domain specialization:** adapt the model to Python, ML, and LLM education.
6. **Chatbot conversion:** perform SFT and demonstrate simple instruction following.
7. **Preference alignment:** perform DPO and compare response quality.
8. **Final chatbot:** run an interactive chatbot and publish an evaluation report.
9. **Optional scaling study:** train or inspect the 360M A100 checkpoint and compare it with the 8M and 46M models.

---

# 10. Final student demonstration

Each student or team should demonstrate:

1. Their custom tokenizer.
2. Their decoder-only Transformer architecture.
3. Loss reduction during pretraining.
4. Sample text from the random, pretrained, and domain-adapted models.
5. Chat behavior before and after SFT.
6. Response-quality differences before and after DPO.
7. Their evaluation rubric and results.
8. Their interactive chatbot.
9. Their model card.
10. Their explanation of limitations.

---

# 11. Core course message

Students should finish the course understanding that an LLM is not magic.

It is a neural network trained to predict the next token.

```text
We started with random weights.
We converted text into tokens.
We built a decoder-only Transformer.
We trained it to predict the next token.
We gave it a narrow educational corpus.
We taught it how to answer questions.
We taught it which answers were better.
We evaluated it honestly.
We chatted with a model we trained ourselves.
```

That is the achievement of the course.
---

# 12. Reference training plan for course authors

Before teaching the course, the course authors should complete the following implementation sequence:

```text
Experiment 1: 1M–3M smoke test on a TinyStories subset
Experiment 2: approximately 8M on TinyStories for 50M–100M tokens
Experiment 3: approximately 46M on BabyLM-2026-Strict for 100M tokens
Experiment 4: continue the 46M model on 50M–150M FineWeb-Edu tokens
Experiment 5: continue the 46M model on 5M–20M reviewed domain tokens
Experiment 6: SFT the 46M model on filtered tutor conversations
Experiment 7: DPO the SFT checkpoint on preference pairs
Experiment 8: validate notebook chat and the fixed evaluation suite
Experiment 9: optionally train approximately 360M on one A100 80GB
```

## Required corpora

| Stage | Corpus | Target |
|---|---|---:|
| Warm-up pretraining | `roneneldan/TinyStories` | 50M–100M seen tokens |
| Flagship base pretraining | `BabyLM-community/BabyLM-2026-Strict` | 100M tokens initially |
| Breadth extension | Streamed `HuggingFaceFW/fineweb-edu` slice | 50M–150M tokens for 46M |
| Domain adaptation | Reviewed Python, ML, and LLM text | 5M–20M tokens for 46M |
| SFT | Custom tutor chat + filtered OASST1 + filtered Smol-SmolTalk | 18K–45K examples |
| DPO | Custom preferences + filtered UltraFeedback Binarized | 1.5K–5K pairs |
| A100 scaling | FineWeb-Edu + BabyLM + reviewed domain text | 1B tokens initially; 3B–7B later |

## Required repository outputs

```text
README.md
TRAINING_PLAN.md
DATA_MANIFEST.md
MODEL_CARD_8M.md
MODEL_CARD_46M.md
MODEL_CARD_360M.md
configs/*.yaml
scripts/train_tokenizer.py
scripts/tokenize_and_shard.py
scripts/pretrain.py
scripts/midtrain.py
scripts/sft.py
scripts/dpo.py
scripts/evaluate.py
scripts/chat.py
tests/*.py
notebooks/*.ipynb
```

## Minimum automated tests

```text
tokenizer round trip
causal-mask correctness
attention output shape
forward-pass shape
loss decreases on a tiny overfit batch
checkpoint save/load equivalence
resume-training equivalence
generation stops at EOS
chat-template rendering
assistant-only SFT masking
DPO data-format validation
```

