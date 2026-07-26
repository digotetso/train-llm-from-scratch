import os
from pathlib import Path

import pytest

from audio_mcp.audition.errors import AuditionError, ErrorCode
from audio_mcp.audition.policy import (
    require_confirmation,
    validate_favorite,
    validate_read_path,
    validate_time,
    validate_write_path,
)


@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_confirmation_accepts_only_literal_true(value: object) -> None:
    with pytest.raises(AuditionError) as caught:
        require_confirmation(value)

    assert caught.value.code is ErrorCode.CONFIRMATION_REQUIRED


def test_confirmation_accepts_true() -> None:
    require_confirmation(True)


def test_read_path_accepts_supported_regular_file(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    source = root / "voice.wav"
    source.write_bytes(b"RIFF")

    assert validate_read_path(str(source), (root,)) == source.resolve()


def test_read_path_rejects_traversal_and_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    secret = outside / "secret.wav"
    secret.write_bytes(b"RIFF")
    (root / "link.wav").symlink_to(secret)

    for candidate in (root / ".." / "outside" / "secret.wav", root / "link.wav"):
        with pytest.raises(AuditionError) as caught:
            validate_read_path(str(candidate), (root,))
        assert caught.value.code is ErrorCode.PATH_NOT_ALLOWED


@pytest.mark.parametrize("name", ["voice.WAV", "voice.exe", "voice"])
def test_read_path_requires_allowlisted_lowercase_extension(
    tmp_path: Path, name: str
) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    source = root / name
    source.write_bytes(b"data")

    with pytest.raises(AuditionError) as caught:
        validate_read_path(str(source), (root,))

    assert caught.value.code is ErrorCode.PATH_NOT_ALLOWED


def test_read_path_rejects_nul_missing_directory_and_device(
    tmp_path: Path,
) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    fifo = root / "device.wav"
    os.mkfifo(fifo)

    for candidate in (
        f"{root}/bad\x00.wav",
        str(root / "missing.wav"),
        str(root),
        str(fifo),
    ):
        with pytest.raises(AuditionError) as caught:
            validate_read_path(candidate, (root,))
        assert caught.value.code is ErrorCode.PATH_NOT_ALLOWED


def test_empty_roots_disable_read_operations(tmp_path: Path) -> None:
    source = tmp_path / "voice.wav"
    source.write_bytes(b"RIFF")

    with pytest.raises(AuditionError) as caught:
        validate_read_path(str(source), ())

    assert caught.value.code is ErrorCode.PATH_NOT_ALLOWED


def test_write_accepts_new_scoped_destination_without_creating_it(
    tmp_path: Path,
) -> None:
    root = tmp_path / "exports"
    root.mkdir()
    destination = root / "mix.wav"

    result = validate_write_path(str(destination), (root,), ".wav")

    assert result == destination.resolve()
    assert not destination.exists()


def test_write_rejects_existing_destination(tmp_path: Path) -> None:
    root = tmp_path / "exports"
    root.mkdir()
    destination = root / "mix.wav"
    destination.write_bytes(b"existing")

    with pytest.raises(AuditionError) as caught:
        validate_write_path(str(destination), (root,), ".wav")

    assert caught.value.code is ErrorCode.DESTINATION_EXISTS


def test_write_rejects_dangling_symlink_destination(tmp_path: Path) -> None:
    root = tmp_path / "exports"
    root.mkdir()
    destination = root / "mix.wav"
    destination.symlink_to(root / "missing.wav")

    with pytest.raises(AuditionError) as caught:
        validate_write_path(str(destination), (root,), ".wav")

    assert caught.value.code is ErrorCode.DESTINATION_EXISTS


def test_write_rejects_symlink_parent_escape(tmp_path: Path) -> None:
    root = tmp_path / "exports"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(AuditionError) as caught:
        validate_write_path(str(root / "link" / "mix.wav"), (root,), ".wav")

    assert caught.value.code is ErrorCode.PATH_NOT_ALLOWED


@pytest.mark.parametrize(
    ("name", "extension"),
    [
        ("mix.mp3", ".wav"),
        ("mix.WAV", ".wav"),
        ("mix.wav", "wav"),
        ("mix.wav", ".exe"),
    ],
)
def test_write_requires_exact_supported_preset_extension(
    tmp_path: Path,
    name: str,
    extension: str,
) -> None:
    root = tmp_path / "exports"
    root.mkdir()

    with pytest.raises(AuditionError) as caught:
        validate_write_path(str(root / name), (root,), extension)

    assert caught.value.code is ErrorCode.PATH_NOT_ALLOWED


def test_empty_roots_disable_write_operations(tmp_path: Path) -> None:
    with pytest.raises(AuditionError) as caught:
        validate_write_path(str(tmp_path / "mix.wav"), (), ".wav")

    assert caught.value.code is ErrorCode.PATH_NOT_ALLOWED


def test_favorite_is_exactly_allowlisted() -> None:
    allowed = ("Normalize -3 dB",)
    assert validate_favorite("Normalize -3 dB", allowed) == "Normalize -3 dB"

    for candidate in (
        "normalize -3 dB",
        "Normalize -3 dB ",
        "Normalize -3 dB; app.quit()",
        123,
    ):
        with pytest.raises(AuditionError) as caught:
            validate_favorite(candidate, allowed)  # type: ignore[arg-type]
        assert caught.value.code is ErrorCode.OPERATION_NOT_ALLOWED


@pytest.mark.parametrize("value", [True, -1, float("inf"), float("nan"), "1"])
def test_time_rejects_invalid_values(value: object) -> None:
    with pytest.raises(AuditionError) as caught:
        validate_time(value, "seconds")  # type: ignore[arg-type]

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


def test_time_accepts_non_negative_finite_number() -> None:
    assert validate_time(0, "seconds") == 0.0
    assert validate_time(1.25, "seconds") == 1.25
