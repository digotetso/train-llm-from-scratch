from __future__ import annotations

from typing import Any, Protocol

from audio_mcp.audition.config import AuditionConfig
from audio_mcp.audition.errors import AuditionError, ErrorCode
from audio_mcp.audition.policy import (
    require_confirmation,
    validate_favorite,
    validate_read_path,
    validate_time,
    validate_write_path,
)


class Bridge(Protocol):
    @property
    def connected(self) -> bool: ...

    async def request(
        self,
        operation: str,
        arguments: dict[str, Any],
        timeout_ms: int = 5000,
    ) -> dict[str, Any]: ...


class AuditionService:
    def __init__(self, config: AuditionConfig, bridge: Bridge) -> None:
        self._config = config
        self._bridge = bridge

    async def get_status(self) -> dict[str, object]:
        return await self._bridge.request("get_status", {})

    async def get_document(self) -> dict[str, object]:
        return await self._bridge.request("get_document", {})

    async def get_selection(self) -> dict[str, object]:
        return await self._bridge.request("get_selection", {})

    async def set_playhead(self, seconds: float) -> dict[str, object]:
        position = validate_time(seconds, "seconds")
        return await self._bridge.request(
            "set_playhead",
            {"seconds": position},
        )

    async def set_selection(
        self,
        start_seconds: float,
        end_seconds: float,
    ) -> dict[str, object]:
        start = validate_time(start_seconds, "start_seconds")
        end = validate_time(end_seconds, "end_seconds")
        if end <= start:
            raise AuditionError(
                ErrorCode.INVALID_ARGUMENT,
                "end_seconds must be greater than start_seconds.",
            )
        return await self._bridge.request(
            "set_selection",
            {
                "start_seconds": start,
                "end_seconds": end,
            },
        )

    async def play(self) -> dict[str, object]:
        return await self._bridge.request("play", {})

    async def pause(self) -> dict[str, object]:
        return await self._bridge.request("pause", {})

    async def stop(self) -> dict[str, object]:
        return await self._bridge.request("stop", {})

    async def record(self, confirm: bool) -> dict[str, object]:
        require_confirmation(confirm)
        return await self._bridge.request("record", {})

    async def open(self, path: str, confirm: bool) -> dict[str, object]:
        require_confirmation(confirm)
        source = validate_read_path(path, self._config.read_roots)
        return await self._bridge.request(
            "open",
            {"path": str(source)},
        )

    async def import_media(
        self,
        path: str,
        track_index: int,
        confirm: bool,
    ) -> dict[str, object]:
        require_confirmation(confirm)
        if (
            isinstance(track_index, bool)
            or not isinstance(track_index, int)
            or not 0 <= track_index <= 127
        ):
            raise AuditionError(
                ErrorCode.INVALID_ARGUMENT,
                "track_index must be an integer from 0 to 127.",
            )
        source = validate_read_path(path, self._config.read_roots)
        if source.suffix == ".sesx":
            raise AuditionError(
                ErrorCode.OPERATION_NOT_ALLOWED,
                "Session files may be opened but cannot be imported as media.",
            )
        return await self._bridge.request(
            "import_media",
            {
                "path": str(source),
                "track_index": track_index,
            },
        )

    async def save(self, confirm: bool) -> dict[str, object]:
        require_confirmation(confirm)
        return await self._bridge.request("save", {})

    async def export(
        self,
        path: str,
        preset: str,
        confirm: bool,
    ) -> dict[str, object]:
        require_confirmation(confirm)
        if not isinstance(preset, str) or preset not in self._config.export_presets:
            raise AuditionError(
                ErrorCode.OPERATION_NOT_ALLOWED,
                "Export preset is not in the configured allowlist.",
            )
        destination = validate_write_path(
            path,
            self._config.write_roots,
            self._config.export_presets[preset],
        )
        return await self._bridge.request(
            "export",
            {"path": str(destination)},
            timeout_ms=30_000,
        )

    async def list_effects(self) -> dict[str, object]:
        return {"effects": list(self._config.favorites)}

    async def apply_effect(
        self,
        favorite: str,
        confirm: bool,
    ) -> dict[str, object]:
        require_confirmation(confirm)
        if not self._config.favorites:
            raise AuditionError(
                ErrorCode.UNSUPPORTED_OPERATION,
                "No effect favorites have been safely validated for this installation.",
            )
        selected = validate_favorite(favorite, self._config.favorites)
        return await self._bridge.request(
            "apply_favorite",
            {"favorite": selected},
            timeout_ms=30_000,
        )
