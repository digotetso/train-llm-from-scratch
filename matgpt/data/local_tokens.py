"""Batch encoding and bounded binary token-shard writing for local builds."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
from tokenizers import Tokenizer

from matgpt.utils.hashing import sha256_file


DTYPES = {
    "uint16": np.uint16,
    "uint32": np.uint32,
}
_WRITE_BLOCK_TOKENS = 1_048_576


@dataclass(frozen=True)
class EncodedRecord:
    record: Mapping[str, object]
    ids: tuple[int, ...]

    @property
    def quota_tokens(self) -> int:
        """Return tokenizer IDs before the writer adds a document EOS."""

        return len(self.ids)


def encode_record_batch(
    tokenizer: Tokenizer,
    records: Sequence[Mapping[str, object]],
) -> list[EncodedRecord]:
    """Encode a record batch once, preserving its order and source records."""

    encodings = tokenizer.encode_batch([str(record["text"]) for record in records])
    return [
        EncodedRecord(
            record=record,
            ids=tuple(int(token_id) for token_id in encoding.ids),
        )
        for record, encoding in zip(records, encodings, strict=True)
    ]


class PackedShardWriter:
    """Write EOS-delimited documents into bounded, immutable binary shards."""

    def __init__(
        self,
        *,
        output_dir: str | Path,
        split: str,
        dtype: str,
        shard_size_tokens: int,
        eos_id: int,
    ) -> None:
        if dtype not in DTYPES:
            raise ValueError(f"Unsupported dtype {dtype}; choose one of {sorted(DTYPES)}")
        if shard_size_tokens <= 0:
            raise ValueError("shard_size_tokens must be positive")
        if not split or Path(split).name != split:
            raise ValueError("split must be a single safe path component")

        self.output_dir = Path(output_dir).resolve()
        self.split = split
        self.dtype = dtype
        self.numpy_dtype = np.dtype(DTYPES[dtype])
        self.shard_size_tokens = shard_size_tokens
        self.eos_id = int(eos_id)
        self._minimum_id = int(np.iinfo(self.numpy_dtype).min)
        self._maximum_id = int(np.iinfo(self.numpy_dtype).max)
        self._validate_ids((self.eos_id,))

        self._handle = None
        self._partial_path: Path | None = None
        self._current_tokens = 0
        self._next_index = 0
        self._shards: list[dict[str, object]] = []

    def append_document(self, ids: Sequence[int]) -> None:
        """Append one encoded document followed by exactly one EOS token."""

        position = 0
        total_ids = len(ids)
        while position < total_ids:
            room = self.shard_size_tokens - self._current_tokens
            if room == 0:
                self.seal_unit()
                continue
            count = min(room, total_ids - position, _WRITE_BLOCK_TOKENS)
            self._write_piece(ids[position : position + count])
            position += count

        self._write_eos()

    def seal_unit(self) -> dict[str, object] | None:
        """Seal a non-empty current shard, including intentionally short units."""

        if self._handle is None:
            return None

        handle = self._handle
        partial_path = self._partial_path
        if partial_path is None:
            raise RuntimeError("active shard has no partial path")
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()

        final_path = self._final_path(self._next_index)
        os.replace(partial_path, final_path)
        shard = {
            "path": str(final_path),
            "relative_path": final_path.name,
            "index": self._next_index,
            "byte_size": final_path.stat().st_size,
            "num_tokens": self._current_tokens,
            "sha256": sha256_file(final_path),
        }
        self._shards.append(shard)
        self._next_index += 1
        self._handle = None
        self._partial_path = None
        self._current_tokens = 0
        return shard

    def finalize(self) -> list[dict[str, object]]:
        """Seal the remaining shard and return all immutable shard artifacts."""

        self.seal_unit()
        return list(self._shards)

    def _write_eos(self) -> None:
        if self._current_tokens == self.shard_size_tokens:
            self.seal_unit()
        self._write_piece((self.eos_id,))

    def _write_piece(self, ids: Sequence[int]) -> None:
        if not ids:
            return
        self._validate_ids(ids)
        if self._handle is None:
            self._open_shard()
        values = np.asarray(ids, dtype=self.numpy_dtype)
        self._handle.write(values.tobytes(order="C"))
        self._current_tokens += int(values.size)
        if self._current_tokens == self.shard_size_tokens:
            self.seal_unit()

    def _open_shard(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        partial_path = self.output_dir / f"{self.split}_{self._next_index:05d}.bin.partial"
        self._handle = partial_path.open("xb")
        self._partial_path = partial_path

    def _final_path(self, index: int) -> Path:
        return self.output_dir / f"{self.split}_{index:05d}.bin"

    def _validate_ids(self, ids: Sequence[int]) -> None:
        values = np.asarray(ids, dtype=np.int64)
        if values.size and (
            int(values.min()) < self._minimum_id or int(values.max()) > self._maximum_id
        ):
            raise ValueError(f"token IDs must fit {self.dtype}")
