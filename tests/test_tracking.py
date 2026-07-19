import csv
from pathlib import Path

import pytest
import torch

from matgpt.training.artifacts import validate_run_artifacts, write_run_artifacts
from matgpt.training.metrics import METRIC_FIELDS, append_metric, calculate_tokens_per_second
from matgpt.training.tracking import NullTracker, create_tracker


def test_null_tracker_accepts_logs_and_finish():
    tracker = NullTracker()

    tracker.log({"loss": 1.0}, step=1)
    tracker.finish()


def test_create_tracker_returns_null_when_disabled(tmp_path: Path):
    cfg = {
        "run": {"name": "unit", "output_dir": str(tmp_path)},
        "tracking": {"wandb": {"enabled": False}},
    }

    tracker = create_tracker(cfg, config_snapshot={"a": 1})

    assert isinstance(tracker, NullTracker)


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


def test_metric_append_rejects_an_incompatible_existing_header(tmp_path: Path):
    path = tmp_path / "metrics.csv"
    path.write_text("event,global_step\n", encoding="utf-8")

    with pytest.raises(ValueError, match="header"):
        append_metric(path, {"event": "train", "global_step": 1})

    assert path.read_text(encoding="utf-8") == "event,global_step\n"
    assert METRIC_FIELDS != ("event", "global_step")


def test_run_artifact_preflight_is_read_only_on_conflict(tmp_path: Path):
    cfg = {"run": {"name": "unit"}}
    extra = {
        "config_sha256": "config",
        "tokenizer_sha256": "tokenizer",
        "dataset_manifest_hash": "dataset",
        "git_commit": "commit",
        "parameter_count": 10,
    }
    paths = write_run_artifacts(tmp_path, cfg, extra, torch.device("cpu"))
    before = {name: Path(path).read_text(encoding="utf-8") for name, path in paths.items()}

    with pytest.raises(ValueError, match="configuration snapshot"):
        validate_run_artifacts(tmp_path, {"run": {"name": "other"}}, extra)

    after = {name: Path(path).read_text(encoding="utf-8") for name, path in paths.items()}
    assert after == before
