"""Prepare raw Hugging Face datasets into deterministic JSONL documents.

The training code never reads directly from a remote dataset. We first write a
normalized local JSONL corpus and a manifest so each run can record exactly
which text was used.
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from matgpt.data.normalize import normalize_text
from matgpt.utils.hashing import sha256_json, sha256_text


COMMON_TEXT_FIELDS = ("text", "story", "content", "article", "document")


def detect_text_field(columns: Iterable[str]) -> str:
    columns = list(columns)
    for candidate in COMMON_TEXT_FIELDS:
        if candidate in columns:
            return candidate
    if len(columns) == 1:
        return columns[0]
    raise ValueError(f"Could not detect text field from columns: {columns}")


def make_document_record(
    dataset_name: str,
    split: str,
    index: int,
    text: str,
    source_id: str | int | None = None,
) -> dict[str, Any]:
    normalized = normalize_text(text)
    source = str(source_id) if source_id is not None else str(index)
    return {
        "id": f"{dataset_name}/{split}/{source}",
        "dataset": dataset_name,
        "split": split,
        "source_id": source,
        "text": normalized,
        "text_sha256": sha256_text(normalized),
        "num_chars": len(normalized),
    }


def iter_dataset_records(
    dataset: Iterable[dict[str, Any]],
    dataset_name: str,
    split: str,
    text_field: str,
    max_documents: int | None = None,
) -> Iterator[dict[str, Any]]:
    count = 0
    for index, row in enumerate(dataset):
        if max_documents is not None and count >= max_documents:
            break
        raw_text = row.get(text_field)
        if raw_text is None:
            continue
        record = make_document_record(
            dataset_name=dataset_name,
            split=split,
            index=index,
            text=str(raw_text),
            source_id=row.get("id", index),
        )
        if record["text"]:
            count += 1
            yield record


def effective_validation_split(ds_cfg: dict[str, Any]) -> str:
    return ds_cfg.get("validation_split") or ds_cfg.get("generated_validation_split") or "validation"


def assign_hash_split(record: dict[str, Any], validation_fraction: float) -> str:
    """Assign a document to train/validation using only its content hash.

    Hash-based splitting is stable even if the dataset row order changes. That
    matters for BabyLM because this framework creates a validation split when
    the source dataset exposes only a training split.
    """

    if validation_fraction <= 0.0:
        return "train"
    value = int(record["text_sha256"][:16], 16) / float(16**16 - 1)
    return "validation" if value < validation_fraction else "train"


def write_jsonl_records(path: str | Path, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    document_count = 0
    raw_bytes = 0
    total_chars = 0
    documents_digest = hashlib.sha256()

    with out.open("w", encoding="utf-8") as f:
        for record in records:
            line = json.dumps(record, ensure_ascii=False, sort_keys=True)
            f.write(line + "\n")
            document_count += 1
            encoded = line.encode("utf-8")
            raw_bytes += len(encoded) + 1
            total_chars += int(record.get("num_chars", len(record.get("text", ""))))
            documents_digest.update(record["text_sha256"].encode("utf-8"))

    return {
        "path": str(out),
        "document_count": document_count,
        "raw_bytes": raw_bytes,
        "total_chars": total_chars,
        "documents_sha256": documents_digest.hexdigest(),
    }


def write_hash_split_jsonl_records(
    train_path: str | Path,
    validation_path: str | Path,
    records: Iterable[dict[str, Any]],
    train_split: str,
    validation_split: str,
    validation_fraction: float,
    max_train_documents: int | None = None,
    max_validation_documents: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    train_out = Path(train_path)
    val_out = Path(validation_path)
    train_out.parent.mkdir(parents=True, exist_ok=True)
    val_out.parent.mkdir(parents=True, exist_ok=True)

    stats = {
        train_split: {"path": str(train_out), "document_count": 0, "raw_bytes": 0, "total_chars": 0, "digest": hashlib.sha256()},
        validation_split: {"path": str(val_out), "document_count": 0, "raw_bytes": 0, "total_chars": 0, "digest": hashlib.sha256()},
    }

    with train_out.open("w", encoding="utf-8") as train_f, val_out.open("w", encoding="utf-8") as val_f:
        for record in records:
            train_full = max_train_documents is not None and stats[train_split]["document_count"] >= max_train_documents
            val_full = (
                max_validation_documents is not None
                and stats[validation_split]["document_count"] >= max_validation_documents
            )
            if train_full and val_full:
                break

            assigned = assign_hash_split(record, validation_fraction)
            target_split = validation_split if assigned == "validation" else train_split
            if target_split == validation_split:
                if max_validation_documents is not None and stats[validation_split]["document_count"] >= max_validation_documents:
                    continue
                record = dict(record)
                record["split"] = validation_split
                record["id"] = record["id"].replace(f"/{train_split}/", f"/{validation_split}/")
                target_f = val_f
            else:
                if max_train_documents is not None and stats[train_split]["document_count"] >= max_train_documents:
                    continue
                target_f = train_f

            line = json.dumps(record, ensure_ascii=False, sort_keys=True)
            target_f.write(line + "\n")
            encoded_len = len(line.encode("utf-8")) + 1
            split_stats = stats[target_split]
            split_stats["document_count"] += 1
            split_stats["raw_bytes"] += encoded_len
            split_stats["total_chars"] += int(record.get("num_chars", len(record.get("text", ""))))
            split_stats["digest"].update(record["text_sha256"].encode("utf-8"))

    def finalize(split: str) -> dict[str, Any]:
        split_stats = stats[split]
        return {
            "path": split_stats["path"],
            "document_count": split_stats["document_count"],
            "raw_bytes": split_stats["raw_bytes"],
            "total_chars": split_stats["total_chars"],
            "documents_sha256": split_stats["digest"].hexdigest(),
        }

    return finalize(train_split), finalize(validation_split)


def write_manifest(
    path: str | Path,
    dataset_name: str,
    version_or_commit: str | None,
    license_name: str,
    stage: str,
    language: str,
    split_stats: dict[str, Any],
    notes: str,
) -> dict[str, Any]:
    manifest = {
        "dataset_name": dataset_name,
        "version_or_commit": version_or_commit or "unknown",
        "license": license_name,
        "stage": stage,
        "language": language,
        "download_date": datetime.now(timezone.utc).date().isoformat(),
        "split_stats": split_stats,
        "notes": notes,
    }
    manifest["manifest_sha256"] = sha256_json(manifest)

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def prepare_hf_dataset(cfg: dict[str, Any]) -> dict[str, Any]:
    """Download and normalize the configured Hugging Face dataset."""

    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError("Install datasets to prepare Hugging Face corpora.") from exc

    ds_cfg = cfg["dataset"]
    normalized_dir = Path(ds_cfg["normalized_dir"])
    normalized_dir.mkdir(parents=True, exist_ok=True)

    dataset_kwargs: dict[str, Any] = {}
    if ds_cfg.get("hf_config"):
        dataset_kwargs["name"] = ds_cfg["hf_config"]
    if ds_cfg.get("revision"):
        dataset_kwargs["revision"] = ds_cfg["revision"]

    split_stats = {}
    if ds_cfg.get("validation_split"):
        requested_splits = [ds_cfg["train_split"], ds_cfg["validation_split"]]
        for split in requested_splits:
            dataset = load_dataset(ds_cfg["hf_name"], split=split, **dataset_kwargs)
            text_field = ds_cfg.get("text_field") or detect_text_field(dataset.column_names)
            max_docs = (
                ds_cfg.get("max_train_documents")
                if split == ds_cfg["train_split"]
                else ds_cfg.get("max_validation_documents")
            )
            records = iter_dataset_records(
                dataset=dataset,
                dataset_name=ds_cfg["hf_name"],
                split=split,
                text_field=text_field,
                max_documents=max_docs,
            )
            path = normalized_dir / f"{split}.jsonl"
            split_stats[split] = write_jsonl_records(path, records)
            split_stats[split]["text_field"] = text_field
    else:
        train_split = ds_cfg["train_split"]
        validation_split = effective_validation_split(ds_cfg)
        dataset = load_dataset(ds_cfg["hf_name"], split=train_split, **dataset_kwargs)
        text_field = ds_cfg.get("text_field") or detect_text_field(dataset.column_names)
        validation_fraction = float(ds_cfg.get("validation_fraction", 0.01))
        train_path = normalized_dir / f"{train_split}.jsonl"
        val_path = normalized_dir / f"{validation_split}.jsonl"
        max_train = ds_cfg.get("max_train_documents")
        max_val = ds_cfg.get("max_validation_documents")

        records = iter_dataset_records(
            dataset=dataset,
            dataset_name=ds_cfg["hf_name"],
            split=train_split,
            text_field=text_field,
            max_documents=None,
        )
        train_stats, val_stats = write_hash_split_jsonl_records(
            train_path=train_path,
            validation_path=val_path,
            records=records,
            train_split=train_split,
            validation_split=validation_split,
            validation_fraction=validation_fraction,
            max_train_documents=max_train,
            max_validation_documents=max_val,
        )

        split_stats[train_split] = train_stats
        split_stats[train_split]["text_field"] = text_field
        split_stats[validation_split] = val_stats
        split_stats[validation_split]["text_field"] = text_field
        split_stats[validation_split]["generated_from_split"] = train_split
        split_stats[validation_split]["validation_fraction"] = validation_fraction

    return write_manifest(
        normalized_dir / "manifest.json",
        dataset_name=ds_cfg["hf_name"],
        version_or_commit=ds_cfg.get("revision"),
        license_name=ds_cfg["license"],
        stage=ds_cfg["stage"],
        language=ds_cfg["language"],
        split_stats=split_stats,
        notes=f"Prepared from Hugging Face dataset {ds_cfg['hf_name']}.",
    )
