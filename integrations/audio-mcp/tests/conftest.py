import json
import socket
from pathlib import Path

import pytest

from audio_mcp.audition.config import AuditionConfig


@pytest.fixture
def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@pytest.fixture
def config(tmp_path: Path, free_port: int) -> AuditionConfig:
    read_root = tmp_path / "read"
    write_root = tmp_path / "write"
    read_root.mkdir()
    write_root.mkdir()
    return AuditionConfig(
        secret="a" * 64,
        read_roots=(read_root,),
        write_roots=(write_root,),
        host="127.0.0.1",
        port=free_port,
        favorites=("Normalize -3 dB",),
        export_presets={"wav": ".wav"},
    )


@pytest.fixture
def config_path(config: AuditionConfig, tmp_path: Path) -> Path:
    path = tmp_path / "audition.json"
    path.write_text(
        json.dumps(
            {
                "secret": config.secret,
                "read_roots": [str(value) for value in config.read_roots],
                "write_roots": [str(value) for value in config.write_roots],
                "host": config.host,
                "port": config.port,
                "favorites": list(config.favorites),
                "export_presets": config.export_presets,
            }
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path
