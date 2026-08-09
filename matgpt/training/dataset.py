from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import numpy as np
import torch

from matgpt.data.shard import resolve_shard_artifact_path
from matgpt.utils.hashing import sha256_file, sha256_json
from matgpt.utils.paths import require_managed_path


NUMPY_DTYPES = {
    "uint16": np.uint16,
    "uint32": np.uint32,
}


@dataclass
class PackedShard:
    path: Path
    num_tokens: int
    data: np.memmap


class PackedTokenDataset:
    def __init__(self, shards: list[PackedShard], context_length: int, seed: int = 42) -> None:
        self.shards = [shard for shard in shards if shard.num_tokens > context_length]
        if not self.shards:
            raise ValueError("No shard has enough tokens for the requested context length.")
        self.context_length = context_length

        # Create this dataset's own random-number generator.
        self.rng = np.random.default_rng(seed)

        # Estimate how many starting positions each shard provides.
        weights = np.asarray([shard.num_tokens - context_length for shard in self.shards], dtype=np.float64)

        # Convert the raw weights into probabilities that add to 1.
        self.weights = weights / weights.sum()

    @classmethod
    def from_metadata(
        cls,
        metadata_path: str | Path,
        context_length: int,
        seed: int = 42,
        *,
        metadata_root: str | Path | None = None,
        finalized_root: str | Path | None = None,
        finalized_artifact: Mapping[str, object] | None = None,
    ) -> "PackedTokenDataset":
        # Read the shard metadata file.
        metadata_file, metadata = load_verified_shard_metadata(
            metadata_path,
            metadata_root=metadata_root,
            finalized_root=finalized_root,
            finalized_artifact=finalized_artifact,
        )

        # Find out whether the token IDs use uint16 or uint32.
        dtype = NUMPY_DTYPES[metadata["dtype"]]

        # creates a memory map:
        shards = []
        for shard in metadata["shards"]:
            path = resolve_shard_artifact_path(
                metadata_file,
                shard.get("path"),
                shard_root=metadata_root,
            )
            expected_tokens = int(shard["num_tokens"])
            expected_size = expected_tokens * np.dtype(dtype).itemsize
            if path.stat().st_size != expected_size:
                raise ValueError(
                    f"shard size mismatch: path={path} "
                    f"observed={path.stat().st_size} expected={expected_size}"
                )
            expected_sha256 = shard.get("sha256")
            if not isinstance(expected_sha256, str) or sha256_file(path) != expected_sha256:
                raise ValueError(f"shard SHA-256 mismatch: {path}")
            shards.append(
                PackedShard(
                    path=path,
                    num_tokens=expected_tokens,

                    # Make the binary file accessible like a NumPy array.
                    data=np.memmap(path, mode="r", dtype=dtype),
                )
            )
        return cls(shards=shards, context_length=context_length, seed=seed)

# batch_size means:
# "How many training examples should we create at once?"
    def sample_batch(self, batch_size: int, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
        # Create an empty number table for input examples.
        # Number of rows = batch_size.
        # Number of columns = context_length.
        x = np.empty((batch_size, self.context_length), dtype=np.int64)

        # Create another number table for target answers.
        # It has the same shape as x.
        y = np.empty((batch_size, self.context_length), dtype=np.int64)

        # Randomly choose which data shard each batch example comes from.
        shard_indices = self.rng.choice(len(self.shards), size=batch_size, p=self.weights)
        for row, shard_index in enumerate(shard_indices):
            shard = self.shards[int(shard_index)]
            start = int(self.rng.integers(0, shard.num_tokens - self.context_length - 1))

            # Take a slice from the long token stream.
            # Example window:
            window = np.asarray(shard.data[start : start + self.context_length + 1], dtype=np.int64)
            x[row] = window[:-1]
            y[row] = window[1:]

            # x and y started as numpy arrays
            # numpy arrays are block of numbers python can work with
            # torch.from_numpy(x) -> turns x into pytorch tensor
            # .to(device) -> move the tensor to the place where math will happen (GPU or CPU)
        return torch.from_numpy(x).to(device), torch.from_numpy(y).to(device)

    # Read this dataset RNG's current internal position.
    def get_rng_state(self) -> dict[str, Any]:
        return self.rng.bit_generator.state

    def set_rng_state(self, state: dict[str, Any]) -> None:
        # Move this dataset RNG back to its saved position.
        self.rng.bit_generator.state = state


def metadata_path_for_split(shard_dir: str | Path, split: str) -> Path:
    return Path(shard_dir) / f"{split}_metadata.json"


def load_verified_shard_metadata(
    metadata_path: str | Path,
    *,
    metadata_root: str | Path | None = None,
    finalized_root: str | Path | None = None,
    finalized_artifact: Mapping[str, object] | None = None,
    require_internal_fingerprint: bool = False,
) -> tuple[Path, dict[str, Any]]:
    """Load shard metadata and optionally bind it to final manifest evidence."""

    metadata_file = Path(metadata_path)
    configured_root = (
        Path(metadata_root) if metadata_root is not None else metadata_file.parent
    )
    configured_root = require_managed_path(
        configured_root, configured_root, kind="directory", allow_missing=False
    )
    metadata_file = require_managed_path(
        configured_root, metadata_file, kind="file", allow_missing=False
    )

    if finalized_artifact is not None:
        if finalized_root is None:
            raise ValueError("finalized_root is required for finalized manifest evidence")
        artifact_path = finalized_artifact.get("path")
        if not isinstance(artifact_path, str):
            raise ValueError("finalized manifest metadata path must be a safe relative path")
        relative = PurePosixPath(artifact_path)
        if (
            not artifact_path
            or "\\" in artifact_path
            or relative.is_absolute()
            or ".." in relative.parts
            or str(relative) != artifact_path
        ):
            raise ValueError("finalized manifest metadata path must be a safe relative path")
        evidence_root = Path(finalized_root)
        evidence_root = require_managed_path(
            evidence_root, evidence_root, kind="directory", allow_missing=False
        )
        finalized_file = require_managed_path(
            evidence_root,
            evidence_root / Path(*relative.parts),
            kind="file",
            allow_missing=False,
        )
        if metadata_file != finalized_file:
            raise ValueError(
                "configured shard metadata is not the file recorded by the finalized manifest"
            )
        expected_size = finalized_artifact.get("size")
        if (
            not isinstance(expected_size, int)
            or isinstance(expected_size, bool)
            or metadata_file.stat().st_size != expected_size
        ):
            raise ValueError(
                "configured shard metadata size does not match the finalized manifest"
            )
        expected_sha256 = finalized_artifact.get("sha256")
        if (
            not isinstance(expected_sha256, str)
            or sha256_file(metadata_file) != expected_sha256
        ):
            raise ValueError(
                "configured shard metadata SHA-256 does not match the finalized manifest"
            )

    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    stored_hash = metadata.get("metadata_sha256")
    if (
        stored_hash is not None
        or finalized_artifact is not None
        or require_internal_fingerprint
    ):
        unsigned = dict(metadata)
        unsigned.pop("metadata_sha256", None)
        if not isinstance(stored_hash, str) or stored_hash != sha256_json(unsigned):
            raise ValueError(
                f"{metadata_file.name} metadata_sha256 does not match metadata content"
            )
    if (
        finalized_artifact is not None
        and finalized_artifact.get("metadata_sha256") != stored_hash
    ):
        raise ValueError(
            "configured shard metadata internal fingerprint does not match the "
            "finalized manifest"
        )
    return metadata_file, metadata


def finalized_split_metadata_artifacts(
    manifest_path: str | Path,
    splits: tuple[str, ...],
) -> tuple[Path, dict[str, Mapping[str, object]]] | None:
    """Return manifest-bound metadata evidence for chunked training inputs."""

    path = Path(manifest_path)
    if not path.exists():
        return None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("storage_format") != "chunked_prebuilt_v1":
        return None
    unsigned = dict(manifest)
    stored_hash = unsigned.pop("manifest_sha256", None)
    if not isinstance(stored_hash, str) or stored_hash != sha256_json(unsigned):
        raise ValueError("finalized dataset manifest checksum does not match its content")
    if manifest.get("complete") is not True or manifest.get("status") != "complete":
        raise ValueError("finalized dataset manifest is not complete")
    records = manifest.get("split_metadata")
    if not isinstance(records, dict):
        raise ValueError("finalized dataset manifest has no split metadata")
    selected: dict[str, Mapping[str, object]] = {}
    for split in splits:
        record = records.get(split)
        if not isinstance(record, Mapping):
            raise ValueError(
                f"finalized dataset manifest has no metadata for split {split!r}"
            )
        selected[split] = record
    return path.parent, selected
