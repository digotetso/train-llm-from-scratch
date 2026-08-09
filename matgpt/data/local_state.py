"""Crash-safe local state for resumable corpus builds."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Iterable, Iterator, Mapping

from matgpt.utils.hashing import sha256_json
from matgpt.utils.paths import require_managed_path


@dataclass(frozen=True)
class BuildIdentity:
    """The immutable inputs that define one corpus build."""

    version: int
    mode: str
    plan_sha256: str
    source_registry_sha256: str
    contamination_sha256: str
    quality_policy_sha256: str
    tokenizer_sha256: str | None
    format_sha256: str
    operational: Mapping[str, str] | None = None

    @property
    def content_payload(self) -> dict[str, object]:
        """Return path-independent inputs that define produced content."""

        payload = asdict(self)
        payload.pop("operational")
        return payload

    @property
    def journal_payload(self) -> dict[str, object]:
        """Return content plus machine-local state/publication ownership."""

        payload = self.content_payload
        if self.operational is not None:
            payload["operational"] = dict(self.operational)
        return payload

    @property
    def content_sha256(self) -> str:
        return sha256_json(self.content_payload)

    @property
    def sha256(self) -> str:
        return sha256_json(self.journal_payload)


@dataclass(frozen=True)
class UnitCommit:
    """The durable state produced after a successful build unit."""

    unit_id: str
    stage: str
    source_id: str
    row_cursor: int
    quota_tokens: int
    accepted_hashes: tuple[str, ...]
    artifacts: tuple[dict[str, object], ...]
    published: bool = False
    state: Mapping[str, object] = field(default_factory=dict)


_IDENTITY_JSON_KEY = "identity_json"
_IDENTITY_SHA256_KEY = "identity_sha256"
_HASH_BATCH_SIZE = 900
_STATE_TABLES = ("units", "seen_hashes", "artifacts")


class BuildJournal:
    """SQLite journal whose unit commits are all-or-nothing."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    @classmethod
    def open(
        cls,
        path: str | Path,
        identity: BuildIdentity,
        *,
        managed_root: str | Path | None = None,
    ) -> "BuildJournal":
        """Open a journal, creating it only for the supplied exact identity."""

        journal_path = Path(path)
        root = Path(managed_root) if managed_root is not None else journal_path.parent
        require_managed_path(root, journal_path.parent, kind="directory")
        require_managed_path(root, journal_path, kind="file")
        for suffix in ("-wal", "-shm", "-journal"):
            require_managed_path(root, Path(f"{journal_path}{suffix}"), kind="file")
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(journal_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
            cls._create_schema(connection)
            cls._ensure_identity(connection, identity)
        except BaseException:
            connection.close()
            raise
        return cls(connection)

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS units (
                unit_id TEXT PRIMARY KEY,
                stage TEXT NOT NULL,
                source_id TEXT NOT NULL,
                row_cursor INTEGER NOT NULL,
                quota_tokens INTEGER NOT NULL,
                artifacts_json TEXT NOT NULL,
                state_json TEXT NOT NULL DEFAULT '{}',
                published INTEGER NOT NULL CHECK (published IN (0, 1))
            );

            CREATE TABLE IF NOT EXISTS seen_hashes (
                content_sha256 TEXT PRIMARY KEY,
                unit_id TEXT NOT NULL,
                FOREIGN KEY (unit_id) REFERENCES units(unit_id)
            );

            CREATE TABLE IF NOT EXISTS artifacts (
                unit_id TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                size INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                destination_relative_path TEXT,
                published INTEGER NOT NULL CHECK (published IN (0, 1)),
                destination_sha256 TEXT,
                published_at TEXT,
                PRIMARY KEY (unit_id, relative_path),
                FOREIGN KEY (unit_id) REFERENCES units(unit_id)
            );

            CREATE INDEX IF NOT EXISTS seen_hashes_unit_id_idx
            ON seen_hashes(unit_id, content_sha256);

            CREATE INDEX IF NOT EXISTS artifacts_relative_path_idx
            ON artifacts(relative_path);
            """
        )
        columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(artifacts)")
        }
        if "destination_relative_path" not in columns:
            connection.execute(
                "ALTER TABLE artifacts ADD COLUMN destination_relative_path TEXT"
            )
        unit_columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(units)")}
        if "state_json" not in unit_columns:
            connection.execute("ALTER TABLE units ADD COLUMN state_json TEXT NOT NULL DEFAULT '{}'")

    @staticmethod
    def _ensure_identity(connection: sqlite3.Connection, identity: BuildIdentity) -> None:
        identity_json = json.dumps(
            identity.journal_payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        rows = dict(
            connection.execute(
                "SELECT key, value FROM metadata WHERE key IN (?, ?)",
                (_IDENTITY_JSON_KEY, _IDENTITY_SHA256_KEY),
            )
        )
        if not rows:
            if BuildJournal._has_persisted_state(connection):
                raise ValueError("journal state is missing identity metadata")
            with connection:
                connection.executemany(
                    "INSERT INTO metadata(key, value) VALUES (?, ?)",
                    (
                        (_IDENTITY_JSON_KEY, identity_json),
                        (_IDENTITY_SHA256_KEY, identity.sha256),
                    ),
                )
            return
        if set(rows) != {_IDENTITY_JSON_KEY, _IDENTITY_SHA256_KEY}:
            raise ValueError("journal identity is incomplete")
        if rows[_IDENTITY_SHA256_KEY] != sha256_json(json.loads(rows[_IDENTITY_JSON_KEY])):
            raise ValueError("journal identity integrity mismatch")
        if (
            rows[_IDENTITY_JSON_KEY] != identity_json
            or rows[_IDENTITY_SHA256_KEY] != identity.sha256
        ):
            raise ValueError("journal identity mismatch")

    @staticmethod
    def _has_persisted_state(connection: sqlite3.Connection) -> bool:
        return any(
            connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
            for table in _STATE_TABLES
        )

    def commit_unit(self, unit: UnitCommit) -> None:
        """Atomically store a build unit, its content hashes, and artifacts."""

        artifacts = _normalized_artifacts(unit.artifacts)
        artifacts_json = json.dumps(
            artifacts, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        try:
            with self.connection:
                self.connection.execute(
                    """
                    INSERT INTO units(
                        unit_id, stage, source_id, row_cursor, quota_tokens,
                        artifacts_json, state_json, published
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        unit.unit_id,
                        unit.stage,
                        unit.source_id,
                        unit.row_cursor,
                        unit.quota_tokens,
                        artifacts_json,
                        json.dumps(unit.state, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                        int(not artifacts),
                    ),
                )
                self.connection.executemany(
                    "INSERT INTO seen_hashes(content_sha256, unit_id) VALUES (?, ?)",
                    ((digest, unit.unit_id) for digest in unit.accepted_hashes),
                )
                self.connection.executemany(
                    """
                    INSERT INTO artifacts(
                        unit_id, relative_path, size, sha256,
                        destination_relative_path, published
                    ) VALUES (?, ?, ?, ?, ?, 0)
                    """,
                    (
                        (
                            unit.unit_id,
                            str(artifact["path"]),
                            int(artifact["size"]),
                            str(artifact["sha256"]),
                            artifact.get("destination_path"),
                        )
                        for artifact in artifacts
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError("unit ID or document hash already committed") from error

    def committed_hashes(self, hashes: Iterable[str]) -> set[str]:
        """Return the supplied digests that are already committed."""

        committed: set[str] = set()
        batch: list[str] = []
        for digest in hashes:
            batch.append(digest)
            if len(batch) == _HASH_BATCH_SIZE:
                committed.update(self._committed_hashes_batch(batch))
                batch.clear()
        if batch:
            committed.update(self._committed_hashes_batch(batch))
        return committed

    def _committed_hashes_batch(self, hashes: list[str]) -> set[str]:
        placeholders = ", ".join("?" for _ in hashes)
        rows = self.connection.execute(
            f"SELECT content_sha256 FROM seen_hashes WHERE content_sha256 IN ({placeholders})",
            hashes,
        )
        return {str(row["content_sha256"]) for row in rows}

    def iter_units(self) -> Iterator[UnitCommit]:
        """Stream committed units in deterministic order, one bounded unit at a time."""

        rows = self.connection.execute(
            """
            SELECT unit_id, stage, source_id, row_cursor, quota_tokens,
                   artifacts_json, state_json, published
            FROM units
            ORDER BY unit_id
            """
        )
        for row in rows:
            yield UnitCommit(
                unit_id=str(row["unit_id"]),
                stage=str(row["stage"]),
                source_id=str(row["source_id"]),
                row_cursor=int(row["row_cursor"]),
                quota_tokens=int(row["quota_tokens"]),
                accepted_hashes=self._hashes_for_unit(str(row["unit_id"])),
                artifacts=tuple(json.loads(str(row["artifacts_json"]))),
                published=bool(row["published"]),
                state=json.loads(str(row["state_json"])),
            )

    def iter_units_in_commit_order(self) -> Iterator[UnitCommit]:
        """Stream units in transaction order for cumulative-snapshot deltas."""

        rows = self.connection.execute(
            """
            SELECT unit_id, stage, source_id, row_cursor, quota_tokens,
                   artifacts_json, state_json, published
            FROM units
            ORDER BY rowid
            """
        )
        for row in rows:
            yield UnitCommit(
                unit_id=str(row["unit_id"]),
                stage=str(row["stage"]),
                source_id=str(row["source_id"]),
                row_cursor=int(row["row_cursor"]),
                quota_tokens=int(row["quota_tokens"]),
                accepted_hashes=self._hashes_for_unit(str(row["unit_id"])),
                artifacts=tuple(json.loads(str(row["artifacts_json"]))),
                published=bool(row["published"]),
                state=json.loads(str(row["state_json"])),
            )

    def units(self) -> tuple[UnitCommit, ...]:
        """Return all committed units; prefer ``iter_units`` for large builds."""

        return tuple(self.iter_units())

    def iter_artifacts(self) -> Iterator[dict[str, object]]:
        """Stream committed artifact identities in relative-path order."""

        rows = self.connection.execute(
            """
            SELECT relative_path, size, sha256 FROM artifacts
            ORDER BY relative_path
            """
        )
        for row in rows:
            yield {
                "path": str(row["relative_path"]),
                "size": int(row["size"]),
                "sha256": str(row["sha256"]),
            }

    def has_artifact(self, relative_path: str) -> bool:
        """Return whether a normalized artifact path is durably committed."""

        return (
            self.connection.execute(
                "SELECT 1 FROM artifacts WHERE relative_path = ? LIMIT 1",
                (relative_path,),
            ).fetchone()
            is not None
        )

    def artifact(self, unit_id: str, relative_path: str) -> dict[str, object]:
        """Return one committed artifact identity or reject an unknown artifact."""

        relative_path = _normalized_relative_posix_path(relative_path)
        row = self.connection.execute(
            """
            SELECT unit_id, relative_path, size, sha256, published, destination_sha256,
                   destination_relative_path
            FROM artifacts
            WHERE unit_id = ? AND relative_path = ?
            """,
            (unit_id, relative_path),
        ).fetchone()
        if row is None:
            raise ValueError("unknown artifact")
        return {
            "unit_id": str(row["unit_id"]),
            "path": str(row["relative_path"]),
            "size": int(row["size"]),
            "sha256": str(row["sha256"]),
            "published": bool(row["published"]),
            "destination_sha256": row["destination_sha256"],
            "destination_relative_path": row["destination_relative_path"],
        }

    def record_destination(
        self,
        unit_id: str,
        relative_path: str,
        destination_relative_path: str,
    ) -> None:
        """Durably bind a pending source artifact to one destination path."""

        relative_path = _normalized_relative_posix_path(relative_path)
        destination_relative_path = _normalized_relative_posix_path(
            destination_relative_path
        )
        with self.connection:
            artifact = self.connection.execute(
                """
                SELECT destination_relative_path FROM artifacts
                WHERE unit_id = ? AND relative_path = ?
                """,
                (unit_id, relative_path),
            ).fetchone()
            if artifact is None:
                raise ValueError("unknown artifact")
            existing = artifact["destination_relative_path"]
            if existing is not None and existing != destination_relative_path:
                raise ValueError("artifact destination mapping conflict")
            self.connection.execute(
                """
                UPDATE artifacts
                SET destination_relative_path = ?
                WHERE unit_id = ? AND relative_path = ?
                """,
                (destination_relative_path, unit_id, relative_path),
            )

    def unpublished_artifacts(self) -> tuple[dict[str, object], ...]:
        """Return all unrecorded artifact publications in deterministic order."""

        rows = self.connection.execute(
            """
            SELECT unit_id, relative_path, size, sha256, destination_relative_path
            FROM artifacts
            WHERE published = 0
            ORDER BY unit_id, relative_path
            """
        )
        return tuple(
            {
                "unit_id": str(row["unit_id"]),
                "path": str(row["relative_path"]),
                "size": int(row["size"]),
                "sha256": str(row["sha256"]),
                "destination_relative_path": row["destination_relative_path"],
            }
            for row in rows
        )

    def published_artifacts(self) -> tuple[dict[str, object], ...]:
        """Return recorded artifact publications for post-commit release recovery."""

        rows = self.connection.execute(
            """
            SELECT unit_id, relative_path, size, sha256, destination_relative_path,
                   destination_sha256
            FROM artifacts
            WHERE published = 1
            ORDER BY unit_id, relative_path
            """
        )
        return tuple(
            {
                "unit_id": str(row["unit_id"]),
                "path": str(row["relative_path"]),
                "size": int(row["size"]),
                "sha256": str(row["sha256"]),
                "destination_relative_path": row["destination_relative_path"],
                "destination_sha256": row["destination_sha256"],
            }
            for row in rows
        )

    def _hashes_for_unit(self, unit_id: str) -> tuple[str, ...]:
        rows = self.connection.execute(
            """
            SELECT content_sha256 FROM seen_hashes
            WHERE unit_id = ?
            ORDER BY content_sha256
            """,
            (unit_id,),
        )
        return tuple(str(row["content_sha256"]) for row in rows)

    def mark_published(
        self,
        unit_id: str,
        relative_path: str,
        destination_sha256: str,
    ) -> None:
        """Record one artifact publication and complete its unit when all are done."""

        relative_path = _normalized_relative_posix_path(relative_path)
        with self.connection:
            artifact = self.connection.execute(
                """
                SELECT published, sha256, destination_sha256 FROM artifacts
                WHERE unit_id = ? AND relative_path = ?
                """,
                (unit_id, relative_path),
            ).fetchone()
            if artifact is None:
                raise ValueError("unknown artifact")
            if artifact["sha256"] != destination_sha256:
                raise ValueError("destination checksum does not match committed source hash")
            if artifact["published"]:
                if artifact["destination_sha256"] != destination_sha256:
                    raise ValueError("artifact was already published with another hash")
                return
            self.connection.execute(
                """
                UPDATE artifacts
                SET published = 1, destination_sha256 = ?, published_at = ?
                WHERE unit_id = ? AND relative_path = ?
                """,
                (
                    destination_sha256,
                    datetime.now(UTC).isoformat(),
                    unit_id,
                    relative_path,
                ),
            )
            self.connection.execute(
                """
                UPDATE units
                SET published = NOT EXISTS (
                    SELECT 1 FROM artifacts
                    WHERE unit_id = ? AND published = 0
                )
                WHERE unit_id = ?
                """,
                (unit_id, unit_id),
            )

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "BuildJournal":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()


def _normalized_artifacts(
    artifacts: tuple[dict[str, object], ...],
) -> tuple[dict[str, object], ...]:
    normalized = tuple(
        {**artifact, "path": _normalized_relative_posix_path(artifact["path"])}
        for artifact in artifacts
    )
    return tuple(sorted(normalized, key=lambda artifact: str(artifact["path"])))


def _normalized_relative_posix_path(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("artifact path must be a normalized relative POSIX path")
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or ".." in path.parts
        or str(path) != value
    ):
        raise ValueError("artifact path must be a normalized relative POSIX path")
    return value
