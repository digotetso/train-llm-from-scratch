import json
import sys
from pathlib import Path

from matgpt.config import config_to_yaml
from matgpt.utils.hashing import sha256_file, sha256_json, sha256_text
from scripts import evaluate as evaluate_script
from scripts import evaluate_tasks as tasks_script


class _FakeDevice:
    type = "cpu"


class _FakeModel:
    def __init__(self, _config: object):
        pass

    def to(self, _device: object) -> "_FakeModel":
        return self


class _FakeConfig:
    @staticmethod
    def from_dict(value: object) -> object:
        return value


class _FakeTokenizer:
    def token_to_id(self, token: str) -> int:
        assert token == "<|eos|>"
        return 2


def _producer_fixture(tmp_path: Path) -> tuple[dict[str, object], Path, dict[str, str]]:
    tokenizer = tmp_path / "tokenizer"
    tokenizer.mkdir()
    tokenizer_sha = "a" * 64
    (tokenizer / "special_tokens.json").write_text(
        json.dumps({"tokenizer_sha256": tokenizer_sha}), encoding="utf-8"
    )
    normalized = tmp_path / "normalized"
    normalized.mkdir()
    unsigned_manifest = {"version": 1, "complete": True}
    manifest_identity = sha256_json(unsigned_manifest)
    manifest = {**unsigned_manifest, "manifest_sha256": manifest_identity}
    manifest_path = normalized / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    checkpoint = tmp_path / "pilot-checkpoint.pt"
    checkpoint.write_bytes(b"immutable pilot checkpoint")
    cfg: dict[str, object] = {
        "run": {"seed": 17, "output_dir": str(tmp_path / "run")},
        "model": {"context_length": 8},
        "tokenizer": {"output_dir": str(tokenizer)},
        "sharding": {"output_dir": str(tmp_path / "shards")},
        "dataset": {
            "normalized_dir": str(normalized),
            "validation_split": "validation",
        },
        "training": {
            "micro_batch_size": 1,
            "eval_batches": 1,
            "precision": "fp32",
            "allow_artifact_mismatch": False,
        },
        "evaluation": {
            "prompts": ["A router"],
            "max_new_tokens": 2,
            "temperature": 1.0,
            "top_k": None,
            "top_p": None,
        },
    }
    identity = {
        "config_sha256": sha256_text(config_to_yaml(cfg)),
        "tokenizer_sha256": tokenizer_sha,
        "dataset_manifest_sha256": sha256_file(manifest_path),
        "dataset_manifest_identity_sha256": manifest_identity,
        "build_identity_sha256": sha256_json({
            "format": "legacy_telco_prepare_v1",
            "manifest_sha256": manifest_identity,
            "tokenizer_sha256": tokenizer_sha,
        }),
    }
    return cfg, checkpoint, identity


def _patch_common(monkeypatch, script, cfg: dict[str, object]) -> None:
    monkeypatch.setattr(script, "load_config", lambda _path: cfg)
    monkeypatch.setattr(script, "get_device", lambda: _FakeDevice())
    monkeypatch.setattr(script, "GPTConfig", _FakeConfig)
    monkeypatch.setattr(script, "GPT", _FakeModel)
    monkeypatch.setattr(script, "load_tokenizer", lambda _path: _FakeTokenizer())
    monkeypatch.setattr(script, "load_checkpoint", lambda *_args, **_kwargs: {"model": {}})


def test_evaluate_producer_emits_checkpoint_and_build_identity(
    tmp_path: Path, monkeypatch
):
    cfg, checkpoint, identity = _producer_fixture(tmp_path)
    output = tmp_path / "base.json"
    _patch_common(monkeypatch, evaluate_script, cfg)
    monkeypatch.setattr(evaluate_script, "validate_checkpoint_compatibility", lambda *_: None)
    monkeypatch.setattr(evaluate_script, "apply_checkpoint_payload", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(evaluate_script, "PackedTokenDataset", type(
        "FakeDataset", (), {"from_metadata": classmethod(lambda cls, *_args, **_kwargs: object())}
    ))
    monkeypatch.setattr(evaluate_script, "metadata_path_for_split", lambda *_: tmp_path / "metadata.json")
    monkeypatch.setattr(evaluate_script, "evaluate_loss", lambda *_args, **_kwargs: 2.0)
    monkeypatch.setattr(evaluate_script, "generate_samples", lambda **_kwargs: [
        {"prompt": "A router", "text": "A router forwards packets."}
    ])
    monkeypatch.setattr(evaluate_script, "set_seed", lambda _seed: None)
    monkeypatch.setattr(sys, "argv", [
        "evaluate.py", "--config", "config.yaml", "--checkpoint", str(checkpoint),
        "--output", str(output),
    ])

    evaluate_script.main()

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["checkpoint_binding"] == {
        "path": str(checkpoint.resolve()),
        "size": 26,
        "sha256": "1bd7d298d2207a97e0b486cd344a0d273c117000dbeae4fb68bf9c9e8151fefb",
    }
    assert payload["artifact_identity"] == identity


def test_evaluate_tasks_producer_emits_same_checkpoint_and_build_identity(
    tmp_path: Path, monkeypatch
):
    cfg, checkpoint, identity = _producer_fixture(tmp_path)
    output = tmp_path / "tasks.json"
    task = tmp_path / "task.jsonl"
    task.write_text("{}\n", encoding="utf-8")
    _patch_common(monkeypatch, tasks_script, cfg)
    monkeypatch.setattr(tasks_script, "load_checkpoint", lambda *_args, **_kwargs: {
        "model": {},
        "extra": {
            "config_sha256": identity["config_sha256"],
            "tokenizer_sha256": identity["tokenizer_sha256"],
            "dataset_manifest_hash": identity["dataset_manifest_sha256"],
        },
    })
    monkeypatch.setattr(
        tasks_script, "apply_checkpoint_payload", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(tasks_script, "evaluate_multiple_choice_file", lambda **_kwargs: {
        "task_type": "multiple_choice", "path": str(task), "total": 1,
        "correct": 1, "accuracy": 1.0, "categories": {
            "routing": {"total": 1, "correct": 1, "accuracy": 1.0}
        }, "examples": [{"id": "q1", "category": "routing", "answer_index": 0,
            "prediction_index": 0, "correct": True, "choice_losses": [0.1, 1.0]}],
    })
    monkeypatch.setattr(sys, "argv", [
        "evaluate_tasks.py", "--config", "config.yaml", "--checkpoint",
        str(checkpoint), "--task", str(task), "--output", str(output),
    ])

    tasks_script.main()

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["checkpoint_binding"]["sha256"] == (
        "1bd7d298d2207a97e0b486cd344a0d273c117000dbeae4fb68bf9c9e8151fefb"
    )
    assert payload["checkpoint_binding"]["path"] == str(checkpoint.resolve())
    assert payload["artifact_identity"] == identity
