from pathlib import Path

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
