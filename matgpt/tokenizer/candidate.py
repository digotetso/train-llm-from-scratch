"""Validated recipe for the 200M-token Telco tokenizer candidate."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from matgpt.data.mixture import build_mixture_plan


TARGET_SAMPLE_TOKENS = 200_000_000
REQUIRED_MIXTURE_STAGE = "pilot"
REQUIRED_MIXTURE_SEED = 42
REQUIRED_ROLE_QUOTAS = {
    "pretrain_general": 128_333_333,
    "pretrain_structured": 10_000_000,
    "pretrain_telecom": 61_666_667,
}
_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_TOP_LEVEL_KEYS = frozenset(
    {
        "version",
        "sample_tokens",
        "mixture_stage",
        "baseline_label",
        "candidate_label",
        "comparison",
        "local",
    }
)
_COMPARISON_KEYS = frozenset(
    {
        "max_general_regression",
        "max_telecom_regression",
        "max_probe_p95_regression",
        "min_overall_improvement",
        "min_telecom_improvement",
    }
)
_LOCAL_KEYS = frozenset({"max_working_gib", "min_free_gib"})


@dataclass(frozen=True)
class TokenizerCandidateConfig:
    sample_tokens: int
    mixture_stage: str
    baseline_label: str
    candidate_label: str
    max_general_regression: float
    max_telecom_regression: float
    max_probe_p95_regression: float
    min_overall_improvement: float
    min_telecom_improvement: float
    max_working_gib: int
    min_free_gib: int


def _positive_integer(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"Tokenizer candidate config {field} must be positive.")
    return value


def _safe_label(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Tokenizer candidate config {field} must be non-empty.")
    if not _LABEL_PATTERN.fullmatch(value):
        raise ValueError(
            f"Tokenizer candidate config {field} must contain only safe label characters."
        )
    return value


def _fraction(value: Any, field: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or not 0 <= float(value) < 1
    ):
        raise ValueError(f"Tokenizer candidate config {field} must be in [0, 1).")
    return float(value)


def _require_mapping(raw: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    value = raw.get(field)
    if not isinstance(value, Mapping):
        raise ValueError(f"Tokenizer candidate config requires {field} mapping.")
    return value


def _reject_unknown_keys(raw: Mapping[str, Any], allowed: frozenset[str], scope: str) -> None:
    unknown = set(raw) - allowed
    if unknown:
        location = f" {scope}" if scope else ""
        raise ValueError(
            f"Tokenizer candidate config{location} contains unknown keys: {sorted(unknown)}"
        )


def load_tokenizer_candidate_config(path: str | Path) -> TokenizerCandidateConfig:
    """Load the strict, fixed-size tokenizer candidate recipe."""

    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("Tokenizer candidate config must be a mapping.")
    _reject_unknown_keys(raw, _TOP_LEVEL_KEYS, "")
    if raw.get("version") != 1:
        raise ValueError("Tokenizer candidate config version must be 1.")

    comparison = _require_mapping(raw, "comparison")
    local = _require_mapping(raw, "local")
    _reject_unknown_keys(comparison, _COMPARISON_KEYS, "comparison")
    _reject_unknown_keys(local, _LOCAL_KEYS, "local")

    sample_tokens = _positive_integer(raw.get("sample_tokens"), "sample_tokens")
    if sample_tokens != TARGET_SAMPLE_TOKENS:
        raise ValueError(
            "Tokenizer candidate config sample_tokens must be exactly 200000000."
        )

    mixture_stage = _safe_label(raw.get("mixture_stage"), "mixture_stage")
    if mixture_stage != REQUIRED_MIXTURE_STAGE:
        raise ValueError("Tokenizer candidate config mixture_stage must be pilot.")

    return TokenizerCandidateConfig(
        sample_tokens=sample_tokens,
        mixture_stage=mixture_stage,
        baseline_label=_safe_label(raw.get("baseline_label"), "baseline_label"),
        candidate_label=_safe_label(raw.get("candidate_label"), "candidate_label"),
        max_general_regression=_fraction(
            comparison.get("max_general_regression"), "max_general_regression"
        ),
        max_telecom_regression=_fraction(
            comparison.get("max_telecom_regression"), "max_telecom_regression"
        ),
        max_probe_p95_regression=_fraction(
            comparison.get("max_probe_p95_regression"), "max_probe_p95_regression"
        ),
        min_overall_improvement=_fraction(
            comparison.get("min_overall_improvement"), "min_overall_improvement"
        ),
        min_telecom_improvement=_fraction(
            comparison.get("min_telecom_improvement"), "min_telecom_improvement"
        ),
        max_working_gib=_positive_integer(
            local.get("max_working_gib"), "max_working_gib"
        ),
        min_free_gib=_positive_integer(local.get("min_free_gib"), "min_free_gib"),
    )


def build_tokenizer_sample_plan(
    registry: Any,
    mixture: Mapping[str, Any],
    config: TokenizerCandidateConfig,
) -> dict[str, Any]:
    """Build the exact pilot-stage mixture plan for the candidate sample."""

    if config.mixture_stage != REQUIRED_MIXTURE_STAGE:
        raise ValueError("Tokenizer candidate config mixture_stage must be pilot.")
    plan = build_mixture_plan(
        registry,
        mixture,
        config.mixture_stage,
        total_tokens=config.sample_tokens,
    )
    if plan["seed"] != REQUIRED_MIXTURE_SEED:
        raise ValueError("Tokenizer candidate mixture seed must be 42.")
    if plan["role_quotas"] != REQUIRED_ROLE_QUOTAS:
        raise ValueError("Tokenizer candidate mixture role quotas do not match the recipe.")
    return plan
