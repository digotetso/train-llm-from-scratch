"""Capacity guards and provider-safe publication for local corpus artifacts."""

from __future__ import annotations

import fcntl
import os
import shutil
import uuid
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator

from matgpt.data.local_state import BuildJournal
from matgpt.utils.hashing import sha256_file
from matgpt.utils.paths import open_exclusive_nofollow, require_managed_path


@dataclass(frozen=True)
class StoragePolicy:
    max_working_bytes: int
    min_free_bytes: int


@dataclass(frozen=True)
class StorageSnapshot:
    active_bytes: int
    free_bytes: int


@dataclass(frozen=True)
class Publication:
    source: str
    source_relative_path: str
    destination: str
    destination_relative_path: str
    size: int
    sha256: str
    destination_sha256: str
    unit_id: str | None = None
    duration_seconds: float = 0.0


class StoragePressure(RuntimeError):
    """Raised before an operation would exceed a local storage guard."""


class DrivePublisher:
    """Publish sealed artifacts through fsynced partial-to-final renames.

    Operators can call ``preflight_destination_provider`` before a real build;
    it creates and removes only a random probe below ``destination_root``.
    """

    def __init__(
        self,
        *,
        local_root: str | Path,
        destination_root: str | Path,
        policy: StoragePolicy,
        free_bytes: Callable[[Path], int] | None = None,
        journal: BuildJournal | None = None,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.local_root = _absolute_root(local_root, "local_root")
        self.destination_root = _absolute_root(destination_root, "destination_root")
        if self.local_root == self.destination_root:
            raise ValueError("local_root and destination_root must be distinct")
        if self.local_root.is_relative_to(self.destination_root) or self.destination_root.is_relative_to(
            self.local_root
        ):
            raise ValueError("local_root and destination_root must not contain one another")
        if policy.max_working_bytes < 0 or policy.min_free_bytes < 0:
            raise ValueError("storage policy values must be non-negative")
        self.policy = policy
        self.free_bytes = free_bytes or _free_bytes_nearest_ancestor
        self.journal = journal
        self.monotonic_clock = monotonic_clock
        self._publications: deque[Publication] = deque(maxlen=1)
        require_managed_path(self.local_root, self.local_root, kind="directory")
        require_managed_path(self.destination_root, self.destination_root, kind="directory")

    def check_capacity(self, next_unit_bytes: int) -> StorageSnapshot:
        """Enforce capacity guards before accepting another local work unit."""

        snapshot = self._storage_snapshot()
        reason = self._pressure_reason(snapshot, next_unit_bytes)
        if reason is not None:
            raise StoragePressure(reason)
        return snapshot

    def publish(
        self,
        source: str | Path,
        destination_relative_path: str,
        *,
        unit_id: str | None = None,
    ) -> Publication:
        """Publish a sealed artifact and record it before any local release."""

        source_path, source_relative_path, size, source_sha256 = self._source_identity(
            source, unit_id
        )
        destination_relative_path = _normalized_relative_posix_path(destination_relative_path)
        destination = self._destination_path(destination_relative_path)
        if self.journal is not None and unit_id is not None and destination.exists():
            if self.journal.prepared_publication(unit_id, source_relative_path) is None:
                raise ValueError(
                    "existing unpublished destination has no prepared publication "
                    "receipt; publication duration is unrecoverable"
                )
        if self.journal is not None:
            if unit_id is None:
                raise ValueError("unit_id is required when a journal is configured")
        self._ensure_destination_root()
        require_managed_path(self.destination_root, destination.parent, kind="directory")
        destination.parent.mkdir(parents=True, exist_ok=True)
        require_managed_path(self.destination_root, destination.parent, kind="directory")
        partial = Path(f"{destination}.partial")
        require_managed_path(self.destination_root, destination, kind="file")
        require_managed_path(self.destination_root, partial, kind="file")
        with self._publication_lock():
            receipt = (
                self.journal.prepared_publication(unit_id, source_relative_path)
                if self.journal is not None and unit_id is not None else None
            )
            if destination.exists():
                if self.journal is not None and receipt is None:
                    raise ValueError(
                        "existing unpublished destination has no prepared publication "
                        "receipt; publication duration is unrecoverable"
                    )
            if self.journal is not None and unit_id is not None:
                self.journal.record_destination(
                    unit_id, source_relative_path, destination_relative_path
                )
            if destination.exists():
                destination_sha256 = self._verified_destination(
                    destination, size, source_sha256
                )
                duration = float(receipt["duration_seconds"]) if receipt else 0.0
            else:
                if partial.exists() and not self._matches_identity(
                    partial, size, source_sha256
                ):
                    self._quarantine(partial)
                if partial.exists() and receipt is None:
                    partial.unlink()
                if not partial.exists():
                    started = float(self.monotonic_clock())
                    self._copy_fsynced(source_path, partial)
                    duration = max(0.0, float(self.monotonic_clock()) - started)
                    if self.journal is not None and unit_id is not None:
                        self.journal.prepare_publication(
                            unit_id, source_relative_path, source_sha256,
                            size=size, duration_seconds=duration,
                        )
                else:
                    duration = float(receipt["duration_seconds"])
                self._move_partial_to_final(partial, destination)
                destination_sha256 = self._verified_destination(
                    destination, size, source_sha256
                )
        publication = Publication(
            source=str(source_path),
            source_relative_path=source_relative_path,
            destination=str(destination),
            destination_relative_path=destination_relative_path,
            size=size,
            sha256=source_sha256,
            destination_sha256=destination_sha256,
            unit_id=unit_id,
            duration_seconds=duration,
        )
        self._publications.append(publication)
        self._record_then_release(publication)
        return publication

    def reconcile(
        self, publication: Publication | None = None
    ) -> Publication | tuple[Publication, ...]:
        """Finish known work, including pending records after process restart."""

        if publication is not None:
            destination = self._destination_path(publication.destination_relative_path)
            with self._publication_lock():
                self._verified_destination(destination, publication.size, publication.sha256)
            self._record_then_release(publication)
            return publication
        if self.journal is None:
            raise ValueError("fresh reconciliation requires a journal")
        recovered: list[Publication] = []
        for artifact in self.journal.iter_unpublished_artifacts():
            destination_relative_path = artifact["destination_relative_path"]
            if not isinstance(destination_relative_path, str):
                raise ValueError("pending artifact has no destination mapping")
            recovered.append(
                self.publish(
                    self.local_root / str(artifact["path"]),
                    destination_relative_path,
                    unit_id=str(artifact["unit_id"]),
                )
            )
        for artifact in self.journal.iter_published_artifacts():
            source = self.local_root / str(artifact["path"])
            if not source.exists():
                continue
            destination_relative_path = artifact["destination_relative_path"]
            if not isinstance(destination_relative_path, str):
                raise ValueError("published artifact has no destination mapping")
            destination = self._destination_path(destination_relative_path)
            self._ensure_destination_root()
            with self._publication_lock():
                destination_sha256 = self._verified_destination(
                    destination,
                    int(artifact["size"]),
                    str(artifact["sha256"]),
                )
            publication = Publication(
                source=str(source),
                source_relative_path=str(artifact["path"]),
                destination=str(destination),
                destination_relative_path=destination_relative_path,
                size=int(artifact["size"]),
                sha256=str(artifact["sha256"]),
                destination_sha256=destination_sha256,
                unit_id=str(artifact["unit_id"]),
            )
            self._record_then_release(publication)
            recovered.append(publication)
        return tuple(recovered)

    def status(self) -> dict[str, object]:
        """Observe storage and pending work without turning pressure into an error."""

        snapshot = self._storage_snapshot()
        return {
            "storage": snapshot,
            "pressure": self._pressure_reason(snapshot, 0),
            "artifact_aggregates": (
                self.journal.artifact_aggregates()
                if self.journal is not None
                else {
                    "published_artifacts": 0,
                    "published_bytes": 0,
                    "unpublished_artifacts": 0,
                    "unpublished_bytes": 0,
                }
            ),
            "publications": tuple(self._publications),
        }

    def preflight_destination_provider(self) -> dict[str, bool]:
        """Safely prove the mounted provider supports fsynced atomic rename."""

        self._ensure_destination_root()
        with self._publication_lock():
            token = uuid.uuid4().hex
            partial = self.destination_root / f".publication-probe-{token}.partial"
            final = self.destination_root / f".publication-probe-{token}"
            try:
                with open_exclusive_nofollow(partial, "wb") as handle:
                    handle.write(b"matgpt-publication-probe\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                self._move_partial_to_final(partial, final)
                if final.read_bytes() != b"matgpt-publication-probe\n":
                    raise ValueError("destination provider rename probe changed bytes")
            finally:
                if partial.exists():
                    partial.unlink()
                if final.exists():
                    final.unlink()
                _fsync_directory(self.destination_root)
        return {"fsynced_partial_rename": True, "hard_links_required": False}

    def _storage_snapshot(self) -> StorageSnapshot:
        active = sum(
            path.stat().st_size
            for path in self.local_root.rglob("*")
            if _managed_regular_file(self.local_root, path)
        )
        return StorageSnapshot(active_bytes=active, free_bytes=int(self.free_bytes(self.local_root)))

    def _pressure_reason(self, snapshot: StorageSnapshot, next_unit_bytes: int) -> str | None:
        if not isinstance(next_unit_bytes, int) or isinstance(next_unit_bytes, bool):
            raise ValueError("next_unit_bytes must be a non-negative integer")
        if next_unit_bytes < 0:
            raise ValueError("next_unit_bytes must be a non-negative integer")
        if snapshot.free_bytes - next_unit_bytes < self.policy.min_free_bytes:
            return "free disk floor would be crossed"
        if snapshot.active_bytes + next_unit_bytes > self.policy.max_working_bytes:
            return "local working-set cap would be crossed"
        return None

    def _source_identity(self, source: str | Path, unit_id: str | None) -> tuple[Path, str, int, str]:
        source_path = require_managed_path(self.local_root, source, kind="file", allow_missing=False)
        if source_path.name.endswith(".partial"):
            raise ValueError("source artifact must be sealed, not a partial file")
        source_relative_path = source_path.relative_to(self.local_root).as_posix()
        with source_path.open("rb") as handle:
            os.fsync(handle.fileno())
        size = source_path.stat().st_size
        source_sha256 = sha256_file(source_path)
        if self.journal is not None:
            if unit_id is None:
                raise ValueError("unit_id is required when a journal is configured")
            committed = self.journal.artifact(unit_id, source_relative_path)
            if committed["size"] != size or committed["sha256"] != source_sha256:
                raise ValueError("source artifact differs from its committed journal identity")
        elif unit_id is not None:
            raise ValueError("unit_id requires a configured journal")
        return source_path, source_relative_path, size, source_sha256

    def _complete_destination(self, source: Path, destination: Path, partial: Path, size: int, source_sha256: str) -> str:
        if destination.exists():
            return self._verified_destination(destination, size, source_sha256)
        if partial.exists():
            if self._matches_identity(partial, size, source_sha256):
                self._move_partial_to_final(partial, destination)
            else:
                self._quarantine(partial)
                self._copy_fsynced(source, partial)
                self._move_partial_to_final(partial, destination)
        else:
            self._copy_fsynced(source, partial)
            self._move_partial_to_final(partial, destination)
        return self._verified_destination(destination, size, source_sha256)

    def _destination_path(self, destination_relative_path: str) -> Path:
        return require_managed_path(self.destination_root, self.destination_root / Path(destination_relative_path), kind="file")

    def _ensure_destination_root(self) -> None:
        require_managed_path(self.destination_root, self.destination_root, kind="directory")
        self.destination_root.mkdir(parents=True, exist_ok=True)
        require_managed_path(self.destination_root, self.destination_root, kind="directory", allow_missing=False)

    @contextmanager
    def _publication_lock(self) -> Iterator[None]:
        lock_path = self.destination_root / ".matgpt-publication.lock"
        require_managed_path(self.destination_root, lock_path, kind="file")
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _move_partial_to_final(self, partial: Path, destination: Path) -> None:
        require_managed_path(self.destination_root, partial, kind="file", allow_missing=False)
        require_managed_path(self.destination_root, destination, kind="file")
        if destination.exists():
            raise FileExistsError(f"destination already exists: {destination}")
        os.rename(partial, destination)
        _fsync_directory(destination.parent)

    def _verified_destination(self, destination: Path, size: int, expected_sha256: str) -> str:
        require_managed_path(self.destination_root, destination, kind="file", allow_missing=False)
        actual_size = destination.stat().st_size
        actual_sha256 = sha256_file(destination)
        if actual_size != size or actual_sha256 != expected_sha256:
            self._quarantine(destination)
            raise ValueError("destination checksum mismatch")
        return actual_sha256

    @staticmethod
    def _matches_identity(path: Path, size: int, expected_sha256: str) -> bool:
        return path.stat().st_size == size and sha256_file(path) == expected_sha256

    def _quarantine(self, path: Path) -> None:
        require_managed_path(self.destination_root, path, kind="file", allow_missing=False)
        relative = path.relative_to(self.destination_root)
        quarantine_parent = self.destination_root / "quarantine" / relative.parent
        require_managed_path(self.destination_root, quarantine_parent, kind="directory")
        quarantine_parent.mkdir(parents=True, exist_ok=True)
        require_managed_path(self.destination_root, quarantine_parent, kind="directory", allow_missing=False)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        quarantined = quarantine_parent / f"{relative.name}.{timestamp}"
        while quarantined.exists():
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
            quarantined = quarantine_parent / f"{relative.name}.{timestamp}"
        os.rename(path, quarantined)
        _fsync_directory(path.parent)
        _fsync_directory(quarantine_parent)

    def _record_then_release(self, publication: Publication) -> None:
        if self.journal is None:
            return
        if publication.unit_id is None:
            raise ValueError("journal publication is missing its unit_id")
        self.journal.mark_published(
            publication.unit_id,
            publication.source_relative_path,
            publication.destination_sha256,
            duration_seconds=publication.duration_seconds,
        )
        source = Path(publication.source)
        if source.exists():
            source = require_managed_path(self.local_root, source, kind="file", allow_missing=False)
            source.unlink()
            _fsync_directory(source.parent)

    @staticmethod
    def _copy_fsynced(source: Path, partial: Path) -> None:
        with source.open("rb") as input_handle, open_exclusive_nofollow(partial, "wb") as output_handle:
            shutil.copyfileobj(input_handle, output_handle, length=1024 * 1024)
            output_handle.flush()
            os.fsync(output_handle.fileno())


def _absolute_root(value: str | Path, name: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{name} must be absolute")
    absolute = Path(os.path.abspath(os.fspath(path)))
    if absolute.resolve(strict=False) != absolute:
        raise ValueError(f"{name} contains a symbolic link")
    return absolute


def _free_bytes_nearest_ancestor(path: Path) -> int:
    """Probe capacity before a configured local root has been created."""

    candidate = path
    while not candidate.exists():
        if candidate.parent == candidate:
            raise ValueError(f"no existing ancestor for storage root: {path}")
        candidate = candidate.parent
    if not candidate.is_dir():
        candidate = candidate.parent
    return int(shutil.disk_usage(candidate).free)


def _normalized_relative_posix_path(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("path must be a normalized relative POSIX path")
    path = PurePosixPath(value)
    if not value or "\\" in value or path.is_absolute() or ".." in path.parts or str(path) != value:
        raise ValueError("path must be a normalized relative POSIX path")
    return value


def _managed_regular_file(root: Path, path: Path) -> bool:
    require_managed_path(root, path)
    return path.is_file()


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
