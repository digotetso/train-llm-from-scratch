# Colab T4 First-Run Runbook

Use this runbook with `notebooks/train_matgpt_t4_base_colab.ipynb`. It is for a
beginner operating the stage-gated base-pretraining workflow on Google Colab.

## Evidence Status

No real TinyStories or T4 run was performed while writing this runbook. GPU
availability, wall time, cost, throughput, loss, gradient norm, and memory
figures are **expected until observed** in the persisted artifacts from your
own run. Do not present expected T4 values as measured results.

The Mini configuration has a fixed 200M-token target. Its configured batch math
is 32,768 tokens per successful optimizer update and 6,104 full-schedule steps.
Preflight must report those values before they are treated as observed for a
run. `--max-steps` limits additional successful updates in one invocation; it
does not shorten or restart the learning-rate schedule.

## Prerequisites

- A Google account with enough Drive capacity for synchronized prepared data,
  checkpoints, metrics, evaluations, and samples.
- A Colab runtime manually set to an NVIDIA T4 for `smoke`, `pilot`, and `full`.
  T4 allocation is not guaranteed.
- At least 20 GiB free under `/content` before preparation or training.
- This repository available through `REPO_URL`, or already checked out at
  `PROJECT_DIR` under `/content`.
- A Colab `GITHUB_TOKEN` secret with read access when the repository is private.
- A Hugging Face account and optional `HF_TOKEN` secret for dataset access.
- An optional W&B account and `WANDB_API_KEY` secret when W&B is enabled.
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

The notebook copies `normalized/`, `tokenizer/`, and `shards/` to the matching
Drive root after successful preparation. At the start of a later session, it
restores any missing local directory from Drive. The fixed `/content` path is
important because shard metadata records absolute local paths.

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
run/samples/samples_*.json
run/run_summary.md
```

Do not point normalized data, tokenizer files, or shards directly at Drive for
active training. Do not move the local root between sessions.

## Exact Stage Order

1. Select `RUN_STAGE = "prepare"` and run the notebook top to bottom.
2. Start a fresh run with `RUN_STAGE = "smoke"`. This performs 20 successful
   updates, then resumes `latest.pt` for 5 additional successful updates.
3. Select `RUN_STAGE = "pilot"`. It resumes and stops at global step 306,
   approximately 10M configured Mini tokens.
4. Select `RUN_STAGE = "evaluate"`. Review all gate evidence with the user and
   Codex. Step 306 alone is not approval.
5. Only after explicit approval, manually select `RUN_STAGE = "full"`. The
   notebook never changes this selection automatically.
6. Select `RUN_STAGE = "evaluate"` again after full training.

Changing the stage requires rerunning the notebook top to bottom in the same or
a new Colab session. Keep `MODEL`, Drive root, and config inputs unchanged for a
single run lineage.

## Commands The Notebook Runs

The notebook writes a fixed local Colab config and uses it for every command.
`$CONFIG` below represents that generated YAML path.

Preparation, only when each expected output set is absent:

```bash
python scripts/prepare_dataset.py --config "$CONFIG"
python scripts/train_tokenizer.py --config "$CONFIG"
python scripts/tokenize_and_shard.py --config "$CONFIG"
```

Before every training stage:

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

Full training has no `--max-steps` override:

```bash
python scripts/pretrain.py \
  --config "$CONFIG" \
  --resume-from "$RUN_DIR/checkpoints/latest.pt"
```

Evaluation runs once for each existing `latest.pt` and `best.pt`, followed by:

```bash
python scripts/evaluate.py --config "$CONFIG" --checkpoint "$CHECKPOINT"
python scripts/summarize_run.py --run-dir "$RUN_DIR"
```

## Gates 0-9

| Gate | Pass criteria | Evidence |
| --- | --- | --- |
| 0. Scope | The operator has selected the intended model and stage, accepts unobserved time/cost, and understands that `full` requires manual approval. | Settings cell and operator confirmation. |
| 1. Storage and device | `/content` and Drive usage print successfully; local free space is at least 20 GiB. Training stages observe CUDA and a GPU name containing `T4`. | Storage/GPU cell output. |
| 2. Preparation | Manifest, both normalized splits, tokenizer files, and both shard metadata files exist locally; synchronization completes for all three artifact directories. | Preparation output and Drive directories. |
| 3. Preflight | Process exits zero, top-level status is `pass`, all ten checks pass, and the JSON is persisted. For Mini, confirm preflight training math reports the configured 32,768 tokens/update and 6,104 steps. | `run/preflight.json`. |
| 4. Benchmark | The configured micro-batch result has status `ok`; loss and pre-clip gradient norm are finite; throughput is finite and positive; memory fraction is finite and below 0.90. | `run/benchmark.json`. |
| 5. Smoke | No prior `latest.pt` exists; the first invocation finishes at exactly global step 20 with no non-finite failure. | `latest.pt`, command output, `metrics.csv`. |
| 6. Resume check | Loading `latest.pt` and running 5 additional successful updates finishes at exactly global step 25. The full LR schedule remains unchanged. | Updated `latest.pt`, `metrics.csv`. |
| 7. Pilot stop | Resume begins from durable `latest.pt` and finishes at exactly global step 306. This is a stop point, not promotion approval. | Updated `latest.pt`, `metrics.csv`. |
| 8. Pilot review | All reviewed rows are finite; late training-loss median is below early median; first-to-last finite validation loss improves; late/early throughput ratio is at least 0.80; benchmark memory remains below 0.90; skipped-update counters are reviewed; samples/evaluations are usable. Investigate a warning if every logged peak-memory value strictly increases. | Notebook review output, `benchmark.json`, `metrics.csv`, `run_summary.md`, samples, evaluations. |
| 9. Full and final review | The user and Codex explicitly approve promotion before `full` is selected. The full command resumes without `--max-steps`; final `evaluate` regenerates evaluation JSON and `run_summary.md`. | Approval record and final Drive artifacts. |

The Gate 8 calculations inform a decision; they do not mutate `RUN_STAGE`.
Skipped updates are not hidden: any nonzero count requires explicit review, and
repeated skipped updates or any non-finite value is a stop condition.

## Stop Conditions

Stop without promoting when any of these occurs:

- local free space is below 20 GiB, Drive is not writable, or synchronization
  does not include `normalized`, `tokenizer`, and `shards`;
- a training stage does not observe CUDA on a T4;
- preflight exits nonzero, reports any failed check, or does not persist valid
  JSON;
- the configured benchmark batch fails, loss or gradient norm is non-finite,
  throughput is not positive, or memory fraction is at least 0.90;
- smoke does not begin fresh, step 20 or step 25 is not observed, or checkpoint
  resume reports an artifact/config mismatch;
- pilot does not stop at step 306;
- training or validation evidence is non-finite, late loss does not improve,
  validation loss does not improve, throughput ratio is below 0.80, or skipped
  updates need investigation;
- peak memory increases at every logged point without an understood bounded
  cause;
- samples, evaluation JSON, metrics, or the run summary are missing or invalid.

Preserve the evidence and diagnose the failure. Do not work around a gate by
editing the full schedule, document caps, evaluation intervals, sample
intervals, checkpoint intervals, or test expectations.

## Resume After A Disconnect

1. Start a new Colab session, mount the same Drive, select the same `MODEL`, and
   keep the same project/config inputs.
2. Select the stage that was interrupted and rerun top to bottom. Missing local
   prepared directories restore from Drive before preflight.
3. If `prepare` was interrupted, rerun `prepare`; completed output sets are
   skipped and the successful set is synchronized again.
4. If smoke completed through step 25, do not rerun `smoke`; select `pilot`.
5. If smoke was interrupted before a valid `latest.pt` was written, preserve or
   rename the partial Drive `run/` directory for diagnosis, then start smoke
   with a new empty run directory. A partial metrics file is not a checkpoint.
6. For pilot or full, the notebook loads durable `latest.pt`. Pilot recomputes
   `306 - current_step`; full resumes the unchanged schedule. Inspect metrics
   around the interruption for duplicate or non-monotonic rows before approval.
7. Rerun `evaluate` after recovery so evaluation JSON and the summary describe
   the latest durable checkpoint.

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
samples/samples_*.json        # latest plus any comparison sample
```

Include the generated config snapshot and `environment.json` when diagnosing a
failure. State the selected model/stage, checkpoint global step, whether the
numbers are expected or observed, and any disconnect or skipped-update event.
The user and Codex should review this bundle before `full` is selected.
