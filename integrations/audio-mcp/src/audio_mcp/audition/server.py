from __future__ import annotations

import json
import sys
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Protocol

from mcp.server.fastmcp import FastMCP
from pydantic import StrictBool, StrictInt

from audio_mcp.audition.bridge import AuditionBridge
from audio_mcp.audition.config import AuditionConfig, ConfigError, load_config
from audio_mcp.audition.errors import AuditionError, ErrorCode
from audio_mcp.audition.service import AuditionService, Bridge


class ManagedBridge(Bridge, Protocol):
    async def start(self) -> None: ...

    async def close(self) -> None: ...


def _write_log(record: dict[str, object]) -> None:
    print(
        json.dumps(record, separators=(",", ":"), sort_keys=True),
        file=sys.stderr,
        flush=True,
    )


def create_server(
    config: AuditionConfig,
    bridge: ManagedBridge | None = None,
) -> FastMCP:
    active_bridge = bridge or AuditionBridge(config)
    service = AuditionService(config, active_bridge)

    @asynccontextmanager
    async def lifespan(_: FastMCP) -> AsyncIterator[dict[str, object]]:
        await active_bridge.start()
        try:
            yield {"bridge": active_bridge, "service": service}
        finally:
            await active_bridge.close()

    mcp = FastMCP(
        "Adobe Audition",
        instructions=(
            "Local, confirmation-gated Adobe Audition control. "
            "Do not retry side-effecting tools automatically."
        ),
        lifespan=lifespan,
        log_level="WARNING",
    )

    async def invoke(
        operation: str,
        call: Callable[[], Awaitable[dict[str, object]]],
        *,
        confirmation_required: bool = False,
        confirmation_present: bool = False,
    ) -> dict[str, object]:
        request_id = uuid.uuid4().hex
        started = time.monotonic()
        base_log: dict[str, object] = {
            "request_id": request_id,
            "operation": operation,
            "confirmation_required": confirmation_required,
            "confirmation_present": confirmation_present,
        }
        try:
            result = await call()
        except AuditionError as error:
            _write_log(
                {
                    **base_log,
                    "duration_ms": round(
                        (time.monotonic() - started) * 1000,
                        3,
                    ),
                    "outcome": "error",
                    "error_code": error.code.value,
                }
            )
            return {
                "ok": False,
                "code": error.code.value,
                "message": str(error),
                "retryable": error.retryable,
                "request_id": request_id,
            }
        except Exception:
            _write_log(
                {
                    **base_log,
                    "duration_ms": round(
                        (time.monotonic() - started) * 1000,
                        3,
                    ),
                    "outcome": "error",
                    "error_code": ErrorCode.APPLICATION_ERROR.value,
                }
            )
            return {
                "ok": False,
                "code": ErrorCode.APPLICATION_ERROR.value,
                "message": (
                    "Unexpected Audition integration failure. "
                    f"Reference request_id={request_id}."
                ),
                "retryable": False,
                "request_id": request_id,
            }

        application_version = _application_version(result)
        record = {
            **base_log,
            "duration_ms": round((time.monotonic() - started) * 1000, 3),
            "outcome": "success",
            "error_code": None,
        }
        if application_version is not None:
            record["application_version"] = application_version
        _write_log(record)
        return result

    @mcp.tool()
    async def audition_get_status() -> dict[str, object]:
        """Report Audition application, document, and transport status."""
        return await invoke("get_status", service.get_status)

    @mcp.tool()
    async def audition_get_document() -> dict[str, object]:
        """Report metadata for the active Audition document or session."""
        return await invoke("get_document", service.get_document)

    @mcp.tool()
    async def audition_get_selection() -> dict[str, object]:
        """Report the active playhead and time selection."""
        return await invoke("get_selection", service.get_selection)

    @mcp.tool()
    async def audition_set_playhead(seconds: float) -> dict[str, object]:
        """Move the playhead to a non-negative time in seconds."""
        return await invoke(
            "set_playhead",
            lambda: service.set_playhead(seconds),
        )

    @mcp.tool()
    async def audition_set_selection(
        start_seconds: float,
        end_seconds: float,
    ) -> dict[str, object]:
        """Set a time selection whose end is greater than its start."""
        return await invoke(
            "set_selection",
            lambda: service.set_selection(start_seconds, end_seconds),
        )

    @mcp.tool()
    async def audition_play() -> dict[str, object]:
        """Start Audition playback."""
        return await invoke("play", service.play)

    @mcp.tool()
    async def audition_pause() -> dict[str, object]:
        """Pause Audition playback."""
        return await invoke("pause", service.pause)

    @mcp.tool()
    async def audition_stop() -> dict[str, object]:
        """Stop Audition playback or recording."""
        return await invoke("stop", service.stop)

    @mcp.tool()
    async def audition_record(confirm: StrictBool) -> dict[str, object]:
        """Begin recording; requires literal confirm=true."""
        return await invoke(
            "record",
            lambda: service.record(confirm),
            confirmation_required=True,
            confirmation_present=confirm is True,
        )

    @mcp.tool()
    async def audition_open(
        path: str,
        confirm: StrictBool,
    ) -> dict[str, object]:
        """Open an allowlisted existing media or session file."""
        return await invoke(
            "open",
            lambda: service.open(path, confirm),
            confirmation_required=True,
            confirmation_present=confirm is True,
        )

    @mcp.tool(name="audition_import")
    async def audition_import_media(
        path: str,
        track_index: StrictInt,
        confirm: StrictBool,
    ) -> dict[str, object]:
        """Import allowlisted media into a validated multitrack index."""
        return await invoke(
            "import_media",
            lambda: service.import_media(path, track_index, confirm),
            confirmation_required=True,
            confirmation_present=confirm is True,
        )

    @mcp.tool()
    async def audition_save(confirm: StrictBool) -> dict[str, object]:
        """Save the active document in place; requires literal confirm=true."""
        return await invoke(
            "save",
            lambda: service.save(confirm),
            confirmation_required=True,
            confirmation_present=confirm is True,
        )

    @mcp.tool()
    async def audition_export(
        path: str,
        preset: str,
        confirm: StrictBool,
    ) -> dict[str, object]:
        """Export with an allowlisted preset to a new scoped path."""
        return await invoke(
            "export",
            lambda: service.export(path, preset, confirm),
            confirmation_required=True,
            confirmation_present=confirm is True,
        )

    @mcp.tool()
    async def audition_list_effects() -> dict[str, object]:
        """List exact favorite names allowed by local configuration."""
        return await invoke("list_effects", service.list_effects)

    @mcp.tool()
    async def audition_apply_effect(
        favorite: str,
        confirm: StrictBool,
    ) -> dict[str, object]:
        """Apply one allowlisted favorite; requires literal confirm=true."""
        return await invoke(
            "apply_favorite",
            lambda: service.apply_effect(favorite, confirm),
            confirmation_required=True,
            confirmation_present=confirm is True,
        )

    return mcp


def _application_version(result: dict[str, object]) -> str | None:
    direct = result.get("version")
    if isinstance(direct, (str, int, float)) and not isinstance(direct, bool):
        return str(direct)
    application = result.get("application")
    if isinstance(application, dict):
        nested = application.get("version")
        if isinstance(nested, (str, int, float)) and not isinstance(
            nested, bool
        ):
            return str(nested)
    return None


def main() -> None:
    try:
        config = load_config()
    except ConfigError as error:
        _write_log(
            {
                "outcome": "startup_error",
                "error_code": "CONFIGURATION_ERROR",
                "message": str(error),
            }
        )
        raise SystemExit(2) from None
    create_server(config).run(transport="stdio")


if __name__ == "__main__":
    main()
