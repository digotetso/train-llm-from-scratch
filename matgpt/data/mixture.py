"""Deterministic token-quota planning for the Telco 300M corpus."""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path
from typing import Any, Mapping

import yaml

from matgpt.data.sources import (
    PRETRAIN_ROLES,
    SourceRegistry,
    select_pretraining_sources,
)
from matgpt.utils.hashing import sha256_json


MIXTURE_KEYS = frozenset(
    {"version", "seed", "quota_tolerance", "buffer_size", "stages"}
)
STAGE_KEYS = frozenset({"total_tokens", "role_weights", "source_weights"})
PATENT_MAX_FRACTION = Decimal("0.08")


def _decimal_weight(value: Any, item_id: str) -> Decimal:
    if not isinstance(value, (int, float, Decimal)) or isinstance(value, bool):
        raise ValueError(f"Weight for {item_id!r} must be numeric.")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"Weight for {item_id!r} must be finite.")
    weight = Decimal(str(value))
    if not weight.is_finite():
        raise ValueError(f"Weight for {item_id!r} must be finite.")
    if weight < 0:
        raise ValueError(f"Weight for {item_id!r} must be non-negative.")
    return weight


def allocate_integer_quotas(
    total: int,
    weights: Mapping[str, float | int | Decimal],
) -> dict[str, int]:
    """Allocate an integer total with deterministic largest-remainder rounding."""

    if not isinstance(total, int) or isinstance(total, bool) or total <= 0:
        raise ValueError("Quota total must be a positive integer.")
    if not isinstance(weights, Mapping):
        raise ValueError("Quota weights must be a mapping.")

    decimal_weights = {
        str(item_id): _decimal_weight(weight, str(item_id))
        for item_id, weight in weights.items()
    }
    total_weight = sum(decimal_weights.values(), Decimal(0))
    if total_weight <= 0:
        raise ValueError("Quota weights must contain at least one positive weight.")

    raw_quotas = {
        item_id: (Decimal(total) * weight / total_weight)
        for item_id, weight in decimal_weights.items()
    }
    quotas = {
        item_id: int(raw.to_integral_value(rounding=ROUND_FLOOR))
        for item_id, raw in raw_quotas.items()
    }
    remaining = total - sum(quotas.values())
    ranked = sorted(
        raw_quotas,
        key=lambda item_id: (
            -(raw_quotas[item_id] - Decimal(quotas[item_id])),
            item_id,
        ),
    )
    for item_id in ranked[:remaining]:
        quotas[item_id] += 1
    return {item_id: quotas[item_id] for item_id in sorted(quotas)}


def load_mixture_config(path: str | Path) -> dict[str, Any]:
    mixture_path = Path(path)
    with mixture_path.open("r", encoding="utf-8") as handle:
        mixture = yaml.safe_load(handle)
    if not isinstance(mixture, dict):
        raise ValueError(f"Mixture config must be a mapping: {mixture_path}")
    unknown = set(mixture) - MIXTURE_KEYS
    if unknown:
        raise ValueError(f"Mixture config contains unknown keys: {sorted(unknown)}")
    if mixture.get("version") != 1:
        raise ValueError("Mixture config version must be 1.")
    if not isinstance(mixture.get("seed"), int) or isinstance(
        mixture.get("seed"), bool
    ):
        raise ValueError("Mixture seed must be an integer.")
    tolerance = mixture.get("quota_tolerance")
    if (
        not isinstance(tolerance, (int, float))
        or isinstance(tolerance, bool)
        or not math.isfinite(float(tolerance))
        or not 0 <= float(tolerance) < 1
    ):
        raise ValueError("Mixture quota_tolerance must be in [0, 1).")
    buffer_size = mixture.get("buffer_size")
    if (
        not isinstance(buffer_size, int)
        or isinstance(buffer_size, bool)
        or buffer_size < 1
    ):
        raise ValueError("Mixture buffer_size must be a positive integer.")
    stages = mixture.get("stages")
    if not isinstance(stages, dict):
        raise ValueError("Mixture config requires a 'stages' mapping.")
    for stage_name, stage in stages.items():
        if not isinstance(stage_name, str) or not stage_name:
            raise ValueError("Mixture stage names must be non-empty strings.")
        if not isinstance(stage, dict):
            raise ValueError(f"Mixture stage {stage_name!r} must be a mapping.")
        unknown_stage_keys = set(stage) - STAGE_KEYS
        if unknown_stage_keys:
            raise ValueError(
                f"Mixture stage {stage_name!r} contains unknown keys: "
                f"{sorted(unknown_stage_keys)}"
            )
    return mixture


def _cap_patent_rounding(
    bucket_quotas: dict[str, int],
    source_total: int,
) -> dict[str, int]:
    """Keep integer rounding from moving patents above the configured 8% cap."""

    if "patents" not in bucket_quotas:
        return bucket_quotas
    maximum = int(
        (Decimal(source_total) * PATENT_MAX_FRACTION).to_integral_value(
            rounding=ROUND_FLOOR
        )
    )
    excess = max(0, bucket_quotas["patents"] - maximum)
    if excess:
        bucket_quotas = dict(bucket_quotas)
        bucket_quotas["patents"] = maximum
        recipients = sorted(
            (item_id for item_id in bucket_quotas if item_id != "patents"),
            key=lambda item_id: (-bucket_quotas[item_id], item_id),
        )
        if not recipients:
            raise ValueError("Patent quota cannot be capped without another bucket.")
        bucket_quotas[recipients[0]] += excess
    return bucket_quotas


def build_mixture_plan(
    registry: SourceRegistry,
    mixture: Mapping[str, Any],
    stage: str,
    *,
    total_tokens: int | None = None,
) -> dict[str, Any]:
    """Expand one configured stage into exact source and bucket token quotas."""

    stages = mixture.get("stages")
    if not isinstance(stages, Mapping) or stage not in stages:
        raise ValueError(f"Unknown mixture stage: {stage!r}")
    stage_cfg = stages[stage]
    if not isinstance(stage_cfg, Mapping):
        raise ValueError(f"Mixture stage {stage!r} must be a mapping.")
    unknown_stage_keys = set(stage_cfg) - STAGE_KEYS
    if unknown_stage_keys:
        raise ValueError(
            f"Mixture stage {stage!r} contains unknown keys: "
            f"{sorted(unknown_stage_keys)}"
        )

    source_weights = stage_cfg.get("source_weights")
    if not isinstance(source_weights, Mapping) or not source_weights:
        raise ValueError(f"Mixture stage {stage!r} requires source_weights.")
    selected_sources = select_pretraining_sources(registry, source_weights)

    role_weights = stage_cfg.get("role_weights")
    if not isinstance(role_weights, Mapping) or not role_weights:
        raise ValueError(f"Mixture stage {stage!r} requires role_weights.")
    invalid_roles = set(role_weights) - PRETRAIN_ROLES
    if invalid_roles:
        raise ValueError(
            f"Mixture stage {stage!r} contains roles not permitted for pretraining: "
            f"{sorted(invalid_roles)}"
        )

    planned_total = stage_cfg.get("total_tokens") if total_tokens is None else total_tokens
    role_quotas = allocate_integer_quotas(planned_total, role_weights)
    items: list[dict[str, Any]] = []

    for role in sorted(role_quotas):
        role_sources = [source for source in selected_sources if source.role == role]
        if not role_sources:
            raise ValueError(
                f"Mixture stage {stage!r} has a non-zero quota for {role!r} "
                "but no source with that role."
            )
        weights_for_role = {
            source.id: source_weights[source.id] for source in role_sources
        }
        source_quotas = allocate_integer_quotas(role_quotas[role], weights_for_role)
        for source in role_sources:
            source_quota = source_quotas[source.id]
            if source.buckets:
                patent_bucket = source.bucket_by_id.get("patents")
                if (
                    patent_bucket is not None
                    and Decimal(str(patent_bucket.weight)) > PATENT_MAX_FRACTION
                ):
                    raise ValueError(
                        "Patent quota exceeds the 8% telecom ceiling: "
                        f"{patent_bucket.weight:.2%}."
                    )
                bucket_quotas = allocate_integer_quotas(
                    source_quota,
                    {bucket.id: bucket.weight for bucket in source.buckets},
                )
                bucket_quotas = _cap_patent_rounding(bucket_quotas, source_quota)
                for bucket in source.buckets:
                    items.append(
                        {
                            "id": f"{source.id}/{bucket.id}",
                            "source_id": source.id,
                            "bucket_id": bucket.id,
                            "role": source.role,
                            "token_quota": bucket_quotas[bucket.id],
                        }
                    )
            else:
                items.append(
                    {
                        "id": source.id,
                        "source_id": source.id,
                        "bucket_id": None,
                        "role": source.role,
                        "token_quota": source_quota,
                    }
                )

    items.sort(key=lambda item: item["id"])
    if sum(item["token_quota"] for item in items) != planned_total:
        raise AssertionError("Mixture item quotas do not preserve the stage total.")
    plan = {
        "version": 1,
        "stage": stage,
        "seed": int(mixture["seed"]),
        "total_tokens": planned_total,
        "quota_tolerance": float(mixture["quota_tolerance"]),
        "buffer_size": int(mixture["buffer_size"]),
        "role_quotas": role_quotas,
        "items": items,
    }
    plan["plan_sha256"] = sha256_json(plan)
    return plan
