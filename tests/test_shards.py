import json
from pathlib import Path

import numpy as np
import pytest

from matgpt.data import shard as shard_module
from matgpt.data.shard import tokenize_jsonl_to_shards, tokenize_splits_from_config
from matgpt.tokenizer.io import load_tokenizer
from matgpt.tokenizer.train import train_tokenizer_from_jsonl
from matgpt.training.dataset import PackedTokenDataset


SPECIAL_TOKENS = ["<|pad|>", "<|bos|>", "<|eos|>", "<|system|>", "<|user|>", "<|assistant|>", "<|end|>"]


def test_tokenize_jsonl_to_uint16_shards_with_eos(tmp_path: Path):
    corpus = tmp_path / "train.jsonl"
    records = [
        {"text": "First document."},
        {"text": "Second document."},
    ]
    corpus.write_text("\n".join(json.dumps(row) for row in records) + "\n", encoding="utf-8")
    tokenizer_dir = tmp_path / "tokenizer"
    train_tokenizer_from_jsonl([corpus], tokenizer_dir, vocab_size=320, min_frequency=1, special_tokens=SPECIAL_TOKENS)

    metadata = tokenize_jsonl_to_shards(
        input_path=corpus,
        tokenizer_dir=tokenizer_dir,
        output_dir=tmp_path / "shards",
        split="train",
        shard_size_tokens=8,
        dtype="uint16",
        append_eos=True,
    )

    tokenizer = load_tokenizer(tokenizer_dir)
    eos_id = tokenizer.token_to_id("<|eos|>")

    assert metadata["split"] == "train"
    assert metadata["dtype"] == "uint16"
    assert metadata["total_documents"] == 2
    assert metadata["total_tokens"] > 2
    assert len(metadata["shards"]) >= 1

    first_shard = tmp_path / "shards" / metadata["shards"][0]["path"]
    tokens = np.fromfile(first_shard, dtype=np.uint16)
    all_tokens = []
    for shard in metadata["shards"]:
        all_tokens.extend(
            np.fromfile(tmp_path / "shards" / shard["path"], dtype=np.uint16).tolist()
        )
    assert all_tokens.count(eos_id) == 2
    assert len(tokens) <= 8
    assert len(metadata["shards"][0]["sha256"]) == 64
    assert not Path(metadata["shards"][0]["path"]).is_absolute()


def test_packed_dataset_reads_legacy_absolute_shard_metadata(tmp_path: Path):
    shard_path = tmp_path / "legacy.bin"
    np.arange(16, dtype=np.uint16).tofile(shard_path)
    metadata_path = tmp_path / "legacy_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "dtype": "uint16",
                "shards": [
                    {
                        "path": str(shard_path),
                        "num_tokens": 16,
                        "sha256": "ignored-by-reader",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    dataset = PackedTokenDataset.from_metadata(metadata_path, context_length=8)

    assert dataset.shards[0].path == shard_path


class _Encoding:
    def __init__(self, ids: list[int]):
        self.ids = ids


class _TokenizerWithIds:
    def __init__(self, *, vocabulary_size: int, encoded_ids: list[int], eos_id: int):
        self.vocabulary_size = vocabulary_size
        self.encoded_ids = encoded_ids
        self.eos_id = eos_id

    def get_vocab_size(self) -> int:
        return self.vocabulary_size

    def token_to_id(self, token: str) -> int | None:
        assert token == "<|eos|>"
        return self.eos_id

    def encode(self, text: str) -> _Encoding:
        return _Encoding(self.encoded_ids)


def _tokenize_with_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    vocabulary_size: int,
    encoded_ids: list[int],
    eos_id: int,
):
    source = tmp_path / "records.jsonl"
    source.write_text('{"text": "input"}\n', encoding="utf-8")
    tokenizer = _TokenizerWithIds(
        vocabulary_size=vocabulary_size,
        encoded_ids=encoded_ids,
        eos_id=eos_id,
    )
    monkeypatch.setattr(shard_module, "load_tokenizer", lambda _path: tokenizer)
    monkeypatch.setattr(
        shard_module,
        "load_tokenizer_metadata",
        lambda _path: {"tokenizer_sha256": "0" * 64},
    )
    return tokenize_jsonl_to_shards(
        source,
        tmp_path / "tokenizer",
        tmp_path / "shards",
        "train",
        shard_size_tokens=8,
    )


def test_uint16_shards_allow_the_full_65536_token_id_range(tmp_path: Path, monkeypatch):
    metadata = _tokenize_with_ids(
        tmp_path,
        monkeypatch,
        vocabulary_size=65_536,
        encoded_ids=[65_535],
        eos_id=65_535,
    )

    tokens = np.fromfile(tmp_path / "shards" / metadata["shards"][0]["path"], dtype=np.uint16)
    assert tokens.tolist() == [65_535, 65_535]


@pytest.mark.parametrize(
    ("encoded_ids", "eos_id"),
    [([65_536], 1), ([1], 65_536)],
)
def test_uint16_shards_reject_out_of_range_encoded_or_eos_ids_before_writing(
    tmp_path: Path,
    monkeypatch,
    encoded_ids: list[int],
    eos_id: int,
):
    with pytest.raises(ValueError, match="token IDs must fit uint16"):
        _tokenize_with_ids(
            tmp_path,
            monkeypatch,
            vocabulary_size=2,
            encoded_ids=encoded_ids,
            eos_id=eos_id,
        )

    assert not (tmp_path / "shards").exists()


def test_tokenize_config_supports_named_training_phase_splits(tmp_path: Path):
    normalized = tmp_path / "normalized"
    normalized.mkdir()
    for split, text in {
        "main": "Main phase text.",
        "cooldown": "Cooldown phase text.",
        "validation": "Held-out validation text.",
    }.items():
        (normalized / f"{split}.jsonl").write_text(
            json.dumps({"text": text}) + "\n",
            encoding="utf-8",
        )
    tokenizer_dir = tmp_path / "tokenizer"
    train_tokenizer_from_jsonl(
        [normalized / "main.jsonl", normalized / "cooldown.jsonl"],
        tokenizer_dir,
        vocab_size=320,
        min_frequency=1,
        special_tokens=SPECIAL_TOKENS,
    )
    cfg = {
        "dataset": {
            "train_split": "main",
            "validation_split": "validation",
            "training_splits": {"main": "main", "cooldown": "cooldown"},
            "normalized_dir": str(normalized),
        },
        "tokenizer": {"output_dir": str(tokenizer_dir)},
        "sharding": {
            "output_dir": str(tmp_path / "shards"),
            "shard_size_tokens": 8,
            "dtype": "uint16",
            "append_eos": True,
        },
    }

    metadata = tokenize_splits_from_config(cfg)

    assert set(metadata["splits"]) == {"main", "cooldown", "validation"}
    for split in metadata["splits"]:
        assert (tmp_path / "shards" / f"{split}_metadata.json").exists()
