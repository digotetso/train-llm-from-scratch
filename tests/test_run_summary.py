import json
from pathlib import Path

import pytest

from matgpt.training.run_summary import build_run_summary, write_evaluation_result


def _write_complete_run(run_dir: Path) -> None:
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


def test_evaluation_and_summary_are_persisted(tmp_path: Path):
    run_dir = tmp_path / "run"
    _write_complete_run(run_dir)

    output = write_evaluation_result(run_dir / "evaluation" / "best.json", {"val_loss": 4.7})
    summary = build_run_summary(run_dir, ["Single T4 run; exact CUDA determinism is not claimed."])

    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8")) == {"val_loss": 4.7}
    assert "Initial validation loss: 5.0" in summary
    assert "Best validation loss: 4.7" in summary
    assert "best.json" in summary
    assert "Single T4 run" in summary


def test_summary_fails_closed_when_metrics_are_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Run metrics are missing"):
        build_run_summary(tmp_path / "run", [])


def test_summary_marks_absent_optional_evidence_unavailable(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "metrics.csv").write_text(
        "event,val_loss,optimizer_steps_skipped_total\nvalidation,4.7,\n",
        encoding="utf-8",
    )

    summary = build_run_summary(run_dir, [])

    assert "Device: unavailable" in summary
    assert "Config SHA-256: unavailable" in summary
    assert "Skipped optimizer updates: unavailable" in summary
    assert "- none" in summary


def test_summary_fails_closed_for_malformed_optional_json(tmp_path: Path):
    run_dir = tmp_path / "run"
    _write_complete_run(run_dir)
    (run_dir / "environment.json").write_text("{not json}\n", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        build_run_summary(run_dir, [])
