from __future__ import annotations

import math
import stat
from pathlib import Path
from typing import Sequence

from audio_mcp.audition.config import SUPPORTED_EXPORT_EXTENSIONS
from audio_mcp.audition.errors import AuditionError, ErrorCode


READ_EXTENSIONS = frozenset(
    {".wav", ".wave", ".aif", ".aiff", ".mp3", ".flac", ".sesx"}
)


def _path_error(message: str) -> AuditionError:
    return AuditionError(ErrorCode.PATH_NOT_ALLOWED, message)


def _canonical_roots(roots: Sequence[Path]) -> tuple[Path, ...]:
    canonical: list[Path] = []
    for root in roots:
        try:
            resolved = root.resolve(strict=True)
        except (OSError, RuntimeError):
            raise _path_error("A configured media root is unavailable.") from None
        if not resolved.is_dir():
            raise _path_error("A configured media root is not a directory.")
        canonical.append(resolved)
    return tuple(canonical)


def _raw_absolute_path(path: object) -> Path:
    if not isinstance(path, str) or not path or "\x00" in path:
        raise _path_error("Path must be a non-empty absolute path.")
    candidate = Path(path)
    if not candidate.is_absolute():
        raise _path_error("Path must be absolute.")
    return candidate


def require_confirmation(confirm: object) -> None:
    if confirm is not True:
        raise AuditionError(
            ErrorCode.CONFIRMATION_REQUIRED,
            "This operation requires confirm=true on the same request.",
        )


def validate_read_path(path: str, roots: tuple[Path, ...]) -> Path:
    raw = _raw_absolute_path(path)
    if raw.suffix not in READ_EXTENSIONS:
        raise _path_error("Source file extension is not allowed.")
    try:
        candidate = raw.resolve(strict=True)
        metadata = candidate.stat()
    except (OSError, RuntimeError):
        raise _path_error("Source file is unavailable.") from None
    if not stat.S_ISREG(metadata.st_mode):
        raise _path_error("Source path must identify a regular file.")

    allowed_roots = _canonical_roots(roots)
    if not any(candidate.is_relative_to(root) for root in allowed_roots):
        raise _path_error("Source path is outside configured read roots.")
    return candidate


def validate_write_path(
    path: str,
    roots: tuple[Path, ...],
    extension: str,
) -> Path:
    raw = _raw_absolute_path(path)
    if (
        not isinstance(extension, str)
        or extension not in SUPPORTED_EXPORT_EXTENSIONS
        or raw.suffix != extension
    ):
        raise _path_error("Destination must use the selected export extension.")
    if not raw.name or raw.name in {".", ".."}:
        raise _path_error("Destination filename is invalid.")

    try:
        parent = raw.parent.resolve(strict=True)
    except (OSError, RuntimeError):
        raise _path_error("Destination parent directory is unavailable.") from None
    if not parent.is_dir():
        raise _path_error("Destination parent must be a directory.")

    allowed_roots = _canonical_roots(roots)
    if not any(parent.is_relative_to(root) for root in allowed_roots):
        raise _path_error("Destination is outside configured write roots.")

    candidate = parent / raw.name
    if candidate.exists() or candidate.is_symlink():
        raise AuditionError(
            ErrorCode.DESTINATION_EXISTS,
            "Destination already exists; choose a new path.",
        )
    return candidate


def validate_favorite(name: str, allowed: tuple[str, ...]) -> str:
    if not isinstance(name, str) or name not in allowed:
        raise AuditionError(
            ErrorCode.OPERATION_NOT_ALLOWED,
            "Favorite is not in the configured allowlist.",
        )
    return name


def validate_time(value: float, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        label = name if isinstance(name, str) and name else "time"
        raise AuditionError(
            ErrorCode.INVALID_ARGUMENT,
            f"{label} must be a non-negative finite number.",
        )
    return float(value)
