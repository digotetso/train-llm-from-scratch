import json
import os
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "install-audition-cep.sh"
EXTENSION_NAME = "com.zx.audio-mcp-audition"


def _environment(home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    return environment


def test_audition_installer_has_valid_shell_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_audition_installer_dry_run_is_user_scoped(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    result = subprocess.run(
        ["bash", str(SCRIPT), "--dry-run"],
        capture_output=True,
        text=True,
        env=_environment(home),
        check=True,
    )

    assert EXTENSION_NAME in result.stdout
    assert "Application Support/audio-mcp/audition.json" in result.stdout
    assert str(home) in result.stdout
    assert "/Applications/" not in result.stdout
    assert "defaults write" not in result.stdout
    assert not (home / "Library").exists()


def test_audition_installer_creates_secure_config_and_extension(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()

    subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env=_environment(home),
        check=True,
    )

    support = home / "Library" / "Application Support"
    config_path = support / "audio-mcp" / "audition.json"
    extension = (
        support / "Adobe" / "CEP" / "extensions" / EXTENSION_NAME
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config_path.stat().st_mode & 0o777 == 0o600
    assert len(config["secret"]) == 64
    assert set(config["secret"]) <= set("0123456789abcdef")
    assert config["host"] == "127.0.0.1"
    assert config["port"] == 18765
    assert config["favorites"] == []
    assert config["export_presets"] == {"wav": ".wav"}
    assert (extension / "CSXS" / "manifest.xml").is_file()
    assert all(Path(root).is_dir() for root in config["read_roots"])
    assert all(Path(root).is_dir() for root in config["write_roots"])


def test_audition_installer_preserves_existing_config(tmp_path: Path) -> None:
    home = tmp_path / "home"
    config_path = (
        home
        / "Library"
        / "Application Support"
        / "audio-mcp"
        / "audition.json"
    )
    config_path.parent.mkdir(parents=True)
    original = '{"sentinel":"do-not-replace"}\n'
    config_path.write_text(original, encoding="utf-8")
    config_path.chmod(0o600)

    subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env=_environment(home),
        check=True,
    )

    assert config_path.read_text(encoding="utf-8") == original


def test_audition_installer_backs_up_existing_extension(tmp_path: Path) -> None:
    home = tmp_path / "home"
    extension_parent = (
        home
        / "Library"
        / "Application Support"
        / "Adobe"
        / "CEP"
        / "extensions"
    )
    existing = extension_parent / EXTENSION_NAME
    existing.mkdir(parents=True)
    (existing / "old.txt").write_text("old", encoding="utf-8")

    subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env=_environment(home),
        check=True,
    )

    backups = list(extension_parent.glob(f"{EXTENSION_NAME}.backup-*"))
    assert len(backups) == 1
    assert (backups[0] / "old.txt").read_text(encoding="utf-8") == "old"
    assert (existing / "CSXS" / "manifest.xml").is_file()


def test_audition_installer_rejects_unknown_argument(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    result = subprocess.run(
        ["bash", str(SCRIPT), "--edit-client-configs"],
        capture_output=True,
        text=True,
        env=_environment(home),
        check=False,
    )

    assert result.returncode == 2
    assert "usage:" in result.stderr
    assert not (home / "Library").exists()


def test_audition_installer_rejects_unsafe_home() -> None:
    environment = os.environ.copy()
    environment["HOME"] = "/"

    result = subprocess.run(
        ["bash", str(SCRIPT), "--dry-run"],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 1
    assert "safe HOME" in result.stderr
