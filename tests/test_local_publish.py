import hashlib
from pathlib import Path

import pytest

from matgpt.data.local_publish import (
    DrivePublisher,
    StoragePolicy,
    StoragePressure,
)
from matgpt.data.local_state import BuildJournal
from tests.test_local_build_state import _identity, _unit


def _publisher(local: Path, destination: Path, **kwargs: object) -> DrivePublisher:
    return DrivePublisher(
        local_root=local,
        destination_root=destination,
        policy=StoragePolicy(max_working_bytes=1_000, min_free_bytes=1),
        free_bytes=lambda _path: 10_000,
        **kwargs,
    )


def test_capacity_pauses_before_free_floor(tmp_path: Path):
    publisher = DrivePublisher(
        local_root=tmp_path / "local",
        destination_root=tmp_path / "drive",
        policy=StoragePolicy(max_working_bytes=1_000, min_free_bytes=500),
        free_bytes=lambda _path: 499,
    )

    with pytest.raises(StoragePressure, match="free disk floor"):
        publisher.check_capacity(next_unit_bytes=1)


def test_capacity_pauses_before_working_set_cap(tmp_path: Path):
    local = tmp_path / "local"
    local.mkdir()
    (local / "sealed.bin").write_bytes(b"1234")
    publisher = DrivePublisher(
        local_root=local,
        destination_root=tmp_path / "drive",
        policy=StoragePolicy(max_working_bytes=5, min_free_bytes=1),
        free_bytes=lambda _path: 10_000,
    )

    with pytest.raises(StoragePressure, match="working-set cap"):
        publisher.check_capacity(next_unit_bytes=2)


def test_publish_rechecks_destination_bytes_and_sha(tmp_path: Path):
    local = tmp_path / "local"
    local.mkdir()
    artifact = local / "main_00000.bin"
    artifact.write_bytes(b"abcdef")
    publisher = _publisher(local, tmp_path / "drive")

    published = publisher.publish(artifact, "shards/main_00000.bin")

    assert published.size == 6
    assert Path(published.destination).read_bytes() == b"abcdef"
    assert published.sha256 == published.destination_sha256
    assert artifact.exists()


def test_publish_accepts_existing_matching_destination(tmp_path: Path):
    local = tmp_path / "local"
    destination = tmp_path / "drive"
    local.mkdir()
    artifact = local / "chunk.jsonl"
    artifact.write_text("valid\n", encoding="utf-8")
    existing = destination / "text" / "chunk.jsonl"
    existing.parent.mkdir(parents=True)
    existing.write_text("valid\n", encoding="utf-8")

    published = _publisher(local, destination).publish(artifact, "text/chunk.jsonl")

    assert Path(published.destination) == existing
    assert existing.read_text(encoding="utf-8") == "valid\n"
    assert artifact.exists()


def test_publish_quarantines_mismatched_destination_without_deleting_source(
    tmp_path: Path,
):
    local = tmp_path / "local"
    destination = tmp_path / "drive"
    local.mkdir()
    artifact = local / "chunk.jsonl"
    artifact.write_text("valid\n", encoding="utf-8")
    existing = destination / "text" / "chunk.jsonl"
    existing.parent.mkdir(parents=True)
    existing.write_text("corrupt\n", encoding="utf-8")

    with pytest.raises(ValueError, match="checksum mismatch"):
        _publisher(local, destination).publish(artifact, "text/chunk.jsonl")

    assert artifact.read_text(encoding="utf-8") == "valid\n"
    quarantined = tuple((destination / "quarantine").rglob("chunk.jsonl.*"))
    assert len(quarantined) == 1
    assert quarantined[0].read_text(encoding="utf-8") == "corrupt\n"


def test_publish_refuses_stale_partial_without_mutating_source(tmp_path: Path):
    local = tmp_path / "local"
    destination = tmp_path / "drive"
    local.mkdir()
    artifact = local / "chunk.jsonl"
    artifact.write_text("valid\n", encoding="utf-8")
    partial = destination / "text" / "chunk.jsonl.partial"
    partial.parent.mkdir(parents=True)
    partial.write_text("interrupted\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="stale partial"):
        _publisher(local, destination).publish(artifact, "text/chunk.jsonl")

    assert artifact.read_text(encoding="utf-8") == "valid\n"
    assert partial.read_text(encoding="utf-8") == "interrupted\n"


def test_reconcile_refuses_corrupt_destination(tmp_path: Path):
    local = tmp_path / "local"
    destination = tmp_path / "drive"
    local.mkdir()
    artifact = local / "chunk.jsonl"
    artifact.write_text("valid\n", encoding="utf-8")
    publisher = _publisher(local, destination)
    published = publisher.publish(artifact, "text/chunk.jsonl")
    Path(published.destination).write_text("corrupt\n", encoding="utf-8")

    with pytest.raises(ValueError, match="checksum mismatch"):
        publisher.reconcile(published)

    assert artifact.read_text(encoding="utf-8") == "valid\n"
    assert tuple((destination / "quarantine").rglob("chunk.jsonl.*"))


def test_journal_record_precedes_local_release_and_reconcile_recovers_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    local = tmp_path / "local"
    destination = tmp_path / "drive"
    local.mkdir()
    artifact = local / "fit_00000.jsonl"
    artifact.write_bytes(b"committed\n")
    with BuildJournal.open(tmp_path / "state.sqlite3", _identity()) as journal:
        journal.commit_unit(
            _unit(
                artifacts=(
                    {
                        "path": "fit_00000.jsonl",
                        "size": artifact.stat().st_size,
                        "sha256": hashlib.sha256(b"committed\n").hexdigest(),
                    },
                )
            )
        )
        publisher = _publisher(local, destination, journal=journal)
        original_mark_published = journal.mark_published

        def crash_after_copy(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("simulated journal crash")

        monkeypatch.setattr(journal, "mark_published", crash_after_copy)
        with pytest.raises(RuntimeError, match="simulated journal crash"):
            publisher.publish(artifact, "text/fit_00000.jsonl", unit_id="fit-00000")

        assert artifact.exists()
        assert journal.unpublished_artifacts()[0]["path"] == "fit_00000.jsonl"
        monkeypatch.setattr(journal, "mark_published", original_mark_published)
        recovered = publisher.reconcile(
            publisher.status()["publications"][0]  # type: ignore[index]
        )

        assert recovered.destination_sha256 == recovered.sha256
        assert not artifact.exists()
        assert journal.unpublished_artifacts() == ()


@pytest.mark.parametrize("relative_path", ("../escape.bin", "/escape.bin"))
def test_publish_refuses_destination_path_traversal(tmp_path: Path, relative_path: str):
    local = tmp_path / "local"
    local.mkdir()
    artifact = local / "chunk.jsonl"
    artifact.write_text("valid\n", encoding="utf-8")

    with pytest.raises(ValueError, match="normalized relative POSIX path"):
        _publisher(local, tmp_path / "drive").publish(artifact, relative_path)

    assert artifact.exists()


def test_publish_refuses_symlinked_destination_descendant_before_writing(
    tmp_path: Path,
):
    local = tmp_path / "local"
    destination = tmp_path / "drive"
    outside = tmp_path / "outside"
    local.mkdir()
    destination.mkdir()
    outside.mkdir()
    artifact = local / "chunk.jsonl"
    artifact.write_text("valid\n", encoding="utf-8")
    (destination / "text").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symbolic link"):
        _publisher(local, destination).publish(artifact, "text/chunk.jsonl")

    assert artifact.exists()
    assert not (outside / "chunk.jsonl").exists()


def test_publisher_refuses_root_with_a_symlinked_ancestor(tmp_path: Path):
    local = tmp_path / "local"
    outside = tmp_path / "outside"
    symlinked_parent = tmp_path / "linked-parent"
    local.mkdir()
    outside.mkdir()
    symlinked_parent.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symbolic link"):
        _publisher(local, symlinked_parent / "drive")
