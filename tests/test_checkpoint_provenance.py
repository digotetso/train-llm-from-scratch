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


@pytest.mark.parametrize("label", ("", "../pilot", "pilot/latest", "pilot latest"))
def test_snapshot_checkpoint_rejects_unsafe_labels(tmp_path: Path, label: str):
    from matgpt.training.checkpoint_provenance import snapshot_checkpoint

    checkpoint = tmp_path / "latest.pt"
    checkpoint.write_bytes(b"checkpoint")
    with pytest.raises(ValueError, match="label"):
        snapshot_checkpoint(checkpoint, tmp_path / "snapshots", label=label)
