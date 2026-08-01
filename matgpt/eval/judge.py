from __future__ import annotations

import json
import random
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Iterable, Mapping, Sequence


ALLOWED_FLAGS = frozenset(
    {
        "character_swap",
        "object_swap",
        "location_conflict",
        "state_reversal",
        "causal_break",
        "ending_break",
        "none",
    }
)
SCORE_FIELDS = (
    "character_consistency",
    "object_location_consistency",
    "causal_coherence",
    "overall_consistency",
)
JUDGMENT_FIELDS = frozenset(
    {"review_id", *SCORE_FIELDS, "flags", "evidence", "reason"}
)
VISIBLE_FIELDS = frozenset({"review_id", "prompt", "text"})
FORBIDDEN_VISIBLE_FIELDS = frozenset(
    {
        "checkpoint",
        "checkpoint_label",
        "checkpoint_path",
        "generation_id",
        "generation_seed",
        "prompt_id",
        "tokens_seen",
        "validation_loss",
        "validation_seed",
    }
)


def _required_generation_text(
    row: Mapping[str, object], field: str, checkpoint_label: str
) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"generation for checkpoint {checkpoint_label!r} has invalid {field!r}"
        )
    return value


def build_judge_bundle(
    generations_by_checkpoint: Mapping[str, Sequence[Mapping[str, object]]],
    per_checkpoint: int,
    review_seed: int,
    batch_size: int = 20,
) -> dict[str, object]:
    if isinstance(per_checkpoint, bool) or per_checkpoint <= 0:
        raise ValueError("per_checkpoint must be a positive integer")
    if isinstance(batch_size, bool) or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    if not generations_by_checkpoint:
        raise ValueError("at least one checkpoint is required")

    rng = random.Random(review_seed)
    selected: list[tuple[str, Mapping[str, object]]] = []
    seen_generation_ids: set[str] = set()
    for checkpoint_label in sorted(generations_by_checkpoint):
        rows = list(generations_by_checkpoint[checkpoint_label])
        if len(rows) < per_checkpoint:
            raise ValueError(
                f"checkpoint {checkpoint_label!r} has {len(rows)} generations; "
                f"{per_checkpoint} required"
            )
        for row in rows:
            generation_id = _required_generation_text(
                row, "generation_id", checkpoint_label
            )
            _required_generation_text(row, "prompt_id", checkpoint_label)
            _required_generation_text(row, "prompt", checkpoint_label)
            _required_generation_text(row, "text", checkpoint_label)
            generation_seed = row.get("generation_seed")
            if isinstance(generation_seed, bool) or not isinstance(
                generation_seed, int
            ):
                raise ValueError(
                    f"generation {generation_id!r} has an invalid generation_seed"
                )
            if generation_id in seen_generation_ids:
                raise ValueError(f"duplicate generation id: {generation_id!r}")
            seen_generation_ids.add(generation_id)
        selected.extend(
            (checkpoint_label, rows[index])
            for index in rng.sample(range(len(rows)), per_checkpoint)
        )

    rng.shuffle(selected)
    visible_rows: list[dict[str, str]] = []
    review_key: dict[str, dict[str, object]] = {}
    for index, (checkpoint_label, row) in enumerate(selected, start=1):
        review_id = f"review-{index:04d}"
        visible_rows.append(
            {
                "review_id": review_id,
                "prompt": str(row["prompt"]),
                "text": str(row["text"]),
            }
        )
        review_key[review_id] = {
            "checkpoint_label": checkpoint_label,
            "generation_id": row["generation_id"],
            "prompt_id": row["prompt_id"],
            "generation_seed": row["generation_seed"],
        }

    batches = [
        visible_rows[index : index + batch_size]
        for index in range(0, len(visible_rows), batch_size)
    ]
    return {
        "review_seed": review_seed,
        "per_checkpoint": per_checkpoint,
        "batch_size": batch_size,
        "batches": batches,
        "review_key": review_key,
    }


def validate_judgments(
    rows: Iterable[Mapping[str, object]], expected_review_ids: set[str]
) -> list[dict[str, object]]:
    checked: list[dict[str, object]] = []
    seen: set[str] = set()
    for position, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            raise ValueError(f"judgment {position} must be an object")
        review_id = row.get("review_id")
        if not isinstance(review_id, str) or not review_id.strip():
            raise ValueError(f"judgment {position} has an invalid review_id")
        if review_id not in expected_review_ids:
            raise ValueError(f"unknown review id: {review_id!r}")
        if review_id in seen:
            raise ValueError(f"duplicate review id: {review_id!r}")

        missing = JUDGMENT_FIELDS - set(row)
        if missing:
            raise ValueError(
                f"judgment {review_id!r} is missing {sorted(missing)[0]}"
            )
        extra = set(row) - JUDGMENT_FIELDS
        if extra:
            raise ValueError(
                f"judgment {review_id!r} has unexpected field {sorted(extra)[0]!r}"
            )

        normalized: dict[str, object] = {"review_id": review_id}
        for field in SCORE_FIELDS:
            value = row[field]
            if isinstance(value, bool) or not isinstance(value, int) or value not in {
                0,
                1,
                2,
            }:
                raise ValueError(f"{field} must be the integer 0, 1, or 2")
            normalized[field] = value

        flags = row["flags"]
        if not isinstance(flags, list) or any(
            not isinstance(flag, str) for flag in flags
        ):
            raise ValueError("flags must be a list of strings")
        if len(flags) != len(set(flags)):
            raise ValueError("flags must not contain duplicates")
        unknown_flags = set(flags) - ALLOWED_FLAGS
        if unknown_flags:
            raise ValueError(f"unsupported judgment flag: {sorted(unknown_flags)[0]!r}")
        if "none" in flags and len(flags) != 1:
            raise ValueError("the none flag cannot be combined with other flags")
        normalized["flags"] = list(flags)

        for field in ("evidence", "reason"):
            value = row[field]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be non-empty text")
            value = value.strip()
            if len(value) > 500:
                raise ValueError(f"{field} must not exceed 500 characters")
            normalized[field] = value

        seen.add(review_id)
        checked.append(normalized)

    missing_ids = expected_review_ids - seen
    if missing_ids:
        raise ValueError(f"missing review ids: {sorted(missing_ids)}")
    return checked


def summarize_judgments(
    rows: Sequence[Mapping[str, object]],
    review_key: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for row in rows:
        review_id = str(row["review_id"])
        key_row = review_key.get(review_id)
        if key_row is None:
            raise ValueError(f"review key is missing {review_id!r}")
        checkpoint_label = key_row.get("checkpoint_label")
        if not isinstance(checkpoint_label, str) or not checkpoint_label:
            raise ValueError(f"review key entry {review_id!r} has no checkpoint label")
        grouped.setdefault(checkpoint_label, []).append(row)

    checkpoint_summaries: dict[str, object] = {}
    for checkpoint_label in sorted(grouped):
        checkpoint_rows = grouped[checkpoint_label]
        summary: dict[str, object] = {"story_count": len(checkpoint_rows)}
        for field in SCORE_FIELDS:
            values = [int(row[field]) for row in checkpoint_rows]
            distribution = Counter(values)
            summary[f"mean_{field}"] = mean(values)
            summary[f"{field}_distribution"] = {
                str(score): distribution[score] for score in (0, 1, 2)
            }
        flag_counts = Counter(
            flag
            for row in checkpoint_rows
            for flag in row["flags"]
            if flag != "none"
        )
        summary["flag_counts"] = {
            flag: flag_counts[flag] for flag in sorted(flag_counts)
        }
        checkpoint_summaries[checkpoint_label] = summary

    return {
        "review_count": len(rows),
        "checkpoints": checkpoint_summaries,
    }


def _json_text(value: object) -> str:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True
    ) + "\n"


def write_judge_bundle(
    root: Path, bundle: Mapping[str, object], prompt_text: str
) -> None:
    batches = bundle.get("batches")
    review_key = bundle.get("review_key")
    if not isinstance(batches, list) or not isinstance(review_key, Mapping):
        raise ValueError("judge bundle must contain batches and a review key")
    for batch in batches:
        if not isinstance(batch, list):
            raise ValueError("each judge batch must be a list")
        for row in batch:
            if not isinstance(row, Mapping):
                raise ValueError("each judge-visible row must be an object")
            leaked = set(row) & FORBIDDEN_VISIBLE_FIELDS
            if leaked:
                raise ValueError(f"judge-visible identity leak: {sorted(leaked)[0]}")
            if set(row) != VISIBLE_FIELDS:
                raise ValueError("judge-visible rows must contain only review_id, prompt, and text")

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    target = root / "llm_judge"
    if target.exists():
        raise FileExistsError(f"judge bundle already exists: {target}")

    staging = Path(tempfile.mkdtemp(prefix=".llm_judge-", dir=root))
    try:
        batch_root = staging / "batches"
        batch_root.mkdir()
        (staging / "results").mkdir()
        (staging / "judge_prompt.md").write_text(prompt_text, encoding="utf-8")
        (staging / "review_key.json").write_text(
            _json_text(review_key), encoding="utf-8"
        )
        width = max(2, len(str(len(batches))))
        for index, batch in enumerate(batches, start=1):
            lines = [
                json.dumps(row, ensure_ascii=False, allow_nan=False, sort_keys=True)
                for row in batch
            ]
            (batch_root / f"judge_batch_{index:0{width}d}.jsonl").write_text(
                "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
            )
        staging.rename(target)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
