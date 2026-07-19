from __future__ import annotations

from pathlib import Path
from typing import Mapping

from matgpt.utils.logging import append_csv_row


METRIC_FIELDS = (
    "event",
    "attempted_step",
    "global_step",
    "tokens_processed",
    "train_loss",
    "val_loss",
    "val_perplexity",
    "lr",
    "grad_norm",
    "grad_scale",
    "optimizer_step_skipped",
    "optimizer_steps_skipped_total",
    "consecutive_optimizer_steps_skipped",
    "tokens_per_second",
    "peak_memory_mb",
    "elapsed_seconds",
)


def append_metric(path: str | Path, row: Mapping[str, object]) -> None:
    append_csv_row(path, row, fieldnames=METRIC_FIELDS)


def calculate_tokens_per_second(
    start_tokens: int,
    current_tokens: int,
    elapsed_seconds: float,
) -> float:
    return (current_tokens - start_tokens) / max(elapsed_seconds, 1e-6)
