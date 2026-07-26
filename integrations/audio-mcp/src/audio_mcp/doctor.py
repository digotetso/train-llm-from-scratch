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
    plist_path = app_path / "Contents" / "Info.plist"
    if not plist_path.is_file():
        return None
    try:
        with plist_path.open("rb") as handle:
            metadata = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException):
        return None

    version = metadata.get("CFBundleShortVersionString")
    return version if isinstance(version, str) and version else None


def audacity_checks(
    app_path: Path,
    pipe_dir: Path,
    mcp_executable: Path,
    *,
    uid: int,
) -> list[Check]:
    checks: list[Check] = []
    app_exists = app_path.is_dir()
    checks.append(
        Check(
            "audacity.application",
            "pass" if app_exists else "fail",
            str(app_path) if app_exists else f"Audacity was not found at {app_path}.",
        )
    )

    version = _audacity_version(app_path)
    if version is None:
        checks.append(
            Check(
                "audacity.version",
                "fail",
                "Unable to read the installed Audacity version.",
            )
        )
    elif version.split(".", 1)[0] == "4":
        checks.append(
            Check(
                "audacity.version",
                "fail",
                f"Audacity 4 is unsupported; detected {version}.",
            )
        )
    elif version.split(".", 1)[0] == "3":
        checks.append(Check("audacity.version", "pass", version))
    else:
        checks.append(
            Check(
                "audacity.version",
                "warning",
                f"Expected Audacity 3.x; detected {version}.",
            )
        )

    to_pipe = pipe_dir / f"audacity_script_pipe.to.{uid}"
    from_pipe = pipe_dir / f"audacity_script_pipe.from.{uid}"
    pipes_ready = to_pipe.exists() and from_pipe.exists()
    checks.append(
        Check(
            "audacity.script_pipe",
            "pass" if pipes_ready else "fail",
            (
                f"{to_pipe} and {from_pipe}"
                if pipes_ready
                else "Enable mod-script-pipe, restart Audacity, and run doctor again."
            ),
        )
    )

    executable_ready = mcp_executable.is_file() and os.access(
        mcp_executable, os.X_OK
    )
    checks.append(
        Check(
            "audacity.mcp_executable",
            "pass" if executable_ready else "fail",
            (
                str(mcp_executable)
                if executable_ready
                else f"Install audacity-mcp at {mcp_executable}."
            ),
        )
    )
    return checks


def format_report(checks: Sequence[Check], *, json_output: bool) -> str:
    if json_output:
        return json.dumps(
            {"checks": [asdict(check) for check in checks]},
            sort_keys=True,
        )
    return "\n".join(
        f"{check.status.upper():7} {check.name}: {check.detail}" for check in checks
    )


def run_doctor(*, json_output: bool = False) -> int:
    integration_root = Path(__file__).resolve().parents[2]
    checks = audacity_checks(
        Path("/Applications/Audacity.app"),
        Path("/tmp"),
        integration_root / ".venv-audacity" / "bin" / "audacity-mcp",
        uid=os.getuid(),
    )
    print(format_report(checks, json_output=json_output))
    return 1 if any(check.status == "fail" for check in checks) else 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check the local Audacity MCP prerequisites."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON report.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    return run_doctor(json_output=args.json)
