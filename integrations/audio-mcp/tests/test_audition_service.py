import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from audio_mcp.audition.errors import AuditionError, ErrorCode
from audio_mcp.audition.service import AuditionService


class FakeBridge:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any], int]] = []
        self.connected = True

    async def request(
        self,
        operation: str,
        arguments: dict[str, Any],
        timeout_ms: int = 5000,
    ) -> dict[str, Any]:
        self.calls.append((operation, arguments, timeout_ms))
        return {"operation": operation}


@pytest.mark.parametrize(
    ("method_name", "arguments", "operation", "bridge_arguments"),
    [
        ("get_status", (), "get_status", {}),
        ("get_document", (), "get_document", {}),
        ("get_selection", (), "get_selection", {}),
        ("set_playhead", (1.25,), "set_playhead", {"seconds": 1.25}),
        (
            "set_selection",
            (0.25, 1.5),
            "set_selection",
            {"start_seconds": 0.25, "end_seconds": 1.5},
        ),
        ("play", (), "play", {}),
        ("pause", (), "pause", {}),
        ("stop", (), "stop", {}),
        ("record", (True,), "record", {}),
        ("save", (True,), "save", {}),
    ],
)
def test_service_translates_fixed_operations(
    config,
    method_name: str,
    arguments: tuple[object, ...],
    operation: str,
    bridge_arguments: dict[str, object],
) -> None:
    bridge = FakeBridge()
    service = AuditionService(config, bridge)

    result = asyncio.run(getattr(service, method_name)(*arguments))

    assert result == {"operation": operation}
    assert bridge.calls == [(operation, bridge_arguments, 5000)]


def test_open_validates_path_and_confirmation_before_bridge(config) -> None:
    source = config.read_roots[0] / "voice.wav"
    source.write_bytes(b"RIFF")
    bridge = FakeBridge()
    service = AuditionService(config, bridge)

    result = asyncio.run(service.open(str(source), confirm=True))

    assert result == {"operation": "open"}
    assert bridge.calls == [
        ("open", {"path": str(source.resolve())}, 5000)
    ]


def test_import_validates_media_and_track_index(config) -> None:
    source = config.read_roots[0] / "voice.wav"
    source.write_bytes(b"RIFF")
    bridge = FakeBridge()
    service = AuditionService(config, bridge)

    result = asyncio.run(
        service.import_media(str(source), track_index=2, confirm=True)
    )

    assert result == {"operation": "import_media"}
    assert bridge.calls == [
        (
            "import_media",
            {"path": str(source.resolve()), "track_index": 2},
            5000,
        )
    ]


@pytest.mark.parametrize("track_index", [True, -1, 128, 1.5, "1"])
def test_import_rejects_invalid_track_without_bridge(
    config,
    track_index: object,
) -> None:
    source = config.read_roots[0] / "voice.wav"
    source.write_bytes(b"RIFF")
    bridge = FakeBridge()
    service = AuditionService(config, bridge)

    with pytest.raises(AuditionError) as caught:
        asyncio.run(
            service.import_media(
                str(source),
                track_index=track_index,  # type: ignore[arg-type]
                confirm=True,
            )
        )

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
    assert bridge.calls == []


def test_import_rejects_session_file_without_bridge(config) -> None:
    session = config.read_roots[0] / "session.sesx"
    session.write_text("<sesx/>", encoding="utf-8")
    bridge = FakeBridge()
    service = AuditionService(config, bridge)

    with pytest.raises(AuditionError) as caught:
        asyncio.run(
            service.import_media(str(session), track_index=0, confirm=True)
        )

    assert caught.value.code is ErrorCode.OPERATION_NOT_ALLOWED
    assert bridge.calls == []


def test_export_validates_preset_and_destination(config) -> None:
    bridge = FakeBridge()
    service = AuditionService(config, bridge)
    destination = config.write_roots[0] / "mix.wav"

    result = asyncio.run(
        service.export(str(destination), "wav", confirm=True)
    )

    assert result == {"operation": "export"}
    assert bridge.calls == [
        ("export", {"path": str(destination.resolve())}, 30_000)
    ]
    assert not destination.exists()


def test_export_rejects_unknown_preset_without_bridge(config) -> None:
    bridge = FakeBridge()
    service = AuditionService(config, bridge)
    destination = config.write_roots[0] / "mix.wav"

    with pytest.raises(AuditionError) as caught:
        asyncio.run(
            service.export(str(destination), "unknown", confirm=True)
        )

    assert caught.value.code is ErrorCode.OPERATION_NOT_ALLOWED
    assert bridge.calls == []


def test_list_effects_is_local_and_apply_effect_is_fixed(config) -> None:
    bridge = FakeBridge()
    service = AuditionService(config, bridge)

    effects = asyncio.run(service.list_effects())
    result = asyncio.run(
        service.apply_effect("Normalize -3 dB", confirm=True)
    )

    assert effects == {"effects": ["Normalize -3 dB"]}
    assert result == {"operation": "apply_favorite"}
    assert bridge.calls == [
        (
            "apply_favorite",
            {"favorite": "Normalize -3 dB"},
            30_000,
        )
    ]


def test_apply_effect_reports_unsupported_when_allowlist_is_empty(config) -> None:
    empty_config = replace(config, favorites=())
    bridge = FakeBridge()
    service = AuditionService(empty_config, bridge)

    assert asyncio.run(service.list_effects()) == {"effects": []}
    with pytest.raises(AuditionError) as caught:
        asyncio.run(service.apply_effect("anything", confirm=True))

    assert caught.value.code is ErrorCode.UNSUPPORTED_OPERATION
    assert bridge.calls == []


@pytest.mark.parametrize(
    ("method_name", "arguments"),
    [
        ("record", (False,)),
        ("open", ("/not/read.wav", False)),
        ("import_media", ("/not/read.wav", 0, False)),
        ("save", (False,)),
        ("export", ("/not/write.wav", "wav", False)),
        ("apply_effect", ("Normalize -3 dB", False)),
    ],
)
def test_confirmed_operations_reject_without_bridge(
    config,
    method_name: str,
    arguments: tuple[object, ...],
) -> None:
    bridge = FakeBridge()
    service = AuditionService(config, bridge)

    with pytest.raises(AuditionError) as caught:
        asyncio.run(getattr(service, method_name)(*arguments))

    assert caught.value.code is ErrorCode.CONFIRMATION_REQUIRED
    assert bridge.calls == []


def test_set_selection_rejects_reversed_range_without_bridge(config) -> None:
    bridge = FakeBridge()
    service = AuditionService(config, bridge)

    with pytest.raises(AuditionError) as caught:
        asyncio.run(service.set_selection(2.0, 1.0))

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
    assert bridge.calls == []
