import json
import sys
from pathlib import Path

import pytest

from matgpt.utils.hashing import sha256_file
from scripts import compare_checkpoints as compare_script


def _base_cli_files(tmp_path: Path) -> dict[str, Path]:
    files = {
        "config": tmp_path / "config.yaml",
        "first": tmp_path / "first.pt",
        "second": tmp_path / "second.pt",
        "prompts": tmp_path / "prompts.jsonl",
        "task": tmp_path / "task.jsonl",
        "judge_prompt": tmp_path / "judge_prompt.md",
    }
    for key in ("config", "first", "second", "task"):
        files[key].write_text("placeholder\n", encoding="utf-8")
    files["prompts"].write_text(
        '{"id":"p1","category":"mixed","text":"Once upon a time"}\n',
        encoding="utf-8",
    )
    files["judge_prompt"].write_text("Judge these stories.", encoding="utf-8")
    return files


def _valid_argv(files: dict[str, Path], output: Path) -> list[str]:
    return [
        "compare_checkpoints.py",
        "--config",
        str(files["config"]),
        "--checkpoint",
        f"170m={files['first']}",
        "--checkpoint",
        f"200m={files['second']}",
        "--validation-seeds",
        "1001,1002",
        "--generation-seeds",
        "2001,2002",
        "--prompts",
        str(files["prompts"]),
        "--task",
        str(files["task"]),
        "--judge-prompt",
        str(files["judge_prompt"]),
        "--review-per-checkpoint",
        "1",
        "--output-dir",
        str(output),
    ]


@pytest.mark.parametrize(
    "case",
    [
        "duplicate_labels",
        "duplicate_seeds",
        "one_checkpoint",
        "missing_prompts",
        "missing_task",
        "existing_output",
    ],
)
def test_compare_checkpoints_rejects_invalid_requests_before_model_loading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
):
    files = _base_cli_files(tmp_path)
    output = tmp_path / "comparison"
    argv = _valid_argv(files, output)
    if case == "duplicate_labels":
        argv[6] = f"170m={files['second']}"
    elif case == "duplicate_seeds":
        argv[8] = "1001,1001"
    elif case == "one_checkpoint":
        del argv[5:7]
    elif case == "missing_prompts":
        argv[12] = str(tmp_path / "missing-prompts.jsonl")
    elif case == "missing_task":
        argv[14] = str(tmp_path / "missing-task.jsonl")
    elif case == "existing_output":
        output.mkdir()

    monkeypatch.setattr(sys, "argv", argv)

    def fail_model_probe():
        raise AssertionError("model loading started before request validation")

    monkeypatch.setattr(compare_script, "get_device", fail_model_probe)

    with pytest.raises((ValueError, FileExistsError)):
        compare_script.main()


def test_compare_checkpoints_runs_tiny_protocol_and_writes_blinded_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    files = _base_cli_files(tmp_path)
    files["prompts"].write_text(
        "".join(
            [
                '{"id":"p1","category":"character","text":"Once upon a time"}\n',
                '{"id":"p2","category":"cause_effect","text":"Because it rained"}\n',
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "comparison"
    normalized = tmp_path / "normalized"
    normalized.mkdir()
    (normalized / "manifest.json").write_text("{}\n", encoding="utf-8")
    cfg = {
        "run": {"seed": 17},
        "model": {"context_length": 8},
        "tokenizer": {"output_dir": str(tmp_path / "tokenizer")},
        "sharding": {"output_dir": str(tmp_path / "shards")},
        "dataset": {"normalized_dir": str(normalized)},
        "training": {
            "micro_batch_size": 1,
            "eval_batches": 1,
            "precision": "fp32",
            "allow_artifact_mismatch": True,
        },
        "evaluation": {
            "max_new_tokens": 4,
            "temperature": 1.0,
            "top_k": None,
            "top_p": None,
        },
    }

    class FakeDevice:
        type = "cpu"

    class FakeConfig:
        @staticmethod
        def from_dict(value: dict[str, object]) -> object:
            return value

    class FakeModel:
        label = ""

        def __init__(self, config: object):
            self.config = config

        def to(self, device: object) -> "FakeModel":
            return self

    class FakeTokenizer:
        def token_to_id(self, token: str) -> int:
            assert token == "<|eos|>"
            return 2

    dataset_seed_calls: list[int] = []

    class FakeDataset:
        @classmethod
        def from_metadata(cls, *args, **kwargs) -> dict[str, int]:
            dataset_seed_calls.append(kwargs["seed"])
            return {"seed": kwargs["seed"]}

    def fake_apply(payload: dict[str, object], model: FakeModel, **kwargs) -> None:
        model.label = str(payload["label"])

    def fake_loss(model: FakeModel, dataset: dict[str, int], **kwargs) -> float:
        offset = 0.0 if model.label == "170m" else 0.1
        return 1.0 + offset + (dataset["seed"] - 1000) / 100.0

    seed_calls: list[int] = []

    def fake_generate(**kwargs) -> list[dict[str, str]]:
        return [
            {"prompt": prompt, "text": f"{prompt} story seed {seed_calls[-1]}."}
            for prompt in kwargs["prompts"]
        ]

    monkeypatch.setattr(compare_script, "load_config", lambda path: cfg)
    monkeypatch.setattr(compare_script, "get_device", lambda: FakeDevice())
    monkeypatch.setattr(compare_script, "GPTConfig", FakeConfig)
    monkeypatch.setattr(compare_script, "GPT", FakeModel)
    monkeypatch.setattr(
        compare_script,
        "load_checkpoint",
        lambda path, **kwargs: {"label": Path(path).stem, "model": {}},
    )
    monkeypatch.setattr(compare_script, "apply_checkpoint_payload", fake_apply)
    monkeypatch.setattr(compare_script, "load_tokenizer", lambda path: FakeTokenizer())
    monkeypatch.setattr(compare_script, "PackedTokenDataset", FakeDataset)
    monkeypatch.setattr(
        compare_script,
        "metadata_path_for_split",
        lambda *args: tmp_path / "metadata.json",
    )
    monkeypatch.setattr(
        compare_script, "effective_validation_split", lambda dataset: "validation"
    )
    monkeypatch.setattr(compare_script, "evaluate_loss", fake_loss)
    monkeypatch.setattr(
        compare_script,
        "evaluate_multiple_choice_file",
        lambda **kwargs: {
            "task_type": "multiple_choice",
            "total": 1,
            "correct": 1,
            "accuracy": 1.0,
            "categories": {
                "character": {"total": 1, "correct": 1, "accuracy": 1.0}
            },
            "examples": [],
        },
    )
    monkeypatch.setattr(compare_script, "generate_samples", fake_generate)
    monkeypatch.setattr(compare_script, "set_seed", seed_calls.append)
    monkeypatch.setattr(compare_script, "validate_consistency_asset", lambda path: {})
    monkeypatch.setattr(sys, "argv", _valid_argv(files, output))

    compare_script.main()

    summary = json.loads(
        (output / "comparison_summary.json").read_text(encoding="utf-8")
    )
    assert summary["protocol"]["validation_seeds"] == [1001, 1002]
    assert summary["protocol"]["generation_seeds"] == [2001, 2002]
    assert summary["validation"]["pairs"][0]["seed_count"] == 2
    batch_paths = list((output / "llm_judge" / "batches").glob("*.jsonl"))
    assert len(batch_paths) == 1
    judge_rows = [
        json.loads(line)
        for line in batch_paths[0].read_text(encoding="utf-8").splitlines()
    ]
    assert len(judge_rows) == 2
    assert not any("checkpoint" in row for row in judge_rows)
    assert all(
        (output / "checkpoints" / f"{label}.json").is_file()
        for label in ("170m", "200m")
    )
    for label, source_name in (("170m", "first"), ("200m", "second")):
        expected_binding = {
            "path": str(files[source_name].resolve()),
            "size": files[source_name].stat().st_size,
            "sha256": sha256_file(files[source_name]),
        }
        assert summary["checkpoints"][label]["binding"] == expected_binding
        detail = json.loads(
            (output / "checkpoints" / f"{label}.json").read_text(encoding="utf-8")
        )
        assert detail["checkpoint_binding"] == expected_binding
    assert dataset_seed_calls == [1001, 1002, 1001, 1002]
    assert seed_calls == [17, 2001, 2002, 17, 2001, 2002]
