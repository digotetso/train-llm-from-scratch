import sqlite3
import tracemalloc
from pathlib import Path

import pytest

import matgpt.data.local_sample as local_sample
from matgpt.data.local_sample import (
    LocalSampleRequest,
    _write_chunks,
    build_tokenizer_sample,
)
from matgpt.data.local_state import BuildJournal
from matgpt.data.quality import DataQualityPolicy
from matgpt.data.sources import load_source_registry


def _tiny_plan():
    return {
        "version": 1,
        "stage": "pilot",
        "seed": 42,
        "total_tokens": 2_000,
        "quota_tolerance": 0.03,
        "validation_fraction": 0.2,
        "buffer_size": 8,
        "role_quotas": {"pretrain_general": 2_000},
        "items": [
            {
                "id": "common_pile_wikimedia",
                "source_id": "common_pile_wikimedia",
                "bucket_id": None,
                "role": "pretrain_general",
                "token_quota": 2_000,
            }
        ],
        "plan_sha256": "f" * 64,
    }


def _fake_telco_loader(_dataset_id: str, **_kwargs):
    return iter(
        {
            "text": f"Document {index} explains deterministic telecom routing behavior.",
        }
        for index in range(10_000)
    )


def _large_fake_telco_loader(_dataset_id: str, **_kwargs):
    return iter(
        {
            "text": (
                f"Scaled document {index} explains deterministic telecom routing "
                "behavior with enough unique content."
            ),
        }
        for index in range(100_000)
    )


def _files(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*.jsonl"))
    }


def test_interrupted_sample_resumes_byte_identically(tmp_path: Path):
    registry = load_source_registry("configs/data/telco_300m_sources.yaml")
    tiny_plan = _tiny_plan()
    request = LocalSampleRequest(
        registry=registry,
        plan=tiny_plan,
        output_dir=tmp_path / "resumed",
        state_path=tmp_path / "resumed.sqlite3",
        quality_policy=DataQualityPolicy(enabled=True, min_chars=2, exact_dedup=True),
        chunk_bytes=300,
        progress_interval_seconds=0,
    )
    commits = 0

    def interrupt_after_first(_unit):
        nonlocal commits
        commits += 1
        if commits == 1:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        build_tokenizer_sample(
            request,
            dataset_loader=_fake_telco_loader,
            on_unit_committed=interrupt_after_first,
        )
    resumed = build_tokenizer_sample(request, dataset_loader=_fake_telco_loader)

    clean_request = LocalSampleRequest(
        registry=request.registry,
        plan=request.plan,
        output_dir=tmp_path / "clean",
        state_path=tmp_path / "clean.sqlite3",
        quality_policy=request.quality_policy,
        chunk_bytes=300,
        progress_interval_seconds=0,
    )
    clean = build_tokenizer_sample(clean_request, dataset_loader=_fake_telco_loader)

    assert resumed["manifest_sha256"] == clean["manifest_sha256"]
    assert _files(request.output_dir) == _files(clean_request.output_dir)


def test_sample_holdout_is_persistently_disjoint_and_progress_reports_quota(
    tmp_path: Path,
):
    registry = load_source_registry("configs/data/telco_300m_sources.yaml")
    tiny_plan = _tiny_plan()
    events = []
    request = LocalSampleRequest(
        registry=registry,
        plan=tiny_plan,
        output_dir=tmp_path / "sample",
        state_path=tmp_path / "state.sqlite3",
        quality_policy=DataQualityPolicy(enabled=True, min_chars=2, exact_dedup=True),
        chunk_bytes=300,
        progress_interval_seconds=0,
    )
    manifest = build_tokenizer_sample(
        request,
        dataset_loader=_fake_telco_loader,
        progress_sink=events.append,
    )
    with sqlite3.connect(request.state_path) as connection:
        persisted_hashes = connection.execute(
            "SELECT COUNT(*) FROM seen_hashes"
        ).fetchone()[0]

    assert manifest["version"] == 2
    assert isinstance(manifest["fit_content_sha256"], str)
    assert len(manifest["fit_content_sha256"]) == 64
    assert isinstance(manifest["holdout_content_sha256"], str)
    assert len(manifest["holdout_content_sha256"]) == 64
    assert manifest["accepted_documents"] > 0
    assert manifest["holdout_documents"] > 0
    assert persisted_hashes == (
        manifest["accepted_documents"] + manifest["holdout_documents"]
    )
    assert events[-1].accepted_estimated_tokens >= tiny_plan["total_tokens"]
    assert events[-1].requested_estimated_tokens == tiny_plan["total_tokens"]


def test_resume_does_not_use_materializing_journal_units(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    registry = load_source_registry("configs/data/telco_300m_sources.yaml")
    request = LocalSampleRequest(
        registry=registry,
        plan=_tiny_plan(),
        output_dir=tmp_path / "sample",
        state_path=tmp_path / "state.sqlite3",
        quality_policy=DataQualityPolicy(enabled=True, min_chars=2, exact_dedup=True),
        chunk_bytes=300,
        progress_interval_seconds=0,
    )
    build_tokenizer_sample(request, dataset_loader=_fake_telco_loader)

    def reject_materialization(_journal):
        raise AssertionError("resume must stream journal units")

    monkeypatch.setattr(BuildJournal, "units", reject_materialization)

    resumed = build_tokenizer_sample(request, dataset_loader=_fake_telco_loader)

    assert resumed["complete"] is True


def test_chunk_writer_does_not_retain_all_encoded_chunk_payloads(tmp_path: Path):
    shared_text = "x" * 524_288
    records = [
        {"content_sha256": f"{index:064x}", "text": shared_text}
        for index in range(12)
    ]
    tracemalloc.start()
    try:
        artifacts, next_index = _write_chunks(
            tmp_path,
            "fit",
            records,
            chunk_bytes=530_000,
            start_index=0,
        )
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert len(artifacts) == 12
    assert next_index == 12
    assert peak_bytes < 4_000_000


def test_sample_manifest_persists_the_supplied_build_provenance(tmp_path: Path):
    registry = load_source_registry("configs/data/telco_300m_sources.yaml")
    provenance = {
        "version": 1,
        "workflow": "test_tokenizer_sample",
        "target_estimated_tokens": 2_000,
        "role_quotas": {"pretrain_general": 2_000},
        "plan": {"sha256": "1" * 64},
        "recipe": {"sha256": "2" * 64},
        "sources": {"sha256": "3" * 64},
        "quality_policy": {"sha256": "4" * 64},
        "contamination_evidence": {"sha256": "5" * 64},
        "format": {"version": 3},
    }
    request = LocalSampleRequest(
        registry=registry,
        plan=_tiny_plan(),
        output_dir=tmp_path / "sample",
        state_path=tmp_path / "state" / "tokenizer_sample.sqlite3",
        quality_policy=DataQualityPolicy(enabled=True, min_chars=2, exact_dedup=True),
        chunk_bytes=300,
        progress_interval_seconds=0,
        build_provenance=provenance,
    )

    manifest = build_tokenizer_sample(request, dataset_loader=_fake_telco_loader)

    assert manifest["version"] == 3
    assert manifest["build_provenance"] == provenance
    assert len(manifest["build_provenance_sha256"]) == 64


def test_sampler_exact_dedup_does_not_retain_every_accepted_hash_in_memory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    registry = load_source_registry("configs/data/telco_300m_sources.yaml")
    plan = _tiny_plan()
    plan["total_tokens"] = 50_000
    plan["role_quotas"] = {"pretrain_general": 50_000}
    plan["items"][0]["token_quota"] = 50_000
    captured_filters = []
    real_filter = local_sample.QualityFilter

    class CapturingQualityFilter(real_filter):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured_filters.append(self)

    monkeypatch.setattr(local_sample, "QualityFilter", CapturingQualityFilter)
    request = LocalSampleRequest(
        registry=registry,
        plan=plan,
        output_dir=tmp_path / "sample",
        state_path=tmp_path / "state" / "tokenizer_sample.sqlite3",
        quality_policy=DataQualityPolicy(enabled=True, min_chars=2, exact_dedup=True),
        chunk_bytes=2_000,
        progress_interval_seconds=0,
    )

    manifest = build_tokenizer_sample(request, dataset_loader=_large_fake_telco_loader)

    assert manifest["accepted_documents"] > 100
    assert len(captured_filters) == 1
    assert len(captured_filters[0].seen_hashes) <= plan["buffer_size"]


@pytest.mark.parametrize("escaped_component", ("sample", "fit", "state"))
def test_sample_refuses_symlinked_managed_descendants_before_mutation(
    tmp_path: Path, escaped_component: str
):
    registry = load_source_registry("configs/data/telco_300m_sources.yaml")
    work = tmp_path / "work"
    outside = tmp_path / "outside"
    work.mkdir()
    outside.mkdir()
    outside_marker = outside / "keep.txt"
    outside_marker.write_text("keep\n", encoding="utf-8")
    sample = work / "tokenizer_sample"
    state = work / "state"
    state_path = state / "tokenizer_sample.sqlite3"

    if escaped_component == "sample":
        sample.symlink_to(outside, target_is_directory=True)
    elif escaped_component == "fit":
        sample.mkdir()
        (sample / "fit").symlink_to(outside, target_is_directory=True)
        (outside / "fit_00000.jsonl.tmp").write_text(
            "must not be deleted\n", encoding="utf-8"
        )
    else:
        state.symlink_to(outside, target_is_directory=True)

    request = LocalSampleRequest(
        registry=registry,
        plan=_tiny_plan(),
        output_dir=sample,
        state_path=state_path,
        quality_policy=DataQualityPolicy(enabled=True, min_chars=2, exact_dedup=True),
        chunk_bytes=300,
        progress_interval_seconds=0,
    )

    with pytest.raises(ValueError, match="managed path|symbolic link"):
        build_tokenizer_sample(request, dataset_loader=_fake_telco_loader)

    assert outside_marker.read_text(encoding="utf-8") == "keep\n"
    if escaped_component == "fit":
        assert (outside / "fit_00000.jsonl.tmp").read_text(encoding="utf-8") == (
            "must not be deleted\n"
        )
    if escaped_component != "state":
        assert not state_path.exists()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("chunk_bytes", 0, "chunk_bytes must be positive"),
        (
            "progress_interval_seconds",
            -1,
            "progress_interval_seconds must be non-negative",
        ),
    ),
)
def test_sample_request_rejects_invalid_bounds(
    tmp_path: Path, field: str, value: int, message: str
):
    registry = load_source_registry("configs/data/telco_300m_sources.yaml")
    kwargs = {
        "registry": registry,
        "plan": _tiny_plan(),
        "output_dir": tmp_path / "sample",
        "state_path": tmp_path / "state.sqlite3",
        "quality_policy": DataQualityPolicy(enabled=True),
        field: value,
    }

    with pytest.raises(ValueError, match=message):
        build_tokenizer_sample(
            LocalSampleRequest(**kwargs), dataset_loader=_fake_telco_loader
        )
