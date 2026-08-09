"""Deterministic, crash-resumable local tokenizer sample construction."""

from __future__ import annotations

import itertools
import json
import math
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping

from matgpt.data.contamination import pattern_fingerprint
from matgpt.data.local_state import BuildIdentity, BuildJournal, UnitCommit
from matgpt.data.quality import DataQualityPolicy, QualityFilter
from matgpt.data.sources import SourceRegistry
from matgpt.data.telco_prepare import (
    _item_id,
    _load_dataset_function,
    _loader_kwargs,
    _validated_plan_items,
    is_validation_record,
    iter_deterministic_source_windows,
)
from matgpt.utils.hashing import sha256_file, sha256_json


_CHUNK_NAME = re.compile(r"^(fit|holdout)_(\d{5,})\.jsonl$")
_FORMAT_VERSION = 1


@dataclass(frozen=True)
class LocalSampleRequest:
    registry: SourceRegistry
    plan: Mapping[str, object]
    output_dir: Path
    state_path: Path
    quality_policy: DataQualityPolicy
    chunk_bytes: int = 268_435_456
    progress_interval_seconds: float = 30.0


@dataclass(frozen=True)
class ProgressEvent:
    stage: str
    source_id: str
    row_cursor: int
    accepted_documents: int
    accepted_estimated_tokens: int
    requested_estimated_tokens: int
    elapsed_seconds: float
    tokens_per_second: float
    eta_seconds: float | None


@dataclass
class _SampleState:
    item_tokens: dict[str, int]
    fit_hashes: list[str]
    holdout_hashes: list[str]
    source_cursors: dict[str, int]
    artifacts: list[dict[str, object]]
    next_chunk: dict[str, int]

    @property
    def accepted_estimated_tokens(self) -> int:
        return sum(self.item_tokens.values())

    @property
    def accepted_documents(self) -> int:
        return len(self.fit_hashes)


ProgressSink = Callable[[ProgressEvent], object]


def _validate_request(request: LocalSampleRequest) -> dict[str, dict[str, Any]]:
    if (
        not isinstance(request.chunk_bytes, int)
        or isinstance(request.chunk_bytes, bool)
        or request.chunk_bytes < 1
    ):
        raise ValueError("chunk_bytes must be positive.")
    interval = request.progress_interval_seconds
    if (
        not isinstance(interval, (int, float))
        or isinstance(interval, bool)
        or not math.isfinite(float(interval))
        or interval < 0
    ):
        raise ValueError("progress_interval_seconds must be non-negative.")
    items = _validated_plan_items(request.registry, request.plan)
    buffer_size = request.plan.get("buffer_size")
    if (
        not isinstance(buffer_size, int)
        or isinstance(buffer_size, bool)
        or buffer_size < 1
    ):
        raise ValueError("plan buffer_size must be a positive integer.")
    seed = request.plan.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("plan seed must be an integer.")
    fraction = request.plan.get("validation_fraction", 0.0)
    if (
        not isinstance(fraction, (int, float))
        or isinstance(fraction, bool)
        or not math.isfinite(float(fraction))
        or not 0 <= float(fraction) < 1
    ):
        raise ValueError("plan validation_fraction must be in [0, 1).")
    return items


def _build_identity(request: LocalSampleRequest) -> BuildIdentity:
    format_description = {
        "version": _FORMAT_VERSION,
        "encoding": "utf-8",
        "json": {"ensure_ascii": False, "sort_keys": True},
        "chunk_bytes": request.chunk_bytes,
    }
    return BuildIdentity(
        version=1,
        mode="tokenizer_sample",
        plan_sha256=sha256_json(request.plan),
        source_registry_sha256=sha256_json(asdict(request.registry)),
        contamination_sha256=pattern_fingerprint(
            request.quality_policy.contamination_patterns
        ),
        quality_policy_sha256=sha256_json(asdict(request.quality_policy)),
        tokenizer_sha256=None,
        format_sha256=sha256_json(format_description),
    )


def _artifact_paths(units: Iterable[UnitCommit]) -> set[str]:
    return {
        str(artifact["path"])
        for unit in units
        for artifact in unit.artifacts
    }


def _cleanup_uncommitted_files(output_dir: Path, committed_paths: set[str]) -> None:
    for split in ("fit", "holdout"):
        split_dir = output_dir / split
        if not split_dir.exists():
            continue
        for path in split_dir.iterdir():
            relative = path.relative_to(output_dir).as_posix()
            if path.name.endswith(".tmp") or (
                _CHUNK_NAME.fullmatch(path.name) and relative not in committed_paths
            ):
                path.unlink()
    temporary_manifest = output_dir / "manifest.json.tmp"
    if temporary_manifest.exists():
        temporary_manifest.unlink()
    final_manifest = output_dir / "manifest.json"
    if final_manifest.exists():
        final_manifest.unlink()


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Committed artifact {path} has invalid JSON on line {line_number}."
                ) from error
            if not isinstance(record, dict):
                raise ValueError(f"Committed artifact {path} contains a non-object row.")
            yield record


def _load_state(
    output_dir: Path,
    units: tuple[UnitCommit, ...],
    items: Mapping[str, Mapping[str, Any]],
) -> _SampleState:
    committed_paths = _artifact_paths(units)
    _cleanup_uncommitted_files(output_dir, committed_paths)
    item_tokens = {item_id: 0 for item_id in items}
    fit_hashes: list[str] = []
    holdout_hashes: list[str] = []
    source_cursors: dict[str, int] = {}
    artifacts: list[dict[str, object]] = []
    next_chunk = {"fit": 0, "holdout": 0}

    for unit in units:
        source_cursors[unit.source_id] = max(
            source_cursors.get(unit.source_id, 0), unit.row_cursor
        )
        unit_hashes: set[str] = set()
        unit_fit_tokens = 0
        for artifact in unit.artifacts:
            relative = str(artifact["path"])
            path = output_dir / relative
            if (
                not path.is_file()
                or path.stat().st_size != int(artifact["size"])
                or sha256_file(path) != str(artifact["sha256"])
            ):
                raise ValueError(f"Committed artifact failed integrity check: {relative}")
            artifacts.append(dict(artifact))
            match = _CHUNK_NAME.fullmatch(path.name)
            if match is None or path.parent.name != match.group(1):
                raise ValueError(f"Committed sample artifact has invalid path: {relative}")
            split = match.group(1)
            next_chunk[split] = max(next_chunk[split], int(match.group(2)) + 1)
            for record in _iter_jsonl(path):
                digest = str(record["content_sha256"])
                unit_hashes.add(digest)
                if split == "fit":
                    item_id = _item_id(record)
                    if item_id not in item_tokens:
                        raise ValueError(
                            f"Committed artifact contains unplanned item {item_id!r}."
                        )
                    estimated_tokens = int(record["estimated_tokens"])
                    item_tokens[item_id] += estimated_tokens
                    unit_fit_tokens += estimated_tokens
                    fit_hashes.append(digest)
                else:
                    holdout_hashes.append(digest)
        if unit_hashes != set(unit.accepted_hashes):
            raise ValueError(f"Committed unit hash mismatch: {unit.unit_id}")
        if unit_fit_tokens != unit.quota_tokens:
            raise ValueError(f"Committed unit token mismatch: {unit.unit_id}")

    return _SampleState(
        item_tokens=item_tokens,
        fit_hashes=fit_hashes,
        holdout_hashes=holdout_hashes,
        source_cursors=source_cursors,
        artifacts=artifacts,
        next_chunk=next_chunk,
    )


def _line_bytes(record: Mapping[str, Any]) -> bytes:
    return (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _write_chunks(
    output_dir: Path,
    split: str,
    records: list[dict[str, Any]],
    *,
    chunk_bytes: int,
    start_index: int,
) -> tuple[list[dict[str, object]], int]:
    if not records:
        return [], start_index
    chunks: list[bytes] = []
    pending = bytearray()
    for record in records:
        line = _line_bytes(record)
        if pending and len(pending) + len(line) > chunk_bytes:
            chunks.append(bytes(pending))
            pending.clear()
        pending.extend(line)
        if len(pending) >= chunk_bytes:
            chunks.append(bytes(pending))
            pending.clear()
    if pending:
        chunks.append(bytes(pending))

    split_dir = output_dir / split
    split_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, object]] = []
    for offset, payload in enumerate(chunks):
        index = start_index + offset
        final_path = split_dir / f"{split}_{index:05d}.jsonl"
        temporary_path = final_path.with_suffix(".jsonl.tmp")
        with temporary_path.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(final_path)
        artifacts.append(
            {
                "path": final_path.relative_to(output_dir).as_posix(),
                "size": final_path.stat().st_size,
                "sha256": sha256_file(final_path),
            }
        )
    return artifacts, start_index + len(chunks)


def _emit_progress(
    sink: ProgressSink | None,
    *,
    stage: str,
    source_id: str,
    row_cursor: int,
    state: _SampleState,
    requested_tokens: int,
    started_at: float,
) -> None:
    if sink is None:
        return
    elapsed = max(0.0, time.monotonic() - started_at)
    rate = state.accepted_estimated_tokens / elapsed if elapsed > 0 else 0.0
    remaining = max(0, requested_tokens - state.accepted_estimated_tokens)
    eta = remaining / rate if rate > 0 else None
    sink(
        ProgressEvent(
            stage=stage,
            source_id=source_id,
            row_cursor=row_cursor,
            accepted_documents=state.accepted_documents,
            accepted_estimated_tokens=state.accepted_estimated_tokens,
            requested_estimated_tokens=requested_tokens,
            elapsed_seconds=elapsed,
            tokens_per_second=rate,
            eta_seconds=eta,
        )
    )


def _manifest(
    request: LocalSampleRequest,
    identity: BuildIdentity,
    state: _SampleState,
) -> dict[str, object]:
    artifacts = sorted(state.artifacts, key=lambda artifact: str(artifact["path"]))
    manifest: dict[str, object] = {
        "version": 1,
        "complete": True,
        "stage": str(request.plan["stage"]),
        "plan_sha256": str(request.plan["plan_sha256"]),
        "build_identity_sha256": identity.sha256,
        "requested_estimated_tokens": int(request.plan["total_tokens"]),
        "accepted_estimated_tokens": state.accepted_estimated_tokens,
        "accepted_documents": state.accepted_documents,
        "holdout_documents": len(state.holdout_hashes),
        "chunk_bytes": request.chunk_bytes,
        "fit_content_sha256": state.fit_hashes,
        "holdout_content_sha256": state.holdout_hashes,
        "artifacts": artifacts,
        "item_estimated_tokens": {
            item_id: state.item_tokens[item_id] for item_id in sorted(state.item_tokens)
        },
    }
    manifest["manifest_sha256"] = sha256_json(manifest)
    return manifest


def _write_manifest(output_dir: Path, manifest: Mapping[str, object]) -> None:
    temporary = output_dir / "manifest.json.tmp"
    final = output_dir / "manifest.json"
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(final)


def build_tokenizer_sample(
    request: LocalSampleRequest,
    dataset_loader=None,
    progress_sink=None,
    on_unit_committed=None,
) -> dict[str, object]:
    """Build or resume the deterministic candidate sample."""

    items = _validate_request(request)
    loader = _load_dataset_function(dataset_loader)
    output_dir = Path(request.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    identity = _build_identity(request)
    stage = str(request.plan["stage"])
    seed = int(request.plan["seed"])
    buffer_size = int(request.plan["buffer_size"])
    validation_fraction = float(request.plan.get("validation_fraction", 0.0))
    requested_tokens = int(request.plan["total_tokens"])
    source_ids = sorted({str(item["source_id"]) for item in items.values()})
    started_at = time.monotonic()
    last_progress_at = started_at
    last_source_id = source_ids[-1]
    last_cursor = 0

    with BuildJournal.open(request.state_path, identity) as journal:
        state = _load_state(output_dir, journal.units(), items)
        quality_filter = QualityFilter(request.quality_policy)
        last_cursor = state.source_cursors.get(last_source_id, 0)

        for source_index, source_id in enumerate(source_ids):
            source = request.registry.by_id[source_id]
            source_item_ids = sorted(
                item_id
                for item_id, item in items.items()
                if item["source_id"] == source_id
            )
            if all(
                state.item_tokens[item_id] >= int(items[item_id]["token_quota"])
                for item_id in source_item_ids
            ):
                continue

            raw_cursor = state.source_cursors.get(source_id, 0)
            dataset = loader(source.hf_name, **_loader_kwargs(source))
            skip = getattr(dataset, "skip", None)
            if raw_cursor:
                dataset = (
                    skip(raw_cursor)
                    if callable(skip)
                    else itertools.islice(dataset, raw_cursor, None)
                )

            for window in iter_deterministic_source_windows(
                source,
                dataset,
                stage,
                quality_filter,
                seed=seed,
                buffer_size=buffer_size,
                start_raw_cursor=raw_cursor,
            ):
                fit_records: list[dict[str, Any]] = []
                holdout_records: list[dict[str, Any]] = []
                pending_hashes: set[str] = set()
                committed_hashes = journal.committed_hashes(
                    str(record["content_sha256"]) for record in window.records
                )
                unit_tokens = 0

                for record in window.records:
                    item_id = _item_id(record)
                    if item_id not in source_item_ids:
                        raise ValueError(
                            f"Source {source.id!r} produced unplanned item {item_id!r}."
                        )
                    if state.item_tokens[item_id] >= int(
                        items[item_id]["token_quota"]
                    ):
                        if all(
                            state.item_tokens[planned]
                            >= int(items[planned]["token_quota"])
                            for planned in source_item_ids
                        ):
                            break
                        continue

                    digest = str(record["content_sha256"])
                    if digest in committed_hashes or digest in pending_hashes:
                        quality_filter.record_rejection("duplicate_exact")
                        continue
                    if not quality_filter.accept(record):
                        continue
                    pending_hashes.add(digest)

                    if is_validation_record(record, validation_fraction):
                        holdout_record = dict(record)
                        holdout_record["source_split"] = holdout_record["split"]
                        holdout_record["split"] = "holdout"
                        holdout_records.append(holdout_record)
                        continue

                    estimated_tokens = int(record["estimated_tokens"])
                    fit_records.append(record)
                    state.item_tokens[item_id] += estimated_tokens
                    state.fit_hashes.append(digest)
                    unit_tokens += estimated_tokens
                    if all(
                        state.item_tokens[planned]
                        >= int(items[planned]["token_quota"])
                        for planned in source_item_ids
                    ):
                        break

                artifacts: list[dict[str, object]] = []
                try:
                    fit_artifacts, state.next_chunk["fit"] = _write_chunks(
                        output_dir,
                        "fit",
                        fit_records,
                        chunk_bytes=request.chunk_bytes,
                        start_index=state.next_chunk["fit"],
                    )
                    holdout_artifacts, state.next_chunk["holdout"] = _write_chunks(
                        output_dir,
                        "holdout",
                        holdout_records,
                        chunk_bytes=request.chunk_bytes,
                        start_index=state.next_chunk["holdout"],
                    )
                    artifacts.extend(fit_artifacts)
                    artifacts.extend(holdout_artifacts)
                    unit = UnitCommit(
                        unit_id=(
                            f"{stage}-{source_index:05d}-"
                            f"{window.next_raw_cursor:020d}"
                        ),
                        stage=stage,
                        source_id=source.id,
                        row_cursor=window.next_raw_cursor,
                        quota_tokens=unit_tokens,
                        accepted_hashes=tuple(sorted(pending_hashes)),
                        artifacts=tuple(artifacts),
                    )
                    journal.commit_unit(unit)
                except Exception:
                    for artifact in artifacts:
                        path = output_dir / str(artifact["path"])
                        if path.exists():
                            path.unlink()
                    raise

                state.holdout_hashes.extend(
                    str(record["content_sha256"]) for record in holdout_records
                )
                state.source_cursors[source_id] = window.next_raw_cursor
                state.artifacts.extend(artifacts)
                last_source_id = source_id
                last_cursor = window.next_raw_cursor
                now = time.monotonic()
                if (
                    request.progress_interval_seconds == 0
                    or now - last_progress_at >= request.progress_interval_seconds
                ):
                    _emit_progress(
                        progress_sink,
                        stage=stage,
                        source_id=source_id,
                        row_cursor=last_cursor,
                        state=state,
                        requested_tokens=requested_tokens,
                        started_at=started_at,
                    )
                    last_progress_at = now
                if on_unit_committed is not None:
                    on_unit_committed(unit)

                if all(
                    state.item_tokens[item_id] >= int(items[item_id]["token_quota"])
                    for item_id in source_item_ids
                ):
                    break

            incomplete = [
                item_id
                for item_id in source_item_ids
                if state.item_tokens[item_id] < int(items[item_id]["token_quota"])
            ]
            if incomplete:
                details = ", ".join(
                    f"{item_id}={state.item_tokens[item_id]}/"
                    f"{items[item_id]['token_quota']}"
                    for item_id in incomplete
                )
                raise ValueError(
                    f"Source {source.id!r} exhausted before quota for stage "
                    f"{stage!r}: {details}"
                )

        manifest = _manifest(request, identity, state)
        _write_manifest(output_dir, manifest)
        _emit_progress(
            progress_sink,
            stage=stage,
            source_id=last_source_id,
            row_cursor=last_cursor,
            state=state,
            requested_tokens=requested_tokens,
            started_at=started_at,
        )
        return manifest
