from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SECRET_PATTERN = re.compile(r"[0-9a-f]{64}")
MAX_CONFIG_BYTES = 65_536
SUPPORTED_EXPORT_EXTENSIONS = frozenset(
    {".wav", ".wave", ".aif", ".aiff", ".mp3", ".flac"}
)


class ConfigError(ValueError):
    """Raised when the local Audition bridge configuration is unsafe."""


@dataclass(frozen=True)
class AuditionConfig:
    secret: str
    read_roots: tuple[Path, ...]
    write_roots: tuple[Path, ...]
    host: str
    port: int
    favorites: tuple[str, ...]
    export_presets: dict[str, str]


def default_config_path() -> Path:
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "audio-mcp"
        / "audition.json"
    )


def _validate_root(value: object) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ConfigError("Configured media roots must be existing directories.")
    try:
        root = Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise ConfigError(
            "Configured media roots must be existing directories."
        ) from None
    if not root.is_dir():
        raise ConfigError("Configured media roots must be existing directories.")

    try:
        home = Path.home().resolve(strict=True)
    except OSError:
        home = Path.home().resolve()
    if root == Path(root.anchor) or root == home or os.path.ismount(root):
        raise ConfigError(
            "Filesystem, volume, and user-home roots are forbidden."
        )
    return root


def _validate_roots(raw: object) -> tuple[Path, ...]:
    if not isinstance(raw, list):
        raise ConfigError("Configured media roots must be JSON arrays.")
    roots = tuple(_validate_root(value) for value in raw)
    if len(set(roots)) != len(roots):
        raise ConfigError("Configured media roots must not contain duplicates.")
    return roots


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        metadata = path.lstat()
    except OSError:
        raise ConfigError("Audition configuration file is unavailable.") from None
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise ConfigError("Audition configuration must be a regular file.")
    if metadata.st_uid != os.getuid():
        raise ConfigError("Audition configuration must be owned by the current user.")
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise ConfigError("Audition configuration must have mode 0600.")
    if metadata.st_size > MAX_CONFIG_BYTES:
        raise ConfigError(
            "Audition configuration exceeds the 65536-byte size limit."
        )

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ConfigError("Audition configuration must contain valid JSON.") from None
    if not isinstance(raw, dict):
        raise ConfigError("Audition configuration must be a JSON object.")
    return raw


def load_config(path: Path | None = None) -> AuditionConfig:
    configured_path = os.environ.get("AUDIO_MCP_AUDITION_CONFIG")
    selected = path or (
        Path(configured_path) if configured_path else default_config_path()
    )
    raw = _load_json_object(selected)

    secret = raw.get("secret")
    if not isinstance(secret, str) or SECRET_PATTERN.fullmatch(secret) is None:
        raise ConfigError(
            "Audition configuration secret must be 64 lowercase hex characters."
        )
    if raw.get("host") != "127.0.0.1":
        raise ConfigError("Audition bridge host must be exactly 127.0.0.1.")

    port = raw.get("port")
    if (
        isinstance(port, bool)
        or not isinstance(port, int)
        or not 1024 <= port <= 65535
    ):
        raise ConfigError("Audition bridge port must be between 1024 and 65535.")

    favorites = raw.get("favorites", [])
    if not isinstance(favorites, list) or not all(
        isinstance(value, str) and 0 < len(value) <= 256 for value in favorites
    ):
        raise ConfigError("Favorite names must be non-empty strings.")
    if len(set(favorites)) != len(favorites):
        raise ConfigError("Favorite names must not contain duplicates.")

    export_presets = raw.get("export_presets", {})
    if not isinstance(export_presets, dict) or not all(
        isinstance(name, str)
        and 0 < len(name) <= 128
        and isinstance(extension, str)
        and extension in SUPPORTED_EXPORT_EXTENSIONS
        for name, extension in export_presets.items()
    ):
        raise ConfigError(
            "Export presets must map names to supported lowercase file extensions."
        )

    return AuditionConfig(
        secret=secret,
        read_roots=_validate_roots(raw.get("read_roots", [])),
        write_roots=_validate_roots(raw.get("write_roots", [])),
        host="127.0.0.1",
        port=port,
        favorites=tuple(favorites),
        export_presets=dict(export_presets),
    )
