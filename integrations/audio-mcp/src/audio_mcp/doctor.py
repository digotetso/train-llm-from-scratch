from __future__ import annotations

import argparse
import json
import os
import plistlib
import socket
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Literal, Sequence

from audio_mcp.audition.config import (
    AuditionConfig,
    ConfigError,
    default_config_path,
    load_config,
)


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


def _is_owned_fifo(path: Path, uid: int) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return stat.S_ISFIFO(metadata.st_mode) and metadata.st_uid == uid


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
    endpoints_exist = to_pipe.exists() and from_pipe.exists()
    pipes_ready = endpoints_exist and all(
        _is_owned_fifo(endpoint, uid) for endpoint in (to_pipe, from_pipe)
    )
    if pipes_ready:
        pipe_detail = f"{to_pipe} and {from_pipe}"
    elif endpoints_exist:
        pipe_detail = "Script-pipe endpoints must be same-user named pipes."
    else:
        pipe_detail = (
            "Enable mod-script-pipe, restart Audacity, and run doctor again."
        )
    checks.append(
        Check(
            "audacity.script_pipe",
            "pass" if pipes_ready else "fail",
            pipe_detail,
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


AUDITION_CEP_FILES = (
    "CSXS/manifest.xml",
    "index.html",
    "js/cep.js",
    "js/dispatcher.js",
    "js/main.js",
    "jsx/host.jsx",
)


def audition_checks(
    app_path: Path,
    extension_path: Path,
    config_path: Path,
    *,
    port_probe: Callable[[str, int], bool],
) -> list[Check]:
    checks: list[Check] = []
    app_exists = app_path.is_dir()
    checks.append(
        Check(
            "audition.application",
            "pass" if app_exists else "fail",
            str(app_path)
            if app_exists
            else f"Adobe Audition was not found at {app_path}.",
        )
    )

    version = _audacity_version(app_path)
    if version is None:
        checks.append(
            Check(
                "audition.version",
                "fail",
                "Unable to read the installed Adobe Audition version.",
            )
        )
    elif version == "13.0.2":
        checks.append(
            Check(
                "audition.version",
                "warning",
                (
                    "13.0.2 is the local compatibility target; "
                    "26.3 requires separate smoke evidence."
                ),
            )
        )
    else:
        checks.append(
            Check(
                "audition.version",
                "warning",
                (
                    f"Detected {version}; complete the disposable smoke runbook "
                    "before claiming compatibility."
                ),
            )
        )

    missing_files = [
        relative
        for relative in AUDITION_CEP_FILES
        if not (extension_path / relative).is_file()
    ]
    checks.append(
        Check(
            "audition.cep_extension",
            "fail" if missing_files else "pass",
            (
                "CEP extension is incomplete; reinstall the user-scoped extension."
                if missing_files
                else str(extension_path)
            ),
        )
    )

    config: AuditionConfig | None = None
    try:
        config = load_config(config_path)
    except ConfigError as error:
        checks.append(Check("audition.config", "fail", str(error)))
    else:
        checks.append(
            Check(
                "audition.config",
                "pass",
                (
                    f"{config.host}:{config.port}; "
                    f"{len(config.read_roots)} read root(s), "
                    f"{len(config.write_roots)} write root(s), "
                    f"{len(config.favorites)} favorite(s)"
                ),
            )
        )

    if config is None:
        checks.append(
            Check(
                "audition.port",
                "skipped",
                "Port check requires a valid owner-only configuration.",
            )
        )
    else:
        try:
            occupied = port_probe(config.host, config.port)
        except OSError:
            checks.append(
                Check(
                    "audition.port",
                    "warning",
                    "Unable to probe the configured loopback port.",
                )
            )
        else:
            checks.append(
                Check(
                    "audition.port",
                    "warning" if occupied else "pass",
                    (
                        "Loopback port is in use; this is not proof of an "
                        "authenticated CEP handshake."
                        if occupied
                        else "Configured loopback port is available."
                    ),
                )
            )
    return checks


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        return probe.connect_ex((host, port)) == 0


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
        integration_root / ".venv-audacity" / "bin" / "audio-mcp-audacity",
        uid=os.getuid(),
    )
    checks.extend(
        audition_checks(
            Path(
                "/Applications/Adobe Audition 2020/"
                "Adobe Audition 2020.app"
            ),
            (
                Path.home()
                / "Library"
                / "Application Support"
                / "Adobe"
                / "CEP"
                / "extensions"
                / "com.zx.audio-mcp-audition"
            ),
            default_config_path(),
            port_probe=_port_in_use,
        )
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
