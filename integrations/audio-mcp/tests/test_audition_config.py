import json
from pathlib import Path

import pytest

from audio_mcp.audition.config import ConfigError, default_config_path, load_config


def _write_config(
    path: Path,
    read_root: Path,
    write_root: Path,
    **overrides: object,
) -> None:
    payload: dict[str, object] = {
        "secret": "a" * 64,
        "read_roots": [str(read_root)],
        "write_roots": [str(write_root)],
        "host": "127.0.0.1",
        "port": 18765,
        "favorites": ["Normalize -3 dB"],
        "export_presets": {"wav": ".wav"},
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)


def test_load_config_accepts_owner_only_local_configuration(tmp_path: Path) -> None:
    read_root = tmp_path / "read"
    write_root = tmp_path / "write"
    read_root.mkdir()
    write_root.mkdir()
    config_path = tmp_path / "audition.json"
    _write_config(config_path, read_root, write_root)

    config = load_config(config_path)

    assert config.secret == "a" * 64
    assert config.read_roots == (read_root.resolve(),)
    assert config.write_roots == (write_root.resolve(),)
    assert config.host == "127.0.0.1"
    assert config.port == 18765
    assert config.favorites == ("Normalize -3 dB",)
    assert config.export_presets == {"wav": ".wav"}


def test_environment_selects_config_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    read_root = tmp_path / "read"
    write_root = tmp_path / "write"
    read_root.mkdir()
    write_root.mkdir()
    config_path = tmp_path / "selected.json"
    _write_config(config_path, read_root, write_root)
    monkeypatch.setenv("AUDIO_MCP_AUDITION_CONFIG", str(config_path))

    assert load_config().port == 18765


def test_default_config_path_is_user_scoped() -> None:
    expected = (
        Path.home()
        / "Library"
        / "Application Support"
        / "audio-mcp"
        / "audition.json"
    )
    assert default_config_path() == expected


@pytest.mark.parametrize("host", ["localhost", "0.0.0.0", "::1", "192.168.1.2"])
def test_load_config_rejects_non_exact_loopback(
    tmp_path: Path, host: str
) -> None:
    read_root = tmp_path / "read"
    write_root = tmp_path / "write"
    read_root.mkdir()
    write_root.mkdir()
    config_path = tmp_path / "audition.json"
    _write_config(config_path, read_root, write_root, host=host)

    with pytest.raises(ConfigError, match="127.0.0.1"):
        load_config(config_path)


def test_load_config_rejects_group_permissions(tmp_path: Path) -> None:
    read_root = tmp_path / "read"
    write_root = tmp_path / "write"
    read_root.mkdir()
    write_root.mkdir()
    config_path = tmp_path / "audition.json"
    _write_config(config_path, read_root, write_root)
    config_path.chmod(0o640)

    with pytest.raises(ConfigError, match="0600"):
        load_config(config_path)


@pytest.mark.parametrize(
    "secret",
    [
        "z" * 64,
        "A" * 64,
        "a" * 63,
        123,
    ],
)
def test_load_config_rejects_invalid_secret(
    tmp_path: Path, secret: object
) -> None:
    read_root = tmp_path / "read"
    write_root = tmp_path / "write"
    read_root.mkdir()
    write_root.mkdir()
    config_path = tmp_path / "audition.json"
    _write_config(config_path, read_root, write_root, secret=secret)

    with pytest.raises(ConfigError, match="lowercase hex"):
        load_config(config_path)


@pytest.mark.parametrize("port", [True, 1023, 65536, "18765"])
def test_load_config_rejects_invalid_port(tmp_path: Path, port: object) -> None:
    read_root = tmp_path / "read"
    write_root = tmp_path / "write"
    read_root.mkdir()
    write_root.mkdir()
    config_path = tmp_path / "audition.json"
    _write_config(config_path, read_root, write_root, port=port)

    with pytest.raises(ConfigError, match="between 1024 and 65535"):
        load_config(config_path)


@pytest.mark.parametrize("root_kind", ["filesystem", "home"])
def test_load_config_rejects_broad_roots(
    tmp_path: Path, root_kind: str
) -> None:
    safe_root = tmp_path / "safe"
    safe_root.mkdir()
    forbidden = Path("/") if root_kind == "filesystem" else Path.home()
    config_path = tmp_path / "audition.json"
    _write_config(
        config_path,
        safe_root,
        safe_root,
        read_roots=[str(forbidden)],
    )

    with pytest.raises(ConfigError, match="root"):
        load_config(config_path)


def test_load_config_rejects_missing_root(tmp_path: Path) -> None:
    safe_root = tmp_path / "safe"
    safe_root.mkdir()
    config_path = tmp_path / "audition.json"
    _write_config(
        config_path,
        safe_root,
        safe_root,
        read_roots=[str(tmp_path / "missing")],
    )

    with pytest.raises(ConfigError, match="media roots"):
        load_config(config_path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("favorites", ["", "Normalize"], "Favorite"),
        ("favorites", "Normalize", "Favorite"),
        ("export_presets", {"wav": "wav"}, "Export presets"),
        ("export_presets", {"exe": ".exe"}, "Export presets"),
        ("export_presets", [], "Export presets"),
        ("read_roots", "not-a-list", "media roots"),
    ],
)
def test_load_config_rejects_malformed_allowlists(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    root = tmp_path / "safe"
    root.mkdir()
    config_path = tmp_path / "audition.json"
    _write_config(config_path, root, root, **{field: value})

    with pytest.raises(ConfigError, match=message):
        load_config(config_path)


def test_config_errors_never_include_secret(tmp_path: Path) -> None:
    secret = "do-not-print-this-secret"
    config_path = tmp_path / "audition.json"
    config_path.write_text(
        json.dumps({"secret": secret, "host": "127.0.0.1"}),
        encoding="utf-8",
    )
    config_path.chmod(0o600)

    with pytest.raises(ConfigError) as caught:
        load_config(config_path)

    assert secret not in str(caught.value)
    assert secret not in repr(caught.value)


def test_load_config_rejects_oversized_file(tmp_path: Path) -> None:
    config_path = tmp_path / "audition.json"
    config_path.write_text("x" * 65_537, encoding="utf-8")
    config_path.chmod(0o600)

    with pytest.raises(ConfigError, match="65536-byte"):
        load_config(config_path)
