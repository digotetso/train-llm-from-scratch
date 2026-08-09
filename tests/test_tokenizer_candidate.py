from dataclasses import replace
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


def test_candidate_recipe_requires_pilot_mixture_stage(tmp_path: Path):
    raw = yaml.safe_load(
        Path("configs/data/telco_300m_tokenizer_candidate.yaml").read_text(
            encoding="utf-8"
        )
    )
    raw["mixture_stage"] = "main"
    path = tmp_path / "candidate.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="mixture_stage must be pilot"):
        load_tokenizer_candidate_config(path)


def test_candidate_sample_plan_requires_pilot_stage_from_direct_config():
    config = load_tokenizer_candidate_config(
        "configs/data/telco_300m_tokenizer_candidate.yaml"
    )

    with pytest.raises(ValueError, match="mixture_stage must be pilot"):
        build_tokenizer_sample_plan(
            load_source_registry("configs/data/telco_300m_sources.yaml"),
            load_mixture_config("configs/data/telco_300m_mixture.yaml"),
            replace(config, mixture_stage="main"),
        )


def test_candidate_recipe_rejects_mixture_with_unexpected_seed():
    config = load_tokenizer_candidate_config(
        "configs/data/telco_300m_tokenizer_candidate.yaml"
    )
    mixture = load_mixture_config("configs/data/telco_300m_mixture.yaml")
    mixture["seed"] = 7

    with pytest.raises(ValueError, match="seed must be 42"):
        build_tokenizer_sample_plan(
            load_source_registry("configs/data/telco_300m_sources.yaml"),
            mixture,
            config,
        )


def test_candidate_recipe_rejects_mixture_with_changed_role_weights():
    config = load_tokenizer_candidate_config(
        "configs/data/telco_300m_tokenizer_candidate.yaml"
    )
    mixture = load_mixture_config("configs/data/telco_300m_mixture.yaml")
    mixture["stages"]["pilot"]["role_weights"]["pretrain_general"] = 1

    with pytest.raises(ValueError, match="role quotas"):
        build_tokenizer_sample_plan(
            load_source_registry("configs/data/telco_300m_sources.yaml"),
            mixture,
            config,
        )


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
