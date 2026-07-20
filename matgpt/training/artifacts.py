from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any

import torch

from matgpt.config import config_to_yaml


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _write_if_missing_or_equal(path: Path, text: str, label: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise ValueError(f"Existing {label} conflicts with the current run: {path}")
        return
    _atomic_write_text(path, text)


def _validate_if_exists(path: Path, text: str, label: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != text:
        raise ValueError(f"Existing {label} conflicts with the current run: {path}")


def _json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _write_json_if_missing(path: Path, payload: dict[str, Any]) -> None:
    if not path.exists():
        _atomic_write_text(path, _json_text(payload))


def _fingerprints(extra: dict[str, Any]) -> dict[str, Any]:
    return {
        "config_sha256": extra["config_sha256"],
        "tokenizer_sha256": extra["tokenizer_sha256"],
        "dataset_manifest_hash": extra["dataset_manifest_hash"],
        "git_commit": extra["git_commit"],
        "parameter_count": extra["parameter_count"],
    }


_TRAINING_IDENTITY_FIELDS = (
    "config_sha256",
    "tokenizer_sha256",
    "dataset_manifest_hash",
    "parameter_count",
)


def _validate_fingerprints_if_exists(
    path: Path,
    expected: dict[str, Any],
) -> None:
    if not path.exists():
        return
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Existing fingerprints are invalid JSON: {path}") from exc
    if not isinstance(stored, dict):
        raise ValueError(f"Existing fingerprints must contain a JSON object: {path}")
    for field in (*_TRAINING_IDENTITY_FIELDS, "git_commit"):
        if field not in stored:
            raise ValueError(f"Existing fingerprints are missing {field}: {path}")
    for field in _TRAINING_IDENTITY_FIELDS:
        if stored[field] != expected[field]:
            raise ValueError(
                f"Existing fingerprints {field} conflicts with the current run: {path}"
            )


def validate_run_artifacts(
    run_dir: Path,
    cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    run_dir = Path(run_dir)
    _validate_if_exists(
        run_dir / "config.snapshot.yaml",
        config_to_yaml(cfg),
        "configuration snapshot",
    )
    _validate_fingerprints_if_exists(
        run_dir / "fingerprints.json",
        _fingerprints(extra),
    )


def write_run_artifacts(
    run_dir: Path,
    cfg: dict[str, Any],
    extra: dict[str, Any],
    device: torch.device,
) -> dict[str, str]:
    run_dir = Path(run_dir)
    validate_run_artifacts(run_dir, cfg, extra)
    config_text = config_to_yaml(cfg)
    _write_if_missing_or_equal(run_dir / "config.snapshot.yaml", config_text, "configuration snapshot")
    environment = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda,
        "device_type": device.type,
        "device_name": torch.cuda.get_device_name(device) if device.type == "cuda" else "cpu",
    }
    _write_json_if_missing(run_dir / "environment.json", environment)
    fingerprints = _fingerprints(extra)
    _write_json_if_missing(run_dir / "fingerprints.json", fingerprints)
    return {
        "config": str(run_dir / "config.snapshot.yaml"),
        "environment": str(run_dir / "environment.json"),
        "fingerprints": str(run_dir / "fingerprints.json"),
    }
