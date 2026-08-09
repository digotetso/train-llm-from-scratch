"""Capacity guards and crash-safe publication for local corpus artifacts."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Callable

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


class StoragePressure(RuntimeError):
    """Raised before an operation would exceed a local storage guard."""


class DrivePublisher:
    """Copy sealed local artifacts to a distinct durable root with verification."""

    def __init__(
        self,
        *,
        local_root: str | Path,
        destination_root: str | Path,
        policy: StoragePolicy,
        free_bytes: Callable[[Path], int] | None = None,
        journal: BuildJournal | None = None,
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
        self.free_bytes = free_bytes or (lambda path: shutil.disk_usage(path).free)
        self.journal = journal
        self._publications: list[Publication] = []
        require_managed_path(self.local_root, self.local_root, kind="directory")
        require_managed_path(
            self.destination_root, self.destination_root, kind="directory"
        )

    def check_capacity(self, next_unit_bytes: int) -> StorageSnapshot:
        """Return current capacity evidence or stop before a configured limit."""

        if not isinstance(next_unit_bytes, int) or isinstance(next_unit_bytes, bool):
            raise ValueError("next_unit_bytes must be a non-negative integer")
        if next_unit_bytes < 0:
            raise ValueError("next_unit_bytes must be a non-negative integer")
        active = sum(
            path.stat().st_size
            for path in self.local_root.rglob("*")
            if _managed_regular_file(self.local_root, path)
        )
        free = int(self.free_bytes(self.local_root))
        if free - next_unit_bytes < self.policy.min_free_bytes:
            raise StoragePressure("free disk floor would be crossed")
        if active + next_unit_bytes > self.policy.max_working_bytes:
            raise StoragePressure("local working-set cap would be crossed")
        return StorageSnapshot(active_bytes=active, free_bytes=free)

    def publish(
        self,
        source: str | Path,
        destination_relative_path: str,
        *,
        unit_id: str | None = None,
    ) -> Publication:
        """Publish a sealed artifact, verify it, then durably record any release."""

        source_path, source_relative_path, size, source_sha256 = self._source_identity(
            source, unit_id
        )
        destination_relative_path = _normalized_relative_posix_path(
            destination_relative_path
        )
        destination = self._destination_path(destination_relative_path)
        self._ensure_destination_root()
        require_managed_path(self.destination_root, destination.parent, kind="directory")
        destination.parent.mkdir(parents=True, exist_ok=True)
        require_managed_path(self.destination_root, destination.parent, kind="directory")
        require_managed_path(self.destination_root, destination, kind="file")
        partial = Path(f"{destination}.partial")
        require_managed_path(self.destination_root, partial, kind="file")

        if destination.exists():
            destination_sha256 = self._verified_destination(destination, size, source_sha256)
        else:
            if partial.exists():
                raise FileExistsError(f"stale partial publication exists: {partial}")
            self._copy_fsynced(source_path, partial)
            try:
                os.link(partial, destination)
            except FileExistsError:
                destination_sha256 = self._verified_destination(
                    destination, size, source_sha256
                )
                partial.unlink()
            else:
                partial.unlink()
                _fsync_directory(destination.parent)
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
        )
        self._publications.append(publication)
        self._record_then_release(publication)
        return publication

    def reconcile(self, publication: Publication) -> Publication:
        """Re-verify a published artifact and finish an interrupted local release."""

        destination = self._destination_path(publication.destination_relative_path)
        self._verified_destination(destination, publication.size, publication.sha256)
        self._record_then_release(publication)
        return publication

    def status(self) -> dict[str, object]:
        """Return capacity evidence and publication work still known to this process."""

        return {
            "storage": self.check_capacity(0),
            "unpublished_artifacts": (
                self.journal.unpublished_artifacts() if self.journal is not None else ()
            ),
            "publications": tuple(self._publications),
        }

    def _source_identity(
        self, source: str | Path, unit_id: str | None
    ) -> tuple[Path, str, int, str]:
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

    def _destination_path(self, destination_relative_path: str) -> Path:
        return require_managed_path(
            self.destination_root,
            self.destination_root / Path(destination_relative_path),
            kind="file",
        )

    def _ensure_destination_root(self) -> None:
        require_managed_path(
            self.destination_root, self.destination_root, kind="directory"
        )
        self.destination_root.mkdir(parents=True, exist_ok=True)
        require_managed_path(
            self.destination_root,
            self.destination_root,
            kind="directory",
            allow_missing=False,
        )

    def _verified_destination(self, destination: Path, size: int, expected_sha256: str) -> str:
        require_managed_path(
            self.destination_root, destination, kind="file", allow_missing=False
        )
        actual_size = destination.stat().st_size
        actual_sha256 = sha256_file(destination)
        if actual_size != size or actual_sha256 != expected_sha256:
            self._quarantine(destination)
            raise ValueError("destination checksum mismatch")
        return actual_sha256

    def _quarantine(self, destination: Path) -> None:
        require_managed_path(
            self.destination_root, destination, kind="file", allow_missing=False
        )
        relative = destination.relative_to(self.destination_root)
        quarantine_parent = self.destination_root / "quarantine" / relative.parent
        require_managed_path(self.destination_root, quarantine_parent, kind="directory")
        quarantine_parent.mkdir(parents=True, exist_ok=True)
        require_managed_path(
            self.destination_root, quarantine_parent, kind="directory", allow_missing=False
        )
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        quarantined = quarantine_parent / f"{relative.name}.{timestamp}"
        while quarantined.exists():
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
            quarantined = quarantine_parent / f"{relative.name}.{timestamp}"
        os.link(destination, quarantined)
        destination.unlink()
        _fsync_directory(destination.parent)
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
        )
        source = Path(publication.source)
        if source.exists():
            source = require_managed_path(
                self.local_root, source, kind="file", allow_missing=False
            )
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


def _normalized_relative_posix_path(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("path must be a normalized relative POSIX path")
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or ".." in path.parts
        or str(path) != value
    ):
        raise ValueError("path must be a normalized relative POSIX path")
    return value


def _managed_regular_file(root: Path, path: Path) -> bool:
    require_managed_path(root, path)
    return path.is_file()


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(directory, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
