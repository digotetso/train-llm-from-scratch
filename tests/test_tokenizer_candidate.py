import hashlib
import json
from dataclasses import replace
from pathlib import Path, PurePosixPath

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
from matgpt.utils.hashing import sha256_file, sha256_json


SPECIAL_TOKEN_IDS = {
    "<|pad|>": 0,
    "<|bos|>": 1,
    "<|eos|>": 2,
    "<|system|>": 3,
    "<|user|>": 4,
    "<|assistant|>": 5,
    "<|end|>": 6,
}


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


def test_candidate_recipe_rejects_equal_labels(tmp_path: Path):
    raw = yaml.safe_load(
        Path("configs/data/telco_300m_tokenizer_candidate.yaml").read_text(
            encoding="utf-8"
        )
    )
    raw["candidate_label"] = raw["baseline_label"]
    path = tmp_path / "candidate.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="labels must differ"):
        load_tokenizer_candidate_config(path)


def test_candidate_config_direct_construction_rejects_equal_labels():
    config = candidate_config()

    with pytest.raises(ValueError, match="labels must differ"):
        replace(config, candidate_label=config.baseline_label)


def test_candidate_config_direct_construction_rejects_non_advisory_storage_mode():
    config = candidate_config()

    with pytest.raises(ValueError, match="storage_enforcement must be advisory"):
        replace(config, storage_enforcement="enforced")


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
        "local": {
            "max_working_gib": 20,
            "min_free_gib": 25,
            "enforcement": "advisory",
        },
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


def test_candidate_storage_limits_are_explicitly_advisory():
    config = load_tokenizer_candidate_config(
        "configs/data/telco_300m_tokenizer_candidate.yaml"
    )

    assert config.storage_enforcement == "advisory"


def evaluation(
    *,
    overall_tokens: int,
    general_tokens: int,
    telecom_tokens: int,
    probe_p95: float,
    tokenizer_sha256: str = "a" * 64,
    input_files_sha256: str = "c" * 64,
    probe_sets_sha256: str = "d" * 64,
    sample_manifest_sha256: str = "e" * 64,
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
        "tokenizer_identity_failures": 0,
        "algorithm": "byte_level_bpe",
        "vocab_size_requested": 32_768,
        "vocab_size_actual": 32_768,
        "special_token_ids": SPECIAL_TOKEN_IDS,
        "tokenizer_sha256": tokenizer_sha256,
        "input_files_sha256": input_files_sha256,
        "probe_sets_sha256": probe_sets_sha256,
        "sample_manifest_sha256": sample_manifest_sha256,
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


def test_comparison_recommends_candidate_when_only_baseline_has_a_fatal_gate():
    baseline = evaluation(
        overall_tokens=10_000,
        general_tokens=6_000,
        telecom_tokens=3_000,
        probe_p95=4.0,
    )
    baseline["round_trip_failures"] = 1
    candidate = evaluation(
        overall_tokens=9_850,
        general_tokens=6_030,
        telecom_tokens=2_900,
        probe_p95=4.02,
        tokenizer_sha256="b" * 64,
    )

    report = compare_tokenizers(baseline, candidate, candidate_config())

    assert report["shared_evidence_valid"] is True
    assert report["side_validity"] == {"baseline": False, "candidate": True}
    assert report["recommended_winner"] == "representative_200m"
    assert "round_trip_failure" in report["baseline_fatal_failures"]


def test_comparison_recommends_baseline_when_only_candidate_has_a_fatal_gate():
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
    candidate["special_token_failures"] = 1

    report = compare_tokenizers(baseline, candidate, candidate_config())

    assert report["shared_evidence_valid"] is True
    assert report["side_validity"] == {"baseline": True, "candidate": False}
    assert report["recommended_winner"] == "pilot_20m"
    assert "special_token_failure" in report["candidate_fatal_failures"]


def test_comparison_recommends_no_winner_when_both_sides_are_invalid():
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
    baseline["round_trip_failures"] = 1
    candidate["special_token_failures"] = 1

    report = compare_tokenizers(baseline, candidate, candidate_config())

    assert report["side_validity"] == {"baseline": False, "candidate": False}
    assert report["recommended_winner"] is None


def test_comparison_recommends_no_winner_when_shared_evidence_is_invalid():
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
        input_files_sha256="f" * 64,
    )

    report = compare_tokenizers(baseline, candidate, candidate_config())

    assert report["shared_evidence_valid"] is False
    assert report["recommended_winner"] is None
    assert "holdout_mismatch" in report["shared_fatal_failures"]


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


@pytest.mark.parametrize(
    ("side", "field", "value", "failure"),
    [
        ("baseline", "input_files_sha256", None, "holdout_fingerprint_invalid"),
        ("candidate", "input_files_sha256", "ABC", "holdout_fingerprint_invalid"),
        ("baseline", "probe_sets_sha256", None, "probe_fingerprint_invalid"),
        ("candidate", "probe_sets_sha256", "f" * 63, "probe_fingerprint_invalid"),
    ],
)
def test_comparison_blocks_missing_or_malformed_shared_fingerprints(
    side: str, field: str, value: str | None, failure: str
):
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
    target = baseline if side == "baseline" else candidate
    if value is None:
        target.pop(field)
    else:
        target[field] = value

    report = compare_tokenizers(baseline, candidate, candidate_config())

    assert report["eligible"] is False
    assert failure in report["guardrail_failures"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("algorithm", "wordpiece"),
        ("vocab_size_requested", 320),
        ("vocab_size_actual", 320),
        ("tokenizer_identity_failures", 1),
        ("special_token_ids", {"<|pad|>": 0}),
        (
            "special_token_ids",
            {**SPECIAL_TOKEN_IDS, "<|pad|>": False},
        ),
    ],
)
def test_comparison_blocks_invalid_candidate_tokenizer_identity(
    field: str, value: object
):
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
    candidate[field] = value

    report = compare_tokenizers(baseline, candidate, candidate_config())

    assert report["eligible"] is False
    assert "tokenizer_identity_failure" in report["guardrail_failures"]


def test_comparison_rejects_equal_labels_even_if_config_is_mutated():
    config = candidate_config()
    object.__setattr__(config, "candidate_label", config.baseline_label)

    with pytest.raises(ValueError, match="labels must differ"):
        compare_tokenizers(
            evaluation(
                overall_tokens=10_000,
                general_tokens=6_000,
                telecom_tokens=3_000,
                probe_p95=4.0,
            ),
            evaluation(
                overall_tokens=9_700,
                general_tokens=5_900,
                telecom_tokens=2_850,
                probe_p95=3.9,
            ),
            config,
        )


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
    output_path = tmp_path / "tokenizer_selection.json"

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


def test_selection_refuses_invalid_baseline_even_with_an_explicit_override(
    tmp_path: Path,
):
    baseline = evaluation(
        overall_tokens=10_000,
        general_tokens=6_000,
        telecom_tokens=3_000,
        probe_p95=4.0,
    )
    baseline["round_trip_failures"] = 1
    comparison = compare_tokenizers(
        baseline,
        evaluation(
            overall_tokens=9_850,
            general_tokens=6_030,
            telecom_tokens=2_900,
            probe_p95=4.02,
            tokenizer_sha256="b" * 64,
        ),
        candidate_config(),
    )

    with pytest.raises(ValueError, match="invalid baseline"):
        write_tokenizer_selection(
            comparison,
            "pilot_20m",
            tmp_path / "tokenizer_selection.json",
        )


def test_selection_refuses_to_overwrite_existing_approval(tmp_path: Path):
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
    output_path = tmp_path / "tokenizer_selection.json"
    output_path.write_text("existing approval\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        write_tokenizer_selection(
            comparison,
            "representative_200m",
            output_path,
        )

    assert output_path.read_text(encoding="utf-8") == "existing approval\n"


def test_selection_requires_dedicated_output_name(tmp_path: Path):
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

    with pytest.raises(ValueError, match="tokenizer_selection.json"):
        write_tokenizer_selection(
            comparison,
            "representative_200m",
            tmp_path / "tokenizer.json",
        )


def _local_cli_common_args(tmp_path: Path) -> tuple[list[str], Path, Path]:
    work_dir = tmp_path / "local-work"
    drive_dir = tmp_path / "drive-publish"
    drive_dir.mkdir()
    return (
        [
            "--sources",
            "configs/data/telco_300m_sources.yaml",
            "--mixture",
            "configs/data/telco_300m_mixture.yaml",
            "--candidate-config",
            "configs/data/telco_300m_tokenizer_candidate.yaml",
            "--model-config",
            "configs/matgpt_telco_300m.yaml",
            "--work-dir",
            str(work_dir),
            "--drive-dir",
            str(drive_dir),
        ],
        work_dir,
        drive_dir,
    )


def _complete_contamination_evidence(
    tmp_path: Path,
    *,
    empty: tuple[str, str] | None = None,
    with_manifests: bool = False,
) -> list[str]:
    registry = load_source_registry("configs/data/telco_300m_sources.yaml")
    paths: list[Path] = []
    for dataset in ("lite", "full"):
        root = tmp_path / f"open_telco_{dataset}"
        root.mkdir(parents=True)
        configs: dict[str, dict[str, object]] = {}
        for config in ("oranbench", "sixg_bench", "srsranbench", "teleqna"):
            path = root / f"{config}.jsonl"
            text = "" if empty == (dataset, config) else f'{json.dumps({"prompt": f"{dataset} {config} evidence"})}\n'
            path.write_text(text, encoding="utf-8")
            configs[config] = {
                "path": path.name,
                "examples": 0 if not text else 1,
                "raw_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            paths.append(path)
        if with_manifests:
            source = registry.by_id[f"open_telco_{dataset}"]
            manifest = {
                "version": 1,
                "complete": True,
                "created_at": "2026-08-09T00:00:00+00:00",
                "dataset_id": source.hf_name,
                "source_id": source.id,
                "revision": source.revision,
                "role": source.role,
                "license": source.license,
                "configs": configs,
            }
            manifest["manifest_sha256"] = sha256_json(manifest)
            (root / "manifest.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    return [str(path) for path in paths]


def _with_contamination(arguments: list[str], paths: list[str]) -> list[str]:
    result = list(arguments)
    for path in paths:
        result.extend(["--contamination-patterns", path])
    return result


def test_local_cli_rejects_overlapping_work_and_drive_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    def reject_expensive_sample(*_args, **_kwargs):
        raise AssertionError("test must not reach the real 200M sample builder")

    monkeypatch.setattr(
        prepare_telco_local, "build_tokenizer_sample", reject_expensive_sample
    )

    common, _, drive_dir = _local_cli_common_args(tmp_path)
    work_index = common.index("--work-dir") + 1
    common[work_index] = str(drive_dir)

    result = prepare_telco_local.main(["--stage", "tokenizer_sample", *common])

    assert result != 0
    assert not (drive_dir / "tokenizer_sample").exists()


def test_local_cli_requires_contamination_evidence_before_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    def reject_expensive_sample(*_args, **_kwargs):
        raise AssertionError("test must not reach the real 200M sample builder")

    monkeypatch.setattr(
        prepare_telco_local, "build_tokenizer_sample", reject_expensive_sample
    )

    common, work_dir, _ = _local_cli_common_args(tmp_path)

    result = prepare_telco_local.main(["--stage", "tokenizer_sample", *common])

    assert result != 0
    assert not work_dir.exists()


def test_local_cli_requires_all_eight_contamination_files_before_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    def reject_expensive_sample(*_args, **_kwargs):
        raise AssertionError("test must not reach the real 200M sample builder")

    monkeypatch.setattr(
        prepare_telco_local, "build_tokenizer_sample", reject_expensive_sample
    )
    common, work_dir, _ = _local_cli_common_args(tmp_path)
    paths = _complete_contamination_evidence(tmp_path / "evidence")

    result = prepare_telco_local.main(
        ["--stage", "tokenizer_sample", *_with_contamination(common, paths[:-1])]
    )

    assert result != 0
    assert not work_dir.exists()


def test_local_cli_rejects_empty_contamination_file_before_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    def reject_expensive_sample(*_args, **_kwargs):
        raise AssertionError("test must not reach the real 200M sample builder")

    monkeypatch.setattr(
        prepare_telco_local, "build_tokenizer_sample", reject_expensive_sample
    )
    common, work_dir, _ = _local_cli_common_args(tmp_path)
    paths = _complete_contamination_evidence(
        tmp_path / "evidence", empty=("full", "teleqna")
    )

    result = prepare_telco_local.main(
        ["--stage", "tokenizer_sample", *_with_contamination(common, paths)]
    )

    assert result != 0
    assert not work_dir.exists()


@pytest.mark.parametrize(
    ("option", "canonical"),
    (
        ("--sources", "configs/data/telco_300m_sources.yaml"),
        ("--mixture", "configs/data/telco_300m_mixture.yaml"),
        (
            "--candidate-config",
            "configs/data/telco_300m_tokenizer_candidate.yaml",
        ),
        ("--model-config", "configs/matgpt_telco_300m.yaml"),
    ),
)
def test_local_cli_rejects_alternate_config_identity_before_sample(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    option: str,
    canonical: str,
):
    from scripts import prepare_telco_local

    def reject_expensive_sample(*_args, **_kwargs):
        raise AssertionError("test must not reach the real 200M sample builder")

    monkeypatch.setattr(
        prepare_telco_local, "build_tokenizer_sample", reject_expensive_sample
    )
    common, work_dir, _ = _local_cli_common_args(tmp_path)
    altered = tmp_path / Path(canonical).name
    altered.write_bytes(Path(canonical).read_bytes() + b"\n")
    common[common.index(option) + 1] = str(altered)
    paths = _complete_contamination_evidence(tmp_path / "evidence")

    result = prepare_telco_local.main(
        ["--stage", "tokenizer_sample", *_with_contamination(common, paths)]
    )

    assert result != 0
    assert not work_dir.exists()


def test_local_cli_cross_checks_available_contamination_manifests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    def reject_expensive_sample(*_args, **_kwargs):
        raise AssertionError("test must not reach the real 200M sample builder")

    monkeypatch.setattr(
        prepare_telco_local, "build_tokenizer_sample", reject_expensive_sample
    )
    common, work_dir, _ = _local_cli_common_args(tmp_path)
    paths = _complete_contamination_evidence(
        tmp_path / "evidence", with_manifests=True
    )
    manifest_path = Path(paths[0]).parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["configs"]["oranbench"]["sha256"] = "0" * 64
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256")
    manifest["manifest_sha256"] = sha256_json(unsigned)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = prepare_telco_local.main(
        ["--stage", "tokenizer_sample", *_with_contamination(common, paths)]
    )

    assert result != 0
    assert not work_dir.exists()


def test_local_cli_requires_both_contamination_manifests_before_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    def reject_expensive_sample(*_args, **_kwargs):
        raise AssertionError("test must not reach the real 200M sample builder")

    monkeypatch.setattr(
        prepare_telco_local, "build_tokenizer_sample", reject_expensive_sample
    )
    common, work_dir, _ = _local_cli_common_args(tmp_path)
    paths = _complete_contamination_evidence(tmp_path / "evidence")

    result = prepare_telco_local.main(
        ["--stage", "tokenizer_sample", *_with_contamination(common, paths)]
    )

    assert result != 0
    assert not work_dir.exists()


def test_local_cli_accepts_complete_manifest_bound_contamination_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    captured_patterns: list[str] = []

    def fake_sample(request, **_kwargs):
        captured_patterns.extend(request.quality_policy.contamination_patterns)
        return {"complete": True}

    monkeypatch.setattr(prepare_telco_local, "build_tokenizer_sample", fake_sample)
    common, work_dir, _ = _local_cli_common_args(tmp_path)
    paths = _complete_contamination_evidence(
        work_dir / "evaluation", with_manifests=True
    )

    result = prepare_telco_local.main(
        ["--stage", "tokenizer_sample", *_with_contamination(common, paths)]
    )

    assert result == 0
    assert len(captured_patterns) == 8


def test_local_cli_reports_storage_limits_as_advisory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    from scripts import prepare_telco_local

    common, _, _ = _local_cli_common_args(tmp_path)

    assert prepare_telco_local.main(["--stage", "tokenizer_sample", *common]) != 0
    output = capsys.readouterr().out
    advisory = json.loads(output.splitlines()[0])
    assert advisory == {
        "enforced": False,
        "event": "storage_advisory",
        "max_working_gib": 20,
        "min_free_gib": 25,
        "mode": "advisory",
    }


def test_local_cli_refuses_to_overwrite_candidate_directory(tmp_path: Path):
    from scripts.prepare_telco_local import main

    common, work_dir, drive_dir = _local_cli_common_args(tmp_path)
    sample_manifest = _write_canonical_sample_manifest(work_dir)
    candidate_dir = drive_dir / "tokenizers" / "representative_200m"
    candidate_dir.mkdir(parents=True)
    marker = candidate_dir / "keep.txt"
    marker.write_text("existing candidate\n", encoding="utf-8")

    result = main(
        [
            "--stage",
            "tokenizer_candidate",
            *common,
            "--sample-manifest",
            str(sample_manifest),
        ]
    )

    assert result != 0
    assert marker.read_text(encoding="utf-8") == "existing candidate\n"


def _write_canonical_sample_manifest(work_dir: Path, digest: str | None = None) -> Path:
    from scripts import prepare_telco_local

    path = work_dir / "tokenizer_sample" / "manifest.json"
    path.parent.mkdir(parents=True)
    _complete_contamination_evidence(
        work_dir / "evaluation", with_manifests=True
    )
    provenance = prepare_telco_local._current_sample_provenance(
        work_dir=work_dir,
        registry=load_source_registry("configs/data/telco_300m_sources.yaml"),
        mixture=load_mixture_config("configs/data/telco_300m_mixture.yaml"),
        candidate_config=load_tokenizer_candidate_config(
            "configs/data/telco_300m_tokenizer_candidate.yaml"
        ),
        model_config=prepare_telco_local.load_config(
            "configs/matgpt_telco_300m.yaml"
        ),
    )
    payload = {
        "version": 3,
        "complete": True,
        "build_provenance": provenance,
        "build_provenance_sha256": sha256_json(provenance),
    }
    payload["manifest_sha256"] = digest or sha256_json(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_local_cli_candidate_requires_canonical_sample_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    def reject_training(*_args, **_kwargs):
        raise AssertionError("test must not reach tokenizer training")

    monkeypatch.setattr(
        prepare_telco_local, "train_tokenizer_from_manifest", reject_training
    )
    common, work_dir, _ = _local_cli_common_args(tmp_path)
    canonical = _write_canonical_sample_manifest(work_dir)
    copied = tmp_path / "copied-manifest.json"
    copied.write_bytes(canonical.read_bytes())

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_candidate",
            *common,
            "--sample-manifest",
            str(copied),
        ]
    )

    assert result != 0


@pytest.mark.parametrize(
    "manifest_payload",
    (
        {"manifest_sha256": "a" * 64},
        {
            "manifest_sha256": "a" * 64,
            "build_provenance_sha256": "b" * 64,
            "build_provenance": {"version": 1, "workflow": "foreign_workflow"},
        },
    ),
    ids=("missing", "foreign"),
)
def test_local_cli_candidate_rejects_unbound_or_foreign_sample_provenance_before_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    manifest_payload: dict[str, object],
):
    from scripts import prepare_telco_local

    common, work_dir, drive_dir = _local_cli_common_args(tmp_path)
    manifest = work_dir / "tokenizer_sample" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")

    def reject_training(*_args, **_kwargs):
        raise AssertionError("unbound sample must fail before tokenizer training")

    monkeypatch.setattr(
        prepare_telco_local, "train_tokenizer_from_manifest", reject_training
    )

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_candidate",
            *common,
            "--sample-manifest",
            str(manifest),
        ]
    )

    assert result != 0
    assert not (drive_dir / "tokenizers" / "representative_200m").exists()


def test_local_cli_candidate_rejects_self_consistent_stale_sample_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, work_dir, drive_dir = _local_cli_common_args(tmp_path)
    manifest_path = _write_canonical_sample_manifest(work_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    recipe = manifest["build_provenance"]["recipe"]
    recipe["candidate_config_file_sha256"] = "0" * 64
    unsigned_recipe = dict(recipe)
    unsigned_recipe.pop("sha256")
    recipe["sha256"] = sha256_json(unsigned_recipe)
    manifest["build_provenance_sha256"] = sha256_json(
        manifest["build_provenance"]
    )
    manifest.pop("manifest_sha256")
    manifest["manifest_sha256"] = sha256_json(manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def reject_training(*_args, **_kwargs):
        raise AssertionError("stale sample must fail before tokenizer training")

    monkeypatch.setattr(
        prepare_telco_local, "train_tokenizer_from_manifest", reject_training
    )

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_candidate",
            *common,
            "--sample-manifest",
            str(manifest_path),
        ]
    )

    assert result != 0
    assert not (drive_dir / "tokenizers" / "representative_200m").exists()


def test_local_cli_refuses_symlinked_candidate_publish_directory_before_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, work_dir, drive_dir = _local_cli_common_args(tmp_path)
    sample_manifest = _write_canonical_sample_manifest(work_dir)
    outside = tmp_path / "outside-tokenizers"
    outside.mkdir()
    (drive_dir / "tokenizers").symlink_to(outside, target_is_directory=True)

    def reject_training(*_args, **_kwargs):
        raise AssertionError("symlinked publish path must fail before training")

    monkeypatch.setattr(
        prepare_telco_local, "train_tokenizer_from_manifest", reject_training
    )

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_candidate",
            *common,
            "--sample-manifest",
            str(sample_manifest),
        ]
    )

    assert result != 0
    assert list(outside.iterdir()) == []


def test_local_cli_atomically_claims_candidate_before_training(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, work_dir, drive_dir = _local_cli_common_args(tmp_path)
    sample_manifest = _write_canonical_sample_manifest(work_dir)
    expected_digest = json.loads(sample_manifest.read_text(encoding="utf-8"))[
        "manifest_sha256"
    ]

    def fake_training(
        _manifest,
        output_dir,
        _vocab_size,
        _min_frequency,
        _special_tokens,
        _probe_sets,
    ):
        destination = Path(output_dir)
        assert destination.is_dir()
        (destination / "tokenizer.json").write_text("{}\n", encoding="utf-8")
        (destination / "special_tokens.json").write_text("{}\n", encoding="utf-8")
        report = {
            "fitting_manifest_sha256": expected_digest,
            "tokenizer_sha256": sha256_file(destination / "tokenizer.json"),
        }
        (destination / "tokenizer_report.json").write_text(
            json.dumps(report), encoding="utf-8"
        )
        return report

    monkeypatch.setattr(
        prepare_telco_local, "train_tokenizer_from_manifest", fake_training
    )

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_candidate",
            *common,
            "--sample-manifest",
            str(sample_manifest),
        ]
    )

    assert result == 0
    assert (drive_dir / "tokenizers" / "representative_200m").is_dir()


def test_local_cli_candidate_atomic_claim_loses_race_without_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, work_dir, drive_dir = _local_cli_common_args(tmp_path)
    sample_manifest = _write_canonical_sample_manifest(work_dir)
    destination = drive_dir / "tokenizers" / "representative_200m"
    original_manifest_check = prepare_telco_local._canonical_sample_manifest

    def insert_competing_destination(*args, **kwargs):
        result = original_manifest_check(*args, **kwargs)
        destination.mkdir(parents=True)
        (destination / "competitor.txt").write_text("keep\n", encoding="utf-8")
        return result

    def reject_training(*_args, **_kwargs):
        raise AssertionError("losing racer must not train or overwrite")

    monkeypatch.setattr(
        prepare_telco_local,
        "_canonical_sample_manifest",
        insert_competing_destination,
    )
    monkeypatch.setattr(
        prepare_telco_local, "train_tokenizer_from_manifest", reject_training
    )

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_candidate",
            *common,
            "--sample-manifest",
            str(sample_manifest),
        ]
    )

    assert result != 0
    assert (destination / "competitor.txt").read_text(encoding="utf-8") == "keep\n"


def test_local_cli_candidate_preserves_claim_when_manifest_binding_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, work_dir, drive_dir = _local_cli_common_args(tmp_path)
    sample_manifest = _write_canonical_sample_manifest(work_dir)

    def fake_training(
        _manifest,
        output_dir,
        _vocab_size,
        _min_frequency,
        _special_tokens,
        _probe_sets,
    ):
        report = {
            "fitting_manifest_sha256": "0" * 64,
            "tokenizer_sha256": "b" * 64,
        }
        (Path(output_dir) / "tokenizer_report.json").write_text(
            json.dumps(report), encoding="utf-8"
        )
        return report

    monkeypatch.setattr(
        prepare_telco_local, "train_tokenizer_from_manifest", fake_training
    )

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_candidate",
            *common,
            "--sample-manifest",
            str(sample_manifest),
        ]
    )

    destination = drive_dir / "tokenizers" / "representative_200m"
    assert result != 0
    assert destination.is_dir()
    assert (destination / "tokenizer_report.json").is_file()


def _comparison_cli_fixture(
    tmp_path: Path,
) -> tuple[list[str], Path, Path, Path, str, str]:
    common, work_dir, drive_dir = _local_cli_common_args(tmp_path)
    sample_manifest = _write_canonical_sample_manifest(work_dir)
    baseline_dir, provenance, baseline_sha256 = _canonical_pilot_fixture(drive_dir)
    drive_option_index = common.index("--drive-dir")
    common[drive_option_index:drive_option_index] = [
        "--baseline-provenance",
        str(provenance),
    ]
    candidate_dir = drive_dir / "tokenizers" / "representative_200m"
    candidate_dir.mkdir(parents=True)
    (candidate_dir / "tokenizer.json").write_bytes(b"candidate tokenizer")
    (candidate_dir / "special_tokens.json").write_text("{}\n", encoding="utf-8")
    candidate_sha256 = sha256_file(candidate_dir / "tokenizer.json")
    (candidate_dir / "tokenizer_report.json").write_text(
        json.dumps(
            {
                "fitting_manifest_sha256": json.loads(
                    sample_manifest.read_text(encoding="utf-8")
                )["manifest_sha256"],
                "tokenizer_sha256": candidate_sha256,
            }
        ),
        encoding="utf-8",
    )
    return (
        common,
        sample_manifest,
        baseline_dir,
        candidate_dir,
        baseline_sha256,
        candidate_sha256,
    )


def _pilot_recipe_sha256() -> str:
    digest = hashlib.sha256()
    digest.update(b"telco-data-recipe-v1\0")
    digest.update(Path("configs/matgpt_telco_300m.yaml").read_bytes())
    digest.update(b"\0")
    digest.update(Path("configs/data/telco_300m_sources.yaml").read_bytes())
    digest.update(b"\0")
    digest.update(Path("configs/data/telco_300m_mixture.yaml").read_bytes())
    return digest.hexdigest()


def _canonical_pilot_fixture(drive_dir: Path) -> tuple[Path, Path, str]:
    recipe_sha256 = _pilot_recipe_sha256()
    recipe_root = drive_dir / "recipes" / recipe_sha256[:12]
    baseline = recipe_root / "prepared" / "pilot" / "tokenizer"
    baseline.mkdir(parents=True)
    (baseline / "tokenizer.json").write_bytes(b"canonical pilot tokenizer")
    (baseline / "special_tokens.json").write_text("{}\n", encoding="utf-8")
    tokenizer_sha256 = sha256_file(baseline / "tokenizer.json")
    corpus_manifest = recipe_root / "corpora" / "pilot" / "manifest.json"
    corpus_manifest.parent.mkdir(parents=True)
    pilot_stage = {
        "requested_tokens": 20_000_000,
        "estimated_tokens": 20_000_003,
        "quota_tokens": 20_000_003,
        "documents": 2,
        "document_count": 2,
        "items": {
            "canonical-source": {
                "requested_tokens": 20_000_000,
                "estimated_tokens": 20_000_003,
                "quota_tokens": 20_000_003,
                "documents": 2,
                "raw_bytes": 42,
            }
        },
    }
    validation_stage = {
        "estimated_tokens": 3,
        "quota_tokens": 3,
        "documents": 1,
        "document_count": 1,
        "items": {"canonical-source": 1},
    }
    corpus_payload = {
        "version": 1,
        "complete": True,
        "quota_counting": {
            "method": "tokenizer_exact",
            "tokenizer_sha256": tokenizer_sha256,
        },
        "stages": {"pilot": pilot_stage},
        "validation": validation_stage,
        "split_stats": {"pilot": pilot_stage, "validation": validation_stage},
    }
    corpus_payload["manifest_sha256"] = sha256_json(corpus_payload)
    corpus_manifest.write_text(json.dumps(corpus_payload), encoding="utf-8")
    provenance_path = (
        recipe_root / "evidence" / "pilot" / "tokenizer_provenance.json"
    )
    provenance_path.parent.mkdir(parents=True)
    provenance = {
        "version": 1,
        "stage": "pilot",
        "recipe_sha256": recipe_sha256,
        "recipe_id": recipe_sha256[:12],
        "sample_manifest_relative_path": "corpora/pilot/manifest.json",
        "sample_manifest_file_sha256": sha256_file(corpus_manifest),
        "sample_manifest_sha256": corpus_payload["manifest_sha256"],
        "tokenizer_relative_path": "prepared/pilot/tokenizer",
        "tokenizer_sha256": tokenizer_sha256,
    }
    provenance["provenance_sha256"] = sha256_json(provenance)
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    return baseline, provenance_path, tokenizer_sha256


def _write_pilot_gate_evidence(
    gate_root: Path,
    *,
    tokenizer_sha256: str,
    build_identity_sha256: str,
) -> None:
    gate_root.mkdir(parents=True, exist_ok=True)
    from matgpt.training.checkpoint_provenance import snapshot_checkpoint

    checkpoint_root = gate_root / "checkpoints"
    mutable = gate_root / "latest.pt"
    mutable.write_bytes(b"candidate smoke checkpoint")
    smoke_binding = snapshot_checkpoint(mutable, checkpoint_root, label="smoke")
    mutable.write_bytes(b"candidate pilot checkpoint")
    pilot_binding = snapshot_checkpoint(mutable, checkpoint_root, label="pilot")
    mutable.unlink()

    def payload(gate: str, **extra: object) -> dict[str, object]:
        return {
            "version": 1,
            "status": "pass",
            "gate": gate,
            "gate_passed": True,
            "tokenizer_sha256": tokenizer_sha256,
            "build_identity_sha256": build_identity_sha256,
            **extra,
        }

    from matgpt.preflight import CHECK_IDS as PREFLIGHT_CHECK_IDS
    (gate_root / "preflight.json").write_text(
        json.dumps(payload("preflight", checks=[
            {"name": name, "status": "pass", "message": "ok", "details": {}}
            for name in PREFLIGHT_CHECK_IDS
        ])), encoding="utf-8"
    )
    (gate_root / "smoke_resume_verified.json").write_text(
        json.dumps(payload(
            "smoke", resume_verified=True, checkpoint=smoke_binding["path"],
            checkpoint_binding=smoke_binding,
        )), encoding="utf-8"
    )
    (gate_root / "pilot_complete.json").write_text(
        json.dumps(payload(
            "pilot", complete=True, tokens_processed=20_000_000,
            checkpoint=pilot_binding["path"], checkpoint_binding=pilot_binding,
            checkpoint_bindings=[pilot_binding],
        )),
        encoding="utf-8",
    )
    evaluation_dir = gate_root / "evaluation"
    evaluation_dir.mkdir(parents=True, exist_ok=True)
    (evaluation_dir / "review.json").write_text(
        json.dumps(payload(
            "evaluation", evaluation_passed=True,
            checkpoint=pilot_binding["path"], checkpoint_binding=pilot_binding,
        )), encoding="utf-8"
    )


def _write_valid_preserved_pilot_evidence(
    drive_dir: Path, selected_sha256: str
) -> tuple[Path, str]:
    from scripts import prepare_telco_local

    _, provenance_path, _ = prepare_telco_local._canonical_pilot_provenance(
        drive_dir
    )
    recipe_root = provenance_path.parents[2]
    _, build_identity_sha256 = prepare_telco_local._validated_pilot_manifest(
        recipe_root / "corpora/pilot/manifest.json",
        managed_root=drive_dir,
        tokenizer_sha256=selected_sha256,
    )
    shard_root = recipe_root / "prepared/pilot/shards"
    shard_root.mkdir(parents=True, exist_ok=True)
    pilot_shard = shard_root / "pilot_00000.bin"
    with pilot_shard.open("wb") as handle:
        chunk = b"\x01\x00" * 524_288
        for document_tokens in (10_000_000, 10_000_003):
            remaining = document_tokens
            while remaining:
                count = min(remaining, 524_288)
                handle.write(chunk[: count * 2])
                remaining -= count
            handle.write(b"\x02\x00")
    validation_shard = shard_root / "validation_00000.bin"
    validation_shard.write_bytes(b"\x01\x00" * 3 + b"\x02\x00")
    from matgpt.data.shard import build_split_metadata

    metadata = build_split_metadata(
        split="pilot",
        tokenizer_sha256=selected_sha256,
        dtype="uint16",
        append_eos=True,
        shard_size_tokens=1024,
        total_documents=2,
        shards=[{
            "relative_path": "pilot_00000.bin",
            "index": 0,
            "num_tokens": 20_000_005,
            "num_documents": 2,
            "byte_size": 40_000_010,
            "sha256": sha256_file(pilot_shard),
        }],
    )
    (shard_root / "pilot_metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    validation_metadata = build_split_metadata(
        split="validation", tokenizer_sha256=selected_sha256, dtype="uint16",
        append_eos=True, shard_size_tokens=1024, total_documents=1,
        shards=[{"relative_path": "validation_00000.bin", "num_tokens": 4,
                 "index": 0,
                 "num_documents": 1, "byte_size": 8,
                 "sha256": sha256_file(validation_shard)}],
    )
    (shard_root / "validation_metadata.json").write_text(
        json.dumps(validation_metadata), encoding="utf-8"
    )
    config_path = recipe_root / "prepared/pilot/config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = yaml.safe_load(Path("configs/matgpt_telco_300m.yaml").read_text())
    config["dataset"].update({"normalized_dir": str(recipe_root / "corpora/pilot"),
        "train_split": "pilot", "training_splits": {"pilot": "pilot"}})
    config["tokenizer"]["output_dir"] = str(recipe_root / "prepared/pilot/tokenizer")
    config["sharding"]["output_dir"] = str(shard_root)
    config["run"]["output_dir"] = str(recipe_root / "runs/pilot")
    config["training"].update({"max_tokens": 20_000_000,
        "data_phases": [{"name": "pilot", "split": "pilot",
                         "until_tokens": 20_000_000}]})
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    from matgpt.config import config_to_yaml, load_config
    from matgpt.preflight import CHECK_IDS as PREFLIGHT_CHECK_IDS
    from matgpt.utils.hashing import sha256_text
    config_sha = sha256_text(config_to_yaml(load_config(config_path)))
    manifest_path = recipe_root / "corpora/pilot/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    artifact_identity = {
        "config_sha256": config_sha,
        "tokenizer_sha256": selected_sha256,
        "dataset_manifest_sha256": sha256_file(manifest_path),
        "dataset_manifest_identity_sha256": manifest["manifest_sha256"],
        "build_identity_sha256": build_identity_sha256,
    }
    metadata_by_split = {"pilot": metadata, "validation": validation_metadata}
    checks = []
    for name in PREFLIGHT_CHECK_IDS:
        details: dict[str, object] = {}
        if name == "config":
            details = {"config_sha256": config_sha}
        elif name == "tokenizer":
            details = {"tokenizer_sha256": selected_sha256, "vocab_size": 32_768}
        elif name == "dataset_manifest":
            details = {"manifest_sha256": manifest["manifest_sha256"]}
        elif name == "shards":
            details = {
                split: {
                    "total_tokens": split_metadata["total_tokens"],
                    "metadata_sha256": split_metadata["metadata_sha256"],
                    "shard_files_sha256": sha256_json([
                        {"path": row["path"], "byte_size": row["byte_size"],
                         "num_tokens": row["num_tokens"], "sha256": row["sha256"]}
                        for row in split_metadata["shards"]
                    ]),
                }
                for split, split_metadata in metadata_by_split.items()
            }
        checks.append({"name": name, "status": "pass", "message": "ok",
                       "details": details})
    evidence_root = recipe_root / "evidence/pilot"
    evidence_root.mkdir(parents=True, exist_ok=True)
    (evidence_root / "preflight.json").write_text(
        json.dumps({"status": "pass", "environment": {}, "checks": checks}),
        encoding="utf-8",
    )
    checkpoint_root = recipe_root / "runs/pilot/checkpoints"
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    from matgpt.training.checkpoint_provenance import snapshot_checkpoint

    mutable = checkpoint_root / "latest.pt"
    mutable.write_bytes(b"canonical smoke checkpoint")
    smoke_binding = snapshot_checkpoint(mutable, checkpoint_root, label="smoke")
    mutable.write_bytes(b"canonical pilot latest checkpoint")
    pilot_binding = snapshot_checkpoint(mutable, checkpoint_root, label="pilot-latest")
    mutable.write_bytes(b"canonical pilot best checkpoint")
    pilot_best_binding = snapshot_checkpoint(mutable, checkpoint_root, label="pilot-best")
    mutable.unlink()
    (evidence_root / "smoke_resume_verified.json").write_text(json.dumps({
        "status": "pass", "resume_verified": True,
        "checkpoint": smoke_binding["path"],
        "checkpoint_binding": smoke_binding,
        "artifact_identity": artifact_identity,
    }), encoding="utf-8")
    (evidence_root / "pilot_complete.json").write_text(json.dumps({
        "status": "pass", "complete": True, "tokens_processed": 20_000_000,
        "checkpoint": pilot_binding["path"],
        "checkpoint_binding": pilot_binding,
        "checkpoint_bindings": [pilot_binding, pilot_best_binding],
        "artifact_identity": artifact_identity,
    }), encoding="utf-8")
    evaluation = recipe_root / "runs/pilot/evaluation/current"
    evaluation.mkdir(parents=True, exist_ok=True)
    checkpoint_rows = {}
    for index, (name, binding) in enumerate((
        ("latest.pt", pilot_binding), ("best.pt", pilot_best_binding)
    )):
        label = f"checkpoint_{index:02d}_{Path(name).stem}"
        checkpoint_ref = binding["path"]
        (evaluation / f"{label}_base.json").write_text(json.dumps({
            "checkpoint": checkpoint_ref, "evaluation_seed": 42,
            "checkpoint_binding": binding,
            "artifact_identity": artifact_identity,
            "validation_seed": 43, "generation_seed": 42,
            "val_loss": 2.0 + index / 10, "perplexity": 7.389 + index,
            "samples": [{"prompt": "A router", "text": "A router forwards packets."}],
        }), encoding="utf-8")
        (evaluation / f"{label}_open_telco.json").write_text(json.dumps({
            "checkpoint": checkpoint_ref,
            "checkpoint_binding": binding,
            "artifact_identity": artifact_identity,
            "tasks": [{"task_type": "multiple_choice", "path": "teleqna.jsonl",
                "total": 1, "correct": 1, "accuracy": 1.0,
                "categories": {"routing": {"total": 1, "correct": 1,
                                              "accuracy": 1.0}},
                "examples": [{"id": "q1", "category": "routing",
                    "answer_index": 0, "prediction_index": 0, "correct": True,
                    "choice_losses": [0.1, 1.0]}]}]
        }), encoding="utf-8")
        checkpoint_rows[label] = {"path": checkpoint_ref, "binding": binding,
                                   "evidence": f"checkpoints/{label}.json"}
    comparison_root = evaluation / "checkpoint_comparison"
    (comparison_root / "checkpoints").mkdir(parents=True)
    for label, row in checkpoint_rows.items():
        (comparison_root / row["evidence"]).write_text(json.dumps({
            "checkpoint_label": label, "checkpoint_path": row["path"],
            "checkpoint_binding": row["binding"],
            "artifact_identity": artifact_identity,
            "validation": [{"seed": 1001, "loss": 2.0, "perplexity": 7.389}],
            "consistency_task": {"task_type": "multiple_choice",
                "path": "story_consistency.jsonl", "total": 1,
                "correct": 1, "accuracy": 1.0,
                "categories": {"routing": {"total": 1, "correct": 1,
                                              "accuracy": 1.0}},
                "examples": [{"id": "q1", "category": "routing",
                    "answer_index": 0, "prediction_index": 0, "correct": True,
                    "choice_losses": [0.1, 1.0]}]},
            "generations": [{"generation_id": f"{label}-g1", "prompt_id": "p1",
                "prompt_category": "routing", "prompt": "A router", "text": "Story",
                "generation_seed": 2001, "repetition": {"repeated_4gram_fraction": 0.0}}],
            "generation_summary": {"repeated_4gram_fraction": 0.0},
        }), encoding="utf-8")
    comparison_payload = {
        "protocol": {"validation_seeds": [1001], "generation_seeds": [2001],
            "review_seed": 3001, "review_per_checkpoint": 1,
            "judge_batch_size": 1, "prompt_count": 1,
            "task_category_counts": {"routing": 1},
            "same_validation_dataset": "validation_metadata.json",
            "generation": {"max_new_tokens": 10, "temperature": 0.7,
                           "top_k": 50, "top_p": 0.95}},
        "config": {"path": str(config_path.resolve()), "sha256": config_sha},
        "artifact_identity": artifact_identity,
        "checkpoints": checkpoint_rows,
        "validation": {"checkpoints": {label: {"seed_count": 1,
            "mean_loss": 2.0, "stdev_loss": 0.0, "minimum_loss": 2.0,
            "maximum_loss": 2.0} for label in checkpoint_rows}, "pairs": []},
        "consistency": {label: {"total": 1, "correct": 1, "accuracy": 1.0,
                                 "categories": {}} for label in checkpoint_rows},
        "generations": {label: {"repeated_4gram_fraction": 0.0}
                        for label in checkpoint_rows},
        "llm_judge": {"status": "awaiting_judgments",
            "batch_directory": "llm_judge/batches", "review_key": "llm_judge/review_key.json",
            "judge_prompt": "llm_judge/judge_prompt.md", "review_count": 2},
    }
    comparison_path = comparison_root / "comparison_summary.json"
    comparison_path.write_text(json.dumps(comparison_payload), encoding="utf-8")
    review_key = {
        f"review-{index:04d}": {"checkpoint_label": label,
            "generation_id": f"{label}-g1", "prompt_id": "p1",
            "generation_seed": 2001}
        for index, label in enumerate(checkpoint_rows, start=1)
    }
    (comparison_root / "llm_judge").mkdir(parents=True)
    (comparison_root / "llm_judge/review_key.json").write_text(
        json.dumps(review_key), encoding="utf-8"
    )
    scored = comparison_root / "llm_judge/results/scored_llm.json"
    scored.parent.mkdir(parents=True)
    scored.write_text(json.dumps({"reviewer": "llm", "review_count": 2,
        "artifact_identity": artifact_identity,
        "judgments": [{"review_id": f"review-{index:04d}",
            "checkpoint_label": label, "generation_id": f"{label}-g1",
            "prompt_id": "p1", "generation_seed": 2001,
            "character_consistency": 2, "object_location_consistency": 2,
            "causal_coherence": 2, "overall_consistency": 2,
            "flags": ["none"], "evidence": "The story remains consistent.",
            "reason": "No contradiction is present."}
            for index, label in enumerate(checkpoint_rows, start=1)],
        "summary": {"checkpoints": {label: {"mean_overall_consistency": 2.0}
                                      for label in checkpoint_rows}},
        "comparison": {"path": "../../comparison_summary.json",
                       "sha256": sha256_file(comparison_path)},
        "checkpoints": {label: dict(row["binding"])
            for label, row in checkpoint_rows.items()}},), encoding="utf-8")
    return recipe_root, build_identity_sha256


def _create_canonical_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[list[str], Path, Path, Path, Path]:
    from scripts import prepare_telco_local

    common, manifest, baseline, candidate, baseline_sha, candidate_sha = (
        _comparison_cli_fixture(tmp_path)
    )
    manifest_sha = json.loads(manifest.read_text(encoding="utf-8"))[
        "manifest_sha256"
    ]

    def fake_evaluation(tokenizer_dir, _inputs, _probes):
        is_candidate = Path(tokenizer_dir).resolve() == candidate.resolve()
        return evaluation(
            overall_tokens=9_850 if is_candidate else 10_000,
            general_tokens=6_030 if is_candidate else 6_000,
            telecom_tokens=2_900 if is_candidate else 3_000,
            probe_p95=4.02 if is_candidate else 4.0,
            tokenizer_sha256=candidate_sha if is_candidate else baseline_sha,
            sample_manifest_sha256=manifest_sha,
        )

    monkeypatch.setattr(
        prepare_telco_local, "evaluate_tokenizer_on_jsonl", fake_evaluation
    )
    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_compare",
            *common,
            "--baseline-tokenizer",
            str(baseline),
            "--candidate-tokenizer",
            str(candidate),
            "--holdout-manifest",
            str(manifest),
        ]
    )
    assert result == 0
    drive_dir = Path(common[-1])
    return common, manifest, baseline, candidate, drive_dir / "comparison.json"


def test_local_cli_comparison_binds_the_canonical_pilot_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, work_dir, drive_dir = _local_cli_common_args(tmp_path)
    sample_manifest = _write_canonical_sample_manifest(work_dir)
    sample_manifest_sha256 = json.loads(sample_manifest.read_text(encoding="utf-8"))[
        "manifest_sha256"
    ]
    baseline, provenance, baseline_sha256 = _canonical_pilot_fixture(drive_dir)
    candidate = drive_dir / "tokenizers" / "representative_200m"
    candidate.mkdir(parents=True)
    (candidate / "tokenizer.json").write_bytes(b"candidate tokenizer")
    (candidate / "special_tokens.json").write_text("{}\n", encoding="utf-8")
    candidate_sha256 = sha256_file(candidate / "tokenizer.json")
    (candidate / "tokenizer_report.json").write_text(
        json.dumps(
            {
                "fitting_manifest_sha256": sample_manifest_sha256,
                "tokenizer_sha256": candidate_sha256,
            }
        ),
        encoding="utf-8",
    )

    def fake_evaluation(tokenizer_dir, _inputs, _probes):
        is_candidate = Path(tokenizer_dir).resolve() == candidate.resolve()
        return evaluation(
            overall_tokens=9_850 if is_candidate else 10_000,
            general_tokens=6_030 if is_candidate else 6_000,
            telecom_tokens=2_900 if is_candidate else 3_000,
            probe_p95=4.02 if is_candidate else 4.0,
            tokenizer_sha256=candidate_sha256 if is_candidate else baseline_sha256,
            sample_manifest_sha256=sample_manifest_sha256,
        )

    monkeypatch.setattr(
        prepare_telco_local, "evaluate_tokenizer_on_jsonl", fake_evaluation
    )

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_compare",
            *common,
            "--baseline-tokenizer",
            str(baseline),
            "--baseline-provenance",
            str(provenance),
            "--candidate-tokenizer",
            str(candidate),
            "--holdout-manifest",
            str(sample_manifest),
        ]
    )

    assert result == 0
    comparison = json.loads((drive_dir / "comparison.json").read_text(encoding="utf-8"))
    assert comparison["workflow_evidence"]["baseline_provenance_sha256"] == (
        json.loads(provenance.read_text(encoding="utf-8"))["provenance_sha256"]
    )


def test_local_cli_comparison_requires_explicit_pilot_provenance_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, manifest, baseline, candidate, _, _ = _comparison_cli_fixture(tmp_path)
    provenance_index = common.index("--baseline-provenance")
    del common[provenance_index : provenance_index + 2]

    def reject_evaluation(*_args, **_kwargs):
        raise AssertionError("missing provenance must fail before evaluation")

    monkeypatch.setattr(
        prepare_telco_local, "evaluate_tokenizer_on_jsonl", reject_evaluation
    )

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_compare",
            *common,
            "--baseline-tokenizer",
            str(baseline),
            "--candidate-tokenizer",
            str(candidate),
            "--holdout-manifest",
            str(manifest),
        ]
    )

    assert result != 0
    assert not (Path(common[-1]) / "comparison.json").exists()


def test_local_cli_comparison_rejects_an_arbitrary_tokenizer_labeled_pilot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, work_dir, drive_dir = _local_cli_common_args(tmp_path)
    sample_manifest = _write_canonical_sample_manifest(work_dir)
    _, provenance, _ = _canonical_pilot_fixture(drive_dir)
    arbitrary = tmp_path / "pilot_20m"
    arbitrary.mkdir()
    (arbitrary / "tokenizer.json").write_bytes(b"arbitrary tokenizer")
    candidate = drive_dir / "tokenizers" / "representative_200m"
    candidate.mkdir(parents=True)
    (candidate / "tokenizer.json").write_bytes(b"candidate")
    (candidate / "special_tokens.json").write_text("{}\n", encoding="utf-8")
    candidate_sha = sha256_file(candidate / "tokenizer.json")
    sample_sha = json.loads(sample_manifest.read_text(encoding="utf-8"))[
        "manifest_sha256"
    ]
    (candidate / "tokenizer_report.json").write_text(
        json.dumps(
            {"fitting_manifest_sha256": sample_sha, "tokenizer_sha256": candidate_sha}
        ),
        encoding="utf-8",
    )

    def reject_evaluation(*_args, **_kwargs):
        raise AssertionError("wrong pilot must fail before evaluation")

    monkeypatch.setattr(
        prepare_telco_local, "evaluate_tokenizer_on_jsonl", reject_evaluation
    )

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_compare",
            *common,
            "--baseline-tokenizer",
            str(arbitrary),
            "--baseline-provenance",
            str(provenance),
            "--candidate-tokenizer",
            str(candidate),
            "--holdout-manifest",
            str(sample_manifest),
        ]
    )

    assert result != 0
    assert not (drive_dir / "comparison.json").exists()


def test_local_cli_comparison_rejects_stale_sample_provenance_before_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, manifest, baseline, candidate, _, _ = _comparison_cli_fixture(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["build_provenance"]["target_estimated_tokens"] = 199_999_999
    payload["build_provenance_sha256"] = sha256_json(payload["build_provenance"])
    payload.pop("manifest_sha256")
    payload["manifest_sha256"] = sha256_json(payload)
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    def reject_evaluation(*_args, **_kwargs):
        raise AssertionError("stale sample must fail before evaluation")

    monkeypatch.setattr(
        prepare_telco_local, "evaluate_tokenizer_on_jsonl", reject_evaluation
    )

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_compare",
            *common,
            "--baseline-tokenizer",
            str(baseline),
            "--candidate-tokenizer",
            str(candidate),
            "--holdout-manifest",
            str(manifest),
        ]
    )

    assert result != 0
    assert not (Path(common[-1]) / "comparison.json").exists()


def test_local_cli_comparison_refuses_symlinked_candidate_directory_before_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, manifest, baseline, candidate, _, _ = _comparison_cli_fixture(tmp_path)
    outside = tmp_path / "outside-candidate"
    outside.mkdir()
    for entry in candidate.iterdir():
        entry.unlink()
    candidate.rmdir()
    candidate.symlink_to(outside, target_is_directory=True)

    def reject_evaluation(*_args, **_kwargs):
        raise AssertionError("symlinked candidate must fail before evaluation")

    monkeypatch.setattr(
        prepare_telco_local, "evaluate_tokenizer_on_jsonl", reject_evaluation
    )

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_compare",
            *common,
            "--baseline-tokenizer",
            str(baseline),
            "--candidate-tokenizer",
            str(candidate),
            "--holdout-manifest",
            str(manifest),
        ]
    )

    assert result != 0
    assert list(outside.iterdir()) == []


def test_local_cli_comparison_rejects_swapped_tokenizer_sides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    def reject_evaluation(*_args, **_kwargs):
        raise AssertionError("test must not evaluate swapped tokenizer sides")

    monkeypatch.setattr(
        prepare_telco_local, "evaluate_tokenizer_on_jsonl", reject_evaluation
    )
    common, manifest, baseline, candidate, _, _ = _comparison_cli_fixture(tmp_path)

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_compare",
            *common,
            "--baseline-tokenizer",
            str(candidate),
            "--candidate-tokenizer",
            str(baseline),
            "--holdout-manifest",
            str(manifest),
        ]
    )

    assert result != 0


def test_local_cli_comparison_rejects_identical_tokenizer_fingerprints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, manifest, baseline, candidate, _, candidate_sha = (
        _comparison_cli_fixture(tmp_path)
    )
    manifest_sha256 = json.loads(manifest.read_text(encoding="utf-8"))[
        "manifest_sha256"
    ]

    def fake_evaluation(_tokenizer_dir, _inputs, _probes):
        return evaluation(
            overall_tokens=10_000,
            general_tokens=6_000,
            telecom_tokens=3_000,
            probe_p95=4.0,
            tokenizer_sha256=candidate_sha,
            sample_manifest_sha256=manifest_sha256,
        )

    monkeypatch.setattr(
        prepare_telco_local, "evaluate_tokenizer_on_jsonl", fake_evaluation
    )

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_compare",
            *common,
            "--baseline-tokenizer",
            str(baseline),
            "--candidate-tokenizer",
            str(candidate),
            "--holdout-manifest",
            str(manifest),
        ]
    )

    assert result != 0
    assert not (Path(common[-1]) / "comparison.json").exists()


def test_local_cli_comparison_preserves_configured_side_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, manifest, baseline, candidate, baseline_sha, candidate_sha = (
        _comparison_cli_fixture(tmp_path)
    )
    manifest_sha256 = json.loads(manifest.read_text(encoding="utf-8"))[
        "manifest_sha256"
    ]

    def fake_evaluation(tokenizer_dir, _inputs, _probes):
        is_candidate = Path(tokenizer_dir).resolve() == candidate.resolve()
        return evaluation(
            overall_tokens=9_850 if is_candidate else 10_000,
            general_tokens=6_030 if is_candidate else 6_000,
            telecom_tokens=2_900 if is_candidate else 3_000,
            probe_p95=4.02 if is_candidate else 4.0,
            tokenizer_sha256=candidate_sha if is_candidate else baseline_sha,
            sample_manifest_sha256=manifest_sha256,
        )

    monkeypatch.setattr(
        prepare_telco_local, "evaluate_tokenizer_on_jsonl", fake_evaluation
    )

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_compare",
            *common,
            "--baseline-tokenizer",
            str(baseline),
            "--candidate-tokenizer",
            str(candidate),
            "--holdout-manifest",
            str(manifest),
        ]
    )

    comparison = json.loads(
        (Path(common[-1]) / "comparison.json").read_text(encoding="utf-8")
    )
    assert result == 0
    assert comparison["labels"] == {
        "baseline": "pilot_20m",
        "candidate": "representative_200m",
    }
    assert comparison["fingerprints"]["baseline_tokenizer_sha256"] == baseline_sha
    assert comparison["fingerprints"]["candidate_tokenizer_sha256"] == candidate_sha


def test_local_cli_requires_explicit_selection_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, manifest, baseline, candidate, baseline_sha, candidate_sha = (
        _comparison_cli_fixture(tmp_path)
    )
    drive_dir = Path(common[-1])
    manifest_sha256 = json.loads(manifest.read_text(encoding="utf-8"))[
        "manifest_sha256"
    ]

    def fake_evaluation(tokenizer_dir, _inputs, _probes):
        is_candidate = Path(tokenizer_dir).resolve() == candidate.resolve()
        return evaluation(
            overall_tokens=9_850 if is_candidate else 10_000,
            general_tokens=6_030 if is_candidate else 6_000,
            telecom_tokens=2_900 if is_candidate else 3_000,
            probe_p95=4.02 if is_candidate else 4.0,
            tokenizer_sha256=candidate_sha if is_candidate else baseline_sha,
            sample_manifest_sha256=manifest_sha256,
        )

    monkeypatch.setattr(
        prepare_telco_local, "evaluate_tokenizer_on_jsonl", fake_evaluation
    )
    assert (
        prepare_telco_local.main(
            [
                "--stage",
                "tokenizer_compare",
                *common,
                "--baseline-tokenizer",
                str(baseline),
                "--candidate-tokenizer",
                str(candidate),
                "--holdout-manifest",
                str(manifest),
            ]
        )
        == 0
    )
    comparison_path = drive_dir / "comparison.json"
    arguments = [
        "--stage",
        "tokenizer_select",
        *common,
        "--comparison",
        str(comparison_path),
        "--winner",
        "representative_200m",
    ]

    assert prepare_telco_local.main(arguments) != 0
    assert not (drive_dir / "tokenizer_selection.json").exists()

    assert prepare_telco_local.main([*arguments, "--approve"]) == 0
    selection = json.loads(
        (drive_dir / "tokenizer_selection.json").read_text(encoding="utf-8")
    )
    assert selection["winner"] == "representative_200m"
    assert selection["approved"] is True


def test_local_cli_selection_rejects_noncanonical_comparison_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, _, _, _, canonical = _create_canonical_comparison(tmp_path, monkeypatch)
    copied = tmp_path / "reviewed-comparison.json"
    copied.write_bytes(canonical.read_bytes())
    drive_dir = Path(common[-1])

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_select",
            *common,
            "--comparison",
            str(copied),
            "--winner",
            "representative_200m",
            "--approve",
        ]
    )

    assert result != 0
    assert not (drive_dir / "tokenizer_selection.json").exists()


@pytest.mark.parametrize("mutation", ("stale_recipe", "wrong_labels"))
def test_local_cli_selection_rejects_stale_recipe_or_labels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
):
    from scripts import prepare_telco_local

    common, _, _, _, comparison_path = _create_canonical_comparison(
        tmp_path, monkeypatch
    )
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    if mutation == "stale_recipe":
        comparison["workflow_evidence"]["candidate_recipe_sha256"] = "0" * 64
    else:
        comparison["labels"]["candidate"] = "foreign_candidate"
    comparison.pop("comparison_sha256")
    comparison["comparison_sha256"] = sha256_json(comparison)
    comparison_path.write_text(json.dumps(comparison), encoding="utf-8")
    drive_dir = Path(common[-1])

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_select",
            *common,
            "--comparison",
            str(comparison_path),
            "--winner",
            "representative_200m",
            "--approve",
        ]
    )

    assert result != 0
    assert not (drive_dir / "tokenizer_selection.json").exists()


def test_local_cli_selection_rejects_tokenizer_mutation_after_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, _, _, candidate, comparison_path = _create_canonical_comparison(
        tmp_path, monkeypatch
    )
    (candidate / "tokenizer.json").write_bytes(b"mutated after comparison")
    drive_dir = Path(common[-1])

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_select",
            *common,
            "--comparison",
            str(comparison_path),
            "--winner",
            "representative_200m",
            "--approve",
        ]
    )

    assert result != 0
    assert not (drive_dir / "tokenizer_selection.json").exists()


def test_local_cli_selection_rejects_rebound_stale_candidate_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, _, _, candidate, comparison_path = _create_canonical_comparison(
        tmp_path, monkeypatch
    )
    candidate_report_path = candidate / "tokenizer_report.json"
    candidate_report = json.loads(
        candidate_report_path.read_text(encoding="utf-8")
    )
    candidate_report["fitting_manifest_sha256"] = "0" * 64
    candidate_report_path.write_text(json.dumps(candidate_report), encoding="utf-8")
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    comparison["workflow_evidence"]["candidate_report_sha256"] = sha256_json(
        candidate_report
    )
    comparison.pop("comparison_sha256")
    comparison["comparison_sha256"] = sha256_json(comparison)
    comparison_path.write_text(json.dumps(comparison), encoding="utf-8")
    drive_dir = Path(common[-1])

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_select",
            *common,
            "--comparison",
            str(comparison_path),
            "--winner",
            "representative_200m",
            "--approve",
        ]
    )

    assert result != 0
    assert not (drive_dir / "tokenizer_selection.json").exists()


def test_local_cli_selection_refuses_symlinked_selection_file_without_outside_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, _, _, _, comparison_path = _create_canonical_comparison(
        tmp_path, monkeypatch
    )
    drive_dir = Path(common[-1])
    outside = tmp_path / "outside-selection.json"
    outside.write_text("preserve\n", encoding="utf-8")
    (drive_dir / "tokenizer_selection.json").symlink_to(outside)

    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_select",
            *common,
            "--comparison",
            str(comparison_path),
            "--winner",
            "representative_200m",
            "--approve",
        ]
    )

    assert result != 0
    assert outside.read_text(encoding="utf-8") == "preserve\n"


def _selected_local_cli_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    winner: str = "representative_200m",
) -> tuple[list[str], Path, Path, Path, str]:
    from scripts import prepare_telco_local

    common, _, baseline, candidate, comparison = _create_canonical_comparison(
        tmp_path, monkeypatch
    )
    result = prepare_telco_local.main(
        [
            "--stage",
            "tokenizer_select",
            *common,
            "--comparison",
            str(comparison),
            "--winner",
            winner,
            "--approve",
        ]
    )
    assert result == 0
    selected = baseline if winner == "pilot_20m" else candidate
    selected_sha256 = sha256_file(selected / "tokenizer.json")
    (selected / "special_tokens.json").write_text(
        json.dumps({"tokenizer_sha256": selected_sha256}), encoding="utf-8"
    )
    return common, Path(common[-3]), Path(common[-1]), selected, selected_sha256


def test_local_cli_source_has_no_pretraining_import_or_call():
    source = Path("scripts/prepare_telco_local.py").read_text(encoding="utf-8")
    tree = __import__("ast").parse(source)
    imported = {
        alias.name
        for node in __import__("ast").walk(tree)
        if isinstance(node, (__import__("ast").Import, __import__("ast").ImportFrom))
        for alias in node.names
    }
    imported_modules = {
        node.module
        for node in __import__("ast").walk(tree)
        if isinstance(node, __import__("ast").ImportFrom) and node.module
    }

    assert all("pretrain" not in name and "training" not in name for name in imported)
    assert "matgpt.preflight" not in imported_modules
    assert "run_pretraining" not in source


def test_full_calibration_uses_100m_stop_and_writes_complete_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from matgpt.data.local_corpus import LocalCorpusResult
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch
    )
    observed: dict[str, object] = {}

    def fake_provider_preflight(self):
        observed["provider_root"] = self.destination_root
        return {"fsynced_partial_rename": True, "hard_links_required": False}

    def fake_build(request, **kwargs):
        observed["request"] = request
        observed["stop"] = kwargs.get("stop_after_quota_tokens")
        identity = prepare_telco_local._expected_build_identity(request)
        _write_core_calibration_report(
            request.destination_root,
            identity=identity.content_sha256,
            tokens=100_000_007,
        )
        return LocalCorpusResult(
            "calibration_complete", identity.content_sha256, 100_000_007, None
        )

    monkeypatch.setattr(
        prepare_telco_local.DrivePublisher,
        "preflight_destination_provider",
        fake_provider_preflight,
    )
    monkeypatch.setattr(prepare_telco_local, "build_local_corpus", fake_build)

    result = prepare_telco_local.main(
        [
            "--stage",
            "full_calibration",
            *common,
            "--stop-after-quota-tokens",
            "100000000",
        ]
    )

    request = observed["request"]
    assert result == 0
    assert observed["stop"] == 100_000_000
    assert selected_sha256 in request.destination_root.parts
    assert [plan["stage"] for plan in request.plans] == ["main", "cooldown"]
    report_path = prepare_telco_local._calibration_operator_path(
        drive_dir, selected_sha256
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["actual_committed_quota_tokens"] == 100_000_007
    assert report["build_identity_sha256"] == (
        prepare_telco_local._expected_build_identity(request).content_sha256
    )
    assert report["provider_preflight"]["fsynced_partial_rename"] is True
    assert report["drive_verification_state"] == "verified"
    core_path = request.destination_root / "calibration_report.json"
    assert report["core_calibration_report"] == {
        "path": "calibration_report.json",
        "size": core_path.stat().st_size,
        "sha256": sha256_file(core_path),
        "calibration_report_sha256": json.loads(
            core_path.read_text(encoding="utf-8")
        )["calibration_report_sha256"],
    }
    assert report["measurement_methods"] == {
        "source_network_wait": "provider_load_and_next_wall_time",
        "encode": "tokenizer_encode_batch_wall_time",
        "contamination": "quality_filter_accept_wall_time",
        "publication": "publisher_publish_wall_time",
    }
    for metric in (
        "wall_time_seconds",
        "process_cpu_time_seconds",
        "peak_rss_bytes",
        "source_network_wait_seconds",
        "encode_tokens_per_second",
        "contamination_documents_per_second",
        "publication_bytes_per_second",
        "mean_overall_tokens_per_second",
        "rolling_overall_tokens_per_second",
        "projected_12b_wall_time_seconds",
    ):
        assert isinstance(report[metric], (int, float))
        assert report[metric] >= 0


def test_full_calibration_refuses_to_report_less_than_100m_committed_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from matgpt.data.local_corpus import LocalCorpusResult
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch
    )
    monkeypatch.setattr(
        prepare_telco_local.DrivePublisher,
        "preflight_destination_provider",
        lambda _self: {
            "fsynced_partial_rename": True,
            "hard_links_required": False,
        },
    )
    monkeypatch.setattr(
        prepare_telco_local,
        "build_local_corpus",
        lambda *_args, **_kwargs: LocalCorpusResult(
            "stopped_cleanly", "a" * 64, 99_999_999, None
        ),
    )

    result = prepare_telco_local.main(
        ["--stage", "full_calibration", *common]
    )

    assert result != 0
    assert not prepare_telco_local._calibration_operator_path(
        drive_dir, selected_sha256
    ).exists()


def test_full_calibration_rejects_changed_builder_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from matgpt.data.local_corpus import LocalCorpusResult
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch
    )
    monkeypatch.setattr(
        prepare_telco_local.DrivePublisher,
        "preflight_destination_provider",
        lambda _self: {
            "fsynced_partial_rename": True,
            "hard_links_required": False,
        },
    )
    monkeypatch.setattr(
        prepare_telco_local,
        "build_local_corpus",
        lambda *_args, **_kwargs: LocalCorpusResult(
            "calibration_complete", "f" * 64, 100_000_001, None
        ),
    )

    result = prepare_telco_local.main(
        ["--stage", "full_calibration", *common]
    )

    assert result != 0
    assert not prepare_telco_local._calibration_operator_path(
        drive_dir, selected_sha256
    ).exists()


def test_full_calibration_reports_storage_pressure_as_a_clean_cli_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from matgpt.data.local_publish import StoragePressure
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch
    )
    monkeypatch.setattr(
        prepare_telco_local.DrivePublisher,
        "preflight_destination_provider",
        lambda _self: {
            "fsynced_partial_rename": True,
            "hard_links_required": False,
        },
    )
    monkeypatch.setattr(
        prepare_telco_local,
        "build_local_corpus",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            StoragePressure("working-set cap reached")
        ),
    )

    assert prepare_telco_local.main(["--stage", "full_calibration", *common]) == 2
    assert not prepare_telco_local._calibration_operator_path(
        drive_dir, selected_sha256
    ).exists()


def _write_core_calibration_report(
    root: Path,
    *,
    identity: str = "a" * 64,
    status: str = "calibration_complete",
    tokens: int = 100_000_000,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    metrics = {
        "version": 1,
        "wall_time_seconds": 100.0,
        "process_cpu_time_seconds": 50.0,
        "peak_rss_bytes": 1_000,
        "source_network": {
            "method": "provider_load_and_next_wall_time",
            "wall_time_seconds": 10.0,
            "operations": 10,
            "rows": 9,
        },
        "encode": {
            "method": "tokenizer_encode_batch_wall_time",
            "wall_time_seconds": 20.0,
            "batches": 5,
            "documents": 50,
            "tokens": tokens,
        },
        "contamination": {
            "method": "quality_filter_accept_wall_time",
            "wall_time_seconds": 5.0,
            "documents": 50,
        },
        "publication": {
            "method": "publisher_publish_wall_time",
            "wall_time_seconds": 5.0,
            "artifacts": 4,
            "bytes": 2_000,
        },
    }
    payload: dict[str, object] = {
        "version": 2,
        "status": status,
        "build_identity_sha256": identity,
        "accepted_quota_tokens": tokens,
        "committed_units": 1,
        "elapsed_seconds": 100.0,
        "peak_rss_bytes": 1_000,
        "metrics": metrics,
        "throughput": {
            "encode_tokens_per_second": tokens / 20.0,
            "contamination_documents_per_second": 10.0,
            "publication_bytes_per_second": 400.0,
            "mean_overall_tokens_per_second": tokens / 100.0,
            "rolling_overall_tokens_per_second": tokens / 100.0,
        },
    }
    payload["calibration_report_sha256"] = sha256_json(payload)
    path = root / "calibration_report.json"
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _calibration_report_payload(
    core_report_path: Path,
    *,
    identity: str = "a" * 64,
    projected_seconds: float = 47 * 3600,
    storage_pressure: bool = False,
) -> dict[str, object]:
    core = json.loads(core_report_path.read_text(encoding="utf-8"))
    core["throughput"]["rolling_overall_tokens_per_second"] = (
        12_000_000_000 / projected_seconds
    )
    core.pop("calibration_report_sha256")
    core["calibration_report_sha256"] = sha256_json(core)
    core_report_path.write_text(
        json.dumps(core, sort_keys=True) + "\n", encoding="utf-8"
    )
    metrics = core["metrics"]
    throughput = core["throughput"]
    payload: dict[str, object] = {
        "version": 2,
        "status": "calibration_complete",
        "build_identity_sha256": identity,
        "actual_committed_quota_tokens": core["accepted_quota_tokens"],
        "wall_time_seconds": metrics["wall_time_seconds"],
        "process_cpu_time_seconds": metrics["process_cpu_time_seconds"],
        "peak_rss_bytes": metrics["peak_rss_bytes"],
        "source_network_wait_seconds": metrics["source_network"][
            "wall_time_seconds"
        ],
        "encode_tokens_per_second": throughput["encode_tokens_per_second"],
        "contamination_documents_per_second": throughput[
            "contamination_documents_per_second"
        ],
        "publication_bytes_per_second": throughput[
            "publication_bytes_per_second"
        ],
        "mean_overall_tokens_per_second": throughput[
            "mean_overall_tokens_per_second"
        ],
        "rolling_overall_tokens_per_second": throughput[
            "rolling_overall_tokens_per_second"
        ],
        "projected_12b_wall_time_seconds": projected_seconds,
        "unrecovered_storage_pressure": storage_pressure,
        "drive_verification_state": "verified",
        "measurement_methods": {
            "source_network_wait": metrics["source_network"]["method"],
            "encode": metrics["encode"]["method"],
            "contamination": metrics["contamination"]["method"],
            "publication": metrics["publication"]["method"],
        },
        "core_calibration_report": {
            "path": "calibration_report.json",
            "size": core_report_path.stat().st_size,
            "sha256": sha256_file(core_report_path),
            "calibration_report_sha256": core["calibration_report_sha256"],
        },
    }
    payload["operator_report_sha256"] = sha256_json(payload)
    return payload


def _full_request_for_cli(prepare_telco_local, common: list[str]):
    args = prepare_telco_local.build_parser().parse_args(
        ["--stage", "status", *common]
    )
    work_dir, drive_dir = prepare_telco_local._resolved_roots(
        args.work_dir, args.drive_dir
    )
    registry = prepare_telco_local.load_source_registry(Path(args.sources))
    mixture = prepare_telco_local.load_mixture_config(Path(args.mixture))
    candidate_config = prepare_telco_local.load_tokenizer_candidate_config(
        Path(args.candidate_config)
    )
    model_config = prepare_telco_local.load_config(Path(args.model_config))
    _, tokenizer_dir, tokenizer_sha256, _, _ = (
        prepare_telco_local._selected_tokenizer_evidence(
            drive_dir=drive_dir,
            work_dir=work_dir,
            registry=registry,
            mixture=mixture,
            candidate_config=candidate_config,
            model_config=model_config,
        )
    )
    request = prepare_telco_local._corpus_request(
        kind="full",
        work_dir=work_dir,
        drive_dir=drive_dir,
        registry=registry,
        mixture=mixture,
        candidate_config=candidate_config,
        model_config=model_config,
        tokenizer_dir=tokenizer_dir,
        tokenizer_sha256=tokenizer_sha256,
    )
    return request, prepare_telco_local._expected_build_identity(request), drive_dir, tokenizer_sha256


@pytest.mark.parametrize(
    ("accepted", "override", "reason", "match"),
    [
        (False, False, "", "--accept-calibration"),
        (True, False, "", "48 hours"),
        (True, True, "", "--override-reason"),
    ],
)
def test_full_resume_calibration_guards_fail_closed(
    tmp_path: Path, accepted: bool, override: bool, reason: str, match: str
):
    from scripts import prepare_telco_local

    core_path = _write_core_calibration_report(tmp_path)

    with pytest.raises(ValueError, match=match):
        prepare_telco_local._require_accepted_calibration(
            _calibration_report_payload(
                core_path, projected_seconds=49 * 3600
            ),
            expected_build_identity="a" * 64,
            core_report_path=core_path,
            core_managed_root=tmp_path,
            accept_calibration=accepted,
            override_guard=override,
            override_reason=reason,
        )


def test_full_resume_storage_guard_requires_explicit_reasoned_override(
    tmp_path: Path,
):
    from scripts import prepare_telco_local

    core_path = _write_core_calibration_report(tmp_path)
    report = _calibration_report_payload(core_path, storage_pressure=True)
    with pytest.raises(ValueError, match="storage pressure"):
        prepare_telco_local._require_accepted_calibration(
            report,
            expected_build_identity="a" * 64,
            core_report_path=core_path,
            core_managed_root=tmp_path,
            accept_calibration=True,
            override_guard=False,
            override_reason="",
        )

    authorization = prepare_telco_local._require_accepted_calibration(
        report,
        expected_build_identity="a" * 64,
        core_report_path=core_path,
        core_managed_root=tmp_path,
        accept_calibration=True,
        override_guard=True,
        override_reason="Reviewed migration to a larger local volume",
    )

    assert authorization["override_reason"] == (
        "Reviewed migration to a larger local volume"
    )
    assert authorization["build_identity_sha256"] == "a" * 64


def test_full_resume_rejects_foreign_calibration_identity(tmp_path: Path):
    from scripts import prepare_telco_local

    core_path = _write_core_calibration_report(tmp_path)

    with pytest.raises(ValueError, match="build identity"):
        prepare_telco_local._require_accepted_calibration(
            _calibration_report_payload(core_path, identity="b" * 64),
            expected_build_identity="a" * 64,
            core_report_path=core_path,
            core_managed_root=tmp_path,
            accept_calibration=True,
            override_guard=True,
            override_reason="Identity mismatch must never be overridable",
        )


def test_full_resume_rejects_invalid_core_before_provider_or_builder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, _, _, _, _ = _selected_local_cli_fixture(tmp_path, monkeypatch)
    request, identity, drive_dir, tokenizer_sha256 = _full_request_for_cli(
        prepare_telco_local, common
    )
    core_path = _write_core_calibration_report(
        request.destination_root,
        identity=identity.content_sha256,
        status="stopped_cleanly",
    )
    operator = _calibration_report_payload(
        core_path, identity=identity.content_sha256
    )
    operator_path = prepare_telco_local._calibration_operator_path(
        drive_dir, tokenizer_sha256
    )
    operator_path.parent.mkdir(parents=True)
    operator_path.write_text(
        json.dumps(operator, sort_keys=True) + "\n", encoding="utf-8"
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("invalid core evidence must fail before provider/builder")

    monkeypatch.setattr(
        prepare_telco_local.DrivePublisher,
        "preflight_destination_provider",
        forbidden,
    )
    monkeypatch.setattr(prepare_telco_local, "build_local_corpus", forbidden)

    assert prepare_telco_local.main(
        ["--stage", "full_resume", *common, "--accept-calibration"]
    ) == 2


def test_status_reports_missing_core_binding_as_false_without_operational_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, _, _, _, _ = _selected_local_cli_fixture(tmp_path, monkeypatch)
    request, identity, drive_dir, tokenizer_sha256 = _full_request_for_cli(
        prepare_telco_local, common
    )
    core_path = _write_core_calibration_report(
        request.destination_root, identity=identity.content_sha256
    )
    operator = _calibration_report_payload(
        core_path, identity=identity.content_sha256
    )
    operator_path = prepare_telco_local._calibration_operator_path(
        drive_dir, tokenizer_sha256
    )
    operator_path.parent.mkdir(parents=True)
    operator_path.write_text(
        json.dumps(operator, sort_keys=True) + "\n", encoding="utf-8"
    )
    core_path.unlink()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("status must not call source/provider/builder")

    monkeypatch.setattr(prepare_telco_local, "build_local_corpus", forbidden)
    monkeypatch.setattr(prepare_telco_local, "_load_dataset_function", forbidden)
    monkeypatch.setattr(
        prepare_telco_local.DrivePublisher,
        "preflight_destination_provider",
        forbidden,
    )

    status = prepare_telco_local.run(
        prepare_telco_local.build_parser().parse_args(["--stage", "status", *common])
    )
    assert status["calibration_gate_satisfied"] is False
    assert "core" in status["calibration_gate_reason"].lower()


@pytest.mark.parametrize("kind", ("oversized", "deep"))
def test_full_resume_and_status_bound_hostile_operator_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
):
    from scripts import prepare_telco_local

    common, _, _, _, _ = _selected_local_cli_fixture(tmp_path, monkeypatch)
    request, _, drive_dir, tokenizer_sha256 = _full_request_for_cli(
        prepare_telco_local, common
    )
    path = prepare_telco_local._calibration_operator_path(drive_dir, tokenizer_sha256)
    path.parent.mkdir(parents=True)
    if kind == "oversized":
        path.write_bytes(b'{"padding":"' + b"x" * (4 * 1024 * 1024) + b'"}')
    else:
        value: object = "leaf"
        for _ in range(80):
            value = {"nested": value}
        path.write_text(json.dumps(value), encoding="utf-8")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("hostile evidence must not trigger operational reads")

    monkeypatch.setattr(prepare_telco_local, "build_local_corpus", forbidden)
    monkeypatch.setattr(prepare_telco_local, "_load_dataset_function", forbidden)
    monkeypatch.setattr(
        prepare_telco_local.DrivePublisher,
        "preflight_destination_provider",
        forbidden,
    )
    assert prepare_telco_local.main(
        ["--stage", "full_resume", *common, "--accept-calibration"]
    ) == 2
    status = prepare_telco_local.run(
        prepare_telco_local.build_parser().parse_args(["--stage", "status", *common])
    )
    assert status["calibration_gate_satisfied"] is False
    expected_reason = "size" if kind == "oversized" else "nesting"
    assert expected_reason in status["calibration_gate_reason"].lower()
    assert not (request.destination_root / "manifest.json").exists()


def test_pilot_status_bounds_recursive_evaluation_json_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch, winner="pilot_20m"
    )
    recipe_root, _ = _write_valid_preserved_pilot_evidence(
        drive_dir, selected_sha256
    )
    assert prepare_telco_local.main(["--stage", "pilot_refresh", *common]) == 0
    evaluation = recipe_root / "runs/pilot/evaluation"
    template = (evaluation / "current/checkpoint_00_latest_base.json").read_bytes()
    for index in range(256):
        (evaluation / f"extra_{index:03d}.json").write_bytes(template)
    status = prepare_telco_local.run(
        prepare_telco_local.build_parser().parse_args(["--stage", "status", *common])
    )
    assert status["pilot_refresh_gate_satisfied"] is False
    assert "maximum json file count" in status["pilot_refresh_gate_reason"].lower()


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("actual_committed_quota_tokens", None, "committed tokens"),
        ("projected_12b_wall_time_seconds", float("nan"), "projection"),
        ("projected_12b_wall_time_seconds", 10**1000, "projection"),
    ],
)
def test_full_resume_rejects_malformed_calibration_metrics(
    tmp_path: Path, field: str, value: object, match: str
):
    from scripts import prepare_telco_local

    core_path = _write_core_calibration_report(tmp_path)
    report = _calibration_report_payload(core_path)
    report[field] = value
    report.pop("operator_report_sha256")
    report["operator_report_sha256"] = sha256_json(report)

    with pytest.raises(ValueError, match=match):
        prepare_telco_local._require_accepted_calibration(
            report,
            expected_build_identity="a" * 64,
            core_report_path=core_path,
            core_managed_root=tmp_path,
            accept_calibration=True,
            override_guard=False,
            override_reason="",
        )


def test_status_never_calls_corpus_builder_or_source_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, _, _, _, _ = _selected_local_cli_fixture(tmp_path, monkeypatch)

    def reject_source_read(*_args, **_kwargs):
        raise AssertionError("status must not call a provider or corpus builder")

    monkeypatch.setattr(prepare_telco_local, "build_local_corpus", reject_source_read)
    monkeypatch.setattr(
        prepare_telco_local, "_load_dataset_function", reject_source_read
    )

    assert prepare_telco_local.main(["--stage", "status", *common]) == 0


def test_candidate_pilot_refresh_rebuilds_in_fingerprinted_namespace_without_gates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from matgpt.data.local_corpus import LocalCorpusResult
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch
    )
    observed: dict[str, object] = {}

    monkeypatch.setattr(
        prepare_telco_local.DrivePublisher,
        "preflight_destination_provider",
        lambda _self: {
            "fsynced_partial_rename": True,
            "hard_links_required": False,
        },
    )

    def fake_build(request, **_kwargs):
        observed["request"] = request
        identity = prepare_telco_local._expected_build_identity(request)
        request.destination_root.mkdir(parents=True, exist_ok=True)
        manifest = {
            "version": 2,
            "status": "complete",
            "complete": True,
            "build_identity_sha256": identity.content_sha256,
            "quota_counting": {
                "method": "tokenizer_exact_one_pass",
                "tokenizer_sha256": selected_sha256,
            },
        }
        manifest["manifest_sha256"] = sha256_json(manifest)
        (request.destination_root / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        return LocalCorpusResult(
            "complete", identity.content_sha256, 20_000_000, {"complete": True}
        )

    monkeypatch.setattr(prepare_telco_local, "build_local_corpus", fake_build)

    result = prepare_telco_local.main(["--stage", "pilot_refresh", *common])

    request = observed["request"]
    report = json.loads(
        prepare_telco_local._pilot_refresh_path(
            drive_dir, selected_sha256
        ).read_text(encoding="utf-8")
    )
    assert result == 0
    assert selected_sha256 in request.destination_root.parts
    assert [plan["stage"] for plan in request.plans] == ["pilot"]
    assert report["action"] == "rebuild"
    assert report["status"] == "ready_for_colab"
    assert report["refreshed_pilot_gates_passed"] is False
    assert report["pending_colab_gates"] == ["smoke", "pilot", "evaluation"]

    status = prepare_telco_local.run(
        prepare_telco_local.build_parser().parse_args(["--stage", "status", *common])
    )
    assert status["pilot_refresh_gate_satisfied"] is False
    assert status["full_completion_gate_satisfied"] is False

    _write_pilot_gate_evidence(
        prepare_telco_local._operator_evidence_root(
            drive_dir, selected_sha256
        ) / "pilot/colab",
        tokenizer_sha256=selected_sha256,
        build_identity_sha256=str(report["build_identity_sha256"]),
    )
    passed_status = prepare_telco_local.run(
        prepare_telco_local.build_parser().parse_args(["--stage", "status", *common])
    )
    assert passed_status["pilot_refresh_gate_satisfied"] is True


def test_pilot_reuse_rejects_failed_evaluation_with_nested_matching_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch, winner="pilot_20m"
    )
    recipe_root, build_identity_sha256 = _write_valid_preserved_pilot_evidence(
        drive_dir, selected_sha256
    )
    evaluation_path = recipe_root / "runs/pilot/evaluation/current/checkpoint_00_latest_base.json"
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    evaluation.update(
        {
            "status": "fail",
            "gate_passed": False,
            "unrelated": {"tokenizer_sha256": selected_sha256},
            "build_identity_sha256": build_identity_sha256,
        }
    )
    evaluation_path.write_text(json.dumps(evaluation), encoding="utf-8")

    assert prepare_telco_local.main(["--stage", "pilot_refresh", *common]) == 2
    assert not prepare_telco_local._pilot_refresh_path(
        drive_dir, selected_sha256
    ).exists()


def test_pilot_reuse_accepts_current_repo_legacy_producer_schemas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch, winner="pilot_20m"
    )
    recipe_root, _ = _write_valid_preserved_pilot_evidence(
        drive_dir, selected_sha256
    )
    evidence = recipe_root / "evidence/pilot"
    assert prepare_telco_local.main(["--stage", "pilot_refresh", *common]) == 0
    preflight_path = evidence / "preflight.json"
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    preflight["checks"][0]["details"]["config_sha256"] = "0" * 64
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")
    assert prepare_telco_local.main(["--stage", "pilot_refresh", *common]) == 2


@pytest.mark.parametrize(
    "mutation",
    (
        "pilot_quota",
        "pilot_documents",
        "pilot_item_requested",
        "pilot_item_quota",
        "pilot_item_documents",
        "validation_quota",
        "validation_documents",
        "validation_items",
        "split_stats",
        "append_eos",
    ),
)
def test_pilot_reuse_rejects_inconsistent_producer_quota_and_eos_accounting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
):
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch, winner="pilot_20m"
    )
    recipe_root, _ = _write_valid_preserved_pilot_evidence(
        drive_dir, selected_sha256
    )
    manifest_path = recipe_root / "corpora/pilot/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pilot = manifest["stages"]["pilot"]
    validation = manifest["validation"]
    if mutation == "pilot_quota":
        pilot["quota_tokens"] += 1
    elif mutation == "pilot_documents":
        pilot["documents"] += 1
    elif mutation == "pilot_item_requested":
        pilot["items"]["canonical-source"]["requested_tokens"] -= 1
    elif mutation == "pilot_item_quota":
        pilot["items"]["canonical-source"]["quota_tokens"] -= 1
    elif mutation == "pilot_item_documents":
        pilot["items"]["canonical-source"]["documents"] += 1
    elif mutation == "validation_quota":
        validation["quota_tokens"] += 1
    elif mutation == "validation_documents":
        validation["documents"] += 1
    elif mutation == "validation_items":
        validation["items"]["canonical-source"] += 1
    elif mutation == "split_stats":
        manifest["split_stats"]["pilot"] = dict(pilot, quota_tokens=20_000_004)
    else:
        metadata_path = recipe_root / "prepared/pilot/shards/pilot_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["append_eos"] = False
        metadata.pop("metadata_sha256")
        metadata["metadata_sha256"] = sha256_json(metadata)
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    if mutation != "append_eos":
        manifest.pop("manifest_sha256")
        manifest["manifest_sha256"] = sha256_json(manifest)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert prepare_telco_local.main(["--stage", "pilot_refresh", *common]) == 2


@pytest.mark.parametrize(
    "mutation",
    ("claimed_twenty_million_one_token", "swapped_splits", "duplicate_shard",
     "missing_shard", "traversal", "bad_dtype", "bad_byte_size", "bad_sha",
     "totals_mismatch", "token_outside_vocab"),
)
def test_pilot_reuse_rejects_false_exact_shard_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
):
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch, winner="pilot_20m"
    )
    recipe_root, _ = _write_valid_preserved_pilot_evidence(
        drive_dir, selected_sha256
    )
    shard_root = recipe_root / "prepared/pilot/shards"
    pilot_path = shard_root / "pilot_metadata.json"
    validation_path = shard_root / "validation_metadata.json"
    pilot = json.loads(pilot_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if mutation == "claimed_twenty_million_one_token":
        shard = pilot["shards"][0]
        shard["num_tokens"] = 1
        shard["byte_size"] = 2
        one_token = shard_root / shard["path"]
        one_token.write_bytes(b"\0\0")
        shard["sha256"] = sha256_file(one_token)
        # This is the historical exploit: the headline still claims 20M.
        pilot["total_tokens"] = 20_000_000
    elif mutation == "swapped_splits":
        pilot["split"], validation["split"] = validation["split"], pilot["split"]
    elif mutation == "duplicate_shard":
        pilot["shards"].append(dict(pilot["shards"][0]))
        pilot["total_tokens"] = 40_000_000
    elif mutation == "missing_shard":
        (shard_root / pilot["shards"][0]["path"]).unlink()
    elif mutation == "traversal":
        pilot["shards"][0]["path"] = "../pilot_00000.bin"
    elif mutation == "bad_dtype":
        pilot["dtype"] = "uint32"
    elif mutation == "bad_byte_size":
        pilot["shards"][0]["byte_size"] -= 2
    elif mutation == "bad_sha":
        pilot["shards"][0]["sha256"] = "0" * 64
    elif mutation == "totals_mismatch":
        pilot["total_tokens"] -= 1
    else:
        shard_path = shard_root / pilot["shards"][0]["path"]
        with shard_path.open("r+b") as handle:
            handle.write(b"\0\x80")
        pilot["shards"][0]["sha256"] = sha256_file(shard_path)
    for path, payload in ((pilot_path, pilot), (validation_path, validation)):
        payload.pop("metadata_sha256")
        payload["metadata_sha256"] = sha256_json(payload)
        path.write_text(json.dumps(payload), encoding="utf-8")

    assert prepare_telco_local.main(["--stage", "pilot_refresh", *common]) == 2


def test_pilot_reuse_rejects_single_check_preflight_toy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch, winner="pilot_20m"
    )
    recipe_root, _ = _write_valid_preserved_pilot_evidence(
        drive_dir, selected_sha256
    )
    evidence = recipe_root / "evidence/pilot/preflight.json"
    evidence.write_text(json.dumps({
        "status": "pass",
        "checks": [{"name": "config", "status": "pass", "message": "ok",
                    "details": {"config_sha256": "0" * 64}}],
    }), encoding="utf-8")

    assert prepare_telco_local.main(["--stage", "pilot_refresh", *common]) == 2


@pytest.mark.parametrize("mutation", ("missing", "duplicate", "unknown", "failed"))
def test_pilot_reuse_rejects_non_authoritative_full_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
):
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch, winner="pilot_20m"
    )
    recipe_root, _ = _write_valid_preserved_pilot_evidence(drive_dir, selected_sha256)
    path = recipe_root / "evidence/pilot/preflight.json"
    payload = json.loads(path.read_text())
    if mutation == "missing":
        payload["checks"].pop()
    elif mutation == "duplicate":
        payload["checks"][-1] = dict(payload["checks"][0])
    elif mutation == "unknown":
        payload["checks"][-1]["name"] = "unknown"
    else:
        payload["checks"][3]["status"] = "fail"
        payload["status"] = "fail"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert prepare_telco_local.main(["--stage", "pilot_refresh", *common]) == 2


@pytest.mark.parametrize(
    "mutation",
    ("foreign_same_basename", "empty_task_row", "invalid_task_outcome",
     "missing_comparison_checkpoint", "arbitrary_scored_review"),
)
def test_pilot_reuse_rejects_unbound_or_incomplete_evaluation_roles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
):
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch, winner="pilot_20m"
    )
    recipe_root, _ = _write_valid_preserved_pilot_evidence(
        drive_dir, selected_sha256
    )
    if mutation == "foreign_same_basename":
        path = recipe_root / "evidence/pilot/smoke_resume_verified.json"
        payload = json.loads(path.read_text())
        payload["checkpoint"] = "/content/drive/MyDrive/foreign/checkpoints/latest.pt"
    elif mutation == "empty_task_row":
        path = recipe_root / "runs/pilot/evaluation/current/checkpoint_00_latest_open_telco.json"
        payload = {"tasks": [{}]}
    elif mutation == "invalid_task_outcome":
        path = recipe_root / "runs/pilot/evaluation/current/checkpoint_00_latest_open_telco.json"
        payload = json.loads(path.read_text())
        payload["tasks"][0]["examples"][0]["correct"] = False
    elif mutation == "missing_comparison_checkpoint":
        path = recipe_root / "runs/pilot/evaluation/current/checkpoint_comparison/comparison_summary.json"
        payload = json.loads(path.read_text())
        payload["checkpoints"]["checkpoint_00_latest"]["path"] = (
            "/content/drive/MyDrive/foreign/checkpoints/latest.pt"
        )
    else:
        path = recipe_root / "runs/pilot/evaluation/current/checkpoint_comparison/llm_judge/results/scored_llm.json"
        payload = {"reviewer": "llm", "review_count": 1, "judgments": [],
                   "summary": {}}
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert prepare_telco_local.main(["--stage", "pilot_refresh", *common]) == 2


@pytest.mark.parametrize(
    "role",
    ("smoke", "pilot", "base", "tasks", "comparison", "comparison_detail"),
)
def test_pilot_reuse_rejects_path_only_checkpoint_provenance_from_every_role(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str
):
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch, winner="pilot_20m"
    )
    recipe_root, _ = _write_valid_preserved_pilot_evidence(
        drive_dir, selected_sha256
    )
    paths = {
        "smoke": recipe_root / "evidence/pilot/smoke_resume_verified.json",
        "pilot": recipe_root / "evidence/pilot/pilot_complete.json",
        "base": recipe_root / "runs/pilot/evaluation/current/checkpoint_00_latest_base.json",
        "tasks": recipe_root / "runs/pilot/evaluation/current/checkpoint_00_latest_open_telco.json",
        "comparison": recipe_root / "runs/pilot/evaluation/current/checkpoint_comparison/comparison_summary.json",
        "comparison_detail": recipe_root / "runs/pilot/evaluation/current/checkpoint_comparison/checkpoints/checkpoint_00_latest.json",
    }
    path = paths[role]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if role == "comparison":
        payload["checkpoints"]["checkpoint_00_latest"].pop("binding")
    else:
        payload.pop("checkpoint_binding")
    path.write_text(json.dumps(payload), encoding="utf-8")
    if role == "comparison":
        scored_path = (
            recipe_root
            / "runs/pilot/evaluation/current/checkpoint_comparison/llm_judge/results/scored_llm.json"
        )
        scored = json.loads(scored_path.read_text(encoding="utf-8"))
        scored["comparison"]["sha256"] = sha256_file(path)
        scored_path.write_text(json.dumps(scored), encoding="utf-8")

    assert prepare_telco_local.main(["--stage", "pilot_refresh", *common]) == 2


def test_pilot_reuse_rejects_replaced_pilot_snapshot_even_if_only_scorer_is_refreshed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from matgpt.training.checkpoint_provenance import checkpoint_binding
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch, winner="pilot_20m"
    )
    recipe_root, _ = _write_valid_preserved_pilot_evidence(
        drive_dir, selected_sha256
    )
    pilot_gate = json.loads(
        (recipe_root / "evidence/pilot/pilot_complete.json").read_text()
    )
    checkpoint = Path(pilot_gate["checkpoint_binding"]["path"])
    checkpoint.write_bytes(b"replacement checkpoint after all evaluations")
    refreshed = checkpoint_binding(checkpoint)
    scored_path = (
        recipe_root
        / "runs/pilot/evaluation/current/checkpoint_comparison/llm_judge/results/scored_llm.json"
    )
    scored = json.loads(scored_path.read_text(encoding="utf-8"))
    matching_label = next(
        label for label, binding in scored["checkpoints"].items()
        if binding["path"] == str(checkpoint.resolve())
    )
    scored["checkpoints"][matching_label] = refreshed
    scored_path.write_text(json.dumps(scored), encoding="utf-8")

    assert prepare_telco_local.main(["--stage", "pilot_refresh", *common]) == 2


@pytest.mark.parametrize("mutation", ("zero_smoke", "same_smoke_and_pilot"))
def test_pilot_reuse_rejects_zero_or_aliased_stage_snapshots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
):
    from matgpt.training.checkpoint_provenance import checkpoint_binding
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch, winner="pilot_20m"
    )
    recipe_root, _ = _write_valid_preserved_pilot_evidence(
        drive_dir, selected_sha256
    )
    smoke_path = recipe_root / "evidence/pilot/smoke_resume_verified.json"
    pilot_path = recipe_root / "evidence/pilot/pilot_complete.json"
    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    pilot = json.loads(pilot_path.read_text(encoding="utf-8"))
    if mutation == "zero_smoke":
        checkpoint = Path(smoke["checkpoint_binding"]["path"])
        checkpoint.write_bytes(b"")
        smoke["checkpoint_binding"] = {
            "path": str(checkpoint.resolve()), "size": 0,
            "sha256": sha256_file(checkpoint),
        }
        smoke_path.write_text(json.dumps(smoke), encoding="utf-8")
    else:
        pilot["checkpoint"] = smoke["checkpoint"]
        pilot["checkpoint_binding"] = smoke["checkpoint_binding"]
        pilot_path.write_text(json.dumps(pilot), encoding="utf-8")

    assert prepare_telco_local.main(["--stage", "pilot_refresh", *common]) == 2


def test_existing_pilot_refresh_revalidates_current_artifacts_without_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch, winner="pilot_20m"
    )
    recipe_root, _ = _write_valid_preserved_pilot_evidence(
        drive_dir, selected_sha256
    )

    assert prepare_telco_local.main(["--stage", "pilot_refresh", *common]) == 0
    report_path = prepare_telco_local._pilot_refresh_path(
        drive_dir, selected_sha256
    )
    original_report = report_path.read_bytes()
    evaluation_path = recipe_root / "runs/pilot/evaluation/current/checkpoint_00_latest_base.json"
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    evaluation["review_note"] = "current bytes drifted after immutable refresh"
    evaluation_path.write_text(json.dumps(evaluation), encoding="utf-8")

    assert prepare_telco_local.main(["--stage", "pilot_refresh", *common]) == 2
    assert report_path.read_bytes() == original_report
    status = prepare_telco_local.run(
        prepare_telco_local.build_parser().parse_args(["--stage", "status", *common])
    )
    assert status["pilot_refresh_gate_satisfied"] is False
    assert "artifact" in status["pilot_refresh_gate_reason"].lower()


def test_candidate_pilot_refresh_rejects_changed_builder_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from matgpt.data.local_corpus import LocalCorpusResult
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch
    )
    monkeypatch.setattr(
        prepare_telco_local.DrivePublisher,
        "preflight_destination_provider",
        lambda _self: {
            "fsynced_partial_rename": True,
            "hard_links_required": False,
        },
    )
    monkeypatch.setattr(
        prepare_telco_local,
        "build_local_corpus",
        lambda *_args, **_kwargs: LocalCorpusResult(
            "complete", "c" * 64, 20_000_000, {"complete": True}
        ),
    )

    assert prepare_telco_local.main(["--stage", "pilot_refresh", *common]) == 2
    assert not prepare_telco_local._pilot_refresh_path(
        drive_dir, selected_sha256
    ).exists()


def test_pilot_reuse_fails_closed_when_any_existing_gate_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts import prepare_telco_local

    common, _, drive_dir, _, selected_sha256 = _selected_local_cli_fixture(
        tmp_path, monkeypatch, winner="pilot_20m"
    )
    monkeypatch.setattr(
        prepare_telco_local,
        "build_local_corpus",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("pilot reuse must not rebuild")
        ),
    )

    result = prepare_telco_local.main(["--stage", "pilot_refresh", *common])

    assert result != 0
    assert not prepare_telco_local._pilot_refresh_path(
        drive_dir, selected_sha256
    ).exists()
