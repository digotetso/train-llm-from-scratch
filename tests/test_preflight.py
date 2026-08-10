import json
from pathlib import Path

import pytest
import torch

import matgpt.preflight as preflight_module
from matgpt.config import clone_config, config_to_yaml, load_config
from matgpt.data.prepare import make_document_record, write_jsonl_records, write_manifest
from matgpt.data.shard import tokenize_splits_from_config
from matgpt.preflight import build_preflight_report, run_preflight
from matgpt.data.sources import load_source_registry
from matgpt.tokenizer.train import train_tokenizer_from_config
from matgpt.utils.hashing import sha256_file, sha256_json, sha256_text
from scripts.preflight_t4 import main as preflight_main


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
CHECK_IDS = [
    "config",
    "source_revision",
    "dataset_manifest",
    "dataset_overlap",
    "tokenizer",
    "shards",
    "output_storage",
    "device",
    "training_math",
    "checkpoint",
]


def _check(report, name):
    return next(item for item in report["checks"] if item["name"] == name)


@pytest.mark.parametrize(
    ("device_name", "total_memory_gb", "expected_profile", "high_throughput"),
    [
        ("Tesla T4", 14.75, "t4", False),
        ("NVIDIA A100-SXM4-80GB", 79.2, "a100_80gb", True),
        (
            "NVIDIA RTX PRO 6000 Blackwell Server Edition",
            95.6,
            "rtx_pro_6000_blackwell",
            True,
        ),
    ],
)
def test_classify_training_gpu_accepts_supported_full_gpu_profiles(
    device_name,
    total_memory_gb,
    expected_profile,
    high_throughput,
):
    profile = preflight_module.classify_training_gpu(device_name, total_memory_gb)

    assert profile == {
        "profile": expected_profile,
        "device_name": device_name,
        "total_memory_gb": total_memory_gb,
        "high_throughput": high_throughput,
    }


def test_classify_training_gpu_rejects_fractional_rtx_pro_6000():
    with pytest.raises(ValueError, match="at least 90.0 GiB"):
        preflight_module.classify_training_gpu(
            "NVIDIA RTX PRO 6000 Blackwell Server Edition",
            48.0,
        )


def test_cli_supported_gpu_gate_records_full_rtx_profile(
    synthetic_preflight_cfg,
    tmp_path,
    monkeypatch,
):
    config_path = tmp_path / "rtx-preflight.yaml"
    config_path.write_text(config_to_yaml(synthetic_preflight_cfg), encoding="utf-8")
    report_path = tmp_path / "rtx-preflight.json"
    properties = type("DeviceProperties", (), {"total_memory": 97887 * 1024**2})()
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(
        torch.cuda,
        "get_device_name",
        lambda _index: "NVIDIA RTX PRO 6000 Blackwell Server Edition",
    )
    monkeypatch.setattr(torch.cuda, "get_device_properties", lambda _index: properties)

    exit_code = preflight_main(
        [
            "--config",
            str(config_path),
            "--report-path",
            str(report_path),
            "--require-supported-gpu",
        ]
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert _check(report, "device")["details"]["profile"] == "rtx_pro_6000_blackwell"
    assert _check(report, "device")["details"]["high_throughput"] is True


def _write_hashed_json(path: Path, payload: dict, hash_field: str) -> None:
    payload = dict(payload)
    payload.pop(hash_field, None)
    payload[hash_field] = sha256_json(payload)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
    assert [check["name"] for check in report["checks"]] == CHECK_IDS
    assert _check(report, "config")["details"]["config_sha256"] == sha256_text(
        config_to_yaml(synthetic_preflight_cfg)
    )
    shard_details = _check(report, "shards")["details"]
    for split, details in shard_details.items():
        metadata_path = Path(synthetic_preflight_cfg["sharding"]["output_dir"]) / f"{split}_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert details["metadata_sha256"] == metadata["metadata_sha256"]
        assert details["shard_files_sha256"] == sha256_json([
            {"path": shard["path"], "byte_size": shard["byte_size"],
             "num_tokens": shard["num_tokens"], "sha256": sha256_file(metadata_path.parent / shard["path"])}
            for shard in metadata["shards"]
        ])
    assert (tmp_path / "preflight.json").exists()


def test_preflight_checks_every_configured_training_phase(
    synthetic_preflight_cfg,
    tmp_path,
):
    cfg = synthetic_preflight_cfg
    normalized = Path(cfg["dataset"]["normalized_dir"])
    train_rows = [
        json.loads(line)
        for line in (normalized / "train.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    main_stats = write_jsonl_records(normalized / "main.jsonl", train_rows[:20])
    cooldown_rows = [
        make_document_record(
            "unit",
            "cooldown",
            index,
            f"Cooldown telecom example {index} discusses routing and radio links.",
        )
        for index in range(20)
    ]
    cooldown_stats = write_jsonl_records(
        normalized / "cooldown.jsonl", cooldown_rows
    )
    validation_stats = preflight_module._normalized_split_evidence(
        normalized / "validation.jsonl"
    )
    write_manifest(
        normalized / "manifest.json",
        dataset_name="unit-phased",
        version_or_commit=REVISION,
        license_name="test",
        stage="base_pretraining",
        language="en",
        split_stats={
            "main": main_stats,
            "cooldown": cooldown_stats,
            "validation": validation_stats,
        },
        notes="synthetic phased preflight fixture",
    )
    cfg["dataset"].update(
        {
            "train_split": "main",
            "training_splits": {"main": "main", "cooldown": "cooldown"},
        }
    )
    cfg["training"]["data_phases"] = [
        {"name": "main", "split": "main", "until_tokens": 2048},
        {"name": "cooldown", "split": "cooldown", "until_tokens": 4096},
    ]
    train_tokenizer_from_config(cfg)
    tokenize_splits_from_config(cfg)

    report = build_preflight_report(cfg, require_t4=False, min_free_disk_gb=0.0)

    assert _check(report, "dataset_manifest")["status"] == "pass"
    assert _check(report, "dataset_overlap")["status"] == "pass"
    assert set(_check(report, "shards")["details"]) == {
        "main",
        "cooldown",
        "validation",
    }


def test_preflight_accepts_pinned_registry_dataset_identity(tmp_path):
    registry_path = Path("configs/data/telco_300m_sources.yaml")
    registry = load_source_registry(registry_path)
    normalized = tmp_path / "normalized"
    split_stats = {}
    for split in ("main", "cooldown", "validation"):
        records = [
            make_document_record(
                "registry-unit",
                split,
                index,
                f"Unique {split} telecom routing sample {index}.",
            )
            for index in range(3)
        ]
        split_stats[split] = write_jsonl_records(
            normalized / f"{split}.jsonl", records
        )
    manifest = {
        "version": 1,
        "complete": True,
        "split_stats": split_stats,
        "sources": [
            {
                "id": source.id,
                "revision": source.revision,
                "role": source.role,
            }
            for source in registry.sources
            if source.role.startswith("pretrain_")
        ],
    }
    _write_hashed_json(normalized / "manifest.json", manifest, "manifest_sha256")
    cfg = clone_config(load_config("configs/matgpt_telco_300m.yaml"))
    cfg["dataset"]["normalized_dir"] = str(normalized)

    source_details = preflight_module._check_source_revision(cfg)
    manifest_details = preflight_module._check_dataset_manifest(cfg)

    assert source_details["registry_source_count"] == len(registry.sources)
    assert set(manifest_details["document_counts"]) == {
        "main",
        "cooldown",
        "validation",
    }


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


def test_failed_device_probe_persists_complete_report(
    synthetic_preflight_cfg,
    tmp_path,
    monkeypatch,
):
    report_path = tmp_path / "failed-preflight.json"

    def unavailable():
        raise RuntimeError("cuda probe unavailable")

    monkeypatch.setattr(torch.cuda, "is_available", unavailable)

    with pytest.raises(RuntimeError, match="device"):
        run_preflight(synthetic_preflight_cfg, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "fail"
    assert [check["name"] for check in report["checks"]] == CHECK_IDS
    assert _check(report, "device")["status"] == "fail"
    assert report["environment"]["cuda_available"] is None
    assert report["environment"]["device_name"] == "unavailable"
    assert report["environment"]["device_probe_error"] == "cuda probe unavailable"


def test_cli_persists_deterministic_report_for_malformed_config(tmp_path):
    config_path = tmp_path / "malformed.yaml"
    config_path.write_text("run: [\n", encoding="utf-8")
    report_paths = [tmp_path / "first.json", tmp_path / "second.json"]

    exit_codes = [
        preflight_main(
            [
                "--config",
                str(config_path),
                "--report-path",
                str(report_path),
            ]
        )
        for report_path in report_paths
    ]
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]

    assert exit_codes == [1, 1]
    assert reports[0] == reports[1]
    assert reports[0]["status"] == "fail"
    assert [check["name"] for check in reports[0]["checks"]] == CHECK_IDS
    assert _check(reports[0], "config")["status"] == "fail"


def test_cli_uses_safe_fallback_report_for_invalid_config(tmp_path, monkeypatch):
    config_path = tmp_path / "invalid.yaml"
    config_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = preflight_main(["--config", str(config_path)])

    report_path = tmp_path / "preflight.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert report["status"] == "fail"
    assert _check(report, "config")["status"] == "fail"


@pytest.mark.parametrize("output_dir_state", ["missing", "null", "empty"])
def test_cli_falls_back_for_unusable_run_output_dir(
    tmp_path,
    monkeypatch,
    output_dir_state,
):
    cfg = clone_config(load_config("configs/matgpt_mini_8m.yaml"))
    if output_dir_state == "missing":
        cfg["run"].pop("output_dir")
    else:
        cfg["run"]["output_dir"] = None if output_dir_state == "null" else ""
    config_path = tmp_path / f"{output_dir_state}.yaml"
    config_path.write_text(config_to_yaml(cfg), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = preflight_main(["--config", str(config_path)])

    report_path = tmp_path / "preflight.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert report["status"] == "fail"
    assert [check["name"] for check in report["checks"]] == CHECK_IDS
    assert _check(report, "config")["status"] == "fail"
    assert "run.output_dir" in _check(report, "config")["message"]


def test_explicit_report_path_precedes_unusable_run_output_dir(tmp_path, monkeypatch):
    cfg = clone_config(load_config("configs/matgpt_mini_8m.yaml"))
    cfg["run"]["output_dir"] = None
    config_path = tmp_path / "null-output.yaml"
    config_path.write_text(config_to_yaml(cfg), encoding="utf-8")
    report_path = tmp_path / "explicit" / "preflight.json"
    monkeypatch.chdir(tmp_path)

    exit_code = preflight_main(
        [
            "--config",
            str(config_path),
            "--report-path",
            str(report_path),
        ]
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert not (tmp_path / "preflight.json").exists()
    assert _check(report, "config")["status"] == "fail"
    assert "run.output_dir" in _check(report, "config")["message"]


def test_preflight_recomputes_normalized_record_hashes(synthetic_preflight_cfg):
    train_path = Path(synthetic_preflight_cfg["dataset"]["normalized_dir"]) / "train.jsonl"
    lines = train_path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    record["text"] += " tampered"
    lines[0] = json.dumps(record, ensure_ascii=False, sort_keys=True)
    train_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = build_preflight_report(synthetic_preflight_cfg, False, 0.0)

    check = _check(report, "dataset_manifest")
    assert check["status"] == "fail"
    assert "text_sha256" in check["message"]


def test_normalized_digest_does_not_join_all_document_hashes(
    synthetic_preflight_cfg,
    monkeypatch,
):
    train_path = Path(synthetic_preflight_cfg["dataset"]["normalized_dir"]) / "train.jsonl"
    manifest = json.loads(
        (train_path.parent / "manifest.json").read_text(encoding="utf-8")
    )
    hashed_inputs = []

    def tracking_sha256_text(value):
        hashed_inputs.append(value)
        return sha256_text(value)

    monkeypatch.setattr(preflight_module, "sha256_text", tracking_sha256_text)

    evidence = preflight_module._normalized_split_evidence(train_path)

    assert evidence["documents_sha256"] == manifest["split_stats"]["train"][
        "documents_sha256"
    ]
    assert max(len(value) for value in hashed_inputs) < 128


@pytest.mark.parametrize("field", ["raw_bytes", "total_chars", "documents_sha256"])
def test_preflight_recomputes_manifest_split_evidence(synthetic_preflight_cfg, field):
    manifest_path = (
        Path(synthetic_preflight_cfg["dataset"]["normalized_dir"]) / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    split_stats = manifest["split_stats"]["train"]
    split_stats[field] = "0" * 64 if field == "documents_sha256" else split_stats[field] + 1
    _write_hashed_json(manifest_path, manifest, "manifest_sha256")

    report = build_preflight_report(synthetic_preflight_cfg, False, 0.0)

    check = _check(report, "dataset_manifest")
    assert check["status"] == "fail"
    assert field in check["message"]


@pytest.mark.parametrize(
    ("field", "stale_value"),
    [
        ("split", "other"),
        ("tokenizer_sha256", "0" * 64),
        ("dtype", "uint32"),
        ("append_eos", False),
        ("shard_size_tokens", 4097),
        ("total_documents", 41),
    ],
)
def test_preflight_rejects_stale_shard_provenance(
    synthetic_preflight_cfg,
    field,
    stale_value,
):
    metadata_path = (
        Path(synthetic_preflight_cfg["sharding"]["output_dir"]) / "train_metadata.json"
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata[field] = stale_value
    _write_hashed_json(metadata_path, metadata, "metadata_sha256")

    report = build_preflight_report(synthetic_preflight_cfg, False, 0.0)

    check = _check(report, "shards")
    assert check["status"] == "fail"
    assert field in check["message"]


@pytest.mark.parametrize("split", ("train", "validation"))
def test_legacy_preflight_requires_each_shard_metadata_internal_fingerprint(
    synthetic_preflight_cfg,
    split,
):
    metadata_path = (
        Path(synthetic_preflight_cfg["sharding"]["output_dir"])
        / f"{split}_metadata.json"
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.pop("metadata_sha256")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    report = build_preflight_report(synthetic_preflight_cfg, False, 0.0)

    check = _check(report, "shards")
    assert report["status"] == "fail"
    assert check["status"] == "fail"
    assert "metadata_sha256" in check["message"]


def test_preflight_rejects_shard_path_outside_output_root(
    synthetic_preflight_cfg,
    tmp_path,
):
    metadata_path = (
        Path(synthetic_preflight_cfg["sharding"]["output_dir"]) / "train_metadata.json"
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    source_path = metadata_path.parent / metadata["shards"][0]["path"]
    outside_path = tmp_path / "outside.bin"
    outside_path.write_bytes(source_path.read_bytes())
    metadata["shards"][0]["path"] = str(outside_path)
    _write_hashed_json(metadata_path, metadata, "metadata_sha256")

    report = build_preflight_report(synthetic_preflight_cfg, False, 0.0)

    check = _check(report, "shards")
    assert check["status"] == "fail"
    assert "outside sharding.output_dir" in check["message"]


def test_output_storage_does_not_destroy_preexisting_probe_name(synthetic_preflight_cfg):
    output_dir = Path(synthetic_preflight_cfg["run"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    collision = output_dir / ".preflight-write-probe"
    collision.write_text("user-owned\n", encoding="utf-8")

    report = build_preflight_report(synthetic_preflight_cfg, False, 0.0)

    assert _check(report, "output_storage")["status"] == "pass"
    assert collision.read_text(encoding="utf-8") == "user-owned\n"
