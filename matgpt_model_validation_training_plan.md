# MatGPT Validation Training Plan
## Train the 8M, 46M, and optional A100 stretch models before producing the course

**Project goal:** validate the full educational pipeline end to end before recording lessons:

```text
raw corpora
→ corpus audit and cleaning
→ custom tokenizer
→ decoder-only Transformer initialized from random weights
→ base pretraining
→ continued pretraining / mid-training
→ supervised fine-tuning (SFT)
→ preference tuning (DPO)
→ evaluation
→ interactive chat
```

The objective is not to build a frontier model. The objective is to prove that every lesson, script, dataset transformation, training stage, checkpoint, and evaluation step works reliably and produces visible improvements.

---

# 1. Final decision

Train three model tiers.

| Tier | Model | Hardware target | Role |
|---|---|---|---|
| Warm-up | **MatGPT-Mini: ~8M parameters** | Free Colab T4 | Fast proof that the implementation learns coherent English |
| Flagship | **MatGPT-Tiny: ~46M parameters** | Free Colab T4 across resumable sessions | Main course chatbot trained from scratch |
| Stretch | **MatGPT-A100: ~360M parameters** | One A100 80GB | Optional higher-quality validation and scaling experiment |
| Upper-bound experiment | **MatGPT-A100-XL: ~1.28B parameters** | One A100 80GB with activation checkpointing | Demonstrate what can fit; do not start here |

The most important distinction is:

> **A model fitting in memory is not the same as a model being practical to train well.**

The recommended A100 extension is therefore approximately **360M parameters**, not the largest model that can technically fit.

---

# 2. Success criteria

Before recording the course, complete the following gates.

## Gate A — Infrastructure

- Training can start from random weights.
- The code can resume from an interrupted checkpoint.
- Dataset preprocessing is deterministic.
- The tokenizer can be saved, loaded, and reproduced.
- Loss, validation loss, tokens processed, throughput, GPU memory, and generated samples are logged.
- The same checkpoint can be loaded for inference.
- Every run records its configuration and source-code commit hash.

## Gate B — 8M warm-up model

The model should:

- produce clear loss reduction;
- generate coherent multi-sentence TinyStories-style English;
- avoid immediate repetitive collapse under reasonable sampling settings;
- support checkpoint resume;
- prove the tokenizer, data loader, optimizer, sampling, and evaluation code.

## Gate C — 46M flagship base model

The model should:

- learn stable English completions on held-out data;
- improve meaningfully after continued pretraining on educational text;
- become a basic chatbot after SFT;
- answer a narrow Python, ML, and LLM tutor prompt suite more consistently after DPO;
- run interactively in a notebook chat loop.

## Gate D — A100 stretch model

The model should:

- train with the same code path and dataset schema;
- demonstrate better general English and chat behavior than the 46M model;
- provide a scaling comparison for the advanced course section.

---

# 3. Recommended architecture

Use a modern but readable decoder-only causal Transformer.

```text
Input text
   ↓
Tokenizer
   ↓
Token IDs
   ↓
Token embeddings + RoPE positional information
   ↓
Decoder block × N
   ├── RMSNorm or LayerNorm
   ├── Causal multi-head self-attention
   ├── Residual connection
   ├── RMSNorm or LayerNorm
   ├── Feed-forward MLP
   └── Residual connection
   ↓
Final normalization
   ↓
Tied LM head
   ↓
Next-token logits
```

## Architecture principles

Use:

- decoder-only causal attention;
- tied input embeddings and output LM head;
- rotary position embeddings (RoPE);
- pre-normalization;
- GELU or SiLU activation;
- causal masking;
- FP16 on T4;
- BF16 on A100;
- context length 512 initially;
- standard PyTorch scaled-dot-product attention when available;
- deterministic configuration files.

Avoid during the first validation pass:

- mixture-of-experts;
- long-context experiments;
- retrieval augmentation;
- distributed training;
- speculative decoding;
- custom CUDA kernels;
- full PPO-style RLHF;
- unnecessary architectural experimentation.

The first objective is a stable reproducible pipeline.

---

# 4. Model configurations

## 4.1 MatGPT-Mini: approximately 8M parameters

Use this to validate the entire base-pretraining loop quickly.

| Component | Value |
|---|---:|
| Vocabulary size | 8,192 |
| Layers | 6 |
| Hidden dimension | 256 |
| Attention heads | 8 |
| Head dimension | 32 |
| Feed-forward dimension | 1,024 |
| Context length | 256 initially; 512 after validation |
| Positional method | RoPE |
| Parameters | Approximately 7M–8M |
| Precision | FP16 |
| Dataset | TinyStories |

Approximate parameter budget:

```text
Token embeddings:     8,192 × 256                  ≈ 2.1M
Transformer blocks:   6 × 12 × 256²               ≈ 4.7M
Norms and biases:                                  < 0.2M
Total:                                             ≈ 7.0M
```

It is acceptable to land between 7M and 9M. The educational purpose is more important than an exact round number.

---

## 4.2 MatGPT-Tiny: approximately 46M parameters

This is the flagship free-Colab model.

| Component | Value |
|---|---:|
| Vocabulary size | 16,384 |
| Layers | 12 |
| Hidden dimension | 512 |
| Attention heads | 8 |
| Head dimension | 64 |
| Feed-forward dimension | 2,048 |
| Context length | 512 |
| Positional method | RoPE |
| Parameters | Approximately 46M |
| Precision | FP16 |
| Hardware | T4, with resumable sessions |

Approximate parameter budget:

```text
Token embeddings:     16,384 × 512                ≈ 8.4M
Transformer blocks:   12 × 12 × 512²             ≈ 37.7M
Norms and biases:                                  < 0.3M
Total:                                             ≈ 46.4M
```

---

## 4.3 MatGPT-A100: approximately 360M parameters

This is the recommended A100 80GB stretch model.

| Component | Value |
|---|---:|
| Vocabulary size | 32,768 |
| Layers | 26 |
| Hidden dimension | 1,024 |
| Attention heads | 16 |
| Head dimension | 64 |
| Feed-forward dimension | 4,096 |
| Context length | 1,024 initially |
| Positional method | RoPE |
| Parameters | Approximately 360M |
| Precision | BF16 |
| Hardware | One A100 80GB |

Approximate parameter budget:

```text
Token embeddings:     32,768 × 1,024              ≈ 33.6M
Transformer blocks:   26 × 12 × 1,024²           ≈ 327.2M
Norms and biases:                                  < 1.0M
Total:                                             ≈ 361M
```

This model is large enough to demonstrate a noticeable quality improvement while remaining realistic on one A100 80GB.

---

## 4.4 MatGPT-A100-XL: approximately 1.28B parameters

This is an upper-bound experiment, not the starting point.

| Component | Value |
|---|---:|
| Vocabulary size | 32,768 |
| Layers | 24 |
| Hidden dimension | 2,048 |
| Attention heads | 16 |
| Head dimension | 128 |
| Feed-forward dimension | 8,192 |
| Context length | 1,024 initially |
| Positional method | RoPE |
| Parameters | Approximately 1.28B |
| Precision | BF16 |
| Memory strategy | Activation checkpointing and small micro-batches |
| Hardware | One A100 80GB |

Approximate parameter budget:

```text
Token embeddings:     32,768 × 2,048              ≈ 67.1M
Transformer blocks:   24 × 12 × 2,048²           ≈ 1.21B
Norms and biases:                                  ≈ 1M
Total:                                             ≈ 1.28B
```

Train this only after the 360M pipeline is stable. It may fit, but it requires much more data and compute to justify its size.

---

# 5. Token budget strategy

Training compute grows approximately with:

```text
training FLOPs ≈ 6 × parameters × training tokens
```

Use this as a planning tool, not as an exact runtime prediction.

| Model | Initial validation tokens | Better-quality target | Approximate FLOPs at quality target |
|---|---:|---:|---:|
| 8M | 20M–30M | 50M–100M | 4.8 × 10^15 FLOPs at 100M tokens |
| 46M | 100M | 150M–300M | 5.52 × 10^16 FLOPs at 200M tokens |
| 360M | 1B | 3B–7B | 1.512 × 10^19 FLOPs at 7B tokens |
| 1.28B | 2B–5B smoke test | 10B–30B+ | 1.92 × 10^20 FLOPs at 25B tokens |

Compute-optimal scaling research shows that model size and token count should scale together. For this educational project, the smaller validation runs can intentionally be undertrained, but label them honestly as validation checkpoints rather than final high-quality models.

---

# 6. Dataset strategy

Use separate corpora for separate purposes. Do not dump unrelated text into one folder and hope for the best.

## 6.1 Stage A: 8M warm-up corpus

### Primary dataset

```text
roneneldan/TinyStories
```

TinyStories contains synthetic short stories using deliberately simple vocabulary. This is the correct first dataset because the language domain is constrained enough for very small models to learn coherent English.

### Use

| Split | Purpose |
|---|---|
| Official train split | Base pretraining |
| Official validation split | Validation loss and sample comparison |
| Fixed prompt list | Reproducible qualitative evaluation |

### Token target

```text
Initial: 20M–30M seen tokens
Main warm-up: 50M–100M seen tokens
```

### Do not do yet

- Do not mix in broad web text.
- Do not add complicated instruction datasets.
- Do not judge general knowledge.
- Do not expect a useful tutor chatbot.

The 8M model proves that the language-model engine works.

---

## 6.2 Stage B: 46M flagship base corpus

### Required base corpus

```text
BabyLM-community/BabyLM-2026-Strict
```

This is a detoxified 100M-token English training dataset designed for sample-efficient language-model training.

### Recommended first serious run

```text
BabyLM-2026-Strict: 100M tokens
```

Train the 46M model on this corpus first. This produces a controlled, reproducible baseline.

### Recommended second serious run

After validating the baseline, expand with:

```text
BabyLM-2026-Strict:                   100M tokens
FineWeb-Edu streamed sample:          50M–150M tokens
Reviewed educational domain corpus:   5M–20M tokens
```

This creates a more useful tutor-oriented base model without making the first experiment unnecessarily complex.

### Optional expository supplement

Use a reviewed subset of:

```text
WikiText-103
```

Add it only if you want more encyclopedic prose and a stable held-out comparison set.

---

## 6.3 Stage C: custom domain corpus

The tutor should specialize in:

```text
Python fundamentals
machine-learning fundamentals
LLM foundations
tokenization
embeddings
attention
Transformers
training loops
pretraining
continued pretraining
SFT
DPO
evaluation
```

### Target size

```text
46M model:    5M–20M reviewed domain tokens
360M model:  25M–100M reviewed domain tokens
```

### Acceptable sources

Collect only material you are allowed to use:

- your own course scripts;
- your own notes;
- openly licensed documentation;
- openly licensed tutorials;
- openly licensed textbooks;
- public-domain material;
- reviewed synthetic explanations;
- reviewed question-answer examples;
- reviewed glossary entries;
- reviewed worked Python examples.

### Domain text format

Use one JSONL record per document:

```json
{"id":"python_lists_001","source":"matcode_notes","license":"owned","topic":"python/lists","text":"A Python list is an ordered collection..."}
```

### Review rule

No synthetic text enters the final corpus automatically.

Use this process:

```text
generate draft
→ run factual checks
→ remove duplication
→ simplify wording
→ human review
→ approve
→ add provenance metadata
```

---

## 6.4 Stage D: A100 stretch corpus

For the 360M model, use broader pretraining data.

### Minimum validation recipe

```text
FineWeb-Edu streamed sample:        750M–900M tokens
BabyLM-2026-Strict:                 100M tokens
Reviewed educational domain text:   25M–50M tokens
Total:                              approximately 1B tokens
```

### Better-quality recipe

```text
FineWeb-Edu streamed sample:        2.8B–6.5B tokens
BabyLM-2026-Strict:                 100M tokens
Reviewed educational domain text:   50M–100M tokens
Optional clean expository corpus:   reviewed and licence-audited
Total:                              approximately 3B–7B tokens
```

### 1.28B upper-bound model

Do not train a 1.28B model on only 100M tokens and claim success. Use:

```text
Smoke test:       2B–5B tokens
Serious run:     10B–30B+ tokens
```

This is an advanced experiment with a separate budget.

---

# 7. Post-training datasets

## 7.1 8M model post-training

Keep it narrow. Post-training is optional for the first warm-up.

### Recommended demonstration mix

```text
TinyStoriesInstruct:                 1K–5K examples
Custom simple tutor prompts:         500–2K examples
```

Goal:

- prove chat formatting;
- show that a base completer can learn a response pattern;
- avoid pretending the 8M model is a general assistant.

---

## 7.2 46M flagship SFT dataset

Use a small, high-quality mix.

| Source | Target examples | Role |
|---|---:|---|
| Custom MatGPT tutor conversations | 8K–20K | Main behavior and domain expertise |
| Filtered English OASST1 conversations | 5K–10K | Human-authored assistant behavior |
| Filtered Smol-SmolTalk conversations | 5K–15K | Short assistant-style examples for small models |
| Optional filtered UltraChat | 2K–5K | Extra diversity only if useful |

### Filtering rules

Keep examples that are:

- English;
- short enough for the model context;
- clear;
- factual;
- beginner-friendly;
- free from unnecessary complexity;
- free from long reasoning traces;
- free from unsafe content unless deliberately used as a refusal example;
- aligned with a concise tutor style.

Reject examples that contain:

- long advanced mathematics;
- long code dumps;
- unsupported factual claims;
- excessively verbose responses;
- hidden chain-of-thought style reasoning;
- duplicate or near-duplicate prompts;
- malformed chat roles;
- very long conversations that crowd out useful training signal.

### Chat schema

```text
<|system|>
You are MatGPT-Tiny, a patient beginner-friendly tutor.
<|user|>
Explain tokenization simply.
<|assistant|>
Tokenization is the process of splitting text into smaller pieces called tokens.
<|end|>
```

Use assistant-only loss masking during SFT.

---

## 7.3 Preference tuning dataset

Use DPO after SFT.

| Source | Target pairs | Role |
|---|---:|---|
| Custom MatGPT preference pairs | 1K–3K | Tutor style and factual humility |
| Filtered UltraFeedback Binarized | 500–2K | Additional generic preference patterns |

### Pair format

```json
{
  "prompt": "Explain embeddings simply.",
  "chosen": "Embeddings are lists of numbers that represent information. Similar words often have similar embeddings.",
  "rejected": "Embeddings are multidimensional latent manifolds generated through complex representational transformations."
}
```

Prefer answers that are:

- correct;
- simple;
- direct;
- concise;
- honest;
- safe;
- well structured.

Reject answers that are:

- factually wrong;
- overly technical;
- repetitive;
- verbose;
- unsafe;
- fabricated;
- poorly formatted.

### Optional ORPO comparison

DPO should remain the primary course demonstration. Add ORPO as an optional advanced comparison because it avoids a separate reference model during optimization.

---

# 8. Data preparation pipeline

The data pipeline is as important as the model.

## 8.1 Directory layout

```text
matgpt/
├── configs/
│   ├── matgpt_mini_8m.yaml
│   ├── matgpt_tiny_46m.yaml
│   ├── matgpt_a100_360m.yaml
│   └── matgpt_a100_xl_1_28b.yaml
├── data/
│   ├── raw/
│   ├── normalized/
│   ├── filtered/
│   ├── deduped/
│   ├── tokenized/
│   ├── manifests/
│   └── shards/
├── tokenizer/
├── checkpoints/
│   ├── pretrain/
│   ├── midtrain/
│   ├── sft/
│   └── dpo/
├── eval/
├── logs/
├── scripts/
└── notebooks/
```

## 8.2 Create a corpus manifest

Every data source must be logged.

```json
{
  "dataset_name": "BabyLM-community/BabyLM-2026-Strict",
  "version_or_commit": "PIN_THE_COMMIT_HASH",
  "license": "MIT",
  "stage": "base_pretraining",
  "language": "en",
  "download_date": "YYYY-MM-DD",
  "document_count": 0,
  "raw_bytes": 0,
  "token_count": 0,
  "notes": "Detoxified 100M-token BabyLM 2026 strict corpus."
}
```

## 8.3 Normalize text

Apply deterministic normalization:

- Unicode normalization (`NFKC` unless a source requires preservation);
- normalize line endings;
- remove invalid control characters;
- collapse excessive blank lines;
- strip leading and trailing whitespace;
- preserve paragraph boundaries;
- append an end-of-document token between documents.

Do not aggressively lowercase text. Preserve capitalization and punctuation.

## 8.4 Filter

For collected corpora, remove:

- empty records;
- extremely short fragments;
- boilerplate navigation text;
- pages dominated by URLs;
- pages dominated by punctuation;
- repeated headers and footers;
- obvious spam;
- binary garbage;
- malformed encoding;
- documents outside the intended language;
- personally identifying data where it should not be retained.

For TinyStories and BabyLM, preserve the official baseline version first. Apply custom filters only in a separate experimental variant so comparisons remain meaningful.

## 8.5 Deduplicate

Perform:

1. exact document hashing;
2. normalized exact hashing;
3. optional near-duplicate detection using MinHash or SimHash;
4. prompt deduplication for SFT and DPO;
5. train-validation leakage checks.

## 8.6 Split deterministically

Split by document hash, not random row order:

```text
train:      98%
validation:  1%
test:        1%
```

For datasets with official splits, preserve the official split.

## 8.7 Train the tokenizer

Train the tokenizer only on the training corpus.

### Tokenizer recommendations

| Model | Tokenizer vocab |
|---|---:|
| 8M TinyStories warm-up | 8,192 |
| 46M flagship | 16,384 |
| 360M A100 stretch | 32,768 |
| 1.28B upper bound | 32,768–65,536 |

Reserve:

```text
<|pad|>
<|bos|>
<|eos|>
<|system|>
<|user|>
<|assistant|>
<|end|>
```

Record:

- vocabulary size;
- tokenizer algorithm;
- special-token IDs;
- training-data sample hash;
- compression ratio;
- average tokens per document;
- encode-decode round-trip tests.

## 8.8 Tokenize once and shard

Do not tokenize every epoch.

For vocabulary sizes below 65,536, store token IDs as `uint16`.

Recommended shard structure:

```text
data/shards/babylm_train_00000.bin
data/shards/babylm_train_00001.bin
data/shards/babylm_val_00000.bin
data/shards/metadata.json
```

Pack sequences efficiently:

```text
document 1 tokens + <|eos|>
document 2 tokens + <|eos|>
document 3 tokens + <|eos|>
...
```

Sample fixed-length windows from the packed stream.

---

# 9. Training implementation strategy

Use two layers of implementation.

## Layer A — validation harness

Build a reliable practical harness first:

- PyTorch;
- Hugging Face `datasets`;
- Hugging Face `tokenizers` or SentencePiece;
- `safetensors`;
- `accelerate`;
- `bitsandbytes` when memory savings are useful;
- TRL for SFT and DPO;
- `lm-evaluation-harness` for optional benchmark checks;
- a simple notebook chat loop.

Initialize the model from random weights.

## Layer B — teaching implementation

After validation, produce a plain-PyTorch educational implementation that reveals:

- embeddings;
- RoPE;
- causal mask;
- Q, K, and V projections;
- multi-head attention;
- residual connections;
- normalization;
- MLP;
- logits;
- cross-entropy;
- sampling.

Use Andrej Karpathy's `nanochat`, `nanoGPT`, and `microgpt` as references for clarity and pipeline shape, but keep your course implementation independently understandable.

---

# 10. Training stages

## Stage 0 — Environment smoke test

Before a real run:

```text
print GPU name
print CUDA version
print PyTorch version
print available VRAM
mount persistent storage
set deterministic seed
write run configuration
run one forward pass
run one backward pass
save checkpoint
reload checkpoint
generate sample text
```

## Stage 1 — Tokenizer validation

Check:

- special tokens;
- encode-decode round trip;
- common English words;
- technical words;
- punctuation;
- multiline text;
- chat template tokens;
- compression ratio.

## Stage 2 — Base pretraining

Objective:

```text
predict the next token given previous tokens
```

Use:

```text
AdamW
cross-entropy loss
gradient clipping
warm-up
cosine learning-rate decay
mixed precision
gradient accumulation
validation intervals
sample generation intervals
checkpoint intervals
```

## Stage 3 — Continued pretraining / mid-training

Continue next-token training on:

```text
reviewed Python + ML + LLM textbook corpus
```

Use a lower learning rate than base pretraining.

## Stage 4 — SFT

Train on assistant conversations:

```text
system → user → assistant
```

Mask loss so the model learns primarily from assistant tokens.

## Stage 5 — DPO

Optimize preferred responses over rejected responses.

Run this only after SFT is stable.

## Stage 6 — Evaluation

Compare:

```text
random initialization
base pretrained checkpoint
mid-trained checkpoint
SFT checkpoint
DPO checkpoint
```

## Stage 7 — Interactive inference

Use a notebook-based chat loop first. Add a lightweight Gradio UI later.

---

# 11. Hyperparameter starting points

These are starting points. Benchmark the actual GPU before committing to a long run.

## 11.1 MatGPT-Mini 8M on T4

| Setting | Starting value |
|---|---:|
| Sequence length | 256, then 512 |
| Micro-batch size | 16 at 256; benchmark at 512 |
| Gradient accumulation | 8–16 |
| Effective tokens per update | Aim for 16K–64K |
| Optimizer | AdamW |
| Peak learning rate | 5e-4 |
| Betas | (0.9, 0.95) |
| Weight decay | 0.1 |
| Warm-up | 2% |
| Schedule | Cosine decay or constant for controlled comparison |
| Gradient clipping | 1.0 |
| Precision | FP16 |
| Initial token target | 20M–30M |
| Main token target | 50M–100M |

## 11.2 MatGPT-Tiny 46M on T4

| Setting | Starting value |
|---|---:|
| Sequence length | 512 |
| Micro-batch size | 4 |
| Gradient accumulation | 16 |
| Effective tokens per update | 32,768 |
| Optimizer | AdamW; switch to 8-bit AdamW if useful |
| Peak learning rate | 3e-4 |
| Betas | (0.9, 0.95) |
| Weight decay | 0.1 |
| Warm-up | 3% |
| Schedule | Cosine decay |
| Gradient clipping | 1.0 |
| Precision | FP16 |
| Dropout | 0.0 with sufficient data; otherwise test 0.1 |
| Initial token target | 100M |
| Better-quality target | 150M–300M |
| Checkpoint interval | Every 5M–10M tokens |
| Eval interval | Every 1M–5M tokens |

## 11.3 MatGPT-A100 360M on A100 80GB

| Setting | Starting value |
|---|---:|
| Sequence length | 1,024 |
| Micro-batch size | Benchmark 8–16 |
| Gradient accumulation | Choose for 128K–512K effective tokens/update |
| Optimizer | Fused AdamW or 8-bit AdamW |
| Peak learning rate | 2e-4 to 3e-4 |
| Betas | (0.9, 0.95) |
| Weight decay | 0.1 |
| Warm-up | 2%–3% |
| Schedule | Cosine decay |
| Gradient clipping | 1.0 |
| Precision | BF16 |
| Activation checkpointing | Optional initially; enable if needed |
| Validation token target | 1B |
| Better-quality target | 3B–7B |

## 11.4 Mid-training

| Setting | Value |
|---|---:|
| Starting checkpoint | Best base checkpoint |
| Corpus | Reviewed domain corpus |
| Learning rate | Approximately 10%–30% of base-pretraining peak |
| Sequence length | 512 for T4; 1,024 for A100 |
| Epochs | Prefer token target over rigid epochs |
| Validation | Separate held-out domain split |

## 11.5 SFT

| Setting | 46M model starting point |
|---|---:|
| Learning rate | 1e-5 to 5e-5 |
| Epochs | 1–3 |
| Sequence length | 512–768 |
| Loss masking | Assistant tokens only |
| Evaluation | Fixed chat prompt suite |
| Checkpoint selection | Best held-out SFT loss plus manual chat review |

## 11.6 DPO

| Setting | 46M model starting point |
|---|---:|
| Starting checkpoint | Best SFT checkpoint |
| Pairs | 1.5K–5K |
| Epochs | 1 |
| Learning rate | Conservative: 5e-7 to 1e-5 |
| Evaluation | Compare SFT and DPO responses side by side |
| Failure signal | Degraded fluency, over-refusal, repetition, or verbosity collapse |

---

# 12. Checkpointing requirements

A resumable checkpoint must contain:

```text
model weights
optimizer state
scheduler state
gradient-scaler state
global update step
tokens processed
epoch or shard position
random-number-generator states
training configuration
tokenizer version
dataset-manifest hash
source-code commit hash
validation metrics
sample generations
```

Keep:

```text
latest checkpoint
best validation-loss checkpoint
milestone checkpoints
final model-only safetensors export
```

Do not keep every full optimizer checkpoint forever.

---

# 13. Evaluation plan

## 13.1 Tokenizer tests

Evaluate:

- average characters per token;
- average tokens per document;
- common English words;
- technical vocabulary;
- code snippets;
- punctuation;
- chat-role tokens;
- round-trip decoding;
- unknown-token behavior.

## 13.2 Base-model evaluation

Track:

```text
training loss
validation loss
perplexity
gradient norm
learning rate
tokens processed
tokens per second
peak VRAM
sample generations
repetition rate
```

Use fixed prompts:

```text
Once upon a time
The little dog wanted to
Python is a programming language that
A token is
An embedding is
The purpose of pretraining is
```

## 13.3 Domain evaluation

Create a held-out domain set with:

```text
50 definitions
30 explanation prompts
20 analogy prompts
20 Python examples
20 misconception-correction prompts
```

## 13.4 Chat evaluation

Create a fixed suite of 100 prompts.

Score each response from 1 to 5:

| Dimension | Meaning |
|---|---|
| Correctness | Is the answer technically accurate? |
| Relevance | Does it answer the question? |
| Clarity | Can a beginner understand it? |
| Conciseness | Is it appropriately brief? |
| Fluency | Does it read naturally? |
| Honesty | Does it avoid fabrication? |
| Safety | Is the guidance responsible? |
| Format adherence | Did it follow the requested format? |

Compare:

```text
base
vs.
mid-trained
vs.
SFT
vs.
DPO
```

## 13.5 Optional benchmarks

Use small subsets cautiously:

```text
BabyLM evaluation tasks
BLiMP-style grammatical checks
HellaSwag
ARC-Easy
TruthfulQA subset
```

Do not over-interpret benchmark scores from very small models. The central evaluation is whether each training stage improves the intended behavior.

---

# 14. Experiment sequence

Follow this order.

## Experiment 1 — Pipeline smoke test

```text
Model:        1M–3M
Data:         TinyStories subset
Tokens:       1M–5M
Goal:         Confirm end-to-end execution
```

## Experiment 2 — 8M warm-up

```text
Model:        MatGPT-Mini ~8M
Data:         TinyStories
Tokens:       50M–100M
Goal:         Produce coherent simple English
```

## Experiment 3 — 46M baseline

```text
Model:        MatGPT-Tiny ~46M
Data:         BabyLM-2026-Strict
Tokens:       100M
Goal:         Establish clean serious baseline
```

## Experiment 4 — 46M breadth upgrade

```text
Model:        Continue from the 46M baseline
Data:         50M–150M FineWeb-Edu tokens
Goal:         Improve educational breadth
```

## Experiment 5 — 46M domain mid-training

```text
Model:        Continue from best 46M base
Data:         5M–20M reviewed Python, ML, and LLM text
Goal:         Improve tutor-domain completions
```

## Experiment 6 — 46M SFT

```text
Model:        Continue from best mid-trained checkpoint
Data:         18K–45K filtered chat examples
Goal:         Convert completer into chatbot
```

## Experiment 7 — 46M DPO

```text
Model:        Continue from best SFT checkpoint
Data:         1.5K–5K preference pairs
Goal:         Improve style, simplicity, and honesty
```

## Experiment 8 — A100 stretch

```text
Model:        MatGPT-A100 ~360M
Data:         1B tokens first; 3B–7B later
Goal:         Demonstrate scaling and better chat behavior
```

## Experiment 9 — Optional A100-XL upper bound

```text
Model:        MatGPT-A100-XL ~1.28B
Data:         2B–5B token smoke test only at first
Goal:         Measure feasibility; do not make it a course dependency
```

---

# 15. Run ledger

Maintain a `runs.csv` or experiment-tracking database.

| Field | Example |
|---|---|
| `run_id` | `tiny46m_babylm100m_seed42_v1` |
| `model_config` | `configs/matgpt_tiny_46m.yaml` |
| `git_commit` | Commit hash |
| `tokenizer_hash` | SHA-256 |
| `dataset_manifest_hash` | SHA-256 |
| `seed` | `42` |
| `tokens_target` | `100000000` |
| `tokens_completed` | Updated continuously |
| `best_val_loss` | Metric |
| `checkpoint_path` | Persistent path |
| `status` | planned / running / passed / failed |
| `notes` | Observations |

Never overwrite an important result without preserving its metadata.

---

# 16. Repository deliverables

Before teaching, publish or internally freeze:

```text
README.md
TRAINING_PLAN.md
DATA_MANIFEST.md
MODEL_CARD_8M.md
MODEL_CARD_46M.md
MODEL_CARD_360M.md
configs/*.yaml
scripts/prepare_*.py
scripts/train_tokenizer.py
scripts/tokenize_and_shard.py
scripts/pretrain.py
scripts/midtrain.py
scripts/sft.py
scripts/dpo.py
scripts/evaluate.py
scripts/chat.py
notebooks/*.ipynb
tests/*.py
```

Minimum automated tests:

```text
tokenizer round trip
causal mask correctness
attention output shape
forward-pass shape
loss decreases on tiny overfit batch
checkpoint save/load equivalence
resume-training equivalence
generation stopping at EOS
chat-template rendering
assistant-only SFT masking
DPO data-format validation
```

---

# 17. Practical decisions to freeze now

Use these defaults unless experiments prove otherwise.

```text
Warm-up model:           ~8M parameters
Flagship model:          ~46M parameters
A100 stretch model:      ~360M parameters
A100 upper-bound model:  ~1.28B parameters

Warm-up corpus:          TinyStories
Flagship corpus:         BabyLM-2026-Strict
Breadth extension:       streamed FineWeb-Edu slice
Domain corpus:           reviewed MatCode Python, ML, and LLM textbooks
SFT corpus:              custom tutor chat + filtered OASST1 + filtered Smol-SmolTalk
DPO corpus:              custom preference pairs + filtered UltraFeedback Binarized

T4 precision:            FP16
A100 precision:          BF16
T4 context:              512
A100 context:            1,024 initially
Tokenizer vocab:         8K / 16K / 32K by model tier
Checkpointing:           mandatory and resumable
Primary alignment stage: DPO
Optional comparison:     ORPO
```

---

# 18. Licensing and provenance checklist

Record and verify licences before publishing models or redistributing processed data.

| Dataset | Intended use | Licence shown on dataset page |
|---|---|---|
| TinyStories | 8M warm-up pretraining | CDLA-Sharing-1.0 |
| BabyLM-2026-Strict | 46M core pretraining | MIT |
| FineWeb-Edu | Breadth extension | ODC-By; review Common Crawl and source-page considerations |
| OASST1 | Human-authored SFT examples | Apache-2.0 |
| Smol-SmolTalk | Small-model SFT examples | Apache-2.0 |
| UltraFeedback Binarized | DPO preference examples | MIT |

For your own corpus, store:

```text
source URL or internal source identifier
author or owner
licence
retrieval date
document hash
transformation history
approval status
```

---

# 19. Immediate execution checklist

## Phase 1 — Establish the repository

- [ ] Create the repository structure.
- [ ] Add YAML configuration files for the 8M, 46M, and 360M models.
- [ ] Add deterministic seed handling.
- [ ] Add checkpoint save/load tests.
- [ ] Add a run ledger.

## Phase 2 — Prepare the 8M warm-up

- [ ] Download and pin TinyStories.
- [ ] Train the 8K tokenizer.
- [ ] Tokenize once and shard to `uint16`.
- [ ] Run a 1M-token smoke test.
- [ ] Resume from checkpoint.
- [ ] Train to 50M–100M tokens.
- [ ] Save sample generations at fixed milestones.

## Phase 3 — Prepare the 46M baseline

- [ ] Download and pin BabyLM-2026-Strict.
- [ ] Train the 16K tokenizer on the selected flagship corpus.
- [ ] Tokenize and shard the corpus.
- [ ] Benchmark T4 throughput and VRAM.
- [ ] Run a 10M-token smoke test.
- [ ] Train to 100M tokens across resumable sessions.
- [ ] Evaluate the base checkpoint.

## Phase 4 — Improve the 46M model

- [ ] Stream and collect a 50M–150M-token FineWeb-Edu slice.
- [ ] Build a reviewed 5M–20M-token MatCode textbook corpus.
- [ ] Continue pretraining.
- [ ] Build and filter the SFT mix.
- [ ] Perform SFT with assistant-only loss.
- [ ] Build the preference-pair set.
- [ ] Perform one conservative DPO run.
- [ ] Compare all checkpoints using the fixed prompt suite.

## Phase 5 — Scale on A100

- [ ] Train the 32K tokenizer.
- [ ] Collect at least 1B pretraining tokens.
- [ ] Run the 360M configuration on one A100 80GB.
- [ ] Benchmark throughput and memory.
- [ ] Scale toward 3B–7B tokens only after the 1B run is stable.
- [ ] Treat the 1.28B configuration as a separate upper-bound experiment.

---

# 20. Final recommendation

Start immediately with this sequence:

```text
1. Train ~8M on TinyStories.
2. Freeze the working data loader, tokenizer pipeline, checkpoint format, and evaluator.
3. Train ~46M on BabyLM-2026-Strict.
4. Continue the 46M model on a small FineWeb-Edu slice and reviewed MatCode textbooks.
5. SFT the 46M model on custom tutor conversations plus filtered OASST1 and Smol-SmolTalk.
6. DPO the SFT checkpoint on custom preference pairs plus a small UltraFeedback subset.
7. Run the notebook chat interface and fixed evaluation suite.
8. Only then scale the same pipeline to ~360M on an A100 80GB.
9. Treat ~1.28B as an advanced feasibility experiment, not a course dependency.
```

This gives you a credible, teachable story:

> We first proved that language emerges in a tiny constrained model. We then trained a more serious English base model from random weights, specialized it, converted it into a chatbot, aligned its response style, evaluated every stage, and finally scaled the exact same pipeline on stronger hardware.

---

# References

1. [TinyStories dataset](https://huggingface.co/datasets/roneneldan/TinyStories)
2. [TinyStories paper](https://arxiv.org/abs/2305.07759)
3. [TinyStoriesInstruct dataset](https://huggingface.co/datasets/roneneldan/TinyStoriesInstruct)
4. [BabyLM-2026-Strict dataset](https://huggingface.co/datasets/BabyLM-community/BabyLM-2026-Strict)
5. [BabyLM Challenge](https://babylm.github.io/)
6. [FineWeb-Edu dataset](https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu)
7. [OASST1 dataset](https://huggingface.co/datasets/OpenAssistant/oasst1)
8. [Smol-SmolTalk dataset](https://huggingface.co/datasets/HuggingFaceTB/smol-smoltalk)
9. [UltraFeedback Binarized dataset](https://huggingface.co/datasets/HuggingFaceH4/ultrafeedback_binarized)
10. [TRL documentation](https://huggingface.co/docs/trl/index)
11. [TRL DPO Trainer](https://huggingface.co/docs/trl/dpo_trainer)
12. [bitsandbytes 8-bit optimizers](https://huggingface.co/docs/bitsandbytes/optimizers)
13. [NVIDIA A100 official product page](https://www.nvidia.com/en-us/data-center/a100/)
14. [Chinchilla scaling paper](https://arxiv.org/abs/2203.15556)
15. [Karpathy nanochat](https://github.com/karpathy/nanochat)
16. [Karpathy nanoGPT](https://github.com/karpathy/nanoGPT)
17. [Karpathy microgpt](https://karpathy.github.io/2026/02/12/microgpt/)
