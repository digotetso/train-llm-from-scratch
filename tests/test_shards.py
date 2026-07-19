import json
from pathlib import Path

import numpy as np

from matgpt.data.shard import tokenize_jsonl_to_shards
from matgpt.tokenizer.io import load_tokenizer
from matgpt.tokenizer.train import train_tokenizer_from_jsonl


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

    first_shard = Path(metadata["shards"][0]["path"])
    tokens = np.fromfile(first_shard, dtype=np.uint16)
    all_tokens = []
    for shard in metadata["shards"]:
        all_tokens.extend(np.fromfile(shard["path"], dtype=np.uint16).tolist())
    assert all_tokens.count(eos_id) == 2
    assert len(tokens) <= 8
    assert len(metadata["shards"][0]["sha256"]) == 64
