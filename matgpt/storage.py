"""Storage-capacity evidence that distinguishes remote quota from local mounts."""

from __future__ import annotations

import math
from typing import Any, Mapping


GIB = 1024**3


def _nonnegative_integer(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a non-negative integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a non-negative integer.") from exc
    if parsed < 0 or str(parsed) != str(value).strip():
        raise ValueError(f"{field} must be a non-negative integer.")
    return parsed


def google_drive_storage_evidence(about: Mapping[str, Any]) -> dict[str, Any]:
    """Parse Drive API ``about.get(fields='storageQuota')`` evidence.

    Google reports total account usage in ``storageQuota.usage``. The mounted
    filesystem's ``statvfs`` value is a Colab cache/filesystem measurement and
    is deliberately not accepted here as account-quota evidence.
    """

    if not isinstance(about, Mapping):
        raise ValueError("Google Drive about response must be a mapping.")
    quota = about.get("storageQuota")
    if not isinstance(quota, Mapping):
        raise ValueError("Google Drive about response requires storageQuota.")
    usage = _nonnegative_integer(quota.get("usage"), "storageQuota.usage")
    raw_limit = quota.get("limit")
    if raw_limit is None:
        return {
            "source": "google_drive_api",
            "unlimited": True,
            "limit_bytes": None,
            "usage_bytes": usage,
            "free_bytes": None,
            "free_gib": None,
        }
    limit = _nonnegative_integer(raw_limit, "storageQuota.limit")
    free = max(0, limit - usage)
    return {
        "source": "google_drive_api",
        "unlimited": False,
        "limit_bytes": limit,
        "usage_bytes": usage,
        "free_bytes": free,
        "free_gib": free / GIB,
    }


def operator_storage_evidence(free_gb: float) -> dict[str, Any]:
    """Create fallback evidence from the decimal-GB value shown in Drive UI."""

    if (
        not isinstance(free_gb, (int, float))
        or isinstance(free_gb, bool)
        or not math.isfinite(float(free_gb))
        or float(free_gb) <= 0
    ):
        raise ValueError("Operator-reported free storage must be positive and finite.")
    free_gb = float(free_gb)
    free_bytes = int(free_gb * 1_000_000_000)
    return {
        "source": "operator_override",
        "unlimited": False,
        "limit_bytes": None,
        "usage_bytes": None,
        "reported_free_gb": free_gb,
        "free_bytes": free_bytes,
        "free_gib": free_bytes / GIB,
    }


def require_free_storage_gib(
    evidence: Mapping[str, Any],
    minimum_free_gib: float,
) -> None:
    """Fail unless quota evidence proves the requested remote capacity."""

    if (
        not isinstance(minimum_free_gib, (int, float))
        or isinstance(minimum_free_gib, bool)
        or not math.isfinite(float(minimum_free_gib))
        or float(minimum_free_gib) < 0
    ):
        raise ValueError("Minimum free storage must be non-negative and finite.")
    if evidence.get("unlimited") is True:
        return
    free_gib = evidence.get("free_gib")
    if (
        not isinstance(free_gib, (int, float))
        or isinstance(free_gib, bool)
        or not math.isfinite(float(free_gib))
        or float(free_gib) < 0
    ):
        raise ValueError("Storage evidence does not contain a usable free_gib value.")
    required = float(minimum_free_gib)
    observed = float(free_gib)
    if observed < required:
        raise ValueError(
            f"Insufficient remote storage: observed {observed:.2f} GiB; "
            f"required {required:.2f} GiB."
        )
