import json
from pathlib import Path

from matgpt.data.prepare import make_document_record
from matgpt.data.quality import DataQualityPolicy, QualityFilter, load_contamination_patterns


def test_quality_filter_rejects_short_duplicate_and_contaminated_records(tmp_path: Path):
    contamination_path = tmp_path / "contamination.txt"
    contamination_path.write_text("benchmark answer phrase\n", encoding="utf-8")
    policy = DataQualityPolicy(
        enabled=True,
        min_chars=10,
        exact_dedup=True,
        contamination_patterns=load_contamination_patterns([contamination_path]),
    )
    quality_filter = QualityFilter(policy)
    first = make_document_record("unit", "train", 0, "This is a useful document.")
    duplicate = make_document_record("unit", "train", 1, "This is a useful document.")
    too_short = make_document_record("unit", "train", 2, "short")
    contaminated = make_document_record("unit", "train", 3, "This contains benchmark answer phrase.")

    accepted = list(quality_filter.filter([first, duplicate, too_short, contaminated]))

    assert accepted == [first]
    assert quality_filter.report()["accepted_documents"] == 1
    assert quality_filter.report()["rejected_documents"] == 3
    assert quality_filter.report()["rejection_reasons"] == {
        "duplicate_exact": 1,
        "too_short": 1,
        "benchmark_contamination": 1,
    }


def test_quality_filter_policy_loads_from_dataset_config(tmp_path: Path):
    blocklist = tmp_path / "blocked.jsonl"
    blocklist.write_text(json.dumps({"text": "secret eval phrase"}) + "\n", encoding="utf-8")

    policy = DataQualityPolicy.from_dataset_config(
        {
            "quality": {
                "enabled": True,
                "min_chars": 5,
                "max_chars": 100,
                "exact_dedup": True,
                "contamination_patterns_path": str(blocklist),
            }
        }
    )

    assert policy.enabled is True
    assert policy.min_chars == 5
    assert policy.max_chars == 100
    assert policy.exact_dedup is True
    assert policy.contamination_patterns == ["secret eval phrase"]
