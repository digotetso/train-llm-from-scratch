# Integrated T4 Training And Course Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the 8.39M TinyStories run safe to start on a Google Colab T4, preserve trustworthy run evidence, and create the complete course outline plus the first finished video package.

**Architecture:** Keep the existing PyTorch pipeline and add small, testable boundaries around tokenizer coverage, schedule planning, AMP update accounting, run artifacts, and preflight validation. The Colab notebook uses local ephemeral storage for performance, synchronizes durable artifacts to Google Drive, and advances through smoke, pilot, and full stages only after explicit review. Course files consume verified repository behavior and run evidence rather than guessed output.

**Tech Stack:** Python 3.10+, PyTorch, Hugging Face `datasets`, Hugging Face `tokenizers`, NumPy, PyYAML, pytest, Google Colab T4, Google Drive, Markdown, Jupyter Notebook JSON.

**Design specification:** `docs/superpowers/specs/2026-07-19-integrated-training-course-design.md`

## Global Constraints

- Preserve all existing user changes. Do not revert, reformat, or stage unrelated hunks.
- The worktree is dirty. Before every commit, inspect `git diff -- <task-files>` and `git diff --cached`; if a modified file contains pre-existing user work that cannot be isolated safely, leave that file uncommitted and report it instead of sweeping it into a commit.
- Use `apply_patch` for manual file edits, including notebook JSON edits.
- Follow TDD for every behavior change: failing focused test, minimal implementation, focused pass, broader pass.
- Tests must not download TinyStories or require CUDA.
- CUDA-only acceptance is deferred to the real Colab T4 gates.
- Do not add dependencies unless the current standard library and declared packages are insufficient.
- The byte-level alphabet has 256 symbols; seven unique special tokens require a minimum requested vocabulary of 263.
- The real 8M run uses TinyStories revision `f54c09fd23315a6f9c86f9dc80f725de7d8f9c64`.
- The 8M schedule remains 32,768 tokens per optimizer update, 6,104 planned updates, 122 warmup updates, and pilot stop step 306.
- `--max-steps N` means at most N additional successful optimizer updates in the current invocation; it never shortens the 6,104-step schedule.
- Abort after five consecutive skipped AMP optimizer updates.
- Never promote the 10M-token pilot automatically to the 200M-token run.
- Produce one course video at a time after the outline and reusable template exist.

## File And Responsibility Map

**Create:**

- `matgpt/training/schedule.py`: derive token/update counts, full schedule horizon, warmup, invocation stop, and per-step learning rate.
- `matgpt/training/metrics.py`: define one stable CSV schema and append train/validation rows safely.
- `matgpt/training/artifacts.py`: write immutable configuration, environment, and fingerprint artifacts.
- `matgpt/preflight.py`: pure and filesystem-backed readiness checks with a machine-readable report.
- `matgpt/training/run_summary.py`: summarize metrics and artifacts after a run.
- `scripts/preflight_t4.py`: CLI for preflight checks.
- `scripts/summarize_run.py`: CLI for `run_summary.md`.
- `tests/test_schedule.py`: schedule and resume-equivalence tests.
- `tests/test_preflight.py`: synthetic artifact and failure-report tests.
- `tests/test_benchmark.py`: finite-loss, finite-gradient, throughput, and memory result tests.
- `tests/test_run_summary.py`: evaluation artifact and summary tests.
- `tests/test_course_structure.py`: course outline/template/Video 1 contract tests.
- `docs/runbooks/colab-t4-first-run.md`: exact gate commands, expected evidence, stop conditions, and recovery steps.
- `course/outline.md`: all 64 approved video titles in order.
- `course/glossary.md`: beginner-first definitions introduced by Video 1 and expansion rules.
- `course/templates/video/`: six reusable Markdown templates.
- `course/videos/001-computer-learning-from-text/`: complete Video 1 package plus runnable lab.

**Modify:**

- `matgpt/config.py`: byte-BPE minimum vocabulary and skipped-update limit validation.
- `matgpt/tokenizer/train.py`: complete initial byte alphabet.
- `matgpt/training/amp.py`: public-hook optimizer update tracking.
- `matgpt/training/checkpoint.py`: separate checkpoint reading from state application so compatibility is checked first.
- `matgpt/training/pretrain.py`: fixed schedule, baseline evaluation, finite checks, AMP counters, stable metrics, and run artifacts.
- `matgpt/utils/logging.py`: explicit CSV field order.
- `scripts/pretrain.py`: precise `--max-steps` help text.
- `scripts/benchmark_t4.py`: report finite loss, gradient norm, and memory fraction.
- `scripts/evaluate.py`: persist evaluation JSON.
- `configs/matgpt_mini_8m.yaml`: pin TinyStories and set the consecutive-skip limit.
- `notebooks/train_matgpt_t4_base_colab.ipynb`: stage-gated local/Drive workflow.
- `tests/test_config.py`, `tests/test_tokenizer.py`, `tests/test_shards.py`, `tests/test_pretrain_smoke.py`, `tests/test_training_core.py`, `tests/test_tracking.py`, `tests/test_notebook_colab.py`: focused regression coverage.
- `README.md`: point to preflight, runbook, stage semantics, and evidence.
- `docs/llm_training_progress.md`: record completed theory and the practical build phase.

---

### Task 1: Guarantee Complete Byte-Level Tokenizer Coverage

**Files:**
- Modify: `matgpt/config.py:10-61`
- Modify: `matgpt/tokenizer/train.py:41-67`
- Modify: `tests/test_config.py:1-42`
- Modify: `tests/test_tokenizer.py:1-54`
- Modify: `tests/test_shards.py:1-50`
- Modify: `tests/test_pretrain_smoke.py:1-118`

**Interfaces:**
- Produces: `minimum_byte_bpe_vocab_size(special_tokens: list[str]) -> int`
- Produces: byte-level BPE tokenizers whose initial alphabet is `pre_tokenizers.ByteLevel.alphabet()`
- Consumes: existing `tokenizer.algorithm`, `tokenizer.vocab_size`, and `tokenizer.special_tokens` configuration

- [ ] **Step 1: Write failing configuration and Unicode tests**

Add to `tests/test_config.py`:

```python
def test_config_rejects_byte_bpe_vocab_smaller_than_alphabet_and_specials():
    cfg = load_config("configs/matgpt_mini_8m.yaml")
    cfg["tokenizer"]["vocab_size"] = 262
    cfg["model"]["vocab_size"] = 262

    with pytest.raises(ValueError, match="at least 263"):
        validate_config(cfg)
```

Update the tokenizer fixture vocabulary and `report["vocab_size_actual"] <= 128` assertion to `320`, then add to `tests/test_tokenizer.py`:

```python
def test_byte_level_tokenizer_round_trips_unseen_unicode(tmp_path: Path):
    corpus = tmp_path / "train.jsonl"
    output_dir = tmp_path / "tokenizer"
    write_corpus(corpus)
    train_tokenizer_from_jsonl(
        [corpus],
        output_dir,
        vocab_size=320,
        min_frequency=1,
        special_tokens=SPECIAL_TOKENS,
    )
    tokenizer = load_tokenizer(output_dir)

    for text in ["🙂", "café", "你好", "A space, then punctuation!"]:
        ids = tokenizer.encode(text).ids
        assert ids, f"non-empty text encoded to no IDs: {text!r}"
        assert tokenizer.decode(ids) == text
```

Change tokenizer/model vocabulary values from `128` to `320` in `tests/test_shards.py` and `tests/test_pretrain_smoke.py` so their fixtures remain valid after minimum-vocabulary enforcement.

- [ ] **Step 2: Run the tests and verify the intended failures**

Run:

```bash
uv run pytest tests/test_config.py::test_config_rejects_byte_bpe_vocab_smaller_than_alphabet_and_specials tests/test_tokenizer.py::test_byte_level_tokenizer_round_trips_unseen_unicode -v
```

Expected: FAIL because config validation accepts 262 and the unseen emoji encoding is empty or does not round trip.

- [ ] **Step 3: Add minimum-vocabulary validation**

Add to `matgpt/config.py`:

```python
BYTE_LEVEL_ALPHABET_SIZE = 256


def minimum_byte_bpe_vocab_size(special_tokens: list[str]) -> int:
    return BYTE_LEVEL_ALPHABET_SIZE + len(set(special_tokens))
```

Inside `validate_config`, after reading `special_tokens`, add:

```python
if tokenizer.get("algorithm") == "byte_level_bpe":
    minimum_vocab = minimum_byte_bpe_vocab_size(special_tokens)
    if tokenizer["vocab_size"] < minimum_vocab:
        raise ValueError(
            "byte_level_bpe tokenizer.vocab_size must be at least "
            f"{minimum_vocab} for 256 byte symbols and "
            f"{len(set(special_tokens))} unique special tokens"
        )
```

- [ ] **Step 4: Give BPE the complete byte alphabet**

Add this argument to `trainers.BpeTrainer(...)` in `matgpt/tokenizer/train.py`:

```python
initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
```

- [ ] **Step 5: Run focused tokenizer, shard, and smoke tests**

Run:

```bash
uv run pytest tests/test_config.py tests/test_tokenizer.py tests/test_shards.py tests/test_pretrain_smoke.py -v
```

Expected: PASS, including unseen Unicode round trips and one-step synthetic pretraining.

- [ ] **Step 6: Commit only isolated task changes**

First inspect:

```bash
git diff -- matgpt/config.py matgpt/tokenizer/train.py tests/test_config.py tests/test_tokenizer.py tests/test_shards.py tests/test_pretrain_smoke.py
```

If the diff contains only intended task hunks, stage those files and commit:

```bash
git add matgpt/config.py matgpt/tokenizer/train.py tests/test_config.py tests/test_tokenizer.py tests/test_shards.py tests/test_pretrain_smoke.py
git diff --cached --check
git commit -m "fix: guarantee byte tokenizer coverage"
```

Expected: one commit, or an explicit report that overlapping user hunks were left uncommitted.

---

### Task 2: Separate The Full Schedule From Invocation Stops

**Files:**
- Create: `matgpt/training/schedule.py`
- Create: `tests/test_schedule.py`
- Modify: `matgpt/training/pretrain.py:67-75,193-205,228-235,390-391`
- Modify: `scripts/pretrain.py:15-24`

**Interfaces:**
- Produces: `TrainingSchedule(tokens_per_step: int, total_steps: int, warmup_steps: int, stop_step: int)`
- Produces: `build_training_schedule(cfg: dict[str, Any], global_step: int = 0, max_steps_override: int | None = None) -> TrainingSchedule`
- Produces: `learning_rate_at_step(cfg: dict[str, Any], schedule: TrainingSchedule, step: int) -> float`
- Consumes: `cosine_warmup_lr(...)` from `matgpt.training.optim`

- [ ] **Step 1: Write failing schedule and resume-equivalence tests**

Create `tests/test_schedule.py`:

```python
import pytest
import torch

from matgpt.config import load_config
from matgpt.training.schedule import build_training_schedule, learning_rate_at_step


def test_mini_schedule_math_is_unchanged_by_smoke_cap():
    cfg = load_config("configs/matgpt_mini_8m.yaml")
    schedule = build_training_schedule(cfg, global_step=0, max_steps_override=20)

    assert schedule.tokens_per_step == 32_768
    assert schedule.total_steps == 6_104
    assert schedule.warmup_steps == 122
    assert schedule.stop_step == 20


def test_resumed_learning_rates_equal_uninterrupted_learning_rates():
    cfg = load_config("configs/matgpt_mini_8m.yaml")
    uninterrupted = build_training_schedule(cfg)
    first = build_training_schedule(cfg, global_step=0, max_steps_override=20)
    resumed = build_training_schedule(cfg, global_step=20, max_steps_override=5)

    expected = [learning_rate_at_step(cfg, uninterrupted, step) for step in range(25)]
    actual = [learning_rate_at_step(cfg, first, step) for step in range(20)]
    actual += [learning_rate_at_step(cfg, resumed, step) for step in range(20, 25)]
    assert actual == expected


def test_step_override_must_be_positive():
    cfg = load_config("configs/matgpt_mini_8m.yaml")
    with pytest.raises(ValueError, match="positive"):
        build_training_schedule(cfg, max_steps_override=0)
```

- [ ] **Step 2: Run the new test and verify import failure**

Run:

```bash
uv run pytest tests/test_schedule.py -v
```

Expected: FAIL because `matgpt.training.schedule` does not exist.

- [ ] **Step 3: Implement the schedule boundary**

Create `matgpt/training/schedule.py`:

```python
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from matgpt.training.optim import cosine_warmup_lr


@dataclass(frozen=True)
class TrainingSchedule:
    tokens_per_step: int
    total_steps: int
    warmup_steps: int
    stop_step: int


def build_training_schedule(
    cfg: dict[str, Any],
    global_step: int = 0,
    max_steps_override: int | None = None,
) -> TrainingSchedule:
    if max_steps_override is not None and max_steps_override < 1:
        raise ValueError("max_steps_override must be positive")
    training = cfg["training"]
    tokens_per_step = (
        training["micro_batch_size"]
        * training["gradient_accumulation_steps"]
        * cfg["model"]["context_length"]
    )
    total_steps = max(1, math.ceil(training["max_tokens"] / tokens_per_step))
    warmup_steps = max(1, int(total_steps * training["warmup_ratio"]))
    stop_step = total_steps
    if max_steps_override is not None:
        stop_step = min(total_steps, global_step + max_steps_override)
    return TrainingSchedule(tokens_per_step, total_steps, warmup_steps, stop_step)


def learning_rate_at_step(
    cfg: dict[str, Any],
    schedule: TrainingSchedule,
    step: int,
) -> float:
    return cosine_warmup_lr(
        step=step,
        warmup_steps=schedule.warmup_steps,
        total_steps=schedule.total_steps,
        max_lr=cfg["training"]["learning_rate"],
        min_lr=cfg["training"]["min_learning_rate"],
    )
```

- [ ] **Step 4: Use the schedule in pretraining**

Replace the local `total_steps`, `warmup_steps`, and `tokens_per_step` derivation in `run_pretraining` with:

```python
schedule = build_training_schedule(
    cfg,
    global_step=state["global_step"],
    max_steps_override=max_steps_override,
)
```

Use:

```python
while (
    state["global_step"] < schedule.stop_step
    and state["tokens_processed"] < cfg["training"]["max_tokens"]
):
    lr = learning_rate_at_step(cfg, schedule, state["global_step"])
```

Import `asdict` from `dataclasses` and return `asdict(schedule)` under a `schedule` key. Remove `_steps_from_tokens` only after `rg '_steps_from_tokens'` confirms no callers remain.

- [ ] **Step 5: Clarify the CLI contract**

Change the `--max-steps` help text in `scripts/pretrain.py` to:

```python
help="Maximum additional successful optimizer updates in this invocation; the full LR schedule is unchanged.",
```

- [ ] **Step 6: Run schedule and smoke tests**

Run:

```bash
uv run pytest tests/test_schedule.py tests/test_pretrain_smoke.py tests/test_training_core.py -v
```

Expected: PASS; the one-step smoke result reports the full schedule horizon and a stop step of 1.

- [ ] **Step 7: Commit the schedule unit**

```bash
git add matgpt/training/schedule.py tests/test_schedule.py matgpt/training/pretrain.py scripts/pretrain.py
git diff --cached --check
git commit -m "fix: preserve full learning rate schedule"
```

Stage modified existing files only when their pre-existing user hunks have been isolated safely.

---

### Task 3: Write Stable Metrics And Immutable Run Metadata

**Files:**
- Create: `matgpt/training/metrics.py`
- Create: `matgpt/training/artifacts.py`
- Modify: `matgpt/utils/logging.py:14-20`
- Modify: `matgpt/training/checkpoint.py:62-79`
- Modify: `matgpt/training/pretrain.py:131-202,281-340,381-391`
- Modify: `tests/test_tracking.py:1-20`
- Modify: `tests/test_pretrain_smoke.py:115-118`
- Modify: `tests/test_training_core.py:70-95`

**Interfaces:**
- Produces: `METRIC_FIELDS: tuple[str, ...]`
- Produces: `append_metric(path: str | Path, row: Mapping[str, object]) -> None`
- Produces: `calculate_tokens_per_second(start_tokens: int, current_tokens: int, elapsed_seconds: float) -> float`
- Produces: `write_run_artifacts(run_dir: Path, cfg: dict[str, Any], extra: dict[str, Any], device: torch.device) -> dict[str, str]`
- Produces: `apply_checkpoint_payload(payload: dict[str, Any], model=None, optimizer=None, scaler=None, restore_rng: bool = False) -> None`
- Consumes: `config_to_yaml`, `sha256_text`, and the existing run `extra` fingerprints

- [ ] **Step 1: Write failing heterogeneous-CSV and artifact tests**

Add to `tests/test_tracking.py`:

```python
import csv

from matgpt.training.metrics import append_metric, calculate_tokens_per_second


def test_metric_rows_share_one_stable_csv_schema(tmp_path: Path):
    path = tmp_path / "metrics.csv"
    append_metric(path, {"event": "baseline", "global_step": 0, "val_loss": 5.0})
    append_metric(path, {"event": "train", "global_step": 1, "train_loss": 4.9})

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["val_loss"] == "5.0"
    assert rows[0]["train_loss"] == ""
    assert rows[1]["train_loss"] == "4.9"
    assert rows[1]["val_loss"] == ""


def test_resumed_throughput_uses_only_current_invocation_tokens():
    assert calculate_tokens_per_second(1_000_000, 1_032_768, 10.0) == 3_276.8
```

Add `import csv` to `tests/test_pretrain_smoke.py`, then extend its assertions:

```python
run_dir = tmp_path / "run"
assert (run_dir / "config.snapshot.yaml").exists()
assert (run_dir / "environment.json").exists()
assert (run_dir / "fingerprints.json").exists()
rows = list(csv.DictReader((run_dir / "metrics.csv").open(encoding="utf-8")))
assert rows[0]["event"] == "baseline"
assert rows[0]["global_step"] == "0"
assert rows[-1]["event"] == "train"
```

Add this checkpoint-order test to `tests/test_training_core.py`:

```python
from matgpt.training.checkpoint import apply_checkpoint_payload


def test_checkpoint_can_be_validated_before_state_is_applied(tmp_path: Path):
    torch.manual_seed(7)
    source = GPT(tiny_config())
    source_optimizer = build_optimizer(source, "adamw", 1e-3, 0.1, (0.9, 0.95))
    checkpoint = tmp_path / "latest.pt"
    save_checkpoint(
        checkpoint,
        source,
        source_optimizer,
        None,
        {"global_step": 3, "tokens_processed": 1024},
        {"run": {"name": "unit"}},
        {"config_sha256": "expected"},
    )
    restored = GPT(tiny_config())
    before = {name: value.detach().clone() for name, value in restored.state_dict().items()}

    payload = load_checkpoint(checkpoint)
    assert all(torch.equal(before[name], value) for name, value in restored.state_dict().items())
    validate_checkpoint_compatibility(payload, {"config_sha256": "expected"})
    apply_checkpoint_payload(payload, model=restored)

    assert all(
        torch.equal(source.state_dict()[name], restored.state_dict()[name])
        for name in source.state_dict()
    )
```

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```bash
uv run pytest tests/test_tracking.py::test_metric_rows_share_one_stable_csv_schema tests/test_pretrain_smoke.py::test_run_pretraining_one_step_with_synthetic_shards -v
```

Expected: FAIL because the metrics module and run artifacts do not exist.

- [ ] **Step 3: Add explicit CSV field order**

Change `append_csv_row` to accept an optional field list:

```python
def append_csv_row(
    path: str | Path,
    row: Mapping[str, object],
    fieldnames: tuple[str, ...] | list[str] | None = None,
) -> None:
    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists()
    fields = list(fieldnames) if fieldnames is not None else list(row.keys())
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="raise")
        if write_header:
            writer.writeheader()
        writer.writerow(row)
```

Create `matgpt/training/metrics.py` with this schema:

```python
METRIC_FIELDS = (
    "event",
    "attempted_step",
    "global_step",
    "tokens_processed",
    "train_loss",
    "val_loss",
    "val_perplexity",
    "lr",
    "grad_norm",
    "grad_scale",
    "optimizer_step_skipped",
    "optimizer_steps_skipped_total",
    "consecutive_optimizer_steps_skipped",
    "tokens_per_second",
    "peak_memory_mb",
    "elapsed_seconds",
)


def append_metric(path, row):
    append_csv_row(path, row, fieldnames=METRIC_FIELDS)


def calculate_tokens_per_second(start_tokens, current_tokens, elapsed_seconds):
    return (current_tokens - start_tokens) / max(elapsed_seconds, 1e-6)
```

- [ ] **Step 4: Implement immutable run artifacts**

Create `matgpt/training/artifacts.py` with:

```python
from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any

import torch

from matgpt.config import config_to_yaml


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _write_if_missing_or_equal(path: Path, text: str, label: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise ValueError(f"Existing {label} conflicts with the current run: {path}")
        return
    _atomic_write_text(path, text)


def _json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _write_json_if_missing(path: Path, payload: dict[str, Any]) -> None:
    if not path.exists():
        _atomic_write_text(path, _json_text(payload))


def _write_json_if_missing_or_equal(path: Path, payload: dict[str, Any], label: str) -> None:
    _write_if_missing_or_equal(path, _json_text(payload), label)


def write_run_artifacts(run_dir, cfg, extra, device):
    run_dir = Path(run_dir)
    config_text = config_to_yaml(cfg)
    _write_if_missing_or_equal(run_dir / "config.snapshot.yaml", config_text, "configuration snapshot")
    environment = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda,
        "device_type": device.type,
        "device_name": torch.cuda.get_device_name(device) if device.type == "cuda" else "cpu",
    }
    _write_json_if_missing(run_dir / "environment.json", environment)
    fingerprints = {
        "config_sha256": extra["config_sha256"],
        "tokenizer_sha256": extra["tokenizer_sha256"],
        "dataset_manifest_hash": extra["dataset_manifest_hash"],
        "git_commit": extra["git_commit"],
        "parameter_count": extra["parameter_count"],
    }
    _write_json_if_missing_or_equal(run_dir / "fingerprints.json", fingerprints, "fingerprints")
    return {
        "config": str(run_dir / "config.snapshot.yaml"),
        "environment": str(run_dir / "environment.json"),
        "fingerprints": str(run_dir / "fingerprints.json"),
}
```

The configuration and fingerprint writers reject conflicting existing content. The environment file records the first session and is not overwritten on resume.

- [ ] **Step 5: Record a step-zero validation baseline**

First split checkpoint reading from state application in `matgpt/training/checkpoint.py`:

```python
def apply_checkpoint_payload(
    payload,
    model=None,
    optimizer=None,
    scaler=None,
    restore_rng=False,
):
    if model is not None:
        model.load_state_dict(payload["model"])
    if optimizer is not None and payload.get("optimizer") is not None:
        optimizer.load_state_dict(payload["optimizer"])
    if scaler is not None and payload.get("scaler") is not None:
        scaler.load_state_dict(payload["scaler"])
    if restore_rng:
        restore_rng_state(payload.get("rng_state"))


def load_checkpoint(path, model=None, optimizer=None, scaler=None, map_location="cpu", restore_rng=False):
    payload = torch.load(Path(path), map_location=map_location, weights_only=False)
    apply_checkpoint_payload(payload, model, optimizer, scaler, restore_rng)
    return payload
```

In `run_pretraining`, read without applying, validate, then apply:

```python
payload = load_checkpoint(resume_from, map_location=device)
if not cfg["training"].get("allow_artifact_mismatch", False):
    validate_checkpoint_compatibility(payload, extra)
apply_checkpoint_payload(
    payload,
    model=model,
    optimizer=optimizer,
    scaler=scaler,
    restore_rng=True,
)
```

Only after compatibility succeeds should dataset RNG state and scalar counters be restored.

After checkpoint restoration and before the training loop, write run artifacts and retain the returned path mapping as `run_artifacts`. For a fresh run only, evaluate validation loss before the first update:

```python
if state["global_step"] == 0 and "initial_val_loss" not in state:
    initial_val_loss = evaluate_loss(
        model=train_model,
        dataset=val_dataset,
        batch_size=cfg["training"]["micro_batch_size"],
        eval_batches=cfg["training"]["eval_batches"],
        device=device,
        precision=cfg["training"]["precision"],
    )
    if not math.isfinite(initial_val_loss):
        raise FloatingPointError(f"Non-finite baseline validation loss: {initial_val_loss}")
    state["initial_val_loss"] = initial_val_loss
    state["best_val_loss"] = initial_val_loss
    append_metric(metrics_path, {
        "event": "baseline",
        "attempted_step": 0,
        "global_step": 0,
        "tokens_processed": 0,
        "val_loss": initial_val_loss,
        "val_perplexity": perplexity(initial_val_loss),
        "peak_memory_mb": _peak_memory_mb(device),
        "elapsed_seconds": 0.0,
    })
    tracker.log(
        {"val_loss": initial_val_loss, "val_perplexity": perplexity(initial_val_loss)},
        step=0,
    )
```

Create the experiment tracker before this baseline block. Replace all training and validation `append_csv_row` calls with `append_metric`, always including `event`. Include `"artifacts": run_artifacts` in the final `run_pretraining` result.

Before the loop, retain invocation-local starting values while preserving cumulative elapsed time in checkpoint state:

```python
state.setdefault("elapsed_seconds", 0.0)
elapsed_before_invocation = float(state["elapsed_seconds"])
invocation_start_tokens = int(state["tokens_processed"])
invocation_start_time = time.time()
```

After every attempted update, calculate:

```python
invocation_elapsed = max(1e-6, time.time() - invocation_start_time)
state["elapsed_seconds"] = elapsed_before_invocation + invocation_elapsed
tokens_per_second = calculate_tokens_per_second(
    invocation_start_tokens,
    state["tokens_processed"],
    invocation_elapsed,
)
```

Log cumulative `state["elapsed_seconds"]` in the `elapsed_seconds` CSV column. This prevents resumed invocations from dividing historical token counts by only the new process runtime.

- [ ] **Step 6: Run focused tests**

```bash
uv run pytest tests/test_tracking.py tests/test_training_core.py tests/test_pretrain_smoke.py -v
```

Expected: PASS; `metrics.csv` parses under one header and begins with a finite baseline row.

- [ ] **Step 7: Commit the metrics and artifact boundary**

```bash
git add matgpt/training/metrics.py matgpt/training/artifacts.py matgpt/training/checkpoint.py matgpt/utils/logging.py matgpt/training/pretrain.py tests/test_tracking.py tests/test_training_core.py tests/test_pretrain_smoke.py
git diff --cached --check
git commit -m "feat: preserve trustworthy run evidence"
```

---

### Task 4: Track AMP Skips And Abort Unstable Training

**Files:**
- Modify: `matgpt/training/amp.py:1-34`
- Modify: `matgpt/training/pretrain.py:183-389`
- Modify: `matgpt/config.py:37-61`
- Modify: `configs/matgpt_mini_8m.yaml:48-75`
- Modify: `tests/test_training_core.py:1-133`
- Modify: `tests/test_config.py:1-42`
- Modify: `tests/test_pretrain_smoke.py:84-105`

**Interfaces:**
- Produces: `OptimizerStepTracker`
- Produces: `ScalerStepResult(update_applied: bool, scale_before: float, scale_after: float)`
- Produces: `step_optimizer_with_scaler(scaler, optimizer, tracker) -> ScalerStepResult`
- Produces: `require_finite_loss(loss: torch.Tensor, *, global_step: int, label: str, lr: float, grad_scale: float) -> None`
- Consumes: `training.max_consecutive_skipped_updates`, fixed at 5 for the Mini run

- [ ] **Step 1: Write failing AMP tracker and stability tests**

Add `import pytest` to `tests/test_training_core.py`, then add:

```python
from matgpt.training.amp import OptimizerStepTracker, require_finite_loss, step_optimizer_with_scaler


class FakeScaler:
    def __init__(self, apply_update: bool):
        self.apply_update = apply_update
        self.scale_value = 1024.0

    def get_scale(self):
        return self.scale_value

    def step(self, optimizer):
        if self.apply_update:
            optimizer.step()

    def update(self):
        if not self.apply_update:
            self.scale_value /= 2


def test_optimizer_step_tracker_detects_applied_and_skipped_updates():
    parameter = torch.nn.Parameter(torch.tensor(1.0))
    optimizer = torch.optim.SGD([parameter], lr=0.1)
    tracker = OptimizerStepTracker(optimizer)
    try:
        applied = step_optimizer_with_scaler(FakeScaler(True), optimizer, tracker)
        skipped = step_optimizer_with_scaler(FakeScaler(False), optimizer, tracker)
    finally:
        tracker.close()

    assert applied.update_applied is True
    assert skipped.update_applied is False
    assert skipped.scale_after == 512.0


def test_require_finite_loss_rejects_nan():
    with pytest.raises(FloatingPointError, match="micro-batch"):
        require_finite_loss(
            torch.tensor(float("nan")),
            global_step=7,
            label="micro-batch",
            lr=1e-4,
            grad_scale=1024.0,
        )
```

Add config validation coverage:

```python
def test_config_rejects_nonpositive_skipped_update_limit():
    cfg = load_config("configs/matgpt_mini_8m.yaml")
    cfg["training"]["max_consecutive_skipped_updates"] = 0
    with pytest.raises(ValueError, match="max_consecutive_skipped_updates"):
        validate_config(cfg)
```

- [ ] **Step 2: Run tests and verify missing-interface failures**

```bash
uv run pytest tests/test_training_core.py::test_optimizer_step_tracker_detects_applied_and_skipped_updates tests/test_config.py::test_config_rejects_nonpositive_skipped_update_limit -v
```

Expected: FAIL because the tracker and config key do not exist.

- [ ] **Step 3: Implement public-hook update tracking**

Add to `matgpt/training/amp.py`:

```python
@dataclass(frozen=True)
class ScalerStepResult:
    update_applied: bool
    scale_before: float
    scale_after: float


class OptimizerStepTracker:
    def __init__(self, optimizer: torch.optim.Optimizer) -> None:
        self.count = 0
        self._handle = optimizer.register_step_pre_hook(self._before_step)

    def _before_step(self, optimizer, args, kwargs):
        self.count += 1

    def close(self) -> None:
        self._handle.remove()


def step_optimizer_with_scaler(scaler, optimizer, tracker):
    count_before = tracker.count
    scale_before = float(scaler.get_scale())
    scaler.step(optimizer)
    scaler.update()
    return ScalerStepResult(
        update_applied=tracker.count > count_before,
        scale_before=scale_before,
        scale_after=float(scaler.get_scale()),
    )


def require_finite_loss(
    loss: torch.Tensor,
    *,
    global_step: int,
    label: str,
    lr: float,
    grad_scale: float,
) -> None:
    if bool(torch.isfinite(loss).all()):
        return
    value = float(loss.detach().cpu())
    raise FloatingPointError(
        f"Non-finite {label} loss at global_step={global_step}: "
        f"loss={value} lr={lr} grad_scale={grad_scale}"
    )
```

Use the public optimizer hook only; do not read private GradScaler attributes.

API basis: PyTorch documents that `GradScaler.step()` calls `optimizer.step()` only when gradients contain no Inf/NaN values, and that an optimizer step pre-hook runs before `optimizer.step()`: [AMP examples](https://docs.pytorch.org/docs/stable/notes/amp_examples.html), [optimizer hook API](https://docs.pytorch.org/docs/stable/optim).

- [ ] **Step 4: Validate the skip limit**

Add to the Mini config:

```yaml
max_consecutive_skipped_updates: 5
```

Add to `validate_config`:

```python
if training.get("max_consecutive_skipped_updates", 5) < 1:
    raise ValueError("training.max_consecutive_skipped_updates must be positive")
```

Add the same key to synthetic pretraining test configuration.

- [ ] **Step 5: Enforce finite loss and update counters**

Initialize or restore these state keys:

```python
state.setdefault("attempted_steps", state["global_step"])
state.setdefault("optimizer_steps_skipped_total", 0)
state.setdefault("consecutive_optimizer_steps_skipped", 0)
```

Before each backward call:

```python
require_finite_loss(
    loss,
    global_step=state["global_step"],
    label="micro-batch",
    lr=lr,
    grad_scale=float(scaler.get_scale()),
)
```

Replace direct `scaler.step()` and `scaler.update()` with `step_optimizer_with_scaler`. Advance counters as follows:

```python
state["attempted_steps"] += 1
state["tokens_processed"] += schedule.tokens_per_step
if step_result.update_applied:
    state["global_step"] += 1
    state["consecutive_optimizer_steps_skipped"] = 0
else:
    state["optimizer_steps_skipped_total"] += 1
    state["consecutive_optimizer_steps_skipped"] += 1
```

The learning-rate schedule advances only after an applied optimizer update. Log skipped attempts even when they do not fall on the normal log interval. Raise `FloatingPointError` when the consecutive count reaches the configured limit, before periodic checkpoint code runs.

Use this exact branch after updating the counters:

```python
optimizer_step_skipped = not step_result.update_applied
should_log = (
    optimizer_step_skipped
    or state["global_step"] % cfg["training"]["log_interval_steps"] == 0
)
if should_log:
    append_metric(metrics_path, {
        "event": "train",
        "attempted_step": state["attempted_steps"],
        "global_step": state["global_step"],
        "tokens_processed": state["tokens_processed"],
        "train_loss": step_loss,
        "lr": lr,
        "grad_norm": float(grad_norm.detach().cpu()),
        "grad_scale": step_result.scale_after,
        "optimizer_step_skipped": optimizer_step_skipped,
        "optimizer_steps_skipped_total": state["optimizer_steps_skipped_total"],
        "consecutive_optimizer_steps_skipped": state["consecutive_optimizer_steps_skipped"],
        "tokens_per_second": tokens_per_second,
        "peak_memory_mb": _peak_memory_mb(device),
        "elapsed_seconds": state["elapsed_seconds"],
    })

skip_limit = int(cfg["training"].get("max_consecutive_skipped_updates", 5))
if state["consecutive_optimizer_steps_skipped"] >= skip_limit:
    raise FloatingPointError(
        "Aborting after repeated skipped optimizer updates: "
        f"global_step={state['global_step']} "
        f"consecutive_skips={state['consecutive_optimizer_steps_skipped']} "
        f"loss={step_loss} grad_norm={float(grad_norm.detach().cpu())} "
        f"lr={lr} grad_scale={step_result.scale_after}"
    )
```

- [ ] **Step 6: Guarantee tracker cleanup**

Wrap the training section in `try/finally` and call:

```python
optimizer_step_tracker.close()
tracker.finish()
```

Save the final `latest.pt` only on normal loop completion. Non-finite-loss and five-skip failures must not overwrite the last known-good checkpoint.

- [ ] **Step 7: Assert new smoke metrics**

Extend `tests/test_pretrain_smoke.py`:

```python
assert rows[-1]["grad_scale"] == "1.0"
assert rows[-1]["optimizer_step_skipped"] == "False"
assert rows[-1]["optimizer_steps_skipped_total"] == "0"
assert result["state"]["attempted_steps"] == 1
assert result["state"]["global_step"] == 1
```

- [ ] **Step 8: Run focused and broader training tests**

```bash
uv run pytest tests/test_config.py tests/test_training_core.py tests/test_pretrain_smoke.py tests/test_tracking.py -v
```

Expected: PASS; CPU GradScaler scale is 1.0 and the update is recorded as applied.

- [ ] **Step 9: Commit the stability unit**

```bash
git add matgpt/training/amp.py matgpt/training/pretrain.py matgpt/config.py configs/matgpt_mini_8m.yaml tests/test_training_core.py tests/test_config.py tests/test_pretrain_smoke.py
git diff --cached --check
git commit -m "feat: detect skipped and unstable updates"
```

---

### Task 5: Build A Fail-Closed Colab Preflight

**Files:**
- Create: `matgpt/preflight.py`
- Create: `scripts/preflight_t4.py`
- Create: `tests/test_preflight.py`
- Modify: `configs/matgpt_mini_8m.yaml:8-20`
- Modify: `tests/test_config.py:11-17`

**Interfaces:**
- Produces: `PreflightCheck(name: str, status: str, message: str, details: dict[str, Any])`
- Produces: `build_preflight_report(cfg: dict[str, Any], require_t4: bool, min_free_disk_gb: float) -> dict[str, Any]`
- Produces: `run_preflight(cfg: dict[str, Any], report_path: str | Path, require_t4: bool = False, min_free_disk_gb: float = 0.0) -> dict[str, Any]`
- Consumes: dataset `manifest.json`, tokenizer files, split shard metadata, schedule, and model report

- [ ] **Step 1: Pin the immutable dataset revision and test it**

Set in `configs/matgpt_mini_8m.yaml`:

```yaml
revision: f54c09fd23315a6f9c86f9dc80f725de7d8f9c64
```

Add to `tests/test_config.py`:

```python
assert cfg["dataset"]["revision"] == "f54c09fd23315a6f9c86f9dc80f725de7d8f9c64"
```

Source: the official [TinyStories commit page](https://huggingface.co/datasets/roneneldan/TinyStories/commit/f54c09fd23315a6f9c86f9dc80f725de7d8f9c64).

- [ ] **Step 2: Write failing synthetic preflight tests**

Create `tests/test_preflight.py` with this synthetic fixture and the two tests below:

```python
import json
from pathlib import Path

import pytest

from matgpt.config import clone_config, load_config
from matgpt.data.prepare import make_document_record, write_jsonl_records, write_manifest
from matgpt.data.shard import tokenize_splits_from_config
from matgpt.preflight import build_preflight_report, run_preflight
from matgpt.tokenizer.train import train_tokenizer_from_config


SPECIAL_TOKENS = [
    "<|pad|>", "<|bos|>", "<|eos|>", "<|system|>",
    "<|user|>", "<|assistant|>", "<|end|>",
]
REVISION = "f54c09fd23315a6f9c86f9dc80f725de7d8f9c64"


@pytest.fixture
def synthetic_preflight_cfg(tmp_path: Path):
    cfg = clone_config(load_config("configs/matgpt_mini_8m.yaml"))
    normalized = tmp_path / "normalized"
    tokenizer_dir = tmp_path / "tokenizer"
    shard_dir = tmp_path / "shards"
    run_dir = tmp_path / "run"

    train_records = [
        make_document_record(
            "unit",
            "train",
            index,
            f"Story number {index} has alpha{index}, beta{index}, gamma{index}, and a happy ending.",
        )
        for index in range(40)
    ]
    validation_records = [
        make_document_record(
            "unit",
            "validation",
            index,
            f"Validation tale {index} contains delta{index}, epsilon{index}, and a different ending.",
        )
        for index in range(10)
    ]
    train_stats = write_jsonl_records(normalized / "train.jsonl", train_records)
    validation_stats = write_jsonl_records(normalized / "validation.jsonl", validation_records)
    write_manifest(
        normalized / "manifest.json",
        dataset_name="unit",
        version_or_commit=REVISION,
        license_name="test",
        stage="base_pretraining",
        language="en",
        split_stats={"train": train_stats, "validation": validation_stats},
        notes="synthetic preflight fixture",
    )

    cfg["run"]["name"] = "unit_preflight"
    cfg["run"]["output_dir"] = str(run_dir)
    cfg["dataset"].update({
        "hf_name": "unit",
        "revision": REVISION,
        "normalized_dir": str(normalized),
        "train_split": "train",
        "validation_split": "validation",
    })
    cfg["tokenizer"].update({
        "vocab_size": 320,
        "output_dir": str(tokenizer_dir),
        "min_frequency": 1,
        "special_tokens": SPECIAL_TOKENS,
    })
    cfg["model"]["vocab_size"] = 320
    cfg["model"]["context_length"] = 8
    cfg["sharding"].update({
        "output_dir": str(shard_dir),
        "shard_size_tokens": 4096,
        "dtype": "uint16",
        "append_eos": True,
    })
    cfg["training"]["max_tokens"] = 4096

    tokenizer_report = train_tokenizer_from_config(cfg)
    assert tokenizer_report["vocab_size_actual"] == 320
    tokenize_splits_from_config(cfg)
    return cfg


def test_preflight_passes_complete_synthetic_artifacts(synthetic_preflight_cfg, tmp_path):
    report = run_preflight(
        synthetic_preflight_cfg,
        tmp_path / "preflight.json",
        require_t4=False,
        min_free_disk_gb=0.0,
    )
    assert report["status"] == "pass"
    assert all(check["status"] == "pass" for check in report["checks"])
    assert (tmp_path / "preflight.json").exists()


def test_preflight_reports_train_validation_overlap(synthetic_preflight_cfg, tmp_path):
    validation_path = Path(synthetic_preflight_cfg["dataset"]["normalized_dir"]) / "validation.jsonl"
    train_record = json.loads(
        (Path(synthetic_preflight_cfg["dataset"]["normalized_dir"]) / "train.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    validation_path.write_text(json.dumps(train_record) + "\n", encoding="utf-8")
    report = build_preflight_report(synthetic_preflight_cfg, require_t4=False, min_free_disk_gb=0.0)
    overlap = next(check for check in report["checks"] if check["name"] == "dataset_overlap")
    assert overlap["status"] == "fail"


def test_preflight_rejects_incompatible_latest_checkpoint(synthetic_preflight_cfg):
    checkpoint = Path(synthetic_preflight_cfg["run"]["output_dir"]) / "checkpoints" / "latest.pt"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"extra": {"config_sha256": "wrong"}, "state": {}}, checkpoint)

    report = build_preflight_report(synthetic_preflight_cfg, require_t4=False, min_free_disk_gb=0.0)
    check = next(item for item in report["checks"] if item["name"] == "checkpoint")
    assert check["status"] == "fail"
```

- [ ] **Step 3: Run tests and verify module failure**

```bash
uv run pytest tests/test_preflight.py -v
```

Expected: FAIL because `matgpt.preflight` does not exist.

- [ ] **Step 4: Implement structured checks**

Create `matgpt/preflight.py`. Use this check contract:

```python
from __future__ import annotations

import json
import platform
import re
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import torch

from matgpt.config import config_to_yaml, validate_config
from matgpt.data.prepare import effective_validation_split
from matgpt.model.gpt import GPT, GPTConfig, count_parameters
from matgpt.tokenizer.io import load_tokenizer, load_tokenizer_metadata
from matgpt.training.dataset import metadata_path_for_split
from matgpt.training.pretrain import validate_checkpoint_compatibility
from matgpt.training.schedule import build_training_schedule
from matgpt.utils.hashing import sha256_file, sha256_json, sha256_text


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def _run_check(name: str, function: Callable[[], dict[str, Any]]) -> PreflightCheck:
    try:
        details = function()
        return PreflightCheck(name, "pass", "ok", details or {})
    except Exception as exc:
        return PreflightCheck(name, "fail", str(exc), {})
```

Add these dataset and configuration checks:

```python
def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Required JSON artifact is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _nonempty_jsonl_rows(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"Required JSONL artifact is missing: {path}")
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.strip():
                yield line_number, json.loads(line)


def _check_config(cfg: dict[str, Any]) -> dict[str, Any]:
    validate_config(cfg)
    return {"run_name": cfg["run"]["name"]}


def _check_source_revision(cfg: dict[str, Any]) -> dict[str, Any]:
    revision = cfg["dataset"].get("revision")
    if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError(f"dataset.revision must be a 40-character commit hash; observed {revision!r}")
    return {"revision": revision}


def _check_dataset_manifest(cfg: dict[str, Any]) -> dict[str, Any]:
    dataset_cfg = cfg["dataset"]
    normalized = Path(dataset_cfg["normalized_dir"])
    manifest = _read_json(normalized / "manifest.json")
    if manifest.get("version_or_commit") != dataset_cfg["revision"]:
        raise ValueError(
            "Dataset revision mismatch: "
            f"manifest={manifest.get('version_or_commit')} config={dataset_cfg['revision']}"
        )
    stored_hash = manifest.get("manifest_sha256")
    hash_payload = dict(manifest)
    hash_payload.pop("manifest_sha256", None)
    if stored_hash != sha256_json(hash_payload):
        raise ValueError("Dataset manifest_sha256 does not match manifest content")
    counts = {}
    for split in (dataset_cfg["train_split"], effective_validation_split(dataset_cfg)):
        rows = sum(1 for _ in _nonempty_jsonl_rows(normalized / f"{split}.jsonl"))
        expected = int(manifest["split_stats"][split]["document_count"])
        if rows != expected or rows < 1:
            raise ValueError(f"{split} document count mismatch: file={rows} manifest={expected}")
        counts[split] = rows
    quality = manifest.get("quality_filter")
    if quality:
        accepted = int(quality["accepted_documents"])
        rejected = int(quality["rejected_documents"])
        total = int(quality["total_documents"])
        reason_total = sum(int(value) for value in quality["rejection_reasons"].values())
        if accepted != sum(counts.values()):
            raise ValueError(f"Quality accepted count mismatch: quality={accepted} files={sum(counts.values())}")
        if total != accepted + rejected or rejected != reason_total:
            raise ValueError(
                "Quality counts do not reconcile: "
                f"total={total} accepted={accepted} rejected={rejected} reasons={reason_total}"
            )
    return {"manifest_sha256": stored_hash, "document_counts": counts}


def _check_dataset_overlap(cfg: dict[str, Any]) -> dict[str, Any]:
    dataset_cfg = cfg["dataset"]
    normalized = Path(dataset_cfg["normalized_dir"])
    validation_split = effective_validation_split(dataset_cfg)
    validation_hashes = {
        row["text_sha256"]
        for _, row in _nonempty_jsonl_rows(normalized / f"{validation_split}.jsonl")
    }
    overlaps = []
    for _, row in _nonempty_jsonl_rows(normalized / f"{dataset_cfg['train_split']}.jsonl"):
        if row["text_sha256"] in validation_hashes:
            overlaps.append(row["text_sha256"])
            if len(overlaps) == 5:
                break
    if overlaps:
        raise ValueError(f"Exact train/validation overlap detected: {overlaps}")
    return {"overlap_count": 0, "validation_hash_count": len(validation_hashes)}
```

Add the tokenizer and shard checks:

```python
def _check_tokenizer(cfg: dict[str, Any]) -> dict[str, Any]:
    tokenizer_dir = Path(cfg["tokenizer"]["output_dir"])
    tokenizer_path = tokenizer_dir / "tokenizer.json"
    metadata = load_tokenizer_metadata(tokenizer_dir)
    tokenizer = load_tokenizer(tokenizer_dir)
    if sha256_file(tokenizer_path) != metadata.get("tokenizer_sha256"):
        raise ValueError("Tokenizer SHA-256 does not match special_tokens.json")
    actual_vocab = tokenizer.get_vocab_size()
    expected_vocab = int(cfg["tokenizer"]["vocab_size"])
    if actual_vocab != expected_vocab:
        raise ValueError(f"Tokenizer vocabulary mismatch: actual={actual_vocab} expected={expected_vocab}")
    missing_specials = [
        token for token in cfg["tokenizer"]["special_tokens"]
        if tokenizer.token_to_id(token) is None
    ]
    if missing_specials:
        raise ValueError(f"Tokenizer is missing special tokens: {missing_specials}")
    for probe in ["🙂", "café", "你好", "A space, then punctuation!"]:
        ids = tokenizer.encode(probe).ids
        if not ids or tokenizer.decode(ids) != probe:
            raise ValueError(f"Tokenizer Unicode round trip failed for {probe!r}")
    return {"tokenizer_sha256": metadata["tokenizer_sha256"], "vocab_size": actual_vocab}


def _check_shards(cfg: dict[str, Any]) -> dict[str, Any]:
    dtype_map = {"uint16": np.dtype(np.uint16), "uint32": np.dtype(np.uint32)}
    tokenizer = load_tokenizer(cfg["tokenizer"]["output_dir"])
    eos_id = tokenizer.token_to_id("<|eos|>")
    if eos_id is None:
        raise ValueError("Tokenizer has no <|eos|> ID")
    details = {}
    dataset_cfg = cfg["dataset"]
    for split in (dataset_cfg["train_split"], effective_validation_split(dataset_cfg)):
        metadata = _read_json(metadata_path_for_split(cfg["sharding"]["output_dir"], split))
        stored_hash = metadata.get("metadata_sha256")
        hash_payload = dict(metadata)
        hash_payload.pop("metadata_sha256", None)
        if stored_hash != sha256_json(hash_payload):
            raise ValueError(f"{split} metadata_sha256 does not match metadata content")
        dtype = dtype_map[metadata["dtype"]]
        total_tokens = 0
        eos_count = 0
        maximum_id = -1
        for shard in metadata["shards"]:
            path = Path(shard["path"])
            expected_tokens = int(shard["num_tokens"])
            expected_bytes = expected_tokens * dtype.itemsize
            if not path.is_file() or path.stat().st_size != expected_bytes:
                observed = path.stat().st_size if path.exists() else "missing"
                raise ValueError(f"{split} shard size mismatch for {path}: observed={observed} expected={expected_bytes}")
            if sha256_file(path) != shard["sha256"]:
                raise ValueError(f"{split} shard SHA-256 mismatch: {path}")
            values = np.memmap(path, mode="r", dtype=dtype)
            total_tokens += int(values.size)
            if values.size:
                maximum_id = max(maximum_id, int(values.max()))
                eos_count += int(np.count_nonzero(values == eos_id))
        if total_tokens != int(metadata["total_tokens"]):
            raise ValueError(f"{split} token total mismatch: files={total_tokens} metadata={metadata['total_tokens']}")
        if total_tokens < int(cfg["model"]["context_length"]) + 1:
            raise ValueError(f"{split} has too few tokens for one context window")
        if maximum_id >= int(cfg["tokenizer"]["vocab_size"]):
            raise ValueError(f"{split} token ID {maximum_id} exceeds the configured vocabulary")
        if metadata.get("append_eos") and eos_count != int(metadata["total_documents"]):
            raise ValueError(f"{split} EOS count mismatch: eos={eos_count} documents={metadata['total_documents']}")
        details[split] = {"total_tokens": total_tokens, "maximum_id": maximum_id, "eos_count": eos_count}
    return details
```

Add storage, device, schedule, and report assembly:

```python
def _check_output_storage(cfg: dict[str, Any], min_free_disk_gb: float) -> dict[str, Any]:
    output_dir = Path(cfg["run"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    probe = output_dir / ".preflight-write-probe"
    probe.write_text("ok\n", encoding="utf-8")
    probe.unlink()
    free_gb = shutil.disk_usage(output_dir).free / (1024**3)
    if free_gb < min_free_disk_gb:
        raise ValueError(f"Insufficient free disk: observed={free_gb:.2f} GiB required={min_free_disk_gb:.2f} GiB")
    return {"output_dir": str(output_dir), "free_disk_gb": free_gb}


def _check_device(require_t4: bool) -> dict[str, Any]:
    cuda = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if cuda else "cpu"
    total_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3) if cuda else 0.0
    if require_t4 and (not cuda or "T4" not in device_name or total_memory_gb < 14.0):
        raise ValueError(
            f"Google Colab T4 required: cuda={cuda} device={device_name!r} total_memory_gb={total_memory_gb:.2f}"
        )
    return {"cuda_available": cuda, "device_name": device_name, "total_memory_gb": total_memory_gb}


def _check_training_math(cfg: dict[str, Any]) -> dict[str, Any]:
    schedule = build_training_schedule(cfg)
    model = GPT(GPTConfig.from_dict(cfg["model"]))
    return {
        "parameter_count": count_parameters(model),
        "tokens_per_step": schedule.tokens_per_step,
        "total_steps": schedule.total_steps,
        "warmup_steps": schedule.warmup_steps,
    }


def _check_checkpoint(cfg: dict[str, Any]) -> dict[str, Any]:
    checkpoint = Path(cfg["run"]["output_dir"]) / "checkpoints" / "latest.pt"
    if not checkpoint.exists():
        return {"present": False}
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    tokenizer_metadata = load_tokenizer_metadata(cfg["tokenizer"]["output_dir"])
    expected = {
        "config_sha256": sha256_text(config_to_yaml(cfg)),
        "tokenizer_sha256": tokenizer_metadata["tokenizer_sha256"],
        "dataset_manifest_hash": sha256_file(Path(cfg["dataset"]["normalized_dir"]) / "manifest.json"),
    }
    validate_checkpoint_compatibility(payload, expected)
    return {
        "present": True,
        "path": str(checkpoint),
        "global_step": int(payload.get("state", {}).get("global_step", 0)),
    }


def build_preflight_report(
    cfg: dict[str, Any],
    require_t4: bool,
    min_free_disk_gb: float,
) -> dict[str, Any]:
    check_functions = [
        ("config", lambda: _check_config(cfg)),
        ("source_revision", lambda: _check_source_revision(cfg)),
        ("dataset_manifest", lambda: _check_dataset_manifest(cfg)),
        ("dataset_overlap", lambda: _check_dataset_overlap(cfg)),
        ("tokenizer", lambda: _check_tokenizer(cfg)),
        ("shards", lambda: _check_shards(cfg)),
        ("output_storage", lambda: _check_output_storage(cfg, min_free_disk_gb)),
        ("device", lambda: _check_device(require_t4)),
        ("training_math", lambda: _check_training_math(cfg)),
        ("checkpoint", lambda: _check_checkpoint(cfg)),
    ]
    checks = [_run_check(name, function) for name, function in check_functions]
    return {
        "status": "pass" if all(check.status == "pass" for check in checks) else "fail",
        "environment": {
            "python_version": platform.python_version(),
            "torch_version": torch.__version__,
            "cuda_version": torch.version.cuda,
            "cuda_available": torch.cuda.is_available(),
            "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        },
        "checks": [asdict(check) for check in checks],
    }
```

The report must include Python, PyTorch, CUDA, device, free disk, parameter count, and schedule details even when another check fails.

- [ ] **Step 5: Persist reports even on failure**

Implement:

```python
def run_preflight(cfg, report_path, require_t4=False, min_free_disk_gb=0.0):
    report = build_preflight_report(cfg, require_t4, min_free_disk_gb)
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if report["status"] != "pass":
        failures = [c for c in report["checks"] if c["status"] == "fail"]
        raise RuntimeError("Preflight failed: " + "; ".join(f"{c['name']}: {c['message']}" for c in failures))
    return report
```

Adjust the overlap test to call `build_preflight_report`; the pass test calls `run_preflight`.

- [ ] **Step 6: Add the CLI**

Create `scripts/preflight_t4.py`:

```python
#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.config import load_config
from matgpt.preflight import run_preflight


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate MatGPT artifacts and T4 readiness.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--require-t4", action="store_true")
    parser.add_argument("--min-free-disk-gb", type=float, default=0.0)
    args = parser.parse_args()

    cfg = load_config(args.config)
    output = Path(args.output) if args.output else Path(cfg["run"]["output_dir"]) / "preflight.json"
    report = run_preflight(
        cfg,
        output,
        require_t4=args.require_t4,
        min_free_disk_gb=args.min_free_disk_gb,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

On failure, retain `preflight.json` and return a nonzero process exit through the uncaught `RuntimeError`.

- [ ] **Step 7: Run preflight tests and local expected-failure probe**

```bash
uv run pytest tests/test_preflight.py tests/test_config.py -v
uv run python scripts/preflight_t4.py --config configs/matgpt_mini_8m.yaml
```

Expected: tests PASS. The real-config command FAILS clearly because production artifacts do not exist yet, while still writing `runs/matgpt_mini_8m/preflight.json`. Remove only that newly generated report after inspecting it; do not delete user artifacts.

- [ ] **Step 8: Commit the preflight unit**

```bash
git add matgpt/preflight.py scripts/preflight_t4.py tests/test_preflight.py configs/matgpt_mini_8m.yaml tests/test_config.py
git diff --cached --check
git commit -m "feat: add fail-closed T4 preflight"
```

---

### Task 6: Persist Evaluation Results And Build Run Summaries

**Files:**
- Create: `matgpt/training/run_summary.py`
- Create: `scripts/summarize_run.py`
- Create: `tests/test_run_summary.py`
- Modify: `scripts/evaluate.py:23-58`

**Interfaces:**
- Produces: `write_evaluation_result(path: str | Path, result: dict[str, Any]) -> Path`
- Produces: `build_run_summary(run_dir: str | Path, known_limitations: list[str]) -> str`
- Produces: `write_run_summary(run_dir: str | Path, known_limitations: list[str]) -> Path`
- Consumes: stable `metrics.csv`, checkpoints, config snapshot, environment, fingerprints, and evaluation JSON

- [ ] **Step 1: Write failing summary tests**

Create `tests/test_run_summary.py`:

```python
from pathlib import Path

from matgpt.training.run_summary import build_run_summary, write_evaluation_result


def test_evaluation_and_summary_are_persisted(tmp_path: Path):
    run_dir = tmp_path / "run"
    (run_dir / "checkpoints").mkdir(parents=True)
    (run_dir / "checkpoints" / "latest.pt").write_bytes(b"checkpoint")
    (run_dir / "checkpoints" / "best.pt").write_bytes(b"checkpoint")
    (run_dir / "config.snapshot.yaml").write_text("run:\n  name: unit\n", encoding="utf-8")
    (run_dir / "environment.json").write_text('{"device_name":"Tesla T4"}\n', encoding="utf-8")
    (run_dir / "fingerprints.json").write_text('{"config_sha256":"abc"}\n', encoding="utf-8")
    (run_dir / "metrics.csv").write_text(
        "event,global_step,tokens_processed,train_loss,val_loss,val_perplexity,tokens_per_second,peak_memory_mb,elapsed_seconds,optimizer_steps_skipped_total\n"
        "baseline,0,0,,5.0,148.4,,100,0,0\n"
        "train,1,32768,4.8,,,1000,2000,10,0\n"
        "validation,1,32768,,4.7,109.9,,2000,12,0\n",
        encoding="utf-8",
    )
    output = write_evaluation_result(run_dir / "evaluation" / "best.json", {"val_loss": 4.7})
    summary = build_run_summary(run_dir, ["Single T4 run; exact CUDA determinism is not claimed."])

    assert output.exists()
    assert "Initial validation loss: 5.0" in summary
    assert "Best validation loss: 4.7" in summary
    assert "Single T4 run" in summary
```

- [ ] **Step 2: Run the test and verify import failure**

```bash
uv run pytest tests/test_run_summary.py -v
```

Expected: FAIL because `matgpt.training.run_summary` does not exist.

- [ ] **Step 3: Implement evaluation persistence and summary rendering**

Create `matgpt/training/run_summary.py` with deterministic parsing, rendering, and atomic writes:

```python
from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path
from typing import Any


def write_evaluation_result(path, result):
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, out)
    return out


def _finite_values(rows: list[dict[str, str]], key: str) -> list[float]:
    values = []
    for row in rows:
        raw = row.get(key, "")
        if raw in (None, ""):
            continue
        value = float(raw)
        if math.isfinite(value):
            values.append(value)
    return values


def _load_json_if_present(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_run_summary(run_dir, known_limitations):
    root = Path(run_dir)
    metrics_path = root / "metrics.csv"
    if not metrics_path.is_file():
        raise FileNotFoundError(f"Run metrics are missing: {metrics_path}")
    with metrics_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    validation_losses = _finite_values(rows, "val_loss")
    training_losses = _finite_values(rows, "train_loss")
    throughput = _finite_values(rows, "tokens_per_second")
    peak_memory = _finite_values(rows, "peak_memory_mb")
    elapsed = _finite_values(rows, "elapsed_seconds")
    skipped = _finite_values(rows, "optimizer_steps_skipped_total")
    if not validation_losses:
        raise ValueError("No finite validation loss is present in metrics.csv")

    environment = _load_json_if_present(root / "environment.json")
    fingerprints = _load_json_if_present(root / "fingerprints.json")
    evaluation_files = sorted((root / "evaluation").glob("*.json")) if (root / "evaluation").exists() else []
    latest_exists = (root / "checkpoints" / "latest.pt").is_file()
    best_exists = (root / "checkpoints" / "best.pt").is_file()
    lines = [
        "# Run Summary",
        "",
        "## Identity",
        f"- Run directory: {root}",
        f"- Device: {environment.get('device_name', 'unknown')}",
        f"- Config SHA-256: {fingerprints.get('config_sha256', 'missing')}",
        "",
        "## Quality",
        f"- Initial validation loss: {validation_losses[0]}",
        f"- Best validation loss: {min(validation_losses)}",
        f"- Final validation loss: {validation_losses[-1]}",
        f"- Final training loss: {training_losses[-1] if training_losses else 'missing'}",
        "",
        "## Performance",
        f"- Maximum tokens/second: {max(throughput) if throughput else 'missing'}",
        f"- Peak memory MB: {max(peak_memory) if peak_memory else 'missing'}",
        f"- Elapsed seconds: {max(elapsed) if elapsed else 'missing'}",
        f"- Skipped optimizer updates: {int(max(skipped)) if skipped else 0}",
        "",
        "## Checkpoints",
        f"- latest.pt load candidate exists: {latest_exists}",
        f"- best.pt load candidate exists: {best_exists}",
        "",
        "## Evaluation Artifacts",
    ]
    lines.extend(f"- {path.name}" for path in evaluation_files)
    if not evaluation_files:
        lines.append("- none")
    lines.extend(["", "## Known Limitations"])
    lines.extend(f"- {limitation}" for limitation in known_limitations)
    return "\n".join(lines) + "\n"


def write_run_summary(run_dir, known_limitations):
    root = Path(run_dir)
    output = root / "run_summary.md"
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(build_run_summary(root, known_limitations), encoding="utf-8")
    os.replace(temporary, output)
    return output
```

- [ ] **Step 4: Update evaluation CLI**

Add `--output` to `scripts/evaluate.py`. After loading the config, resolve the path with:

```python
default_output = Path(cfg["run"]["output_dir"]) / "evaluation" / f"{Path(args.checkpoint).stem}.json"
output_path = Path(args.output) if args.output else default_output
```

Build and persist one result dictionary:

```python
result = {
    "checkpoint": str(Path(args.checkpoint)),
    "val_loss": val_loss,
    "perplexity": perplexity(val_loss),
    "samples": samples,
}
write_evaluation_result(output_path, result)
print(json.dumps(result, indent=2, sort_keys=True))
```

- [ ] **Step 5: Add summary CLI**

Create `scripts/summarize_run.py`:

```python
#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.training.run_summary import write_run_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize a MatGPT training run.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--known-limitation", action="append", default=[])
    args = parser.parse_args()
    limitations = args.known_limitation or [
        "Single T4 run; exact CUDA determinism is not claimed."
    ]
    output = write_run_summary(args.run_dir, limitations)
    print(output)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run summary tests**

```bash
uv run pytest tests/test_run_summary.py -v
```

Expected: PASS with deterministic Markdown and evaluation JSON.

- [ ] **Step 7: Commit evaluation evidence support**

```bash
git add matgpt/training/run_summary.py scripts/summarize_run.py scripts/evaluate.py tests/test_run_summary.py
git diff --cached --check
git commit -m "feat: persist evaluation and run summaries"
```

---

### Task 7: Turn The Colab Notebook Into A Stage-Gated T4 Runbook

**Files:**
- Create: `docs/runbooks/colab-t4-first-run.md`
- Create: `tests/test_benchmark.py`
- Modify: `notebooks/train_matgpt_t4_base_colab.ipynb`
- Modify: `scripts/benchmark_t4.py:26-68`
- Modify: `tests/test_notebook_colab.py:1-42`
- Modify: `README.md:39-105,163-183`

**Interfaces:**
- Consumes: `scripts/preflight_t4.py`, `scripts/pretrain.py`, `scripts/evaluate.py`, and `scripts/summarize_run.py`
- Produces: notebook stages `prepare`, `smoke`, `pilot`, `full`, and `evaluate`
- Produces: persistent Drive artifacts and a fixed local working copy

- [ ] **Step 1: Write failing benchmark and notebook contract tests**

Create `tests/test_benchmark.py`:

```python
import math

from matgpt.config import clone_config, load_config
from scripts.benchmark_t4 import benchmark_batch_size


def test_benchmark_reports_finite_loss_gradient_and_memory():
    cfg = clone_config(load_config("configs/matgpt_mini_8m.yaml"))
    cfg["model"].update({
        "vocab_size": 64,
        "context_length": 8,
        "n_layers": 1,
        "n_heads": 4,
        "d_model": 32,
        "d_ff": 96,
    })
    cfg["training"].update({"precision": "fp32", "grad_clip": 1.0})

    result = benchmark_batch_size(cfg, batch_size=2, steps=1)

    assert result["status"] == "ok"
    assert math.isfinite(result["loss"])
    assert math.isfinite(result["grad_norm"])
    assert result["tokens_per_second"] > 0
    assert result["memory_fraction"] == 0.0
```

Add a shared helper to `tests/test_notebook_colab.py` that returns joined code-cell source. Add:

```python
def notebook_code_source() -> str:
    notebook = json.loads(Path("notebooks/train_matgpt_t4_base_colab.ipynb").read_text(encoding="utf-8"))
    return "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )


def test_colab_uses_full_schedule_for_smoke_and_stage_gates():
    source = notebook_code_source()
    assert 'RUN_STAGE = "prepare"' in source
    assert '"smoke", "pilot", "full", "evaluate"' in source
    assert "SMOKE_MAX_STEPS = 20" in source
    assert "PILOT_STOP_STEP = 306" in source
    assert 'cfg["training"]["max_tokens"] = 200_000' not in source
    assert "scripts/preflight_t4.py" in source
    assert "--require-t4" in source


def test_colab_separates_fast_local_data_from_persistent_drive_artifacts():
    source = notebook_code_source()
    assert 'LOCAL_ROOT = Path("/content/matgpt_work")' in source
    assert 'DRIVE_ROOT = Path("/content/drive/MyDrive/matgpt_artifacts")' in source
    assert "restore_artifacts_from_drive" in source
    assert "sync_artifacts_to_drive" in source
```

- [ ] **Step 2: Run benchmark and notebook tests and verify failure**

```bash
uv run pytest tests/test_benchmark.py tests/test_notebook_colab.py -v
```

Expected: FAIL because benchmark results lack loss/gradient fields and the notebook still uses `RUN_MODE` and rewrites `max_tokens` for smoke.

- [ ] **Step 3: Make the benchmark prove finite math**

In `benchmark_batch_size`, retain the final detached loss and pre-clip gradient norm. Reject non-finite values and return:

```python
loss_value = float(loss.detach().cpu())
grad_norm_value = float(grad_norm.detach().cpu())
if not math.isfinite(loss_value) or not math.isfinite(grad_norm_value):
    raise FloatingPointError(
        f"Non-finite benchmark result: loss={loss_value} grad_norm={grad_norm_value}"
    )
peak_memory_mb = (
    torch.cuda.max_memory_allocated(device) / (1024 * 1024)
    if device.type == "cuda"
    else 0.0
)
total_memory_mb = (
    torch.cuda.get_device_properties(device).total_memory / (1024 * 1024)
    if device.type == "cuda"
    else 0.0
)
return {
    "batch_size": batch_size,
    "status": "ok",
    "loss": loss_value,
    "grad_norm": grad_norm_value,
    "tokens_per_second": tokens_per_step * steps / elapsed,
    "peak_memory_mb": peak_memory_mb,
    "total_memory_mb": total_memory_mb,
    "memory_fraction": peak_memory_mb / total_memory_mb if total_memory_mb else 0.0,
}
```

Import `math`, assign `grad_norm = torch.nn.utils.clip_grad_norm_(...)`, and catch both `RuntimeError` and `FloatingPointError` in the existing failed-result branch.

- [ ] **Step 4: Replace run settings with explicit stages**

Use these exact settings in the first code cell:

```python
MODEL = "mini_8m"  # @param ["mini_8m", "tiny_59m"]
RUN_STAGE = "prepare"  # @param ["prepare", "smoke", "pilot", "full", "evaluate"]
SMOKE_MAX_STEPS = 20
RESUME_CHECK_STEPS = 5
PILOT_STOP_STEP = 306
```

Do not modify `training.max_tokens`, dataset document caps, evaluation intervals, sample intervals, or checkpoint intervals for smoke. A smoke run is a stop cap on the real configuration and real artifacts.

- [ ] **Step 5: Separate local performance paths from Drive persistence**

Use:

```python
LOCAL_ROOT = Path("/content/matgpt_work") / cfg["run"]["name"]
DRIVE_ROOT = Path("/content/drive/MyDrive/matgpt_artifacts") / cfg["run"]["name"]
cfg["run"]["output_dir"] = str(DRIVE_ROOT / "run")
cfg["dataset"]["normalized_dir"] = str(LOCAL_ROOT / "normalized")
cfg["tokenizer"]["output_dir"] = str(LOCAL_ROOT / "tokenizer")
cfg["sharding"]["output_dir"] = str(LOCAL_ROOT / "shards")
```

Implement exact restore and synchronization helpers:

```python
PERSISTED_ARTIFACT_DIRS = ("normalized", "tokenizer", "shards")


def restore_artifacts_from_drive():
    restored = []
    for name in PERSISTED_ARTIFACT_DIRS:
        local_path = LOCAL_ROOT / name
        drive_path = DRIVE_ROOT / name
        if not local_path.exists() and drive_path.exists():
            local_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(drive_path, local_path)
            restored.append(name)
    print("Restored from Drive:", restored or "nothing")


def sync_artifacts_to_drive():
    synchronized = []
    for name in PERSISTED_ARTIFACT_DIRS:
        local_path = LOCAL_ROOT / name
        drive_path = DRIVE_ROOT / name
        if local_path.exists():
            drive_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(local_path, drive_path, dirs_exist_ok=True)
            synchronized.append(name)
    print("Synchronized to Drive:", synchronized or "nothing")
```

Synchronize `normalized`, `tokenizer`, and `shards` after successful preparation. Restore them at session start when the local directories are missing.

Print local and persistent paths before any expensive command.

- [ ] **Step 6: Add early storage and GPU checks**

Before data preparation, print `shutil.disk_usage` for `/content` and Drive and require at least 20 GiB free locally. Keep `nvidia-smi`, then require CUDA and a GPU name containing `T4` for smoke, pilot, and full stages.

- [ ] **Step 7: Add preparation, preflight, and benchmark stages**

For `prepare`, run dataset preparation, tokenizer training, and sharding only when their expected outputs are absent; then sync to Drive. For all training stages, run:

```python
run_command([
    "python", "scripts/preflight_t4.py",
    "--config", str(colab_config_path),
    "--require-t4",
    "--min-free-disk-gb", "20",
])
```

Make `run_command` return its completed subprocess result after successful execution. Run the batch benchmark after preflight and persist its JSON:

```python
benchmark = run_command([
    "python", "scripts/benchmark_t4.py",
    "--config", str(colab_config_path),
    "--batch-sizes", batch_sizes,
    "--steps", "5",
])
benchmark_path = Path(cfg["run"]["output_dir"]) / "benchmark.json"
benchmark_path.parent.mkdir(parents=True, exist_ok=True)
benchmark_path.write_text(benchmark.stdout, encoding="utf-8")
```

Display the selected batch's loss, gradient norm, memory fraction, and tokens/second. The gate fails when status is not `ok`, loss/norm is non-finite, or memory fraction is 0.90 or greater.

- [ ] **Step 8: Encode smoke, resume-check, pilot, and full semantics**

Use the persistent `latest.pt` and read its state with `torch.load(latest, map_location="cpu", weights_only=False)`.

```python
if RUN_STAGE == "smoke":
    assert not latest.exists(), "Smoke must begin from a new run directory."
    run_command(base_train_cmd + ["--max-steps", str(SMOKE_MAX_STEPS)])
    run_command(base_train_cmd + ["--resume-from", str(latest), "--max-steps", str(RESUME_CHECK_STEPS)])
elif RUN_STAGE == "pilot":
    assert latest.exists(), "Run the smoke and resume check first."
    current_step = int(torch.load(latest, map_location="cpu", weights_only=False)["state"]["global_step"])
    remaining = PILOT_STOP_STEP - current_step
    assert remaining > 0, f"Pilot already reached: global_step={current_step}"
    run_command(base_train_cmd + ["--resume-from", str(latest), "--max-steps", str(remaining)])
elif RUN_STAGE == "full":
    assert latest.exists(), "Run and approve the pilot first."
    current_step = int(torch.load(latest, map_location="cpu", weights_only=False)["state"]["global_step"])
    assert current_step >= PILOT_STOP_STEP, "Pilot gate has not been reached."
    run_command(base_train_cmd + ["--resume-from", str(latest)])
```

The notebook text must say that reaching step 306 is not approval; the user and Codex review evidence before selecting `full`.

- [ ] **Step 9: Persist evaluation and summary outputs**

The evaluate stage runs `scripts/evaluate.py` for `latest.pt` and `best.pt` when present, followed by `scripts/summarize_run.py`. Display `run_summary.md`, the last 30 metric rows, loss curves, skipped-update counters, and the latest sample file.

For pilot review, compute the approved quantitative gates from finite training rows:

```python
import math

train_rows = metrics.dropna(subset=["train_loss"]).copy()
window = max(5, math.ceil(len(train_rows) * 0.20))
assert len(train_rows) >= window * 2, "Not enough logged pilot rows for early/late comparison."
early = train_rows.head(window)
late = train_rows.tail(window)
pilot_gate = {
    "early_loss_median": float(early["train_loss"].median()),
    "late_loss_median": float(late["train_loss"].median()),
    "throughput_ratio": float(late["tokens_per_second"].median() / early["tokens_per_second"].median()),
    "maximum_peak_memory_mb": float(train_rows["peak_memory_mb"].max()),
    "skipped_updates_total": int(train_rows["optimizer_steps_skipped_total"].max()),
}
pilot_gate["loss_improved"] = pilot_gate["late_loss_median"] < pilot_gate["early_loss_median"]
pilot_gate["throughput_stable"] = pilot_gate["throughput_ratio"] >= 0.80
print(json.dumps(pilot_gate, indent=2, sort_keys=True))
```

Also compare the first and last finite `val_loss` rows and calculate peak-memory fraction from `benchmark.json`. Display a warning when every logged peak-memory value is strictly greater than the preceding value. These calculations inform the review; they do not automatically select the `full` stage.

- [ ] **Step 10: Write the beginner-facing runbook**

Create `docs/runbooks/colab-t4-first-run.md` with:

1. prerequisites and expected cost/time uncertainty
2. Drive and local path explanation
3. exact stage order
4. commands the notebook runs
5. pass criteria for Gates 0-9
6. stop conditions
7. how to resume after disconnect
8. how to share `preflight.json`, `benchmark.json`, `metrics.csv`, `run_summary.md`, and sample/evaluation files for review

Clearly label all T4 values as expected until observed.

- [ ] **Step 11: Update README and validate notebook JSON**

Link the runbook, preflight command, five stages, and artifact layout. Then run:

```bash
jq empty notebooks/train_matgpt_t4_base_colab.ipynb
uv run pytest tests/test_benchmark.py tests/test_notebook_colab.py -v
```

Expected: valid JSON and all notebook contract tests PASS.

- [ ] **Step 12: Commit notebook and runbook changes**

```bash
git add docs/runbooks/colab-t4-first-run.md notebooks/train_matgpt_t4_base_colab.ipynb scripts/benchmark_t4.py tests/test_benchmark.py tests/test_notebook_colab.py README.md
git diff --cached --check
git commit -m "docs: add stage-gated Colab T4 workflow"
```

---

### Task 8: Create The Course Foundation And Video 1

**Files:**
- Create: `course/outline.md`
- Create: `course/glossary.md`
- Create: `course/templates/video/script.md`
- Create: `course/templates/video/lesson.md`
- Create: `course/templates/video/lab.md`
- Create: `course/templates/video/quiz.md`
- Create: `course/templates/video/answer-key.md`
- Create: `course/templates/video/evidence.md`
- Create: `course/videos/001-computer-learning-from-text/script.md`
- Create: `course/videos/001-computer-learning-from-text/lesson.md`
- Create: `course/videos/001-computer-learning-from-text/lab.md`
- Create: `course/videos/001-computer-learning-from-text/lab.py`
- Create: `course/videos/001-computer-learning-from-text/quiz.md`
- Create: `course/videos/001-computer-learning-from-text/answer-key.md`
- Create: `course/videos/001-computer-learning-from-text/evidence.md`
- Create: `tests/test_course_structure.py`

**Interfaces:**
- Produces: the exact approved 64-video sequence from specification Section 10
- Produces: a repeatable six-file video artifact contract
- Produces: `lab.py` with deterministic standard-library output
- Consumes: verified text normalization and repository pipeline references

- [ ] **Step 1: Write failing course structure and lab tests**

Create `tests/test_course_structure.py`:

```python
import subprocess
import sys
from pathlib import Path


def test_course_outline_contains_all_64_numbered_videos():
    outline = Path("course/outline.md").read_text(encoding="utf-8")
    numbered = [line for line in outline.splitlines() if line.startswith(tuple(f"{n}. " for n in range(1, 65)))]
    assert len(numbered) == 64
    assert numbered[0].startswith("1. What Does It Mean")
    assert numbered[-1].startswith("64. Building and Teaching")


def test_video_one_has_required_artifacts_and_runnable_lab():
    video_dir = Path("course/videos/001-computer-learning-from-text")
    for name in ["script.md", "lesson.md", "lab.md", "quiz.md", "answer-key.md", "evidence.md", "lab.py"]:
        assert (video_dir / name).is_file(), name
    result = subprocess.run([sys.executable, str(video_dir / "lab.py")], text=True, capture_output=True, check=True)
    assert "Character numbers: [67, 97, 116]" in result.stdout
    assert "UTF-8 bytes: [67, 97, 116]" in result.stdout
```

- [ ] **Step 2: Run the tests and verify missing-file failures**

```bash
uv run pytest tests/test_course_structure.py -v
```

Expected: FAIL because `course/` does not exist.

- [ ] **Step 3: Create the complete outline and glossary**

Copy all 64 approved titles, in order and grouped under the 19 modules, from specification Section 10 into `course/outline.md`. Add audience, prerequisites, course promise, module outcomes, and the rule that videos are completed and reviewed one at a time.

Start `course/glossary.md` with plain-language definitions for:

- computer
- text
- character
- number representation
- Unicode
- UTF-8
- data
- example
- pattern
- model
- learning

Each entry must have `Simple meaning`, `Technical meaning`, and `First video` fields. State that future videos extend the glossary before using a new term.

- [ ] **Step 4: Create reusable templates**

Each file under `course/templates/video/` must include exact required headings.

`script.md`:

```markdown
# Video N: Title
## 00:00 Hook
## 00:45 Analogy
## 02:00 Technical Meaning
## 04:00 Tiny Example
## 06:00 Repository Walkthrough
## 09:00 Live Mini-Lab
## 12:00 Common Mistake
## 13:00 Recap And Exercise
```

`lesson.md` requires prerequisites, one objective, simple explanation, analogy and limitation, technical meaning, math/example, commented code, misconception, and recap. `lab.md` requires setup, command, prediction, steps, expected output, explanation, and extension. `quiz.md` contains questions only. `answer-key.md` contains answers and gap explanations. `evidence.md` contains repository anchors, commands run, observed output, and unverified claims.

- [ ] **Step 5: Write the deterministic Video 1 lab**

Create `lab.py`:

```python
text = "Cat"

print("Human text:", text)
print("Character numbers:", [ord(character) for character in text])
print("UTF-8 bytes:", list(text.encode("utf-8")))
print("Can arithmetic use the raw string directly? No")
print("Learning begins after text is represented as numbers.")
```

`lab.md` asks the learner to predict the numbers, run the script, replace `Cat` with `A`, and explain why agreed numbers are representation rather than human meaning.

- [ ] **Step 6: Write the complete Video 1 teaching package**

Title: **What Does It Mean for a Computer to Learn From Text?**

The single learning objective is: “Explain why text must be represented as numbers before a mathematical model can learn patterns from it.”

Required teaching path:

1. A computer does not naturally experience the meaning of `cat`.
2. A library-card analogy distinguishes an agreed identifier from meaning.
3. Characters are stored using agreed numeric representations.
4. Those numbers are not yet token embeddings or learned meaning; those arrive later.
5. “Learning” means adjusting internal numbers so predictions become less wrong across many examples.
6. Show `ord`, UTF-8 bytes, and the repository's `normalize_text` only as a preview of the first pipeline step.
7. Explicitly avoid unexplained use of token, tensor, logit, gradient, or attention.

Quiz questions:

1. Does a computer naturally understand `cat` like a human?
2. What does `ord("A")` return, and what does that number represent?
3. Is character number 65 the human meaning of `A`?
4. Why must text become numbers before a mathematical model can use it?
5. In one sentence, what does learning mean at this stage?

The answer key corrects the misconception that character numbers contain semantic meaning.

`evidence.md` links `matgpt/data/normalize.py`, `matgpt/data/prepare.py`, the lab command, and the passing course-structure test. Mark future tokenization/model details as intentionally deferred.

- [ ] **Step 7: Run the course tests and beginner-language scan**

```bash
uv run pytest tests/test_course_structure.py -v
rg -n '\b(token|tensor|logit|gradient|attention)\b' course/videos/001-computer-learning-from-text
```

Expected: tests PASS. Any advanced term found outside the explicit “not taught yet” boundary is removed or defined before use.

- [ ] **Step 8: Commit the course foundation**

```bash
git add course tests/test_course_structure.py
git diff --cached --check
git commit -m "docs: create LLM course foundation and video one"
```

---

### Task 9: Align Progress And Operator Documentation

**Files:**
- Modify: `docs/llm_training_progress.md:1-240`
- Modify: `README.md`

**Interfaces:**
- Consumes: implemented tasks and their verified test output
- Produces: one accurate current-status record and one repository entry point

- [ ] **Step 1: Update progress only with observed results**

Change the progress document to record:

- theory completed through Lesson 100 and the positional/RoPE rotation lessons before the build-first transition
- numerical-stability lessons completed: clipping, overflow, Inf/NaN, BF16, and stability metrics
- current phase: repository hardening and first real 8M T4 run
- completed implementation tasks and exact passing test count observed at this point
- real Colab data preparation/training status remains “not started” until actual artifacts are inspected
- links to the approved design, implementation plan, runbook, course outline, and Video 1
- remaining theory will be learned just in time during implementation and training

Do not invent a percentage or mark a T4 gate complete from local tests.

- [ ] **Step 2: Reconcile README commands and semantics**

Ensure README states:

- TinyStories is pinned to the exact commit
- tokenizer has complete byte coverage
- preflight runs after artifacts are prepared
- `--max-steps` preserves the full schedule
- smoke is 20 updates followed by a five-update resume check
- pilot stops at global step 306
- full training requires explicit pilot approval
- evaluation writes JSON and summary writes Markdown
- local tests cannot prove T4 readiness by themselves

- [ ] **Step 3: Check documentation paths and stale claims**

```bash
rg -n 'Lesson 92|RUN_MODE|200_000|100M|128' README.md docs/llm_training_progress.md docs/runbooks course
```

Expected: no stale progress, old notebook mode, shortened smoke token budget, or obsolete tokenizer-test vocabulary claims remain. Legitimate historical/math uses must be reviewed rather than mechanically deleted.

- [ ] **Step 4: Commit documentation alignment**

```bash
git add README.md docs/llm_training_progress.md
git diff --cached --check
git commit -m "docs: align training and course progress"
```

---

### Task 10: Run Gate 0 Verification And Prepare The Colab Handoff

**Files:**
- Verify: all files changed by Tasks 1-9
- Update only if evidence requires it: `docs/llm_training_progress.md`

**Interfaces:**
- Consumes: complete local readiness implementation
- Produces: Gate 0 evidence and exact first Colab action

- [ ] **Step 1: Run the narrowest complete local suite**

```bash
uv run pytest tests/test_tokenizer.py tests/test_schedule.py tests/test_tracking.py tests/test_training_core.py tests/test_pretrain_smoke.py tests/test_preflight.py tests/test_run_summary.py tests/test_benchmark.py tests/test_notebook_colab.py tests/test_course_structure.py -v
```

Expected: all targeted readiness tests PASS with no retries.

- [ ] **Step 2: Run the full repository suite**

```bash
uv run pytest
```

Expected: all tests PASS. Record the exact count and duration from this run.

- [ ] **Step 3: Verify model and schedule math**

```bash
uv run python scripts/model_report.py --config configs/matgpt_mini_8m.yaml
uv run python -c 'from matgpt.config import load_config; from matgpt.training.schedule import build_training_schedule; print(build_training_schedule(load_config("configs/matgpt_mini_8m.yaml"), max_steps_override=20))'
```

Expected model report: `8,391,936` trainable parameters.

Expected schedule fields:

```text
tokens_per_step=32768
total_steps=6104
warmup_steps=122
stop_step=20
```

- [ ] **Step 4: Verify repository hygiene**

```bash
jq empty notebooks/train_matgpt_t4_base_colab.ipynb
git diff --check
git status --short
```

Expected: notebook JSON is valid and no whitespace errors. Existing unrelated dirty files may remain; enumerate them without changing them.

- [ ] **Step 5: Review implementation against the specification**

Check each specification acceptance criterion and mark it:

- locally verified
- requires Colab T4 evidence
- requires prepared TinyStories artifacts
- requires pilot/full-run evidence

Do not collapse these categories into a single “ready” claim.

- [ ] **Step 6: Commit any evidence-only progress correction**

If the exact test count changed the progress file and that hunk is isolated:

```bash
git add docs/llm_training_progress.md
git diff --cached --check
git commit -m "docs: record Gate 0 verification"
```

- [ ] **Step 7: Hand off the first real Colab action**

Tell the user to open `notebooks/train_matgpt_t4_base_colab.ipynb`, select a T4 runtime, set `RUN_STAGE = "prepare"`, and run cells only through preparation and preflight. Ask them to return the generated `preflight.json` and `benchmark.json` evidence before starting smoke training.

Expected stopping point: prepared and audited data/tokenizer/shards plus T4 benchmark evidence. No full training command has run.

---

## Specification Coverage

| Approved requirement | Implemented by |
|---|---|
| Complete byte alphabet and Unicode round trips | Task 1 |
| Full schedule preserved under smoke and resume | Task 2 |
| Stable metrics, baseline, cumulative time, and immutable artifacts | Task 3 |
| Compatibility checked before checkpoint state application | Tasks 3 and 5 |
| Gradient scale, skipped updates, finite-loss stops, and five-skip abort | Task 4 |
| Dataset, tokenizer, shard, storage, device, and checkpoint preflight | Task 5 |
| Evaluation JSON and `run_summary.md` | Task 6 |
| Local/Drive Colab workflow and human-controlled gates | Task 7 |
| Finite T4 benchmark loss, gradient norm, memory, and throughput | Task 7 |
| Complete 64-video outline, templates, glossary, and Video 1 | Task 8 |
| Accurate progress and operator documentation | Task 9 |
| Gate 0 verification and honest Colab handoff | Task 10 |

No approved requirement is intentionally omitted. CUDA execution, TinyStories artifact inspection, pilot quality, and full-run quality remain runtime gates because they cannot be established by local implementation alone.

---

## Execution Completion Boundary

Completing this plan proves local repository readiness and creates the teaching foundation. It does not prove the T4 runtime, prepared TinyStories artifacts, pilot quality, or final model quality.

After Gate 0, continue interactively:

1. Colab `prepare` and preflight review
2. T4 benchmark review
3. 20-update smoke plus five-update resume review
4. pilot continuation to step 306
5. explicit go/no-go decision
6. full continuation to step 6,104 when approved
7. final evaluation and run summary review
