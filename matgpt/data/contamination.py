from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

import ahocorasick

from matgpt.utils.hashing import sha256_json


class ContaminationMatcher(Protocol):
    engine: str

    def contains(self, folded_text: str) -> bool:
        raise NotImplementedError


def _canonical_patterns(patterns: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({pattern for pattern in patterns if pattern}))


def pattern_fingerprint(patterns: Iterable[str]) -> str:
    return sha256_json(list(_canonical_patterns(patterns)))


def ordered_pattern_fingerprint(patterns: Iterable[str]) -> str:
    """Fingerprint the exact normalized pattern sequence used by corpus manifests."""
    return sha256_json(list(patterns))


@dataclass(frozen=True)
class NaiveContaminationMatcher:
    patterns: tuple[str, ...]
    engine: str = "naive_reference"

    def __init__(self, patterns: Iterable[str]) -> None:
        object.__setattr__(self, "patterns", _canonical_patterns(patterns))

    def contains(self, folded_text: str) -> bool:
        return any(pattern in folded_text for pattern in self.patterns)


class AhoCorasickContaminationMatcher:
    engine = "pyahocorasick"

    def __init__(self, patterns: Iterable[str]) -> None:
        canonical = _canonical_patterns(patterns)
        self.automaton = ahocorasick.Automaton()
        for pattern in canonical:
            self.automaton.add_word(pattern, None)
        self.automaton.make_automaton()

    def contains(self, folded_text: str) -> bool:
        return next(self.automaton.iter(folded_text), None) is not None


def build_contamination_matcher(patterns: Iterable[str]) -> ContaminationMatcher:
    canonical = _canonical_patterns(patterns)
    if not canonical:
        return NaiveContaminationMatcher(())
    return AhoCorasickContaminationMatcher(canonical)
