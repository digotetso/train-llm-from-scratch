# Audacity MCP Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an isolated, pinned, diagnosable Audacity MCP setup that can be launched by Codex and Claude Desktop without changing the MatGPT package.

**Architecture:** A repository-local integration project owns setup, client examples, diagnostics, tests, and runbooks. It installs upstream `audacity-mcp==0.1.8` into a dedicated `.venv-audacity`, then each MCP client launches that environment's `audacity-mcp` executable over stdio while Audacity 3.7.8 communicates through local `mod-script-pipe`.

**Tech Stack:** Python 3.11+, pytest 8, Python standard library, POSIX shell, uv 0.8+, `audacity-mcp==0.1.8`, Audacity 3.7.8.

## Global Constraints

- All files live under `integrations/audio-mcp/`; do not modify the root `matgpt-training` dependencies or `uv.lock`.
- Pin upstream Audacity MCP exactly to `audacity-mcp==0.1.8`.
- Support and verify this first release on macOS.
- Do not expose Audacity's script pipe over a network.
- Installation must be idempotent, support `--dry-run`, and touch only `integrations/audio-mcp/.venv-audacity`.
- Do not edit the user's Codex or Claude Desktop configuration automatically.
- Diagnostics must not start an edit, open a valuable project, or print secrets.
- Audacity 4 is unsupported and must produce a diagnostic failure.
- Existing unrelated working-tree changes must remain untouched.

---

## File Map

| File | Responsibility |
|---|---|
| `integrations/audio-mcp/.gitignore` | Exclude dedicated environments and Python caches |
| `integrations/audio-mcp/pyproject.toml` | Isolated integration package metadata and test dependencies |
| `integrations/audio-mcp/src/audio_mcp/__init__.py` | Package version |
| `integrations/audio-mcp/src/audio_mcp/doctor.py` | Audacity installation, version, pipe, executable, and client-example diagnostics |
| `integrations/audio-mcp/scripts/install-audacity-mcp.sh` | Idempotent dedicated-environment installation |
| `integrations/audio-mcp/configs/codex.example.toml` | Codex MCP launch example |
| `integrations/audio-mcp/configs/claude-desktop.example.json` | Claude Desktop MCP launch example |
| `integrations/audio-mcp/tests/test_audacity_doctor.py` | Unit tests for detection and classification |
| `integrations/audio-mcp/tests/test_audacity_install_script.py` | Syntax, dry-run, and scope tests for installation |
| `integrations/audio-mcp/tests/test_client_configs.py` | TOML/JSON parsing and launch-shape tests |
| `integrations/audio-mcp/docs/audacity-smoke-test.md` | Disposable-project smoke test and evidence format |
| `integrations/audio-mcp/docs/security.md` | Audacity pipe risk and local-only operating constraints |
| `integrations/audio-mcp/README.md` | Setup, enablement, client configuration, verification, and rollback |

### Task 1: Create the isolated integration package

**Files:**
- Create: `integrations/audio-mcp/.gitignore`
- Create: `integrations/audio-mcp/pyproject.toml`
- Create: `integrations/audio-mcp/src/audio_mcp/__init__.py`
- Create: `integrations/audio-mcp/tests/test_package.py`

**Interfaces:**
- Consumes: Python 3.11+ and the repository test conventions.
- Produces: importable package `audio_mcp` with `__version__ == "0.1.0"` and an `audio-mcp-doctor` console entry point reserved for Task 2.

- [ ] **Step 1: Add isolated project configuration and the failing package test**

```gitignore
# integrations/audio-mcp/.gitignore
.venv/
.venv-audacity/
__pycache__/
*.pyc
```

```toml
# integrations/audio-mcp/pyproject.toml
[build-system]
requires = ["setuptools>=80,<81", "wheel>=0.45,<1"]
build-backend = "setuptools.build_meta"

[project]
name = "audio-mcp-integrations"
version = "0.1.0"
description = "Local Audacity and Adobe Audition MCP integrations."
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
test = ["pytest>=8,<9"]

[project.scripts]
audio-mcp-doctor = "audio_mcp.doctor:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-q"
```

```python
# integrations/audio-mcp/tests/test_package.py
from audio_mcp import __version__


def test_package_version_is_explicit() -> None:
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_package.py -q
```

Expected: dependency setup and lock creation succeed, then collection fails with
`ModuleNotFoundError: No module named 'audio_mcp'`.

- [ ] **Step 3: Add the minimal package**

```python
# integrations/audio-mcp/src/audio_mcp/__init__.py
"""Local audio-editor MCP integrations."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Run the package test and verify GREEN**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_package.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit the isolated foundation**

```bash
git add integrations/audio-mcp/.gitignore integrations/audio-mcp/pyproject.toml integrations/audio-mcp/uv.lock integrations/audio-mcp/src/audio_mcp/__init__.py integrations/audio-mcp/tests/test_package.py
git commit -m "build: add isolated audio MCP project"
```

### Task 2: Implement evidence-based Audacity diagnostics

**Files:**
- Create: `integrations/audio-mcp/src/audio_mcp/doctor.py`
- Create: `integrations/audio-mcp/tests/test_audacity_doctor.py`

**Interfaces:**
- Consumes: `pathlib.Path`, `plistlib`, `os.getuid`, and injected filesystem paths.
- Produces:
  - `Check(name: str, status: Literal["pass", "warning", "fail", "skipped"], detail: str)`
  - `audacity_checks(app_path: Path, pipe_dir: Path, mcp_executable: Path, uid: int) -> list[Check]`
  - `run_doctor(json_output: bool = False) -> int`
  - `main() -> None`

- [ ] **Step 1: Write failing version and pipe tests**

```python
# integrations/audio-mcp/tests/test_audacity_doctor.py
import plistlib
from pathlib import Path

from audio_mcp.doctor import audacity_checks


def _write_app(app: Path, version: str) -> None:
    plist = app / "Contents" / "Info.plist"
    plist.parent.mkdir(parents=True)
    with plist.open("wb") as handle:
        plistlib.dump({"CFBundleShortVersionString": version}, handle)


def test_audacity_3_7_8_and_both_pipes_pass(tmp_path: Path) -> None:
    app = tmp_path / "Audacity.app"
    _write_app(app, "3.7.8.0")
    executable = tmp_path / "audacity-mcp"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    (tmp_path / "audacity_script_pipe.to.501").touch()
    (tmp_path / "audacity_script_pipe.from.501").touch()

    checks = audacity_checks(app, tmp_path, executable, uid=501)

    assert [(check.name, check.status) for check in checks] == [
        ("audacity.application", "pass"),
        ("audacity.version", "pass"),
        ("audacity.script_pipe", "pass"),
        ("audacity.mcp_executable", "pass"),
    ]


def test_audacity_4_is_rejected(tmp_path: Path) -> None:
    app = tmp_path / "Audacity.app"
    _write_app(app, "4.0.0")

    checks = audacity_checks(app, tmp_path, tmp_path / "missing", uid=501)

    version = next(check for check in checks if check.name == "audacity.version")
    assert version.status == "fail"
    assert "Audacity 4 is unsupported" in version.detail
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_audacity_doctor.py -q
```

Expected: collection fails because `audio_mcp.doctor` does not exist.

- [ ] **Step 3: Implement the diagnostic model and checks**

```python
# integrations/audio-mcp/src/audio_mcp/doctor.py
from __future__ import annotations

import argparse
import json
import os
import plistlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Sequence

Status = Literal["pass", "warning", "fail", "skipped"]


@dataclass(frozen=True)
class Check:
    name: str
    status: Status
    detail: str


def _audacity_version(app_path: Path) -> str | None:
    plist = app_path / "Contents" / "Info.plist"
    if not plist.is_file():
        return None
    with plist.open("rb") as handle:
        value = plistlib.load(handle).get("CFBundleShortVersionString")
    return str(value) if value else None


def audacity_checks(
    app_path: Path,
    pipe_dir: Path,
    mcp_executable: Path,
    uid: int,
) -> list[Check]:
    installed = app_path.is_dir()
    version = _audacity_version(app_path)
    app_check = Check(
        "audacity.application",
        "pass" if installed else "fail",
        str(app_path) if installed else "Audacity.app was not found.",
    )
    if version is None:
        version_check = Check("audacity.version", "skipped", "Version is unavailable.")
    elif version.split(".", 1)[0] == "3":
        version_check = Check("audacity.version", "pass", version)
    else:
        version_check = Check(
            "audacity.version",
            "fail",
            f"Audacity 4 is unsupported; detected {version}.",
        )
    to_pipe = pipe_dir / f"audacity_script_pipe.to.{uid}"
    from_pipe = pipe_dir / f"audacity_script_pipe.from.{uid}"
    pipe_check = Check(
        "audacity.script_pipe",
        "pass" if to_pipe.exists() and from_pipe.exists() else "fail",
        "Both local pipe endpoints exist."
        if to_pipe.exists() and from_pipe.exists()
        else "Enable mod-script-pipe, restart Audacity, and run doctor again.",
    )
    executable_check = Check(
        "audacity.mcp_executable",
        "pass" if mcp_executable.is_file() and os.access(mcp_executable, os.X_OK) else "fail",
        str(mcp_executable)
        if mcp_executable.is_file()
        else "Run scripts/install-audacity-mcp.sh.",
    )
    return [app_check, version_check, pipe_check, executable_check]


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser.parse_args(argv)


def run_doctor(json_output: bool = False) -> int:
    integration_root = Path(__file__).resolve().parents[2]
    checks = audacity_checks(
        Path("/Applications/Audacity.app"),
        Path("/tmp"),
        integration_root / ".venv-audacity" / "bin" / "audacity-mcp",
        os.getuid(),
    )
    if json_output:
        print(json.dumps({"checks": [asdict(check) for check in checks]}, sort_keys=True))
    else:
        for check in checks:
            print(f"{check.status.upper():7} {check.name}: {check.detail}")
    return 1 if any(check.status == "fail" for check in checks) else 0


def main() -> None:
    args = _parse_args()
    raise SystemExit(run_doctor(json_output=args.json_output))
```

- [ ] **Step 4: Add JSON and secret-redaction assertions**

```python
def test_check_details_never_contain_environment_values(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("AUDIO_MCP_TEST_SECRET", "do-not-print-this")
    checks = audacity_checks(
        tmp_path / "missing.app",
        tmp_path,
        tmp_path / "missing",
        uid=501,
    )
    assert "do-not-print-this" not in repr(checks)
```

- [ ] **Step 5: Run the doctor tests and verify GREEN**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_audacity_doctor.py -q
```

Expected: all doctor tests pass.

- [ ] **Step 6: Commit the diagnostic slice**

```bash
git add integrations/audio-mcp/src/audio_mcp/doctor.py integrations/audio-mcp/tests/test_audacity_doctor.py
git commit -m "feat: add Audacity MCP diagnostics"
```

### Task 3: Add the scoped Audacity installer

**Files:**
- Create: `integrations/audio-mcp/scripts/install-audacity-mcp.sh`
- Create: `integrations/audio-mcp/tests/test_audacity_install_script.py`

**Interfaces:**
- Consumes: `uv`, repository-local integration root, optional `--dry-run`.
- Produces: executable `integrations/audio-mcp/.venv-audacity/bin/audacity-mcp` containing `audacity-mcp==0.1.8`.

- [ ] **Step 1: Write failing installer contract tests**

```python
# integrations/audio-mcp/tests/test_audacity_install_script.py
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "install-audacity-mcp.sh"


def test_install_script_has_valid_shell_syntax() -> None:
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
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
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_audacity_install_script.py -q
```

Expected: tests fail because the script does not exist.

- [ ] **Step 3: Implement the idempotent installer**

```bash
#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
integration_root="$(cd "${script_dir}/.." && pwd)"
venv_path="${integration_root}/.venv-audacity"
dry_run=false

if [[ "${1:-}" == "--dry-run" ]]; then
  dry_run=true
elif [[ $# -gt 0 ]]; then
  echo "usage: $0 [--dry-run]" >&2
  exit 2
fi

commands=(
  "uv venv --python 3.11 ${venv_path}"
  "uv pip install --python ${venv_path}/bin/python audacity-mcp==0.1.8"
)

if [[ "${dry_run}" == true ]]; then
  printf '%s\n' "${commands[@]}"
  exit 0
fi

command -v uv >/dev/null 2>&1 || {
  echo "uv is required but was not found." >&2
  exit 1
}

if [[ ! -x "${venv_path}/bin/python" ]]; then
  uv venv --python 3.11 "${venv_path}"
fi
uv pip install --python "${venv_path}/bin/python" "audacity-mcp==0.1.8"
"${venv_path}/bin/python" -c \
  'from importlib.metadata import version; assert version("audacity-mcp") == "0.1.8"'
echo "Installed audacity-mcp==0.1.8 at ${venv_path}/bin/audacity-mcp"
```

- [ ] **Step 4: Mark executable and verify tests**

Run:

```bash
chmod +x integrations/audio-mcp/scripts/install-audacity-mcp.sh
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_audacity_install_script.py -q
```

Expected: all installer contract tests pass.

- [ ] **Step 5: Commit the installer**

```bash
git add integrations/audio-mcp/scripts/install-audacity-mcp.sh integrations/audio-mcp/tests/test_audacity_install_script.py
git commit -m "feat: add pinned Audacity MCP installer"
```

### Task 4: Add Codex and Claude Desktop launch examples

**Files:**
- Create: `integrations/audio-mcp/configs/codex.example.toml`
- Create: `integrations/audio-mcp/configs/claude-desktop.example.json`
- Create: `integrations/audio-mcp/tests/test_client_configs.py`

**Interfaces:**
- Consumes: sentinel `__ABSOLUTE_REPOSITORY_ROOT__`.
- Produces: parseable client examples whose Audacity command is exactly the dedicated environment executable.

- [ ] **Step 1: Write failing example-parsing tests**

```python
# integrations/audio-mcp/tests/test_client_configs.py
import json
import tomllib
from pathlib import Path

CONFIGS = Path(__file__).parents[1] / "configs"
EXPECTED = (
    "__ABSOLUTE_REPOSITORY_ROOT__/"
    "integrations/audio-mcp/.venv-audacity/bin/audacity-mcp"
)


def test_codex_example_launches_pinned_environment() -> None:
    with (CONFIGS / "codex.example.toml").open("rb") as handle:
        config = tomllib.load(handle)
    assert config["mcp_servers"]["audacity"]["command"] == EXPECTED


def test_claude_example_launches_pinned_environment() -> None:
    config = json.loads(
        (CONFIGS / "claude-desktop.example.json").read_text(encoding="utf-8")
    )
    assert config["mcpServers"]["audacity"]["command"] == EXPECTED
    assert config["mcpServers"]["audacity"]["args"] == []
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_client_configs.py -q
```

Expected: both tests fail because the example files do not exist.

- [ ] **Step 3: Add exact examples**

```toml
# integrations/audio-mcp/configs/codex.example.toml
[mcp_servers.audacity]
command = "__ABSOLUTE_REPOSITORY_ROOT__/integrations/audio-mcp/.venv-audacity/bin/audacity-mcp"
```

```json
{
  "mcpServers": {
    "audacity": {
      "command": "__ABSOLUTE_REPOSITORY_ROOT__/integrations/audio-mcp/.venv-audacity/bin/audacity-mcp",
      "args": []
    }
  }
}
```

- [ ] **Step 4: Run config tests and verify GREEN**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_client_configs.py -q
```

Expected: both tests pass.

- [ ] **Step 5: Commit the client examples**

```bash
git add integrations/audio-mcp/configs integrations/audio-mcp/tests/test_client_configs.py
git commit -m "docs: add Audacity MCP client examples"
```

### Task 5: Document security, operation, smoke testing, and rollback

**Files:**
- Create: `integrations/audio-mcp/README.md`
- Create: `integrations/audio-mcp/docs/security.md`
- Create: `integrations/audio-mcp/docs/audacity-smoke-test.md`
- Create: `integrations/audio-mcp/tests/test_audacity_docs.py`

**Interfaces:**
- Consumes: installer, doctor, client examples, Audacity 3.7.8.
- Produces: complete operator path from installation to evidence recording and rollback.

- [ ] **Step 1: Write failing documentation-contract tests**

```python
# integrations/audio-mcp/tests/test_audacity_docs.py
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_readme_contains_required_operator_commands() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    required = [
        "scripts/install-audacity-mcp.sh",
        "Preferences",
        "mod-script-pipe",
        "audio-mcp-doctor --json",
        "codex.example.toml",
        "claude-desktop.example.json",
        "audacity-mcp==0.1.8",
        "Rollback",
    ]
    for phrase in required:
        assert phrase in text


def test_security_doc_forbids_remote_pipe_exposure() -> None:
    text = (ROOT / "docs" / "security.md").read_text(encoding="utf-8")
    assert "Do not expose" in text
    assert "web server" in text
    assert "same-user local process" in text


def test_smoke_test_uses_disposable_media() -> None:
    text = (ROOT / "docs" / "audacity-smoke-test.md").read_text(encoding="utf-8")
    assert "disposable" in text.lower()
    assert "3.7.8" in text
    assert "Audacity 4" in text
    assert "Evidence" in text
```

- [ ] **Step 2: Run docs tests and verify RED**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_audacity_docs.py -q
```

Expected: tests fail because the operator documents do not exist.

- [ ] **Step 3: Write the operator documents**

The README must contain these exact ordered commands:

```bash
cd integrations/audio-mcp
scripts/install-audacity-mcp.sh --dry-run
scripts/install-audacity-mcp.sh
uv run --extra test audio-mcp-doctor --json
```

It must then instruct the operator to enable
**Audacity → Settings/Preferences → Modules → mod-script-pipe → Enabled**,
restart Audacity, replace `__ABSOLUTE_REPOSITORY_ROOT__` in only the selected
client example, merge that one entry into the client configuration, restart
the client, and execute the smoke runbook.

The rollback section must remove only the matching client entry and the exact
repository-local `.venv-audacity` directory after resolving it with:

```bash
cd integrations/audio-mcp
pwd -P
```

The documentation must not instruct the operator to delete Audacity
preferences, projects, `/tmp`, a home directory, or a workspace root.

- [ ] **Step 4: Run docs and complete integration tests**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests -q
bash -n integrations/audio-mcp/scripts/install-audacity-mcp.sh
git diff --check
```

Expected: all integration tests pass, shell syntax succeeds, and
`git diff --check` prints nothing.

- [ ] **Step 5: Commit the Audacity runbooks**

```bash
git add integrations/audio-mcp/README.md integrations/audio-mcp/docs integrations/audio-mcp/tests/test_audacity_docs.py
git commit -m "docs: add Audacity MCP operating runbook"
```

### Task 6: Install and run local Audacity verification

**Files:**
- Modify only if evidence requires correction:
  - `integrations/audio-mcp/docs/audacity-smoke-test.md`

**Interfaces:**
- Consumes: installed Audacity 3.7.8, enabled `mod-script-pipe`, disposable generated WAV, and the dedicated environment.
- Produces: recorded pass/fail evidence without modifying user media.

- [ ] **Step 1: Run the installer preview**

Run:

```bash
integrations/audio-mcp/scripts/install-audacity-mcp.sh --dry-run
```

Expected: exactly two scoped `uv` commands referencing `.venv-audacity` and
`audacity-mcp==0.1.8`.

- [ ] **Step 2: Install the pinned upstream package**

Run:

```bash
integrations/audio-mcp/scripts/install-audacity-mcp.sh
```

Expected: package-version assertion succeeds and the executable path is
printed.

- [ ] **Step 3: Run diagnostics before application automation**

Run:

```bash
uv run --project integrations/audio-mcp audio-mcp-doctor --json
```

Expected:

- application version is `3.7.8.0`;
- executable check passes;
- pipe check passes after Audacity is open and `mod-script-pipe` is enabled.

If the pipe check fails, stop and ask the user to enable the module and restart
Audacity; do not alter Audacity preferences programmatically.

- [ ] **Step 4: Run the disposable-project smoke test**

Follow `integrations/audio-mcp/docs/audacity-smoke-test.md` and record:

```text
Audacity version:
audacity-mcp version:
MCP client:
Status result:
Import result:
Selection result:
Analysis result:
New disposable project save result:
Observed warnings:
```

Expected: status, import, selection, analysis, and save-to-new-path succeed.

- [ ] **Step 5: Run the final Audacity verification set**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests -q
uv run --project integrations/audio-mcp audio-mcp-doctor --json
git status --short
```

Expected: tests pass; doctor reports the observed local state; only scoped
integration files and pre-existing user changes appear in status.

- [ ] **Step 6: Commit evidence-only corrections when necessary**

If the smoke test reveals a documentation error, update only the runbook and
commit:

```bash
git add integrations/audio-mcp/docs/audacity-smoke-test.md
git commit -m "docs: correct Audacity MCP smoke instructions"
```

If no correction is required, do not create an empty commit.
