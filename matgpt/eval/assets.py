from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from matgpt.eval.tasks import load_multiple_choice_examples


CONSISTENCY_CATEGORIES = frozenset(
    {"character", "object_attribute", "location_state", "cause_effect"}
)


@dataclass(frozen=True)
class StoryPrompt:
    id: str
    category: str
    text: str


def _required_text(row: dict[str, object], field: str, line_number: int) -> str:
    if field not in row:
        raise ValueError(f"Line {line_number} is missing {field!r}.")
    value = row[field]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Line {line_number} must contain a non-empty {field!r}.")
    return value.strip()


def load_story_prompts(path: str | Path) -> list[StoryPrompt]:
    prompt_path = Path(path)
    prompts: list[StoryPrompt] = []
    seen_ids: set[str] = set()
    seen_text: set[str] = set()

    with prompt_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON at {prompt_path}:{line_number}: {error.msg}"
                ) from error
            if not isinstance(row, dict):
                raise ValueError(f"Line {line_number} must contain a JSON object.")

            prompt_id = _required_text(row, "id", line_number)
            category = _required_text(row, "category", line_number)
            text = _required_text(row, "text", line_number)
            if prompt_id in seen_ids:
                raise ValueError(f"Duplicate prompt id: {prompt_id!r}")
            if text in seen_text:
                raise ValueError(f"Duplicate prompt text at line {line_number}.")
            seen_ids.add(prompt_id)
            seen_text.add(text)
            prompts.append(StoryPrompt(id=prompt_id, category=category, text=text))

    return prompts


def validate_consistency_asset(path: str | Path) -> dict[str, int]:
    examples = load_multiple_choice_examples(path)
    seen_ids: set[str] = set()
    seen_content: set[tuple[str, tuple[str, ...]]] = set()
    counts: Counter[str] = Counter()

    for example in examples:
        if example.category not in CONSISTENCY_CATEGORIES:
            raise ValueError(f"Unsupported consistency category: {example.category!r}")
        if not example.id.startswith(f"{example.category}-"):
            raise ValueError(
                f"Example id {example.id!r} must start with {example.category!r}."
            )
        if example.id in seen_ids:
            raise ValueError(f"Duplicate consistency example id: {example.id!r}")
        content_key = (example.prompt, tuple(example.choices))
        if content_key in seen_content:
            raise ValueError(f"Duplicate prompt and choices for {example.id!r}.")
        seen_ids.add(example.id)
        seen_content.add(content_key)
        counts[example.category] += 1

    if set(counts) != CONSISTENCY_CATEGORIES:
        missing = sorted(CONSISTENCY_CATEGORIES - set(counts))
        raise ValueError(f"Consistency asset is missing categories: {missing}")
    return {category: counts[category] for category in sorted(counts)}
