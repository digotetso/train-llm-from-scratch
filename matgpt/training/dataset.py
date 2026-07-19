from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch


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
    def from_metadata(cls, metadata_path: str | Path, context_length: int, seed: int = 42) -> "PackedTokenDataset":
        # Read the shard metadata file.
        metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))

        # Find out whether the token IDs use uint16 or uint32.
        dtype = NUMPY_DTYPES[metadata["dtype"]]

        # creates a memory map:
        shards = [
            PackedShard(
                path=Path(shard["path"]),
                num_tokens=int(shard["num_tokens"]),

                # Make the binary file accessible like a NumPy array.
                data=np.memmap(shard["path"], mode="r", dtype=dtype),
            )
            for shard in metadata["shards"]
        ]
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
