import json
import multiprocessing
import os
import shutil
import signal
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from matgpt.config import clone_config, load_config
from matgpt.data.local_corpus import LocalCorpusRequest, build_local_corpus
from matgpt.data.local_publish import StoragePressure
from matgpt.data.quality import DataQualityPolicy
from matgpt.data.sources import load_source_registry
from matgpt.data.telco_prepare import (
    corpus_has_exact_token_quotas,
    iter_corpus_split_records,
)
from matgpt.tokenizer.train import train_tokenizer_from_jsonl
from matgpt.preflight import build_preflight_report
from matgpt.utils.hashing import sha256_file, sha256_json, sha256_text


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


def _last_cumulative(request: LocalCorpusRequest) -> dict:
    import sqlite3

    with sqlite3.connect(request.local_root / "corpus.sqlite3") as connection:
        row = connection.execute(
            "SELECT state_json FROM units ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    assert row is not None
    return json.loads(row[0])["cumulative"]


def _single_source_plan(
    stage: str, *, token_quota: int = 20, validation_fraction: float = 0.4,
    buffer_size: int = 2,
) -> dict:
    item = {
        "id": "common_pile_wikimedia",
        "source_id": "common_pile_wikimedia",
        "bucket_id": None,
        "role": "pretrain_general",
        "token_quota": token_quota,
    }
    return {
        "version": 1,
        "stage": stage,
        "seed": 42,
        "total_tokens": token_quota,
        "quota_tolerance": 0.03,
        "validation_fraction": validation_fraction,
        "buffer_size": buffer_size,
        "role_quotas": {"pretrain_general": token_quota},
        "items": [item],
        "plan_sha256": (stage + "0" * 64)[:64],
    }


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

    assert result.status == "complete"
    # Post-quota encodings are intentionally not remembered across stages:
    # they remain eligible for a later stage unless durably accepted.
    assert all(count <= 2 for count in encode_calls.values())
    assert max(batch_sizes) <= 4
    assert result.manifest["quota_counting"]["method"] == "tokenizer_exact_one_pass"
    assert result.manifest["quality_filter"]["exact_dedup"] is True
    assert result.manifest["complete"] is True


def test_complete_build_finalizes_committed_units_and_publishes_manifest_last(
    tmp_path: Path,
):
    plans = [_tiny_plan("main"), _tiny_plan("cooldown")]
    request = make_corpus_request(tmp_path / "complete", plans=plans)

    result = build_local_corpus(request, dataset_loader=_loader)

    assert result.status == "complete"
    assert result.manifest is not None
    assert result.manifest["complete"] is True
    assert result.manifest["storage_format"] == "chunked_prebuilt_v1"
    assert result.manifest["build_identity_sha256"] == result.build_identity_sha256
    assert corpus_has_exact_token_quotas(
        request.destination_root, request.tokenizer_dir, plans
    )
    assert (request.destination_root / "manifest.json").is_file()
    for name in (
        "quota_audit.json",
        "license_audit.json",
        "quality_audit.json",
        "overlap_audit.json",
        "calibration_report.json",
        "main_metadata.json",
        "cooldown_metadata.json",
    ):
        assert (request.destination_root / name).is_file(), name
    for split, stats in result.manifest["split_stats"].items():
        assert stats["document_count"] > 0
        assert stats["raw_chunks"]
        assert all(not Path(chunk["path"]).is_absolute() for chunk in stats["raw_chunks"])
    main = result.manifest["stages"]["main"]
    assert main["items"]["common_pile_wikimedia"]["documents"] > 0
    assert main["roles"]["pretrain_general"]["documents"] > 0
    assert result.manifest["breakdowns"]["sources"][
        "main:common_pile_wikimedia"
    ]["characters"] > 0
    assert result.manifest["breakdowns"]["buckets"][
        "main:telco_common_corpus/rfc"
    ]["packed_tokens"] > 0


def test_calibration_remains_provisional_and_never_writes_manifest(tmp_path: Path):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])

    result = build_local_corpus(
        request, dataset_loader=_loader, stop_after_quota_tokens=24
    )

    assert result.status == "calibration_complete"
    assert result.manifest is None
    assert not (request.destination_root / "manifest.json").exists()
    assert (request.destination_root / "calibration_report.json").is_file()


def test_calibration_refuses_valid_existing_evidence_from_another_build(tmp_path: Path):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    request.destination_root.mkdir()
    payload = {
        "version": 1,
        "status": "calibration_complete",
        "build_identity_sha256": "0" * 64,
        "accepted_quota_tokens": 1,
        "committed_units": 1,
        "elapsed_seconds": 1.0,
        "peak_rss_bytes": 1,
    }
    payload["calibration_report_sha256"] = sha256_json(payload)
    path = request.destination_root / "calibration_report.json"
    original = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(original)

    with pytest.raises(ValueError, match="calibration.*identity"):
        build_local_corpus(
            request, dataset_loader=_loader, stop_after_quota_tokens=24
        )

    assert path.read_bytes() == original
    assert not (request.destination_root / "manifest.json").exists()


def test_finalization_refuses_inconsistent_journaled_quality_counts(tmp_path: Path):
    import sqlite3

    plan = _single_source_plan(
        "main", token_quota=1, validation_fraction=0.0, buffer_size=2
    )
    request = make_corpus_request(tmp_path, plans=[plan])
    build_local_corpus(
        request, dataset_loader=_loader, stop_after_quota_tokens=1
    )
    with sqlite3.connect(request.local_root / "corpus.sqlite3") as connection:
        rowid, encoded = connection.execute(
            "SELECT rowid, state_json FROM units ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        state = json.loads(encoded)
        state["cumulative"]["quality"]["rejected_documents"] += 1
        connection.execute(
            "UPDATE units SET state_json = ? WHERE rowid = ?",
            (json.dumps(state, sort_keys=True), rowid),
        )

    with pytest.raises(ValueError, match="quality.*reconcile"):
        build_local_corpus(request, dataset_loader=_loader)

    assert not (request.destination_root / "manifest.json").exists()


def test_finalization_crash_resumes_without_provider_read_or_reencoding(
    tmp_path: Path, monkeypatch
):
    import matgpt.data.local_corpus as local_corpus

    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    real_publish = local_corpus._publish_json_evidence
    crashed = False

    def crash_after_quality(publisher, relative_path, payload):
        nonlocal crashed
        artifact = real_publish(publisher, relative_path, payload)
        if relative_path == "quality_audit.json" and not crashed:
            crashed = True
            raise RuntimeError("crash-after-quality-audit")
        return artifact

    monkeypatch.setattr(local_corpus, "_publish_json_evidence", crash_after_quality)
    with pytest.raises(RuntimeError, match="crash-after-quality-audit"):
        build_local_corpus(request, dataset_loader=_loader)
    assert not (request.destination_root / "manifest.json").exists()

    monkeypatch.setattr(local_corpus, "_publish_json_evidence", real_publish)

    def unexpected_provider(*_args, **_kwargs):
        raise AssertionError("finalization resume must not reopen the provider")

    monkeypatch.setattr(local_corpus, "encode_record_batch", unexpected_provider)
    result = build_local_corpus(request, dataset_loader=unexpected_provider)

    assert result.status == "complete"
    assert result.manifest["complete"] is True


def test_final_raw_chunk_reader_rejects_changed_or_traversing_artifacts(tmp_path: Path):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    result = build_local_corpus(request, dataset_loader=_loader)

    records = list(iter_corpus_split_records(request.destination_root, "main"))
    assert len(records) == result.manifest["split_stats"]["main"]["document_count"]

    chunk = request.destination_root / result.manifest["split_stats"]["main"][
        "raw_chunks"
    ][0]["path"]
    original = chunk.read_bytes()
    chunk.write_bytes(original + b"{}\n")
    with pytest.raises(ValueError, match="checksum|size"):
        list(iter_corpus_split_records(request.destination_root, "main"))

    chunk.write_bytes(original)
    manifest_path = request.destination_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["split_stats"]["main"]["raw_chunks"][0]["path"] = "../outside.jsonl"
    manifest.pop("manifest_sha256")
    manifest["manifest_sha256"] = sha256_json(manifest)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="safe relative|escapes"):
        list(iter_corpus_split_records(request.destination_root, "main"))


def _local_preflight_config(tmp_path: Path, request: LocalCorpusRequest) -> dict:
    cfg = clone_config(load_config("configs/matgpt_telco_300m.yaml"))
    cfg["run"]["output_dir"] = str(tmp_path / "run")
    cfg["dataset"]["normalized_dir"] = str(request.destination_root)
    cfg["dataset"]["train_split"] = "main"
    cfg["dataset"]["validation_split"] = "validation"
    cfg["dataset"]["training_splits"] = {"main": "main"}
    cfg["tokenizer"]["output_dir"] = str(request.tokenizer_dir)
    cfg["tokenizer"]["vocab_size"] = 320
    cfg["model"]["vocab_size"] = 320
    cfg["model"]["context_length"] = 8
    cfg["sharding"]["output_dir"] = str(request.destination_root)
    cfg["sharding"]["shard_size_tokens"] = request.shard_size_tokens
    cfg["training"]["max_tokens"] = 40
    cfg["training"]["data_phases"] = [
        {"name": "main", "split": "main", "until_tokens": 40}
    ]
    return cfg


def test_finalized_local_corpus_passes_preflight_without_raw_rescan(
    tmp_path: Path, monkeypatch
):
    plan = _single_source_plan(
        "main", token_quota=40, validation_fraction=0.4, buffer_size=2
    )
    request = make_corpus_request(tmp_path, plans=[plan])
    build_local_corpus(request, dataset_loader=_loader)
    cfg = _local_preflight_config(tmp_path, request)

    import matgpt.preflight as preflight

    def unexpected_raw_scan(_path):
        raise AssertionError("chunked preflight must consume signed audits")

    monkeypatch.setattr(preflight, "_normalized_split_evidence", unexpected_raw_scan)
    report = build_preflight_report(cfg, require_t4=False, min_free_disk_gb=0)

    assert report["status"] == "pass", report


@pytest.mark.parametrize("failure", ("changed", "traversal"))
def test_finalized_local_corpus_preflight_fails_closed_on_audit_drift(
    tmp_path: Path, failure: str
):
    plan = _single_source_plan(
        "main", token_quota=40, validation_fraction=0.4, buffer_size=2
    )
    request = make_corpus_request(tmp_path, plans=[plan])
    build_local_corpus(request, dataset_loader=_loader)
    cfg = _local_preflight_config(tmp_path, request)
    manifest_path = request.destination_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if failure == "changed":
        audit = request.destination_root / "quota_audit.json"
        audit.write_bytes(audit.read_bytes() + b" ")
    else:
        manifest["audits"]["quota_audit"]["path"] = "../quota_audit.json"
        manifest.pop("manifest_sha256")
        manifest["manifest_sha256"] = sha256_json(manifest)
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
        )

    report = build_preflight_report(cfg, require_t4=False, min_free_disk_gb=0)

    assert report["status"] == "fail"
    manifest_check = next(
        check for check in report["checks"] if check["name"] == "dataset_manifest"
    )
    assert manifest_check["status"] == "fail"


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
    resumed_evidence = _last_cumulative(resumed_request)
    clean_evidence = _last_cumulative(clean_request)
    resumed_evidence.pop("progress", None)
    clean_evidence.pop("progress", None)
    assert resumed_evidence == clean_evidence


def test_calibration_stop_resumes_same_identity(tmp_path: Path):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    calibrated = build_local_corpus(request, dataset_loader=_loader, stop_after_quota_tokens=24)

    assert calibrated.status == "calibration_complete"
    assert calibrated.accepted_quota_tokens >= 24
    completed = build_local_corpus(request, dataset_loader=_loader)

    assert completed.status == "complete"
    assert completed.build_identity_sha256 == calibrated.build_identity_sha256


def test_two_stage_calibration_resume_matches_uninterrupted_content_and_bytes(tmp_path: Path):
    plans = [_tiny_plan("main"), _tiny_plan("cooldown")]
    resumed_request = make_corpus_request(tmp_path / "resumed", plans=plans)

    calibrated = build_local_corpus(
        resumed_request, dataset_loader=_loader, stop_after_quota_tokens=24
    )
    resumed = build_local_corpus(resumed_request, dataset_loader=_loader)

    clean_request = make_corpus_request(tmp_path / "clean", plans=plans)
    clean = build_local_corpus(clean_request, dataset_loader=_loader)

    assert calibrated.status == "calibration_complete"
    assert resumed.manifest["content_sha256"] == clean.manifest["content_sha256"]
    assert _artifact_bytes(resumed_request.destination_root) == _artifact_bytes(
        clean_request.destination_root
    )


def test_streaming_validation_evidence_restores_identically_after_restart(tmp_path: Path):
    plan = _single_source_plan(
        "main", token_quota=40, validation_fraction=0.8, buffer_size=2
    )
    resumed_request = replace(
        make_corpus_request(tmp_path / "resumed-evidence", plans=[plan]),
        raw_unit_bytes=600,
        shard_size_tokens=1_000_000,
    )
    commits = 0

    def interrupt_after_first(_unit):
        nonlocal commits
        commits += 1
        if commits == 1:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        build_local_corpus(
            resumed_request,
            dataset_loader=_loader,
            on_unit_committed=interrupt_after_first,
        )
    resumed = build_local_corpus(resumed_request, dataset_loader=_loader)

    clean_request = replace(
        make_corpus_request(tmp_path / "clean-evidence", plans=[plan]),
        raw_unit_bytes=600,
        shard_size_tokens=1_000_000,
    )
    clean = build_local_corpus(clean_request, dataset_loader=_loader)
    resumed_evidence = _last_cumulative(resumed_request)
    clean_evidence = _last_cumulative(clean_request)
    resumed_evidence.pop("progress", None)
    clean_evidence.pop("progress", None)

    assert resumed.status == clean.status == "complete"
    assert resumed_evidence["validation"]["documents"] > 0
    assert resumed_evidence == clean_evidence
    assert _artifact_bytes(resumed_request.destination_root) == _artifact_bytes(
        clean_request.destination_root
    )


def test_atomic_unit_state_contains_truthful_streaming_cumulative_evidence(tmp_path: Path):
    def text_for_split(index: int, *, heldout: bool) -> str:
        candidate = 0
        while True:
            text = f"unique evidence document {index} candidate {candidate}"
            fraction = int(sha256_text(text)[:16], 16) / float(16**16)
            if (fraction < 0.4) is heldout:
                return text
            candidate += 1

    rows = [
        {"text": ""},
        {"text": "x"},
        {"text": "heldout contamination evidence appears here"},
        {"text": text_for_split(0, heldout=True)},
        {"text": text_for_split(1, heldout=True)},
        {"text": text_for_split(2, heldout=False)},
        {"text": text_for_split(3, heldout=False)},
        *({"text": f"unused evidence document {index}"} for index in range(80)),
    ]

    def evidence_loader(hf_name: str, **kwargs):
        if hf_name == "common-pile/comma_v0.1_training_dataset":
            return iter(rows)
        return _loader(hf_name, **kwargs)

    plan = _single_source_plan(
        "main", token_quota=1, validation_fraction=0.4, buffer_size=2
    )
    request = make_corpus_request(tmp_path, plans=[plan])
    result = build_local_corpus(request, dataset_loader=evidence_loader)
    cumulative = _last_cumulative(request)
    cursor = cumulative["source_cursors"]["main:common_pile_wikimedia"]
    consumed = rows[:cursor]

    assert result.status == "complete"
    assert cumulative["raw"] == {
        "documents": cursor,
        "chars": sum(len(str(row["text"])) for row in consumed),
        "bytes": sum(
            len(json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")) + 1
            for row in consumed
        ),
    }
    normalized = [str(row["text"]) for row in consumed if str(row["text"]).strip()]
    assert cumulative["normalized"] == {
        "documents": cursor - 1,
        "chars": sum(len(text) for text in normalized),
        "bytes": sum(len(text.encode("utf-8")) for text in normalized),
    }
    assert cumulative["quality"]["total_documents"] == cursor
    assert cumulative["corpus"]["documents"] == (
        cumulative["fit"]["documents"] + cumulative["validation"]["documents"]
    )
    assert cumulative["quality"]["accepted_documents"] == (
        cumulative["corpus"]["documents"] + cumulative["quota_discarded"]["documents"]
    )
    assert cumulative["quota_discarded"]["documents"] == 1
    assert {
        name: count for name, count in cumulative["rejected"].items() if count
    } == cumulative["quality"]["rejection_reasons"]
    assert cumulative["validation"]["documents"] > 0
    assert len(cumulative["validation"]["identity_order_sha256"]) == 64
    assert len(cumulative["validation"]["content_order_sha256"]) == 64
    assert cumulative["validation"]["packed_tokens"] == (
        cumulative["validation"]["tokens"] + cumulative["validation"]["documents"]
    )
    assert cumulative["fit"]["packed_tokens"] == (
        cumulative["fit"]["tokens"] + cumulative["fit"]["documents"]
    )
    raw_fit_bytes = sum(path.stat().st_size for path in request.destination_root.rglob("fit.jsonl"))
    raw_validation_bytes = sum(path.stat().st_size for path in request.destination_root.rglob("holdout.jsonl"))
    assert cumulative["fit"]["raw_bytes"] == raw_fit_bytes
    assert cumulative["validation"]["raw_bytes"] == raw_validation_bytes
    assert sum(cumulative["licenses"].values()) == cumulative["corpus"]["documents"]
    item = cumulative["items"]["main:common_pile_wikimedia"]
    assert item["last_document_tokens"] > 0
    assert item["requested_tokens"] == 1
    assert item["actual_tokens"] == result.accepted_quota_tokens
    assert item["overshoot_tokens"] == result.accepted_quota_tokens - 1


def test_interval_progress_reports_truthful_unsealed_window_state(
    tmp_path: Path, capsys
):
    plan = _single_source_plan(
        "main", token_quota=60, validation_fraction=0.0, buffer_size=2
    )
    request = replace(
        make_corpus_request(tmp_path, plans=[plan]),
        raw_unit_bytes=1_000_000,
        shard_size_tokens=1_000_000,
        progress_interval_seconds=10.0,
    )
    ticks = iter(float(value) for value in range(0, 10_000, 5))
    events = []

    result = build_local_corpus(
        request,
        dataset_loader=_loader,
        monotonic_clock=lambda: next(ticks),
        progress_callback=events.append,
    )

    assert result.status == "complete"
    running = [event for event in events if event["status"] == "running"]
    assert len(running) >= 2
    unsealed = next(event for event in running if event["last_unit"] is None)
    assert unsealed["current"] == {
        "stage": "main",
        "source_id": "common_pile_wikimedia",
        "bucket_id": None,
        "item_id": "common_pile_wikimedia",
    }
    assert unsealed["pending_unit"]["documents"] > 0
    assert unsealed["item_quota"]["requested_tokens"] == 60
    assert unsealed["item_quota"]["actual_tokens"] > 0
    assert unsealed["stage_quota"]["requested_tokens"] == 60
    assert unsealed["stage_quota"]["actual_tokens"] > 0
    assert unsealed["throughput"]["elapsed_seconds"] > 0
    assert unsealed["throughput"]["overall_tokens_per_second"] > 0
    assert unsealed["throughput"]["rolling_tokens_per_second"] > 0
    assert unsealed["throughput"]["eta_seconds"] is not None
    assert unsealed["rss_bytes"] > 0
    assert set(unsealed["storage"]) == {
        "active_bytes", "free_bytes", "unpublished_bytes", "published_bytes"
    }
    assert unsealed["drive"]["verified"] is False
    assert not (request.local_root / "progress.json.partial").exists()
    assert "pending=" in capsys.readouterr().out

    committed_elapsed = _last_cumulative(request)["progress"]["elapsed_seconds"]
    resumed_events = []
    resumed = build_local_corpus(
        request,
        dataset_loader=_loader,
        monotonic_clock=lambda: next(ticks),
        progress_callback=resumed_events.append,
    )
    assert resumed.status == "complete"
    assert resumed_events[-1]["throughput"]["elapsed_seconds"] >= committed_elapsed


def test_resumed_rolling_rate_uses_only_new_process_tokens_and_interval(tmp_path: Path):
    class StepClock:
        def __init__(self, start: float, step: float):
            self.current = start
            self.step = step

        def __call__(self) -> float:
            value = self.current
            self.current += self.step
            return value

    plan = _single_source_plan(
        "main", token_quota=120, validation_fraction=0.0, buffer_size=2
    )
    request = replace(
        make_corpus_request(tmp_path, plans=[plan]),
        raw_unit_bytes=1_000_000,
        shard_size_tokens=1_000_000,
        progress_interval_seconds=0.0,
    )
    calibrated = build_local_corpus(
        request,
        dataset_loader=_loader,
        stop_after_quota_tokens=20,
        monotonic_clock=StepClock(0.0, 10.0),
    )
    saved = _last_cumulative(request)["progress"]
    resumed_events = []

    resumed = build_local_corpus(
        request,
        dataset_loader=_loader,
        monotonic_clock=StepClock(100.0, 5.0),
        progress_callback=resumed_events.append,
    )
    first = next(event for event in resumed_events if event["status"] == "running")
    new_elapsed = first["throughput"]["elapsed_seconds"] - saved["elapsed_seconds"]
    new_tokens = first["accepted_quota_tokens"] - saved["accepted_quota_tokens"]
    rolling = first["throughput"]["rolling_tokens_per_second"]

    assert calibrated.status == "calibration_complete"
    assert saved["accepted_quota_tokens"] < 120
    assert resumed.status == "complete"
    assert new_elapsed > 0
    assert new_tokens > 0
    assert rolling == pytest.approx(new_tokens / new_elapsed)
    assert first["throughput"]["overall_tokens_per_second"] == pytest.approx(
        first["accepted_quota_tokens"] / first["throughput"]["elapsed_seconds"]
    )
    remaining = first["stage_quota"]["requested_tokens"] - first["stage_quota"]["actual_tokens"]
    assert first["throughput"]["eta_seconds"] == pytest.approx(remaining / rolling)


def test_transient_loader_failure_retries_from_committed_cursor(tmp_path: Path):
    attempts = 0

    def flaky_loader(hf_name: str, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("temporary network failure")
        return _loader(hf_name, **kwargs)

    result = build_local_corpus(make_corpus_request(tmp_path, plans=[_tiny_plan("main")]), dataset_loader=flaky_loader)

    assert result.status == "complete"
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


def test_operational_identity_refuses_changed_destination_or_evidence_root_before_reconcile(
    tmp_path: Path, monkeypatch
):
    request = make_corpus_request(tmp_path / "original", plans=[_tiny_plan("main")])
    build_local_corpus(
        request, dataset_loader=_loader, stop_after_quota_tokens=24
    )

    from matgpt.data.local_publish import DrivePublisher

    def unexpected_reconcile(_self):
        raise AssertionError("identity must fail before destination reconciliation")

    monkeypatch.setattr(DrivePublisher, "reconcile", unexpected_reconcile)
    changed_destination = replace(
        request, destination_root=request.evidence_root / "different-drive"
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        build_local_corpus(changed_destination, dataset_loader=_loader)

    copied_root = tmp_path / "copied-evidence"
    copied_root.mkdir()
    shutil.copytree(request.tokenizer_dir, copied_root / "tokenizer")
    shutil.copy2(request.tokenizer_selection_path, copied_root / "tokenizer_selection.json")
    shutil.copy2(request.evidence_root / "comparison.json", copied_root / "comparison.json")
    assert sha256_file(copied_root / "tokenizer_selection.json") == sha256_file(
        request.tokenizer_selection_path
    )
    changed_evidence = replace(
        request,
        evidence_root=copied_root,
        tokenizer_dir=copied_root / "tokenizer",
        tokenizer_selection_path=copied_root / "tokenizer_selection.json",
        destination_root=copied_root / "drive",
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        build_local_corpus(changed_evidence, dataset_loader=_loader)


@pytest.mark.parametrize("evidence_name", ("tokenizer_selection.json", "comparison.json"))
def test_builder_rejects_symlinked_canonical_evidence_file(
    tmp_path: Path, evidence_name: str
):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    canonical = request.evidence_root / evidence_name
    backing = request.evidence_root / f"real-{evidence_name}"
    canonical.rename(backing)
    canonical.symlink_to(backing.name)

    with pytest.raises(ValueError, match="symbolic link"):
        build_local_corpus(request, dataset_loader=_loader)

    assert not (request.local_root / "corpus.sqlite3").exists()


def test_builder_rejects_copied_selection_outside_root_and_symlink_destination(
    tmp_path: Path
):
    request = make_corpus_request(tmp_path / "copied", plans=[_tiny_plan("main")])
    outside = tmp_path / "outside"
    outside.mkdir()
    copied_selection = outside / "tokenizer_selection.json"
    shutil.copy2(request.tokenizer_selection_path, copied_selection)

    with pytest.raises(ValueError, match="directly below evidence_root"):
        build_local_corpus(
            replace(request, tokenizer_selection_path=copied_selection),
            dataset_loader=_loader,
        )

    symlink_request = make_corpus_request(
        tmp_path / "symlink-destination", plans=[_tiny_plan("main")]
    )
    real_destination = symlink_request.evidence_root / "real-drive"
    real_destination.mkdir()
    symlink_request.destination_root.symlink_to(real_destination.name)
    with pytest.raises(ValueError, match="symbolic link"):
        build_local_corpus(symlink_request, dataset_loader=_loader)

    assert not (symlink_request.local_root / "corpus.sqlite3").exists()


_SYMLINK_PATH_CASES = (
    "evidence_root_ancestor",
    "selection_file",
    "comparison_file",
    "tokenizer_dir_ancestor",
    "tokenizer_json_file",
    "special_tokens_file",
    "destination_root_ancestor",
    "local_root_ancestor",
    "journal_file",
)


def _symlink_one_corpus_path(
    request: LocalCorpusRequest, case: str
) -> LocalCorpusRequest:
    root = request.evidence_root
    if case == "evidence_root_ancestor":
        alias = root.parent / "evidence-root-alias"
        alias.symlink_to(".", target_is_directory=True)
        return replace(request, evidence_root=alias / root.name)
    if case == "selection_file":
        target = request.tokenizer_selection_path
    elif case == "comparison_file":
        target = root / "comparison.json"
    elif case == "tokenizer_json_file":
        target = request.tokenizer_dir / "tokenizer.json"
    elif case == "special_tokens_file":
        target = request.tokenizer_dir / "special_tokens.json"
    elif case == "journal_file":
        target = request.local_root / "corpus.sqlite3"
    else:
        alias = root / f"{case}-alias"
        alias.symlink_to(".", target_is_directory=True)
        if case == "tokenizer_dir_ancestor":
            return replace(request, tokenizer_dir=alias / request.tokenizer_dir.name)
        if case == "destination_root_ancestor":
            return replace(request, destination_root=alias / request.destination_root.name)
        if case == "local_root_ancestor":
            return replace(request, local_root=alias / request.local_root.name)
        raise AssertionError(f"unknown path case {case}")

    backing = target.with_name(f"real-{target.name}")
    if target.exists():
        target.rename(backing)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        backing.write_bytes(b"fresh journal symlink sentinel\n")
    target.symlink_to(backing.name)
    return request


_LEXICAL_PATH_FIELDS = (
    "evidence_root",
    "tokenizer_selection_path",
    "tokenizer_dir",
    "destination_root",
    "local_root",
)


def _lexically_alias_one_corpus_path(
    request: LocalCorpusRequest, field: str
) -> LocalCorpusRequest:
    target = getattr(request, field)
    alias = target.parent / f"unused-{field}" / ".." / target.name
    return replace(request, **{field: alias})


def _install_preflight_failure_hooks(monkeypatch) -> None:
    import matgpt.data.local_corpus as local_corpus

    def unexpected(*_args, **_kwargs):
        raise AssertionError("path must fail before evidence, journal, or publisher hooks")

    monkeypatch.setattr(Path, "read_text", unexpected)
    monkeypatch.setattr(local_corpus.BuildJournal, "open", unexpected)
    monkeypatch.setattr(local_corpus, "_cleanup_uncommitted_partials", unexpected)
    monkeypatch.setattr(local_corpus.DrivePublisher, "__init__", unexpected)
    monkeypatch.setattr(local_corpus.DrivePublisher, "reconcile", unexpected)


@pytest.mark.parametrize("resumed", (False, True), ids=("fresh", "resume"))
@pytest.mark.parametrize("path_case", _SYMLINK_PATH_CASES)
def test_each_symlinked_corpus_path_fails_before_evidence_state_or_publisher_hooks(
    tmp_path: Path, monkeypatch, path_case: str, resumed: bool
):
    request = make_corpus_request(tmp_path / "evidence", plans=[_tiny_plan("main")])
    journal = request.local_root / "corpus.sqlite3"
    if resumed:
        build_local_corpus(
            request, dataset_loader=_loader, stop_after_quota_tokens=24
        )
        before = (journal.read_bytes(), journal.stat().st_mtime_ns)
    aliased = _symlink_one_corpus_path(request, path_case)
    physical_journal = (
        journal.with_name("real-corpus.sqlite3")
        if path_case == "journal_file" else journal
    )
    if path_case == "journal_file":
        before = (physical_journal.read_bytes(), physical_journal.stat().st_mtime_ns)
    _install_preflight_failure_hooks(monkeypatch)

    with pytest.raises(ValueError, match="canonical non-symlink"):
        build_local_corpus(aliased, dataset_loader=_loader)

    if resumed or path_case == "journal_file":
        assert (physical_journal.read_bytes(), physical_journal.stat().st_mtime_ns) == before
    else:
        assert not journal.exists()


@pytest.mark.parametrize("resumed", (False, True), ids=("fresh", "resume"))
@pytest.mark.parametrize("field", _LEXICAL_PATH_FIELDS)
def test_each_lexically_aliased_corpus_path_fails_before_hooks(
    tmp_path: Path, monkeypatch, field: str, resumed: bool
):
    request = make_corpus_request(tmp_path / "evidence", plans=[_tiny_plan("main")])
    journal = request.local_root / "corpus.sqlite3"
    if resumed:
        build_local_corpus(
            request, dataset_loader=_loader, stop_after_quota_tokens=24
        )
        before = (journal.read_bytes(), journal.stat().st_mtime_ns)
    aliased = _lexically_alias_one_corpus_path(request, field)
    _install_preflight_failure_hooks(monkeypatch)

    with pytest.raises(ValueError, match="lexical aliases"):
        build_local_corpus(aliased, dataset_loader=_loader)

    if resumed:
        assert (journal.read_bytes(), journal.stat().st_mtime_ns) == before
    else:
        assert not journal.exists()


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
    assert json.loads(
        (request.destination_root / "manifest.json").read_text(encoding="utf-8")
    )["complete"] is True


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
    assert state["version"] == 2
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

    assert result.status == "complete"
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

    assert result.status == "complete"
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
    assert recovered.status == "complete"

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
    assert build_local_corpus(post_mark, dataset_loader=_loader).status == "complete"


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
