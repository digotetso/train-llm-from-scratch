import json
import tomllib
from pathlib import Path


CONFIGS = Path(__file__).parents[1] / "configs"
ROOT_SENTINEL = "__ABSOLUTE_REPOSITORY_ROOT__"
AUDACITY_COMMAND = (
    f"{ROOT_SENTINEL}/"
    "integrations/audio-mcp/.venv-audacity/bin/audacity-mcp"
)


def test_codex_example_launches_audacity_from_the_dedicated_environment() -> None:
    with (CONFIGS / "codex.example.toml").open("rb") as handle:
        config = tomllib.load(handle)

    server = config["mcp_servers"]["audacity"]
    assert server == {"command": AUDACITY_COMMAND}


def test_claude_example_launches_audacity_from_the_dedicated_environment() -> None:
    config = json.loads(
        (CONFIGS / "claude-desktop.example.json").read_text(encoding="utf-8")
    )

    server = config["mcpServers"]["audacity"]
    assert server == {"command": AUDACITY_COMMAND, "args": []}


def test_examples_use_only_the_documented_path_sentinel() -> None:
    codex_text = (CONFIGS / "codex.example.toml").read_text(encoding="utf-8")
    claude_text = (CONFIGS / "claude-desktop.example.json").read_text(
        encoding="utf-8"
    )

    assert codex_text.count(ROOT_SENTINEL) == 1
    assert claude_text.count(ROOT_SENTINEL) == 1
