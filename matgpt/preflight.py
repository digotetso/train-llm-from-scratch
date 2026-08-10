from __future__ import annotations

import hashlib
import json
import math
import platform
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable

import numpy as np
import torch

from matgpt.config import config_to_yaml, validate_config
from matgpt.data.prepare import effective_validation_split
from matgpt.data.shard import resolve_shard_artifact_path
from matgpt.data.sources import PRETRAIN_ROLES, load_source_registry
from matgpt.model.gpt import GPT, GPTConfig, count_parameters
from matgpt.preflight_schema import CHECK_IDS
from matgpt.tokenizer.io import load_tokenizer, load_tokenizer_metadata
from matgpt.training.dataset import (
    load_verified_shard_metadata,
    metadata_path_for_split,
)
from matgpt.training.pretrain import validate_checkpoint_compatibility
from matgpt.training.schedule import build_training_schedule
from matgpt.utils.hashing import sha256_file, sha256_json, sha256_text
from matgpt.utils.paths import require_managed_path


SUPPORTED_TRAINING_GPUS = (
    ("rtx_pro_6000_blackwell", "RTX PRO 6000 Blackwell", 90.0, True),
    ("a100_80gb", "A100", 75.0, True),
    ("t4", "T4", 14.0, False),
)


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


def _normalized_split_evidence(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Required JSONL artifact is missing: {path}")
    document_count = 0
    total_chars = 0
    documents_digest = hashlib.sha256()
    for line_number, row in _nonempty_jsonl_rows(path):
        if not isinstance(row, dict):
            raise TypeError(f"{path}:{line_number} must contain a JSON object")
        text = row.get("text")
        if not isinstance(text, str):
            raise TypeError(f"{path}:{line_number} text must be a string")
        text_hash = sha256_text(text)
        if row.get("text_sha256") != text_hash:
            raise ValueError(
                f"{path}:{line_number} text_sha256 does not match normalized text"
            )
        if "num_chars" in row and (
            type(row["num_chars"]) is not int or row["num_chars"] != len(text)
        ):
            raise ValueError(
                f"{path}:{line_number} num_chars does not match normalized text"
            )
        document_count += 1
        total_chars += len(text)
        documents_digest.update(text_hash.encode("utf-8"))
    return {
        "document_count": document_count,
        "raw_bytes": path.stat().st_size,
        "total_chars": total_chars,
        "documents_sha256": documents_digest.hexdigest(),
    }


def _check_config(cfg: dict[str, Any]) -> dict[str, Any]:
    validate_config(cfg)
    return {
        "run_name": cfg["run"]["name"],
        "config_sha256": sha256_text(config_to_yaml(cfg)),
    }


def _check_source_revision(cfg: dict[str, Any]) -> dict[str, Any]:
    dataset_cfg = cfg["dataset"]
    revision = dataset_cfg.get("revision")
    if isinstance(revision, str) and revision.startswith("registry:"):
        declared_path = Path(revision.removeprefix("registry:"))
        registry_path = Path(dataset_cfg.get("source_registry_path", declared_path))
        if declared_path.resolve() != registry_path.resolve():
            raise ValueError(
                "dataset.revision registry path does not match "
                "dataset.source_registry_path"
            )
        registry = load_source_registry(registry_path)
        return {
            "revision": revision,
            "registry_path": str(registry_path),
            "registry_sha256": sha256_file(registry_path),
            "registry_source_count": len(registry.sources),
        }
    if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError(
            "dataset.revision must be a 40-character commit hash or a pinned "
            f"registry reference; observed {revision!r}"
        )
    return {"revision": revision}


def _configured_data_splits(dataset_cfg: dict[str, Any]) -> list[str]:
    training_splits = dataset_cfg.get("training_splits")
    if training_splits:
        splits = list(dict.fromkeys(training_splits.values()))
    else:
        splits = [dataset_cfg["train_split"]]
    validation_split = effective_validation_split(dataset_cfg)
    if validation_split not in splits:
        splits.append(validation_split)
    return splits


def _safe_relative_artifact(
    root: Path, value: object, *, kind: str = "file", allow_missing: bool = False
) -> Path:
    if not isinstance(value, str):
        raise ValueError("artifact path must be a safe relative POSIX path")
    relative = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or relative.is_absolute()
        or ".." in relative.parts
        or str(relative) != value
    ):
        raise ValueError("artifact path must be a safe relative POSIX path")
    return require_managed_path(
        root,
        root / Path(*relative.parts),
        kind=kind,
        allow_missing=allow_missing,
    )


def _verified_json_artifact(
    root: Path, record: object, *, internal_hash_field: str | None = None
) -> tuple[Path, dict[str, Any]]:
    if not isinstance(record, dict):
        raise ValueError("manifest artifact evidence must be an object")
    path = _safe_relative_artifact(root, record.get("path"))
    if path.stat().st_size != int(record.get("size", -1)):
        raise ValueError(f"artifact size mismatch: {path}")
    if sha256_file(path) != record.get("sha256"):
        raise ValueError(f"artifact SHA-256 mismatch: {path}")
    payload = _read_json(path)
    if internal_hash_field is not None:
        stored = payload.get(internal_hash_field)
        unsigned = dict(payload)
        unsigned.pop(internal_hash_field, None)
        if stored != sha256_json(unsigned):
            raise ValueError(f"{path.name} internal checksum mismatch")
    return path, payload


def _check_chunked_dataset_manifest(
    cfg: dict[str, Any], manifest: dict[str, Any], normalized: Path, stored_hash: str
) -> dict[str, Any]:
    if manifest.get("complete") is not True or manifest.get("status") != "complete":
        raise ValueError("Chunked corpus manifest is not complete")
    if manifest.get("version") != 2 or manifest.get("evidence_schema_version") != 2:
        raise ValueError("Unsupported chunked corpus builder/schema version")
    if manifest.get("builder") != "local_corpus":
        raise ValueError("Chunked corpus builder must be local_corpus")
    fingerprints = manifest.get("fingerprints")
    if not isinstance(fingerprints, dict):
        raise ValueError("Chunked corpus manifest has no fingerprints")
    if manifest.get("build_identity_sha256") != sha256_json(fingerprints):
        raise ValueError("Chunked corpus build identity does not match fingerprints")
    content_keys = [
        "version",
        "builder",
        "storage_format",
        "build_identity_sha256",
        "fingerprints",
        "stages",
        "sources",
        "split_stats",
        "breakdowns",
        "unit_artifacts",
        "audits",
    ]
    if "raw_record_schema" in manifest:
        content_keys.insert(3, "raw_record_schema")
    content_payload = {key: manifest.get(key) for key in content_keys}
    if manifest.get("content_sha256") != sha256_json(content_payload):
        raise ValueError("Chunked corpus content_sha256 does not match logical content")
    tokenizer_sha256 = load_tokenizer_metadata(cfg["tokenizer"]["output_dir"])[
        "tokenizer_sha256"
    ]
    if fingerprints.get("tokenizer_sha256") != tokenizer_sha256:
        raise ValueError("Chunked corpus tokenizer fingerprint mismatch")
    revision = cfg["dataset"]["revision"]
    if isinstance(revision, str) and revision.startswith("registry:"):
        registry = load_source_registry(cfg["dataset"]["source_registry_path"])
        if fingerprints.get("source_registry_sha256") != sha256_json(asdict(registry)):
            raise ValueError("Chunked corpus source-registry fingerprint mismatch")

    audit_payloads: dict[str, dict[str, Any]] = {}
    audits = manifest.get("audits")
    if not isinstance(audits, dict):
        raise ValueError("Chunked corpus manifest has no audit evidence")
    for name in ("quota_audit", "license_audit", "quality_audit", "overlap_audit"):
        _path, payload = _verified_json_artifact(
            normalized, audits.get(name), internal_hash_field="audit_sha256"
        )
        if payload.get("passed") is not True:
            raise ValueError(f"{name} did not pass")
        audit_payloads[name] = payload
    if audit_payloads["quota_audit"].get("tokenizer_sha256") != tokenizer_sha256:
        raise ValueError("Quota audit tokenizer fingerprint mismatch")
    if audit_payloads["quota_audit"].get("plan_sha256") != fingerprints.get("plan_sha256"):
        raise ValueError("Quota audit plan fingerprint mismatch")
    if audit_payloads["license_audit"].get("source_registry_sha256") != fingerprints.get(
        "source_registry_sha256"
    ):
        raise ValueError("License audit source-registry fingerprint mismatch")
    if audit_payloads["quality_audit"].get("contamination_sha256") != fingerprints.get(
        "contamination_sha256"
    ):
        raise ValueError("Quality audit contamination fingerprint mismatch")

    split_stats = manifest.get("split_stats")
    split_metadata = manifest.get("split_metadata")
    if not isinstance(split_stats, dict) or not isinstance(split_metadata, dict):
        raise ValueError("Chunked corpus split evidence is incomplete")
    counts: dict[str, int] = {}
    metadata_evidence: dict[str, Any] = {}
    for split in _configured_data_splits(cfg["dataset"]):
        stats = split_stats.get(split)
        if not isinstance(stats, dict):
            raise ValueError(f"Chunked corpus has no split {split!r}")
        count = stats.get("document_count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise ValueError(f"Chunked corpus split {split!r} has no documents")
        chunks = stats.get("raw_chunks")
        if not isinstance(chunks, list) or not chunks:
            raise ValueError(f"Chunked corpus split {split!r} has no raw chunks")
        for chunk in chunks:
            if not isinstance(chunk, dict):
                raise ValueError("raw chunk evidence must be an object")
            expected_size = chunk.get("size")
            expected_sha256 = chunk.get("sha256")
            if (
                not isinstance(expected_size, int)
                or isinstance(expected_size, bool)
                or expected_size < 0
                or not isinstance(expected_sha256, str)
                or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
            ):
                raise ValueError("raw chunk fingerprint evidence is invalid")
            # A Colab prebuilt restore intentionally omits normalized text. The
            # final manifest already binds each raw chunk's safe path, size, and
            # SHA while training consumes only the separately verified shards.
            chunk_path = _safe_relative_artifact(
                normalized, chunk.get("path"), allow_missing=True
            )
            if chunk_path.exists() and chunk_path.stat().st_size != expected_size:
                raise ValueError(f"raw chunk size mismatch: {chunk_path}")
        metadata_record = split_metadata.get(split)
        _metadata_path, metadata = _verified_json_artifact(
            normalized,
            metadata_record,
            internal_hash_field="metadata_sha256",
        )
        if (
            not isinstance(metadata_record, dict)
            or metadata_record.get("metadata_sha256")
            != metadata.get("metadata_sha256")
        ):
            raise ValueError(f"{split} metadata internal fingerprint mismatch")
        if metadata.get("split") != split or metadata.get("total_documents") != count:
            raise ValueError(f"{split} metadata provenance mismatch")
        counts[split] = count
        metadata_evidence[split] = {
            "metadata_sha256": metadata["metadata_sha256"],
            "document_count": count,
        }
    return {
        "manifest_sha256": stored_hash,
        "document_counts": counts,
        "split_evidence": metadata_evidence,
        "storage_format": "chunked_prebuilt_v1",
        "build_identity_sha256": manifest["build_identity_sha256"],
    }


def _check_dataset_manifest(cfg: dict[str, Any]) -> dict[str, Any]:
    dataset_cfg = cfg["dataset"]
    normalized = Path(dataset_cfg["normalized_dir"])
    normalized = require_managed_path(
        normalized, normalized, kind="directory", allow_missing=False
    )
    manifest = _read_json(normalized / "manifest.json")
    revision = dataset_cfg["revision"]
    if isinstance(revision, str) and revision.startswith("registry:"):
        registry_path = Path(dataset_cfg["source_registry_path"])
        registry = load_source_registry(registry_path)
        registry_sources = registry.by_id
        manifest_sources = manifest.get("sources")
        if not isinstance(manifest_sources, list) or not manifest_sources:
            raise ValueError("Registry-backed dataset manifest requires sources")
        for source in manifest_sources:
            source_id = source.get("id") if isinstance(source, dict) else None
            if source_id not in registry_sources:
                raise ValueError(f"Dataset manifest has unknown source {source_id!r}")
            expected = registry_sources[source_id]
            if source.get("revision") != expected.revision:
                raise ValueError(
                    f"Dataset source {source_id!r} revision does not match registry"
                )
            if source.get("role") != expected.role or expected.role not in PRETRAIN_ROLES:
                raise ValueError(
                    f"Dataset source {source_id!r} is not approved for pretraining"
                )
        if manifest.get("complete") is not True:
            raise ValueError("Registry-backed dataset manifest is not complete")
    elif manifest.get("version_or_commit") != revision:
        raise ValueError(
            "Dataset revision mismatch: "
            f"manifest={manifest.get('version_or_commit')} config={revision}"
        )
    stored_hash = manifest.get("manifest_sha256")
    hash_payload = dict(manifest)
    hash_payload.pop("manifest_sha256", None)
    if stored_hash != sha256_json(hash_payload):
        raise ValueError("Dataset manifest_sha256 does not match manifest content")
    if manifest.get("storage_format") == "chunked_prebuilt_v1":
        return _check_chunked_dataset_manifest(
            cfg, manifest, normalized, str(stored_hash)
        )
    counts = {}
    split_evidence = {}
    for split in _configured_data_splits(dataset_cfg):
        observed = _normalized_split_evidence(normalized / f"{split}.jsonl")
        expected = manifest["split_stats"][split]
        for field_name, observed_value in observed.items():
            if field_name not in expected:
                raise ValueError(f"{split} manifest is missing {field_name} evidence")
            if expected[field_name] != observed_value:
                raise ValueError(
                    f"{split} {field_name} mismatch: "
                    f"file={observed_value} manifest={expected[field_name]}"
                )
        if observed["document_count"] < 1:
            raise ValueError(f"{split} has no normalized documents")
        counts[split] = observed["document_count"]
        split_evidence[split] = observed
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
    return {
        "manifest_sha256": stored_hash,
        "document_counts": counts,
        "split_evidence": split_evidence,
    }


def _check_dataset_overlap(cfg: dict[str, Any]) -> dict[str, Any]:
    dataset_cfg = cfg["dataset"]
    normalized = Path(dataset_cfg["normalized_dir"])
    normalized = require_managed_path(
        normalized, normalized, kind="directory", allow_missing=False
    )
    manifest = _read_json(normalized / "manifest.json")
    if manifest.get("storage_format") == "chunked_prebuilt_v1":
        audits = manifest.get("audits")
        if not isinstance(audits, dict):
            raise ValueError("Chunked corpus manifest has no audit evidence")
        _path, overlap = _verified_json_artifact(
            normalized,
            audits.get("overlap_audit"),
            internal_hash_field="audit_sha256",
        )
        if overlap.get("passed") is not True or overlap.get("overlap_count") != 0:
            raise ValueError("Signed overlap audit did not prove zero overlap")
        return {
            "overlap_count": 0,
            "validation_hash_count": int(overlap.get("validation_hash_count", 0)),
            "method": overlap.get("method"),
        }
    validation_split = effective_validation_split(dataset_cfg)
    validation_hashes = {
        row["text_sha256"]
        for _, row in _nonempty_jsonl_rows(normalized / f"{validation_split}.jsonl")
    }
    overlaps = []
    for split in _configured_data_splits(dataset_cfg):
        if split == validation_split:
            continue
        for _, row in _nonempty_jsonl_rows(normalized / f"{split}.jsonl"):
            if row["text_sha256"] in validation_hashes:
                overlaps.append(row["text_sha256"])
                if len(overlaps) == 5:
                    break
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
    tokenizer_metadata = load_tokenizer_metadata(cfg["tokenizer"]["output_dir"])
    eos_id = tokenizer.token_to_id("<|eos|>")
    if eos_id is None:
        raise ValueError("Tokenizer has no <|eos|> ID")
    details = {}
    dataset_cfg = cfg["dataset"]
    sharding_cfg = cfg["sharding"]
    output_root = Path(sharding_cfg["output_dir"])
    output_root = require_managed_path(
        output_root, output_root, kind="directory", allow_missing=False
    )
    normalized_root = Path(dataset_cfg["normalized_dir"])
    normalized_root = require_managed_path(
        normalized_root, normalized_root, kind="directory", allow_missing=False
    )
    manifest = _read_json(normalized_root / "manifest.json")
    is_chunked = manifest.get("storage_format") == "chunked_prebuilt_v1"
    chunked_metadata = manifest.get("split_metadata")
    if is_chunked and not isinstance(chunked_metadata, dict):
        raise ValueError("Chunked corpus manifest has no split metadata")
    for split in _configured_data_splits(dataset_cfg):
        metadata_path = metadata_path_for_split(sharding_cfg["output_dir"], split)
        finalized_artifact = chunked_metadata.get(split) if is_chunked else None
        if is_chunked and not isinstance(finalized_artifact, dict):
            raise ValueError(
                f"Chunked corpus manifest has no metadata for split {split!r}"
            )
        metadata_path, metadata = load_verified_shard_metadata(
            metadata_path,
            metadata_root=output_root,
            finalized_root=normalized_root
            if finalized_artifact is not None
            else None,
            finalized_artifact=finalized_artifact,
            require_internal_fingerprint=True,
        )
        expected_provenance = {
            "split": split,
            "tokenizer_sha256": tokenizer_metadata["tokenizer_sha256"],
            "dtype": sharding_cfg["dtype"],
            "append_eos": sharding_cfg["append_eos"],
            "shard_size_tokens": sharding_cfg["shard_size_tokens"],
            "total_documents": manifest["split_stats"][split]["document_count"],
        }
        for field_name, expected_value in expected_provenance.items():
            observed_value = metadata.get(field_name)
            if type(observed_value) is not type(expected_value) or observed_value != expected_value:
                raise ValueError(
                    f"{split} shard metadata {field_name} mismatch: "
                    f"observed={observed_value!r} expected={expected_value!r}"
                )
        dtype = dtype_map[metadata["dtype"]]
        total_tokens = 0
        eos_count = 0
        maximum_id = -1
        shard_files = []
        for shard in metadata["shards"]:
            try:
                path = resolve_shard_artifact_path(
                    metadata_path, shard.get("path"), shard_root=output_root
                )
            except ValueError as exc:
                raise ValueError(
                    f"{split} shard path is outside sharding.output_dir or unsafe: "
                    f"{shard.get('path')!r}"
                ) from exc
            expected_tokens = int(shard["num_tokens"])
            expected_bytes = expected_tokens * dtype.itemsize
            if not path.is_file() or path.stat().st_size != expected_bytes:
                observed = path.stat().st_size if path.exists() else "missing"
                raise ValueError(
                    f"{split} shard size mismatch for {path}: "
                    f"observed={observed} expected={expected_bytes}"
                )
            if "byte_size" in shard and (
                type(shard["byte_size"]) is not int
                or shard["byte_size"] != expected_bytes
            ):
                raise ValueError(
                    f"{split} shard byte_size mismatch for {path}: "
                    f"observed={shard['byte_size']!r} expected={expected_bytes}"
                )
            if sha256_file(path) != shard["sha256"]:
                raise ValueError(f"{split} shard SHA-256 mismatch: {path}")
            shard_files.append(
                {
                    "path": shard["path"],
                    "byte_size": expected_bytes,
                    "num_tokens": expected_tokens,
                    "sha256": shard["sha256"],
                }
            )
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
            "metadata_sha256": metadata["metadata_sha256"],
            "shard_files_sha256": sha256_json(shard_files),
        }
    return details


def _check_output_storage(cfg: dict[str, Any], min_free_disk_gb: float) -> dict[str, Any]:
    output_dir = Path(cfg["run"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=".preflight-",
        dir=output_dir,
    ) as probe:
        probe.write("ok\n")
        probe.flush()
    free_gb = shutil.disk_usage(output_dir).free / (1024**3)
    if free_gb < min_free_disk_gb:
        raise ValueError(
            f"Insufficient free disk: observed={free_gb:.2f} GiB "
            f"required={min_free_disk_gb:.2f} GiB"
        )
    return {"output_dir": str(output_dir), "free_disk_gb": free_gb}


def classify_training_gpu(device_name: str, total_memory_gb: float) -> dict[str, Any]:
    if not isinstance(device_name, str) or not device_name.strip():
        raise ValueError("CUDA device name must be a non-empty string")
    memory_gb = float(total_memory_gb)
    if not math.isfinite(memory_gb) or memory_gb <= 0:
        raise ValueError(f"CUDA GPU memory must be positive; observed {memory_gb!r} GiB")

    for profile, name_fragment, minimum_memory_gb, high_throughput in SUPPORTED_TRAINING_GPUS:
        if name_fragment not in device_name:
            continue
        if memory_gb < minimum_memory_gb:
            raise ValueError(
                f"{device_name} requires at least {minimum_memory_gb:.1f} GiB for the "
                f"{profile} training profile; observed {memory_gb:.2f} GiB"
            )
        return {
            "profile": profile,
            "device_name": device_name,
            "total_memory_gb": memory_gb,
            "high_throughput": high_throughput,
        }

    supported = ", ".join(spec[1] for spec in SUPPORTED_TRAINING_GPUS)
    raise ValueError(f"Unsupported CUDA GPU {device_name!r}; supported GPUs: {supported}")


def _check_device(
    require_t4: bool,
    require_supported_gpu: bool = False,
) -> dict[str, Any]:
    if require_t4 and require_supported_gpu:
        raise ValueError("require_t4 and require_supported_gpu are mutually exclusive")
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
    details = {
        "cuda_available": cuda,
        "device_name": device_name,
        "total_memory_gb": total_memory_gb,
    }
    if require_supported_gpu:
        if not cuda:
            raise ValueError("A supported CUDA GPU is required; CUDA is unavailable")
        details.update(classify_training_gpu(device_name, total_memory_gb))
    return details


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


def _environment_from_device_check(device_check: PreflightCheck | None) -> dict[str, Any]:
    environment = {
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "cuda_version": torch.version.cuda,
    }
    if device_check is not None and device_check.status == "pass":
        environment.update(
            {
                "cuda_available": device_check.details["cuda_available"],
                "device_name": device_check.details["device_name"],
            }
        )
    else:
        environment.update(
            {
                "cuda_available": None,
                "device_name": "unavailable",
                "device_probe_error": (
                    device_check.message
                    if device_check is not None
                    else "not probed because configuration could not be loaded"
                ),
            }
        )
    return environment


def build_config_failure_report(exc: Exception) -> dict[str, Any]:
    config_message = f"{type(exc).__name__}: {exc}"
    checks = [PreflightCheck("config", "fail", config_message)]
    checks.extend(
        PreflightCheck(
            name,
            "fail",
            "not run because configuration could not be loaded",
        )
        for name in CHECK_IDS[1:]
    )
    return {
        "status": "fail",
        "environment": _environment_from_device_check(None),
        "checks": [asdict(check) for check in checks],
    }


def write_preflight_report(report: dict[str, Any], report_path: str | Path) -> Path:
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_preflight_report(
    cfg: dict[str, Any],
    require_t4: bool,
    min_free_disk_gb: float,
    require_supported_gpu: bool = False,
) -> dict[str, Any]:
    check_functions = dict(
        config=lambda: _check_config(cfg),
        source_revision=lambda: _check_source_revision(cfg),
        dataset_manifest=lambda: _check_dataset_manifest(cfg),
        dataset_overlap=lambda: _check_dataset_overlap(cfg),
        tokenizer=lambda: _check_tokenizer(cfg),
        shards=lambda: _check_shards(cfg),
        output_storage=lambda: _check_output_storage(cfg, min_free_disk_gb),
        device=lambda: _check_device(require_t4, require_supported_gpu),
        training_math=lambda: _check_training_math(cfg),
        checkpoint=lambda: _check_checkpoint(cfg),
    )
    checks = [_run_check(name, check_functions[name]) for name in CHECK_IDS]
    device_check = next(check for check in checks if check.name == "device")
    return {
        "status": "pass" if all(check.status == "pass" for check in checks) else "fail",
        "environment": _environment_from_device_check(device_check),
        "checks": [asdict(check) for check in checks],
    }


def run_preflight(
    cfg: dict[str, Any],
    report_path: str | Path,
    require_t4: bool = False,
    min_free_disk_gb: float = 0.0,
    require_supported_gpu: bool = False,
) -> dict[str, Any]:
    report = build_preflight_report(
        cfg,
        require_t4,
        min_free_disk_gb,
        require_supported_gpu=require_supported_gpu,
    )
    write_preflight_report(report, report_path)
    if report["status"] != "pass":
        failures = [check for check in report["checks"] if check["status"] == "fail"]
        raise RuntimeError(
            "Preflight failed: "
            + "; ".join(f"{check['name']}: {check['message']}" for check in failures)
        )
    return report
