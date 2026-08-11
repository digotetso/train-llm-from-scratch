import errno
import os
import stat
from pathlib import Path

import pytest


def test_checkpoint_binding_rejects_zero_bytes_and_normalizes_real_file(
    tmp_path: Path,
):
    from matgpt.training.checkpoint_provenance import checkpoint_binding

    (tmp_path / "nested").mkdir()
    checkpoint = tmp_path / "nested/../pilot.pt"
    checkpoint.write_bytes(b"pilot checkpoint bytes")

    binding = checkpoint_binding(checkpoint)

    assert binding == {
        "path": str(checkpoint.resolve()),
        "size": 22,
        "sha256": "becd7635bbc6f29d6b4bc20c47bcce1e4e4695e96d8eaef55452cab02eb3a848",
    }
    empty = tmp_path / "empty.pt"
    empty.touch()
    with pytest.raises(ValueError, match="zero-byte"):
        checkpoint_binding(empty)


def test_snapshot_checkpoint_is_stage_distinct_immutable_and_no_overwrite(
    tmp_path: Path,
):
    from matgpt.training.checkpoint_provenance import snapshot_checkpoint

    latest = tmp_path / "latest.pt"
    snapshots = tmp_path / "snapshots"
    latest.write_bytes(b"smoke checkpoint")
    smoke = snapshot_checkpoint(latest, snapshots, label="smoke")
    latest.write_bytes(b"pilot checkpoint")
    pilot = snapshot_checkpoint(latest, snapshots, label="pilot")

    assert smoke["path"] != pilot["path"]
    assert Path(smoke["path"]).name == f"smoke-{smoke['sha256']}.pt"
    assert Path(pilot["path"]).name == f"pilot-{pilot['sha256']}.pt"
    assert Path(smoke["path"]).read_bytes() == b"smoke checkpoint"
    assert Path(pilot["path"]).read_bytes() == b"pilot checkpoint"
    assert snapshot_checkpoint(latest, snapshots, label="pilot") == pilot

    Path(pilot["path"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="immutable checkpoint snapshot"):
        snapshot_checkpoint(latest, snapshots, label="pilot")


def test_snapshot_checkpoint_publishes_when_hard_links_are_unsupported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from matgpt.training.checkpoint_provenance import snapshot_checkpoint

    checkpoint = tmp_path / "latest.pt"
    checkpoint.write_bytes(b"drive checkpoint")
    snapshots = tmp_path / "snapshots"

    def hard_links_unsupported(_source, _destination):
        raise PermissionError(errno.EPERM, "hard links unsupported")

    monkeypatch.setattr(os, "link", hard_links_unsupported)

    binding = snapshot_checkpoint(checkpoint, snapshots, label="smoke")

    assert Path(binding["path"]).read_bytes() == b"drive checkpoint"
    assert binding["size"] == 16
    assert not list(snapshots.glob("*.staging"))


def test_snapshot_checkpoint_propagates_unexpected_hard_link_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from matgpt.training.checkpoint_provenance import snapshot_checkpoint

    checkpoint = tmp_path / "latest.pt"
    checkpoint.write_bytes(b"checkpoint")
    snapshots = tmp_path / "snapshots"

    def broken_hard_link(_source, _destination):
        raise OSError(errno.EIO, "filesystem I/O failure")

    monkeypatch.setattr(os, "link", broken_hard_link)

    with pytest.raises(OSError, match="filesystem I/O failure"):
        snapshot_checkpoint(checkpoint, snapshots, label="smoke")

    assert list(snapshots.iterdir()) == []


def test_snapshot_checkpoint_tolerates_unsupported_directory_fsync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from matgpt.training.checkpoint_provenance import snapshot_checkpoint

    checkpoint = tmp_path / "latest.pt"
    checkpoint.write_bytes(b"checkpoint")
    real_fsync = os.fsync

    def fuse_fsync(descriptor):
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise OSError(errno.EINVAL, "directory fsync unsupported")
        return real_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", fuse_fsync)

    binding = snapshot_checkpoint(checkpoint, tmp_path / "snapshots", label="smoke")

    assert Path(binding["path"]).read_bytes() == b"checkpoint"


@pytest.mark.parametrize("label", ("", "../pilot", "pilot/latest", "pilot latest"))
def test_snapshot_checkpoint_rejects_unsafe_labels(tmp_path: Path, label: str):
    from matgpt.training.checkpoint_provenance import snapshot_checkpoint

    checkpoint = tmp_path / "latest.pt"
    checkpoint.write_bytes(b"checkpoint")
    with pytest.raises(ValueError, match="label"):
        snapshot_checkpoint(checkpoint, tmp_path / "snapshots", label=label)
