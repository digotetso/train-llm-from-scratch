import json
import stat
from pathlib import Path

import numpy as np
import pytest
from tokenizers import Tokenizer, models, pre_tokenizers

from matgpt.data import local_tokens
from matgpt.data.local_tokens import PackedShardWriter, encode_record_batch
from matgpt.data.shard import tokenize_jsonl_to_shards


def _word_tokenizer(path: Path) -> Path:
    path.mkdir()
    tokenizer = Tokenizer(
        models.WordLevel(
            vocab={"[UNK]": 0, "<|eos|>": 1, "router": 2, "packet": 3},
            unk_token="[UNK]",
        )
    )
    tokenizer.pre_tokenizer = pre_tokenizers.WhitespaceSplit()
    tokenizer.save(str(path / "tokenizer.json"))
    return path


def test_batch_encoding_matches_individual_encoding(tmp_path: Path):
    tokenizer_dir = _word_tokenizer(tmp_path / "tokenizer")
    tokenizer = Tokenizer.from_file(str(tokenizer_dir / "tokenizer.json"))
    records = [
        {"document_id": "a", "text": "router packet"},
        {"document_id": "b", "text": "packet router router"},
    ]

    encoded = encode_record_batch(tokenizer, records)

    assert [item.ids for item in encoded] == [
        tuple(tokenizer.encode(record["text"]).ids) for record in records
    ]
    assert [item.quota_tokens for item in encoded] == [2, 3]


def test_streaming_writer_matches_reference_bytes(tmp_path: Path):
    tokenizer_dir = _word_tokenizer(tmp_path / "tokenizer")
    tokenizer = Tokenizer.from_file(str(tokenizer_dir / "tokenizer.json"))
    metadata = {
        "tokenizer_sha256": "0" * 64,
        "special_token_ids": {"<|eos|>": 1},
    }
    (tokenizer_dir / "special_tokens.json").write_text(
        json.dumps(metadata) + "\n", encoding="utf-8"
    )
    records = [
        {"document_id": "a", "text": "router packet"},
        {"document_id": "b", "text": "packet router router"},
    ]
    source = tmp_path / "records.jsonl"
    source.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    reference = tokenize_jsonl_to_shards(
        source, tokenizer_dir, tmp_path / "reference", "main", 4
    )

    writer = PackedShardWriter(
        output_dir=tmp_path / "streaming",
        split="main",
        dtype="uint16",
        shard_size_tokens=4,
        eos_id=1,
    )
    for item in encode_record_batch(tokenizer, records):
        writer.append_document(item.ids)
    actual = writer.finalize()

    expected_bytes = b"".join(
        (tmp_path / "reference" / shard["path"]).read_bytes()
        for shard in reference["shards"]
    )
    actual_bytes = b"".join(Path(shard["path"]).read_bytes() for shard in actual)
    assert actual_bytes == expected_bytes
    assert sum(shard["num_tokens"] for shard in actual) == 7
    assert np.fromfile(actual[0]["path"], dtype=np.uint16).tolist() == [2, 3, 1, 3]


def test_restart_refuses_to_overwrite_sealed_shard_bytes(tmp_path: Path):
    output_dir = tmp_path / "streaming"
    writer = PackedShardWriter(
        output_dir=output_dir,
        split="main",
        dtype="uint16",
        shard_size_tokens=4,
        eos_id=1,
    )
    writer.append_document((2, 3))
    sealed = writer.finalize()[0]
    original_bytes = Path(sealed["path"]).read_bytes()

    with pytest.raises(FileExistsError, match="sealed shard"):
        PackedShardWriter(
            output_dir=output_dir,
            split="main",
            dtype="uint16",
            shard_size_tokens=4,
            eos_id=1,
        )

    assert Path(sealed["path"]).read_bytes() == original_bytes


def test_restart_refuses_stale_partial_before_mutating_it(tmp_path: Path):
    output_dir = tmp_path / "streaming"
    output_dir.mkdir()
    partial = output_dir / "main_00000.bin.partial"
    partial.write_bytes(b"uncommitted")

    with pytest.raises(FileExistsError, match="stale partial"):
        PackedShardWriter(
            output_dir=output_dir,
            split="main",
            dtype="uint16",
            shard_size_tokens=4,
            eos_id=1,
        )

    assert partial.read_bytes() == b"uncommitted"
    assert not (output_dir / "main_00000.bin").exists()


def test_sealing_fsyncs_containing_directory(tmp_path: Path, monkeypatch):
    real_fsync = local_tokens.os.fsync
    fsynced_directory_descriptors = []

    def record_fsync(file_descriptor: int) -> None:
        if stat.S_ISDIR(local_tokens.os.fstat(file_descriptor).st_mode):
            fsynced_directory_descriptors.append(file_descriptor)
        real_fsync(file_descriptor)

    monkeypatch.setattr(local_tokens.os, "fsync", record_fsync)
    writer = PackedShardWriter(
        output_dir=tmp_path / "streaming",
        split="main",
        dtype="uint16",
        shard_size_tokens=4,
        eos_id=1,
    )
    writer.append_document((2, 3))
    writer.finalize()

    assert fsynced_directory_descriptors
