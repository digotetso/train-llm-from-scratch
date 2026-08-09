"""One-pass, restart-safe local construction of the approved Telco corpus."""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import re
import signal
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


@dataclass(frozen=True)
class LocalCorpusRequest:
    registry: SourceRegistry
    plans: tuple[Mapping[str, object], ...]
    tokenizer_dir: Path
    tokenizer_selection_path: Path
    local_root: Path
    destination_root: Path
    quality_policy: DataQualityPolicy
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


def _build_local_corpus(
    request: LocalCorpusRequest,
    *,
    dataset_loader=None,
    on_unit_committed: Callable[[UnitCommit], object] | None = None,
    stop_after_quota_tokens: int | None = None,
) -> LocalCorpusResult:
    """Build deterministic source windows without re-encoding accepted rows."""

    _validate_request(request)
    tokenizer_sha, selection_sha, comparison_sha = _selected_tokenizer_sha(request)
    tokenizer = load_tokenizer(request.tokenizer_dir)
    identity = _identity(request, tokenizer_sha, selection_sha, comparison_sha)
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
        quality = QualityFilter(request.quality_policy, track_seen_hashes=False)
        _restore_quality(quality, cumulative.get("quality", {}))
        discarded_after_quota: set[str] = set()
        for plan in request.plans:
            stage = str(plan["stage"])
            items = _validated_plan_items(request.registry, plan)
            for source_id in sorted({str(item["source_id"]) for item in items.values()}):
                source = request.registry.by_id[source_id]
                source_items = [key for key, item in items.items() if item["source_id"] == source_id]
                if all(counters.get((stage, key), 0) >= int(items[key]["token_quota"]) for key in source_items):
                    continue
                raw_cursor = cursors.get((stage, source_id), 0)
                dataset = _retrying_dataset(
                    loader, source, request.retry_delays, start_raw_cursor=raw_cursor
                )
                pending_fit: list[dict[str, Any]] = []
                pending_holdout: list[dict[str, Any]] = []
                pending_hashes: list[str] = []
                pending_seen: set[str] = set()
                pending_tokens = 0
                for window in iter_deterministic_source_windows(
                    source, dataset, stage, quality, seed=int(plan["seed"]),
                    buffer_size=int(plan["buffer_size"]), start_raw_cursor=raw_cursor,
                ):
                    cumulative["read"]["documents"] += len(window.records)
                    committed = journal.committed_hashes(str(row["content_sha256"]) for row in window.records)
                    accepted: list[dict[str, Any]] = []
                    pending: set[str] = set()
                    for row in window.records:
                        item_id = _item_id(row)
                        if item_id not in items:
                            raise ValueError(f"Source {source_id!r} produced unplanned item {item_id!r}.")
                        if counters.get((stage, item_id), 0) >= int(items[item_id]["token_quota"]):
                            continue
                        digest = str(row["content_sha256"])
                        if digest in discarded_after_quota:
                            continue
                        if digest in committed or digest in pending or digest in pending_seen:
                            quality.record_rejection("duplicate_exact")
                            continue
                        if not quality.accept(row):
                            continue
                        pending.add(digest)
                        accepted.append(row)
                    fit: list[dict[str, Any]] = []
                    holdout: list[dict[str, Any]] = []
                    accepted_hashes: list[str] = []
                    window_tokens = 0
                    for offset in range(0, len(accepted), request.batch_documents):
                        for encoded_row in encode_record_batch(
                            tokenizer, accepted[offset : offset + request.batch_documents]
                        ):
                            row = dict(encoded_row.record)
                            item_id = _item_id(row)
                            if counters.get((stage, item_id), 0) >= int(
                                items[item_id]["token_quota"]
                            ):
                                discarded_after_quota.add(str(row["content_sha256"]))
                                continue
                            if is_validation_record(row, float(plan.get("validation_fraction", 0.0))):
                                row["source_split"] = row["split"]
                                row["split"] = "holdout"
                                row["token_ids"] = list(encoded_row.ids)
                                holdout.append(row)
                                accepted_hashes.append(str(row["content_sha256"]))
                                _accepted(cumulative, row, len(encoded_row.ids), "holdout")
                                continue
                            row["source_split"] = row["split"]
                            row["split"] = "fit"
                            row["token_ids"] = list(encoded_row.ids)
                            fit.append(row)
                            accepted_hashes.append(str(row["content_sha256"]))
                            counters[(stage, item_id)] = counters.get((stage, item_id), 0) + len(encoded_row.ids)
                            window_tokens += len(encoded_row.ids)
                            _accepted(cumulative, row, len(encoded_row.ids), "fit")
                    pending_fit.extend(fit)
                    pending_holdout.extend(holdout)
                    pending_hashes.extend(accepted_hashes)
                    pending_seen.update(accepted_hashes)
                    pending_tokens += window_tokens
                    pending_bytes = _unit_storage_bytes(
                        pending_fit, pending_holdout, tokenizer.token_to_id("<|eos|>")
                    )
                    source_complete = all(
                        counters.get((stage, key), 0) >= int(items[key]["token_quota"])
                        for key in source_items
                    )
                    # Units only seal at a completed deterministic window boundary.
                    # A single oversize window is accepted, then sealed immediately.
                    if not (
                        pending_bytes >= request.raw_unit_bytes
                        or pending_tokens >= request.shard_size_tokens
                        or source_complete
                        or _STOP_REQUESTED
                        or (stop_after_quota_tokens is not None and sum(counters.values()) >= stop_after_quota_tokens)
                    ):
                        continue
                    publisher.check_capacity(
                        pending_bytes + _journal_overhead_bytes(pending_hashes)
                    )
                    artifacts = _seal_unit(local_root, stage, source_id, window.next_raw_cursor, pending_fit, pending_holdout, tokenizer, request)
                    cursors[(stage, source_id)] = window.next_raw_cursor
                    _refresh_cumulative(cumulative, quality, counters, cursors, stage, source_id, window.next_raw_cursor, pending_tokens, artifacts)
                    unit = UnitCommit(
                        unit_id=f"{stage}-{source_id}-{window.next_raw_cursor:020d}",
                        stage=stage, source_id=source_id, row_cursor=window.next_raw_cursor,
                        quota_tokens=pending_tokens, accepted_hashes=tuple(sorted(pending_hashes)),
                        artifacts=tuple(artifacts), state={
                            "version": 1,
                            "item_counters": {key: value for (saved_stage, key), value in counters.items() if saved_stage == stage},
                            "cumulative": cumulative,
                        },
                    )
                    journal.commit_unit(unit)
                    # Persist the deterministic destination mapping before the
                    # first copy, so a fresh process can finish a post-commit
                    # crash without guessing a destination.
                    for artifact in artifacts:
                        journal.record_destination(
                            unit.unit_id, str(artifact["path"]), str(artifact["path"])
                        )
                    for artifact in artifacts:
                        publisher.publish(local_root / str(artifact["path"]), str(artifact["path"]), unit_id=unit.unit_id)
                    pending_fit.clear()
                    pending_holdout.clear()
                    pending_hashes.clear()
                    pending_seen.clear()
                    pending_tokens = 0
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
                        ), cumulative=cumulative, publisher=publisher, interval_seconds=request.progress_interval_seconds,
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
                            ), cumulative=cumulative, publisher=publisher, interval_seconds=request.progress_interval_seconds,
                        )
                        return LocalCorpusResult("calibration_complete", identity.sha256, total, None)
                    if _STOP_REQUESTED:
                        _write_progress(
                            local_root,
                            LocalCorpusProgress(
                                stage=stage,
                                source_id=source_id,
                                row_cursor=window.next_raw_cursor,
                                accepted_quota_tokens=total,
                                status="stopped_cleanly",
                            ), cumulative=cumulative, publisher=publisher, interval_seconds=request.progress_interval_seconds,
                        )
                        return LocalCorpusResult("stopped_cleanly", identity.sha256, total, None)
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
            ), cumulative=cumulative, publisher=publisher, interval_seconds=request.progress_interval_seconds,
        )
        return LocalCorpusResult("provisional_complete", identity.sha256, total, manifest)


def build_local_corpus(
    request: LocalCorpusRequest,
    *,
    dataset_loader=None,
    on_unit_committed: Callable[[UnitCommit], object] | None = None,
    stop_after_quota_tokens: int | None = None,
) -> LocalCorpusResult:
    """Build a provisional, deterministic corpus and restore SIGINT on exit."""

    with _sigint_guard():
        return _build_local_corpus(
            request,
            dataset_loader=dataset_loader,
            on_unit_committed=on_unit_committed,
            stop_after_quota_tokens=stop_after_quota_tokens,
        )


def _validate_request(request: LocalCorpusRequest) -> None:
    if not request.plans:
        raise ValueError("plans must be non-empty")
    if request.batch_documents < 1 or request.shard_size_tokens < 1 or request.raw_unit_bytes < 1:
        raise ValueError("batch and artifact bounds must be positive")
    if request.max_working_bytes < 0 or request.min_free_bytes < 0:
        raise ValueError("storage bounds must be non-negative")
    quality = request.quality_policy
    if (
        quality.enabled is not True
        or quality.exact_dedup is not True
        or not quality.contamination_patterns
    ):
        raise ValueError("mandatory quality controls require enabled exact dedup and contamination evidence")


def _selected_tokenizer_sha(request: LocalCorpusRequest) -> tuple[str, str, str]:
    selection = Path(request.tokenizer_selection_path)
    if selection.name != "tokenizer_selection.json":
        raise ValueError("tokenizer selection must use canonical tokenizer_selection.json")
    data = json.loads(selection.read_text(encoding="utf-8"))
    comparison_path = selection.with_name("tokenizer_comparison.json")
    if not comparison_path.is_file():
        raise ValueError("approved tokenizer selection is missing canonical comparison evidence")
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping) or not isinstance(comparison, Mapping):
        raise ValueError("approved tokenizer selection comparison evidence is invalid")
    selected_sha = validate_tokenizer_selection(data, comparison)
    actual = sha256_file(Path(request.tokenizer_dir) / "tokenizer.json")
    metadata = load_tokenizer_metadata(request.tokenizer_dir)
    if selected_sha != actual:
        raise ValueError("approved tokenizer selection does not match tokenizer")
    if metadata.get("tokenizer_sha256") != actual:
        raise ValueError("tokenizer metadata checksum mismatch")
    return actual, sha256_file(selection), sha256_file(comparison_path)


def _identity(
    request: LocalCorpusRequest,
    tokenizer_sha: str,
    selection_sha: str,
    comparison_sha: str,
) -> BuildIdentity:
    return BuildIdentity(1, "local_corpus", sha256_json(list(request.plans)), sha256_json(asdict(request.registry)), sha256_json(request.quality_policy.contamination_patterns), sha256_json(asdict(request.quality_policy)), tokenizer_sha, sha256_json({"raw_unit_bytes": request.raw_unit_bytes, "shard_size_tokens": request.shard_size_tokens, "selection_sha256": selection_sha, "comparison_sha256": comparison_sha}))


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


def _retrying_dataset(loader, source, delays, *, start_raw_cursor: int):
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
        if isinstance(saved, Mapping) and int(saved.get("accepted", {}).get("tokens", -1)) >= int(cumulative["accepted"]["tokens"]):
            cumulative = json.loads(json.dumps(saved))
    return counters, cursors, cumulative


def _empty_cumulative() -> dict[str, Any]:
    return {
        "read": {"documents": 0, "chars": 0, "bytes": 0},
        "accepted": {"documents": 0, "tokens": 0, "chars": 0, "bytes": 0},
        "heldout": {"documents": 0, "tokens": 0, "chars": 0, "bytes": 0},
        "rejected": {"empty_text": 0, "duplicate_exact": 0, "benchmark_contamination": 0, "quality": 0},
        "licenses": {}, "validation": {"documents": 0, "tokens": 0, "chars": 0, "bytes": 0, "digest": None},
        "fit": {"documents": 0, "tokens": 0, "chars": 0, "bytes": 0},
        "item_quotas": {}, "source_cursors": {}, "packed": {"raw_units": 0, "shards": 0, "raw_bytes": 0, "token_bytes": 0},
        "quality": {}, "last_document": {}, "overshoot": {}, "last_unit": None,
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


def _accepted(cumulative: dict[str, Any], row: Mapping[str, Any], tokens: int, split: str) -> None:
    text = str(row.get("text", ""))
    raw_bytes = len(text.encode("utf-8"))
    target = cumulative["heldout"] if split == "holdout" else cumulative["accepted"]
    for name, value in (("documents", 1), ("tokens", tokens), ("chars", len(text)), ("bytes", raw_bytes)):
        target[name] += value
    if split == "fit":
        for name, value in (("documents", 1), ("tokens", tokens), ("chars", len(text)), ("bytes", raw_bytes)):
            cumulative["fit"][name] += value
    license_name = str(row.get("license", ""))
    cumulative["licenses"][license_name] = cumulative["licenses"].get(license_name, 0) + 1
    item = _item_id(row)
    cumulative["last_document"][item] = str(row.get("document_id", row.get("content_sha256", "")))


def _refresh_cumulative(cumulative, quality, counters, cursors, stage, source_id, cursor, unit_tokens, artifacts) -> None:
    report = quality.report()
    cumulative["quality"] = report
    reasons = report["rejection_reasons"]
    for name in cumulative["rejected"]:
        cumulative["rejected"][name] = int(reasons.get(name, 0))
    cumulative["item_quotas"] = {f"{saved_stage}:{item}": value for (saved_stage, item), value in sorted(counters.items())}
    cumulative["source_cursors"] = {f"{saved_stage}:{source}": value for (saved_stage, source), value in sorted(cursors.items())}
    cumulative["validation"] = dict(cumulative["heldout"])
    cumulative["validation"]["digest"] = sha256_json(cumulative["validation"])
    cumulative["packed"]["raw_units"] += 1
    cumulative["packed"]["shards"] += sum(1 for artifact in artifacts if str(artifact["path"]).endswith(".bin"))
    cumulative["packed"]["raw_bytes"] += sum(int(artifact["size"]) for artifact in artifacts if str(artifact["path"]).endswith(".jsonl"))
    cumulative["packed"]["token_bytes"] += sum(int(artifact["size"]) for artifact in artifacts if str(artifact["path"]).endswith(".bin"))
    cumulative["last_unit"] = {"stage": stage, "source_id": source_id, "row_cursor": cursor, "quota_tokens": unit_tokens}


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
    manifest = {"version": 1, "complete": False, "status": "provisional", "build_identity_sha256": identity.sha256, "quota_counting": {"method": "tokenizer_exact_one_pass"}, "quality_filter": {"exact_dedup": True}, "item_quota_tokens": {f"{stage}:{item}": value for (stage, item), value in sorted(counters.items())}, "artifacts": artifacts}
    manifest["content_sha256"] = sha256_json(manifest)
    return manifest


def _verify_published_units(journal: BuildJournal) -> None:
    """Task 3 may report a provisional result only after every unit is verified."""

    pending = [unit.unit_id for unit in journal.iter_units() if not unit.published]
    if pending:
        raise RuntimeError(f"provisional corpus has unpublished unit artifacts: {pending}")


def _write_progress(
    root: Path,
    progress: LocalCorpusProgress,
    *,
    cumulative: Mapping[str, Any] | None = None,
    publisher: DrivePublisher | None = None,
    interval_seconds: float = 0.0,
) -> None:
    """Atomically persist operator-visible state without changing build identity."""

    partial = root / "progress.json.partial"
    final = root / "progress.json"
    if partial.exists():
        partial.unlink()
    cumulative = cumulative or _empty_cumulative()
    now = time.time()
    previous = float(cumulative.get("progress", {}).get("last_emitted_at", 0.0))
    if progress.status == "running" and interval_seconds > 0 and now - previous < interval_seconds:
        return
    status = publisher.status() if publisher is not None else {}
    storage = status.get("storage")
    payload = {
        **asdict(progress),
        "updated_at": now,
        "item_quotas": cumulative.get("item_quotas", {}),
        "stage_quotas": cumulative.get("item_quotas", {}),
        "read": cumulative.get("read", {}),
        "accepted": cumulative.get("accepted", {}),
        "heldout": cumulative.get("heldout", {}),
        "rejected": cumulative.get("rejected", {}),
        "quality": cumulative.get("quality", {}),
        "last_unit": cumulative.get("last_unit"),
        "storage": {
            "active_bytes": getattr(storage, "active_bytes", 0),
            "free_bytes": getattr(storage, "free_bytes", 0),
            "unpublished_bytes": sum(int(item["size"]) for item in status.get("unpublished_artifacts", ())),
            "published_bytes": sum(int(item["size"]) for item in journal_artifacts(publisher)),
        },
        "throughput": {"overall_tokens_per_second": 0.0, "rolling_tokens_per_second": 0.0, "elapsed_seconds": 0.0, "eta_seconds": None},
        "rss_bytes": _rss_bytes(),
        "drive": {"verified": bool(publisher is not None), "status": "journal_consistent" if publisher is not None else "unavailable"},
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
    print(f"corpus {progress.status}: {progress.stage}/{progress.source_id} cursor={progress.row_cursor} tokens={progress.accepted_quota_tokens}")
    if isinstance(cumulative, dict):
        cumulative.setdefault("progress", {})["last_emitted_at"] = now


def journal_artifacts(publisher: DrivePublisher | None) -> tuple[dict[str, object], ...]:
    if publisher is None or publisher.journal is None:
        return ()
    return tuple(publisher.journal.iter_artifacts())


def _rss_bytes() -> int:
    try:
        import resource
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
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
