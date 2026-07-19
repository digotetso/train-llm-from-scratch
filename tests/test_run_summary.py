import json
import sys
from pathlib import Path

import pytest

import matgpt.training.run_summary as run_summary_module
from matgpt.config import config_to_yaml
from matgpt.training.run_summary import build_run_summary, write_evaluation_result
from matgpt.training.run_summary import write_run_summary
from matgpt.utils.hashing import sha256_file, sha256_text
from scripts import evaluate as evaluate_script


METRIC_FIELDS = [
    "event",
    "global_step",
    "tokens_processed",
    "train_loss",
    "val_loss",
    "val_perplexity",
    "tokens_per_second",
    "peak_memory_mb",
    "elapsed_seconds",
    "optimizer_steps_skipped_total",
]


def _write_metrics(run_dir: Path, rows: list[dict[str, object]]) -> None:
    lines = [",".join(METRIC_FIELDS)]
    for row in rows:
        lines.append(",".join(str(row.get(field, "")) for field in METRIC_FIELDS))
    (run_dir / "metrics.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


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

    with pytest.raises(ValueError, match="Invalid JSON evidence"):
        build_run_summary(run_dir, [])


@pytest.mark.parametrize("invalid", ["not-a-number", "NaN", "Infinity"])
@pytest.mark.parametrize(
    "field",
    [
        "val_loss",
        "train_loss",
        "tokens_per_second",
        "peak_memory_mb",
        "elapsed_seconds",
        "optimizer_steps_skipped_total",
    ],
)
def test_summary_rejects_malformed_or_non_finite_metric_evidence(
    tmp_path: Path,
    field: str,
    invalid: str,
):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    rows = [
        {"event": "baseline", "global_step": 0, "val_loss": 5.0, "peak_memory_mb": 100},
        {
            "event": "train",
            "global_step": 1,
            "train_loss": 4.8,
            "tokens_per_second": 1000,
            "peak_memory_mb": 2000,
            "elapsed_seconds": 10,
            "optimizer_steps_skipped_total": 0,
        },
        {
            "event": "validation",
            "global_step": 1,
            "val_loss": 4.7,
            "peak_memory_mb": 2000,
            "elapsed_seconds": 12,
            "optimizer_steps_skipped_total": 0,
        },
    ]
    rows[1][field] = invalid
    _write_metrics(run_dir, rows)

    with pytest.raises(ValueError, match=f"Invalid {field} value"):
        build_run_summary(run_dir, [])


def test_summary_uses_first_and_final_validation_and_training_evidence(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_metrics(
        run_dir,
        [
            {"event": "baseline", "global_step": 0, "val_loss": 5.0},
            {"event": "train", "global_step": 1, "train_loss": 4.8},
            {"event": "validation", "global_step": 1, "val_loss": 4.7},
            {"event": "train", "global_step": 2, "train_loss": 4.2},
            {"event": "validation", "global_step": 2, "val_loss": 4.9},
        ],
    )

    summary = build_run_summary(run_dir, [])

    assert "Initial validation loss: 5.0" in summary
    assert "Final validation loss: 4.9" in summary
    assert "Initial training loss: 4.8" in summary
    assert "Final training loss: 4.2" in summary


def test_summary_reports_performance_and_skipped_update_evidence(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_metrics(
        run_dir,
        [
            {
                "event": "baseline",
                "global_step": 0,
                "val_loss": 5.0,
                "peak_memory_mb": 100,
                "elapsed_seconds": 0,
                "optimizer_steps_skipped_total": 0,
            },
            {
                "event": "train",
                "global_step": 1,
                "train_loss": 4.8,
                "tokens_per_second": 1000,
                "peak_memory_mb": 2000,
                "elapsed_seconds": 10,
                "optimizer_steps_skipped_total": 2,
            },
            {
                "event": "validation",
                "global_step": 2,
                "val_loss": 4.7,
                "tokens_per_second": 1200,
                "peak_memory_mb": 3000,
                "elapsed_seconds": 22,
                "optimizer_steps_skipped_total": 3,
            },
        ],
    )

    summary = build_run_summary(run_dir, [])

    assert "Maximum tokens/second: 1200.0" in summary
    assert "Peak memory MB: 3000.0" in summary
    assert "Elapsed seconds: 22.0" in summary
    assert "Skipped optimizer updates: 3" in summary


@pytest.mark.parametrize(
    ("relative_path", "content"),
    [
        ("environment.json", '{"device_name": NaN}\n'),
        ("fingerprints.json", '{"metadata": {"value": 1e999}}\n'),
        ("evaluation/best.json", '{"samples": [Infinity]}\n'),
    ],
)
def test_summary_rejects_malformed_or_non_finite_json_evidence(
    tmp_path: Path,
    relative_path: str,
    content: str,
):
    run_dir = tmp_path / "run"
    _write_complete_run(run_dir)
    path = run_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON evidence"):
        build_run_summary(run_dir, [])


def test_evaluation_result_has_deterministic_bytes_and_rejects_non_finite_values(tmp_path: Path):
    first = write_evaluation_result(tmp_path / "first.json", {"z": 2, "a": 1})
    second = write_evaluation_result(tmp_path / "second.json", {"a": 1, "z": 2})

    assert first.read_bytes() == second.read_bytes() == b'{\n  "a": 1,\n  "z": 2\n}\n'
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            write_evaluation_result(tmp_path / "invalid.json", {"value": value})


def test_write_run_summary_replaces_output_with_a_unique_atomic_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    run_dir = tmp_path / "run"
    _write_complete_run(run_dir)
    output = run_dir / "run_summary.md"
    output.write_text("stale summary\n", encoding="utf-8")
    observed_sources: list[Path] = []
    original_replace = run_summary_module.os.replace

    def replace(source: str | Path, destination: str | Path) -> None:
        observed_sources.append(Path(source))
        original_replace(source, destination)

    monkeypatch.setattr(run_summary_module.os, "replace", replace)

    result = write_run_summary(run_dir, ["Synthetic run"])

    assert result == output
    assert output.read_text(encoding="utf-8") == build_run_summary(run_dir, ["Synthetic run"])
    assert observed_sources[0].parent == output.parent
    assert observed_sources[0] != output.with_suffix(output.suffix + ".tmp")
    assert not observed_sources[0].exists()


def test_atomic_write_cleans_up_when_replace_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    output = tmp_path / "evaluation.json"

    def fail_replace(source: str | Path, destination: str | Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(run_summary_module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        write_evaluation_result(output, {"val_loss": 4.7})

    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("explicit_output", [False, True])
def test_evaluate_cli_persists_default_and_explicit_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    explicit_output: bool,
):
    run_dir = tmp_path / "run"
    checkpoint = tmp_path / "checkpoints" / "best.pt"
    configured_output = run_dir / "evaluation" / "best.json"
    requested_output = tmp_path / "requested.json"
    normalized_dir = tmp_path / "normalized"
    normalized_dir.mkdir()
    manifest_path = normalized_dir / "manifest.json"
    manifest_path.write_text('{"dataset":"unit"}\n', encoding="utf-8")
    cfg = {
        "run": {"output_dir": str(run_dir), "seed": 17},
        "model": {"context_length": 8},
        "tokenizer": {"output_dir": str(tmp_path / "tokenizer")},
        "sharding": {"output_dir": str(tmp_path / "shards")},
        "dataset": {"normalized_dir": str(normalized_dir)},
        "training": {"micro_batch_size": 1, "eval_batches": 1, "precision": "fp32"},
        "evaluation": {
            "prompts": ["Hello"],
            "max_new_tokens": 1,
            "temperature": 1.0,
            "top_k": None,
            "top_p": None,
        },
    }

    class FakeConfig:
        @staticmethod
        def from_dict(value: dict) -> object:
            return value

    class FakeModel:
        def __init__(self, config: object):
            self.config = config

        def to(self, device: object) -> "FakeModel":
            return self

    class FakeDataset:
        @classmethod
        def from_metadata(cls, *args, **kwargs) -> object:
            return object()

    class FakeTokenizer:
        def token_to_id(self, token: str) -> int:
            assert token == "<|eos|>"
            return 2

    payload = {
        "model": {},
        "extra": {
            "config_sha256": sha256_text(config_to_yaml(cfg)),
            "tokenizer_sha256": "current-tokenizer",
            "dataset_manifest_hash": sha256_file(manifest_path),
        },
    }

    monkeypatch.setattr(evaluate_script, "load_config", lambda path: cfg)
    monkeypatch.setattr(evaluate_script, "get_device", lambda: "cpu")
    monkeypatch.setattr(evaluate_script, "GPTConfig", FakeConfig)
    monkeypatch.setattr(evaluate_script, "GPT", FakeModel)
    monkeypatch.setattr(evaluate_script, "load_checkpoint", lambda *args, **kwargs: payload)
    monkeypatch.setattr(evaluate_script, "apply_checkpoint_payload", lambda *args, **kwargs: None)
    monkeypatch.setattr(evaluate_script, "load_tokenizer", lambda path: FakeTokenizer())
    monkeypatch.setattr(
        evaluate_script,
        "load_tokenizer_metadata",
        lambda path: {"tokenizer_sha256": "current-tokenizer"},
    )
    monkeypatch.setattr(evaluate_script, "PackedTokenDataset", FakeDataset)
    monkeypatch.setattr(evaluate_script, "metadata_path_for_split", lambda *args: tmp_path / "metadata.json")
    monkeypatch.setattr(evaluate_script, "effective_validation_split", lambda dataset: "validation")
    monkeypatch.setattr(evaluate_script, "evaluate_loss", lambda *args, **kwargs: 4.7)
    monkeypatch.setattr(
        evaluate_script,
        "generate_samples",
        lambda **kwargs: [{"prompt": "Hello", "text": "Hello world"}],
    )
    monkeypatch.setattr(evaluate_script, "perplexity", lambda loss: 109.9)
    argv = ["evaluate.py", "--config", "config.yaml", "--checkpoint", str(checkpoint)]
    if explicit_output:
        argv.extend(["--output", str(requested_output)])
    monkeypatch.setattr(sys, "argv", argv)

    evaluate_script.main()

    output = requested_output if explicit_output else configured_output
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "checkpoint": str(checkpoint),
        "perplexity": 109.9,
        "samples": [{"prompt": "Hello", "text": "Hello world"}],
        "val_loss": 4.7,
    }
    assert json.loads(capsys.readouterr().out) == json.loads(output.read_text(encoding="utf-8"))


def test_evaluate_rejects_artifact_mismatch_before_applying_model_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    run_dir = tmp_path / "run"
    normalized_dir = tmp_path / "normalized"
    normalized_dir.mkdir()
    manifest_path = normalized_dir / "manifest.json"
    manifest_path.write_text('{"dataset":"unit"}\n', encoding="utf-8")
    checkpoint = tmp_path / "checkpoints" / "best.pt"
    cfg = {
        "run": {"output_dir": str(run_dir), "seed": 17},
        "model": {"context_length": 8},
        "tokenizer": {"output_dir": str(tmp_path / "tokenizer")},
        "sharding": {"output_dir": str(tmp_path / "shards")},
        "dataset": {"normalized_dir": str(normalized_dir)},
        "training": {
            "micro_batch_size": 1,
            "eval_batches": 1,
            "precision": "fp32",
            "allow_artifact_mismatch": False,
        },
        "evaluation": {
            "prompts": ["Hello"],
            "max_new_tokens": 1,
            "temperature": 1.0,
            "top_k": None,
            "top_p": None,
        },
    }
    payload = {
        "model": {},
        "extra": {
            "config_sha256": sha256_text(config_to_yaml(cfg)),
            "tokenizer_sha256": "checkpoint-tokenizer",
            "dataset_manifest_hash": sha256_file(manifest_path),
        },
    }
    model_application_attempts = []

    class FakeConfig:
        @staticmethod
        def from_dict(value: dict) -> object:
            return value

    class FakeModel:
        def __init__(self, config: object):
            self.config = config

        def to(self, device: object) -> "FakeModel":
            return self

    def load_checkpoint_probe(*args, **kwargs):
        if kwargs.get("model") is not None:
            model_application_attempts.append("load_checkpoint")
        return payload

    def apply_checkpoint_probe(*args, **kwargs):
        model_application_attempts.append("apply_checkpoint_payload")

    monkeypatch.setattr(evaluate_script, "load_config", lambda path: cfg)
    monkeypatch.setattr(evaluate_script, "get_device", lambda: "cpu")
    monkeypatch.setattr(evaluate_script, "GPTConfig", FakeConfig)
    monkeypatch.setattr(evaluate_script, "GPT", FakeModel)
    monkeypatch.setattr(evaluate_script, "load_checkpoint", load_checkpoint_probe)
    monkeypatch.setattr(
        evaluate_script,
        "apply_checkpoint_payload",
        apply_checkpoint_probe,
        raising=False,
    )
    monkeypatch.setattr(
        evaluate_script,
        "load_tokenizer_metadata",
        lambda path: {"tokenizer_sha256": "current-tokenizer"},
        raising=False,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["evaluate.py", "--config", "config.yaml", "--checkpoint", str(checkpoint)],
    )

    with pytest.raises(ValueError, match="tokenizer_sha256"):
        evaluate_script.main()

    assert model_application_attempts == []
