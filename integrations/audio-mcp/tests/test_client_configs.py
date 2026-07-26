import json
import tomllib
from pathlib import Path


CONFIGS = Path(__file__).parents[1] / "configs"
ROOT_SENTINEL = "__ABSOLUTE_REPOSITORY_ROOT__"
AUDACITY_COMMAND = (
    f"{ROOT_SENTINEL}/"
    "integrations/audio-mcp/.venv-audacity/bin/audacity-mcp"
)
AUDITION_ARGS = [
    "run",
    "--project",
    f"{ROOT_SENTINEL}/integrations/audio-mcp",
    "audio-mcp-audition",
]
AUDITION_CONFIG = "__USER_APPLICATION_SUPPORT__/audio-mcp/audition.json"


def test_codex_example_launches_audacity_from_the_dedicated_environment() -> None:
    with (CONFIGS / "codex.example.toml").open("rb") as handle:
        config = tomllib.load(handle)

    server = config["mcp_servers"]["audacity"]
    assert server == {"command": AUDACITY_COMMAND}


def test_codex_example_launches_audition_with_scoped_config() -> None:
    with (CONFIGS / "codex.example.toml").open("rb") as handle:
        config = tomllib.load(handle)

    server = config["mcp_servers"]["audition"]
    assert server == {
        "command": "uv",
        "args": AUDITION_ARGS,
        "env": {"AUDIO_MCP_AUDITION_CONFIG": AUDITION_CONFIG},
    }


def test_claude_example_launches_audacity_from_the_dedicated_environment() -> None:
    config = json.loads(
        (CONFIGS / "claude-desktop.example.json").read_text(encoding="utf-8")
    )

    server = config["mcpServers"]["audacity"]
    assert server == {"command": AUDACITY_COMMAND, "args": []}


def test_claude_example_launches_audition_with_scoped_config() -> None:
    config = json.loads(
        (CONFIGS / "claude-desktop.example.json").read_text(encoding="utf-8")
    )

    server = config["mcpServers"]["audition"]
    assert server == {
        "command": "uv",
        "args": AUDITION_ARGS,
        "env": {"AUDIO_MCP_AUDITION_CONFIG": AUDITION_CONFIG},
    }


def test_examples_use_only_the_documented_path_sentinel() -> None:
    codex_text = (CONFIGS / "codex.example.toml").read_text(encoding="utf-8")
    claude_text = (CONFIGS / "claude-desktop.example.json").read_text(
        encoding="utf-8"
    )

    assert codex_text.count(ROOT_SENTINEL) == 2
    assert claude_text.count(ROOT_SENTINEL) == 2
    assert codex_text.count("__USER_APPLICATION_SUPPORT__") == 1
    assert claude_text.count("__USER_APPLICATION_SUPPORT__") == 1
