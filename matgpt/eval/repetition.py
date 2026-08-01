from __future__ import annotations

import re
from collections import Counter
from statistics import mean
from typing import Iterable


WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?", re.IGNORECASE)
SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")
RATE_FIELDS = (
    "repeated_3gram_rate",
    "repeated_4gram_rate",
    "duplicate_sentence_rate",
    "distinct_2gram_ratio",
    "distinct_3gram_ratio",
)


def _extra_occurrences(values: list[tuple[str, ...]] | list[str]) -> int:
    return sum(count - 1 for count in Counter(values).values() if count > 1)


def _ngrams(words: list[str], size: int) -> list[tuple[str, ...]]:
    return [
        tuple(words[index : index + size])
        for index in range(len(words) - size + 1)
    ]


def measure_repetition(text: str) -> dict[str, int | float]:
    words = [match.group(0).lower() for match in WORD_RE.finditer(text)]
    sentences = [
        " ".join(WORD_RE.findall(match.group(0).lower()))
        for match in SENTENCE_RE.finditer(text)
        if WORD_RE.search(match.group(0))
    ]
    bigrams, trigrams, fourgrams = (_ngrams(words, size) for size in (2, 3, 4))
    repeated_3 = _extra_occurrences(trigrams)
    repeated_4 = _extra_occurrences(fourgrams)
    duplicate_sentences = _extra_occurrences(sentences)

    return {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "consecutive_duplicate_words": sum(
            left == right for left, right in zip(words, words[1:])
        ),
        "total_3grams": len(trigrams),
        "repeated_3gram_occurrences": repeated_3,
        "repeated_3gram_rate": repeated_3 / len(trigrams) if trigrams else 0.0,
        "total_4grams": len(fourgrams),
        "repeated_4gram_occurrences": repeated_4,
        "repeated_4gram_rate": repeated_4 / len(fourgrams) if fourgrams else 0.0,
        "duplicate_sentence_occurrences": duplicate_sentences,
        "duplicate_sentence_rate": (
            duplicate_sentences / len(sentences) if sentences else 0.0
        ),
        "distinct_2gram_ratio": len(set(bigrams)) / len(bigrams) if bigrams else 0.0,
        "distinct_3gram_ratio": (
            len(set(trigrams)) / len(trigrams) if trigrams else 0.0
        ),
    }


def aggregate_repetition(
    rows: Iterable[dict[str, int | float]],
) -> dict[str, float]:
    items = list(rows)
    return {
        "story_count": len(items),
        **{
            f"mean_{field}": (
                mean(float(item[field]) for item in items) if items else 0.0
            )
            for field in RATE_FIELDS
        },
        "mean_word_count": (
            mean(float(item["word_count"]) for item in items) if items else 0.0
        ),
    }
