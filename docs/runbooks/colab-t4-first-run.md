# Colab T4 First-Run Runbook

Use this runbook with `notebooks/train_matgpt_t4_base_colab.ipynb`. It is for a
beginner operating the stage-gated base-pretraining workflow on Google Colab.

## Evidence Status

A real TinyStories preparation and T4 preflight completed on 2026-07-19. The
persisted preflight report passed all ten checks, including prepared-artifact
integrity, an observed Tesla T4, 8,391,936 parameters, 32,768 tokens per
optimizer update, and 6,104 scheduled steps.

The first benchmark report recorded finite loss, gradient norm, and memory, but
its throughput was rejected because the timer stopped before synchronizing
asynchronous CUDA work and included cold-start work in the first batch size.
The corrected benchmark performs one unmeasured warmup step, synchronizes CUDA
before timing, resets peak-memory measurement, and synchronizes again before
stopping the timer. Its replacement report passed on 2026-07-19. At the
configured micro-batch size of 16 it observed loss `9.0535`, gradient norm
`0.7336`, throughput about `99,961` tokens/second, and peak allocated memory
about `919.9` MiB (`6.17%` of reported T4 memory). Smoke training was approved
from this replacement evidence.

The smoke and resume check passed on 2026-07-20. The first invocation reached
exact step 20 with 655,360 processed tokens; the resumed invocation reached
exact step 25 with 819,200 processed tokens. Logged training loss fell from
`8.8405` at step 10 to `8.3794` at step 20, throughput remained near
`97k-100k` tokens/second, peak allocated memory was about `951.9` MiB, FP16
gradient scale remained `65,536`, and no optimizer update was skipped. Logged
gradient norms `2.4192` and `1.8880` are pre-clip values; the configured norm
limit remained `1.0`. Pilot training is approved but remains unobserved.

The first pilot command stopped before checkpoint state was applied because
`fingerprints.json` compared its original `git_commit` with a newer
documentation commit byte-for-byte. The run's configuration, tokenizer,
dataset, and parameter count were unchanged, and `latest.pt` remained at step
25. Fingerprint validation now treats those four fields as the training
identity while preserving the original commit as provenance. A changed commit
does not overwrite that origin record; checkpoint metadata records the commit
used when each later checkpoint is saved. Operators must still review code
changes between stages. The changes that triggered this recovery were
documentation and run-validation fixes, not model or optimizer math.

The pilot rerun passed on 2026-07-20 at exact step 306 with 10,027,008
processed tokens. Validation loss improved from the step-zero baseline
`9.0790` to `3.7332` near five million tokens and `2.9422` at the pilot stop;
validation perplexity reached `18.96`. Logged training loss declined from
`8.8405` at step 10 to roughly `3.0` near the stop. FP16 gradient scale stayed
at `65,536`, no optimizer update was skipped, peak allocated memory stayed
flat at about `951.9` MiB, and cumulative throughput remained near
`90k-100k` tokens/second after startup and evaluation overhead. The saved
notebook contained no error output. These results approved the `evaluate`
stage; full training remained unapproved until evaluation artifacts, resume
verification, samples, and the generated run summary were reviewed.

The pilot `evaluate` stage then loaded both checkpoints successfully. It
measured standalone validation loss `2.9459` and perplexity `19.03`, while
read-only resume verification confirmed step 306, 10,027,008 processed tokens,
zero skipped optimizer updates, and the unchanged 6,104-step schedule. The
samples were story-like but imperfect. The first comparison used stochastic
generation without resetting an evaluation seed, so differences between the
two sample sets were not a fair checkpoint comparison. The evaluation CLI now
resets the configured run seed before each checkpoint and records
`evaluation_seed` in its JSON. The corrected artifacts both recorded seed `42`
and matched exactly in validation loss (`2.9459`), perplexity (`19.03`), and all
three generated samples. The resume evidence remained complete and healthy.
Promotion to `full` was approved on 2026-07-20. Starting at step 306, the full
stage has 5,798 successful updates and 189,988,864 token positions remaining
before the required stop at exact step 6,104.

Dataset provenance was checked against official Hugging Face repository
metadata on 2026-07-19. Mini pins `roneneldan/TinyStories` at
`f54c09fd23315a6f9c86f9dc80f725de7d8f9c64`; 59M pins
`BabyLM-community/BabyLM-2026-Strict` at
`9e57baaaa91ac3c638746be14d1d5fa6c789f4cf`. The repository SHAs are verified;
an actual authenticated dataset download and preparation remain Colab runtime
gates.

The Mini configuration has a fixed 200M-token target. Its configured batch math
is 32,768 tokens per successful optimizer update and 6,104 full-schedule steps.
Preflight must report those values before they are treated as observed for a
run. `--max-steps` limits additional successful updates in one invocation; it
does not shorten or restart the learning-rate schedule.

## Prerequisites

- A Google account with enough Drive capacity for synchronized prepared data,
  checkpoints, metrics, evaluations, and samples.
- A Colab runtime manually set to an NVIDIA T4 for `prepare`, `smoke`, `pilot`, and `full`.
  T4 allocation is not guaranteed.
- At least 20 GiB free under `/content` before preparation or training.
- This repository available through `REPO_URL`, or already checked out at
  `PROJECT_DIR` under `/content`.
- A Colab `GITHUB_TOKEN` secret with read access when the repository is private.
- A Hugging Face account and optional `HF_TOKEN` secret for dataset access.
- An optional W&B account and `WANDB_API_KEY` secret when W&B is enabled.
- A W&B entity entered as only the username or team name, without URL or `/`
  characters. Leave `WANDB_ENTITY` blank to use the authenticated account's
  default entity. The notebook removes accidental surrounding slashes.
- Operator acceptance that Colab can disconnect. Paid Colab cost and runtime
  duration vary; check the current Colab terms and runtime UI before spending.

## Storage Contract

For the Mini run, the fixed working and durable roots are:

```text
/content/matgpt_work/matgpt_mini_8m_tinystories/
/content/drive/MyDrive/matgpt_artifacts/matgpt_mini_8m_tinystories/
```

The local root is ephemeral and fast. Preparation and training read these local
working artifacts:

```text
normalized/
tokenizer/
shards/
config/mini_8m.yaml
```

The notebook validates `normalized/`, `tokenizer/`, and `shards/` before it
skips or publishes them. Tokenizer metadata must match `tokenizer.json`; shard
metadata, hashes, sizes, token totals, and every referenced binary payload must
be complete. The fixed `/content` path is important because shard metadata
records absolute local paths.

Each Drive artifact directory is copied to a temporary sibling such as
`.shards.syncing-<id>`, validated there, and then replaces the prior directory.
Publication never merges files into an existing artifact directory. Interrupted
temporary copies are not treated as snapshots. Restore likewise validates a
complete Drive snapshot in a `.restoring-<id>` local directory before replacing
an incomplete local copy.

`FORCE_REBUILD_PREPARED` defaults to `False`. Set it to `True` only for a
`prepare` stage when neither the local artifact nor its Drive snapshot is
complete. It may remove only `normalized/`, `tokenizer/`, or `shards/` beneath
the ephemeral `LOCAL_ROOT`; it does not delete the Drive copy. A successful
rebuild publishes a new complete Drive snapshot.

Durable run evidence is written directly to Drive:

```text
run/preflight.json
run/benchmark.json
run/metrics.csv
run/environment.json
run/fingerprints.json
run/config.snapshot.yaml
run/checkpoints/latest.pt
run/checkpoints/best.pt
run/evaluation/latest.json
run/evaluation/best.json
run/resume_verification.json
run/samples/samples_*.json
run/run_summary.md
```

Do not point normalized data, tokenizer files, or shards directly at Drive for
active training. Do not move the local root between sessions.

## Exact Stage Order

1. Select `RUN_STAGE = "prepare"` and run the notebook top to bottom. This
   prepares and validates the artifacts, runs strict T4 preflight, runs the
   temporary five-step batch benchmark, and persists `preflight.json` and
   `benchmark.json`. It does not run the pretraining command or create a
   training checkpoint. Stop and review both reports before selecting `smoke`.
2. Select `RUN_STAGE = "smoke"`. With no `latest.pt`, this performs 20
   successful updates and then a 5-update resume check. At exact step 20 it
   performs only the resume check; at exact step 25 it runs no training command.
   Every other smoke checkpoint step is rejected.
3. Select `RUN_STAGE = "pilot"`. It resumes and stops at global step 306,
   approximately 10M configured Mini tokens.
4. Select `RUN_STAGE = "evaluate"`. Both `latest.pt` and `best.pt` are required.
   The notebook evaluates both and verifies complete `latest.pt` resume state
   without taking an optimizer update. Each evaluation artifact must record the
   configured `evaluation_seed`, and both checkpoints must be evaluated with
   that same seed. Review all gate evidence with the user and Codex. Step 306
   alone is not approval.
5. Only after explicit approval, manually select `RUN_STAGE = "full"`. The
   notebook never changes this selection automatically.
6. Select `RUN_STAGE = "evaluate"` again after full training.

Changing the stage requires rerunning the notebook top to bottom in the same or
a new Colab session. Keep `MODEL`, Drive root, and config inputs unchanged for a
single run lineage.

## Commands The Notebook Runs

The notebook writes a fixed local Colab config and uses it for every command.
`$CONFIG` below represents that generated YAML path.

Preparation, only when the corresponding integrity check fails and the local
artifact has been safely cleared or restored:

```bash
python scripts/prepare_dataset.py --config "$CONFIG"
python scripts/train_tokenizer.py --config "$CONFIG"
python scripts/tokenize_and_shard.py --config "$CONFIG"
```

During `prepare`, and again before every training stage. Each batch-size
benchmark performs one unmeasured warmup step followed by the configured five
synchronized measured steps:

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

The 59M picker uses benchmark sizes `2,4,6,8`. Treat all resulting T4 numbers
as expected until `benchmark.json` records them.

Smoke and resume check:

```bash
python scripts/pretrain.py --config "$CONFIG" --max-steps 20
python scripts/pretrain.py \
  --config "$CONFIG" \
  --resume-from "$RUN_DIR/checkpoints/latest.pt" \
  --max-steps 5
```

Pilot from the expected post-smoke step 25 uses 281 additional successful
updates. The notebook reads the checkpoint and computes this value instead of
assuming it:

```bash
python scripts/pretrain.py \
  --config "$CONFIG" \
  --resume-from "$RUN_DIR/checkpoints/latest.pt" \
  --max-steps 281
```

Full training has no `--max-steps` override and must finish at exact global
step 6,104:

```bash
python scripts/pretrain.py \
  --config "$CONFIG" \
  --resume-from "$RUN_DIR/checkpoints/latest.pt"
```

Evaluation requires and runs once for both `latest.pt` and `best.pt`, verifies
complete resume state without an update, persists that verification as
`resume_verification.json`, and then writes the summary:

Keep the T4 runtime active for this stage. A checkpoint containing CUDA RNG
state cannot pass complete resume verification on CPU because CPU cannot
restore that CUDA state.

```bash
python scripts/evaluate.py --config "$CONFIG" --checkpoint "$CHECKPOINT"
python scripts/pretrain.py \
  --config "$CONFIG" \
  --resume-from "$RUN_DIR/checkpoints/latest.pt" \
  --verify-only
python scripts/summarize_run.py --run-dir "$RUN_DIR"
```

## Gates 0-9

| Gate | Pass criteria | Evidence |
| --- | --- | --- |
| 0. Scope | The operator has selected the intended model and stage, accepts unobserved time/cost, and understands that `full` requires manual approval. | Settings cell and operator confirmation. |
| 1. Storage and device | `/content` and Drive usage print successfully; local free space is at least 20 GiB. `prepare` and training stages observe CUDA and a GPU name containing `T4`. | Storage/GPU cell output. |
| 2. Preparation | Manifest and split counts validate; tokenizer JSON matches its metadata hash; combined/split shard metadata validate; every referenced shard payload has the expected size and hash. Each Drive artifact is published through a validated temporary replacement snapshot. | Preparation output and Drive directories. |
| 3. Preflight | Process exits zero, top-level status is `pass`, all ten checks pass, and the JSON is persisted. For Mini, confirm preflight training math reports the configured 32,768 tokens/update and 6,104 steps. | `run/preflight.json`. |
| 4. Benchmark | Loss, pre-clip gradient norm, throughput, peak memory, total memory, and memory fraction are finite; throughput is positive. On CUDA, total memory is positive, peak memory and fraction are nonnegative, and fraction equals peak/total before the below-0.90 gate. CPU-only tests retain exact zero-memory fields. | `run/benchmark.json`. |
| 5. Smoke | No checkpoint runs the 20-update smoke; exact step 20 runs only the 5-update resume check; exact step 25 is already complete. Post-command checkpoints are exactly 20 and 25, and every other lineage is rejected. | `latest.pt`, command output, `metrics.csv`. |
| 6. Resume check | Loading `latest.pt` and running 5 additional successful updates finishes at exactly global step 25. The full LR schedule remains unchanged. | Updated `latest.pt`, `metrics.csv`. |
| 7. Pilot stop | Resume begins from durable `latest.pt` and finishes at exactly global step 306. This is a stop point, not promotion approval. | Updated `latest.pt`, `metrics.csv`. |
| 8. Pilot review | All reviewed rows are finite; late training-loss median is below early median; first-to-last finite validation loss improves; late/early throughput ratio is at least 0.80; benchmark memory remains below 0.90; skipped-update counters are reviewed; samples/evaluations are usable. Investigate a warning if every logged peak-memory value strictly increases. | Notebook review output, `benchmark.json`, `metrics.csv`, `run_summary.md`, samples, evaluations. |
| 9. Full and final review | The user and Codex explicitly approve promotion before `full` is selected. The full command resumes without `--max-steps` and must finish at exact step 6,104. Final `evaluate` requires and evaluates both checkpoints, verifies complete `latest.pt` resume state without taking an update, persists `resume_verification.json`, and regenerates `run_summary.md`. | Approval record, `resume_verification.json`, and final Drive artifacts. |

The Gate 8 calculations inform a decision; they do not mutate `RUN_STAGE`.
Skipped updates are not hidden: any nonzero count requires explicit review, and
repeated skipped updates or any non-finite value is a stop condition.

## Stop Conditions

Stop without promoting when any of these occurs:

- local free space is below 20 GiB, Drive is not writable, or synchronization
  does not include `normalized`, `tokenizer`, and `shards`;
- `prepare` or a training stage does not observe CUDA on a T4;
- preflight exits nonzero, reports any failed check, or does not persist valid
  JSON;
- the configured benchmark batch fails, loss or gradient norm is non-finite,
  throughput is not positive, or memory fraction is at least 0.90;
- a prepared-artifact hash, metadata record, payload size, or payload file is
  incomplete, or a Drive directory was not published as a validated snapshot;
- a smoke checkpoint is anything other than absent, exact step 20, or exact
  step 25; a post-command step is not exact; or resume reports an
  artifact/config mismatch;
- pilot does not stop at step 306;
- full training does not finish at exact step 6,104, either required checkpoint
  is missing, or read-only resume verification fails;
- training or validation evidence is non-finite, late loss does not improve,
  validation loss does not improve, throughput ratio is below 0.80, or skipped
  updates need investigation;
- peak memory increases at every logged point without an understood bounded
  cause;
- samples, evaluation JSON, resume-verification JSON, metrics, or the run
  summary are missing or invalid.

Preserve the evidence and diagnose the failure. Do not work around a gate by
editing the full schedule, document caps, evaluation intervals, sample
intervals, checkpoint intervals, or test expectations.

## Resume After A Disconnect

1. Start a new Colab session, mount the same Drive, select the same `MODEL`, and
   keep the same project/config inputs.
2. Select the stage that was interrupted and rerun top to bottom. A missing or
   incomplete local artifact restores only from a complete Drive snapshot.
3. If neither local nor Drive preparation is complete, select `prepare`, set
   `FORCE_REBUILD_PREPARED=True`, and rerun. The control clears only the named
   directories under ephemeral `LOCAL_ROOT`; return it to `False` after a
   complete snapshot is published.
4. If `prepare` was interrupted during Drive publication, leave the
   `.syncing-<id>` directory alone. Rerun `prepare`; only the last validated
   destination directory is restorable, and successful publication replaces it.
5. If smoke has no `latest.pt`, it runs the 20-update smoke and the 5-update
   resume check. If a partial `metrics.csv` exists without a checkpoint,
   preserve or rename the partial Drive `run/` directory first because metrics
   alone are not resumable state.
6. If smoke has `latest.pt` at step 20, rerunning `smoke` runs only the 5-update
   resume check. At step 25 it runs no training and reports completion. Any
   other checkpoint step is rejected for investigation.
7. For pilot or full, the notebook loads durable `latest.pt`. Pilot recomputes
   `306 - current_step`; full resumes the unchanged schedule. Inspect metrics
   around the interruption for duplicate or non-monotonic rows before approval.
8. Rerun `evaluate` after recovery. It must find both checkpoints, evaluate
   both, verify complete `latest.pt` resume state without an update, and then
   regenerate the summary.

## W&B Setup Failure Before Step Zero

If W&B reports `entity ... not found during upsertBucket`, confirm that
`WANDB_ENTITY` contains only the username or team name. Do not paste a URL or a
value such as `/team-name`; use `team-name`, or leave it blank to use the
authenticated default. Tracker creation happens before baseline evaluation,
optimizer updates, run-artifact writes, and checkpoint creation. When this
specific failure occurs on a new smoke run, no model progress exists to resume:
correct the entity and rerun `smoke` from the top.

Never resume through a preflight checkpoint-compatibility failure. Preserve the
run directory and review the config, tokenizer, and dataset fingerprints.

## Share The Review Bundle

Share files from the durable Drive `run/` directory, not transient notebook
cell output:

```text
preflight.json
benchmark.json
metrics.csv
run_summary.md
evaluation/latest.json
evaluation/best.json          # when present
resume_verification.json
samples/samples_*.json        # latest plus any comparison sample
```

Include the generated config snapshot and `environment.json` when diagnosing a
failure. State the selected model/stage, checkpoint global step, whether the
numbers are expected or observed, and any disconnect or skipped-update event.
The user and Codex should review this bundle before `full` is selected.
