"""Stream, normalize, and atomically publish Telco 300M corpus stages."""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

from matgpt.data.normalize import normalize_text
from matgpt.data.quality import DataQualityPolicy, QualityFilter
from matgpt.data.sources import (
    PRETRAIN_ROLES,
    SourceRegistry,
    SourceSpec,
    select_pretraining_sources,
)
from matgpt.tokenizer.io import load_tokenizer, load_tokenizer_metadata
from matgpt.utils.hashing import sha256_file, sha256_json, sha256_text
from matgpt.utils.paths import require_managed_path


DatasetLoader = Callable[..., Iterable[Mapping[str, Any]]]
QuotaTokenCounter = Callable[[Mapping[str, Any]], int]
QUOTA_AUDIT_VERSION = 2
QUOTA_AUDIT_METHOD = "tokenizer_exact_whole_document_boundary_v1"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class EmptySourceTextError(ValueError):
    """Raised when a source row's declared text normalizes to empty."""


def _positive_token_estimate(source: SourceSpec, row: Mapping[str, Any], text: str) -> int:
    if source.token_count_field:
        raw = row.get(source.token_count_field)
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ValueError(
                f"Source {source.id!r} row has invalid token estimate in "
                f"{source.token_count_field!r}."
            )
        estimate = int(raw)
        if estimate < 1:
            raise ValueError(
                f"Source {source.id!r} row has non-positive token estimate."
            )
        return estimate
    return max(1, math.ceil(len(text) / 4))


def _validated_tokenizer_sha256(tokenizer_dir: str | Path) -> str:
    base = Path(tokenizer_dir)
    tokenizer_path = base / "tokenizer.json"
    metadata = load_tokenizer_metadata(base)
    expected = metadata.get("tokenizer_sha256")
    actual = sha256_file(tokenizer_path)
    if not isinstance(expected, str) or actual != expected:
        raise ValueError(
            "Tokenizer SHA-256 does not match special_tokens.json; refusing "
            "exact quota collection."
        )
    return actual


def _quota_counter(
    tokenizer_dir: str | Path | None,
) -> tuple[QuotaTokenCounter, dict[str, Any]]:
    if tokenizer_dir is None:
        return (
            lambda record: int(record["estimated_tokens"]),
            {"method": "source_estimate", "tokenizer_sha256": None},
        )

    tokenizer_sha256 = _validated_tokenizer_sha256(tokenizer_dir)
    tokenizer = load_tokenizer(tokenizer_dir)

    def count(record: Mapping[str, Any]) -> int:
        return len(tokenizer.encode(str(record["text"])).ids)

    return count, {
        "method": "tokenizer_exact",
        "tokenizer_sha256": tokenizer_sha256,
    }


def normalize_source_row(
    source: SourceSpec,
    row: Mapping[str, Any],
    index: int,
    stage: str,
    bucket_id: str | None,
) -> dict[str, Any]:
    """Map one source-specific row into the provenance-preserving schema."""

    if source.text_field is None:
        raise ValueError(f"Source {source.id!r} has no text field for pretraining.")
    raw_text = row.get(source.text_field)
    if raw_text is None:
        raise ValueError(
            f"Source {source.id!r} row {index} is missing {source.text_field!r}."
        )
    text = normalize_text(str(raw_text))
    if not text:
        raise EmptySourceTextError(
            f"Source {source.id!r} row {index} has empty text."
        )

    content_sha256 = sha256_text(text)
    raw_document_id = (
        row.get(source.document_id_field) if source.document_id_field else None
    )
    document_id = (
        str(raw_document_id).strip()
        if raw_document_id is not None and str(raw_document_id).strip()
        else content_sha256
    )

    if source.license_field:
        raw_license = row.get(source.license_field)
        if raw_license is None or not str(raw_license).strip():
            raise ValueError(
                f"Source {source.id!r} row {document_id!r} is missing its "
                "document-level license."
            )
        license_name = str(raw_license).strip()
    else:
        license_name = source.license

    if source.collection_field:
        raw_collection = row.get(source.collection_field)
        if raw_collection is None or not str(raw_collection).strip():
            raise ValueError(
                f"Source {source.id!r} row {document_id!r} is missing its "
                "collection value."
            )
        collection = str(raw_collection).strip()
    else:
        collection = source.collection or source.id

    return {
        "id": f"{source.id}/{stage}/{document_id}",
        "dataset": source.hf_name,
        "split": source.split,
        "source_id": source.id,
        "collection": collection,
        "document_id": document_id,
        "license": license_name,
        "license_review": source.license_review,
        "role": source.role,
        "stage": stage,
        "bucket_id": bucket_id,
        "text": text,
        "content_sha256": content_sha256,
        "text_sha256": content_sha256,
        "num_chars": len(text),
        "estimated_tokens": _positive_token_estimate(source, row, text),
    }


def iter_deterministic_buffered(
    records: Iterable[dict[str, Any]],
    *,
    seed: int,
    buffer_size: int,
) -> Iterator[dict[str, Any]]:
    """Sort bounded record windows by a stable, seed-dependent document key."""

    if buffer_size < 1:
        raise ValueError("buffer_size must be positive.")
    buffer: list[dict[str, Any]] = []

    def ordered(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            rows,
            key=lambda record: sha256_text(
                f"{seed}:{record.get('source_id', '')}:"
                f"{record['document_id']}:{record['content_sha256']}"
            ),
        )

    for record in records:
        buffer.append(record)
        if len(buffer) >= buffer_size:
            yield from ordered(buffer)
            buffer.clear()
    if buffer:
        yield from ordered(buffer)


def _validated_plan_items(
    registry: SourceRegistry,
    plan: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    stage = plan.get("stage")
    if not isinstance(stage, str) or not stage:
        raise ValueError("Every corpus plan requires a non-empty stage.")
    raw_items = plan.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError(f"Corpus plan {stage!r} requires non-empty items.")
    source_ids = [str(item.get("source_id")) for item in raw_items]
    selected = select_pretraining_sources(registry, source_ids)
    source_by_id = {source.id: source for source in selected}

    items: dict[str, dict[str, Any]] = {}
    for raw in raw_items:
        if not isinstance(raw, Mapping):
            raise ValueError(f"Corpus plan {stage!r} items must be mappings.")
        item = dict(raw)
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError(f"Corpus plan {stage!r} item requires an id.")
        if item_id in items:
            raise ValueError(f"Corpus plan {stage!r} has duplicate item {item_id!r}.")
        source = source_by_id[str(item.get("source_id"))]
        if item.get("role") != source.role or source.role not in PRETRAIN_ROLES:
            raise ValueError(
                f"Corpus plan item {item_id!r} is not permitted for pretraining."
            )
        quota = item.get("token_quota")
        if not isinstance(quota, int) or isinstance(quota, bool) or quota < 1:
            raise ValueError(
                f"Corpus plan item {item_id!r} requires a positive token quota."
            )
        bucket_id = item.get("bucket_id")
        if source.buckets:
            if bucket_id not in source.bucket_by_id:
                raise ValueError(
                    f"Corpus plan item {item_id!r} has unknown bucket {bucket_id!r}."
                )
            expected_id = f"{source.id}/{bucket_id}"
        else:
            if bucket_id is not None:
                raise ValueError(
                    f"Corpus plan item {item_id!r} sets a bucket on an unbucketed source."
                )
            expected_id = source.id
        if item_id != expected_id:
            raise ValueError(
                f"Corpus plan item {item_id!r} must use canonical id {expected_id!r}."
            )
        items[item_id] = item

    total_tokens = plan.get("total_tokens")
    if total_tokens != sum(item["token_quota"] for item in items.values()):
        raise ValueError(f"Corpus plan {stage!r} item quotas do not match total_tokens.")
    return items


def _load_dataset_function(dataset_loader: DatasetLoader | None) -> DatasetLoader:
    if dataset_loader is not None:
        return dataset_loader
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError(
            "Install the 'datasets' package to stream public Telco corpora."
        ) from exc
    return load_dataset


def _loader_kwargs(source: SourceSpec) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "split": source.split,
        "revision": source.revision,
        "streaming": True,
    }
    if source.hf_config:
        kwargs["name"] = source.hf_config
    if source.data_files:
        kwargs["data_files"] = list(source.data_files)
    return kwargs


def _bucket_lookup(source: SourceSpec) -> dict[str, str]:
    return {
        collection: bucket.id
        for bucket in source.buckets
        for collection in bucket.collections
    }


def _normalize_stream_row(
    source: SourceSpec,
    row: Mapping[str, Any],
    *,
    index: int,
    stage: str,
    quality_filter: QualityFilter,
    collections: Mapping[str, str],
) -> dict[str, Any] | None:
    if not isinstance(row, Mapping):
        raise ValueError(f"Source {source.id!r} row {index} must be a mapping.")
    bucket_id: str | None = None
    if source.buckets:
        raw_collection = row.get(source.collection_field)  # type: ignore[arg-type]
        collection = str(raw_collection).strip() if raw_collection is not None else ""
        if collection not in collections:
            raise ValueError(
                f"Source {source.id!r} exposed unknown collection "
                f"{collection!r}; update and review the registry before continuing."
            )
        bucket_id = collections[collection]
    try:
        return normalize_source_row(
            source,
            row,
            index=index,
            stage=stage,
            bucket_id=bucket_id,
        )
    except EmptySourceTextError:
        quality_filter.record_rejection("empty_text")
        return None


def _iter_normalized_source(
    source: SourceSpec,
    dataset: Iterable[Mapping[str, Any]],
    stage: str,
    quality_filter: QualityFilter,
) -> Iterator[dict[str, Any]]:
    collections = _bucket_lookup(source)
    for index, row in enumerate(dataset):
        record = _normalize_stream_row(
            source,
            row,
            index=index,
            stage=stage,
            quality_filter=quality_filter,
            collections=collections,
        )
        if record is not None:
            yield record


iter_normalized_source = _iter_normalized_source


@dataclass(frozen=True)
class SourceWindow:
    """One restart-safe deterministic buffer and its next raw row cursor."""

    next_raw_cursor: int
    records: tuple[dict[str, Any], ...]


def iter_deterministic_source_windows(
    source: SourceSpec,
    dataset: Iterable[Mapping[str, Any]],
    stage: str,
    quality_filter: QualityFilter,
    seed: int,
    buffer_size: int,
    start_raw_cursor: int = 0,
) -> Iterator[SourceWindow]:
    """Yield sorted normalized windows whose cursor counts every raw row."""

    if buffer_size < 1:
        raise ValueError("buffer_size must be positive.")
    if start_raw_cursor < 0:
        raise ValueError("start_raw_cursor must be non-negative.")

    collections = _bucket_lookup(source)
    records: list[dict[str, Any]] = []
    next_raw_cursor = start_raw_cursor
    window_start_cursor = start_raw_cursor
    for index, row in enumerate(dataset, start=start_raw_cursor):
        next_raw_cursor = index + 1
        record = _normalize_stream_row(
            source,
            row,
            index=index,
            stage=stage,
            quality_filter=quality_filter,
            collections=collections,
        )
        if record is not None:
            records.append(record)
        if len(records) == buffer_size:
            yield SourceWindow(
                next_raw_cursor=next_raw_cursor,
                records=tuple(
                    iter_deterministic_buffered(
                        records,
                        seed=seed,
                        buffer_size=buffer_size,
                    )
                ),
            )
            records = []
            window_start_cursor = next_raw_cursor

    if next_raw_cursor > window_start_cursor:
        yield SourceWindow(
            next_raw_cursor=next_raw_cursor,
            records=tuple(
                iter_deterministic_buffered(
                    records,
                    seed=seed,
                    buffer_size=buffer_size,
                )
            ),
        )


def _item_id(record: Mapping[str, Any]) -> str:
    bucket_id = record.get("bucket_id")
    return (
        f"{record['source_id']}/{bucket_id}"
        if bucket_id is not None
        else str(record["source_id"])
    )


def _is_validation_record(record: Mapping[str, Any], fraction: float) -> bool:
    if fraction <= 0:
        return False
    value = int(str(record["content_sha256"])[:16], 16) / float(16**16)
    return value < fraction


is_validation_record = _is_validation_record


def _write_stage(
    path: Path,
    *,
    registry: SourceRegistry,
    plan: Mapping[str, Any],
    quality_filter: QualityFilter,
    buffer_size: int,
    dataset_loader: DatasetLoader,
    quota_token_counter: QuotaTokenCounter,
    validation_handle,
    validation_stats: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], Counter[str]]:
    stage = str(plan["stage"])
    items = _validated_plan_items(registry, plan)
    source_ids = sorted({item["source_id"] for item in items.values()})
    source_by_id = registry.by_id
    item_stats = {
        item_id: {
            "requested_tokens": item["token_quota"],
            "estimated_tokens": 0,
            "quota_tokens": 0,
            "documents": 0,
            "raw_bytes": 0,
        }
        for item_id, item in items.items()
    }
    loader_calls: list[dict[str, Any]] = []
    license_counts: Counter[str] = Counter()
    total_chars = 0
    documents_digest = hashlib.sha256()
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as handle:
        for source_id in source_ids:
            source = source_by_id[source_id]
            source_item_ids = sorted(
                item_id
                for item_id, item in items.items()
                if item["source_id"] == source_id
            )
            kwargs = _loader_kwargs(source)
            loader_calls.append(
                {
                    "source_id": source.id,
                    "hf_name": source.hf_name,
                    **kwargs,
                }
            )
            dataset = dataset_loader(source.hf_name, **kwargs)
            normalized = iter_normalized_source(
                source,
                dataset,
                stage,
                quality_filter,
            )
            ordered = iter_deterministic_buffered(
                normalized,
                seed=int(plan["seed"]),
                buffer_size=buffer_size,
            )

            for record in ordered:
                item_id = _item_id(record)
                if item_id not in source_item_ids:
                    raise ValueError(
                        f"Source {source.id!r} produced unplanned item {item_id!r}."
                    )
                stats = item_stats[item_id]
                if stats["quota_tokens"] >= stats["requested_tokens"]:
                    if all(
                        item_stats[planned]["quota_tokens"]
                        >= item_stats[planned]["requested_tokens"]
                        for planned in source_item_ids
                    ):
                        break
                    continue
                if not quality_filter.accept(record):
                    continue
                quota_tokens = quota_token_counter(record)
                if quota_tokens < 1:
                    raise ValueError(
                        f"Source {source.id!r} produced a non-positive quota "
                        f"token count for document {record['document_id']!r}."
                    )
                if is_validation_record(
                    record, float(plan.get("validation_fraction", 0.0))
                ):
                    validation_record = dict(record)
                    validation_record["source_split"] = validation_record["split"]
                    validation_record["split"] = "validation"
                    line = json.dumps(
                        validation_record, ensure_ascii=False, sort_keys=True
                    )
                    validation_handle.write(line + "\n")
                    encoded_bytes = len(line.encode("utf-8")) + 1
                    validation_stats["estimated_tokens"] += record["estimated_tokens"]
                    validation_stats["quota_tokens"] += quota_tokens
                    validation_stats["documents"] += 1
                    validation_stats["document_count"] += 1
                    validation_stats["total_chars"] += len(record["text"])
                    validation_stats["_documents_digest"].update(
                        record["text_sha256"].encode("utf-8")
                    )
                    validation_stats["raw_bytes"] += encoded_bytes
                    validation_stats["items"][_item_id(record)] += 1
                    license_counts[record["license"]] += 1
                    continue
                line = json.dumps(record, ensure_ascii=False, sort_keys=True)
                handle.write(line + "\n")
                encoded_bytes = len(line.encode("utf-8")) + 1
                total_chars += len(record["text"])
                documents_digest.update(record["text_sha256"].encode("utf-8"))
                stats["estimated_tokens"] += record["estimated_tokens"]
                stats["quota_tokens"] += quota_tokens
                stats["documents"] += 1
                stats["raw_bytes"] += encoded_bytes
                license_counts[record["license"]] += 1

                if all(
                    item_stats[planned]["quota_tokens"]
                    >= item_stats[planned]["requested_tokens"]
                    for planned in source_item_ids
                ):
                    break

            incomplete = [
                planned
                for planned in source_item_ids
                if item_stats[planned]["quota_tokens"]
                < item_stats[planned]["requested_tokens"]
            ]
            if incomplete:
                details = ", ".join(
                    f"{item_id}={item_stats[item_id]['quota_tokens']}/"
                    f"{item_stats[item_id]['requested_tokens']}"
                    for item_id in incomplete
                )
                raise ValueError(
                    f"Source {source.id!r} exhausted before quota for stage "
                    f"{stage!r}: {details}"
                )

    stage_stats = {
        "path": path.name,
        "plan_sha256": plan["plan_sha256"],
        "requested_tokens": sum(
            stats["requested_tokens"] for stats in item_stats.values()
        ),
        "estimated_tokens": sum(
            stats["estimated_tokens"] for stats in item_stats.values()
        ),
        "quota_tokens": sum(
            stats["quota_tokens"] for stats in item_stats.values()
        ),
        "documents": sum(stats["documents"] for stats in item_stats.values()),
        "document_count": sum(
            stats["documents"] for stats in item_stats.values()
        ),
        "total_chars": total_chars,
        "documents_sha256": documents_digest.hexdigest(),
        "raw_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "items": {item_id: item_stats[item_id] for item_id in sorted(item_stats)},
    }
    return stage_stats, loader_calls, license_counts


def prepare_telco_corpora(
    registry: SourceRegistry,
    plans: Sequence[Mapping[str, Any]],
    output_dir: str | Path,
    quality_policy: DataQualityPolicy,
    *,
    buffer_size: int = 2048,
    force: bool = False,
    dataset_loader: DatasetLoader | None = None,
    tokenizer_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Build one or more stages and publish them as one validated directory."""

    if not plans:
        raise ValueError("At least one corpus plan is required.")
    stages = [plan.get("stage") for plan in plans]
    if len(stages) != len(set(stages)):
        raise ValueError("Corpus plans must use unique stage names.")
    for plan in plans:
        _validated_plan_items(registry, plan)
    validation_fractions = {
        float(plan.get("validation_fraction", 0.0)) for plan in plans
    }
    if len(validation_fractions) != 1:
        raise ValueError("All corpus plans must use the same validation_fraction.")
    validation_fraction = validation_fractions.pop()
    if not 0 <= validation_fraction < 1:
        raise ValueError("validation_fraction must be in [0, 1).")
    if buffer_size < 1:
        raise ValueError("buffer_size must be positive.")

    output = Path(output_dir)
    if output.exists() and not force:
        raise FileExistsError(
            f"Output already exists: {output}. Pass --force to create a backup "
            "and replace it."
        )
    loader = _load_dataset_function(dataset_loader)
    quota_token_counter, quota_counting = _quota_counter(tokenizer_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
    )
    quality_filter = QualityFilter(quality_policy)
    stage_stats: dict[str, Any] = {}
    loader_calls: list[dict[str, Any]] = []
    license_counts: Counter[str] = Counter()
    validation_stats: dict[str, Any] = {
        "path": "validation.jsonl",
        "validation_fraction": validation_fraction,
        "estimated_tokens": 0,
        "quota_tokens": 0,
        "documents": 0,
        "document_count": 0,
        "total_chars": 0,
        "_documents_digest": hashlib.sha256(),
        "raw_bytes": 0,
        "items": Counter(),
    }
    used_source_ids = sorted(
        {
            str(item["source_id"])
            for plan in plans
            for item in plan["items"]
        }
    )

    try:
        validation_path = staging / "validation.jsonl"
        with validation_path.open("w", encoding="utf-8") as validation_handle:
            for plan in plans:
                stage = str(plan["stage"])
                stats, calls, stage_licenses = _write_stage(
                    staging / f"{stage}.jsonl",
                    registry=registry,
                    plan=plan,
                    quality_filter=quality_filter,
                    buffer_size=buffer_size,
                    dataset_loader=loader,
                    quota_token_counter=quota_token_counter,
                    validation_handle=validation_handle,
                    validation_stats=validation_stats,
                )
                stage_stats[stage] = stats
                loader_calls.extend(calls)
                license_counts.update(stage_licenses)

        validation_stats["raw_bytes"] = validation_path.stat().st_size
        validation_stats["sha256"] = sha256_file(validation_path)
        validation_stats["documents_sha256"] = validation_stats.pop(
            "_documents_digest"
        ).hexdigest()
        validation_stats["items"] = dict(sorted(validation_stats["items"].items()))
        if validation_fraction > 0 and validation_stats["documents"] == 0:
            raise ValueError(
                "Validation holdout is empty; increase the prepared corpus or "
                "validation_fraction."
            )

        manifest: dict[str, Any] = {
            "version": 1,
            "complete": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "quota_counting": quota_counting,
            "stages": {stage: stage_stats[stage] for stage in sorted(stage_stats)},
            "validation": validation_stats,
            "split_stats": {
                **{
                    stage: stage_stats[stage]
                    for stage in sorted(stage_stats)
                },
                "validation": validation_stats,
            },
            "sources": [
                {
                    "id": registry.by_id[source_id].id,
                    "hf_name": registry.by_id[source_id].hf_name,
                    "revision": registry.by_id[source_id].revision,
                    "role": registry.by_id[source_id].role,
                    "license": registry.by_id[source_id].license,
                    "license_review": registry.by_id[source_id].license_review,
                }
                for source_id in used_source_ids
            ],
            "loader_calls": loader_calls,
            "license_document_counts": dict(sorted(license_counts.items())),
            "quality_filter": quality_filter.report(),
        }
        manifest["manifest_sha256"] = sha256_json(manifest)
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        for stage, stats in stage_stats.items():
            stage_path = staging / stats["path"]
            if not stage_path.exists() or sha256_file(stage_path) != stats["sha256"]:
                raise ValueError(f"Staging validation failed for stage {stage!r}.")

        backup: Path | None = None
        if output.exists():
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = output.with_name(f"{output.name}.backup-{timestamp}")
            output.replace(backup)
        try:
            staging.replace(output)
        except Exception:
            if backup is not None and not output.exists():
                backup.replace(output)
            raise
        return manifest
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def corpus_has_exact_token_quotas(
    corpus_dir: str | Path,
    tokenizer_dir: str | Path,
    plans: Sequence[Mapping[str, Any]],
) -> bool:
    """Return whether a completed corpus matches one tokenizer and plan set."""

    try:
        manifest = json.loads(
            (Path(corpus_dir) / "manifest.json").read_text(encoding="utf-8")
        )
        tokenizer_sha256 = _validated_tokenizer_sha256(tokenizer_dir)
        expected_plans = {
            str(plan["stage"]): str(plan["plan_sha256"])
            for plan in plans
        }
        if len(expected_plans) != len(plans):
            return False
        stage_manifests = manifest["stages"]
        quota_counting = manifest["quota_counting"]
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return False

    return (
        manifest.get("complete") is True
        and quota_counting.get("method")
        in {"tokenizer_exact", "tokenizer_exact_one_pass"}
        and quota_counting.get("tokenizer_sha256") == tokenizer_sha256
        and set(stage_manifests) == set(expected_plans)
        and all(
            stage_manifests[stage].get("plan_sha256") == plan_sha256
            for stage, plan_sha256 in expected_plans.items()
        )
    )


def _resolve_corpus_relative_file(
    corpus_root: Path, relative_path: object
) -> Path:
    if not isinstance(relative_path, str):
        raise ValueError("corpus artifact path must be a safe relative POSIX path")
    relative = PurePosixPath(relative_path)
    if (
        not relative_path
        or "\\" in relative_path
        or relative.is_absolute()
        or ".." in relative.parts
        or str(relative) != relative_path
    ):
        raise ValueError("corpus artifact path must be a safe relative POSIX path")
    return require_managed_path(
        corpus_root,
        corpus_root / Path(*relative.parts),
        kind="file",
        allow_missing=False,
    )


def iter_corpus_split_records(
    corpus_dir: str | Path, split: str
) -> Iterator[dict[str, Any]]:
    """Read one finalized chunked split, with the legacy JSONL fallback."""

    if not split or Path(split).name != split:
        raise ValueError("split must be a safe path component")
    root = require_managed_path(
        Path(corpus_dir), Path(corpus_dir), kind="directory", allow_missing=False
    )
    manifest_path = require_managed_path(
        root, root / "manifest.json", kind="file", allow_missing=False
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("corpus manifest must contain a JSON object")
    stored = manifest.get("manifest_sha256")
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256", None)
    if stored != sha256_json(unsigned):
        raise ValueError("corpus manifest checksum does not match its content")
    if manifest.get("storage_format") == "chunked_prebuilt_v1":
        try:
            chunks = manifest["split_stats"][split]["raw_chunks"]
        except (KeyError, TypeError) as error:
            raise ValueError(f"chunked corpus has no split {split!r}") from error
        if not isinstance(chunks, list) or not chunks:
            raise ValueError(f"chunked corpus split {split!r} has no raw chunks")
        for chunk in chunks:
            if not isinstance(chunk, Mapping):
                raise ValueError("raw chunk evidence must be a mapping")
            path = _resolve_corpus_relative_file(root, chunk.get("path"))
            if path.stat().st_size != int(chunk.get("size", -1)):
                raise ValueError(f"raw chunk size mismatch: {path}")
            if sha256_file(path) != chunk.get("sha256"):
                raise ValueError(f"raw chunk checksum mismatch: {path}")
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError(f"{path}:{line_number} must contain an object")
                    yield row
        return

    legacy = require_managed_path(
        root, root / f"{split}.jsonl", kind="file", allow_missing=False
    )
    with legacy.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{legacy}:{line_number} must contain an object")
            yield row


def audit_token_quotas(
    input_paths: Sequence[str | Path],
    tokenizer_dir: str | Path,
    plans: Sequence[Mapping[str, Any]],
    *,
    tolerance: float,
    corpus_manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    """Audit tokenizer quotas while preserving whole-document boundaries."""

    if corpus_manifest_path is not None:
        _validate_canonical_plan_identities(plans)
    if not 0 <= tolerance < 1:
        raise ValueError("tolerance must be in [0, 1).")
    plan_by_stage = {str(plan["stage"]): plan for plan in plans}
    if len(plan_by_stage) != len(plans):
        raise ValueError("Quota audit plans must use unique stages.")
    expected: dict[str, dict[str, int]] = {
        stage: {
            str(item["id"]): int(item["token_quota"])
            for item in plan["items"]
        }
        for stage, plan in plan_by_stage.items()
    }
    actual = {
        stage: {item_id: 0 for item_id in items}
        for stage, items in expected.items()
    }
    last_document_tokens = {
        stage: {item_id: 0 for item_id in items}
        for stage, items in expected.items()
    }
    tokenizer = load_tokenizer(tokenizer_dir)
    canonical_identity = (
        _canonical_quota_audit_identity(
            corpus_manifest_path,
            tokenizer_dir=tokenizer_dir,
            plans=plans,
        )
        if corpus_manifest_path is not None
        else None
    )

    for input_path in input_paths:
        with Path(input_path).open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                stage = str(row.get("stage"))
                if stage not in expected:
                    raise ValueError(
                        f"Unexpected stage {stage!r} at {input_path}:{line_number}."
                    )
                item_id = _item_id(row)
                if item_id not in expected[stage]:
                    raise ValueError(
                        f"Unexpected plan item {item_id!r} at "
                        f"{input_path}:{line_number}."
                    )
                document_tokens = len(tokenizer.encode(str(row["text"])).ids)
                actual[stage][item_id] += document_tokens
                last_document_tokens[stage][item_id] = document_tokens

    report: dict[str, Any] = {
        "tolerance": tolerance,
        "item_policy": "relative_tolerance_or_minimal_whole_document_boundary",
        "stage_policy": "relative_tolerance",
        "passed": True,
        "stages": {},
    }
    if canonical_identity is not None:
        report.update(
            {
                "version": QUOTA_AUDIT_VERSION,
                "method": QUOTA_AUDIT_METHOD,
                **canonical_identity,
            }
        )
    failures: list[str] = []
    for stage in sorted(expected):
        stage_planned = sum(expected[stage].values())
        stage_counted = sum(actual[stage].values())
        stage_variance = abs(stage_counted - stage_planned) / stage_planned
        stage_passed = stage_variance <= tolerance
        stage_items: dict[str, Any] = {}
        for item_id in sorted(expected[stage]):
            planned = expected[stage][item_id]
            counted = actual[stage][item_id]
            variance = abs(counted - planned) / planned
            final_document = last_document_tokens[stage][item_id]
            within_tolerance = variance <= tolerance
            boundary_limited = (
                counted > planned
                and counted - final_document < planned
            )
            passed = within_tolerance or boundary_limited
            canonical_boundary_passed = (
                counted >= planned
                and final_document > 0
                and counted - final_document < planned
            )
            if canonical_identity is not None and not canonical_boundary_passed:
                passed = False
                failures.append(
                    f"{stage}/{item_id} does not prove a minimal "
                    "whole-document boundary"
                )
            item_evidence = {
                "planned_tokens": planned,
                "actual_tokens": counted,
                "relative_variance": variance,
                "last_document_tokens": final_document,
                "document_boundary_limited": boundary_limited,
                "passed": passed,
            }
            if canonical_identity is not None:
                item_evidence.update(
                    {
                        "requested_tokens": planned,
                        "overshoot_tokens": max(0, counted - planned),
                    }
                )
            stage_items[item_id] = item_evidence
            if not passed and (
                canonical_identity is None or canonical_boundary_passed
            ):
                failures.append(
                    f"{stage}/{item_id}={counted}/{planned} ({variance:.2%})"
                )
        if not stage_passed:
            failures.append(
                f"{stage} stage total={stage_counted}/{stage_planned} "
                f"({stage_variance:.2%})"
            )
        stage_evidence = {
            "planned_tokens": stage_planned,
            "actual_tokens": stage_counted,
            "relative_variance": stage_variance,
            "passed": stage_passed and all(
                item["passed"] for item in stage_items.values()
            ),
            "items": stage_items,
        }
        if canonical_identity is not None:
            stage_evidence.update(
                {
                    "requested_tokens": stage_planned,
                    "overshoot_tokens": max(0, stage_counted - stage_planned),
                    "document_boundary_limited": all(
                        item["actual_tokens"] >= item["requested_tokens"]
                        and (
                            item["overshoot_tokens"] == 0
                            or item["document_boundary_limited"] is True
                        )
                        for item in stage_items.values()
                    ),
                }
            )
        report["stages"][stage] = stage_evidence
    if failures:
        report["passed"] = False
        raise ValueError(
            "Actual tokenizer quotas are outside tolerance or whole-document "
            "policy: " + "; ".join(failures)
        )
    if canonical_identity is not None:
        report["audit_sha256"] = sha256_json(report)
    return report


def _canonical_quota_audit_identity(
    manifest_path: str | Path,
    *,
    tokenizer_dir: str | Path,
    plans: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    path = Path(manifest_path)
    path = require_managed_path(
        path.parent, path, kind="file", allow_missing=False
    )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Quota audit corpus manifest must contain an object.")
    manifest_sha256 = manifest.get("manifest_sha256")
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256", None)
    if (
        not isinstance(manifest_sha256, str)
        or manifest_sha256 != sha256_json(unsigned)
        or manifest.get("complete") is not True
    ):
        raise ValueError("Quota audit corpus manifest identity is invalid.")
    tokenizer_sha256 = _validated_tokenizer_sha256(tokenizer_dir)
    quota_counting = manifest.get("quota_counting")
    if (
        not isinstance(quota_counting, Mapping)
        or quota_counting.get("tokenizer_sha256") != tokenizer_sha256
    ):
        raise ValueError("Quota audit tokenizer does not match the corpus manifest.")
    stage_plan_sha256s = {
        str(plan["stage"]): str(plan["plan_sha256"])
        for plan in plans
    }
    if len(stage_plan_sha256s) != len(plans) or any(
        len(value) != 64 for value in stage_plan_sha256s.values()
    ):
        raise ValueError("Quota audit plans have invalid stage identities.")
    manifest_stages = manifest.get("stages")
    if not isinstance(manifest_stages, Mapping) or set(manifest_stages) != set(
        stage_plan_sha256s
    ):
        raise ValueError("Quota audit plans do not cover the corpus stages.")
    complete_plan_sha256 = sha256_json(list(plans))
    fingerprints = manifest.get("fingerprints")
    if isinstance(fingerprints, Mapping):
        if fingerprints.get("plan_sha256") != complete_plan_sha256:
            raise ValueError("Quota audit plan does not match the corpus manifest.")
        plan_sha256 = complete_plan_sha256
    elif any(
        not isinstance(manifest_stages[stage], Mapping)
        or manifest_stages[stage].get("plan_sha256") != plan_sha256_value
        for stage, plan_sha256_value in stage_plan_sha256s.items()
    ):
        raise ValueError("Quota audit stage plan does not match the corpus manifest.")
    else:
        plan_sha256 = sha256_json(dict(sorted(stage_plan_sha256s.items())))
    build_identity = manifest.get("build_identity_sha256")
    if not isinstance(build_identity, str):
        build_identity = sha256_json(
            {
                "format": "legacy_telco_prepare_v1",
                "manifest_sha256": manifest_sha256,
                "tokenizer_sha256": tokenizer_sha256,
            }
        )
    return {
        "tokenizer_sha256": tokenizer_sha256,
        "corpus_manifest_sha256": manifest_sha256,
        "corpus_manifest_file_sha256": sha256_file(path),
        "corpus_build_identity_sha256": build_identity,
        "plan_sha256": plan_sha256,
        "stage_plan_sha256s": dict(sorted(stage_plan_sha256s.items())),
    }


def _validate_canonical_plan_identities(
    plans: Sequence[Mapping[str, Any]],
) -> None:
    """Require the exact self-hash emitted by ``build_mixture_plan``."""

    for index, plan in enumerate(plans):
        if not isinstance(plan, Mapping):
            raise ValueError(f"Canonical quota audit plan {index} must be a mapping.")
        declared = plan.get("plan_sha256")
        unsigned = dict(plan)
        unsigned.pop("plan_sha256", None)
        if (
            not isinstance(declared, str)
            or _SHA256_PATTERN.fullmatch(declared) is None
            or declared != sha256_json(unsigned)
        ):
            raise ValueError(
                f"Canonical quota audit plan {index} has an invalid SHA-256 identity."
            )
