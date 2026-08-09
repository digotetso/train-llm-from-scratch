import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from matgpt.data.local_state import BuildIdentity, BuildJournal, UnitCommit


def _identity(tokenizer_sha256: str | None = None) -> BuildIdentity:
    return BuildIdentity(
        version=1,
        mode="tokenizer_sample",
        plan_sha256="a" * 64,
        source_registry_sha256="b" * 64,
        contamination_sha256="c" * 64,
        quality_policy_sha256="e" * 64,
        tokenizer_sha256=tokenizer_sha256,
        format_sha256="d" * 64,
    )


def _unit(
    *,
    unit_id: str = "fit-00000",
    accepted_hashes: tuple[str, ...] = ("1" * 64, "2" * 64),
    artifacts: tuple[dict[str, object], ...] = (
        {"path": "fit_00000.jsonl", "size": 80, "sha256": "3" * 64},
    ),
) -> UnitCommit:
    return UnitCommit(
        unit_id=unit_id,
        stage="pilot",
        source_id="common_pile_wikimedia",
        row_cursor=123,
        quota_tokens=500,
        accepted_hashes=accepted_hashes,
        artifacts=artifacts,
    )


def test_journal_commits_hashes_cursor_and_artifacts_atomically(tmp_path: Path):
    with BuildJournal.open(tmp_path / "state.sqlite3", _identity()) as journal:
        journal.commit_unit(_unit())

    with BuildJournal.open(tmp_path / "state.sqlite3", _identity()) as journal:
        assert journal.committed_hashes(("1" * 64, "9" * 64)) == {"1" * 64}
        assert journal.units()[0].row_cursor == 123
        assert journal.units()[0].published is False


def test_journal_streams_committed_units_lazily(tmp_path: Path):
    with BuildJournal.open(tmp_path / "state.sqlite3", _identity()) as journal:
        journal.commit_unit(_unit(unit_id="fit-00000"))
        journal.commit_unit(
            _unit(
                unit_id="fit-00001",
                accepted_hashes=("4" * 64,),
            )
        )

        units = journal.iter_units()

        assert isinstance(units, Iterator)
        assert next(units).unit_id == "fit-00000"
        assert next(units).unit_id == "fit-00001"
        with pytest.raises(StopIteration):
            next(units)


def test_journal_refuses_changed_build_identity(tmp_path: Path):
    path = tmp_path / "state.sqlite3"
    BuildJournal.open(path, _identity()).close()

    with pytest.raises(ValueError, match="identity mismatch"):
        BuildJournal.open(path, _identity(tokenizer_sha256="e" * 64))


def test_journal_refuses_missing_identity_when_units_are_already_committed(
    tmp_path: Path,
):
    path = tmp_path / "state.sqlite3"
    with BuildJournal.open(path, _identity()) as journal:
        journal.commit_unit(_unit())

    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM metadata")

    with pytest.raises(ValueError, match="missing identity"):
        BuildJournal.open(path, _identity())


def test_duplicate_hash_rolls_back_the_entire_unit_commit(tmp_path: Path):
    with BuildJournal.open(tmp_path / "state.sqlite3", _identity()) as journal:
        journal.commit_unit(_unit())

        with pytest.raises(ValueError, match="already committed"):
            journal.commit_unit(
                _unit(
                    unit_id="fit-00001",
                    accepted_hashes=("1" * 64, "4" * 64),
                )
            )

        assert [unit.unit_id for unit in journal.units()] == ["fit-00000"]
        assert journal.committed_hashes(("4" * 64,)) == set()


def test_mark_published_tracks_each_artifact_before_the_unit(tmp_path: Path):
    artifacts = (
        {"path": "fit_00000.jsonl", "size": 80, "sha256": "3" * 64},
        {"path": "fit_00000.index", "size": 20, "sha256": "4" * 64},
    )
    with BuildJournal.open(tmp_path / "state.sqlite3", _identity()) as journal:
        journal.commit_unit(_unit(artifacts=artifacts))

        journal.mark_published(
            "fit-00000",
            "fit_00000.jsonl",
            "5" * 64,
            "2026-08-09T12:00:00Z",
        )

        assert journal.units()[0].published is False
        artifact = journal.connection.execute(
            """
            SELECT published, destination_sha256, published_at FROM artifacts
            WHERE unit_id = ? AND relative_path = ?
            """,
            ("fit-00000", "fit_00000.jsonl"),
        ).fetchone()
        assert tuple(artifact) == (1, "5" * 64, "2026-08-09T12:00:00Z")

        journal.mark_published(
            "fit-00000",
            "fit_00000.index",
            "6" * 64,
            "2026-08-09T12:01:00Z",
        )

        assert journal.units()[0].published is True


@pytest.mark.parametrize("artifact_path", ("/artifact.jsonl", "a/../artifact.jsonl"))
def test_journal_rejects_non_normalized_artifact_paths(tmp_path: Path, artifact_path: str):
    with BuildJournal.open(tmp_path / "state.sqlite3", _identity()) as journal:
        with pytest.raises(ValueError, match="normalized relative POSIX path"):
            journal.commit_unit(
                _unit(
                    artifacts=(
                        {"path": artifact_path, "size": 80, "sha256": "3" * 64},
                    )
                )
            )

        assert journal.units() == ()


def test_journal_persists_and_reads_artifacts_in_normalized_path_order(tmp_path: Path):
    artifacts = (
        {"path": "b/artifact.jsonl", "size": 80, "sha256": "3" * 64},
        {"path": "a/artifact.jsonl", "size": 20, "sha256": "4" * 64},
    )
    with BuildJournal.open(tmp_path / "state.sqlite3", _identity()) as journal:
        journal.commit_unit(_unit(artifacts=artifacts))

        assert tuple(artifact["path"] for artifact in journal.units()[0].artifacts) == (
            "a/artifact.jsonl",
            "b/artifact.jsonl",
        )
