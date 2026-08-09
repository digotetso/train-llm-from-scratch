"""Fail-closed helpers for files managed below an approved filesystem root."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import IO


def _absolute(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(Path(path).expanduser())))


def require_managed_path(
    root: str | Path,
    target: str | Path,
    *,
    kind: str | None = None,
    allow_missing: bool = True,
) -> Path:
    """Validate that every existing component is real and remains below ``root``.

    ``kind`` may be ``"file"`` or ``"directory"``.  The returned path is
    lexical and absolute; callers must not replace it with a separately resolved
    user-supplied path after validation.
    """

    managed_root = _absolute(root)
    managed_target = _absolute(target)
    try:
        relative = managed_target.relative_to(managed_root)
    except ValueError as error:
        raise ValueError(
            f"Managed path escapes approved root {managed_root}: {managed_target}"
        ) from error

    components = (managed_root, *(managed_root / part for part in _prefixes(relative)))
    for index, component in enumerate(components):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"Managed path contains a symbolic link: {component}")
        if index < len(components) - 1 and not stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"Managed path ancestor must be a directory: {component}")
        resolved = component.resolve(strict=True)
        resolved_root = managed_root.resolve(strict=True) if managed_root.exists() else None
        if resolved_root is not None and (
            resolved != resolved_root and not resolved.is_relative_to(resolved_root)
        ):
            raise ValueError(f"Managed path resolves outside approved root: {component}")

    exists = managed_target.exists() or managed_target.is_symlink()
    if not exists:
        if not allow_missing:
            raise ValueError(f"Managed path does not exist: {managed_target}")
        return managed_target
    metadata = managed_target.lstat()
    if stat.S_ISLNK(metadata.st_mode):
        raise ValueError(f"Managed path contains a symbolic link: {managed_target}")
    if kind == "file" and not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"Managed path must be a real file: {managed_target}")
    if kind == "directory" and not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"Managed path must be a real directory: {managed_target}")
    return managed_target


def _prefixes(relative: Path):
    current = Path()
    for part in relative.parts:
        current /= part
        yield current


def open_exclusive_nofollow(
    path: str | Path,
    mode: str,
    *,
    encoding: str | None = None,
) -> IO:
    """Create a new regular file without following a final-component symlink."""

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(Path(path), flags, 0o600)
    if "b" in mode:
        return os.fdopen(descriptor, mode)
    return os.fdopen(descriptor, mode, encoding=encoding)
