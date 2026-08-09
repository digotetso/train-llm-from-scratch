"""One-pass, restart-safe local construction of the approved Telco corpus."""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import re
import signal
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from matgpt.data.local_publish import DrivePublisher, StoragePolicy
from matgpt.data.local_state import BuildIdentity, BuildJournal, UnitCommit
from matgpt.data.local_tokens import PackedShardWriter, encode_record_batch
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
from matgpt.tokenizer.io import load_tokenizer, load_tokenizer_metadata
from matgpt.tokenizer.candidate import validate_tokenizer_selection
from matgpt.utils.hashing import sha256_file, sha256_json
from matgpt.utils.paths import open_exclusive_nofollow, require_managed_path


_STOP_REQUESTED = False
_EVIDENCE_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class LocalCorpusRequest:
    registry: SourceRegistry
    plans: tuple[Mapping[str, object], ...]
    tokenizer_dir: Path
    tokenizer_selection_path: Path
    local_root: Path
    destination_root: Path
    quality_policy: DataQualityPolicy
    evidence_root: Path
    batch_documents: int = 128
    shard_size_tokens: int = 50_000_000
    raw_unit_bytes: int = 268_435_456
    max_working_bytes: int = 20 * 1024**3
    min_free_bytes: int = 25 * 1024**3
    progress_interval_seconds: float = 30.0
    retry_delays: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0, 16.0)


@dataclass(frozen=True)
class LocalCorpusProgress:
    stage: str
    source_id: str
    row_cursor: int
    accepted_quota_tokens: int
    status: str


@dataclass(frozen=True)
class LocalCorpusResult:
    status: str
    build_identity_sha256: str
    accepted_quota_tokens: int
    manifest: Mapping[str, object] | None


@dataclass
class _ProgressRuntime:
    monotonic_clock: Callable[[], float]
    callback: Callable[[Mapping[str, Any]], object] | None
    started_at: float
    elapsed_base: float
    last_emitted_at: float | None
    last_emitted_tokens: int


def _build_local_corpus(
    request: LocalCorpusRequest,
    *,
    dataset_loader=None,
    on_unit_committed: Callable[[UnitCommit], object] | None = None,
    stop_after_quota_tokens: int | None = None,
    monotonic_clock: Callable[[], float] = time.monotonic,
    progress_callback: Callable[[Mapping[str, Any]], object] | None = None,
) -> LocalCorpusResult:
    """Build deterministic source windows without re-encoding accepted rows."""

    _validate_request(request)
    tokenizer_sha, selection_sha, comparison_sha, operational = _selected_tokenizer_sha(request)
    tokenizer = load_tokenizer(request.tokenizer_dir)
    identity = _identity(
        request, tokenizer_sha, selection_sha, comparison_sha, operational
    )
    local_root = Path(request.local_root)
    destination_root = Path(request.destination_root)
    require_managed_path(local_root, local_root, kind="directory")
    require_managed_path(destination_root, destination_root, kind="directory")
    local_root.mkdir(parents=True, exist_ok=True)
    loader = _load_dataset_function(dataset_loader)
    journal_path = local_root / "corpus.sqlite3"
    publisher = None
    with BuildJournal.open(journal_path, identity, managed_root=local_root) as journal:
        _cleanup_uncommitted_partials(local_root, journal)
        publisher = DrivePublisher(
            local_root=local_root,
            destination_root=destination_root,
            policy=StoragePolicy(request.max_working_bytes, request.min_free_bytes),
            journal=journal,
        )
        publisher.reconcile()
        counters, cursors, cumulative = _state(journal)
        progress_runtime = _progress_runtime(
            cumulative, monotonic_clock, progress_callback
        )
        quality = QualityFilter(request.quality_policy, track_seen_hashes=False)
        _restore_quality(quality, cumulative.get("quality", {}))
        for plan in request.plans:
            stage = str(plan["stage"])
            items = _validated_plan_items(request.registry, plan)
            for source_id in sorted({str(item["source_id"]) for item in items.values()}):
                source = request.registry.by_id[source_id]
                source_items = [key for key, item in items.items() if item["source_id"] == source_id]
                if all(counters.get((stage, key), 0) >= int(items[key]["token_quota"]) for key in source_items):
                    continue
                raw_cursor = cursors.get((stage, source_id), 0)

                def observe_raw_row(row: Mapping[str, Any]) -> None:
                    raw_text = row.get(source.text_field) if source.text_field else ""
                    text = "" if raw_text is None else str(raw_text)
                    cumulative["raw"]["documents"] += 1
                    cumulative["raw"]["chars"] += len(text)
                    cumulative["raw"]["bytes"] += _json_line_size(row)
                    cumulative["read"] = dict(cumulative["raw"])

                dataset = _retrying_dataset(
                    loader,
                    source,
                    request.retry_delays,
                    start_raw_cursor=raw_cursor,
                    on_raw_row=observe_raw_row,
                )
                pending_fit: list[dict[str, Any]] = []
                pending_holdout: list[dict[str, Any]] = []
                pending_hashes: list[str] = []
                pending_seen: set[str] = set()
                pending_tokens = 0
                pending_raw_bytes = 0
                pending_token_bytes = 0
                for window in iter_deterministic_source_windows(
                    source, dataset, stage, quality, seed=int(plan["seed"]),
                    buffer_size=int(plan["buffer_size"]), start_raw_cursor=raw_cursor,
                ):
                    # The cursor counts raw source rows; normalized records are
                    # tracked separately so empty/rejected input is not hidden.
                    cumulative["normalized"]["documents"] += len(window.records)
                    cumulative["normalized"]["chars"] += sum(
                        len(str(row["text"])) for row in window.records
                    )
                    cumulative["normalized"]["bytes"] += sum(
                        len(str(row["text"]).encode("utf-8")) for row in window.records
                    )
                    committed = journal.committed_hashes(str(row["content_sha256"]) for row in window.records)
                    accepted: list[dict[str, Any]] = []
                    pending: set[str] = set()
                    for row in window.records:
                        item_id = _item_id(row)
                        if item_id not in items:
                            raise ValueError(f"Source {source_id!r} produced unplanned item {item_id!r}.")
                        digest = str(row["content_sha256"])
                        if digest in committed or digest in pending or digest in pending_seen:
                            quality.record_rejection("duplicate_exact")
                            continue
                        if not quality.accept(row):
                            continue
                        if counters.get((stage, item_id), 0) >= int(
                            items[item_id]["token_quota"]
                        ):
                            _quota_discarded(cumulative, row, None)
                            continue
                        pending.add(digest)
                        accepted.append(row)
                    fit: list[dict[str, Any]] = []
                    holdout: list[dict[str, Any]] = []
                    accepted_hashes: list[str] = []
                    window_tokens = 0
                    before_item_tokens = {key: counters.get((stage, key), 0) for key in source_items}
                    for offset in range(0, len(accepted), request.batch_documents):
                        for encoded_row in encode_record_batch(
                            tokenizer, accepted[offset : offset + request.batch_documents]
                        ):
                            row = dict(encoded_row.record)
                            item_id = _item_id(row)
                            if counters.get((stage, item_id), 0) >= int(
                                items[item_id]["token_quota"]
                            ):
                                _quota_discarded(cumulative, row, len(encoded_row.ids))
                                continue
                            if is_validation_record(row, float(plan.get("validation_fraction", 0.0))):
                                row["source_split"] = row["split"]
                                row["split"] = "holdout"
                                row["token_ids"] = list(encoded_row.ids)
                                holdout.append(row)
                                accepted_hashes.append(str(row["content_sha256"]))
                                _accepted(
                                    cumulative,
                                    row,
                                    len(encoded_row.ids),
                                    "holdout",
                                    stage=stage,
                                    requested_tokens=int(items[item_id]["token_quota"]),
                                    actual_tokens=counters.get((stage, item_id), 0),
                                )
                                continue
                            row["source_split"] = row["split"]
                            row["split"] = "fit"
                            row["token_ids"] = list(encoded_row.ids)
                            fit.append(row)
                            accepted_hashes.append(str(row["content_sha256"]))
                            counters[(stage, item_id)] = counters.get((stage, item_id), 0) + len(encoded_row.ids)
                            window_tokens += len(encoded_row.ids)
                            _accepted(
                                cumulative,
                                row,
                                len(encoded_row.ids),
                                "fit",
                                stage=stage,
                                requested_tokens=int(items[item_id]["token_quota"]),
                                actual_tokens=counters[(stage, item_id)],
                            )
                    pending_fit.extend(fit)
                    pending_holdout.extend(holdout)
                    pending_hashes.extend(accepted_hashes)
                    pending_seen.update(accepted_hashes)
                    pending_tokens += window_tokens
                    pending_raw_bytes += sum(_json_line_size(row) for row in fit + holdout)
                    pending_token_bytes += sum(
                        (len(row["token_ids"]) + 1) * 2 for row in fit + holdout
                    )
                    pending_bytes = pending_raw_bytes + pending_token_bytes
                    _sync_quality_evidence(cumulative, quality)
                    source_complete = all(
                        counters.get((stage, key), 0) >= int(items[key]["token_quota"])
                        for key in source_items
                    )
                    item_reached = any(
                        before_item_tokens[key] < int(items[key]["token_quota"])
                        <= counters.get((stage, key), 0)
                        for key in source_items
                    )
                    # Units only seal at a completed deterministic window boundary.
                    # A single oversize window is accepted, then sealed immediately.
                    if not (
                        pending_bytes >= request.raw_unit_bytes
                        or pending_tokens >= request.shard_size_tokens
                        or item_reached
                        or source_complete
                        or _STOP_REQUESTED
                        or (stop_after_quota_tokens is not None and sum(counters.values()) >= stop_after_quota_tokens)
                    ):
                        _write_progress(
                            local_root,
                            LocalCorpusProgress(
                                stage=stage,
                                source_id=source_id,
                                row_cursor=window.next_raw_cursor,
                                accepted_quota_tokens=sum(counters.values()),
                                status="running",
                            ),
                            cumulative=cumulative,
                            publisher=publisher,
                            interval_seconds=request.progress_interval_seconds,
                            runtime=progress_runtime,
                            current=_current_progress_context(
                                stage, source_id, window.records, items, counters
                            ),
                            pending_unit=_pending_unit(
                                pending_fit,
                                pending_holdout,
                                pending_tokens,
                                pending_raw_bytes,
                                pending_token_bytes,
                                raw_cursor,
                                window.next_raw_cursor,
                            ),
                        )
                        continue
                    publisher.check_capacity(
                        pending_bytes + _journal_overhead_bytes(pending_hashes)
                    )
                    artifacts = _seal_unit(local_root, stage, source_id, window.next_raw_cursor, pending_fit, pending_holdout, tokenizer, request)
                    artifacts = [{**artifact, "destination_path": str(artifact["path"])} for artifact in artifacts]
                    cursors[(stage, source_id)] = window.next_raw_cursor
                    _snapshot_progress_state(
                        cumulative, progress_runtime, sum(counters.values())
                    )
                    _refresh_cumulative(cumulative, quality, counters, cursors, stage, source_id, window.next_raw_cursor, pending_tokens, artifacts)
                    unit = UnitCommit(
                        unit_id=f"{stage}-{source_id}-{window.next_raw_cursor:020d}",
                        stage=stage, source_id=source_id, row_cursor=window.next_raw_cursor,
                        quota_tokens=pending_tokens, accepted_hashes=tuple(sorted(pending_hashes)),
                        artifacts=tuple(artifacts), state={
                            "version": _EVIDENCE_SCHEMA_VERSION,
                            "item_counters": {key: value for (saved_stage, key), value in counters.items() if saved_stage == stage},
                            "cumulative": cumulative,
                        },
                    )
                    journal.commit_unit(unit)
                    for artifact in artifacts:
                        publisher.publish(local_root / str(artifact["path"]), str(artifact["path"]), unit_id=unit.unit_id)
                    pending_fit.clear()
                    pending_holdout.clear()
                    pending_hashes.clear()
                    pending_seen.clear()
                    pending_tokens = 0
                    pending_raw_bytes = 0
                    pending_token_bytes = 0
                    if on_unit_committed is not None:
                        on_unit_committed(unit)
                    total = sum(counters.values())
                    _write_progress(
                        local_root,
                        LocalCorpusProgress(
                            stage=stage,
                            source_id=source_id,
                            row_cursor=window.next_raw_cursor,
                            accepted_quota_tokens=total,
                            status="running",
                        ), cumulative=cumulative, publisher=publisher,
                        interval_seconds=request.progress_interval_seconds,
                        runtime=progress_runtime,
                        current=_current_progress_context(
                            stage, source_id, window.records, items, counters
                        ),
                        pending_unit=_pending_unit([], [], 0, 0, 0, window.next_raw_cursor, window.next_raw_cursor),
                    )
                    if stop_after_quota_tokens is not None and total >= stop_after_quota_tokens:
                        _write_progress(
                            local_root,
                            LocalCorpusProgress(
                                stage=stage,
                                source_id=source_id,
                                row_cursor=window.next_raw_cursor,
                                accepted_quota_tokens=total,
                                status="calibration_complete",
                            ), cumulative=cumulative, publisher=publisher,
                            interval_seconds=request.progress_interval_seconds,
                            runtime=progress_runtime,
                            current=_current_progress_context(
                                stage, source_id, window.records, items, counters
                            ),
                            pending_unit=_pending_unit([], [], 0, 0, 0, window.next_raw_cursor, window.next_raw_cursor),
                        )
                        return LocalCorpusResult("calibration_complete", identity.content_sha256, total, None)
                    if _STOP_REQUESTED:
                        _write_progress(
                            local_root,
                            LocalCorpusProgress(
                                stage=stage,
                                source_id=source_id,
                                row_cursor=window.next_raw_cursor,
                                accepted_quota_tokens=total,
                                status="stopped_cleanly",
                            ), cumulative=cumulative, publisher=publisher,
                            interval_seconds=request.progress_interval_seconds,
                            runtime=progress_runtime,
                            current=_current_progress_context(
                                stage, source_id, window.records, items, counters
                            ),
                            pending_unit=_pending_unit([], [], 0, 0, 0, window.next_raw_cursor, window.next_raw_cursor),
                        )
                        return LocalCorpusResult("stopped_cleanly", identity.content_sha256, total, None)
                    if all(
                        counters.get((stage, key), 0) >= int(items[key]["token_quota"])
                        for key in source_items
                    ):
                        break
                missing = [key for key in source_items if counters.get((stage, key), 0) < int(items[key]["token_quota"])]
                if missing:
                    raise ValueError(f"Source {source_id!r} exhausted before quota")
        _verify_published_units(journal)
        manifest = _manifest(identity, counters, journal)
        total = sum(counters.values())
        _write_progress(
            local_root,
            LocalCorpusProgress(
                stage=str(request.plans[-1]["stage"]),
                source_id="complete",
                row_cursor=0,
                accepted_quota_tokens=total,
                status="provisional_complete",
            ), cumulative=cumulative, publisher=publisher,
            interval_seconds=request.progress_interval_seconds,
            runtime=progress_runtime,
            current={
                "stage": str(request.plans[-1]["stage"]),
                "source_id": "complete",
                "bucket_id": None,
                "item_id": None,
                "item_requested_tokens": 0,
                "item_actual_tokens": 0,
                "stage_requested_tokens": int(request.plans[-1]["total_tokens"]),
                "stage_actual_tokens": sum(
                    value for (saved_stage, _item), value in counters.items()
                    if saved_stage == str(request.plans[-1]["stage"])
                ),
            },
            pending_unit=_pending_unit([], [], 0, 0, 0, 0, 0),
        )
        return LocalCorpusResult("provisional_complete", identity.content_sha256, total, manifest)


def build_local_corpus(
    request: LocalCorpusRequest,
    *,
    dataset_loader=None,
    on_unit_committed: Callable[[UnitCommit], object] | None = None,
    stop_after_quota_tokens: int | None = None,
    monotonic_clock: Callable[[], float] = time.monotonic,
    progress_callback: Callable[[Mapping[str, Any]], object] | None = None,
) -> LocalCorpusResult:
    """Build a provisional, deterministic corpus and restore SIGINT on exit."""

    with _sigint_guard():
        return _build_local_corpus(
            request,
            dataset_loader=dataset_loader,
            on_unit_committed=on_unit_committed,
            stop_after_quota_tokens=stop_after_quota_tokens,
            monotonic_clock=monotonic_clock,
            progress_callback=progress_callback,
        )


def _validate_request(request: LocalCorpusRequest) -> None:
    if not request.plans:
        raise ValueError("plans must be non-empty")
    if request.batch_documents < 1 or request.shard_size_tokens < 1 or request.raw_unit_bytes < 1:
        raise ValueError("batch and artifact bounds must be positive")
    if request.max_working_bytes < 0 or request.min_free_bytes < 0:
        raise ValueError("storage bounds must be non-negative")
    if request.progress_interval_seconds < 0:
        raise ValueError("progress interval must be non-negative")
    quality = request.quality_policy
    if (
        quality.enabled is not True
        or quality.exact_dedup is not True
        or not quality.contamination_patterns
    ):
        raise ValueError("mandatory quality controls require enabled exact dedup and contamination evidence")


def _selected_tokenizer_sha(
    request: LocalCorpusRequest,
) -> tuple[str, str, str, Mapping[str, str]]:
    if request.evidence_root is None:
        raise ValueError("evidence_root is required")
    evidence_root = require_managed_path(
        request.evidence_root,
        request.evidence_root,
        kind="directory",
        allow_missing=False,
    )
    selection = _absolute_lexical(request.tokenizer_selection_path)
    canonical_selection = evidence_root / "tokenizer_selection.json"
    if selection != canonical_selection:
        raise ValueError("tokenizer selection must be directly below evidence_root")
    selection = require_managed_path(
        evidence_root, canonical_selection, kind="file", allow_missing=False
    )
    data = json.loads(selection.read_text(encoding="utf-8"))
    comparison_path = evidence_root / "comparison.json"
    comparison_path = require_managed_path(
        evidence_root, comparison_path, kind="file", allow_missing=False
    )
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping) or not isinstance(comparison, Mapping):
        raise ValueError("approved tokenizer selection comparison evidence is invalid")
    selected_sha = validate_tokenizer_selection(data, comparison)
    tokenizer_dir = require_managed_path(
        evidence_root,
        request.tokenizer_dir,
        kind="directory",
        allow_missing=False,
    )
    if tokenizer_dir == evidence_root:
        raise ValueError("selected tokenizer must be beneath evidence_root")
    tokenizer_json = require_managed_path(
        evidence_root, tokenizer_dir / "tokenizer.json", kind="file", allow_missing=False
    )
    require_managed_path(
        evidence_root,
        tokenizer_dir / "special_tokens.json",
        kind="file",
        allow_missing=False,
    )
    destination_root = require_managed_path(
        evidence_root, request.destination_root, kind="directory"
    )
    if destination_root == evidence_root:
        raise ValueError("corpus destination must be a managed evidence_root descendant")
    actual = sha256_file(tokenizer_json)
    metadata = load_tokenizer_metadata(tokenizer_dir)
    if selected_sha != actual:
        raise ValueError("approved tokenizer selection does not match tokenizer")
    if metadata.get("tokenizer_sha256") != actual:
        raise ValueError("tokenizer metadata checksum mismatch")
    resolved_root = evidence_root.resolve(strict=True)
    namespace = destination_root.relative_to(evidence_root).as_posix()
    operational = {
        "evidence_root": str(resolved_root),
        "destination_namespace": namespace,
    }
    return actual, sha256_file(selection), sha256_file(comparison_path), operational


def _absolute_lexical(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(Path(path).expanduser())))


def _identity(
    request: LocalCorpusRequest,
    tokenizer_sha: str,
    selection_sha: str,
    comparison_sha: str,
    operational: Mapping[str, str],
) -> BuildIdentity:
    return BuildIdentity(
        version=1,
        mode="local_corpus",
        plan_sha256=sha256_json(list(request.plans)),
        source_registry_sha256=sha256_json(asdict(request.registry)),
        contamination_sha256=sha256_json(
            request.quality_policy.contamination_patterns
        ),
        quality_policy_sha256=sha256_json(asdict(request.quality_policy)),
        tokenizer_sha256=tokenizer_sha,
        format_sha256=sha256_json(
            {
                "raw_unit_bytes": request.raw_unit_bytes,
                "shard_size_tokens": request.shard_size_tokens,
                "evidence_schema_version": _EVIDENCE_SCHEMA_VERSION,
                "selection_sha256": selection_sha,
                "comparison_sha256": comparison_sha,
            }
        ),
        operational=operational,
    )


def _is_transient_error(error: BaseException) -> bool:
    """Classify only connection failures and retryable HTTP status failures."""

    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", getattr(error, "status_code", None))
    return isinstance(status, int) and (status in {408, 429} or 500 <= status <= 599)


def _load_with_retries(loader, source, delays):
    for attempt in range(len(delays) + 1):
        try:
            return loader(source.hf_name, **_loader_kwargs(source))
        except BaseException as error:
            if not _is_transient_error(error):
                raise
            if attempt == len(delays):
                raise
            time.sleep(float(delays[attempt]))
    raise RuntimeError("unreachable")


def _retrying_dataset(
    loader,
    source,
    delays,
    *,
    start_raw_cursor: int,
    on_raw_row: Callable[[Mapping[str, Any]], object] | None = None,
):
    """Reopen a transiently interrupted stream at its exact consumed raw offset.

    This tracks source rows, not accepted records; a failed partially filled
    deterministic window therefore resumes without duplicating or skipping a
    raw input.  Schema, license, fingerprint, and quota errors are deliberately
    not classified as retryable.
    """

    cursor = start_raw_cursor
    attempt = 0
    while True:
        dataset = _load_with_retries(loader, source, delays)
        skip = getattr(dataset, "skip", None)
        dataset = skip(cursor) if cursor and callable(skip) else itertools.islice(dataset, cursor, None)
        try:
            for row in dataset:
                cursor += 1
                attempt = 0
                if on_raw_row is not None:
                    on_raw_row(row)
                yield row
            return
        except BaseException as error:
            if not _is_transient_error(error) or attempt == len(delays):
                raise
            time.sleep(float(delays[attempt]))
            attempt += 1


def _state(journal: BuildJournal):
    counters: dict[tuple[str, str], int] = {}
    cursors: dict[tuple[str, str], int] = {}
    cumulative: dict[str, Any] = _empty_cumulative()
    for unit in journal.iter_units():
        cursors[(unit.stage, unit.source_id)] = max(cursors.get((unit.stage, unit.source_id), 0), unit.row_cursor)
        values = unit.state.get("item_counters", {})
        if isinstance(values, Mapping):
            for item, value in values.items():
                if isinstance(value, int): counters[(unit.stage, str(item))] = value
        saved = unit.state.get("cumulative")
        if isinstance(saved, Mapping) and int(saved.get("committed_units", 0)) >= int(cumulative["committed_units"]):
            cumulative = json.loads(json.dumps(saved))
    return counters, cursors, cumulative


def _empty_cumulative() -> dict[str, Any]:
    return {
        "committed_units": 0,
        "raw": {"documents": 0, "chars": 0, "bytes": 0},
        "read": {"documents": 0, "chars": 0, "bytes": 0},
        "normalized": {"documents": 0, "chars": 0, "bytes": 0},
        "accepted": {"documents": 0, "tokens": 0, "chars": 0, "bytes": 0},
        "heldout": {"documents": 0, "tokens": 0, "chars": 0, "bytes": 0},
        "corpus": {"documents": 0, "tokens": 0, "chars": 0, "bytes": 0, "raw_bytes": 0, "packed_tokens": 0},
        "quota_discarded": {
            "documents": 0,
            "encoded_documents": 0,
            "unencoded_documents": 0,
            "tokens": 0,
            "chars": 0,
            "bytes": 0,
        },
        "rejected": {
            "empty_text": 0,
            "too_short": 0,
            "too_long": 0,
            "duplicate_exact": 0,
            "benchmark_contamination": 0,
            "quality": 0,
        },
        "licenses": {},
        "validation": {
            "documents": 0, "tokens": 0, "packed_tokens": 0,
            "chars": 0, "bytes": 0, "raw_bytes": 0,
            "digest": "0" * 64,
            "identity_order_sha256": "0" * 64,
            "content_order_sha256": "0" * 64,
        },
        "fit": {"documents": 0, "tokens": 0, "packed_tokens": 0, "chars": 0, "bytes": 0, "raw_bytes": 0},
        "item_quotas": {}, "source_cursors": {}, "packed": {"raw_units": 0, "shards": 0, "raw_bytes": 0, "token_bytes": 0},
        "quality": {}, "items": {}, "last_document": {}, "overshoot": {}, "last_unit": None,
    }


def _restore_quality(quality: QualityFilter, saved: object) -> None:
    if not isinstance(saved, Mapping):
        return
    quality.total_documents = int(saved.get("total_documents", 0))
    quality.accepted_documents = int(saved.get("accepted_documents", 0))
    quality.rejected_documents = int(saved.get("rejected_documents", 0))
    reasons = saved.get("rejection_reasons", {})
    if isinstance(reasons, Mapping):
        quality.rejection_reasons.update({str(key): int(value) for key, value in reasons.items()})


def _accepted(
    cumulative: dict[str, Any],
    row: Mapping[str, Any],
    tokens: int,
    split: str,
    *,
    stage: str,
    requested_tokens: int,
    actual_tokens: int,
) -> None:
    text = str(row.get("text", ""))
    text_bytes = len(text.encode("utf-8"))
    raw_bytes = _json_line_size(row)
    packed_tokens = tokens + 1
    target = cumulative["heldout"] if split == "holdout" else cumulative["accepted"]
    for name, value in (("documents", 1), ("tokens", tokens), ("chars", len(text)), ("bytes", text_bytes)):
        target[name] += value
    split_target = cumulative["validation"] if split == "holdout" else cumulative["fit"]
    for name, value in (
        ("documents", 1), ("tokens", tokens), ("packed_tokens", packed_tokens),
        ("chars", len(text)), ("bytes", text_bytes), ("raw_bytes", raw_bytes),
    ):
        split_target[name] += value
    for name, value in (
        ("documents", 1), ("tokens", tokens), ("packed_tokens", packed_tokens),
        ("chars", len(text)), ("bytes", text_bytes), ("raw_bytes", raw_bytes),
    ):
        cumulative["corpus"][name] += value
    license_name = str(row.get("license", ""))
    cumulative["licenses"][license_name] = cumulative["licenses"].get(license_name, 0) + 1
    item = _item_id(row)
    cumulative["last_document"][item] = str(row.get("document_id", row.get("content_sha256", "")))
    item_key = f"{stage}:{item}"
    cumulative["items"][item_key] = {
        "requested_tokens": requested_tokens,
        "actual_tokens": actual_tokens,
        "last_document_tokens": tokens,
        "overshoot_tokens": max(0, actual_tokens - requested_tokens),
    }
    cumulative["overshoot"][item_key] = max(0, actual_tokens - requested_tokens)
    if split == "holdout":
        identity = ":".join(
            (
                str(row.get("stage", "")),
                str(row.get("source_id", "")),
                str(row.get("bucket_id", "")),
                str(row.get("document_id", "")),
                str(row.get("content_sha256", "")),
            )
        )
        cumulative["validation"]["identity_order_sha256"] = _chain_digest(
            str(cumulative["validation"]["identity_order_sha256"]), identity
        )
        cumulative["validation"]["digest"] = cumulative["validation"][
            "identity_order_sha256"
        ]
        cumulative["validation"]["content_order_sha256"] = _chain_digest(
            str(cumulative["validation"]["content_order_sha256"]),
            str(row.get("content_sha256", "")),
        )


def _quota_discarded(
    cumulative: dict[str, Any], row: Mapping[str, Any], tokens: int | None
) -> None:
    text = str(row.get("text", ""))
    for name, value in (
        ("documents", 1),
        ("chars", len(text)),
        ("bytes", len(text.encode("utf-8"))),
    ):
        cumulative["quota_discarded"][name] += value
    if tokens is None:
        cumulative["quota_discarded"]["unencoded_documents"] += 1
    else:
        cumulative["quota_discarded"]["encoded_documents"] += 1
        cumulative["quota_discarded"]["tokens"] += tokens


def _chain_digest(previous: str, value: str) -> str:
    return hashlib.sha256(bytes.fromhex(previous) + value.encode("utf-8")).hexdigest()


def _json_line_size(row: Mapping[str, Any]) -> int:
    return len(json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")) + 1


def _refresh_cumulative(cumulative, quality, counters, cursors, stage, source_id, cursor, unit_tokens, artifacts) -> None:
    _sync_quality_evidence(cumulative, quality)
    cumulative["item_quotas"] = {f"{saved_stage}:{item}": value for (saved_stage, item), value in sorted(counters.items())}
    cumulative["source_cursors"] = {f"{saved_stage}:{source}": value for (saved_stage, source), value in sorted(cursors.items())}
    cumulative["committed_units"] += 1
    cumulative["packed"]["raw_units"] += 1
    cumulative["packed"]["shards"] += sum(1 for artifact in artifacts if str(artifact["path"]).endswith(".bin"))
    cumulative["packed"]["raw_bytes"] += sum(int(artifact["size"]) for artifact in artifacts if str(artifact["path"]).endswith(".jsonl"))
    cumulative["packed"]["token_bytes"] += sum(int(artifact["size"]) for artifact in artifacts if str(artifact["path"]).endswith(".bin"))
    cumulative["last_unit"] = {"stage": stage, "source_id": source_id, "row_cursor": cursor, "quota_tokens": unit_tokens}


def _sync_quality_evidence(cumulative, quality) -> None:
    report = quality.report()
    cumulative["quality"] = report
    categories = {
        "empty_text", "too_short", "too_long", "duplicate_exact",
        "benchmark_contamination", "quality",
    }
    categories.update(str(name) for name in report["rejection_reasons"])
    cumulative["rejected"] = {
        name: int(report["rejection_reasons"].get(name, 0))
        for name in sorted(categories)
    }


def _seal_unit(root, stage, source_id, cursor, fit, holdout, tokenizer, request):
    unit_dir = root / "units" / f"{stage}-{source_id}-{cursor:020d}"
    unit_dir.mkdir(parents=True, exist_ok=True)
    artifacts = []
    for split, rows in (("fit", fit), ("holdout", holdout)):
        if rows:
            raw = unit_dir / f"{split}.jsonl"
            with open_exclusive_nofollow(raw, "w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush(); os.fsync(handle.fileno())
            artifacts.append({"path": raw.relative_to(root).as_posix(), "size": raw.stat().st_size, "sha256": sha256_file(raw)})
            writer = PackedShardWriter(output_dir=unit_dir, split=split, dtype="uint16", shard_size_tokens=request.shard_size_tokens, eos_id=tokenizer.token_to_id("<|eos|>"))
            for row in rows: writer.append_document(row["token_ids"])
            for shard in writer.finalize():
                path = Path(str(shard["path"]))
                artifacts.append({"path": path.relative_to(root).as_posix(), "size": path.stat().st_size, "sha256": sha256_file(path)})
    return artifacts


def _unit_storage_bytes(
    fit: list[Mapping[str, Any]], holdout: list[Mapping[str, Any]], eos_id: int | None
) -> int:
    """Conservative bounded local-space estimate before opening a unit."""

    if eos_id is None:
        raise ValueError("tokenizer must define <|eos|>")
    records = [*fit, *holdout]
    raw_bytes = sum(
        len(json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8")) + 1
        for record in records
    )
    token_bytes = sum((len(record["token_ids"]) + 1) * 2 for record in records)
    return raw_bytes + token_bytes


def _journal_overhead_bytes(hashes: list[str]) -> int:
    """Reserve SQLite/index metadata before retaining one more bounded unit."""

    # Hash key, row header, artifact rows, and conservative WAL amplification.
    return 256 + len(hashes) * 192


def _manifest(identity, counters, journal):
    artifacts = tuple(journal.iter_artifacts())
    manifest = {"version": 1, "complete": False, "status": "provisional", "build_identity_sha256": identity.content_sha256, "quota_counting": {"method": "tokenizer_exact_one_pass"}, "quality_filter": {"exact_dedup": True}, "item_quota_tokens": {f"{stage}:{item}": value for (stage, item), value in sorted(counters.items())}, "artifacts": artifacts}
    manifest["content_sha256"] = sha256_json(manifest)
    return manifest


def _verify_published_units(journal: BuildJournal) -> None:
    """Task 3 may report a provisional result only after every unit is verified."""

    pending = [unit.unit_id for unit in journal.iter_units() if not unit.published]
    if pending:
        raise RuntimeError(f"provisional corpus has unpublished unit artifacts: {pending}")


def _progress_runtime(
    cumulative: Mapping[str, Any],
    monotonic_clock: Callable[[], float],
    callback: Callable[[Mapping[str, Any]], object] | None,
) -> _ProgressRuntime:
    now = float(monotonic_clock())
    saved = cumulative.get("progress", {})
    if not isinstance(saved, Mapping):
        saved = {}
    return _ProgressRuntime(
        monotonic_clock=monotonic_clock,
        callback=callback,
        started_at=now,
        elapsed_base=float(saved.get("elapsed_seconds", 0.0)),
        last_emitted_at=None,
        last_emitted_tokens=int(saved.get("accepted_quota_tokens", 0)),
    )


def _snapshot_progress_state(
    cumulative: dict[str, Any], runtime: _ProgressRuntime, accepted_tokens: int
) -> None:
    now = float(runtime.monotonic_clock())
    cumulative["progress"] = {
        "elapsed_seconds": runtime.elapsed_base + max(0.0, now - runtime.started_at),
        "accepted_quota_tokens": accepted_tokens,
    }


def _current_progress_context(stage, source_id, records, items, counters):
    row = records[-1] if records else None
    item_id = _item_id(row) if row is not None else None
    item = items.get(item_id, {}) if item_id is not None else {}
    return {
        "stage": stage,
        "source_id": source_id,
        "bucket_id": row.get("bucket_id") if row is not None else None,
        "item_id": item_id,
        "item_requested_tokens": int(item.get("token_quota", 0)),
        "item_actual_tokens": counters.get((stage, item_id), 0) if item_id else 0,
        "stage_requested_tokens": sum(int(value["token_quota"]) for value in items.values()),
        "stage_actual_tokens": sum(
            value for (saved_stage, _item), value in counters.items()
            if saved_stage == stage
        ),
    }


def _pending_unit(
    fit, holdout, quota_tokens, raw_bytes, token_bytes, start_cursor, end_cursor
):
    return {
        "documents": len(fit) + len(holdout),
        "fit_documents": len(fit),
        "validation_documents": len(holdout),
        "quota_tokens": quota_tokens,
        "raw_bytes": raw_bytes,
        "token_bytes": token_bytes,
        "start_raw_cursor": start_cursor,
        "next_raw_cursor": end_cursor,
    }


def _write_progress(
    root: Path,
    progress: LocalCorpusProgress,
    *,
    cumulative: Mapping[str, Any] | None = None,
    publisher: DrivePublisher | None = None,
    interval_seconds: float = 0.0,
    runtime: _ProgressRuntime | None = None,
    current: Mapping[str, Any] | None = None,
    pending_unit: Mapping[str, Any] | None = None,
) -> Mapping[str, Any] | None:
    """Atomically persist operator-visible state without changing build identity."""

    partial = root / "progress.json.partial"
    final = root / "progress.json"
    if partial.exists():
        partial.unlink()
    cumulative = cumulative or _empty_cumulative()
    runtime = runtime or _progress_runtime(cumulative, time.monotonic, None)
    monotonic_now = float(runtime.monotonic_clock())
    if (
        progress.status == "running"
        and interval_seconds > 0
        and runtime.last_emitted_at is not None
        and monotonic_now - runtime.last_emitted_at < interval_seconds
    ):
        return None
    elapsed = runtime.elapsed_base + max(0.0, monotonic_now - runtime.started_at)
    process_elapsed = max(0.0, monotonic_now - runtime.started_at)
    since_last = (
        max(0.0, monotonic_now - runtime.last_emitted_at)
        if runtime.last_emitted_at is not None else process_elapsed
    )
    token_delta = progress.accepted_quota_tokens - runtime.last_emitted_tokens
    overall_rate = progress.accepted_quota_tokens / elapsed if elapsed > 0 else 0.0
    rolling_rate = token_delta / since_last if since_last > 0 else overall_rate
    current = dict(current or {})
    stage_requested = int(current.get("stage_requested_tokens", 0))
    stage_actual = int(current.get("stage_actual_tokens", 0))
    remaining = max(0, stage_requested - stage_actual)
    eta_rate = rolling_rate if rolling_rate > 0 else overall_rate
    status = publisher.status() if publisher is not None else {}
    storage = status.get("storage")
    unpublished = tuple(status.get("unpublished_artifacts", ()))
    published = (
        publisher.journal.published_artifacts()
        if publisher is not None and publisher.journal is not None else ()
    )
    units_verified = bool(
        publisher is not None
        and publisher.journal is not None
        and published
        and not unpublished
        and all(unit.published for unit in publisher.journal.iter_units())
    )
    payload = {
        **asdict(progress),
        "updated_at": time.time(),
        "current": {
            "stage": current.get("stage", progress.stage),
            "source_id": current.get("source_id", progress.source_id),
            "bucket_id": current.get("bucket_id"),
            "item_id": current.get("item_id"),
        },
        "item_quota": {
            "requested_tokens": int(current.get("item_requested_tokens", 0)),
            "actual_tokens": int(current.get("item_actual_tokens", 0)),
        },
        "stage_quota": {
            "requested_tokens": stage_requested,
            "actual_tokens": stage_actual,
        },
        "item_quotas": cumulative.get("item_quotas", {}),
        "stage_quotas": {
            "requested_tokens": stage_requested,
            "actual_tokens": stage_actual,
        },
        "read": cumulative.get("read", {}),
        "raw": cumulative.get("raw", {}),
        "normalized": cumulative.get("normalized", {}),
        "accepted": cumulative.get("accepted", {}),
        "heldout": cumulative.get("heldout", {}),
        "corpus": cumulative.get("corpus", {}),
        "quota_discarded": cumulative.get("quota_discarded", {}),
        "rejected": cumulative.get("rejected", {}),
        "quality": cumulative.get("quality", {}),
        "last_unit": cumulative.get("last_unit"),
        "pending_unit": dict(pending_unit or {}),
        "storage": {
            "active_bytes": getattr(storage, "active_bytes", 0),
            "free_bytes": getattr(storage, "free_bytes", 0),
            "unpublished_bytes": sum(int(item["size"]) for item in unpublished),
            "published_bytes": sum(int(item["size"]) for item in published),
        },
        "throughput": {
            "overall_tokens_per_second": overall_rate,
            "rolling_tokens_per_second": rolling_rate,
            "elapsed_seconds": elapsed,
            "eta_seconds": (
                remaining / eta_rate
                if remaining and eta_rate > 0
                else (0.0 if not remaining else None)
            ),
        },
        "rss_bytes": _rss_bytes(),
        "drive": {
            "verified": units_verified,
            "status": "journal_consistent" if units_verified else "pending_or_unavailable",
        },
    }
    with open_exclusive_nofollow(partial, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(partial, final)
    descriptor = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    print(
        f"corpus {progress.status}: {progress.stage}/{progress.source_id} "
        f"cursor={progress.row_cursor} tokens={progress.accepted_quota_tokens} "
        f"pending={int(payload['pending_unit'].get('documents', 0))} "
        f"rate={overall_rate:.2f}tok/s"
    )
    if isinstance(cumulative, dict):
        cumulative["progress"] = {
            "elapsed_seconds": elapsed,
            "accepted_quota_tokens": progress.accepted_quota_tokens,
        }
    runtime.last_emitted_at = monotonic_now
    runtime.last_emitted_tokens = progress.accepted_quota_tokens
    if runtime.callback is not None:
        runtime.callback(json.loads(json.dumps(payload)))
    return payload


def journal_artifacts(publisher: DrivePublisher | None) -> tuple[dict[str, object], ...]:
    if publisher is None or publisher.journal is None:
        return ()
    return tuple(publisher.journal.iter_artifacts())


def _rss_bytes() -> int:
    try:
        import resource
        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return value if sys.platform == "darwin" else value * 1024
    except (ImportError, AttributeError):
        return 0


@contextmanager
def _sigint_guard():
    """Request a clean stop at the next durable boundary and restore SIGINT."""

    global _STOP_REQUESTED
    _STOP_REQUESTED = False

    def request_stop(_signal_number: int, _frame: object) -> None:
        global _STOP_REQUESTED
        _STOP_REQUESTED = True

    try:
        previous = signal.signal(signal.SIGINT, request_stop)
    except ValueError:
        yield
        return
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)


def _cleanup_uncommitted_partials(root: Path, journal: BuildJournal) -> None:
    """Remove pre-commit unit artifacts only after the journal identity verifies."""

    units_root = root / "units"
    if not units_root.exists():
        return
    for path in sorted(units_root.rglob("*"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
            continue
        managed = require_managed_path(root, path, kind="file", allow_missing=False)
        relative = managed.relative_to(root).as_posix()
        if journal.has_artifact(relative):
            continue
        managed.unlink()
