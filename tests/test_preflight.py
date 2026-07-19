import json
from pathlib import Path

import pytest
import torch

from matgpt.config import clone_config, load_config
from matgpt.data.prepare import make_document_record, write_jsonl_records, write_manifest
from matgpt.data.shard import tokenize_splits_from_config
from matgpt.preflight import build_preflight_report, run_preflight
from matgpt.tokenizer.train import train_tokenizer_from_config


SPECIAL_TOKENS = [
    "<|pad|>",
    "<|bos|>",
    "<|eos|>",
    "<|system|>",
    "<|user|>",
    "<|assistant|>",
    "<|end|>",
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
    cfg["dataset"].update(
        {
            "hf_name": "unit",
            "revision": REVISION,
            "normalized_dir": str(normalized),
            "train_split": "train",
            "validation_split": "validation",
        }
    )
    cfg["tokenizer"].update(
        {
            "vocab_size": 320,
            "output_dir": str(tokenizer_dir),
            "min_frequency": 1,
            "special_tokens": SPECIAL_TOKENS,
        }
    )
    cfg["model"]["vocab_size"] = 320
    cfg["model"]["context_length"] = 8
    cfg["sharding"].update(
        {
            "output_dir": str(shard_dir),
            "shard_size_tokens": 4096,
            "dtype": "uint16",
            "append_eos": True,
        }
    )
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


def test_preflight_reports_train_validation_overlap(synthetic_preflight_cfg):
    normalized_dir = Path(synthetic_preflight_cfg["dataset"]["normalized_dir"])
    validation_path = normalized_dir / "validation.jsonl"
    train_record = json.loads(
        (normalized_dir / "train.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    validation_path.write_text(json.dumps(train_record) + "\n", encoding="utf-8")

    report = build_preflight_report(
        synthetic_preflight_cfg,
        require_t4=False,
        min_free_disk_gb=0.0,
    )

    overlap = next(check for check in report["checks"] if check["name"] == "dataset_overlap")
    assert overlap["status"] == "fail"


def test_preflight_rejects_incompatible_latest_checkpoint(synthetic_preflight_cfg):
    checkpoint = Path(synthetic_preflight_cfg["run"]["output_dir"]) / "checkpoints" / "latest.pt"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"extra": {"config_sha256": "wrong"}, "state": {}}, checkpoint)

    report = build_preflight_report(
        synthetic_preflight_cfg,
        require_t4=False,
        min_free_disk_gb=0.0,
    )

    check = next(item for item in report["checks"] if item["name"] == "checkpoint")
    assert check["status"] == "fail"
