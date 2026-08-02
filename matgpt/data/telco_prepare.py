"""Stream, normalize, and atomically publish Telco 300M corpus stages."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

from matgpt.data.normalize import normalize_text
from matgpt.data.quality import DataQualityPolicy, QualityFilter
from matgpt.data.sources import (
    PRETRAIN_ROLES,
    SourceRegistry,
    SourceSpec,
    select_pretraining_sources,
)
from matgpt.tokenizer.io import load_tokenizer
from matgpt.utils.hashing import sha256_file, sha256_json, sha256_text


DatasetLoader = Callable[..., Iterable[Mapping[str, Any]]]


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
        raise ValueError(f"Source {source.id!r} row {index} has empty text.")

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


def _iter_normalized_source(
    source: SourceSpec,
    dataset: Iterable[Mapping[str, Any]],
    stage: str,
) -> Iterator[dict[str, Any]]:
    collections = _bucket_lookup(source)
    for index, row in enumerate(dataset):
        if not isinstance(row, Mapping):
            raise ValueError(
                f"Source {source.id!r} row {index} must be a mapping."
            )
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
        yield normalize_source_row(
            source,
            row,
            index=index,
            stage=stage,
            bucket_id=bucket_id,
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


def _write_stage(
    path: Path,
    *,
    registry: SourceRegistry,
    plan: Mapping[str, Any],
    quality_filter: QualityFilter,
    buffer_size: int,
    dataset_loader: DatasetLoader,
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
            normalized = _iter_normalized_source(source, dataset, stage)
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
                if stats["estimated_tokens"] >= stats["requested_tokens"]:
                    if all(
                        item_stats[planned]["estimated_tokens"]
                        >= item_stats[planned]["requested_tokens"]
                        for planned in source_item_ids
                    ):
                        break
                    continue
                if not quality_filter.accept(record):
                    continue
                if _is_validation_record(
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
                stats["documents"] += 1
                stats["raw_bytes"] += encoded_bytes
                license_counts[record["license"]] += 1

                if all(
                    item_stats[planned]["estimated_tokens"]
                    >= item_stats[planned]["requested_tokens"]
                    for planned in source_item_ids
                ):
                    break

            incomplete = [
                planned
                for planned in source_item_ids
                if item_stats[planned]["estimated_tokens"]
                < item_stats[planned]["requested_tokens"]
            ]
            if incomplete:
                details = ", ".join(
                    f"{item_id}={item_stats[item_id]['estimated_tokens']}/"
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
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
    )
    loader = _load_dataset_function(dataset_loader)
    quality_filter = QualityFilter(quality_policy)
    stage_stats: dict[str, Any] = {}
    loader_calls: list[dict[str, Any]] = []
    license_counts: Counter[str] = Counter()
    validation_stats: dict[str, Any] = {
        "path": "validation.jsonl",
        "validation_fraction": validation_fraction,
        "estimated_tokens": 0,
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


def audit_token_quotas(
    input_paths: Sequence[str | Path],
    tokenizer_dir: str | Path,
    plans: Sequence[Mapping[str, Any]],
    *,
    tolerance: float,
) -> dict[str, Any]:
    """Count actual tokenizer IDs per plan item and fail outside tolerance."""

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
    tokenizer = load_tokenizer(tokenizer_dir)

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
                actual[stage][item_id] += len(tokenizer.encode(str(row["text"])).ids)

    report: dict[str, Any] = {
        "tolerance": tolerance,
        "passed": True,
        "stages": {},
    }
    failures: list[str] = []
    for stage in sorted(expected):
        stage_items: dict[str, Any] = {}
        for item_id in sorted(expected[stage]):
            planned = expected[stage][item_id]
            counted = actual[stage][item_id]
            variance = abs(counted - planned) / planned
            passed = variance <= tolerance
            stage_items[item_id] = {
                "planned_tokens": planned,
                "actual_tokens": counted,
                "relative_variance": variance,
                "passed": passed,
            }
            if not passed:
                failures.append(
                    f"{stage}/{item_id}={counted}/{planned} ({variance:.2%})"
                )
        report["stages"][stage] = {"items": stage_items}
    if failures:
        report["passed"] = False
        raise ValueError(
            "Actual tokenizer quotas are outside tolerance: " + "; ".join(failures)
        )
    return report
