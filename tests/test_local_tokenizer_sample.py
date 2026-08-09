from pathlib import Path

import pytest

from matgpt.data.local_sample import LocalSampleRequest, build_tokenizer_sample
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


def test_sample_holdout_is_disjoint_and_progress_reports_quota(tmp_path: Path):
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
    fit_hashes = set(manifest["fit_content_sha256"])
    holdout_hashes = set(manifest["holdout_content_sha256"])

    assert fit_hashes.isdisjoint(holdout_hashes)
    assert events[-1].accepted_estimated_tokens >= tiny_plan["total_tokens"]
    assert events[-1].requested_estimated_tokens == tiny_plan["total_tokens"]


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
