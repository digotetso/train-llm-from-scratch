from pathlib import Path

import pytest
import yaml

from matgpt.data.mixture import load_mixture_config
from matgpt.data.sources import load_source_registry
from matgpt.tokenizer.candidate import (
    build_tokenizer_sample_plan,
    load_tokenizer_candidate_config,
)


def test_candidate_recipe_builds_exact_200m_combined_role_plan():
    config = load_tokenizer_candidate_config(
        "configs/data/telco_300m_tokenizer_candidate.yaml"
    )
    plan = build_tokenizer_sample_plan(
        load_source_registry("configs/data/telco_300m_sources.yaml"),
        load_mixture_config("configs/data/telco_300m_mixture.yaml"),
        config,
    )

    assert plan["stage"] == "pilot"
    assert plan["total_tokens"] == 200_000_000
    assert plan["role_quotas"] == {
        "pretrain_general": 128_333_333,
        "pretrain_structured": 10_000_000,
        "pretrain_telecom": 61_666_667,
    }
    assert sum(item["token_quota"] for item in plan["items"]) == 200_000_000


def test_candidate_recipe_rejects_unknown_keys(tmp_path: Path):
    path = tmp_path / "candidate.yaml"
    path.write_text(
        "version: 1\nsample_tokens: 200000000\nmixture_stage: pilot\n"
        "baseline_label: pilot_20m\ncandidate_label: representative_200m\n"
        "comparison:\n  max_general_regression: 0.01\n"
        "  max_telecom_regression: 0.0\n"
        "  max_probe_p95_regression: 0.01\n"
        "  min_overall_improvement: 0.01\n"
        "  min_telecom_improvement: 0.02\n"
        "local:\n  max_working_gib: 20\n  min_free_gib: 25\n"
        "unexpected: true\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown keys"):
        load_tokenizer_candidate_config(path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("sample_tokens", 0, "positive"),
        ("sample_tokens", 200_000_001, "exactly 200000000"),
        ("max_working_gib", 0, "positive"),
        ("min_free_gib", 0, "positive"),
        ("baseline_label", "  ", "non-empty"),
        ("candidate_label", "candidate label", "safe label characters"),
        ("max_general_regression", 1.0, r"\[0, 1\)"),
    ],
)
def test_candidate_recipe_rejects_invalid_values(
    tmp_path: Path, field: str, value: object, message: str
):
    config = {
        "version": 1,
        "sample_tokens": 200_000_000,
        "mixture_stage": "pilot",
        "baseline_label": "pilot_20m",
        "candidate_label": "representative_200m",
        "comparison": {
            "max_general_regression": 0.01,
            "max_telecom_regression": 0.0,
            "max_probe_p95_regression": 0.01,
            "min_overall_improvement": 0.01,
            "min_telecom_improvement": 0.02,
        },
        "local": {"max_working_gib": 20, "min_free_gib": 25},
    }
    if field in config:
        config[field] = value
    elif field in config["comparison"]:
        config["comparison"][field] = value
    else:
        config["local"][field] = value
    path = tmp_path / "candidate.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_tokenizer_candidate_config(path)
