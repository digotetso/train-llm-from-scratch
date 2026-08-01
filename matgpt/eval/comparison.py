from __future__ import annotations

import math
import re
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from statistics import mean, stdev
from typing import Mapping, Sequence

from matgpt.eval.repetition import aggregate_repetition


LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MAX_SEED = 2**63


@dataclass(frozen=True)
class CheckpointSpec:
    label: str
    path: Path


def parse_seed_list(raw: str, name: str) -> list[int]:
    values = raw.split(",")
    if not values or any(not value.strip() for value in values):
        raise ValueError(f"{name} seeds must be a comma-separated list of integers.")

    seeds: list[int] = []
    seen: set[int] = set()
    for value in values:
        try:
            seed = int(value.strip())
        except ValueError as error:
            raise ValueError(f"invalid {name} seed: {value!r}") from error
        if not 0 <= seed < MAX_SEED:
            raise ValueError(f"{name} seed outside supported range: {seed}")
        if seed in seen:
            raise ValueError(f"duplicate {name} seed: {seed}")
        seen.add(seed)
        seeds.append(seed)
    return seeds


def parse_checkpoint_specs(
    values: Sequence[str], require_files: bool = True
) -> list[CheckpointSpec]:
    specs: list[CheckpointSpec] = []
    labels: set[str] = set()
    for value in values:
        label, separator, raw_path = value.partition("=")
        if not separator or not raw_path:
            raise ValueError("checkpoint must use LABEL=PATH format")
        if not LABEL_RE.fullmatch(label):
            raise ValueError(f"unsafe checkpoint label: {label!r}")
        if label in labels:
            raise ValueError(f"duplicate checkpoint label: {label!r}")
        path = Path(raw_path).expanduser()
        if require_files and not path.is_file():
            raise ValueError(f"checkpoint file does not exist: {path}")
        labels.add(label)
        specs.append(CheckpointSpec(label=label, path=path))
    return specs


def _validated_seed_losses(
    label: str, rows: Sequence[Mapping[str, float | int]]
) -> dict[int, float]:
    if not rows:
        raise ValueError(f"checkpoint {label!r} has no validation results")
    losses: dict[int, float] = {}
    for row in rows:
        seed_value = row.get("seed")
        if isinstance(seed_value, bool) or not isinstance(seed_value, int):
            raise ValueError(f"checkpoint {label!r} contains an invalid seed")
        if seed_value in losses:
            raise ValueError(
                f"checkpoint {label!r} repeats validation seed {seed_value}"
            )
        try:
            loss = float(row["loss"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                f"checkpoint {label!r} contains an invalid validation loss"
            ) from error
        if not math.isfinite(loss):
            raise ValueError("validation losses must be finite")
        losses[seed_value] = loss
    return losses


def summarize_validation(
    results: Mapping[str, Sequence[Mapping[str, float | int]]],
) -> dict[str, object]:
    if not results:
        raise ValueError("at least one checkpoint result is required")

    by_checkpoint = {
        label: _validated_seed_losses(label, rows) for label, rows in results.items()
    }
    labels = sorted(by_checkpoint)
    reference_seeds = set(by_checkpoint[labels[0]])
    if any(set(by_checkpoint[label]) != reference_seeds for label in labels[1:]):
        raise ValueError("all checkpoints must use the same validation seeds")

    checkpoint_summaries: dict[str, object] = {}
    for label in labels:
        losses = list(by_checkpoint[label].values())
        checkpoint_summaries[label] = {
            "seed_count": len(losses),
            "mean_loss": mean(losses),
            "stdev_loss": stdev(losses) if len(losses) > 1 else 0.0,
            "minimum_loss": min(losses),
            "maximum_loss": max(losses),
        }

    pair_summaries = []
    for left, right in combinations(labels, 2):
        differences = []
        left_wins = 0
        right_wins = 0
        ties = 0
        per_seed = []
        for seed in sorted(reference_seeds):
            left_loss = by_checkpoint[left][seed]
            right_loss = by_checkpoint[right][seed]
            difference = left_loss - right_loss
            differences.append(difference)
            if abs(difference) <= 1e-12:
                ties += 1
            elif difference < 0:
                left_wins += 1
            else:
                right_wins += 1
            per_seed.append(
                {
                    "seed": seed,
                    "left_loss": left_loss,
                    "right_loss": right_loss,
                    "loss_difference": difference,
                }
            )
        mean_difference = mean(differences)
        if abs(mean_difference) <= 1e-12:
            mean_difference = 0.0
        pair_summaries.append(
            {
                "left": left,
                "right": right,
                "seed_count": len(reference_seeds),
                "left_wins": left_wins,
                "right_wins": right_wins,
                "ties": ties,
                "mean_loss_difference": mean_difference,
                "seeds": per_seed,
            }
        )

    return {"checkpoints": checkpoint_summaries, "pairs": pair_summaries}


def summarize_generations(
    generations: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    repetition_rows = []
    for row in generations:
        repetition = row.get("repetition")
        if not isinstance(repetition, dict):
            raise ValueError("each generation must contain repetition metrics")
        repetition_rows.append(repetition)

    word_counts = [int(row["word_count"]) for row in repetition_rows]
    return {
        "generation_count": len(generations),
        "minimum_word_count": min(word_counts) if word_counts else 0,
        "mean_word_count": mean(word_counts) if word_counts else 0.0,
        "maximum_word_count": max(word_counts) if word_counts else 0,
        "repetition": aggregate_repetition(repetition_rows),
    }
