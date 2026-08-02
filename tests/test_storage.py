import pytest

from matgpt.storage import (
    google_drive_storage_evidence,
    operator_storage_evidence,
    require_free_storage_gib,
)


GIB = 1024**3


def test_google_drive_quota_uses_api_limit_and_total_usage():
    evidence = google_drive_storage_evidence(
        {
            "storageQuota": {
                "limit": str(2_000 * GIB),
                "usage": str(419 * GIB),
                "usageInDrive": str(400 * GIB),
                "usageInDriveTrash": str(2 * GIB),
            }
        }
    )

    assert evidence == {
        "source": "google_drive_api",
        "unlimited": False,
        "limit_bytes": 2_000 * GIB,
        "usage_bytes": 419 * GIB,
        "free_bytes": 1_581 * GIB,
        "free_gib": 1_581.0,
    }
    require_free_storage_gib(evidence, 100.0)


def test_google_drive_quota_without_limit_is_treated_as_unlimited():
    evidence = google_drive_storage_evidence(
        {"storageQuota": {"usage": str(25 * GIB)}}
    )

    assert evidence["unlimited"] is True
    assert evidence["free_gib"] is None
    require_free_storage_gib(evidence, 100.0)


def test_operator_override_is_explicit_and_enforces_minimum():
    evidence = operator_storage_evidence(80.0)

    assert evidence["source"] == "operator_override"
    assert evidence["reported_free_gb"] == 80.0
    assert evidence["free_bytes"] == 80_000_000_000
    with pytest.raises(ValueError, match="74.51 GiB.*100.00 GiB"):
        require_free_storage_gib(evidence, 100.0)


@pytest.mark.parametrize("free_gib", [float("nan"), float("inf"), -1.0])
def test_remote_storage_gate_rejects_invalid_evidence(free_gib):
    with pytest.raises(ValueError, match="usable free_gib"):
        require_free_storage_gib(
            {"unlimited": False, "free_gib": free_gib},
            100.0,
        )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"storageQuota": []},
        {"storageQuota": {"usage": "not-an-integer"}},
        {"storageQuota": {"limit": "10", "usage": "-1"}},
    ],
)
def test_google_drive_quota_rejects_malformed_api_payload(payload):
    with pytest.raises(ValueError):
        google_drive_storage_evidence(payload)
