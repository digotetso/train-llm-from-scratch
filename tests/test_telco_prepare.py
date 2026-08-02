import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from tokenizers import Tokenizer, models, pre_tokenizers

from matgpt.data.quality import DataQualityPolicy
from matgpt.config import clone_config, load_config
from matgpt.data.shard import tokenize_splits_from_config
from matgpt.data.sources import load_source_registry
from matgpt.data.telco_prepare import (
    audit_token_quotas,
    corpus_has_exact_token_quotas,
    iter_deterministic_buffered,
    normalize_source_row,
    prepare_telco_corpora,
)
from matgpt.preflight import build_preflight_report
from matgpt.tokenizer.train import train_tokenizer_from_config
from matgpt.utils.hashing import sha256_file


REGISTRY_PATH = Path("configs/data/telco_300m_sources.yaml")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _tiny_plan(stage: str = "pilot") -> dict:
    items = [
        {
            "id": "common_pile_wikimedia",
            "source_id": "common_pile_wikimedia",
            "bucket_id": None,
            "role": "pretrain_general",
            "token_quota": 8,
        },
        {
            "id": "common_pile_github_archive",
            "source_id": "common_pile_github_archive",
            "bucket_id": None,
            "role": "pretrain_structured",
            "token_quota": 8,
        },
    ]
    for bucket_id in ("three_gpp", "rfc", "research", "patents", "semantic"):
        items.append(
            {
                "id": f"telco_common_corpus/{bucket_id}",
                "source_id": "telco_common_corpus",
                "bucket_id": bucket_id,
                "role": "pretrain_telecom",
                "token_quota": 8,
            }
        )
    items.sort(key=lambda item: item["id"])
    return {
        "version": 1,
        "stage": stage,
        "seed": 42,
        "total_tokens": 56,
        "quota_tolerance": 0.03,
        "validation_fraction": 0.2,
        "buffer_size": 3,
        "role_quotas": {
            "pretrain_general": 8,
            "pretrain_structured": 8,
            "pretrain_telecom": 40,
        },
        "items": items,
        "plan_sha256": f"{stage:0<64}"[:64],
    }


def _stream_rows(source_kind: str) -> list[dict]:
    if source_kind == "general":
        return [
            {"text": f"General English document number {index} has useful prose."}
            for index in range(5)
        ]
    if source_kind == "structured":
        return [
            {"text": f"router interface Ethernet{index} uses address 192.0.2.{index}"}
            for index in range(5)
        ]
    collections = {
        "three_gpp": ("3GPP-TSG", "3GPP TDoc (free redistribution)"),
        "rfc": ("IETF-RFCs", "IETF Trust §4.c"),
        "research": ("IEEE-Access", "CC-BY-4.0"),
        "patents": ("USPTO", "Federal Public Domain"),
        "semantic": ("Wikidata-Telecom", "CC0-1.0"),
    }
    rows = []
    for bucket_id, (collection, license_name) in collections.items():
        for index in range(4):
            rows.append(
                {
                    "identifier": f"{bucket_id}-{index}",
                    "collection": collection,
                    "license": license_name,
                    "token_count": 8,
                    "text": f"Unique {bucket_id} telecom material section {index}.",
                }
            )
    return rows


def _fake_loader_with_calls(calls: list[dict]):
    def load_dataset(hf_name: str, **kwargs):
        calls.append({"hf_name": hf_name, **kwargs})
        if hf_name == "GSMA/Telco-Common-Corpus":
            return iter(_stream_rows("telco"))
        data_files = kwargs.get("data_files") or []
        if any("github_archive" in path for path in data_files):
            return iter(_stream_rows("structured"))
        return iter(_stream_rows("general"))

    return load_dataset


def _single_general_plan(token_quota: int = 8) -> dict:
    return {
        "version": 1,
        "stage": "pilot",
        "seed": 42,
        "total_tokens": token_quota,
        "quota_tolerance": 0.0,
        "validation_fraction": 0.0,
        "buffer_size": 3,
        "role_quotas": {"pretrain_general": token_quota},
        "items": [
            {
                "id": "common_pile_wikimedia",
                "source_id": "common_pile_wikimedia",
                "bucket_id": None,
                "role": "pretrain_general",
                "token_quota": token_quota,
            }
        ],
        "plan_sha256": "f" * 64,
    }


def _write_word_tokenizer(path: Path, *, extra_token: str | None = None) -> str:
    path.mkdir(parents=True)
    vocab = {"[UNK]": 0, "a": 1, "b": 2, "c": 3}
    if extra_token is not None:
        vocab[extra_token] = len(vocab)
    tokenizer = Tokenizer(models.WordLevel(vocab=vocab, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = pre_tokenizers.WhitespaceSplit()
    tokenizer.save(str(path / "tokenizer.json"))
    digest = sha256_file(path / "tokenizer.json")
    (path / "special_tokens.json").write_text(
        json.dumps({"tokenizer_sha256": digest}) + "\n",
        encoding="utf-8",
    )
    return digest


def test_normalize_source_row_preserves_required_provenance():
    source = load_source_registry(REGISTRY_PATH).by_id["telco_common_corpus"]

    record = normalize_source_row(
        source,
        {
            "identifier": "RFC8202",
            "collection": "IETF-RFCs",
            "license": "IETF Trust §4.c",
            "token_count": 710,
            "text": "  Link-state routing.\r\n",
        },
        index=0,
        stage="pilot",
        bucket_id="rfc",
    )

    assert record["document_id"] == "RFC8202"
    assert record["source_id"] == "telco_common_corpus"
    assert record["collection"] == "IETF-RFCs"
    assert record["license"] == "IETF Trust §4.c"
    assert record["license_review"] == "required"
    assert record["role"] == "pretrain_telecom"
    assert record["stage"] == "pilot"
    assert record["bucket_id"] == "rfc"
    assert record["estimated_tokens"] == 710
    assert record["content_sha256"] == record["text_sha256"]
    assert record["text"] == "Link-state routing."


def test_normalize_source_row_requires_document_level_license():
    source = load_source_registry(REGISTRY_PATH).by_id["telco_common_corpus"]

    with pytest.raises(ValueError, match="document-level license"):
        normalize_source_row(
            source,
            {
                "identifier": "RFC1",
                "collection": "IETF-RFCs",
                "license": "",
                "token_count": 10,
                "text": "A valid document.",
            },
            index=0,
            stage="pilot",
            bucket_id="rfc",
        )


def test_buffered_order_is_repeatable_seeded_and_bounded():
    records = [
        {"document_id": str(index), "content_sha256": f"{index:064x}"}
        for index in range(20)
    ]

    first = list(iter_deterministic_buffered(records, seed=42, buffer_size=5))

    assert first == list(
        iter_deterministic_buffered(records, seed=42, buffer_size=5)
    )
    assert first != list(
        iter_deterministic_buffered(records, seed=43, buffer_size=5)
    )
    assert {row["document_id"] for row in first} == {
        str(index) for index in range(20)
    }


def test_builder_streams_to_quotas_and_promotes_atomically(tmp_path: Path):
    registry = load_source_registry(REGISTRY_PATH)
    calls: list[dict] = []
    output = tmp_path / "corpus"

    manifest = prepare_telco_corpora(
        registry=registry,
        plans=[_tiny_plan()],
        output_dir=output,
        quality_policy=DataQualityPolicy(
            enabled=True,
            min_chars=2,
            exact_dedup=True,
        ),
        buffer_size=3,
        dataset_loader=_fake_loader_with_calls(calls),
    )

    assert manifest["complete"] is True
    assert manifest["stages"]["pilot"]["requested_tokens"] == 56
    assert manifest["stages"]["pilot"]["estimated_tokens"] >= 56
    assert set(manifest["split_stats"]) == {"pilot", "validation"}
    for split in ("pilot", "validation"):
        assert manifest["split_stats"][split]["document_count"] > 0
        assert manifest["split_stats"][split]["total_chars"] > 0
        assert len(manifest["split_stats"][split]["documents_sha256"]) == 64
    assert (output / "pilot.jsonl").exists()
    assert (output / "validation.jsonl").exists()
    assert (output / "manifest.json").exists()
    assert not list(tmp_path.glob(".corpus.staging-*"))
    rows = _read_jsonl(output / "pilot.jsonl")
    validation_rows = _read_jsonl(output / "validation.jsonl")
    assert all(row["role"].startswith("pretrain_") for row in rows)
    assert all(row["license"] for row in rows)
    assert {row["source_id"] for row in rows} == {
        "common_pile_wikimedia",
        "common_pile_github_archive",
        "telco_common_corpus",
    }
    assert validation_rows
    assert {row["content_sha256"] for row in rows}.isdisjoint(
        row["content_sha256"] for row in validation_rows
    )
    assert manifest["validation"]["documents"] == len(validation_rows)
    assert len(calls) == 3
    assert all(call["streaming"] is True for call in calls)
    assert all(len(call["revision"]) == 40 for call in calls)
    assert any(call.get("data_files") for call in calls)


def test_builder_uses_frozen_tokenizer_counts_to_reach_exact_quota(
    tmp_path: Path,
):
    registry = load_source_registry(REGISTRY_PATH)
    tokenizer_dir = tmp_path / "tokenizer"
    tokenizer_sha256 = _write_word_tokenizer(tokenizer_dir)
    plan = _single_general_plan()
    output = tmp_path / "corpus"
    rows = [
        {"text": "a b c one"},
        {"text": "a b c two"},
        {"text": "a b c three"},
        {"text": "a b c four"},
    ]

    manifest = prepare_telco_corpora(
        registry=registry,
        plans=[plan],
        output_dir=output,
        quality_policy=DataQualityPolicy(enabled=True, min_chars=2),
        buffer_size=1,
        dataset_loader=lambda _name, **_kwargs: iter(rows),
        tokenizer_dir=tokenizer_dir,
    )
    report = audit_token_quotas(
        [output / "pilot.jsonl"],
        tokenizer_dir,
        [plan],
        tolerance=0.0,
    )

    assert report["passed"] is True
    assert len(_read_jsonl(output / "pilot.jsonl")) == 2
    assert manifest["quota_counting"] == {
        "method": "tokenizer_exact",
        "tokenizer_sha256": tokenizer_sha256,
    }
    assert manifest["stages"]["pilot"]["quota_tokens"] == 8
    assert manifest["stages"]["pilot"]["estimated_tokens"] == 6
    assert corpus_has_exact_token_quotas(output, tokenizer_dir, [plan]) is True


def test_exact_quota_compatibility_rejects_changed_tokenizer_or_plan(tmp_path: Path):
    registry = load_source_registry(REGISTRY_PATH)
    tokenizer_dir = tmp_path / "tokenizer"
    _write_word_tokenizer(tokenizer_dir)
    plan = _single_general_plan()
    output = tmp_path / "corpus"
    rows = [{"text": "a b c one"}, {"text": "a b c two"}]
    prepare_telco_corpora(
        registry=registry,
        plans=[plan],
        output_dir=output,
        quality_policy=DataQualityPolicy(enabled=True, min_chars=2),
        buffer_size=1,
        dataset_loader=lambda _name, **_kwargs: iter(rows),
        tokenizer_dir=tokenizer_dir,
    )
    changed_tokenizer_dir = tmp_path / "changed-tokenizer"
    _write_word_tokenizer(changed_tokenizer_dir, extra_token="changed")
    changed_plan = {**plan, "plan_sha256": "e" * 64}

    assert (
        corpus_has_exact_token_quotas(output, changed_tokenizer_dir, [plan])
        is False
    )
    assert corpus_has_exact_token_quotas(output, tokenizer_dir, [changed_plan]) is False


def test_builder_rejects_invalid_tokenizer_before_creating_staging(tmp_path: Path):
    registry = load_source_registry(REGISTRY_PATH)
    tokenizer_dir = tmp_path / "tokenizer"
    _write_word_tokenizer(tokenizer_dir)
    (tokenizer_dir / "special_tokens.json").write_text(
        json.dumps({"tokenizer_sha256": "0" * 64}) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "corpus"
    calls: list[dict] = []

    with pytest.raises(ValueError, match="Tokenizer SHA-256"):
        prepare_telco_corpora(
            registry=registry,
            plans=[_single_general_plan()],
            output_dir=output,
            quality_policy=DataQualityPolicy(enabled=True, min_chars=2),
            dataset_loader=_fake_loader_with_calls(calls),
            tokenizer_dir=tokenizer_dir,
        )

    assert calls == []
    assert not output.exists()
    assert not list(tmp_path.glob(".corpus.staging-*"))


def test_builder_publishes_main_and_cooldown_together(tmp_path: Path):
    registry = load_source_registry(REGISTRY_PATH)
    output = tmp_path / "corpus"

    manifest = prepare_telco_corpora(
        registry=registry,
        plans=[_tiny_plan("main"), _tiny_plan("cooldown")],
        output_dir=output,
        quality_policy=DataQualityPolicy(
            enabled=True,
            min_chars=2,
            exact_dedup=True,
        ),
        buffer_size=3,
        dataset_loader=_fake_loader_with_calls([]),
    )

    assert set(manifest["stages"]) == {"main", "cooldown"}
    assert (output / "main.jsonl").exists()
    assert (output / "cooldown.jsonl").exists()
    main_hashes = {row["content_sha256"] for row in _read_jsonl(output / "main.jsonl")}
    cooldown_hashes = {
        row["content_sha256"] for row in _read_jsonl(output / "cooldown.jsonl")
    }
    assert main_hashes.isdisjoint(cooldown_hashes)
    validation_hashes = {
        row["content_sha256"] for row in _read_jsonl(output / "validation.jsonl")
    }
    assert validation_hashes.isdisjoint(main_hashes | cooldown_hashes)


def test_synthetic_telco_corpus_reaches_shards_and_preflight(tmp_path: Path):
    registry = load_source_registry(REGISTRY_PATH)
    corpus = tmp_path / "corpus"
    prepare_telco_corpora(
        registry=registry,
        plans=[_tiny_plan()],
        output_dir=corpus,
        quality_policy=DataQualityPolicy(
            enabled=True,
            min_chars=2,
            exact_dedup=True,
        ),
        buffer_size=3,
        dataset_loader=_fake_loader_with_calls([]),
    )
    cfg = clone_config(load_config("configs/matgpt_telco_300m.yaml"))
    cfg["run"]["output_dir"] = str(tmp_path / "run")
    cfg["dataset"].update(
        {
            "normalized_dir": str(corpus),
            "train_split": "pilot",
            "training_splits": {"pilot": "pilot"},
        }
    )
    cfg["tokenizer"].update(
        {
            "vocab_size": 320,
            "output_dir": str(tmp_path / "tokenizer"),
            "min_frequency": 1,
        }
    )
    cfg["model"].update({"vocab_size": 320, "context_length": 8})
    cfg["sharding"].update(
        {"output_dir": str(tmp_path / "shards"), "shard_size_tokens": 4096}
    )
    cfg["training"].update(
        {
            "max_tokens": 4096,
            "data_phases": [
                {"name": "pilot", "split": "pilot", "until_tokens": 4096}
            ],
        }
    )

    train_tokenizer_from_config(cfg)
    metadata = tokenize_splits_from_config(cfg)
    report = build_preflight_report(cfg, require_t4=False, min_free_disk_gb=0.0)

    assert set(metadata["splits"]) == {"pilot", "validation"}
    assert report["status"] == "pass"


def test_builder_filters_exact_duplicates_and_contamination(tmp_path: Path):
    registry = load_source_registry(REGISTRY_PATH)
    calls: list[dict] = []
    base_loader = _fake_loader_with_calls(calls)
    plan = _tiny_plan()
    for item in plan["items"]:
        if item["source_id"] in {
                "common_pile_wikimedia",
                "common_pile_github_archive",
        }:
            item["token_quota"] = 40
    plan["role_quotas"]["pretrain_general"] = 40
    plan["role_quotas"]["pretrain_structured"] = 40
    plan["total_tokens"] = sum(item["token_quota"] for item in plan["items"])

    def loader(hf_name: str, **kwargs):
        rows = list(base_loader(hf_name, **kwargs))
        if hf_name == "common-pile/comma_v0.1_training_dataset":
            rows.insert(0, {"text": "FORBIDDEN BENCHMARK QUESTION"})
            rows.insert(1, dict(rows[2]))
        return iter(rows)

    manifest = prepare_telco_corpora(
        registry=registry,
        plans=[plan],
        output_dir=tmp_path / "filtered",
        quality_policy=DataQualityPolicy(
            enabled=True,
            min_chars=2,
            exact_dedup=True,
            contamination_patterns=["forbidden benchmark question"],
        ),
        buffer_size=3,
        dataset_loader=loader,
    )

    reasons = manifest["quality_filter"]["rejection_reasons"]
    assert reasons["benchmark_contamination"] >= 1
    assert reasons["duplicate_exact"] >= 1


def test_builder_skips_empty_text_rows_and_records_rejection(tmp_path: Path):
    registry = load_source_registry(REGISTRY_PATH)
    base_loader = _fake_loader_with_calls([])

    def loader(hf_name: str, **kwargs):
        rows = list(base_loader(hf_name, **kwargs))
        data_files = kwargs.get("data_files") or []
        if any("github_archive" in path for path in data_files):
            rows.insert(0, {"text": " \t\n"})
        return iter(rows)

    output = tmp_path / "corpus"
    manifest = prepare_telco_corpora(
        registry=registry,
        plans=[_tiny_plan()],
        output_dir=output,
        quality_policy=DataQualityPolicy(
            enabled=True,
            min_chars=2,
            exact_dedup=True,
        ),
        buffer_size=3,
        dataset_loader=loader,
    )

    assert manifest["complete"] is True
    assert manifest["quality_filter"]["rejection_reasons"]["empty_text"] == 1
    rows = _read_jsonl(output / "pilot.jsonl")
    rows.extend(_read_jsonl(output / "validation.jsonl"))
    assert rows
    assert all(row["text"].strip() for row in rows)


def test_builder_still_rejects_missing_text_field(tmp_path: Path):
    registry = load_source_registry(REGISTRY_PATH)
    base_loader = _fake_loader_with_calls([])

    def loader(hf_name: str, **kwargs):
        rows = list(base_loader(hf_name, **kwargs))
        data_files = kwargs.get("data_files") or []
        if any("github_archive" in path for path in data_files):
            rows.insert(0, {})
        return iter(rows)

    with pytest.raises(ValueError, match="is missing 'text'"):
        prepare_telco_corpora(
            registry=registry,
            plans=[_tiny_plan()],
            output_dir=tmp_path / "corpus",
            quality_policy=DataQualityPolicy(enabled=True, min_chars=2),
            buffer_size=3,
            dataset_loader=loader,
        )


def test_builder_failure_leaves_existing_output_untouched(tmp_path: Path):
    registry = load_source_registry(REGISTRY_PATH)
    output = tmp_path / "corpus"
    output.mkdir()
    (output / "sentinel").write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="exhausted before quota"):
        prepare_telco_corpora(
            registry=registry,
            plans=[_tiny_plan()],
            output_dir=output,
            quality_policy=DataQualityPolicy(enabled=True, exact_dedup=True),
            force=True,
            dataset_loader=lambda _name, **_kwargs: iter(()),
        )

    assert (output / "sentinel").read_text(encoding="utf-8") == "keep"
    assert not list(tmp_path.glob(".corpus.staging-*"))


def test_builder_refuses_to_overwrite_without_force(tmp_path: Path):
    registry = load_source_registry(REGISTRY_PATH)
    output = tmp_path / "corpus"
    output.mkdir()

    with pytest.raises(FileExistsError, match="--force"):
        prepare_telco_corpora(
            registry=registry,
            plans=[_tiny_plan()],
            output_dir=output,
            quality_policy=DataQualityPolicy(enabled=True),
            dataset_loader=_fake_loader_with_calls([]),
        )


def test_builder_force_keeps_recoverable_backup(tmp_path: Path):
    registry = load_source_registry(REGISTRY_PATH)
    output = tmp_path / "corpus"
    output.mkdir()
    (output / "sentinel").write_text("old corpus", encoding="utf-8")

    prepare_telco_corpora(
        registry=registry,
        plans=[_tiny_plan()],
        output_dir=output,
        quality_policy=DataQualityPolicy(enabled=True, exact_dedup=True),
        force=True,
        dataset_loader=_fake_loader_with_calls([]),
    )

    backups = list(tmp_path.glob("corpus.backup-*"))
    assert len(backups) == 1
    assert (backups[0] / "sentinel").read_text(encoding="utf-8") == "old corpus"
    assert (output / "manifest.json").exists()


def test_builder_rejects_evaluation_plan_before_loading(tmp_path: Path):
    registry = load_source_registry(REGISTRY_PATH)
    calls: list[dict] = []
    bad_plan = {
        "version": 1,
        "stage": "pilot",
        "seed": 42,
        "total_tokens": 10,
        "quota_tolerance": 0.03,
        "validation_fraction": 0.2,
        "buffer_size": 3,
        "role_quotas": {"evaluation_only": 10},
        "items": [
            {
                "id": "open_telco_lite",
                "source_id": "open_telco_lite",
                "bucket_id": None,
                "role": "evaluation_only",
                "token_quota": 10,
            }
        ],
        "plan_sha256": "0" * 64,
    }

    with pytest.raises(ValueError, match="not permitted for pretraining"):
        prepare_telco_corpora(
            registry=registry,
            plans=[bad_plan],
            output_dir=tmp_path / "bad",
            quality_policy=DataQualityPolicy(enabled=True),
            dataset_loader=_fake_loader_with_calls(calls),
        )

    assert calls == []


def test_audit_token_quotas_reports_actual_counts(monkeypatch, tmp_path: Path):
    path = tmp_path / "pilot.jsonl"
    path.write_text(
        json.dumps(
            {
                "source_id": "common_pile_wikimedia",
                "bucket_id": None,
                "stage": "pilot",
                "text": "one two",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    class WordTokenizer:
        def encode(self, text: str):
            return SimpleNamespace(ids=list(range(len(text.split()))))

    monkeypatch.setattr(
        "matgpt.data.telco_prepare.load_tokenizer",
        lambda _path: WordTokenizer(),
    )
    plan = {
        "stage": "pilot",
        "items": [
            {
                "id": "common_pile_wikimedia",
                "source_id": "common_pile_wikimedia",
                "bucket_id": None,
                "token_quota": 2,
            }
        ],
    }

    report = audit_token_quotas(
        [path],
        tmp_path / "tokenizer",
        [plan],
        tolerance=0.0,
    )

    assert report["passed"] is True
    assert report["stages"]["pilot"]["items"]["common_pile_wikimedia"] == {
        "planned_tokens": 2,
        "actual_tokens": 2,
        "relative_variance": 0.0,
        "last_document_tokens": 2,
        "document_boundary_limited": False,
        "passed": True,
    }


def test_audit_accepts_minimal_document_overshoot_when_stage_total_is_within_tolerance(
    monkeypatch, tmp_path: Path
):
    path = tmp_path / "pilot.jsonl"
    rows = [
        {
            "source_id": "tiny",
            "bucket_id": None,
            "stage": "pilot",
            "text": " ".join(["tiny"] * 8),
        },
        {
            "source_id": "tiny",
            "bucket_id": None,
            "stage": "pilot",
            "text": " ".join(["tiny"] * 8),
        },
        {
            "source_id": "bulk",
            "bucket_id": None,
            "stage": "pilot",
            "text": " ".join(["bulk"] * 990),
        },
    ]
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    class WordTokenizer:
        def encode(self, text: str):
            return SimpleNamespace(ids=list(range(len(text.split()))))

    monkeypatch.setattr(
        "matgpt.data.telco_prepare.load_tokenizer",
        lambda _path: WordTokenizer(),
    )
    plan = {
        "stage": "pilot",
        "items": [
            {
                "id": "tiny",
                "source_id": "tiny",
                "bucket_id": None,
                "token_quota": 10,
            },
            {
                "id": "bulk",
                "source_id": "bulk",
                "bucket_id": None,
                "token_quota": 990,
            },
        ],
    }

    report = audit_token_quotas(
        [path],
        tmp_path / "tokenizer",
        [plan],
        tolerance=0.03,
    )

    assert report["passed"] is True
    assert report["stages"]["pilot"]["relative_variance"] == pytest.approx(
        0.006
    )
    assert report["stages"]["pilot"]["items"]["tiny"] == {
        "planned_tokens": 10,
        "actual_tokens": 16,
        "relative_variance": 0.6,
        "last_document_tokens": 8,
        "document_boundary_limited": True,
        "passed": True,
    }


def test_audit_rejects_document_overshoot_when_stage_total_exceeds_tolerance(
    monkeypatch, tmp_path: Path
):
    path = tmp_path / "pilot.jsonl"
    path.write_text(
        "".join(
            json.dumps(
                {
                    "source_id": "tiny",
                    "bucket_id": None,
                    "stage": "pilot",
                    "text": " ".join(["tiny"] * 8),
                }
            )
            + "\n"
            for _ in range(2)
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "matgpt.data.telco_prepare.load_tokenizer",
        lambda _path: SimpleNamespace(
            encode=lambda text: SimpleNamespace(ids=list(range(len(text.split()))))
        ),
    )
    plan = {
        "stage": "pilot",
        "items": [
            {
                "id": "tiny",
                "source_id": "tiny",
                "bucket_id": None,
                "token_quota": 10,
            }
        ],
    }

    with pytest.raises(ValueError, match="stage total"):
        audit_token_quotas(
            [path],
            tmp_path / "tokenizer",
            [plan],
            tolerance=0.03,
        )


def test_audit_token_quotas_fails_outside_tolerance(monkeypatch, tmp_path: Path):
    path = tmp_path / "pilot.jsonl"
    path.write_text(
        json.dumps(
            {
                "source_id": "common_pile_wikimedia",
                "bucket_id": None,
                "stage": "pilot",
                "text": "one",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "matgpt.data.telco_prepare.load_tokenizer",
        lambda _path: SimpleNamespace(
            encode=lambda _text: SimpleNamespace(ids=[1])
        ),
    )
    plan = {
        "stage": "pilot",
        "items": [
            {
                "id": "common_pile_wikimedia",
                "source_id": "common_pile_wikimedia",
                "bucket_id": None,
                "token_quota": 2,
            }
        ],
    }

    with pytest.raises(ValueError, match="outside tolerance"):
        audit_token_quotas(
            [path],
            tmp_path / "tokenizer",
            [plan],
            tolerance=0.0,
        )
