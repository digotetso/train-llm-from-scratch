"""Convert normalized JSONL text into packed binary token shards.

Training reads from these shards instead of tokenizing text every epoch. This is
faster and gives repeatable training examples for interrupted Colab sessions.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np

from matgpt.data.prepare import effective_validation_split
from matgpt.data.token_dtype import DTYPES, validate_token_ids
from matgpt.tokenizer.io import load_tokenizer, load_tokenizer_metadata
from matgpt.utils.hashing import sha256_file, sha256_json
from matgpt.utils.paths import require_managed_path


def resolve_shard_artifact_path(
    metadata_path: str | Path,
    artifact_path: object,
    *,
    shard_root: str | Path | None = None,
) -> Path:
    """Resolve legacy absolute or portable relative shards below one root."""

    metadata_file = Path(metadata_path)
    root = Path(shard_root) if shard_root is not None else metadata_file.parent
    root = require_managed_path(root, root, kind="directory", allow_missing=False)
    if not isinstance(artifact_path, str) or not artifact_path:
        raise ValueError("shard path must be a safe relative or in-root absolute path")
    candidate = Path(artifact_path)
    if candidate.is_absolute():
        if ".." in candidate.parts:
            raise ValueError("shard path must be a safe relative or in-root absolute path")
    else:
        relative = PurePosixPath(artifact_path)
        if (
            "\\" in artifact_path
            or ".." in relative.parts
            or str(relative) != artifact_path
        ):
            raise ValueError("shard path must be a safe relative or in-root absolute path")
        candidate = metadata_file.parent / Path(*relative.parts)
    return require_managed_path(
        root, candidate, kind="file", allow_missing=False
    )


def _flush_shard(
    tokens: list[int],
    output_dir: Path,
    split: str,
    shard_index: int,
    dtype: str,
) -> dict[str, Any]:
    validate_token_ids(tokens, dtype)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{split}_{shard_index:05d}.bin"
    array = np.asarray(tokens, dtype=DTYPES[dtype])
    array.tofile(path)
    return {
        "path": str(path.resolve()),
        "relative_path": path.name,
        "index": shard_index,
        "byte_size": path.stat().st_size,
        "num_tokens": int(array.size),
        "sha256": sha256_file(path),
    }


def build_split_metadata(
    *,
    split: str,
    tokenizer_sha256: str,
    dtype: str,
    append_eos: bool,
    shard_size_tokens: int,
    total_documents: int,
    shards: list[dict[str, object]],
) -> dict[str, object]:
    """Build portable split metadata from local shard artifacts.

    Local artifact records retain their absolute ``path`` for publication,
    while public metadata stores only the checked relative publication path.
    """

    public_shards = []
    for shard in shards:
        relative_path = shard.get("relative_path")
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError("shard artifacts must include a non-empty relative_path")
        relative = Path(relative_path)
        if (
            relative.is_absolute()
            or relative == Path(".")
            or ".." in relative.parts
        ):
            raise ValueError(f"unsafe shard relative_path: {relative_path!r}")
        public_shards.append(
            {
                key: value
                for key, value in shard.items()
                if key not in {"path", "relative_path"}
            }
            | {"path": relative_path}
        )

    metadata: dict[str, object] = {
        "split": split,
        "tokenizer_sha256": tokenizer_sha256,
        "dtype": dtype,
        "append_eos": append_eos,
        "shard_size_tokens": shard_size_tokens,
        "total_documents": total_documents,
        "total_tokens": sum(int(shard["num_tokens"]) for shard in public_shards),
        "shards": public_shards,
    }
    metadata["metadata_sha256"] = sha256_json(metadata)
    return metadata


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

    # Find the EOS token's ID.
    eos_id = tokenizer.token_to_id("<|eos|>")

    if append_eos and eos_id is None:
        raise ValueError("Tokenizer must define <|eos|> when append_eos is true.")
    max_token_id = int(np.iinfo(DTYPES[dtype]).max)
    if tokenizer.get_vocab_size() > max_token_id + 1:
        raise ValueError(
            f"{dtype} shards require tokenizer vocab size <= {max_token_id + 1}."
        )
    if append_eos:
        validate_token_ids((eos_id,), dtype)

    out = Path(output_dir)
    shard_tokens: list[int] = []
    shards: list[dict[str, Any]] = []
    total_documents = 0

    with Path(input_path).open("r", encoding="utf-8") as f:
        # Read one prepared JSONL record at a time.
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)

            # Take the text.
            # Split it into tokens.
            # Convert those tokens into token IDs.
            # Store the result in ids.
            ids = tokenizer.encode(record["text"]).ids
            validate_token_ids(ids, dtype)

            # Add EOS after every document.
            # Mark the end of the document.
            if append_eos:
                ids.append(eos_id)

            total_documents += 1

            # Add each ID to the current shard.
            # The list is not cleared after each document. It is cleared only when the current shard becomes full.
            # Those IDs are appended to the same shard list:
            for token_id in ids:
                shard_tokens.append(int(token_id))

                # Has the shard reached its requested size?
                if len(shard_tokens) >= shard_size_tokens:
                    # Write this shard to disk.
                    shards.append(_flush_shard(shard_tokens, out, split, len(shards), dtype))

                    # Start collecting the next shard.
                    shard_tokens = []
    #  After all documents are processed, the remaining partial shard is also saved:
    if shard_tokens:
        shards.append(_flush_shard(shard_tokens, out, split, len(shards), dtype))

    metadata = build_split_metadata(
        split=split,
        tokenizer_sha256=tokenizer_metadata["tokenizer_sha256"],
        dtype=dtype,
        append_eos=append_eos,
        shard_size_tokens=shard_size_tokens,
        total_documents=total_documents,
        shards=shards,
    )
    metadata.update({
        "input_path": str(Path(input_path)),
        "tokenizer_dir": str(Path(tokenizer_dir)),
    })
    metadata.pop("metadata_sha256")
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
    training_splits = ds_cfg.get("training_splits")
    if training_splits:
        splits = list(dict.fromkeys(training_splits.values()))
    else:
        splits = [ds_cfg["train_split"]]
    if validation_split not in splits:
        splits.append(validation_split)
    for split in splits:
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
