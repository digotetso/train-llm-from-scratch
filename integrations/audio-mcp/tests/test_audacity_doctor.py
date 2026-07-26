import json
import os
import plistlib
from pathlib import Path

from audio_mcp.doctor import Check, audacity_checks, format_report


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
    uid = os.getuid()
    os.mkfifo(tmp_path / f"audacity_script_pipe.to.{uid}")
    os.mkfifo(tmp_path / f"audacity_script_pipe.from.{uid}")

    checks = audacity_checks(app, tmp_path, executable, uid=uid)

    assert [(check.name, check.status) for check in checks] == [
        ("audacity.application", "pass"),
        ("audacity.version", "pass"),
        ("audacity.script_pipe", "pass"),
        ("audacity.mcp_executable", "pass"),
    ]
    assert checks[1].detail == "3.7.8.0"


def test_audacity_4_is_rejected(tmp_path: Path) -> None:
    app = tmp_path / "Audacity.app"
    _write_app(app, "4.0.0")

    checks = audacity_checks(app, tmp_path, tmp_path / "missing", uid=501)

    version = next(check for check in checks if check.name == "audacity.version")
    assert version.status == "fail"
    assert version.detail == "Audacity 4 is unsupported; detected 4.0.0."


def test_missing_pipes_explain_safe_recovery(tmp_path: Path) -> None:
    app = tmp_path / "Audacity.app"
    _write_app(app, "3.7.8.0")

    checks = audacity_checks(app, tmp_path, tmp_path / "missing", uid=501)

    pipe = next(check for check in checks if check.name == "audacity.script_pipe")
    assert pipe.status == "fail"
    assert pipe.detail == "Enable mod-script-pipe, restart Audacity, and run doctor again."


def test_regular_files_do_not_pass_as_audacity_pipes(tmp_path: Path) -> None:
    app = tmp_path / "Audacity.app"
    _write_app(app, "3.7.8.0")
    uid = os.getuid()
    (tmp_path / f"audacity_script_pipe.to.{uid}").touch()
    (tmp_path / f"audacity_script_pipe.from.{uid}").touch()

    checks = audacity_checks(app, tmp_path, tmp_path / "missing", uid=uid)

    pipe = next(check for check in checks if check.name == "audacity.script_pipe")
    assert pipe.status == "fail"
    assert "named pipes" in pipe.detail


def test_json_report_is_machine_readable() -> None:
    report = format_report(
        [Check("audacity.version", "pass", "3.7.8.0")],
        json_output=True,
    )

    assert json.loads(report) == {
        "checks": [
            {
                "detail": "3.7.8.0",
                "name": "audacity.version",
                "status": "pass",
            }
        ]
    }


def test_text_report_is_scannable() -> None:
    report = format_report(
        [Check("audacity.version", "warning", "Review version")],
        json_output=False,
    )

    assert report == "WARNING audacity.version: Review version"
