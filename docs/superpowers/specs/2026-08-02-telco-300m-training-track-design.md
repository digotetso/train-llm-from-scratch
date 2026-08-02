# MatGPT Telco 300M Training Track Design

**Date:** 2026-08-02

**Status:** Approved in conversation; implementation requested

**Target:** A reproducible from-scratch English telecom/networking model that can be trained on one high-memory GPU and later deployed as a small, retrieval-grounded edge component.

## 1. Problem and outcome

The repository currently supports 8M and 59M educational base-pretraining runs. It does not have a production-minded path for assembling a legally traceable general-English and telecom corpus, training a roughly 300M parameter model, post-training it for grounded telecom assistance, or measuring it on the Open Telco benchmarks.

This project adds that path without using the user's private corpus. The implementation prepares and validates public data, trains a custom tokenizer, shards the resulting corpus, runs stage-gated 300M pretraining in Colab, and evaluates preserved checkpoints. The full 12B-token training run remains an operator-controlled GPU action; repository automation must never start it implicitly.

## 2. Success criteria

The implementation is accepted when:

1. A checked-in model configuration instantiates as 306,226,176 trainable parameters using the repository's current decoder-only Transformer.
2. Public source definitions distinguish general pretraining, telecom pretraining, structured networking material, post-training data, RAG-only standards mirrors, and evaluation-only assets.
3. The corpus builder can stream a deterministic, bounded pilot from approved Hugging Face sources without downloading either full upstream corpus.
4. Every normalized document retains source, collection, license, and stable identifier metadata in the corpus manifest.
5. Source quotas are deterministic, are verified against the configured token plan, and cap patents and duplicated standards language.
6. `GSMA/ot-lite`, `GSMA/ot-full`, and configured contamination phrases cannot enter tokenizer fitting or pretraining.
7. The tokenizer report measures general and telecom token fertility, including a fixed set of telecom and networking terms.
8. The stage-gated Colab notebook supports `prepare_data`, `prepare`, `smoke`, `pilot`, `full`, and `evaluate` on the RTX PRO 6000 and other CUDA GPUs with sufficient memory.
9. `prepare_data` and `prepare` are bounded and cannot start pretraining; `full` remains an explicit manual choice.
10. Evaluation compares checkpoints using validation loss/perplexity, fixed generation prompts, repetition/consistency tests, and Open Telco task adapters.
11. Tests cover source validation, quota allocation, deterministic sampling, metadata preservation, benchmark exclusion, configuration size, and notebook stage gates.
12. Documentation tells the operator which assets are safe for pretraining, post-training, RAG, and evaluation, and records unresolved upstream-license obligations.

## 3. Scope

### Included

- A MatGPT Telco 300M YAML configuration.
- A public-data source registry with pinned revisions where available.
- Deterministic streaming and normalization for a small pilot and the 12B-token target mixture.
- Cross-source exact deduplication and contamination hooks compatible with the existing quality pipeline.
- Tokenizer fitting and telecom-fertility reporting.
- Reuse of the existing sharding, preflight, training, checkpoint, and checkpoint-comparison machinery.
- A dedicated Colab notebook and runbook for high-memory CUDA GPUs.
- Open Telco evaluation loading and local JSONL materialization.
- Provenance, license, mixture, and run manifests.

### Excluded

- Running the complete 12B-token training job as part of repository verification.
- Copying or depending on the user's private telecom corpus.
- Treating the unpublished OTel 2.0 440B-token processed mixture as available training data.
- Automatically generating OTel 2.0 synthetic data through a hosted endpoint.
- A full production RAG service, vector database, or network-change agent.
- Automatic application of generated configurations to live networks.
- Depending on Open Telco tools that are still marked as coming soon.

## 4. Approaches considered

### A. Fine-tune the existing OTel 270M model

This is the fastest route to a small telecom assistant and is the strongest operational baseline. It does not meet the course objective of teaching from-scratch pretraining and inherits the upstream Gemma model terms and tokenizer.

### B. Train from scratch only on telecom text

This is simple but likely to produce brittle English, patent-like prose, and excessive 3GPP committee language. It would also make general instruction tuning harder at 300M parameters.

### C. Train a mixed English/telecom model from scratch, then apply OTel post-training

This is the selected approach. It preserves the educational goal, provides a credible general-English base, makes domain strength measurable, and uses OTel assets in the roles for which they were released. OTel 270M remains a control model and OTel 2.0 remains an optional pinned teacher after the base and public-data post-training paths are reproducible.

## 5. Model design

The initial architecture follows the repository's readable GPT implementation:

| Field | Value |
|---|---:|
| Vocabulary | 32,768 byte-level BPE tokens |
| Context length | 2,048 |
| Layers | 20 |
| Attention heads | 16 |
| Hidden size | 1,024 |
| Feed-forward size | 3,072 |
| Activation | SwiGLU |
| Normalization | RMSNorm |
| Position encoding | RoPE |
| Embeddings | Tied |
| Linear bias | Disabled |
| Dropout | 0.0 |
| Parameter count | 306,226,176 |

BF16 is the default precision for Blackwell, Ampere, and newer GPUs. The first implementation retains multi-head attention to stay compatible with the current teaching model. Grouped-query attention is a later edge-inference optimization and is not required to validate the 300M training recipe.

## 6. Data design

### 6.1 Asset classes

Every source is assigned exactly one primary role:

- `pretrain_general`: openly licensed or public-domain general English.
- `pretrain_telecom`: document-level traceable telecom material.
- `pretrain_structured`: permissively licensed network code, configuration, APIs, and technical documentation.
- `posttrain`: instruction, preference, retrieval, reranking, or abstention supervision.
- `rag_only`: standards mirrors whose upstream terms require separate review before model training.
- `evaluation_only`: benchmarks that must never enter training or tokenizer fitting.

The initial registry contains:

- `common-pile/comma_v0.1_training_dataset` for general English.
- `GSMA/Telco-Common-Corpus` for telecom pretraining.
- Allowlisted permissive networking collections for structured material.
- `HuggingFaceTB/smol-smoltalk`, `farbodtavakkoli/OTel-LLM`, and `farbodtavakkoli/OTel-Safety` for later post-training.
- GSMA standards mirrors and telecom knowledge graphs as RAG-only assets.
- `GSMA/ot-lite` and `GSMA/ot-full` as evaluation-only assets.

### 6.2 Token plan

The effective 12B-token plan has two stages:

| Stage | General | Telecom | Structured | Total |
|---|---:|---:|---:|---:|
| Main | 6.5B | 3.0B | 0.5B | 10.0B |
| Cooldown | 1.2B | 0.7B | 0.1B | 2.0B |
| Total | 7.7B | 3.7B | 0.6B | 12.0B |

The telecom quota is stratified as follows:

- 35% 3GPP preparatory documents.
- 30% RFC specifications, drafts, preparatory material, and proceedings.
- 25% open-access research.
- At most 8% patents.
- Approximately 2% Wikipedia, Wikidata, and semantic material.

The pilot uses the same proportions at a configurable smaller token budget. Dataset streaming stops when the normalized token estimate reaches each source quota. Actual tokenizer counts are calculated after tokenizer fitting; quota variance outside the configured tolerance fails preparation.

### 6.3 Determinism and metadata

Sampling is driven by the run seed and stable document identifiers, not upstream streaming order alone. Normalized rows include:

- `text`
- `source_id`
- `collection`
- `document_id`
- `license`
- `role`
- `stage`
- `content_sha256`

The manifest records source revisions, requested quotas, observed documents and bytes, filtering counts, exact duplicates, contamination removals, and final token counts.

### 6.4 Rights and contamination controls

Only sources marked `pretrain_*` may flow into tokenizer fitting and pretraining. `rag_only`, `posttrain`, and `evaluation_only` sources are rejected at the corpus-builder boundary.

The benchmark denylist includes repository identifiers and content-derived contamination patterns for Open Telco tasks. Exact hash matching is supplemented by configured phrase matching. Near-duplicate benchmark checks are performed during evaluation asset materialization and reported separately; they do not silently delete source documents without evidence.

## 7. Components and boundaries

### Source registry

A checked-in YAML file defines source identity, Hugging Face dataset/config/split, revision, role, license policy, text field mapping, collection mapping, and quota weight. Schema validation rejects missing revisions for serious runs, unknown roles, negative weights, and evaluation assets in a training plan.

### Mixture planner

A pure Python module converts stage token budgets and source weights into integer quotas. It is deterministic, preserves totals exactly, and emits a machine-readable plan used by preparation and later verification.

### Streamed corpus builder

A command-line script loads approved sources in streaming mode, maps source-specific rows into the normalized schema, applies existing quality filters, performs exact deduplication, and stops at quotas. It writes normalized JSONL and a manifest compatible with existing tokenizer and shard commands.

Network failures, schema drift, missing license metadata, empty text, and exhausted sources are explicit failures. Partial output is written to a staging directory and promoted only after validation.

### Tokenizer report

The existing tokenizer training remains authoritative. Its report is extended with fertility statistics for fixed general-English and telecom probe sets. A tokenizer that cannot round-trip probes or produces invalid IDs fails preflight.

### Colab notebook

The new notebook reuses the proven stage-gated pattern while using a dedicated run name and Drive directory. It detects CUDA rather than requiring a particular GPU name, prints GPU and disk evidence, and applies minimum-memory warnings appropriate to 300M training.

The stage behavior is:

- `prepare_data`: build a bounded pilot corpus or materialize a previously approved full mixture.
- `prepare`: train/verify tokenizer, shard data, run preflight, and benchmark the configured batch.
- `smoke`: finite updates plus resume verification.
- `pilot`: a bounded token target sufficient to inspect loss, throughput, samples, and memory.
- `full`: explicit 12B-token schedule; never selected automatically.
- `evaluate`: compare preserved checkpoints and run configured task suites.

### Evaluation adapter

A script downloads selected Open Telco configurations and materializes repository-compatible multiple-choice JSONL without adding them to training manifests. Generation and judge-based evaluations retain checkpoint identity, decoding seed, benchmark revision, and prompt-template version.

## 8. Validation strategy

Development follows test-driven changes. The cheapest reliable tests cover:

- Registry schema and role enforcement.
- Exact quota arithmetic and deterministic plans.
- Source-row normalization with synthetic fixtures.
- Metadata and license preservation.
- Contamination and evaluation-only rejection.
- Staged-output promotion and failure cleanup.
- The exact 306,226,176 parameter count.
- Notebook stage names, CUDA checks, Drive paths, and non-promotion guarantees.
- Open Telco JSONL conversion with local fixtures rather than network access.

Broader verification runs the full repository test suite, model report, notebook JSON parsing, and a local synthetic end-to-end corpus-to-shard smoke path. Real Hugging Face access, GPU allocation, throughput, and the full dataset remain notebook preflight evidence rather than unit-test claims.

## 9. Evaluation and release gates

The final model is compared with its base checkpoints, Gemma 3 270M-IT, and OTel-LLM-270M-IT. Promotion evidence includes:

- General and telecom validation loss/perplexity.
- Open Telco development and final benchmark results.
- Three fixed decoding seeds.
- Fifty blinded LLM-judge stories or technical responses per checkpoint where judge evaluation applies.
- Repetition, contradiction, entity confusion, and consistency rates.
- Grounded-answer correctness and unsupported-answer rate.
- Abstention precision and recall.
- BF16 versus deployment-quantized quality change.

Automated judging is the primary research workflow. It is not sufficient authority for live network changes. Operational deployment requires retrieval traceability, output-schema validation, dry-runs, permissions, audit logging, rollback, and an expert review policy proportional to blast radius.

## 10. Rollout and rollback

Implementation lands as additive files and narrow extensions to existing modules. The 8M and 59M configurations and notebook behavior remain unchanged. Every new feature is disabled unless the 300M configuration or telecom corpus command is selected.

Rollback is deletion of the new configuration, registry, notebook, runbook, and additive modules. No existing artifact format is destructively migrated. Prepared data and checkpoints use a new run directory and cannot overwrite prior models.

## 11. Residual risks

- Upstream datasets can change schemas or revisions; serious runs must pin revisions and persist manifests.
- Document-level licensing metadata reduces but does not eliminate the need for release review.
- The structured 0.6B-token source set may be smaller than planned under a strict permissive allowlist; the builder must fail or explicitly rebalance rather than silently repeat excessive data.
- A 300M model has a real reasoning ceiling. RAG and deterministic validation are required for serious telecom use.
- Open Telco benchmark knowledge overlaps with the same public standards used for legitimate pretraining. Exact question leakage can be prevented, but topical overlap is expected and must be disclosed.
- Colab runtime and storage limits may require resumable multi-session training even on a suitable GPU.
