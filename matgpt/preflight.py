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
            raise ValueError(
                f"Quality accepted count mismatch: quality={accepted} files={sum(counts.values())}"
            )
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
        raise ValueError(
            f"Tokenizer vocabulary mismatch: actual={actual_vocab} expected={expected_vocab}"
        )
    missing_specials = [
        token
        for token in cfg["tokenizer"]["special_tokens"]
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
                raise ValueError(
                    f"{split} shard size mismatch for {path}: "
                    f"observed={observed} expected={expected_bytes}"
                )
            if sha256_file(path) != shard["sha256"]:
                raise ValueError(f"{split} shard SHA-256 mismatch: {path}")
            values = np.memmap(path, mode="r", dtype=dtype)
            total_tokens += int(values.size)
            if values.size:
                maximum_id = max(maximum_id, int(values.max()))
                eos_count += int(np.count_nonzero(values == eos_id))
        if total_tokens != int(metadata["total_tokens"]):
            raise ValueError(
                f"{split} token total mismatch: "
                f"files={total_tokens} metadata={metadata['total_tokens']}"
            )
        if total_tokens < int(cfg["model"]["context_length"]) + 1:
            raise ValueError(f"{split} has too few tokens for one context window")
        if maximum_id >= int(cfg["tokenizer"]["vocab_size"]):
            raise ValueError(
                f"{split} token ID {maximum_id} exceeds the configured vocabulary"
            )
        if metadata.get("append_eos") and eos_count != int(metadata["total_documents"]):
            raise ValueError(
                f"{split} EOS count mismatch: eos={eos_count} documents={metadata['total_documents']}"
            )
        details[split] = {
            "total_tokens": total_tokens,
            "maximum_id": maximum_id,
            "eos_count": eos_count,
        }
    return details


def _check_output_storage(cfg: dict[str, Any], min_free_disk_gb: float) -> dict[str, Any]:
    output_dir = Path(cfg["run"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    probe = output_dir / ".preflight-write-probe"
    probe.write_text("ok\n", encoding="utf-8")
    probe.unlink()
    free_gb = shutil.disk_usage(output_dir).free / (1024**3)
    if free_gb < min_free_disk_gb:
        raise ValueError(
            f"Insufficient free disk: observed={free_gb:.2f} GiB "
            f"required={min_free_disk_gb:.2f} GiB"
        )
    return {"output_dir": str(output_dir), "free_disk_gb": free_gb}


def _check_device(require_t4: bool) -> dict[str, Any]:
    cuda = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if cuda else "cpu"
    total_memory_gb = (
        torch.cuda.get_device_properties(0).total_memory / (1024**3) if cuda else 0.0
    )
    if require_t4 and (not cuda or "T4" not in device_name or total_memory_gb < 14.0):
        raise ValueError(
            f"Google Colab T4 required: cuda={cuda} device={device_name!r} "
            f"total_memory_gb={total_memory_gb:.2f}"
        )
    return {
        "cuda_available": cuda,
        "device_name": device_name,
        "total_memory_gb": total_memory_gb,
    }


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
        "dataset_manifest_hash": sha256_file(
            Path(cfg["dataset"]["normalized_dir"]) / "manifest.json"
        ),
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
    cuda_available = torch.cuda.is_available()
    return {
        "status": "pass" if all(check.status == "pass" for check in checks) else "fail",
        "environment": {
            "python_version": platform.python_version(),
            "torch_version": torch.__version__,
            "cuda_version": torch.version.cuda,
            "cuda_available": cuda_available,
            "device_name": torch.cuda.get_device_name(0) if cuda_available else "cpu",
        },
        "checks": [asdict(check) for check in checks],
    }


def run_preflight(
    cfg: dict[str, Any],
    report_path: str | Path,
    require_t4: bool = False,
    min_free_disk_gb: float = 0.0,
) -> dict[str, Any]:
    report = build_preflight_report(cfg, require_t4, min_free_disk_gb)
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if report["status"] != "pass":
        failures = [check for check in report["checks"] if check["status"] == "fail"]
        raise RuntimeError(
            "Preflight failed: "
            + "; ".join(f"{check['name']}: {check['message']}" for check in failures)
        )
    return report
