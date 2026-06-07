"""Convert normalized JSONL text into packed binary token shards.

Training reads from these shards instead of tokenizing text every epoch. This is
faster and gives repeatable training examples for interrupted Colab sessions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from matgpt.tokenizer.io import load_tokenizer, load_tokenizer_metadata
from matgpt.utils.hashing import sha256_file, sha256_json
from matgpt.data.prepare import effective_validation_split


DTYPES = {
    "uint16": np.uint16,
    "uint32": np.uint32,
}


def _flush_shard(
    tokens: list[int],
    output_dir: Path,
    split: str,
    shard_index: int,
    dtype: str,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{split}_{shard_index:05d}.bin"
    array = np.asarray(tokens, dtype=DTYPES[dtype])
    array.tofile(path)
    return {
        "path": str(path),
        "index": shard_index,
        "num_tokens": int(array.size),
        "sha256": sha256_file(path),
    }


def tokenize_jsonl_to_shards(
    input_path: str | Path,
    tokenizer_dir: str | Path,
    output_dir: str | Path,
    split: str,
    shard_size_tokens: int,
    dtype: str = "uint16",
    append_eos: bool = True,
) -> dict[str, Any]:
    """Encode documents, append EOS between documents, and write token shards."""

    if dtype not in DTYPES:
        raise ValueError(f"Unsupported dtype {dtype}; choose one of {sorted(DTYPES)}")

    tokenizer = load_tokenizer(tokenizer_dir)
    tokenizer_metadata = load_tokenizer_metadata(tokenizer_dir)
    eos_id = tokenizer.token_to_id("<|eos|>")
    if append_eos and eos_id is None:
        raise ValueError("Tokenizer must define <|eos|> when append_eos is true.")
    if dtype == "uint16" and tokenizer.get_vocab_size() > 65535:
        raise ValueError("uint16 shards require tokenizer vocab size <= 65535.")

    out = Path(output_dir)
    shard_tokens: list[int] = []
    shards: list[dict[str, Any]] = []
    total_tokens = 0
    total_documents = 0

    with Path(input_path).open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            ids = tokenizer.encode(record["text"]).ids
            if append_eos:
                ids.append(eos_id)
            total_documents += 1
            for token_id in ids:
                shard_tokens.append(int(token_id))
                total_tokens += 1
                if len(shard_tokens) >= shard_size_tokens:
                    shards.append(_flush_shard(shard_tokens, out, split, len(shards), dtype))
                    shard_tokens = []

    if shard_tokens:
        shards.append(_flush_shard(shard_tokens, out, split, len(shards), dtype))

    metadata = {
        "split": split,
        "input_path": str(Path(input_path)),
        "tokenizer_dir": str(Path(tokenizer_dir)),
        "tokenizer_sha256": tokenizer_metadata["tokenizer_sha256"],
        "dtype": dtype,
        "append_eos": append_eos,
        "shard_size_tokens": shard_size_tokens,
        "total_documents": total_documents,
        "total_tokens": total_tokens,
        "shards": shards,
    }
    metadata["metadata_sha256"] = sha256_json(metadata)
    (out / f"{split}_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metadata


def tokenize_splits_from_config(cfg: dict[str, Any]) -> dict[str, Any]:
    ds_cfg = cfg["dataset"]
    shard_cfg = cfg["sharding"]
    tokenizer_dir = cfg["tokenizer"]["output_dir"]
    normalized_dir = Path(ds_cfg["normalized_dir"])
    output_dir = Path(shard_cfg["output_dir"])

    results = {}
    validation_split = effective_validation_split(ds_cfg)
    for split in (ds_cfg["train_split"], validation_split):
        results[split] = tokenize_jsonl_to_shards(
            input_path=normalized_dir / f"{split}.jsonl",
            tokenizer_dir=tokenizer_dir,
            output_dir=output_dir,
            split=split,
            shard_size_tokens=shard_cfg["shard_size_tokens"],
            dtype=shard_cfg["dtype"],
            append_eos=shard_cfg["append_eos"],
        )
    combined = {"splits": results}
    combined["metadata_sha256"] = sha256_json(combined)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metadata.json").write_text(
        json.dumps(combined, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return combined
