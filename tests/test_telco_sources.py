from pathlib import Path

import pytest

from matgpt.data.sources import (
    PRETRAIN_ROLES,
    load_source_registry,
    select_pretraining_sources,
)


REGISTRY_PATH = Path("configs/data/telco_300m_sources.yaml")
COMMON_PILE_REVISION = "5afc546db324e7f39f297ba757c9a60547151e7c"
GENERAL_COLLECTIONS = {
    "common_pile_arxiv_abstracts": "arxiv_abstracts/*.jsonl.gz",
    "common_pile_doab": "doab/*.jsonl.gz",
    "common_pile_libretexts": "libretexts/*.jsonl.gz",
    "common_pile_oercommons": "oercommons/*.jsonl.gz",
    "common_pile_pes2o": "peS2o/*.jsonl.gz",
    "common_pile_pre_1929_books": "pre_1929_books/*.jsonl.gz",
    "common_pile_pressbooks": "pressbooks/*.jsonl.gz",
    "common_pile_project_gutenberg": "project_gutenberg/*.jsonl.gz",
    "common_pile_public_domain_review": "public_domain_review/*.jsonl.gz",
    "common_pile_pubmed": "pubmed/*.jsonl.gz",
    "common_pile_stackexchange": "stackexchange/*.jsonl.gz",
    "common_pile_wikimedia": "wikimedia/*.jsonl.gz",
}
STRUCTURED_COLLECTIONS = {
    "common_pile_github_archive": "github_archive/*.jsonl.gz",
    "common_pile_python_enhancement_proposals": (
        "python_enhancement_proposals/*.jsonl.gz"
    ),
    "common_pile_stackv2_edu": "stackv2_edu/*.jsonl.gz",
}


def test_registry_pins_training_and_evaluation_sources():
    registry = load_source_registry(REGISTRY_PATH)

    assert registry.version == 1
    assert registry.by_id["common_pile_wikimedia"].revision == COMMON_PILE_REVISION
    assert registry.by_id["telco_common_corpus"].revision == (
        "c590e4e6224d2cd50cc9403537cff7656d1535ea"
    )
    assert registry.by_id["open_telco_lite"].revision == (
        "1c0f2eac3ad0baa29704b147a95fea283b2906c7"
    )
    assert registry.by_id["open_telco_full"].revision == (
        "6319806f04783eafe04d9facf755d379c66b7664"
    )
    assert registry.by_id["open_telco_lite"].role == "evaluation_only"
    assert registry.by_id["open_telco_full"].role == "evaluation_only"


def test_registry_declares_all_asset_roles_and_license_review_state():
    registry = load_source_registry(REGISTRY_PATH)

    assert {source.role for source in registry.sources} == {
        "pretrain_general",
        "pretrain_telecom",
        "pretrain_structured",
        "posttrain",
        "rag_only",
        "evaluation_only",
    }
    assert registry.by_id["common_pile_wikimedia"].license_review == "required"
    assert registry.by_id["telco_common_corpus"].license_field == "license"
    assert registry.by_id["smol_smoltalk"].license_review == "required"


def test_telco_source_has_bounded_collection_buckets():
    source = load_source_registry(REGISTRY_PATH).by_id["telco_common_corpus"]

    assert source.collection_field == "collection"
    assert source.document_id_field == "identifier"
    assert source.token_count_field == "token_count"
    assert {bucket.id: bucket.weight for bucket in source.buckets} == {
        "three_gpp": 0.35,
        "rfc": 0.30,
        "research": 0.25,
        "patents": 0.08,
        "semantic": 0.02,
    }
    assert "3GPP-TSG" in source.bucket_by_id["three_gpp"].collections
    assert "USPTO" in source.bucket_by_id["patents"].collections
    assert "Wikidata-Telecom" in source.bucket_by_id["semantic"].collections
    assert {
        collection
        for bucket in source.buckets
        for collection in bucket.collections
    } == {
        "3GPP-TSG",
        "IETF-RFCs",
        "IETF-Drafts",
        "IETF-Proceedings",
        "IETF-Mail-Daily",
        "IEEE-Access",
        "OpenAlex",
        "USPTO",
        "EPO",
        "Wikipedia-Telecom",
        "Wikidata-Telecom",
    }


def test_common_pile_collections_are_independently_quota_controlled():
    registry = load_source_registry(REGISTRY_PATH)

    assert "common_pile_general" not in registry.by_id
    assert "common_pile_structured" not in registry.by_id
    for source_id, data_file in GENERAL_COLLECTIONS.items():
        source = registry.by_id[source_id]
        assert source.role == "pretrain_general"
        assert source.revision == COMMON_PILE_REVISION
        assert source.data_files == (data_file,)
        assert source.collection == data_file.split("/", 1)[0]
    for source_id, data_file in STRUCTURED_COLLECTIONS.items():
        source = registry.by_id[source_id]
        assert source.role == "pretrain_structured"
        assert source.revision == COMMON_PILE_REVISION
        assert source.data_files == (data_file,)
        assert source.collection == data_file.split("/", 1)[0]


@pytest.mark.parametrize(
    "source_id",
    [
        "open_telco_lite",
        "open_telco_full",
        "smol_smoltalk",
        "otel_llm",
        "otel_safety",
        "gsma_3gpp_mirror",
    ],
)
def test_training_boundary_rejects_non_pretraining_roles(source_id: str):
    registry = load_source_registry(REGISTRY_PATH)

    with pytest.raises(ValueError, match="not permitted for pretraining"):
        select_pretraining_sources(registry, [source_id])


def test_training_boundary_returns_only_requested_pretraining_sources():
    registry = load_source_registry(REGISTRY_PATH)

    selected = select_pretraining_sources(
        registry,
        ["telco_common_corpus", "common_pile_wikimedia"],
    )

    assert tuple(source.id for source in selected) == (
        "telco_common_corpus",
        "common_pile_wikimedia",
    )
    assert all(source.role in PRETRAIN_ROLES for source in selected)


def test_serious_registry_requires_immutable_revision(tmp_path: Path):
    path = tmp_path / "sources.yaml"
    path.write_text(
        """
version: 1
sources:
  - id: bad
    hf_name: example/bad
    split: train
    revision: main
    role: pretrain_general
    license: CC0-1.0
    license_review: required
    text_field: text
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="40-character revision"):
        load_source_registry(path)

    registry = load_source_registry(path, serious=False)
    assert registry.by_id["bad"].revision == "main"


def test_registry_rejects_duplicate_ids(tmp_path: Path):
    path = tmp_path / "sources.yaml"
    source = """
    hf_name: example/data
    split: train
    revision: 0123456789abcdef0123456789abcdef01234567
    role: pretrain_general
    license: CC0-1.0
    license_review: required
    text_field: text
"""
    path.write_text(
        f"version: 1\nsources:\n  - id: duplicate\n{source}  - id: duplicate\n{source}",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate source id"):
        load_source_registry(path)


def test_registry_rejects_unknown_source_keys(tmp_path: Path):
    path = tmp_path / "sources.yaml"
    path.write_text(
        """
version: 1
sources:
  - id: unexpected
    hf_name: example/data
    split: train
    revision: 0123456789abcdef0123456789abcdef01234567
    role: pretrain_general
    license: CC0-1.0
    license_review: required
    text_field: text
    silently_ignored: unsafe
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown keys"):
        load_source_registry(path)
