import json
import plistlib
from pathlib import Path

from audio_mcp.doctor import audition_checks


CEP_FILES = (
    "CSXS/manifest.xml",
    "index.html",
    "js/cep.js",
    "js/dispatcher.js",
    "js/main.js",
    "jsx/host.jsx",
)


def _write_app(app: Path, version: str) -> None:
    plist = app / "Contents" / "Info.plist"
    plist.parent.mkdir(parents=True)
    with plist.open("wb") as handle:
        plistlib.dump({"CFBundleShortVersionString": version}, handle)


def _write_extension(extension: Path) -> None:
    for relative in CEP_FILES:
        path = extension / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")


def test_audition_checks_local_13_and_secure_install(
    tmp_path: Path,
    config_path: Path,
) -> None:
    app = tmp_path / "Adobe Audition 2020.app"
    extension = tmp_path / "extension"
    _write_app(app, "13.0.2")
    _write_extension(extension)

    checks = audition_checks(
        app,
        extension,
        config_path,
        port_probe=lambda host, port: False,
    )

    assert [(check.name, check.status) for check in checks] == [
        ("audition.application", "pass"),
        ("audition.version", "warning"),
        ("audition.cep_extension", "pass"),
        ("audition.config", "pass"),
        ("audition.port", "pass"),
    ]
    assert "13.0.2" in checks[1].detail
    assert "local compatibility" in checks[1].detail


def test_audition_checks_occupied_port_is_warning(
    tmp_path: Path,
    config_path: Path,
) -> None:
    app = tmp_path / "Adobe Audition.app"
    extension = tmp_path / "extension"
    _write_app(app, "26.3")
    _write_extension(extension)

    checks = audition_checks(
        app,
        extension,
        config_path,
        port_probe=lambda host, port: True,
    )

    port = next(check for check in checks if check.name == "audition.port")
    assert port.status == "warning"
    assert "not proof" in port.detail


def test_audition_checks_reject_bad_config_without_leaking_secret(
    tmp_path: Path,
) -> None:
    secret = "do-not-print-this"
    config_path = tmp_path / "audition.json"
    config_path.write_text(
        json.dumps({"secret": secret, "host": "0.0.0.0"}),
        encoding="utf-8",
    )
    config_path.chmod(0o600)

    checks = audition_checks(
        tmp_path / "missing.app",
        tmp_path / "missing-extension",
        config_path,
        port_probe=lambda host, port: True,
    )

    config = next(check for check in checks if check.name == "audition.config")
    port = next(check for check in checks if check.name == "audition.port")
    assert config.status == "fail"
    assert port.status == "skipped"
    assert secret not in repr(checks)


def test_audition_checks_require_complete_extension(
    tmp_path: Path,
    config_path: Path,
) -> None:
    extension = tmp_path / "extension"
    extension.mkdir()
    (extension / "index.html").write_text("partial", encoding="utf-8")

    checks = audition_checks(
        tmp_path / "missing.app",
        extension,
        config_path,
        port_probe=lambda host, port: False,
    )

    cep = next(
        check for check in checks if check.name == "audition.cep_extension"
    )
    assert cep.status == "fail"
    assert "incomplete" in cep.detail
