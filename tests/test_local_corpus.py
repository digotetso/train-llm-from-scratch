import json
import multiprocessing
import os
import signal
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from matgpt.data.local_corpus import LocalCorpusRequest, build_local_corpus
from matgpt.data.local_publish import StoragePressure
from matgpt.data.quality import DataQualityPolicy
from matgpt.data.sources import load_source_registry
from matgpt.tokenizer.train import train_tokenizer_from_jsonl
from matgpt.utils.hashing import sha256_file, sha256_json


REGISTRY_PATH = Path("configs/data/telco_300m_sources.yaml")


def _tiny_plan(stage: str) -> dict:
    items = [
        {"id": "common_pile_wikimedia", "source_id": "common_pile_wikimedia", "bucket_id": None, "role": "pretrain_general", "token_quota": 12},
        {"id": "common_pile_github_archive", "source_id": "common_pile_github_archive", "bucket_id": None, "role": "pretrain_structured", "token_quota": 12},
    ]
    for bucket in ("three_gpp", "rfc", "research", "patents", "semantic"):
        items.append({"id": f"telco_common_corpus/{bucket}", "source_id": "telco_common_corpus", "bucket_id": bucket, "role": "pretrain_telecom", "token_quota": 12})
    return {"version": 1, "stage": stage, "seed": 42, "total_tokens": 84, "quota_tolerance": 0.03, "validation_fraction": 0.0, "buffer_size": 3, "role_quotas": {"pretrain_general": 12, "pretrain_structured": 12, "pretrain_telecom": 60}, "items": sorted(items, key=lambda item: item["id"]), "plan_sha256": (stage + "0" * 64)[:64]}


def _rows(kind: str) -> list[dict]:
    if kind == "general":
        return [{"text": f"general router prose {index}"} for index in range(50)]
    if kind == "structured":
        return [{"text": f"interface route code {index}"} for index in range(50)]
    collections = {"3GPP-TSG": "3GPP license", "IETF-RFCs": "IETF license", "IEEE-Access": "CC-BY-4.0", "USPTO": "public domain", "Wikidata-Telecom": "CC0-1.0"}
    return [{"identifier": f"{collection}-{index}", "collection": collection, "license": license_name, "token_count": 4, "text": f"telecom {collection} document {index}"} for collection, license_name in collections.items() for index in range(50)]


def _loader(hf_name: str, **kwargs):
    if hf_name == "GSMA/Telco-Common-Corpus":
        return iter(_rows("telecom"))
    paths = kwargs.get("data_files") or []
    return iter(_rows("structured" if any("github_archive" in path for path in paths) else "general"))


def _write_tokenizer(root: Path) -> Path:
    tokenizer_dir = root / "tokenizer"
    fitting = root / "tokenizer_fit.jsonl"
    texts = ["general router prose interface route code telecom document", "🙂 café 你好 A space, then punctuation!", "3GPP RRC O-RAN IPv6 packet forwarding radio access network"]
    fitting.write_text("".join(json.dumps({"text": text}) + "\n" for text in texts), encoding="utf-8")
    train_tokenizer_from_jsonl([fitting], tokenizer_dir, vocab_size=320, min_frequency=1, special_tokens=["<|pad|>", "<|bos|>", "<|eos|>", "<|system|>", "<|user|>", "<|assistant|>", "<|end|>"])
    return tokenizer_dir


def make_corpus_request(root: Path, *, plans: list[dict], retry_delays: tuple[float, ...] = (0.0,)) -> LocalCorpusRequest:
    root.mkdir(parents=True, exist_ok=True)
    tokenizer_dir = _write_tokenizer(root)
    tokenizer_sha = sha256_file(tokenizer_dir / "tokenizer.json")
    selection = root / "tokenizer_selection.json"
    comparison = {
        "labels": {"baseline": "pilot_20m", "candidate": "representative_200m"},
        "baseline_label": "pilot_20m",
        "candidate_label": "representative_200m",
        "shared_evidence_valid": True,
        "side_validity": {"baseline": True, "candidate": True},
        "baseline": {"tokenizer_sha256": "a" * 64},
        "candidate": {"tokenizer_sha256": tokenizer_sha},
        "fingerprints": {"baseline_tokenizer_sha256": "a" * 64, "candidate_tokenizer_sha256": tokenizer_sha},
    }
    comparison["comparison_sha256"] = sha256_json(comparison)
    (root / "comparison.json").write_text(json.dumps(comparison, sort_keys=True) + "\n", encoding="utf-8")
    selection.write_text(json.dumps({"version": 1, "approved": True, "winner": "representative_200m", "selected_tokenizer_sha256": tokenizer_sha, "comparison_sha256": comparison["comparison_sha256"], "operator_timestamp": "2026-08-09T00:00:00+00:00"}, sort_keys=True) + "\n", encoding="utf-8")
    return LocalCorpusRequest(registry=load_source_registry(REGISTRY_PATH), plans=tuple(plans), tokenizer_dir=tokenizer_dir, tokenizer_selection_path=selection, evidence_root=root, local_root=root / "local", destination_root=root / "drive", quality_policy=DataQualityPolicy(enabled=True, min_chars=2, exact_dedup=True, contamination_patterns=["heldout contamination evidence"]), batch_documents=4, shard_size_tokens=24, raw_unit_bytes=2_048, max_working_bytes=20 * 1024**2, min_free_bytes=1, progress_interval_seconds=0, retry_delays=retry_delays)


def _artifact_bytes(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file() and path.suffix in {".jsonl", ".bin"}}


def _sigint_child(root: str, queue) -> None:
    """Process target: deliver a genuine SIGINT while a corpus unit is running."""

    request = make_corpus_request(Path(root), plans=[_tiny_plan("main")])
    previous = signal.getsignal(signal.SIGINT)

    def interrupt_after_commit(_unit) -> None:
        os.kill(os.getpid(), signal.SIGINT)

    result = build_local_corpus(
        request, dataset_loader=_loader, on_unit_committed=interrupt_after_commit
    )
    queue.put((result.status, signal.getsignal(signal.SIGINT) == previous))


def test_builder_counts_once_and_deduplicates_across_stages(tmp_path: Path, monkeypatch):
    import matgpt.data.local_corpus as local_corpus

    encode_calls = Counter()
    real_encode = local_corpus.encode_record_batch
    batch_sizes = []

    def observed_encode(tokenizer, records):
        batch_sizes.append(len(records))
        encode_calls.update(record["content_sha256"] for record in records)
        return real_encode(tokenizer, records)

    monkeypatch.setattr(local_corpus, "encode_record_batch", observed_encode)
    result = build_local_corpus(make_corpus_request(tmp_path, plans=[_tiny_plan("main"), _tiny_plan("cooldown")]), dataset_loader=_loader)

    assert result.status == "provisional_complete"
    # Post-quota encodings are intentionally not remembered across stages:
    # they remain eligible for a later stage unless durably accepted.
    assert all(count <= 2 for count in encode_calls.values())
    assert max(batch_sizes) <= 4
    assert result.manifest["quota_counting"]["method"] == "tokenizer_exact_one_pass"
    assert result.manifest["quality_filter"]["exact_dedup"] is True
    assert result.manifest["complete"] is False


def test_forced_interruption_resumes_byte_identically(tmp_path: Path):
    resumed_request = make_corpus_request(tmp_path / "resume", plans=[_tiny_plan("main")])
    commits = 0

    def stop_after_second(_unit):
        nonlocal commits
        commits += 1
        if commits == 2:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        build_local_corpus(resumed_request, dataset_loader=_loader, on_unit_committed=stop_after_second)
    resumed = build_local_corpus(resumed_request, dataset_loader=_loader)
    clean_request = make_corpus_request(tmp_path / "clean", plans=[_tiny_plan("main")])
    clean = build_local_corpus(clean_request, dataset_loader=_loader)

    assert resumed.manifest["content_sha256"] == clean.manifest["content_sha256"]
    assert _artifact_bytes(resumed_request.destination_root) == _artifact_bytes(clean_request.destination_root)


def test_calibration_stop_resumes_same_identity(tmp_path: Path):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    calibrated = build_local_corpus(request, dataset_loader=_loader, stop_after_quota_tokens=24)

    assert calibrated.status == "calibration_complete"
    assert calibrated.accepted_quota_tokens >= 24
    completed = build_local_corpus(request, dataset_loader=_loader)

    assert completed.status == "provisional_complete"
    assert completed.build_identity_sha256 == calibrated.build_identity_sha256


def test_transient_loader_failure_retries_from_committed_cursor(tmp_path: Path):
    attempts = 0

    def flaky_loader(hf_name: str, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("temporary network failure")
        return _loader(hf_name, **kwargs)

    result = build_local_corpus(make_corpus_request(tmp_path, plans=[_tiny_plan("main")]), dataset_loader=flaky_loader)

    assert result.status == "provisional_complete"
    assert attempts >= 2


def test_unknown_telco_collection_and_missing_license_fail_without_manifest(tmp_path: Path):
    def drifting_loader(hf_name: str, **kwargs):
        if hf_name == "GSMA/Telco-Common-Corpus":
            return iter([{"identifier": "bad-1", "collection": "UNREVIEWED-COLLECTION", "license": "", "token_count": 4, "text": "schema drift"}])
        return _loader(hf_name, **kwargs)

    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    with pytest.raises(ValueError, match="unknown collection"):
        build_local_corpus(request, dataset_loader=drifting_loader)

    assert not (request.destination_root / "manifest.json").exists()


def test_source_exhaustion_fails_without_rebalancing(tmp_path: Path):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    with pytest.raises(ValueError, match="exhausted before quota"):
        build_local_corpus(request, dataset_loader=lambda _name, **_kwargs: iter(()))

    assert not (request.destination_root / "manifest.json").exists()


def test_builder_rejects_unapproved_or_incomplete_selection_before_opening_state(tmp_path: Path):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    request.tokenizer_selection_path.write_text(
        json.dumps({"approved": True, "selected_tokenizer_sha256": "0" * 64}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid schema"):
        build_local_corpus(request, dataset_loader=_loader)

    assert not (request.local_root / "corpus.sqlite3").exists()


def test_builder_rejects_selection_without_matching_sibling_comparison(tmp_path: Path):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    (request.tokenizer_selection_path.parent / "comparison.json").unlink()

    with pytest.raises(ValueError, match="comparison"):
        build_local_corpus(request, dataset_loader=_loader)

    assert not (request.local_root / "corpus.sqlite3").exists()


def test_evidence_root_and_atomic_destination_mapping_are_canonical(tmp_path: Path):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    request = replace(request, evidence_root=tmp_path / "other")
    with pytest.raises(ValueError, match="evidence_root"):
        build_local_corpus(request, dataset_loader=_loader)

    request = make_corpus_request(tmp_path / "valid", plans=[_tiny_plan("main")])
    build_local_corpus(request, dataset_loader=_loader, stop_after_quota_tokens=24)
    import sqlite3
    with sqlite3.connect(request.local_root / "corpus.sqlite3") as connection:
        assert connection.execute("SELECT count(*) FROM artifacts WHERE destination_relative_path IS NULL").fetchone()[0] == 0


def test_builder_requires_enabled_dedup_and_contamination_controls(tmp_path: Path):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    request = replace(
        request,
        quality_policy=DataQualityPolicy(enabled=False, exact_dedup=False, contamination_patterns=[]),
    )

    with pytest.raises(ValueError, match="quality controls"):
        build_local_corpus(request, dataset_loader=_loader)

    assert not (request.local_root / "corpus.sqlite3").exists()


def test_only_first_encoded_document_that_reaches_item_quota_is_committed(tmp_path: Path):
    plan = _tiny_plan("main")
    plan["items"] = [
        {"id": "common_pile_wikimedia", "source_id": "common_pile_wikimedia", "bucket_id": None, "role": "pretrain_general", "token_quota": 1}
    ]
    plan["role_quotas"] = {"pretrain_general": 1}
    plan["total_tokens"] = 1
    request = make_corpus_request(tmp_path, plans=[plan])

    result = build_local_corpus(request, dataset_loader=_loader)

    assert result.accepted_quota_tokens >= 1
    import sqlite3
    with sqlite3.connect(request.local_root / "corpus.sqlite3") as connection:
        assert connection.execute("SELECT count(*) FROM seen_hashes").fetchone()[0] == 1
    assert not (request.destination_root / "manifest.json").exists()


def test_missing_document_license_fails_without_manifest(tmp_path: Path):
    def missing_license_loader(hf_name: str, **kwargs):
        if hf_name == "GSMA/Telco-Common-Corpus":
            return iter([{"identifier": "rfc-1", "collection": "IETF-RFCs", "license": "", "token_count": 4, "text": "license missing"}])
        return _loader(hf_name, **kwargs)

    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    with pytest.raises(ValueError, match="document-level license"):
        build_local_corpus(request, dataset_loader=missing_license_loader)

    assert not (request.destination_root / "manifest.json").exists()


def test_builder_writes_atomic_progress_evidence(tmp_path: Path):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])

    build_local_corpus(request, dataset_loader=_loader, stop_after_quota_tokens=24)

    progress = json.loads((request.local_root / "progress.json").read_text(encoding="utf-8"))
    assert progress["status"] == "calibration_complete"
    assert progress["accepted_quota_tokens"] >= 24
    assert not (request.local_root / "progress.json.partial").exists()


def test_unit_commit_persists_cumulative_evidence_and_progress_schema(tmp_path: Path):
    """A restart derives all counters from the single atomic unit commit."""

    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    result = build_local_corpus(request, dataset_loader=_loader, stop_after_quota_tokens=24)

    import sqlite3
    with sqlite3.connect(request.local_root / "corpus.sqlite3") as connection:
        state = json.loads(connection.execute("SELECT state_json FROM units ORDER BY unit_id DESC LIMIT 1").fetchone()[0])
    progress = json.loads((request.local_root / "progress.json").read_text(encoding="utf-8"))

    assert result.status == "calibration_complete"
    assert state["cumulative"]["accepted"]["tokens"] == result.accepted_quota_tokens
    assert state["cumulative"]["quality"]["contamination_patterns_sha256"]
    assert state["cumulative"]["last_unit"]
    assert progress["item_quotas"]
    assert progress["rejected"]
    assert progress["storage"]


def test_iteration_timeout_restarts_from_last_committed_cursor(tmp_path: Path):
    """A transient failure raised while consuming a stream resumes without rehashing rows."""

    calls = 0

    def flaky_stream(hf_name: str, **kwargs):
        nonlocal calls
        calls += 1
        rows = _loader(hf_name, **kwargs)
        if calls != 2:
            return rows

        def iterator():
            for index, row in enumerate(rows):
                if index == 4:
                    raise TimeoutError("stream interrupted")
                yield row
        return iterator()

    result = build_local_corpus(
        make_corpus_request(tmp_path, plans=[_tiny_plan("main")]), dataset_loader=flaky_stream
    )

    assert result.status == "provisional_complete"
    assert calls > 2


def test_completed_windows_accumulate_before_bounded_unit_seal(tmp_path: Path):
    plan = _tiny_plan("main")
    plan["items"] = [{"id": "common_pile_wikimedia", "source_id": "common_pile_wikimedia", "bucket_id": None, "role": "pretrain_general", "token_quota": 80}]
    plan["role_quotas"] = {"pretrain_general": 80}
    plan["total_tokens"] = 80
    request = replace(
        make_corpus_request(tmp_path, plans=[plan]), raw_unit_bytes=20_000, shard_size_tokens=10_000
    )

    result = build_local_corpus(request, dataset_loader=_loader)

    assert result.status == "provisional_complete"
    assert len(list((request.destination_root / "units").iterdir())) == 1


def test_fresh_restart_recovers_crashes_at_seal_commit_and_publish_boundaries(tmp_path: Path, monkeypatch):
    """Only pre-commit managed files are removed; committed work is reconciled."""

    import matgpt.data.local_corpus as local_corpus

    request = make_corpus_request(tmp_path / "resumed", plans=[_tiny_plan("main")])
    real_seal = local_corpus._seal_unit

    def crash_after_seal(*args, **kwargs):
        real_seal(*args, **kwargs)
        raise RuntimeError("after-seal")

    monkeypatch.setattr(local_corpus, "_seal_unit", crash_after_seal)
    with pytest.raises(RuntimeError, match="after-seal"):
        build_local_corpus(request, dataset_loader=_loader)
    monkeypatch.setattr(local_corpus, "_seal_unit", real_seal)
    assert any((request.local_root / "units").rglob("*"))

    # Restart deletes only the unreferenced sealed unit, then complete it.
    resumed = build_local_corpus(request, dataset_loader=_loader)
    clean_request = make_corpus_request(tmp_path / "clean", plans=[_tiny_plan("main")])
    clean = build_local_corpus(clean_request, dataset_loader=_loader)
    assert resumed.manifest["content_sha256"] == clean.manifest["content_sha256"]
    assert _artifact_bytes(request.destination_root) == _artifact_bytes(clean_request.destination_root)

    post_commit = make_corpus_request(tmp_path / "post-commit", plans=[_tiny_plan("main")])
    from matgpt.data.local_publish import DrivePublisher
    real_publish = DrivePublisher.publish
    calls = 0

    def crash_before_publish(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("post-commit-pre-publish")
        return real_publish(self, *args, **kwargs)

    monkeypatch.setattr(DrivePublisher, "publish", crash_before_publish)
    with pytest.raises(RuntimeError, match="post-commit-pre-publish"):
        build_local_corpus(post_commit, dataset_loader=_loader)
    monkeypatch.setattr(DrivePublisher, "publish", real_publish)
    recovered = build_local_corpus(post_commit, dataset_loader=_loader)
    assert recovered.status == "provisional_complete"

    post_mark = make_corpus_request(tmp_path / "post-mark", plans=[_tiny_plan("main")])
    real_record = DrivePublisher._record_then_release
    marked = 0

    def crash_after_mark(self, publication):
        nonlocal marked
        real_record(self, publication)
        marked += 1
        if marked == 1:
            raise RuntimeError("after-mark-before-next-publish")

    monkeypatch.setattr(DrivePublisher, "_record_then_release", crash_after_mark)
    with pytest.raises(RuntimeError, match="after-mark-before-next-publish"):
        build_local_corpus(post_mark, dataset_loader=_loader)
    monkeypatch.setattr(DrivePublisher, "_record_then_release", real_record)
    assert build_local_corpus(post_mark, dataset_loader=_loader).status == "provisional_complete"


def test_subprocess_sigint_stops_after_durable_window_and_restores_handler(tmp_path: Path):
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=_sigint_child, args=(str(tmp_path), queue))
    process.start()
    process.join(60)
    assert process.exitcode == 0
    assert queue.get(timeout=5) == ("stopped_cleanly", True)


def test_sigint_request_stops_cleanly_at_a_committed_window_boundary(tmp_path: Path):
    import matgpt.data.local_corpus as local_corpus

    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])

    def request_stop(_unit):
        local_corpus._STOP_REQUESTED = True

    result = build_local_corpus(request, dataset_loader=_loader, on_unit_committed=request_stop)

    assert result.status == "stopped_cleanly"
    assert result.accepted_quota_tokens > 0
    assert json.loads((request.local_root / "progress.json").read_text(encoding="utf-8"))["status"] == "stopped_cleanly"


def test_startup_removes_uncommitted_partials_after_identity_validation(tmp_path: Path):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    partial = request.local_root / "units" / "orphan.bin.partial"
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b"partial")

    result = build_local_corpus(request, dataset_loader=_loader, stop_after_quota_tokens=24)

    assert result.status == "calibration_complete"
    assert not partial.exists()


def test_startup_removes_uncommitted_sealed_artifacts_before_resume(tmp_path: Path):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    orphan = request.local_root / "units" / "orphan" / "fit.jsonl"
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"sealed but uncommitted\n")
    binary = orphan.with_name("fit_00000.bin")
    binary.write_bytes(b"\x00\x00")

    result = build_local_corpus(request, dataset_loader=_loader, stop_after_quota_tokens=24)

    assert result.status == "calibration_complete"
    assert not orphan.exists()
    assert not binary.exists()


def test_raw_records_preserve_upstream_source_split(tmp_path: Path):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    build_local_corpus(request, dataset_loader=_loader, stop_after_quota_tokens=24)

    raw = next(request.destination_root.rglob("fit.jsonl"))
    record = json.loads(raw.read_text(encoding="utf-8").splitlines()[0])
    assert record["source_split"] == "train"
    assert record["split"] == "fit"


def test_builder_checks_storage_before_sealing_a_unit(tmp_path: Path):
    request = replace(
        make_corpus_request(tmp_path, plans=[_tiny_plan("main")]),
        max_working_bytes=1,
    )

    with pytest.raises(StoragePressure, match="working-set cap"):
        build_local_corpus(request, dataset_loader=_loader)

    assert not (request.destination_root / "manifest.json").exists()
