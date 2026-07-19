from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from matgpt.training.optim import cosine_warmup_lr


@dataclass(frozen=True)
class TrainingSchedule:
    tokens_per_step: int
    total_steps: int
    warmup_steps: int
    stop_step: int


def build_training_schedule(
    cfg: dict[str, Any],
    global_step: int = 0,
    max_steps_override: int | None = None,
) -> TrainingSchedule:
    if max_steps_override is not None and max_steps_override < 1:
        raise ValueError("max_steps_override must be positive")
    training = cfg["training"]
    tokens_per_step = (
        training["micro_batch_size"]
        * training["gradient_accumulation_steps"]
        * cfg["model"]["context_length"]
    )
    total_steps = max(1, math.ceil(training["max_tokens"] / tokens_per_step))
    warmup_steps = max(1, int(total_steps * training["warmup_ratio"]))
    stop_step = total_steps
    if max_steps_override is not None:
        stop_step = min(total_steps, global_step + max_steps_override)
    return TrainingSchedule(tokens_per_step, total_steps, warmup_steps, stop_step)


def learning_rate_at_step(
    cfg: dict[str, Any],
    schedule: TrainingSchedule,
    step: int,
) -> float:
    return cosine_warmup_lr(
        step=step,
        warmup_steps=schedule.warmup_steps,
        total_steps=schedule.total_steps,
        max_lr=cfg["training"]["learning_rate"],
        min_lr=cfg["training"]["min_learning_rate"],
    )
