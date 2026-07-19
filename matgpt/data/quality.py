from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

from matgpt.data.normalize import normalize_text


def _as_path_list(value: str | list[str] | None) -> list[Path]:
    if value is None:
        return []
    if isinstance(value, str):
        return [Path(value)]
    return [Path(item) for item in value]


def load_contamination_patterns(paths: Iterable[str | Path]) -> list[str]:
    patterns: list[str] = []
    for path in paths:
        with Path(path).open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                raw = line.strip()
                if raw.startswith("{"):
                    row = json.loads(raw)
                    raw = str(row.get("text") or row.get("prompt") or row.get("content") or "")

                # Clean the known benchmark text.
                normalized = normalize_text(raw).casefold()

                # Remember it as text that should not appear in training data.
                if normalized:
                    patterns.append(normalized)
    return patterns


@dataclass(frozen=True)
class DataQualityPolicy:
    enabled: bool = False
    min_chars: int = 1
    max_chars: int | None = None
    exact_dedup: bool = False
    contamination_patterns: list[str] = field(default_factory=list)

    @classmethod
    def from_dataset_config(cls, ds_cfg: dict[str, Any]) -> "DataQualityPolicy":
        quality_cfg = ds_cfg.get("quality") or {}
        paths = _as_path_list(quality_cfg.get("contamination_patterns_path"))
        patterns = [normalize_text(pattern).casefold() for pattern in quality_cfg.get("contamination_patterns", [])]
        patterns.extend(load_contamination_patterns(paths))
        return cls(
            enabled=bool(quality_cfg.get("enabled", False)),
            min_chars=int(quality_cfg.get("min_chars", 1)),
            max_chars=quality_cfg.get("max_chars"),
            exact_dedup=bool(quality_cfg.get("exact_dedup", False)),
            contamination_patterns=[pattern for pattern in patterns if pattern],
        )


class QualityFilter:
    def __init__(self, policy: DataQualityPolicy) -> None:
        self.policy = policy

        # Start with an empty collection of seen document hashes.
        self.seen_hashes: set[str] = set()
        self.total_documents = 0
        self.accepted_documents = 0
        self.rejected_documents = 0
        self.rejection_reasons: Counter[str] = Counter()

    def _rejection_reason(self, record: dict[str, Any]) -> str | None:
        if not self.policy.enabled:
            return None

        # Get the document's cleaned text.
        text = str(record.get("text", ""))
        # Get its recorded character count.
        num_chars = int(record.get("num_chars", len(text)))

        # Is the document shorter than the allowed minimum?
        if num_chars < self.policy.min_chars:
            # Record why this document was rejected.
            return "too_short"
        if self.policy.max_chars is not None and num_chars > self.policy.max_chars:
            return "too_long"

        # Is exact deduplication enabled, and have we seen this hash?
        if self.policy.exact_dedup and record["text_sha256"] in self.seen_hashes:
                # Reject this document as an exact duplicate.
            return "duplicate_exact"

        # Convert document text to a capitalization-independent form.
        folded = text.casefold()

        # Check whether any known benchmark text appears inside it.
        if any(pattern in folded for pattern in self.policy.contamination_patterns):
            return "benchmark_contamination"
        return None

    def accept(self, record: dict[str, Any]) -> bool:
        self.total_documents += 1
        reason = self._rejection_reason(record)
        if reason is not None:
            self.rejected_documents += 1
            self.rejection_reasons[reason] += 1
            return False
        self.accepted_documents += 1
        if self.policy.exact_dedup:
            # Remember this document's fingerprint.
            self.seen_hashes.add(record["text_sha256"])
        return True

    def filter(self, records: Iterable[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        for record in records:
            if self.accept(record):
                yield record

    def report(self) -> dict[str, Any]:
        return {
            "enabled": self.policy.enabled,
            "min_chars": self.policy.min_chars,
            "max_chars": self.policy.max_chars,
            "exact_dedup": self.policy.exact_dedup,
            "contamination_patterns": len(self.policy.contamination_patterns),
            "total_documents": self.total_documents,
            "accepted_documents": self.accepted_documents,
            "rejected_documents": self.rejected_documents,
            "rejection_reasons": dict(self.rejection_reasons),
        }
