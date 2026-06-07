import json
from pathlib import Path

from matgpt.data.normalize import normalize_text
from matgpt.data.prepare import (
    assign_hash_split,
    detect_text_field,
    effective_validation_split,
    make_document_record,
    write_jsonl_records,
    write_manifest,
)


def test_normalize_text_is_conservative_and_deterministic():
    text = "Ａ token\r\n\r\n\r\ncontains\u0000 text.\n\nSecond paragraph.\t"

    normalized = normalize_text(text)

    assert normalized == "A token\n\ncontains text.\n\nSecond paragraph."
    assert normalize_text(text) == normalized


def test_detect_text_field_prefers_common_columns():
    assert detect_text_field(["id", "story", "text"]) == "text"
    assert detect_text_field(["content", "meta"]) == "content"
    assert detect_text_field(["article", "url"]) == "article"


def test_make_document_record_contains_stable_hash():
    record = make_document_record(
        dataset_name="unit",
        split="train",
        index=3,
        text="Hello world",
        source_id="row-3",
    )

    assert record["id"] == "unit/train/row-3"
    assert record["text"] == "Hello world"
    assert len(record["text_sha256"]) == 64
    assert record["num_chars"] == 11


def test_generated_validation_split_is_deterministic():
    cfg = {"validation_split": None, "generated_validation_split": "validation"}
    record = make_document_record("unit", "train", 0, "Stable text for splitting")

    assert effective_validation_split(cfg) == "validation"
    assert assign_hash_split(record, validation_fraction=0.25) == assign_hash_split(record, validation_fraction=0.25)
    assert assign_hash_split(record, validation_fraction=0.0) == "train"


def test_write_jsonl_records_and_manifest(tmp_path: Path):
    records = [
        make_document_record("unit", "train", 0, "First document"),
        make_document_record("unit", "train", 1, "Second document"),
    ]
    jsonl_path = tmp_path / "train.jsonl"
    manifest_path = tmp_path / "manifest.json"

    stats = write_jsonl_records(jsonl_path, records)
    manifest = write_manifest(
        manifest_path,
        dataset_name="unit",
        version_or_commit="local",
        license_name="test",
        stage="base_pretraining",
        language="en",
        split_stats={"train": stats},
        notes="unit test",
    )

    assert stats["document_count"] == 2
    assert stats["raw_bytes"] > 0
    assert manifest["dataset_name"] == "unit"
    assert manifest["split_stats"]["train"]["document_count"] == 2

    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["text"] == "First document"
    assert len(manifest["manifest_sha256"]) == 64
