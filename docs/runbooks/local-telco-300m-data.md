# Local Telco 300M tokenizer-data runbook

Use this runbook to build and review the 200M-token tokenizer candidate on the
Mac. The authoritative entry point is `scripts/prepare_telco_local.py`; the
local notebook only assembles that command and streams its output. Neither
surface imports or starts model pretraining.

## Prerequisites and current machine evidence

Before starting, install the repository environment, authenticate Hugging Face
for every pinned source that requires it, plug the Mac into power, and prevent
automatic sleep for the duration of the stage. A screen lock is fine; system
sleep interrupts the process and network streams.

The 2026-08-09 machine check reported:

```text
$ sysctl -n hw.memsize
25769803776

$ df -k /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch
Filesystem   1024-blocks      Used Available Capacity ... Mounted on
/dev/disk3s5   482797652 347654456  94154780    79% ... /System/Volumes/Data
```

That is 24GiB RAM and 89.8GiB free local disk at the time of the check. The
planning prerequisite was at least 100GiB free before the first real 200M run,
so reclaim and re-check local space before starting. The checked candidate
recipe has a 20GiB working-set budget and a 25GiB absolute free-space floor;
the larger 100GiB start target leaves room for Drive cache and unexpected
source expansion.

```bash
uv sync --extra test
sysctl -n hw.memsize
df -h /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch
```

No GPU is required. Sampling, byte-level BPE fitting, evaluation, and comparison
are CPU/data operations. Keep GPU training in the guarded Colab workflow.

## Google Drive must remain streamed

In Google Drive for desktop settings, keep **My Drive** in **Stream files**
mode. Do not choose **Available offline** for `matgpt_artifacts` or any parent;
that creates another local copy and defeats the working-set bound. After a
stage, confirm Finder shows the cloud-sync completion state before treating a
Drive artifact as remotely durable.

Discover the mounted path rather than guessing the account suffix:

```bash
find "$HOME/Library/CloudStorage" -maxdepth 2 -type d -name "My Drive" -print
```

On the checked machine this returned:

```text
/Users/digotetsomatema/Library/CloudStorage/GoogleDrive-pro.digmatema@gmail.com/My Drive
```

Use a local work root outside `Library/CloudStorage`, for example
`$HOME/matgpt_work/matgpt_telco_300m`. Use an existing directory below the
mounted `My Drive` as `--drive-dir`. The CLI refuses equal, nested, symlinked,
or missing roots.

## Prepare contamination evidence first

The sample must exclude every Open Telco evaluation question. Materialize the
pinned Lite and Full assets outside the training tree, then pass each generated
config JSONL with a repeated `--contamination-patterns` option.

```bash
uv run python scripts/prepare_open_telco_evals.py \
  --sources configs/data/telco_300m_sources.yaml \
  --dataset lite \
  --output-dir "$HOME/matgpt_work/matgpt_telco_300m/evaluation/open_telco_lite"

uv run python scripts/prepare_open_telco_evals.py \
  --sources configs/data/telco_300m_sources.yaml \
  --dataset full \
  --output-dir "$HOME/matgpt_work/matgpt_telco_300m/evaluation/open_telco_full"
```

The examples below abbreviate the four shared configuration arguments. When
using the CLI directly, include them on every invocation exactly as shown:

```text
--sources configs/data/telco_300m_sources.yaml
--mixture configs/data/telco_300m_mixture.yaml
--candidate-config configs/data/telco_300m_tokenizer_candidate.yaml
--model-config configs/matgpt_telco_300m.yaml
--work-dir <local-work-root>
--drive-dir <existing-streamed-drive-publish-root>
```

The CLI hashes all four YAML inputs and requires byte identity with these
checked repository files. A byte-identical copy is accepted; an edited or
semantically similar alternate file is rejected before sampling, training, or
evaluation begins.

The notebook at `notebooks/prepare_matgpt_telco_300m_local.ipynb` keeps these
paths visible at the top, previews the exact expanded command, and streams
stdout/stderr live with `subprocess.Popen`.

## Stage 1: build or resume `tokenizer_sample`

Pass all eight generated Lite/Full config files (four per dataset):

```bash
uv run python scripts/prepare_telco_local.py \
  --stage tokenizer_sample \
  --sources configs/data/telco_300m_sources.yaml \
  --mixture configs/data/telco_300m_mixture.yaml \
  --candidate-config configs/data/telco_300m_tokenizer_candidate.yaml \
  --model-config configs/matgpt_telco_300m.yaml \
  --work-dir <local-work-root> \
  --drive-dir <streamed-drive-publish-root> \
  --contamination-patterns <local-work-root>/evaluation/open_telco_lite/teleqna.jsonl \
  --contamination-patterns <local-work-root>/evaluation/open_telco_lite/oranbench.jsonl \
  --contamination-patterns <local-work-root>/evaluation/open_telco_lite/srsranbench.jsonl \
  --contamination-patterns <local-work-root>/evaluation/open_telco_lite/sixg_bench.jsonl \
  --contamination-patterns <local-work-root>/evaluation/open_telco_full/teleqna.jsonl \
  --contamination-patterns <local-work-root>/evaluation/open_telco_full/oranbench.jsonl \
  --contamination-patterns <local-work-root>/evaluation/open_telco_full/srsranbench.jsonl \
  --contamination-patterns <local-work-root>/evaluation/open_telco_full/sixg_bench.jsonl
```

All eight unique files are mandatory and each must yield at least one normalized
pattern. A missing, duplicate, empty, or unexpectedly named file fails before
the sample builder is called. When either evaluation directory contains its
generated `manifest.json`, the CLI also verifies its checksum, pinned source
identity, exact four-config set, counts, byte sizes, and file checksums.

Expected local outputs:

```text
<local-work-root>/
  tokenizer_sample/fit/fit_*.jsonl
  tokenizer_sample/holdout/holdout_*.jsonl
  tokenizer_sample/manifest.json
  state/tokenizer_sample.sqlite3
```

Progress lines report the source cursor, accepted estimated tokens, elapsed
time, rate, and ETA. The final manifest is v2 and binds bounded artifact counts,
content digests, and the build identity.

`Ctrl-C` is safe. Rerun the identical command: committed chunks are verified,
uncommitted temporary/chunk files are removed, and sampling resumes from the
journal cursor. Changed source, mixture, quality, contamination, or format
fingerprints refuse resume. Do not edit a committed chunk or the SQLite journal.

## Stage 2: create `tokenizer_candidate`

```bash
uv run python scripts/prepare_telco_local.py \
  --stage tokenizer_candidate \
  --sources configs/data/telco_300m_sources.yaml \
  --mixture configs/data/telco_300m_mixture.yaml \
  --candidate-config configs/data/telco_300m_tokenizer_candidate.yaml \
  --model-config configs/matgpt_telco_300m.yaml \
  --work-dir <local-work-root> \
  --drive-dir <streamed-drive-publish-root> \
  --sample-manifest <local-work-root>/tokenizer_sample/manifest.json
```

Expected durable output is
`<streamed-drive-publish-root>/tokenizers/representative_200m/`, containing
`tokenizer.json`, `special_tokens.json`, and `tokenizer_report.json`. The CLI
refuses an existing candidate directory and never overwrites the preserved
`pilot_20m` tokenizer.

`--sample-manifest` must resolve exactly to
`<local-work-root>/tokenizer_sample/manifest.json`. Before fitting, the CLI
atomically claims the canonical candidate directory. The persisted tokenizer
report must bind back to that sample manifest fingerprint; a failed or
interrupted fit leaves the claimed directory in place for operator review.

Candidate fitting is not resumable. If it is interrupted, preserve the partial
directory for diagnosis, move it aside only after review, and rerun into the
now-absent canonical destination. Never overwrite files in place.

## Stage 3: write `tokenizer_compare`

Locate the preserved pilot tokenizer from the existing recipe namespace,
normally `recipes/<recipe-id>/prepared/pilot/tokenizer`. Compare both tokenizers
against the same verified sample manifest; the evaluation API selects every
holdout chunk in manifest order and verifies all digests and counts.

```bash
uv run python scripts/prepare_telco_local.py \
  --stage tokenizer_compare \
  --sources configs/data/telco_300m_sources.yaml \
  --mixture configs/data/telco_300m_mixture.yaml \
  --candidate-config configs/data/telco_300m_tokenizer_candidate.yaml \
  --model-config configs/matgpt_telco_300m.yaml \
  --work-dir <local-work-root> \
  --drive-dir <streamed-drive-publish-root> \
  --baseline-tokenizer <preserved-pilot-tokenizer-dir> \
  --candidate-tokenizer <streamed-drive-publish-root>/tokenizers/representative_200m \
  --holdout-manifest <local-work-root>/tokenizer_sample/manifest.json
```

Expected output is `<streamed-drive-publish-root>/comparison.json`. It includes
both evaluations, shared holdout/probe fingerprints, tokenizer fingerprints,
hard guardrail failures, eligibility, and a recommendation. Existing output is
refused so an earlier decision record cannot be silently replaced.

The candidate argument must resolve exactly to
`<streamed-drive-publish-root>/tokenizers/representative_200m`, and its report,
tokenizer checksum, and canonical sample-manifest fingerprint must agree. The
CLI rejects swapped sides and equal baseline/candidate tokenizer fingerprints
before writing comparison evidence.

## Stage 4: review, then `tokenizer_select`

Open `comparison.json` and review at least `eligible`, `guardrail_failures`,
`recommended_winner`, per-role token counts, probe fragmentation, and every
fingerprint. Selection is a separate human gate. The CLI does not default a
winner, does not auto-accept the recommendation, and requires `--approve`.

```bash
uv run python scripts/prepare_telco_local.py \
  --stage tokenizer_select \
  --sources configs/data/telco_300m_sources.yaml \
  --mixture configs/data/telco_300m_mixture.yaml \
  --candidate-config configs/data/telco_300m_tokenizer_candidate.yaml \
  --model-config configs/matgpt_telco_300m.yaml \
  --work-dir <local-work-root> \
  --drive-dir <streamed-drive-publish-root> \
  --comparison <streamed-drive-publish-root>/comparison.json \
  --winner <pilot_20m-or-representative_200m> \
  --approve
```

Expected output is a new
`<streamed-drive-publish-root>/tokenizer_selection.json`. Exclusive creation
prevents replacement. The selection binds the comparison checksum and selected
tokenizer digest; it never copies over or modifies either tokenizer. An
ineligible `representative_200m` request fails.

If `representative_200m` is selected, all dependent pilot preparation, smoke,
pilot, and evaluation gates must be refreshed under the new tokenizer
fingerprint before a full-run approval. This increment records the decision but
does not perform that later refresh.

## Progress, disk pressure, and recovery

While a long stage runs, use another terminal:

```bash
df -h <local-work-root>
du -sh <local-work-root> <streamed-drive-publish-root>
ps -o pid,etime,%cpu,%mem,command -ax | grep prepare_telco_local.py
```

Stop the sample with `Ctrl-C` before free local disk reaches the checked 25GiB
floor or the local tree approaches its 20GiB working budget. Drive streaming
can retain an upload cache, so a small artifact tree is not proof of equivalent
free local space. A later corpus-builder increment adds automated disk and
publication backpressure; this tokenizer-only increment relies on the operator
check above.

| Symptom | Safe response |
|---|---|
| Network/authentication error | Fix access, then rerun the identical sample command. |
| Laptop slept, rebooted, or process was killed | Rerun the identical sample command; the journal verifies and resumes committed units. |
| Fingerprint mismatch | Stop. Restore the exact configs/pattern files or choose a fresh work root; do not mix identities. |
| Source exhausted before quota | Preserve logs and evidence; investigate the pinned source/recipe rather than changing quotas mid-run. |
| Missing/changed schema or license evidence | Stop and review the source registry; do not bypass validation. |
| Sample chunk integrity failure | Preserve the workspace for diagnosis. Do not edit the chunk or journal. |
| Candidate directory already exists | Review whether it is complete; preserve or move it aside before a deliberate fresh run. |
| Comparison or selection already exists | Treat it as immutable evidence; use a new reviewed publish namespace for a new decision. |

Do not delete old pilot artifacts, incomplete Drive staging trees, journals, or
selection evidence as part of this workflow.
