import hashlib
import os
from pathlib import Path

import pytest

import matgpt.data.local_publish as local_publish
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


def test_publish_recovers_mismatched_stale_partial_without_mutating_source(tmp_path: Path):
    local = tmp_path / "local"
    destination = tmp_path / "drive"
    local.mkdir()
    artifact = local / "chunk.jsonl"
    artifact.write_text("valid\n", encoding="utf-8")
    partial = destination / "text" / "chunk.jsonl.partial"
    partial.parent.mkdir(parents=True)
    partial.write_text("interrupted\n", encoding="utf-8")

    published = _publisher(local, destination).publish(artifact, "text/chunk.jsonl")

    assert artifact.read_text(encoding="utf-8") == "valid\n"
    assert Path(published.destination).read_text(encoding="utf-8") == "valid\n"
    quarantined = tuple((destination / "quarantine").rglob("chunk.jsonl.partial.*"))
    assert len(quarantined) == 1
    assert quarantined[0].read_text(encoding="utf-8") == "interrupted\n"


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


def test_publication_metrics_are_atomic_and_idempotent_across_return_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    local = tmp_path / "local"
    destination = tmp_path / "drive"
    journal_path = tmp_path / "state.sqlite3"
    local.mkdir()
    artifact = local / "fit_00000.jsonl"
    artifact.write_bytes(b"committed\n")

    class Clock:
        def __init__(self):
            self.values = iter((10.0, 12.5, 20.0, 21.0))

        def __call__(self):
            return next(self.values)

    with BuildJournal.open(journal_path, _identity()) as journal:
        journal.commit_unit(
            _unit(artifacts=({"path": "fit_00000.jsonl", "size": 10,
                              "sha256": hashlib.sha256(b"committed\n").hexdigest()},))
        )
        publisher = _publisher(local, destination, journal=journal,
                               monotonic_clock=Clock())
        original = publisher._record_then_release

        def crash_after_atomic_mark(publication):
            original(publication)
            raise RuntimeError("crash after atomic publication mark")

        monkeypatch.setattr(publisher, "_record_then_release", crash_after_atomic_mark)
        with pytest.raises(RuntimeError, match="atomic publication"):
            publisher.publish(artifact, "text/fit_00000.jsonl", unit_id="fit-00000")
        assert journal.publication_metrics() == {
            "method": "publisher_publish_wall_time",
            "wall_time_seconds": 2.5,
            "artifacts": 1,
            "bytes": 10,
        }

    with BuildJournal.open(journal_path, _identity()) as journal:
        publisher = _publisher(local, destination, journal=journal,
                               monotonic_clock=Clock())
        publisher.reconcile()
        assert journal.publication_metrics()["artifacts"] == 1
        assert journal.publication_metrics()["bytes"] == 10


def test_reconcile_consumes_pre_rename_receipt_after_rename_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    local, destination = tmp_path / "local", tmp_path / "drive"
    local.mkdir()
    artifact = local / "fit_00000.jsonl"
    artifact.write_bytes(b"committed\n")
    journal_path = tmp_path / "state.sqlite3"
    times = iter((0.0, 10.0))
    with BuildJournal.open(journal_path, _identity()) as journal:
        journal.commit_unit(_unit(artifacts=({"path": artifact.name, "size": 10,
            "sha256": hashlib.sha256(b"committed\n").hexdigest()},)))
        publisher = _publisher(local, destination, journal=journal,
                               monotonic_clock=lambda: next(times))
        original_move = publisher._move_partial_to_final
        def crash_after_rename(partial, final):
            original_move(partial, final)
            raise RuntimeError("crash immediately after rename")
        monkeypatch.setattr(publisher, "_move_partial_to_final", crash_after_rename)
        with pytest.raises(RuntimeError, match="after rename"):
            publisher.publish(artifact, "text/fit_00000.jsonl", unit_id="fit-00000")
    with BuildJournal.open(journal_path, _identity()) as journal:
        _publisher(local, destination, journal=journal).reconcile()
        assert journal.publication_metrics() == {"method": "publisher_publish_wall_time",
            "wall_time_seconds": 10.0, "artifacts": 1, "bytes": 10}
        _publisher(local, destination, journal=journal).reconcile()
        assert journal.publication_metrics()["wall_time_seconds"] == 10.0


def test_publish_refuses_legacy_final_without_prepared_receipt_before_mutation(
    tmp_path: Path,
):
    local, destination = tmp_path / "local", tmp_path / "drive"
    local.mkdir()
    artifact = local / "fit_00000.jsonl"
    artifact.write_bytes(b"committed\n")
    journal_path = tmp_path / "state.sqlite3"
    with BuildJournal.open(journal_path, _identity()) as journal:
        journal.commit_unit(_unit(artifacts=({"path": artifact.name, "size": 10,
            "sha256": hashlib.sha256(b"committed\n").hexdigest()},)))
        journal.record_destination("fit-00000", artifact.name, "text/fit_00000.jsonl")
        final = destination / "text/fit_00000.jsonl"
        final.parent.mkdir(parents=True)
        final.write_bytes(b"committed\n")

        with pytest.raises(ValueError, match="prepared publication receipt"):
            _publisher(local, destination, journal=journal).publish(
                artifact, "text/fit_00000.jsonl", unit_id="fit-00000"
            )

        assert artifact.is_file()
        assert final.read_bytes() == b"committed\n"
        assert len(journal.unpublished_artifacts()) == 1
        assert journal.publication_metrics() == {
            "method": "publisher_publish_wall_time",
            "wall_time_seconds": 0.0,
            "artifacts": 0,
            "bytes": 0,
        }


def test_fresh_reconcile_refuses_legacy_final_without_prepared_receipt(
    tmp_path: Path,
):
    local, destination = tmp_path / "local", tmp_path / "drive"
    local.mkdir()
    artifact = local / "fit_00000.jsonl"
    artifact.write_bytes(b"committed\n")
    journal_path = tmp_path / "state.sqlite3"
    with BuildJournal.open(journal_path, _identity()) as journal:
        journal.commit_unit(_unit(artifacts=({"path": artifact.name, "size": 10,
            "sha256": hashlib.sha256(b"committed\n").hexdigest()},)))
        journal.record_destination("fit-00000", artifact.name, "text/fit_00000.jsonl")
    final = destination / "text/fit_00000.jsonl"
    final.parent.mkdir(parents=True)
    final.write_bytes(b"committed\n")

    with BuildJournal.open(journal_path, _identity()) as journal:
        with pytest.raises(ValueError, match="prepared publication receipt"):
            _publisher(local, destination, journal=journal).reconcile()
        assert artifact.is_file()
        assert final.read_bytes() == b"committed\n"
        assert len(journal.unpublished_artifacts()) == 1
        assert journal.publication_metrics()["artifacts"] == 0


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


def test_publish_uses_destination_rename_without_hard_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    local = tmp_path / "local"
    destination = tmp_path / "drive"
    local.mkdir()
    artifact = local / "chunk.jsonl"
    artifact.write_text("valid\n", encoding="utf-8")
    renames: list[tuple[Path, Path]] = []
    real_rename = os.rename

    def reject_hard_link(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Drive publication must not require hard links")

    def record_rename(source: str | Path, target: str | Path) -> None:
        renames.append((Path(source), Path(target)))
        real_rename(source, target)

    monkeypatch.setattr(os, "link", reject_hard_link)
    monkeypatch.setattr(os, "rename", record_rename)

    published = _publisher(local, destination).publish(artifact, "text/chunk.jsonl")

    assert (Path(f"{published.destination}.partial"), Path(published.destination)) in renames


def test_quarantine_uses_rename_without_hard_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    local = tmp_path / "local"
    destination = tmp_path / "drive"
    local.mkdir()
    artifact = local / "chunk.jsonl"
    artifact.write_text("valid\n", encoding="utf-8")
    target = destination / "text" / "chunk.jsonl"
    target.parent.mkdir(parents=True)
    target.write_text("corrupt\n", encoding="utf-8")
    renamed: list[tuple[Path, Path]] = []
    real_rename = os.rename

    monkeypatch.setattr(
        os,
        "link",
        lambda *_args, **_kwargs: pytest.fail("quarantine must not require hard links"),
    )
    monkeypatch.setattr(
        os,
        "rename",
        lambda source, target: (renamed.append((Path(source), Path(target))), real_rename(source, target))[1],
    )

    with pytest.raises(ValueError, match="checksum mismatch"):
        _publisher(local, destination).publish(artifact, "text/chunk.jsonl")

    assert renamed[0][0] == target
    assert "quarantine" in renamed[0][1].parts


def test_fresh_publisher_reconciles_a_matching_stale_partial_from_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    local = tmp_path / "local"
    destination = tmp_path / "drive"
    local.mkdir()
    artifact = local / "fit_00000.jsonl"
    artifact.write_bytes(b"committed\n")
    state_path = tmp_path / "state.sqlite3"
    with BuildJournal.open(state_path, _identity()) as journal:
        journal.commit_unit(
            _unit(
                artifacts=(
                    {
                        "path": artifact.name,
                        "size": artifact.stat().st_size,
                        "sha256": hashlib.sha256(b"committed\n").hexdigest(),
                    },
                )
            )
        )
        publisher = _publisher(local, destination, journal=journal)
        monkeypatch.setattr(
            publisher,
            "_move_partial_to_final",
            lambda *_args: (_ for _ in ()).throw(RuntimeError("interrupted after fsync")),
            raising=False,
        )
        with pytest.raises(RuntimeError, match="interrupted after fsync"):
            publisher.publish(artifact, "text/fit_00000.jsonl", unit_id="fit-00000")

    assert (destination / "text" / "fit_00000.jsonl.partial").exists()
    assert artifact.exists()
    with BuildJournal.open(state_path, _identity()) as journal:
        recovered = _publisher(local, destination, journal=journal).reconcile()

    assert recovered[0].destination_sha256 == hashlib.sha256(b"committed\n").hexdigest()
    assert not artifact.exists()
    assert (destination / "text" / "fit_00000.jsonl").read_bytes() == b"committed\n"


def test_fresh_publisher_quarantines_mismatched_stale_partial_then_republishes(
    tmp_path: Path,
):
    local = tmp_path / "local"
    destination = tmp_path / "drive"
    local.mkdir()
    artifact = local / "fit_00000.jsonl"
    artifact.write_bytes(b"committed\n")
    state_path = tmp_path / "state.sqlite3"
    with BuildJournal.open(state_path, _identity()) as journal:
        journal.commit_unit(
            _unit(
                artifacts=(
                    {
                        "path": artifact.name,
                        "size": artifact.stat().st_size,
                        "sha256": hashlib.sha256(b"committed\n").hexdigest(),
                    },
                )
            )
        )
        journal.record_destination("fit-00000", artifact.name, "text/fit_00000.jsonl")
    partial = destination / "text" / "fit_00000.jsonl.partial"
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b"corrupt\n")

    with BuildJournal.open(state_path, _identity()) as journal:
        recovered = _publisher(local, destination, journal=journal).reconcile()

    assert recovered[0].destination_sha256 == hashlib.sha256(b"committed\n").hexdigest()
    assert tuple((destination / "quarantine").rglob("fit_00000.jsonl.partial.*"))
    assert not artifact.exists()


def test_fresh_reconcile_refuses_pending_artifact_without_destination_mapping(
    tmp_path: Path,
):
    local = tmp_path / "local"
    local.mkdir()
    artifact = local / "fit_00000.jsonl"
    artifact.write_bytes(b"committed\n")
    with BuildJournal.open(tmp_path / "state.sqlite3", _identity()) as journal:
        journal.commit_unit(
            _unit(
                artifacts=(
                    {
                        "path": artifact.name,
                        "size": artifact.stat().st_size,
                        "sha256": hashlib.sha256(b"committed\n").hexdigest(),
                    },
                )
            )
        )

        with pytest.raises(ValueError, match="destination mapping"):
            _publisher(local, tmp_path / "drive", journal=journal).reconcile()


def test_status_reports_pressure_without_raising(tmp_path: Path):
    local = tmp_path / "local"
    local.mkdir()
    (local / "sealed.bin").write_bytes(b"1234")
    publisher = DrivePublisher(
        local_root=local,
        destination_root=tmp_path / "drive",
        policy=StoragePolicy(max_working_bytes=3, min_free_bytes=500),
        free_bytes=lambda _path: 499,
    )

    status = publisher.status()

    assert status["storage"].active_bytes == 4
    assert status["pressure"] == "free disk floor would be crossed"


def test_fresh_reconcile_releases_source_after_committed_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    local = tmp_path / "local"
    destination = tmp_path / "drive"
    local.mkdir()
    artifact = local / "fit_00000.jsonl"
    artifact.write_bytes(b"committed\n")
    target = destination / "text" / artifact.name
    target.parent.mkdir(parents=True)
    target.write_bytes(b"committed\n")
    state_path = tmp_path / "state.sqlite3"
    digest = hashlib.sha256(b"committed\n").hexdigest()
    with BuildJournal.open(state_path, _identity()) as journal:
        journal.commit_unit(
            _unit(
                artifacts=(
                    {"path": artifact.name, "size": artifact.stat().st_size, "sha256": digest},
                )
            )
        )
        journal.record_destination("fit-00000", artifact.name, f"text/{artifact.name}")
        journal.mark_published("fit-00000", artifact.name, digest)

    fsynced_directories: list[Path] = []
    real_fsync_directory = local_publish._fsync_directory
    monkeypatch.setattr(
        local_publish,
        "_fsync_directory",
        lambda directory: (
            fsynced_directories.append(Path(directory)),
            real_fsync_directory(directory),
        )[1],
    )
    with BuildJournal.open(state_path, _identity()) as journal:
        recovered = _publisher(local, destination, journal=journal).reconcile()

    assert recovered[0].destination_sha256 == digest
    assert not artifact.exists()
    assert local in fsynced_directories


@pytest.mark.parametrize("destination_bytes", (None, b"corrupt\n"))
def test_fresh_reconcile_retains_source_when_committed_destination_is_unusable(
    tmp_path: Path, destination_bytes: bytes | None
):
    local = tmp_path / "local"
    destination = tmp_path / "drive"
    local.mkdir()
    artifact = local / "fit_00000.jsonl"
    artifact.write_bytes(b"committed\n")
    state_path = tmp_path / "state.sqlite3"
    digest = hashlib.sha256(b"committed\n").hexdigest()
    with BuildJournal.open(state_path, _identity()) as journal:
        journal.commit_unit(
            _unit(
                artifacts=(
                    {"path": artifact.name, "size": artifact.stat().st_size, "sha256": digest},
                )
            )
        )
        journal.record_destination("fit-00000", artifact.name, f"text/{artifact.name}")
        journal.mark_published("fit-00000", artifact.name, digest)
    if destination_bytes is not None:
        target = destination / "text" / artifact.name
        target.parent.mkdir(parents=True)
        target.write_bytes(destination_bytes)

    with BuildJournal.open(state_path, _identity()) as journal:
        with pytest.raises((ValueError, FileNotFoundError), match="checksum mismatch|does not exist"):
            _publisher(local, destination, journal=journal).reconcile()

    assert artifact.read_bytes() == b"committed\n"
