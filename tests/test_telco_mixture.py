from pathlib import Path

import pytest

from matgpt.data.mixture import (
    allocate_integer_quotas,
    build_mixture_plan,
    load_mixture_config,
)
from matgpt.data.sources import load_source_registry


SOURCES = Path("configs/data/telco_300m_sources.yaml")
MIXTURE = Path("configs/data/telco_300m_mixture.yaml")
GENERAL_MAIN_QUOTAS = {
    "common_pile_arxiv_abstracts": 130_000_000,
    "common_pile_doab": 325_000_000,
    "common_pile_libretexts": 65_000_000,
    "common_pile_oercommons": 6_500_000,
    "common_pile_pes2o": 520_000_000,
    "common_pile_pre_1929_books": 910_000_000,
    "common_pile_pressbooks": 65_000_000,
    "common_pile_project_gutenberg": 650_000_000,
    "common_pile_public_domain_review": 650_000,
    "common_pile_pubmed": 252_850_000,
    "common_pile_stackexchange": 1_300_000_000,
    "common_pile_wikimedia": 2_275_000_000,
}
STRUCTURED_MAIN_QUOTAS = {
    "common_pile_github_archive": 275_000_000,
    "common_pile_python_enhancement_proposals": 2_000_000,
    "common_pile_stackv2_edu": 223_000_000,
}


def test_largest_remainder_allocation_preserves_total_and_is_stable():
    assert allocate_integer_quotas(11, {"b": 1, "a": 1, "c": 1}) == {
        "a": 4,
        "b": 4,
        "c": 3,
    }
    assert allocate_integer_quotas(11, {"c": 1, "b": 1, "a": 1}) == {
        "a": 4,
        "b": 4,
        "c": 3,
    }


@pytest.mark.parametrize(
    ("total", "weights", "message"),
    [
        (0, {"a": 1}, "positive integer"),
        (10, {}, "positive weight"),
        (10, {"a": 0}, "positive weight"),
        (10, {"a": -1}, "non-negative"),
        (10, {"a": float("inf")}, "finite"),
    ],
)
def test_quota_allocation_rejects_invalid_inputs(total, weights, message):
    with pytest.raises(ValueError, match=message):
        allocate_integer_quotas(total, weights)


def test_main_and_cooldown_match_approved_token_plan():
    registry = load_source_registry(SOURCES)
    mixture = load_mixture_config(MIXTURE)

    main = build_mixture_plan(registry, mixture, "main")
    cooldown = build_mixture_plan(registry, mixture, "cooldown")

    assert main["total_tokens"] == 10_000_000_000
    assert main["role_quotas"] == {
        "pretrain_general": 6_500_000_000,
        "pretrain_telecom": 3_000_000_000,
        "pretrain_structured": 500_000_000,
    }
    assert cooldown["total_tokens"] == 2_000_000_000
    assert cooldown["role_quotas"] == {
        "pretrain_general": 1_200_000_000,
        "pretrain_telecom": 700_000_000,
        "pretrain_structured": 100_000_000,
    }
    aggregate = {
        role: main["role_quotas"][role] + cooldown["role_quotas"][role]
        for role in main["role_quotas"]
    }
    assert aggregate == {
        "pretrain_general": 7_700_000_000,
        "pretrain_telecom": 3_700_000_000,
        "pretrain_structured": 600_000_000,
    }


def test_telecom_bucket_quotas_are_exact_and_patents_are_capped():
    registry = load_source_registry(SOURCES)
    mixture = load_mixture_config(MIXTURE)
    plan = build_mixture_plan(registry, mixture, "main")
    items = {item["id"]: item for item in plan["items"]}

    assert items["telco_common_corpus/three_gpp"]["token_quota"] == 1_050_000_000
    assert items["telco_common_corpus/rfc"]["token_quota"] == 900_000_000
    assert items["telco_common_corpus/research"]["token_quota"] == 750_000_000
    assert items["telco_common_corpus/patents"]["token_quota"] == 240_000_000
    assert items["telco_common_corpus/semantic"]["token_quota"] == 60_000_000
    assert items["telco_common_corpus/patents"]["token_quota"] <= int(
        plan["role_quotas"]["pretrain_telecom"] * 0.08
    )


def test_main_plan_exposes_exact_general_and_structured_collection_quotas():
    registry = load_source_registry(SOURCES)
    mixture = load_mixture_config(MIXTURE)
    plan = build_mixture_plan(registry, mixture, "main")
    items = {item["id"]: item["token_quota"] for item in plan["items"]}

    assert {source_id: items[source_id] for source_id in GENERAL_MAIN_QUOTAS} == (
        GENERAL_MAIN_QUOTAS
    )
    assert {
        source_id: items[source_id] for source_id in STRUCTURED_MAIN_QUOTAS
    } == STRUCTURED_MAIN_QUOTAS
    assert sum(GENERAL_MAIN_QUOTAS.values()) == plan["role_quotas"][
        "pretrain_general"
    ]
    assert sum(STRUCTURED_MAIN_QUOTAS.values()) == plan["role_quotas"][
        "pretrain_structured"
    ]


def test_pilot_uses_aggregate_mix_and_accepts_bounded_override():
    registry = load_source_registry(SOURCES)
    mixture = load_mixture_config(MIXTURE)

    configured = build_mixture_plan(registry, mixture, "pilot")
    tiny = build_mixture_plan(registry, mixture, "pilot", total_tokens=1_200)

    assert configured["total_tokens"] == 20_000_000
    assert configured["role_quotas"] == {
        "pretrain_general": 12_833_333,
        "pretrain_telecom": 6_166_667,
        "pretrain_structured": 1_000_000,
    }
    assert sum(tiny["role_quotas"].values()) == 1_200
    assert sum(item["token_quota"] for item in tiny["items"]) == 1_200
    assert configured["validation_fraction"] == 0.005


def test_plan_is_deterministic_and_contains_only_pretraining_roles():
    registry = load_source_registry(SOURCES)
    mixture = load_mixture_config(MIXTURE)

    first = build_mixture_plan(registry, mixture, "pilot")
    second = build_mixture_plan(registry, mixture, "pilot")

    assert first == second
    assert len(first["plan_sha256"]) == 64
    assert all(item["role"].startswith("pretrain_") for item in first["items"])
    assert [item["id"] for item in first["items"]] == sorted(
        item["id"] for item in first["items"]
    )


def test_plan_rejects_evaluation_source():
    registry = load_source_registry(SOURCES)
    mixture = {
        "version": 1,
        "seed": 42,
        "quota_tolerance": 0.03,
        "validation_fraction": 0.005,
        "buffer_size": 32,
        "stages": {
            "bad": {
                "total_tokens": 10,
                "role_weights": {"evaluation_only": 1},
                "source_weights": {"open_telco_lite": 1},
            }
        },
    }

    with pytest.raises(ValueError, match="not permitted for pretraining"):
        build_mixture_plan(registry, mixture, "bad")


def test_plan_rejects_patent_weight_above_ceiling():
    registry = load_source_registry(SOURCES)
    mixture = load_mixture_config(MIXTURE)
    telco = registry.by_id["telco_common_corpus"]
    altered_buckets = tuple(
        type(bucket)(
            id=bucket.id,
            collections=bucket.collections,
            weight=0.09 if bucket.id == "patents" else (
                0.34 if bucket.id == "three_gpp" else bucket.weight
            ),
        )
        for bucket in telco.buckets
    )
    altered_source = type(telco)(
        **{**telco.__dict__, "buckets": altered_buckets}
    )
    altered_registry = type(registry)(
        version=registry.version,
        sources=tuple(
            altered_source if source.id == telco.id else source
            for source in registry.sources
        ),
    )

    with pytest.raises(ValueError, match="Patent quota exceeds"):
        build_mixture_plan(altered_registry, mixture, "main")


def test_mixture_loader_rejects_unknown_top_level_keys(tmp_path: Path):
    path = tmp_path / "mixture.yaml"
    path.write_text(
        "version: 1\nseed: 42\nquota_tolerance: 0.03\nvalidation_fraction: 0.005\nbuffer_size: 16\nstages: {}\nignored: true\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown keys"):
        load_mixture_config(path)
