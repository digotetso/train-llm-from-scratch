# Telco 300M Local Tokenizer and Corpus Build Design

**Date:** 2026-08-09

**Status:** Approved in conversation; pending written-spec review

**Extends:** `2026-08-02-telco-300m-training-track-design.md`

## 1. Decision

Build a second 32,768-token byte-level BPE tokenizer from a deterministic,
representative 200M-token sample. Compare it with the existing 20M-pilot
tokenizer on a shared held-out set and fixed telecom probes. Freeze the better
tokenizer only after explicit review.

After the tokenizer is frozen, prepare the 12B-token corpus on the operator's
24GB-RAM Mac using a chunked, resumable, one-pass pipeline. The pipeline writes
small immutable artifacts locally, publishes them into Google Drive's streamed
filesystem, and releases the local working files. It never starts model
training.

## 2. Why this work is necessary

The existing pilot proved that the source registry, mixture, model, checkpoint,
and evaluation paths work. It did not establish that a tokenizer fitted on only
20M tokens is the most efficient choice for a serious 12B-token run.

The existing full corpus path is also not operationally suitable for this
scale. It performs an `any(pattern in text ...)` scan over 18,171 contamination
patterns for every document, calls the tokenizer per document, materializes
large monolithic JSONL files through the Drive mount, later tokenizes the corpus
again for audit, and tokenizes it a third time for sharding. It provides no
useful progress or resumable unit. Interrupted Colab attempts therefore leave
staging folders and restart from zero.

The revised path must improve performance and recoverability without weakening
source, license, contamination, deduplication, quota, or artifact-compatibility
controls.

## 3. Goals and non-goals

### Goals

1. Produce a representative 200M-token tokenizer-fitting sample from the same
   pinned pretraining sources and combined 12B role proportions.
2. Train a candidate with the same 32,768 vocabulary size, byte-level BPE
   algorithm, and special tokens as the existing tokenizer.
3. Compare both tokenizers on data excluded from both fitting sets.
4. Make tokenizer selection explicit, reviewable, and fingerprinted.
5. Prepare exact tokenizer-measured main and cooldown quotas without holding the
   complete corpus locally.
6. Preserve normalized text, provenance, document-level license evidence,
   quality-filter counts, token shards, and cryptographic checksums.
7. Show source, quota, throughput, elapsed time, ETA, disk use, and publication
   progress at least every 30 seconds.
8. Resume safely from the last committed unit after process, network, or machine
   interruption.
9. Keep the local preparation working set below 20GiB and pause before free disk
   falls below a configured safety floor.
10. Keep the existing Colab GPU training path compatible with finalized binary
    shards.

### Non-goals

- Training the 300M model on the Mac.
- Automatically selecting or starting the full 12B pretraining run.
- Changing the 12B mixture, model architecture, vocabulary size, source roles,
  evaluation assets, or post-training plan.
- Deleting the existing pilot artifacts or incomplete Drive staging folders.
- Weakening contamination checks to gain speed.

## 4. Tokenizer sample and comparison

### 4.1 Representative fitting sample

The sample target is 200M estimated tokens. It uses the combined full-run role
proportions:

| Role | Tokens | Share |
|---|---:|---:|
| General English | 128.333M | 64.167% |
| Telecom/networking | 61.667M | 30.833% |
| Structured/code | 10.000M | 5.000% |

Existing source weights and telecom bucket weights divide these role quotas.
Because a tokenizer is required to count exact tokens, bootstrap sampling uses
the registry's source estimates or normalized character estimate. This is only
for fitting-data selection; the later 12B corpus uses exact counts from the
frozen tokenizer.

The existing stable hash-based validation rule remains active. Documents
assigned to the tokenizer comparison holdout never enter either candidate's
fitting input. Evaluation-only, post-training, and RAG-only sources remain
ineligible. Open Telco content-derived patterns are excluded from fitting.

### 4.2 Candidate identity

The candidate retains:

- byte-level BPE;
- vocabulary size 32,768;
- the current ordered special-token list;
- deterministic training seed and normalized input order;
- tokenizer JSON, metadata, fitting-sample manifest, source revisions, and
  checksums.

The existing pilot tokenizer is baseline `pilot_20m`. The new tokenizer is
candidate `representative_200m`. Neither artifact is overwritten.

### 4.3 Comparison report

Both tokenizers process the identical held-out documents and fixed probe sets.
The report includes:

- round-trip correctness and invalid/unknown-token failures;
- total tokens and bytes per token overall;
- tokens per whitespace word and p50/p95 fragmentation;
- results by general, telecom, structured, source, and telecom bucket;
- token pieces for fixed telecom terms and identifiers;
- estimated sequence-length and 12B-run compression impact;
- tokenizer and evaluation-input fingerprints.

The 200M candidate is eligible only if all round-trip and special-token gates
pass, telecom held-out token count does not regress, general held-out token count
does not regress by more than 1%, and probe fragmentation does not materially
worsen. The report recommends replacement when overall held-out token count
improves by at least 1% or telecom token count improves by at least 2% without a
guardrail failure. Selection remains an explicit operator decision.

Selecting the new tokenizer invalidates the old pilot checkpoint for promotion.
The 20M pilot preparation, smoke, pilot, and evaluation gates must then be
repeated under the new tokenizer fingerprint before full training approval.

## 5. Local one-pass corpus architecture

### 5.1 Components

The implementation has five boundaries:

1. **Approved source reader:** streams pinned Hugging Face revisions and maps
   source rows into the existing normalized schema.
2. **Quality and quota engine:** applies minimum-length checks, exact dedup,
   fast multi-pattern contamination matching, deterministic validation
   assignment, and per-item quotas.
3. **Frozen tokenizer and shard writer:** batch-encodes accepted documents once,
   counts quota tokens before EOS, and writes the existing uint16, 50M-token
   training shard format with EOS document boundaries.
4. **Journal and manifest store:** records resumable cursors, committed document
   hashes, quota counters, artifact checksums, configuration fingerprints, and
   progress.
5. **Drive publisher:** moves only closed, checksummed files into a Drive
   staging namespace and never exposes a complete manifest until all validation
   succeeds.

### 5.2 Files and storage

Normalized text is retained as bounded JSONL chunks rather than monolithic
`main.jsonl` and `cooldown.jsonl`. Binary training output remains compatible
with the current 50M-token uint16 format, approximately 100MB per complete
shard. Validation remains a separate split.

The local workspace contains only:

- the active `.partial` text and token chunks;
- a bounded publication spool;
- the exact-dedup database and resume journal;
- tokenizer and small manifests.

Closed artifacts move into the mounted Drive `My Drive/matgpt_artifacts` tree.
Drive remains in **Stream files** mode. The builder checks real filesystem free
space before opening each unit and pauses with a recoverable status when the
configured floor would be crossed. It does not assume that Drive immediately
evicts its upload cache.

### 5.3 Commit and resume protocol

A unit is committed as follows:

1. Process deterministic input rows into local `.partial` files while holding
   that unit's pending hashes and counters outside the committed state.
2. Close, flush, and checksum the files.
3. Atomically rename them to immutable local names.
4. Commit hashes, counters, input cursor, and artifact metadata in one journal
   transaction.
5. Copy/move the immutable files to the Drive staging namespace.
6. Re-read size and checksum through the mounted destination. This proves the
   File Provider copy; remote-cloud synchronization remains a separate status
   that must be complete before Colab consumes the artifact.
7. Mark the unit published and release the local sealed copy.

On restart, the builder verifies all recipe, source-revision, tokenizer,
contamination, and format fingerprints. It discards uncommitted `.partial`
files, reconciles committed artifacts by checksum, and resumes from the last
committed cursor. A changed fingerprint refuses resume rather than silently
mixing artifacts.

Exact deduplication uses a persistent exact store, not a probabilistic Bloom
filter. The contamination matcher must return the same accept/reject decisions
as the current reference implementation on identical input.

## 6. Operator workflow

A tested CLI is authoritative. A thin local notebook provides the familiar
stage selector without duplicating data logic.

The stages are:

1. `tokenizer_sample`: build/resume the 200M fitting sample and holdout.
2. `tokenizer_candidate`: train the 200M candidate and write its report.
3. `tokenizer_compare`: compare candidate and pilot tokenizers; never select
   automatically.
4. `pilot_refresh`: after explicit selection, reuse the existing 20M pilot only
   when `pilot_20m` wins and all fingerprints verify; rebuild and validate the
   pilot when `representative_200m` wins.
5. `full_calibration`: prepare the first real 100M tokens of the full recipe,
   publish them, report measured ETA, then stop cleanly.
6. `full_resume`: resume the same artifact identity to 12B after explicit review.

The first 100M full tokens are not a throwaway benchmark. They become the first
committed part of the final corpus. The execution stop limit is not part of the
recipe identity, so continuing does not change fingerprints.

After all 12B quotas and validation checks pass, the publisher writes the final
complete manifest. The Colab notebook then restores the frozen tokenizer and
ready binary shards from Drive, runs preflight/benchmark evidence, and requires
manual `FULL_APPROVED=True` before GPU training.

## 7. Observability and evidence

Human-readable progress and machine-readable progress JSON include:

- stage, source, bucket, and current input cursor;
- requested and accepted tokens for the current item and whole stage;
- documents read, accepted, held out, deduplicated, contaminated, and rejected;
- current and rolling tokens/second;
- elapsed time and ETA based on rolling production rate;
- active local bytes, free disk, queued publication bytes, and published bytes;
- most recent committed unit and Drive verification result.

The 100M calibration report records wall time, CPU use, peak memory, network
wait, tokenizer throughput, contamination throughput, publication throughput,
and projected 12B completion time. If projection exceeds 48 hours or local disk
backpressure cannot recover safely, the operator stops and chooses further
optimization or a persistent CPU VM.

## 8. Failure handling

- Network reads use bounded retry with backoff and retain the last committed
  cursor.
- Dataset schema, collection, or license drift fails visibly.
- Exhausting a source before quota fails; it never silently rebalances.
- Drive unavailability pauses publication before the local spool limit is
  exceeded.
- Hash mismatch quarantines the destination artifact and refuses completion.
- Insufficient disk pauses safely before opening another unit.
- `SIGINT` requests a clean stop at the next commit boundary; forced termination
  is recovered through the journal.
- Only a final complete manifest makes the corpus eligible for Colab training.

## 9. Verification strategy

Implementation follows test-driven development. Required tests include:

1. A deterministic 200M-plan fixture with exact combined role/source totals.
2. Holdout isolation from both tokenizer fitting sets.
3. Candidate comparison arithmetic, hard gates, and recommendation rules.
4. Fast contamination matching equivalent to the current reference matcher.
5. Batch tokenization equivalent to per-document tokenization and EOS behavior.
6. Chunked output reconstructing the same normalized record and token order as
   an uninterrupted reference build.
7. Interruption at each commit step followed by byte-identical resume.
8. Fingerprint mismatch refusing unsafe resume.
9. Disk-floor and publication-spool backpressure.
10. Destination size/checksum mismatch refusing publication.
11. Exact deduplication across sources, chunks, main, cooldown, and resume.
12. Synthetic source exhaustion, network retry, schema drift, and license
    failures.
13. Existing pilot, Colab, sharding, evaluation, and full repository regression
    suites.

Real Hugging Face streaming and Drive File Provider behavior are integration
evidence from the 200M sample and 100M calibration, not unit-test claims.

## 10. Rollout and rollback

The work is additive until the tokenizer selection decision. Existing pilot
artifacts remain preserved and the original Colab training stages remain gated.
The local builder publishes to a new fingerprinted staging namespace.

Rollback before selection is deletion of the new candidate and staging output.
Rollback after selecting the candidate means restoring the explicit selection
record to `pilot_20m`, rebuilding any dependent full artifacts, and never
combining shards produced by different tokenizer fingerprints.

Old incomplete `.full.staging-*` directories are outside implementation scope.
They may be removed only after the operator confirms that no active preparation
process depends on them.

## 11. Acceptance criteria

The implementation is ready for the operator's 200M run when:

- the candidate workflow and comparison report pass deterministic fixture tests;
- a killed synthetic build resumes byte-identically;
- contamination results match the reference implementation;
- the local disk cap and Drive staging rules are enforced;
- no stage can start model training;
- the full repository test suite passes;
- documentation gives exact Mac and Drive commands and recovery steps.

The full corpus is ready for GPU pretraining only when the winning tokenizer is
explicitly recorded, its refreshed pilot gates pass, the 100M calibration is
accepted, all 12B quota items complete, every published artifact verifies, and
the final complete manifest is present.
