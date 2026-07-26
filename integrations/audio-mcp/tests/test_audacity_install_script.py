import os
import shutil
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "install-audacity-mcp.sh"


def test_install_script_has_valid_shell_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_dry_run_is_scoped_and_pinned() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--dry-run"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert ".venv-audacity" in result.stdout
    assert "audacity-mcp==0.1.8" in result.stdout
    assert "/Applications" not in result.stdout
    assert "Library/Application Support" not in result.stdout
    assert not (SCRIPT.parents[1] / ".venv-audacity").exists()


def test_unknown_argument_fails_without_side_effects() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--replace-client-config"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "usage:" in result.stderr
    assert not (SCRIPT.parents[1] / ".venv-audacity").exists()


def test_install_is_idempotent_with_a_scoped_uv_environment(tmp_path: Path) -> None:
    integration_root = tmp_path / "audio-mcp"
    script = integration_root / "scripts" / SCRIPT.name
    script.parent.mkdir(parents=True)
    shutil.copy2(SCRIPT, script)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    call_log = tmp_path / "uv-calls.log"
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$FAKE_UV_CALL_LOG"
if [[ "$1" == "venv" ]]; then
  venv="${@: -1}"
  mkdir -p "$venv/bin"
  printf '#!/usr/bin/env bash\\nexit 0\\n' > "$venv/bin/python"
  chmod +x "$venv/bin/python"
elif [[ "$1" == "pip" ]]; then
  python_path="$4"
  venv="${python_path%/bin/python}"
  printf '#!/usr/bin/env bash\\nexit 0\\n' > "$venv/bin/audacity-mcp"
  chmod +x "$venv/bin/audacity-mcp"
fi
""",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["FAKE_UV_CALL_LOG"] = str(call_log)

    first = subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        env=environment,
        check=True,
    )
    second = subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        env=environment,
        check=True,
    )

    assert "Installed audacity-mcp==0.1.8" in first.stdout
    assert "Installed audacity-mcp==0.1.8" in second.stdout
    assert (integration_root / ".venv-audacity" / "bin" / "audacity-mcp").is_file()
    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert sum(call.startswith("venv ") for call in calls) == 1
    assert sum(call.startswith("pip install ") for call in calls) == 2
