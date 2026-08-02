"""Tokenizer fertility and round-trip checks for fixed probe sets."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


PROBE_KEYS = frozenset({"version", "groups"})
WORD_PATTERN = re.compile(r"\w+(?:[-./]\w+)*", flags=re.UNICODE)


def load_probe_sets(path: str | Path) -> dict[str, list[str]]:
    probe_path = Path(path)
    with probe_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Tokenizer probes must be a mapping: {probe_path}")
    unknown = set(payload) - PROBE_KEYS
    if unknown:
        raise ValueError(f"Tokenizer probes contain unknown keys: {sorted(unknown)}")
    if payload.get("version") != 1:
        raise ValueError("Tokenizer probe version must be 1.")
    groups = payload.get("groups")
    if not isinstance(groups, dict) or not groups:
        raise ValueError("Tokenizer probes require a non-empty groups mapping.")

    result: dict[str, list[str]] = {}
    for group_name, texts in groups.items():
        if not isinstance(group_name, str) or not group_name.strip():
            raise ValueError("Tokenizer probe group names must be non-empty strings.")
        if not isinstance(texts, list) or not texts:
            raise ValueError(
                f"Tokenizer probe group {group_name!r} requires a non-empty list."
            )
        normalized: list[str] = []
        for text in texts:
            if not isinstance(text, str) or not text.strip():
                raise ValueError(
                    f"Tokenizer probe group {group_name!r} contains empty text."
                )
            normalized.append(text.strip())
        if len(normalized) != len(set(normalized)):
            raise ValueError(
                f"Tokenizer probe group {group_name!r} contains duplicate text."
            )
        result[group_name.strip()] = normalized
    return result


def measure_tokenizer_fertility(
    tokenizer,
    probe_sets: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    """Measure token fragmentation and require exact byte-level round trips."""

    if not probe_sets:
        raise ValueError("At least one tokenizer probe group is required.")
    vocabulary_size = int(tokenizer.get_vocab_size())
    groups: dict[str, Any] = {}
    round_trip_failures: list[dict[str, str]] = []
    invalid_token_ids: list[dict[str, Any]] = []

    for group_name in sorted(probe_sets):
        texts = probe_sets[group_name]
        if not texts:
            raise ValueError(f"Tokenizer probe group {group_name!r} is empty.")
        rows: list[dict[str, Any]] = []
        total_chars = 0
        total_words = 0
        total_tokens = 0
        for text in texts:
            if not isinstance(text, str) or not text:
                raise ValueError(
                    f"Tokenizer probe group {group_name!r} contains empty text."
                )
            encoding = tokenizer.encode(text)
            token_ids = [int(token_id) for token_id in encoding.ids]
            if not token_ids:
                raise ValueError(f"Tokenizer produced no IDs for probe {text!r}.")
            bad_ids = [
                token_id
                for token_id in token_ids
                if token_id < 0 or token_id >= vocabulary_size
            ]
            if bad_ids:
                invalid_token_ids.append(
                    {"group": group_name, "text": text, "ids": bad_ids}
                )
                raise ValueError(
                    f"Tokenizer produced invalid IDs for probe {text!r}: {bad_ids}."
                )
            decoded = tokenizer.decode(token_ids)
            if decoded != text:
                round_trip_failures.append(
                    {"group": group_name, "text": text, "decoded": decoded}
                )
                raise ValueError(
                    f"Tokenizer failed exact round trip for probe {text!r}."
                )
            word_count = len(WORD_PATTERN.findall(text))
            if word_count < 1:
                raise ValueError(f"Tokenizer probe has no measurable words: {text!r}")
            token_count = len(token_ids)
            rows.append(
                {
                    "text": text,
                    "characters": len(text),
                    "words": word_count,
                    "tokens": token_count,
                    "tokens_per_word": token_count / word_count,
                    "characters_per_token": len(text) / token_count,
                }
            )
            total_chars += len(text)
            total_words += word_count
            total_tokens += token_count

        groups[group_name] = {
            "text_count": len(rows),
            "characters": total_chars,
            "words": total_words,
            "tokens": total_tokens,
            "tokens_per_word": total_tokens / total_words,
            "characters_per_token": total_chars / total_tokens,
            "probes": rows,
        }

    return {
        "vocab_size": vocabulary_size,
        "groups": groups,
        "round_trip_failures": round_trip_failures,
        "invalid_token_ids": invalid_token_ids,
    }
