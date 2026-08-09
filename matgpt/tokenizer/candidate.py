"""Validated recipe for the 200M-token Telco tokenizer candidate."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from matgpt.data.mixture import build_mixture_plan
from matgpt.tokenizer.train import (
    REQUIRED_VOCAB_SIZE,
    has_required_special_token_ids,
)
from matgpt.utils.hashing import sha256_json


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

    def __post_init__(self) -> None:
        if self.baseline_label == self.candidate_label:
            raise ValueError("Tokenizer baseline and candidate labels must differ.")


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


def _metric(mapping: Mapping[str, Any], field: str, *, positive: bool = False) -> float:
    value = mapping.get(field)
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or (positive and float(value) <= 0)
        or (not positive and float(value) < 0)
    ):
        qualifier = "positive" if positive else "non-negative"
        raise ValueError(f"Tokenizer evaluation {field} must be finite and {qualifier}.")
    return float(value)


def _improvement(baseline: int | float, candidate: int | float) -> float:
    baseline_value = float(baseline)
    candidate_value = float(candidate)
    if not math.isfinite(baseline_value) or baseline_value <= 0:
        raise ValueError("Baseline comparison metric must be finite and positive.")
    if not math.isfinite(candidate_value) or candidate_value < 0:
        raise ValueError("Candidate comparison metric must be finite and non-negative.")
    return (baseline_value - candidate_value) / baseline_value


def _roles(evaluation: Mapping[str, Any]) -> Mapping[str, Any]:
    roles = evaluation.get("roles")
    if not isinstance(roles, Mapping):
        raise ValueError("Tokenizer evaluation roles must be a mapping.")
    return roles


def _role_tokens(evaluation: Mapping[str, Any], role: str) -> float:
    role_metrics = _roles(evaluation).get(role)
    if not isinstance(role_metrics, Mapping):
        raise ValueError(f"Tokenizer evaluation is missing role {role!r}.")
    return _metric(role_metrics, "tokens", positive=True)


def _failure_count(evaluation: Mapping[str, Any], field: str) -> int:
    value = evaluation.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"Tokenizer evaluation {field} must be non-negative integer.")
    return value


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _valid_tokenizer_identity(evaluation: Mapping[str, Any]) -> bool:
    special_token_ids = evaluation.get("special_token_ids")
    identity_failures = evaluation.get("tokenizer_identity_failures")
    return (
        type(identity_failures) is int
        and identity_failures == 0
        and evaluation.get("algorithm") == "byte_level_bpe"
        and evaluation.get("vocab_size_requested") == REQUIRED_VOCAB_SIZE
        and evaluation.get("vocab_size_actual") == REQUIRED_VOCAB_SIZE
        and has_required_special_token_ids(special_token_ids)
        and _valid_sha256(evaluation.get("tokenizer_sha256"))
    )


def compare_tokenizers(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    config: TokenizerCandidateConfig,
) -> dict[str, Any]:
    """Compare two evaluations on the same holdout and apply hard guardrails."""

    if config.baseline_label == config.candidate_label:
        raise ValueError("Tokenizer baseline and candidate labels must differ.")
    baseline_general = _role_tokens(baseline, "pretrain_general")
    candidate_general = _role_tokens(candidate, "pretrain_general")
    baseline_telecom = _role_tokens(baseline, "pretrain_telecom")
    candidate_telecom = _role_tokens(candidate, "pretrain_telecom")
    general_regression = -_improvement(baseline_general, candidate_general)
    telecom_improvement = _improvement(baseline_telecom, candidate_telecom)
    overall_improvement = _improvement(
        _metric(baseline, "tokens", positive=True),
        _metric(candidate, "tokens"),
    )
    baseline_probe_p95 = _metric(
        baseline, "probe_p95_tokens_per_word", positive=True
    )
    candidate_probe_p95 = _metric(
        candidate, "probe_p95_tokens_per_word", positive=True
    )
    probe_regression = (candidate_probe_p95 / baseline_probe_p95) - 1.0

    failures: list[str] = []
    if _failure_count(baseline, "round_trip_failures") or _failure_count(
        candidate, "round_trip_failures"
    ):
        failures.append("round_trip_failure")
    if _failure_count(baseline, "special_token_failures") or _failure_count(
        candidate, "special_token_failures"
    ):
        failures.append("special_token_failure")
    if telecom_improvement < -config.max_telecom_regression:
        failures.append("telecom_regression")
    if general_regression > config.max_general_regression:
        failures.append("general_regression")
    if probe_regression > config.max_probe_p95_regression:
        failures.append("probe_p95_regression")
    baseline_holdout = baseline.get("input_files_sha256")
    candidate_holdout = candidate.get("input_files_sha256")
    if not _valid_sha256(baseline_holdout) or not _valid_sha256(candidate_holdout):
        failures.append("holdout_fingerprint_invalid")
    elif baseline_holdout != candidate_holdout:
        failures.append("holdout_mismatch")
    baseline_probes = baseline.get("probe_sets_sha256")
    candidate_probes = candidate.get("probe_sets_sha256")
    if not _valid_sha256(baseline_probes) or not _valid_sha256(candidate_probes):
        failures.append("probe_fingerprint_invalid")
    elif baseline_probes != candidate_probes:
        failures.append("probe_set_mismatch")
    if not _valid_tokenizer_identity(baseline) or not _valid_tokenizer_identity(
        candidate
    ):
        failures.append("tokenizer_identity_failure")

    eligible = not failures
    recommend_candidate = eligible and (
        overall_improvement >= config.min_overall_improvement
        or telecom_improvement >= config.min_telecom_improvement
    )
    labels = {
        "baseline": config.baseline_label,
        "candidate": config.candidate_label,
    }
    all_roles = sorted(set(_roles(baseline)) | set(_roles(candidate)))
    per_role: dict[str, dict[str, Any]] = {}
    for role in all_roles:
        baseline_role = _roles(baseline)[role]
        candidate_role = _roles(candidate)[role]
        baseline_tokens = _role_tokens(baseline, role)
        candidate_tokens = _role_tokens(candidate, role)
        per_role[role] = {
            "baseline": dict(baseline_role),
            "candidate": dict(candidate_role),
            "baseline_tokens": baseline_tokens,
            "candidate_tokens": candidate_tokens,
            "improvement_fraction": _improvement(
                baseline_tokens, candidate_tokens
            ),
        }

    reasons = list(failures)
    if not reasons:
        reasons.append(
            "candidate_meets_improvement_threshold"
            if recommend_candidate
            else "candidate_improvement_below_threshold"
        )
    report: dict[str, Any] = {
        "eligible": eligible,
        "recommended_winner": (
            config.candidate_label if recommend_candidate else config.baseline_label
        ),
        "guardrail_failures": failures,
        "reasons": reasons,
        "labels": labels,
        "baseline_label": config.baseline_label,
        "candidate_label": config.candidate_label,
        "overall_improvement_fraction": overall_improvement,
        "telecom_improvement_fraction": telecom_improvement,
        "general_regression_fraction": general_regression,
        "probe_p95_regression_fraction": probe_regression,
        "per_role": per_role,
        "fragmentation": {
            "baseline": {
                "p50_tokens_per_word": baseline.get("p50_tokens_per_word"),
                "p95_tokens_per_word": baseline.get("p95_tokens_per_word"),
            },
            "candidate": {
                "p50_tokens_per_word": candidate.get("p50_tokens_per_word"),
                "p95_tokens_per_word": candidate.get("p95_tokens_per_word"),
            },
        },
        "probe_metrics": {
            "baseline": baseline.get("probe_metrics"),
            "candidate": candidate.get("probe_metrics"),
            "baseline_p95_tokens_per_word": baseline_probe_p95,
            "candidate_p95_tokens_per_word": candidate_probe_p95,
        },
        "fingerprints": {
            "baseline_tokenizer_sha256": baseline.get("tokenizer_sha256"),
            "candidate_tokenizer_sha256": candidate.get("tokenizer_sha256"),
            "baseline_input_files_sha256": baseline.get("input_files_sha256"),
            "candidate_input_files_sha256": candidate.get("input_files_sha256"),
            "baseline_probe_sets_sha256": baseline.get("probe_sets_sha256"),
            "candidate_probe_sets_sha256": candidate.get("probe_sets_sha256"),
            "baseline_sample_manifest_sha256": baseline.get(
                "sample_manifest_sha256"
            ),
            "candidate_sample_manifest_sha256": candidate.get(
                "sample_manifest_sha256"
            ),
        },
        "baseline": baseline,
        "candidate": candidate,
    }
    report["comparison_sha256"] = sha256_json(report)
    return report


def write_tokenizer_selection(
    comparison: Mapping[str, Any],
    winner: str,
    output_path: str | Path,
    *,
    operator_timestamp: str | None = None,
) -> dict[str, Any]:
    """Persist an explicit approval without modifying either tokenizer."""

    labels = comparison.get("labels")
    if not isinstance(labels, Mapping):
        raise ValueError("Tokenizer comparison labels must be a mapping.")
    baseline_label = labels.get("baseline")
    candidate_label = labels.get("candidate")
    if winner not in {baseline_label, candidate_label}:
        raise ValueError("Tokenizer selection winner must equal a compared label.")
    if winner == candidate_label and comparison.get("eligible") is not True:
        raise ValueError("Cannot approve an ineligible candidate tokenizer.")

    comparison_sha256 = comparison.get("comparison_sha256")
    if not isinstance(comparison_sha256, str):
        raise ValueError("Tokenizer comparison is missing comparison_sha256.")
    unsigned_comparison = dict(comparison)
    unsigned_comparison.pop("comparison_sha256", None)
    if sha256_json(unsigned_comparison) != comparison_sha256:
        raise ValueError("Tokenizer comparison checksum mismatch.")

    for side, label in (
        ("baseline", baseline_label),
        ("candidate", candidate_label),
    ):
        if comparison.get(f"{side}_label") != label:
            raise ValueError(f"Tokenizer comparison {side} label mismatch.")
        compared_evaluation = comparison.get(side)
        if not isinstance(compared_evaluation, Mapping):
            raise ValueError(f"Tokenizer comparison is missing {side} evaluation.")
        compared_sha256 = compared_evaluation.get("tokenizer_sha256")
        if (
            not isinstance(compared_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", compared_sha256) is None
        ):
            raise ValueError(f"Tokenizer comparison {side} SHA-256 is invalid.")
        fingerprints = comparison.get("fingerprints")
        if (
            not isinstance(fingerprints, Mapping)
            or fingerprints.get(f"{side}_tokenizer_sha256") != compared_sha256
        ):
            raise ValueError(f"Tokenizer comparison {side} fingerprint mismatch.")

    side = "candidate" if winner == candidate_label else "baseline"
    evaluation = comparison.get(side)
    if not isinstance(evaluation, Mapping):
        raise ValueError(f"Tokenizer comparison is missing {side} evaluation.")
    selected_tokenizer_sha256 = evaluation.get("tokenizer_sha256")
    if (
        not isinstance(selected_tokenizer_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", selected_tokenizer_sha256) is None
    ):
        raise ValueError("Selected tokenizer SHA-256 is invalid.")

    timestamp = operator_timestamp or datetime.now(timezone.utc).isoformat()
    if not isinstance(timestamp, str) or not timestamp.strip():
        raise ValueError("Tokenizer selection operator timestamp must be non-empty.")
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Tokenizer selection operator timestamp is invalid.") from error
    if parsed_timestamp.tzinfo is None:
        raise ValueError("Tokenizer selection operator timestamp must include a timezone.")

    selection = {
        "version": 1,
        "approved": True,
        "winner": winner,
        "comparison_sha256": comparison_sha256,
        "selected_tokenizer_sha256": selected_tokenizer_sha256,
        "operator_timestamp": timestamp,
    }
    destination = Path(output_path)
    if destination.name != "tokenizer_selection.json":
        raise ValueError("Tokenizer selection output must be tokenizer_selection.json.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as handle:
        json.dump(selection, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return selection
