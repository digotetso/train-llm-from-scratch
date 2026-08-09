import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from matgpt.data.mixture import load_mixture_config
from matgpt.data.sources import load_source_registry
from matgpt.tokenizer.candidate import (
    TokenizerCandidateConfig,
    build_tokenizer_sample_plan,
    compare_tokenizers,
    load_tokenizer_candidate_config,
    write_tokenizer_selection,
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


def candidate_config() -> TokenizerCandidateConfig:
    return TokenizerCandidateConfig(
        sample_tokens=200_000_000,
        mixture_stage="pilot",
        baseline_label="pilot_20m",
        candidate_label="representative_200m",
        max_general_regression=0.01,
        max_telecom_regression=0.0,
        max_probe_p95_regression=0.01,
        min_overall_improvement=0.01,
        min_telecom_improvement=0.02,
        max_working_gib=20,
        min_free_gib=25,
    )


def evaluation(
    *,
    overall_tokens: int,
    general_tokens: int,
    telecom_tokens: int,
    probe_p95: float,
    tokenizer_sha256: str = "a" * 64,
    input_files_sha256: str = "c" * 64,
    probe_sets_sha256: str = "d" * 64,
) -> dict[str, object]:
    return {
        "tokens": overall_tokens,
        "roles": {
            "pretrain_general": {"tokens": general_tokens},
            "pretrain_telecom": {"tokens": telecom_tokens},
            "pretrain_structured": {
                "tokens": overall_tokens - general_tokens - telecom_tokens
            },
        },
        "p50_tokens_per_word": 2.0,
        "p95_tokens_per_word": 3.0,
        "probe_metrics": {"groups": {}},
        "probe_p95_tokens_per_word": probe_p95,
        "round_trip_failures": 0,
        "special_token_failures": 0,
        "tokenizer_sha256": tokenizer_sha256,
        "input_files_sha256": input_files_sha256,
        "probe_sets_sha256": probe_sets_sha256,
    }


def test_comparison_recommends_candidate_only_when_thresholds_and_guards_pass():
    config = candidate_config()
    baseline = evaluation(
        overall_tokens=10_000,
        general_tokens=6_000,
        telecom_tokens=3_000,
        probe_p95=4.0,
    )
    candidate = evaluation(
        overall_tokens=9_850,
        general_tokens=6_030,
        telecom_tokens=2_900,
        probe_p95=4.02,
        tokenizer_sha256="b" * 64,
    )

    report = compare_tokenizers(baseline, candidate, config)

    assert report["eligible"] is True
    assert report["recommended_winner"] == "representative_200m"
    assert report["overall_improvement_fraction"] == pytest.approx(0.015)
    assert report["labels"] == {
        "baseline": "pilot_20m",
        "candidate": "representative_200m",
    }
    assert report["fingerprints"]["baseline_tokenizer_sha256"] == "a" * 64
    assert report["fingerprints"]["candidate_tokenizer_sha256"] == "b" * 64


def test_comparison_blocks_candidate_when_telecom_regresses():
    config = candidate_config()
    baseline = evaluation(
        overall_tokens=10_000,
        general_tokens=6_000,
        telecom_tokens=3_000,
        probe_p95=4.0,
    )
    candidate = evaluation(
        overall_tokens=9_800,
        general_tokens=5_700,
        telecom_tokens=3_100,
        probe_p95=4.0,
    )

    report = compare_tokenizers(baseline, candidate, config)

    assert report["eligible"] is False
    assert "telecom_regression" in report["guardrail_failures"]
    assert report["recommended_winner"] == "pilot_20m"


def test_comparison_blocks_any_round_trip_failure():
    config = candidate_config()
    baseline = evaluation(
        overall_tokens=10_000,
        general_tokens=6_000,
        telecom_tokens=3_000,
        probe_p95=4.0,
    )
    candidate = evaluation(
        overall_tokens=9_700,
        general_tokens=5_900,
        telecom_tokens=2_850,
        probe_p95=3.9,
    )
    candidate["round_trip_failures"] = 1

    report = compare_tokenizers(baseline, candidate, config)

    assert report["eligible"] is False
    assert "round_trip_failure" in report["guardrail_failures"]


def test_comparison_blocks_different_holdout_or_probe_fingerprints():
    config = candidate_config()
    baseline = evaluation(
        overall_tokens=10_000,
        general_tokens=6_000,
        telecom_tokens=3_000,
        probe_p95=4.0,
    )
    candidate = evaluation(
        overall_tokens=9_700,
        general_tokens=5_900,
        telecom_tokens=2_850,
        probe_p95=3.9,
        input_files_sha256="e" * 64,
        probe_sets_sha256="f" * 64,
    )

    report = compare_tokenizers(baseline, candidate, config)

    assert report["eligible"] is False
    assert "holdout_mismatch" in report["guardrail_failures"]
    assert "probe_set_mismatch" in report["guardrail_failures"]


def test_selection_records_explicit_approved_candidate(tmp_path: Path):
    comparison = compare_tokenizers(
        evaluation(
            overall_tokens=10_000,
            general_tokens=6_000,
            telecom_tokens=3_000,
            probe_p95=4.0,
        ),
        evaluation(
            overall_tokens=9_850,
            general_tokens=6_030,
            telecom_tokens=2_900,
            probe_p95=4.02,
            tokenizer_sha256="b" * 64,
        ),
        candidate_config(),
    )
    output_path = tmp_path / "selection.json"

    selection = write_tokenizer_selection(
        comparison,
        "representative_200m",
        output_path,
        operator_timestamp="2026-08-09T12:00:00+00:00",
    )

    assert selection["approved"] is True
    assert selection["winner"] == "representative_200m"
    assert selection["selected_tokenizer_sha256"] == "b" * 64
    assert selection["comparison_sha256"] == comparison["comparison_sha256"]
    assert json.loads(output_path.read_text(encoding="utf-8")) == selection


def test_selection_refuses_ineligible_candidate(tmp_path: Path):
    comparison = compare_tokenizers(
        evaluation(
            overall_tokens=10_000,
            general_tokens=6_000,
            telecom_tokens=3_000,
            probe_p95=4.0,
        ),
        evaluation(
            overall_tokens=9_800,
            general_tokens=5_700,
            telecom_tokens=3_100,
            probe_p95=4.0,
            tokenizer_sha256="b" * 64,
        ),
        candidate_config(),
    )

    with pytest.raises(ValueError, match="ineligible candidate"):
        write_tokenizer_selection(
            comparison,
            "representative_200m",
            tmp_path / "selection.json",
        )
