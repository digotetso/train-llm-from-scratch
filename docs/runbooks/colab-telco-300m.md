# MatGPT Telco 300M Colab Runbook

This runbook is the operator procedure for the `306,226,176`-parameter MatGPT
Telco base model. Use the stage-gated notebook
[`notebooks/train_matgpt_telco_300m_colab.ipynb`](../../notebooks/train_matgpt_telco_300m_colab.ipynb).
Do not start a first run with standalone training commands.

The target is a compact teaching and research model with useful general English
and extra telecom/networking knowledge. It is not an autonomous network
operator. Production use still needs retrieval, citations, deterministic input
validation, permissions, dry-runs, audit logs, and a human approval policy
proportional to the action's blast radius.

## Fixed design

| Item | Value |
| --- | --- |
| Parameters | `306,226,176` |
| Architecture | 20 layers, width 1024, 16 heads, SwiGLU 3072 |
| Context | 2,048 tokens |
| Vocabulary | 32,768 byte-level BPE tokens |
| Main phase | 10B tokens: 65% general, 30% telecom, 5% structured |
| Cooldown phase | 2B tokens: 60% general, 35% telecom, 5% structured |
| Pilot | 20M tokens using aggregate 12B proportions |
| Precision | BF16 |
| Tokens/update | 131,072 (`8 × 8 × 2,048`) |
| Full schedule | 91,553 optimizer updates |

Because updates are fixed-size, the schedule ends 34,816 tokens above 12B
(`0.00029%`). The phase switch can similarly cross the 10B boundary by one
update. This is expected schedule rounding, not silent data rebalancing.

## Source roles and boundaries

The checked registry is
[`configs/data/telco_300m_sources.yaml`](../../configs/data/telco_300m_sources.yaml).
Every upstream Hugging Face dataset is pinned to an immutable commit.

| Source | Role | May enter base pretraining? | Use |
| --- | --- | --- | --- |
| Common Pile selected files | `pretrain_general` | Yes | General English and knowledge |
| GSMA Telco Common Corpus | `pretrain_telecom` | Yes | 3GPP, RFC/IETF, research, patents, semantic telecom text |
| Common Pile structured files | `pretrain_structured` | Yes | Code and structured technical text |
| SmolTalk, OTel-LLM | `posttrain` | No | Reserved for a later instruction-tuning track |
| OTel-Safety | `posttrain` | No | Reserved for later safety alignment work |
| GSMA 3GPP mirror | `rag_only` | No | Retrieval/reference use subject to licence review |
| Open Telco Lite and Full | `evaluation_only` | No | Isolated benchmark and contamination patterns |

Each Common Pile collection is a separate registry source and receives an
explicit token quota. Do not combine these file globs into one streaming source:
the stream could satisfy the quota from early files before later collections
are reached. The selected weights are deliberately below the source token
supplies published in the
[official Comma v0.1 dataset card](https://huggingface.co/datasets/common-pile/comma_v0.1_training_dataset),
although the exact counts still depend on this project's tokenizer.

| General collection | Share of general role | Main | Cooldown | Full total |
| --- | ---: | ---: | ---: | ---: |
| Wikimedia | 35% | 2.275B | 420M | 2.695B |
| Stack Exchange | 20% | 1.300B | 240M | 1.540B |
| Pre-1929 books | 14% | 910M | 168M | 1.078B |
| Project Gutenberg | 10% | 650M | 120M | 770M |
| peS2o | 8% | 520M | 96M | 616M |
| DOAB | 5% | 325M | 60M | 385M |
| PubMed | 3.89% | 252.85M | 46.68M | 299.53M |
| arXiv abstracts | 2% | 130M | 24M | 154M |
| LibreTexts | 1% | 65M | 12M | 77M |
| Pressbooks | 1% | 65M | 12M | 77M |
| OER Commons | 0.1% | 6.5M | 1.2M | 7.7M |
| Public Domain Review | 0.01% | 0.65M | 0.12M | 0.77M |

The structured role is also explicit: GitHub Archive receives 55% (330M full
tokens), Stack v2 educational code 44.6% (267.6M), and Python Enhancement
Proposals 0.4% (2.4M). The telecom role remains 35% 3GPP, 30% RFC/IETF, 25%
research, 8% patents, and 2% semantic telecom text.

`license_review: required` means the pipeline preserves and reports the source
and document-level licence, but it does **not** grant legal clearance. Review
the manifest's licence counts and the upstream terms before publishing the
corpus, tokenizer, weights, or a commercial service. The full build fails when
a planned source is unavailable or cannot meet its quota; do not silently copy,
repeat, or substitute data to get past that failure.

## Capacity and time planning

Use the full RTX PRO 6000 Blackwell 96GB or A100 80GB runtime, not a fractional
GPU. The notebook accepts supported GPUs by CUDA capability and memory; it is
not locked to a T4 name.

Before the full corpus, plan for at least:

- 100–140 GiB free in Google Drive for prepared JSONL, 24GB of uint16 shards,
  checkpoints, evaluations, and safety margin;
- 35 GiB free under `/content` for local shards, tokenizer artifacts, and
  temporary work;
- more space if you enable milestone checkpoints. The checked config keeps only
  rolling `latest.pt` and `best.pt` by setting `keep_milestones: false`.

The value printed by `shutil.disk_usage("/content/drive")` describes Colab's
Drive mount/cache filesystem; it is **not** the Google account quota. For a full
data build, the notebook requests `storageQuota` from Google Drive API v3,
checks the resulting account free space, and writes `drive_storage.json`. If
that API authentication is unavailable, read free space from the Google Drive
Storage page and set `GOOGLE_DRIVE_FREE_GB_OVERRIDE` to its decimal-GB free
amount (not the used amount). The local `/content` check remains separate and still guards
the temporary tokenizer and shard copies.

Do not trust a GPU-name-based time estimate. Read `benchmark.json` and estimate:

```text
hours = target_tokens / measured_tokens_per_second / 3600 × 1.15
```

The 15% factor is a starting allowance for validation, samples, checkpoints,
Drive I/O, and restarts. For perspective, 12B tokens take about 133 hours at
25k tokens/s, 67 hours at 50k tokens/s, or 33 hours at 100k tokens/s before
that allowance. Colab session limits make resumable multi-session training the
normal case.

## Persistent layout

The notebook uses these fixed roots:

```text
/content/matgpt_work/matgpt_telco_300m/<recipe-id>/
  <pilot|full>/tokenizer/       fast local copy
  <pilot|full>/shards/          fast local copy
  <pilot|full>/config/          generated absolute-path config

/content/drive/MyDrive/matgpt_artifacts/matgpt_telco_300m/
  evaluation_assets/           isolated Open Telco Lite/Full JSONL
  recipes/<recipe-id>/
    corpora/<pilot|full>/       normalized JSONL and manifest
    prepared/<pilot|full>/      durable tokenizer and shard snapshot
    evidence/<pilot|full>/      plans, audit, preflight, benchmark, gates
    runs/<pilot|full>/          metrics, samples, checkpoints, evaluations
```

`recipe-id` is the first 12 characters of a SHA-256 over the checked model/data
config, source registry, and mixture. Any checked configuration, mixture, or
source change gets a fresh namespace, so an old corpus, tokenizer, gate, or
checkpoint cannot silently satisfy a new run. Older recipe directories remain
intact for comparison and rollback.

The original 8M/59M directories are not reused or overwritten.

## Exact stage order

Change only `RUN_STAGE` and, where specified, `DATA_PLAN`. Run all notebook
cells from the top after each runtime restart; cells outside the selected stage
only restore context or print that they were skipped.

### 1. `prepare_data` with `DATA_PLAN = "pilot"`

Leave the notebook defaults:

```python
RUN_STAGE = "prepare_data"
DATA_PLAN = "pilot"
ALLOW_FULL_DATA = False
FULL_APPROVED = False
```

This stage first materializes pinned Open Telco Lite and Full outside the
training tree. Their questions become contamination patterns. It then writes
the 20M-token mixture plan and streams a role-approved tokenizer-bootstrap
corpus. At this first gate only, source token fields or `ceil(characters / 4)`
are used to stop collection because the project tokenizer does not exist yet.
The resulting corpus is representative tokenizer-fitting input, not the final
exact 20M-token pilot. This stage does not import or start pretraining.

The pinned Open Telco Full `oranbench` config contains 1,500 source rows, but
three rows have empty questions and cannot be evaluated. Preparation keeps the
1,497 usable rows and records the skipped source indices and reason in the
evaluation manifest. Other malformed row types remain fatal.

Pinned pretraining sources can also contain whitespace-only documents. Corpus
preparation skips those documents, records them as `empty_text` quality
rejections, and continues streaming until the planned token quota is filled.
A missing declared text field or another source-schema violation remains fatal.

Stop and inspect:

- `recipes/<recipe-id>/evidence/pilot/mixture_plan_pilot.json`;
- `recipes/<recipe-id>/corpora/pilot/manifest.json`;
- `quota_counting.method: source_estimate` for a first bootstrap build;
- source revisions, role totals, rejection counts, and licence counts;
- confirmation that Open Telco source IDs are absent from the training sources.

If a source exhausts before quota, preserve the error and manifest/staging
evidence. Change the approved mixture or source registry in Git; never edit the
generated JSONL or plan in Drive.

### 2. `prepare` with `DATA_PLAN = "pilot"`

This stage trains the tokenizer once from the bootstrap corpus (or restores an
already frozen pilot tokenizer), checks general and telecom fertility probes,
and immediately snapshots that tokenizer to
`recipes/<recipe-id>/prepared/pilot/tokenizer`. It then atomically rebuilds the pilot corpus while
counting exact tokenizer IDs, retains the bootstrap corpus as a timestamped
backup, audits every exact quota, creates packed shards, runs the supported-GPU
preflight, and benchmarks micro-batches 4, 8, and 12. It starts no pretraining.

The exact corpus manifest must report `quota_counting.method: tokenizer_exact`
and the same tokenizer SHA-256 as
`recipes/<recipe-id>/prepared/pilot/tokenizer/special_tokens.json`. Do not retrain the tokenizer
after this rebuild: changing the tokenizer would invalidate the counts that
selected the corpus.

Required pass evidence:

- `quota_audit.json` has `passed: true` and every item is within 3%;
- `preflight.json` has `status: pass` for configuration, registry, every data
  split, tokenizer, shards, storage, GPU, schedule math, and checkpoint state;
- `benchmark.json` has a finite batch-8 loss and gradient norm, positive
  throughput, and acceptable memory headroom.

Do not increase batch size merely because it fits once. Keep headroom for
validation, checkpoint serialization, and runtime variance. If batch 8 fails,
change `micro_batch_size`, compensate with gradient accumulation to retain the
intended tokens/update, rerun `prepare`, and treat the result as a new config
fingerprint.

### 3. `smoke` with `DATA_PLAN = "pilot"`

The smoke stage performs 20 successful updates, validates a complete resume,
then resumes for five more updates. It writes
`evidence/pilot/smoke_resume_verified.json`. Stop if loss, gradient norm, or
checkpoint loading is non-finite or inconsistent.

### 4. `pilot` with `DATA_PLAN = "pilot"`

The pilot resumes the smoke checkpoint and runs to at least 20M tokens. It
writes `evidence/pilot/pilot_complete.json` only after the checkpoint state
reaches the configured token target.

Before approving full data or training, inspect:

- validation loss and perplexity trend, not only the last value;
- throughput and peak memory;
- generated English and telecom samples;
- repetition and obvious entity/object confusion;
- successful resume evidence;
- Drive capacity and the estimated full-run duration from measured throughput.

Kill the full experiment if loss is unstable, samples do not improve, quota or
licensing evidence is unresolved, resume fails, or the measured cost is not
acceptable.

### 5. `prepare_data` and `prepare` with `DATA_PLAN = "full"`

Set `ALLOW_FULL_DATA = True` only after the pilot review. Keep
`FULL_APPROVED = False`. A completed
`recipes/<recipe-id>/prepared/pilot/tokenizer` is now a hard prerequisite. The
data stage uses that recipe-matched frozen tokenizer to build exact `main` and
`cooldown` quotas together in one atomic corpus build; a partial phase is never
published. Then select `prepare` to restore/verify the same tokenizer, audit
the exact corpus, and create the full shards.

Changing from pilot to full preserves the tokenizer fingerprint but produces a
different dataset manifest, shard set, config fingerprint, and run directory.
A pilot checkpoint must not be resumed into the full run; checkpoint
compatibility rejects the changed config and corpus even though the vocabulary
is shared.

### 6. `full` with `DATA_PLAN = "full"`

Review the full `quota_audit.json`, `preflight.json`, and `benchmark.json`, then
set `FULL_APPROVED = True` and manually choose `RUN_STAGE = "full"`. The
notebook also requires the completed pilot gate. No earlier stage can promote
itself into full training.

On a new Colab session, run all cells from the top with the same settings. The
notebook restores tokenizer and shards from Drive and passes `latest.pt` to the
resume command. Checkpoint compatibility rejects a changed config, tokenizer,
or corpus manifest. Never bypass that check to rescue a mismatched run.

### 7. `evaluate`

Use the `DATA_PLAN` belonging to the checkpoints. The notebook evaluates every
preserved `best`, milestone (if explicitly enabled), and `latest` checkpoint on:

- fixed validation loss/perplexity;
- the isolated Open Telco multiple-choice tasks;
- repeated words, phrases, and sentences;
- character/object, location/state, and cause/effect consistency;
- fixed-seed generated responses.

With two or more checkpoints, it creates exactly 50 blinded reviews per
checkpoint under `checkpoint_comparison/llm_judge/`. Give
`judge_prompt.md` and one blinded batch at a time to this Codex task. Do not
provide `review_key.json` until all judgments are returned. Save the returned
JSONL files and score them with:

```bash
python scripts/score_story_judgments.py \
  --key /path/to/checkpoint_comparison/llm_judge/review_key.json \
  --judgments /path/to/result-01.jsonl \
  --judgments /path/to/result-02.jsonl \
  --reviewer llm \
  --output /path/to/checkpoint_comparison/llm_judge/llm_scores.json
```

The LLM is the primary blinded judge. Human review is optional and must use a
separate output with `--reviewer human`. Automated judging is research evidence,
not authority for live network changes.

## Recovery and rollback

- A normal interruption: reconnect, select the same stage and data plan, run
  from the top, and resume `latest.pt`.
- A source-registry or mixture change creates a new recipe ID. Start again at
  `prepare_data` with `DATA_PLAN = "pilot"`; the old recipe remains preserved,
  but its tokenizer, pilot gate, and checkpoints cannot promote the new recipe.
- An older pilot `prepare` that fails with `Actual tokenizer quotas are outside
  tolerance`: do not raise the tolerance and do not delete the corpus. Pull the
  merged fix, open the repository's current Telco notebook, select
  `RUN_STAGE = "prepare"` and `DATA_PLAN = "pilot"`, then run all cells. The
  notebook uses the recipe-matched tokenizer (or trains it once if this recipe
  has none), snapshots it before replacement, and atomically rebuilds the
  corpus with exact counts. The earlier estimate-selected corpus remains
  recoverable under `corpora/pilot.backup-<timestamp>` inside that recipe.
- Artifact mismatch: stop. Compare the saved config, manifest, tokenizer hash,
  and current Git commit. Resume only the exact matching run.
- Failed corpus replacement: the builder publishes through a staging directory
  and retains a timestamped backup when `--force` is deliberately used.
- Failed artifact snapshot: the notebook keeps the previous Drive copy under a
  `.previous` directory until the new copy is promoted.
- Rollback: switch back to the earlier Git revision and its matching Drive run
  directory. Do not delete or overwrite checkpoints during diagnosis.

Local tests prove deterministic code paths with synthetic fixtures. They do
not prove current upstream access, licence clearance, available Drive quota,
real GPU throughput, long-run numerical stability, or model quality. Those
claims require the persisted notebook evidence from the actual run.
