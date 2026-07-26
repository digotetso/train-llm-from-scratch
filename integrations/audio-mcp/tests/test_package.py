import tomllib
from pathlib import Path

from audio_mcp import __version__


def test_package_version_is_explicit() -> None:
    assert __version__ == "0.1.0"


def test_package_exposes_audacity_compatibility_entrypoint() -> None:
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    with pyproject.open("rb") as handle:
        config = tomllib.load(handle)

    assert config["project"]["scripts"]["audio-mcp-audacity"] == (
        "audio_mcp.audacity_compat:main"
    )
