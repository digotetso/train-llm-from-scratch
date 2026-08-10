"""Shared token-ID dtype constraints for binary shard writers."""

from __future__ import annotations

from typing import Sequence

import numpy as np


DTYPES = {
    "uint16": np.uint16,
    "uint32": np.uint32,
}


def validate_token_ids(ids: Sequence[int], dtype: str) -> None:
    """Reject token IDs that cannot be represented by ``dtype``."""

    if dtype not in DTYPES:
        raise ValueError(f"Unsupported dtype {dtype}; choose one of {sorted(DTYPES)}")
    try:
        values = np.asarray(ids, dtype=np.int64)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"token IDs must fit {dtype}") from exc
    limits = np.iinfo(DTYPES[dtype])
    if values.size and (
        int(values.min()) < int(limits.min)
        or int(values.max()) > int(limits.max)
    ):
        raise ValueError(f"token IDs must fit {dtype}")
