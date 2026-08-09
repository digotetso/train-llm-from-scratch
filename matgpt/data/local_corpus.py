"""One-pass, restart-safe local construction of the approved Telco corpus."""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import re
import signal
import time
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


def build_local_corpus(
    request: LocalCorpusRequest,
    *,
    dataset_loader=None,
    on_unit_committed: Callable[[UnitCommit], object] | None = None,
    stop_after_quota_tokens: int | None = None,
) -> LocalCorpusResult:
    """Build deterministic source windows without re-encoding accepted rows."""

    global _STOP_REQUESTED
    _STOP_REQUESTED = False
    _validate_request(request)
    tokenizer_sha = _selected_tokenizer_sha(request)
    tokenizer = load_tokenizer(request.tokenizer_dir)
    identity = _identity(request, tokenizer_sha)
    local_root = Path(request.local_root)
    destination_root = Path(request.destination_root)
    require_managed_path(local_root, local_root, kind="directory")
    require_managed_path(destination_root, destination_root, kind="directory")
    local_root.mkdir(parents=True, exist_ok=True)
    loader = _load_dataset_function(dataset_loader)
    journal_path = local_root / "corpus.sqlite3"
    publisher = None
    _install_sigint_handler()
    with BuildJournal.open(journal_path, identity, managed_root=local_root) as journal:
        _cleanup_uncommitted_partials(local_root, journal)
        publisher = DrivePublisher(
            local_root=local_root,
            destination_root=destination_root,
            policy=StoragePolicy(request.max_working_bytes, request.min_free_bytes),
            journal=journal,
        )
        publisher.reconcile()
        counters, cursors = _state(journal)
        quality = QualityFilter(request.quality_policy, track_seen_hashes=False)
        for plan in request.plans:
            stage = str(plan["stage"])
            items = _validated_plan_items(request.registry, plan)
            for source_id in sorted({str(item["source_id"]) for item in items.values()}):
                source = request.registry.by_id[source_id]
                source_items = [key for key, item in items.items() if item["source_id"] == source_id]
                if all(counters.get((stage, key), 0) >= int(items[key]["token_quota"]) for key in source_items):
                    continue
                raw_cursor = cursors.get((stage, source_id), 0)
                dataset = _load_with_retries(loader, source, request.retry_delays)
                skip = getattr(dataset, "skip", None)
                if raw_cursor:
                    import itertools
                    dataset = skip(raw_cursor) if callable(skip) else itertools.islice(dataset, raw_cursor, None)
                for window in iter_deterministic_source_windows(
                    source, dataset, stage, quality, seed=int(plan["seed"]),
                    buffer_size=int(plan["buffer_size"]), start_raw_cursor=raw_cursor,
                ):
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
                        if digest in committed or digest in pending:
                            quality.record_rejection("duplicate_exact")
                            continue
                        if not quality.accept(row):
                            continue
                        pending.add(digest)
                        accepted.append(row)
                    fit: list[dict[str, Any]] = []
                    holdout: list[dict[str, Any]] = []
                    accepted_hashes: list[str] = []
                    unit_tokens = 0
                    for offset in range(0, len(accepted), request.batch_documents):
                        for encoded_row in encode_record_batch(
                            tokenizer, accepted[offset : offset + request.batch_documents]
                        ):
                            row = dict(encoded_row.record)
                            item_id = _item_id(row)
                            if is_validation_record(row, float(plan.get("validation_fraction", 0.0))):
                                row["split"] = "holdout"
                                row["token_ids"] = list(encoded_row.ids)
                                holdout.append(row)
                                accepted_hashes.append(str(row["content_sha256"]))
                                continue
                            row["split"] = "fit"
                            row["token_ids"] = list(encoded_row.ids)
                            fit.append(row)
                            accepted_hashes.append(str(row["content_sha256"]))
                            counters[(stage, item_id)] = counters.get((stage, item_id), 0) + len(encoded_row.ids)
                            unit_tokens += len(encoded_row.ids)
                    publisher.check_capacity(
                        _unit_storage_bytes(fit, holdout, tokenizer.token_to_id("<|eos|>"))
                    )
                    artifacts = _seal_unit(local_root, stage, source_id, window.next_raw_cursor, fit, holdout, tokenizer, request)
                    unit = UnitCommit(
                        unit_id=f"{stage}-{source_id}-{window.next_raw_cursor:020d}",
                        stage=stage, source_id=source_id, row_cursor=window.next_raw_cursor,
                        quota_tokens=unit_tokens, accepted_hashes=tuple(sorted(accepted_hashes)),
                        artifacts=tuple(artifacts), state={"item_counters": {key: value for (saved_stage, key), value in counters.items() if saved_stage == stage}},
                    )
                    journal.commit_unit(unit)
                    for artifact in artifacts:
                        publisher.publish(local_root / str(artifact["path"]), str(artifact["path"]), unit_id=unit.unit_id)
                    cursors[(stage, source_id)] = window.next_raw_cursor
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
                        ),
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
                            ),
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
                            ),
                        )
                        return LocalCorpusResult("stopped_cleanly", identity.sha256, total, None)
                missing = [key for key in source_items if counters.get((stage, key), 0) < int(items[key]["token_quota"])]
                if missing:
                    raise ValueError(f"Source {source_id!r} exhausted before quota")
        manifest = _manifest(identity, counters, journal)
        _write_manifest(destination_root, manifest)
        total = sum(counters.values())
        _write_progress(
            local_root,
            LocalCorpusProgress(
                stage=str(request.plans[-1]["stage"]),
                source_id="complete",
                row_cursor=0,
                accepted_quota_tokens=total,
                status="complete",
            ),
        )
        return LocalCorpusResult("complete", identity.sha256, total, manifest)


def _validate_request(request: LocalCorpusRequest) -> None:
    if not request.plans:
        raise ValueError("plans must be non-empty")
    if request.batch_documents < 1 or request.shard_size_tokens < 1 or request.raw_unit_bytes < 1:
        raise ValueError("batch and artifact bounds must be positive")
    if request.max_working_bytes < 0 or request.min_free_bytes < 0:
        raise ValueError("storage bounds must be non-negative")


def _selected_tokenizer_sha(request: LocalCorpusRequest) -> str:
    selection = Path(request.tokenizer_selection_path)
    if selection.name != "tokenizer_selection.json":
        raise ValueError("tokenizer selection must use canonical tokenizer_selection.json")
    data = json.loads(selection.read_text(encoding="utf-8"))
    required = {"version", "approved", "winner", "comparison_sha256", "selected_tokenizer_sha256", "operator_timestamp"}
    if not isinstance(data, Mapping) or set(data) != required:
        raise ValueError("approved tokenizer selection has an invalid schema")
    if data.get("version") != 1 or data.get("winner") not in {"pilot_20m", "representative_200m"}:
        raise ValueError("approved tokenizer selection has invalid provenance")
    if not isinstance(data.get("comparison_sha256"), str) or re.fullmatch(r"[0-9a-f]{64}", str(data["comparison_sha256"])) is None:
        raise ValueError("approved tokenizer selection has invalid comparison provenance")
    if not isinstance(data.get("operator_timestamp"), str) or not data["operator_timestamp"].strip():
        raise ValueError("approved tokenizer selection is missing operator provenance")
    actual = sha256_file(Path(request.tokenizer_dir) / "tokenizer.json")
    metadata = load_tokenizer_metadata(request.tokenizer_dir)
    if data.get("approved") is not True or data.get("selected_tokenizer_sha256") != actual:
        raise ValueError("approved tokenizer selection does not match tokenizer")
    if metadata.get("tokenizer_sha256") != actual:
        raise ValueError("tokenizer metadata checksum mismatch")
    return actual


def _identity(request: LocalCorpusRequest, tokenizer_sha: str) -> BuildIdentity:
    return BuildIdentity(1, "local_corpus", sha256_json(list(request.plans)), sha256_json(asdict(request.registry)), sha256_json(request.quality_policy.contamination_patterns), sha256_json(asdict(request.quality_policy)), tokenizer_sha, sha256_json({"raw_unit_bytes": request.raw_unit_bytes, "shard_size_tokens": request.shard_size_tokens}))


def _load_with_retries(loader, source, delays):
    for attempt in range(len(delays) + 1):
        try:
            return loader(source.hf_name, **_loader_kwargs(source))
        except (TimeoutError, ConnectionError):
            if attempt == len(delays):
                raise
            time.sleep(float(delays[attempt]))
    raise RuntimeError("unreachable")


def _state(journal: BuildJournal):
    counters: dict[tuple[str, str], int] = {}
    cursors: dict[tuple[str, str], int] = {}
    for unit in journal.iter_units():
        cursors[(unit.stage, unit.source_id)] = max(cursors.get((unit.stage, unit.source_id), 0), unit.row_cursor)
        values = unit.state.get("item_counters", {})
        if isinstance(values, Mapping):
            for item, value in values.items():
                if isinstance(value, int): counters[(unit.stage, str(item))] = value
    return counters, cursors


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


def _manifest(identity, counters, journal):
    artifacts = tuple(journal.iter_artifacts())
    manifest = {"version": 1, "complete": True, "build_identity_sha256": identity.sha256, "quota_counting": {"method": "tokenizer_exact_one_pass"}, "quality_filter": {"exact_dedup": True}, "item_quota_tokens": {f"{stage}:{item}": value for (stage, item), value in sorted(counters.items())}, "artifacts": artifacts}
    manifest["content_sha256"] = sha256_json(manifest)
    return manifest


def _write_manifest(destination_root, manifest):
    destination_root.mkdir(parents=True, exist_ok=True)
    temporary = destination_root / "manifest.json.partial"
    final = destination_root / "manifest.json"
    with open_exclusive_nofollow(temporary, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, sort_keys=True); handle.flush(); os.fsync(handle.fileno())
    os.rename(temporary, final)


def _write_progress(root: Path, progress: LocalCorpusProgress) -> None:
    """Atomically persist operator-visible state without changing build identity."""

    partial = root / "progress.json.partial"
    final = root / "progress.json"
    if partial.exists():
        partial.unlink()
    payload = {**asdict(progress), "updated_at": time.time()}
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


def _install_sigint_handler() -> None:
    """Request a clean stop at the next durable unit boundary."""

    def request_stop(_signal_number: int, _frame: object) -> None:
        global _STOP_REQUESTED
        _STOP_REQUESTED = True

    try:
        signal.signal(signal.SIGINT, request_stop)
    except ValueError:
        # Tests and embedded callers can run outside the main interpreter thread.
        return


def _cleanup_uncommitted_partials(root: Path, journal: BuildJournal) -> None:
    """Remove only uncommitted partial files after the journal identity verifies."""

    for path in root.rglob("*.partial"):
        managed = require_managed_path(root, path, kind="file", allow_missing=False)
        relative = managed.relative_to(root).as_posix()
        if journal.has_artifact(relative):
            raise ValueError(f"committed artifact cannot be a partial file: {relative}")
        managed.unlink()
