"""Immutable checkpoint snapshots and evidence-safe content bindings."""

from __future__ import annotations

import errno
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

from matgpt.config import config_to_yaml
from matgpt.tokenizer.io import load_tokenizer_metadata
from matgpt.utils.hashing import sha256_file, sha256_json, sha256_text


_LABEL_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
_HARD_LINK_UNSUPPORTED = {
    errno.EPERM,
    errno.EXDEV,
    errno.ENOSYS,
    errno.EOPNOTSUPP,
}
_DIRECTORY_FSYNC_UNSUPPORTED = {
    errno.EPERM,
    errno.EINVAL,
    errno.ENOSYS,
    errno.EOPNOTSUPP,
}


def _replace_checkpoint_exclusive(source: Path, destination: Path) -> bool:
    """Reserve a new destination and atomically move the verified staging file."""

    try:
        reservation = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        return False
    os.close(reservation)
    try:
        os.replace(source, destination)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return True


def _fsync_directory(directory: Path) -> None:
    """Persist a directory entry when the backing filesystem supports it."""

    try:
        directory_fd = os.open(directory, os.O_RDONLY)
    except OSError as error:
        if error.errno in _DIRECTORY_FSYNC_UNSUPPORTED:
            return
        raise
    try:
        try:
            os.fsync(directory_fd)
        except OSError as error:
            if error.errno not in _DIRECTORY_FSYNC_UNSUPPORTED:
                raise
    finally:
        os.close(directory_fd)


def training_artifact_identity(cfg: Mapping[str, Any]) -> dict[str, str]:
    """Fingerprint the config, tokenizer, dataset, and build when available."""

    tokenizer_metadata = load_tokenizer_metadata(cfg["tokenizer"]["output_dir"])
    tokenizer_sha256 = tokenizer_metadata.get("tokenizer_sha256")
    if not isinstance(tokenizer_sha256, str) or not tokenizer_sha256:
        raise ValueError("Tokenizer metadata has no content fingerprint.")
    manifest_path = Path(cfg["dataset"]["normalized_dir"]) / "manifest.json"
    identity = {
        "config_sha256": sha256_text(config_to_yaml(dict(cfg))),
        "tokenizer_sha256": tokenizer_sha256,
        "dataset_manifest_sha256": sha256_file(manifest_path),
    }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Dataset manifest is not valid UTF-8 JSON.") from error
    if not isinstance(manifest, dict):
        raise ValueError("Dataset manifest must contain an object.")
    stored_manifest_sha256 = manifest.get("manifest_sha256")
    if stored_manifest_sha256 is not None:
        unsigned = dict(manifest)
        unsigned.pop("manifest_sha256", None)
        if (
            not isinstance(stored_manifest_sha256, str)
            or stored_manifest_sha256 != sha256_json(unsigned)
        ):
            raise ValueError("Dataset manifest content fingerprint is invalid.")
        identity["dataset_manifest_identity_sha256"] = stored_manifest_sha256
        build_identity = manifest.get("build_identity_sha256")
        if isinstance(build_identity, str) and build_identity:
            identity["build_identity_sha256"] = build_identity
        elif manifest.get("version") == 1 and manifest.get("complete") is True:
            identity["build_identity_sha256"] = sha256_json({
                "format": "legacy_telco_prepare_v1",
                "manifest_sha256": stored_manifest_sha256,
                "tokenizer_sha256": tokenizer_sha256,
            })
    return identity


def checkpoint_binding(path: str | Path) -> dict[str, object]:
    """Return the normalized positive-size content identity for a checkpoint."""

    checkpoint = Path(path).expanduser().resolve(strict=True)
    if not checkpoint.is_file():
        raise ValueError(f"Checkpoint is not a regular file: {checkpoint}")
    size = checkpoint.stat().st_size
    if size < 1:
        raise ValueError(f"Checkpoint is a zero-byte file: {checkpoint}")
    return {
        "path": str(checkpoint),
        "size": size,
        "sha256": sha256_file(checkpoint),
    }


def snapshot_checkpoint(
    source: str | Path,
    directory: str | Path,
    *,
    label: str,
) -> dict[str, object]:
    """Copy a checkpoint to a content-named destination without overwriting it."""

    if _LABEL_PATTERN.fullmatch(label) is None:
        raise ValueError("Checkpoint snapshot label is invalid.")
    source_binding = checkpoint_binding(source)
    destination_dir = Path(directory).expanduser().resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{label}-{source_binding['sha256']}.pt"
    if destination.exists():
        try:
            existing = checkpoint_binding(destination)
        except (OSError, ValueError) as error:
            raise ValueError(
                f"Existing immutable checkpoint snapshot is invalid: {destination}"
            ) from error
        if (
            existing["size"] != source_binding["size"]
            or existing["sha256"] != source_binding["sha256"]
        ):
            raise ValueError(
                f"Existing immutable checkpoint snapshot does not match: {destination}"
            )
        return existing

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{label}-", suffix=".staging", dir=destination_dir
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as target, Path(source_binding["path"]).open(
            "rb"
        ) as source_handle:
            shutil.copyfileobj(source_handle, target, length=1024 * 1024)
            target.flush()
            os.fsync(target.fileno())
        copied = checkpoint_binding(temporary)
        if (
            copied["size"] != source_binding["size"]
            or copied["sha256"] != source_binding["sha256"]
        ):
            raise ValueError("Checkpoint changed while creating immutable snapshot.")
        published = False
        try:
            os.link(temporary, destination)
            published = True
        except FileExistsError:
            pass
        except OSError as error:
            if error.errno not in _HARD_LINK_UNSUPPORTED:
                raise
            published = _replace_checkpoint_exclusive(temporary, destination)
        if not published:
            existing = checkpoint_binding(destination)
            if (
                existing["size"] != source_binding["size"]
                or existing["sha256"] != source_binding["sha256"]
            ):
                raise ValueError(
                    f"Existing immutable checkpoint snapshot does not match: {destination}"
                )
        _fsync_directory(destination_dir)
    finally:
        temporary.unlink(missing_ok=True)
    return checkpoint_binding(destination)
