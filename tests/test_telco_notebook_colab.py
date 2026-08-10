import ast
import json
import shutil
from pathlib import Path

import pytest

from matgpt.config import clone_config, load_config
from matgpt.data.local_corpus import LocalCorpusRequest, build_local_corpus
from matgpt.data.quality import DataQualityPolicy
from matgpt.data.sources import load_source_registry
from matgpt.preflight import build_preflight_report
from matgpt.tokenizer.train import train_tokenizer_from_jsonl
from matgpt.utils.hashing import sha256_file, sha256_json


NOTEBOOK = Path("notebooks/train_matgpt_telco_300m_colab.ipynb")


def _cells() -> list[dict]:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]


def _source(cell: dict) -> str:
    return "".join(cell.get("source", []))


def _code_after_heading(heading: str) -> str:
    cells = _cells()
    for index, cell in enumerate(cells):
        if cell.get("cell_type") != "markdown":
            continue
        if _source(cell).splitlines()[0] != heading:
            continue
        for following in cells[index + 1 :]:
            if following.get("cell_type") == "code":
                return _source(following)
            if following.get("cell_type") == "markdown":
                break
    raise AssertionError(f"No code cell follows heading {heading!r}")


def _notebook_namespace(heading: str) -> dict:
    namespace = {
        "RUN_STAGE": "test_only_skip",
        "PREPARED_DATA_MODE": "test_only_skip",
        "json": json,
        "shutil": shutil,
        "Path": Path,
    }
    exec(compile(_code_after_heading(heading), str(NOTEBOOK), "exec"), namespace)
    return namespace


def _write_synthetic_selected_tokenizer(root: Path) -> Path:
    tokenizer_dir = root / "tokenizers/representative_200m"
    fitting = root / "tokenizer_fit.jsonl"
    fitting.parent.mkdir(parents=True, exist_ok=True)
    fitting.write_text(
        "".join(
            json.dumps({"text": text}) + "\n"
            for text in (
                "general router prose packet radio network",
                "validation routing tale with a different ending",
                "🙂 café 你好 A space, then punctuation!",
            )
        ),
        encoding="utf-8",
    )
    train_tokenizer_from_jsonl(
        [fitting],
        tokenizer_dir,
        vocab_size=320,
        min_frequency=1,
        special_tokens=[
            "<|pad|>",
            "<|bos|>",
            "<|eos|>",
            "<|system|>",
            "<|user|>",
            "<|assistant|>",
            "<|end|>",
        ],
    )
    return tokenizer_dir


def _single_source_pilot_plan() -> dict:
    return {
        "version": 1,
        "stage": "pilot",
        "seed": 42,
        "total_tokens": 80,
        "quota_tolerance": 0.03,
        "validation_fraction": 0.25,
        "buffer_size": 3,
        "role_quotas": {"pretrain_general": 80},
        "items": [
            {
                "id": "common_pile_wikimedia",
                "source_id": "common_pile_wikimedia",
                "bucket_id": None,
                "role": "pretrain_general",
                "token_quota": 80,
            }
        ],
        "plan_sha256": "pilot" + "0" * 59,
    }


def _synthetic_prebuilt_tree(tmp_path: Path) -> dict:
    drive_root = tmp_path / "drive"
    drive_root.mkdir()
    tokenizer_dir = _write_synthetic_selected_tokenizer(drive_root)
    tokenizer_sha = sha256_file(tokenizer_dir / "tokenizer.json")
    comparison = {
        "labels": {"baseline": "pilot_20m", "candidate": "representative_200m"},
        "shared_evidence_valid": True,
        "side_validity": {"baseline": True, "candidate": True},
        "baseline": {"tokenizer_sha256": "a" * 64},
        "candidate": {"tokenizer_sha256": tokenizer_sha},
        "fingerprints": {
            "baseline_tokenizer_sha256": "a" * 64,
            "candidate_tokenizer_sha256": tokenizer_sha,
        },
    }
    comparison["comparison_sha256"] = sha256_json(comparison)
    comparison_path = drive_root / "comparison.json"
    comparison_path.write_text(
        json.dumps(comparison, sort_keys=True) + "\n", encoding="utf-8"
    )
    selection = {
        "version": 1,
        "approved": True,
        "winner": "representative_200m",
        "comparison_sha256": comparison["comparison_sha256"],
        "selected_tokenizer_sha256": tokenizer_sha,
        "operator_timestamp": "2026-08-09T00:00:00+00:00",
    }
    selection_path = drive_root / "tokenizer_selection.json"
    selection_path.write_text(
        json.dumps(selection, sort_keys=True) + "\n", encoding="utf-8"
    )
    plan = _single_source_pilot_plan()
    destination_root = drive_root / "corpora/pilot" / tokenizer_sha
    request = LocalCorpusRequest(
        registry=load_source_registry("configs/data/telco_300m_sources.yaml"),
        plans=(plan,),
        tokenizer_dir=tokenizer_dir,
        tokenizer_selection_path=selection_path,
        local_root=tmp_path / "local-builder",
        destination_root=destination_root,
        quality_policy=DataQualityPolicy(
            enabled=True,
            min_chars=2,
            exact_dedup=True,
            contamination_patterns=["heldout contamination evidence"],
        ),
        evidence_root=drive_root,
        batch_documents=4,
        shard_size_tokens=96,
        raw_unit_bytes=2_048,
        max_working_bytes=20 * 1024**2,
        min_free_bytes=1,
        progress_interval_seconds=0,
        retry_delays=(0.0,),
    )

    def loader(_hf_name: str, **_kwargs):
        return iter(
            {"text": f"general router prose packet radio network {index}"}
            for index in range(80)
        )

    result = build_local_corpus(request, dataset_loader=loader)
    assert result.status == "complete"
    pilot_refresh = {
        "version": 1,
        "winner": "representative_200m",
        "selected_tokenizer_sha256": tokenizer_sha,
        "selection_file_sha256": sha256_file(selection_path),
        "comparison_file_sha256": sha256_file(comparison_path),
        "selection_comparison_sha256": selection["comparison_sha256"],
        "comparison_sha256": comparison["comparison_sha256"],
        "action": "rebuild",
        "status": "ready_for_colab",
        "refreshed_pilot_gates_passed": False,
        "pending_colab_gates": ["smoke", "pilot", "evaluation"],
        "build_identity_sha256": result.build_identity_sha256,
    }
    pilot_refresh["pilot_refresh_sha256"] = sha256_json(pilot_refresh)
    pilot_refresh_path = (
        drive_root
        / "evidence/tokenizers"
        / tokenizer_sha
        / "pilot/pilot_refresh.json"
    )
    pilot_refresh_path.parent.mkdir(parents=True)
    pilot_refresh_path.write_text(
        json.dumps(pilot_refresh, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "drive_root": drive_root,
        "source_corpus_dir": destination_root,
        "source_tokenizer_dir": tokenizer_dir,
        "selection_path": selection_path,
        "comparison_path": comparison_path,
        "pilot_refresh_path": pilot_refresh_path,
        "manifest": result.manifest,
        "request": request,
        "tokenizer_sha": tokenizer_sha,
    }


def test_telco_notebook_is_valid_and_defaults_to_prepare_data():
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    source = "\n".join(_source(cell) for cell in notebook["cells"])

    assert notebook["nbformat"] == 4
    assert 'RUN_STAGE = "prepare_data"' in source
    assert 'DATA_PLAN = "pilot"' in source
    assert "ALLOW_FULL_DATA = False" in source
    assert "FULL_APPROVED = False" in source
    assert "GOOGLE_DRIVE_FREE_GB_OVERRIDE = 0.0" in source
    for stage in ("prepare_data", "prepare", "smoke", "pilot", "full", "evaluate"):
        assert stage in source


def test_telco_notebook_operator_headings_are_ordered():
    headings = [
        _source(cell).splitlines()[0]
        for cell in _cells()
        if cell.get("cell_type") == "markdown" and _source(cell).strip()
    ]
    expected = [
        "## 1. Choose one stage",
        "## 2. Mount Google Drive",
        "## 3. Locate or clone the project",
        "## 4. Install and authenticate",
        "## 5. Inspect the runtime",
        "## 6. Build fixed local and Drive paths",
        "## 7. Prepare isolated evaluation and training data",
        "## 8. Prepare tokenizer and shards",
        "## 9. Verify evidence gates",
        "## 10. Run the selected stage",
        "## 11. Evaluate checkpoints",
        "## 12. Review persisted evidence",
    ]

    assert [heading for heading in headings if heading in expected] == expected


def test_runtime_gate_is_cuda_and_memory_based_not_name_locked():
    source = _code_after_heading("## 5. Inspect the runtime")

    assert "torch.cuda.is_available()" in source
    assert "torch.cuda.get_device_properties" in source
    assert "40 * 1024**3" in source
    assert '"T4" in gpu_name' not in source
    assert "RTX PRO 6000" not in source
    assert 'print("Drive mount/cache filesystem:"' in source
    assert 'print("Drive disk:"' not in source


def test_full_data_gate_uses_drive_api_quota_not_mount_cache_statvfs():
    source = _code_after_heading(
        "## 7. Prepare isolated evaluation and training data"
    )

    assert "google_drive_storage_evidence" in source
    assert "storageQuota" in source
    assert "require_free_storage_gib" in source
    assert "GOOGLE_DRIVE_FREE_GB_OVERRIDE" in source
    assert "require_free_storage_gib(drive_storage, 140.0)" in source
    assert 'shutil.disk_usage("/content/drive").free' not in source


def test_prepare_data_materializes_benchmarks_before_training_corpus():
    source = _code_after_heading(
        "## 7. Prepare isolated evaluation and training data"
    )

    eval_position = source.index(
        'run_command([sys.executable, "scripts/prepare_open_telco_evals.py"'
    )
    corpus_position = source.index("run_command(build_corpus_command")
    assert eval_position < corpus_position
    assert "--contamination-patterns" in source
    assert "--allow-full-data" in source
    assert "ALLOW_FULL_DATA" in source
    assert "scripts/pretrain.py" not in source


def test_prepare_data_full_requires_and_uses_frozen_pilot_tokenizer():
    paths = _code_after_heading("## 6. Build fixed local and Drive paths")
    source = _code_after_heading(
        "## 7. Prepare isolated evaluation and training data"
    )

    assert "PILOT_TOKENIZER_DRIVE_DIR" in paths
    assert "corpus_has_exact_token_quotas" in source
    assert (
        'tokenizer_for_quota = PILOT_TOKENIZER_DRIVE_DIR if DATA_PLAN == "full"'
        in source
    )
    assert "tokenizer_dir=tokenizer_for_quota" in source
    assert "Run the pilot prepare stage first" in source


def test_prepare_stage_audits_before_sharding_and_never_pretrains():
    source = _code_after_heading("## 8. Prepare tokenizer and shards")

    tokenizer_position = source.index("scripts/train_tokenizer.py")
    audit_position = source.index("scripts/audit_telco_corpus.py")
    shard_position = source.index("scripts/tokenize_and_shard.py")
    assert tokenizer_position < audit_position < shard_position
    assert "scripts/preflight_t4.py" in source
    assert "--require-supported-gpu" in source
    assert "scripts/benchmark_t4.py" in source
    assert 'batch_size\"] == 8' in source
    assert 'status\"] == \"ok\"' in source
    assert "memory_fraction" in source
    assert "scripts/pretrain.py" not in source
    assert source.count('"--min-free-disk-gb", "0"') == 2
    assert '"--corpus-manifest", CORPUS_DIR / "manifest.json"' in source
    assert '"--output", EVIDENCE_DIR / "quota_audit.json"' in source


def test_colab_supports_prebuilt_shards_without_retokenizing():
    source = _code_after_heading("## 8. Prepare tokenizer and shards")
    restore_source = source[
        source.index("def restore_prebuilt_shards") : source.index(
            "def restore_current_prebuilt"
        )
    ]

    assert 'PREPARED_DATA_MODE == "prebuilt_shards"' in source
    assert "restore_prebuilt_shards" in source
    assert "scripts/tokenize_and_shard.py" in source
    assert 'if PREPARED_DATA_MODE == "legacy_jsonl"' in source
    assert "shutil.rmtree" not in restore_source
    assert "atomic_snapshot" not in restore_source


def test_prebuilt_full_training_still_requires_manual_approval():
    source = "\n".join(_source(cell) for cell in _cells())

    assert "FULL_APPROVED" in source
    assert "final corpus manifest is incomplete" in source
    assert "selected tokenizer fingerprint mismatch" in source


def test_prebuilt_restore_copies_verified_runtime_artifacts_and_passes_preflight(
    tmp_path: Path,
):
    fixture = _synthetic_prebuilt_tree(tmp_path)
    namespace = _notebook_namespace("## 8. Prepare tokenizer and shards")
    target_corpus = tmp_path / "content/pilot/prebuilt"
    target_tokenizer = tmp_path / "content/pilot/tokenizer"
    expected_fingerprints = {
        key: fixture["manifest"]["fingerprints"][key]
        for key in (
            "source_registry_sha256",
            "plan_sha256",
            "contamination_sha256",
        )
    }

    restored = namespace["restore_prebuilt_shards"](
        runtime_root=tmp_path / "content",
        drive_root=fixture["drive_root"],
        source_corpus_dir=fixture["source_corpus_dir"],
        source_tokenizer_dir=fixture["source_tokenizer_dir"],
        target_corpus_dir=target_corpus,
        target_tokenizer_dir=target_tokenizer,
        selection_path=fixture["selection_path"],
        comparison_path=fixture["comparison_path"],
        pilot_refresh_path=fixture["pilot_refresh_path"],
        expected_fingerprints=expected_fingerprints,
        expected_splits=("pilot", "validation"),
        require_pilot_gates=False,
    )

    assert restored["tokenization_invoked"] is False
    assert restored["tokenizer_sha256"] == fixture["tokenizer_sha"]
    assert sha256_file(target_tokenizer / "tokenizer.json") == fixture["tokenizer_sha"]
    assert (target_corpus / "manifest.json").is_file()
    assert not list(target_corpus.rglob("*.jsonl")), "raw corpus text must stay on Drive"
    for split in ("pilot", "validation"):
        metadata = json.loads(
            (target_corpus / f"{split}_metadata.json").read_text(encoding="utf-8")
        )
        for shard in metadata["shards"]:
            copied = target_corpus / shard["path"]
            source = fixture["source_corpus_dir"] / shard["path"]
            assert copied.is_file()
            assert sha256_file(copied) == shard["sha256"] == sha256_file(source)

    cfg = clone_config(load_config("configs/matgpt_telco_300m.yaml"))
    cfg["run"]["output_dir"] = str(tmp_path / "run")
    cfg["dataset"]["normalized_dir"] = str(target_corpus)
    cfg["dataset"]["train_split"] = "pilot"
    cfg["dataset"]["validation_split"] = "validation"
    cfg["dataset"]["training_splits"] = {"pilot": "pilot"}
    cfg["tokenizer"]["output_dir"] = str(target_tokenizer)
    cfg["tokenizer"]["vocab_size"] = 320
    cfg["model"]["vocab_size"] = 320
    cfg["model"]["context_length"] = 8
    cfg["sharding"]["output_dir"] = str(target_corpus)
    cfg["sharding"]["shard_size_tokens"] = fixture["request"].shard_size_tokens
    cfg["training"]["max_tokens"] = 80
    cfg["training"]["data_phases"] = [
        {"name": "pilot", "split": "pilot", "until_tokens": 80}
    ]
    report = build_preflight_report(cfg, require_t4=False, min_free_disk_gb=0)

    assert report["status"] == "pass", json.dumps(report, indent=2, sort_keys=True)


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("missing_manifest", "final corpus manifest is incomplete"),
        ("tokenizer_mismatch", "selected tokenizer fingerprint mismatch"),
        ("pilot_refresh_mismatch", "pilot refresh.*selected tokenizer"),
        ("pilot_refresh_status", "pilot refresh status"),
        ("raw_traversal", "safe relative|outside"),
        ("shard_traversal", "safe relative|outside"),
        ("target_escape", "runtime root"),
    ],
)
def test_prebuilt_restore_fails_closed_on_incomplete_or_foreign_evidence(
    tmp_path: Path,
    failure: str,
    message: str,
):
    fixture = _synthetic_prebuilt_tree(tmp_path)
    if failure == "missing_manifest":
        (fixture["source_corpus_dir"] / "manifest.json").unlink()
    elif failure == "tokenizer_mismatch":
        manifest_path = fixture["source_corpus_dir"] / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["fingerprints"]["tokenizer_sha256"] = "0" * 64
        manifest["build_identity_sha256"] = sha256_json(manifest["fingerprints"])
        logical_keys = (
                "version",
                "builder",
                "storage_format",
                "raw_record_schema",
                "build_identity_sha256",
            "fingerprints",
            "stages",
            "sources",
            "split_stats",
            "breakdowns",
            "unit_artifacts",
            "audits",
        )
        manifest["content_sha256"] = sha256_json(
            {key: manifest[key] for key in logical_keys}
        )
        manifest.pop("manifest_sha256")
        manifest["manifest_sha256"] = sha256_json(manifest)
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
        )
    elif failure == "pilot_refresh_mismatch":
        path = fixture["pilot_refresh_path"]
        refresh = json.loads(path.read_text(encoding="utf-8"))
        refresh["selected_tokenizer_sha256"] = "0" * 64
        refresh.pop("pilot_refresh_sha256")
        refresh["pilot_refresh_sha256"] = sha256_json(refresh)
        path.write_text(json.dumps(refresh, sort_keys=True) + "\n", encoding="utf-8")
    elif failure == "pilot_refresh_status":
        path = fixture["pilot_refresh_path"]
        refresh = json.loads(path.read_text(encoding="utf-8"))
        refresh["status"] = "failed"
        refresh.pop("pilot_refresh_sha256")
        refresh["pilot_refresh_sha256"] = sha256_json(refresh)
        path.write_text(json.dumps(refresh, sort_keys=True) + "\n", encoding="utf-8")
    elif failure == "raw_traversal":
        manifest_path = fixture["source_corpus_dir"] / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["split_stats"]["pilot"]["raw_chunks"][0]["path"] = (
            "../outside.jsonl"
        )
        logical_keys = (
                "version",
                "builder",
                "storage_format",
                "raw_record_schema",
                "build_identity_sha256",
            "fingerprints",
            "stages",
            "sources",
            "split_stats",
            "breakdowns",
            "unit_artifacts",
            "audits",
        )
        manifest["content_sha256"] = sha256_json(
            {key: manifest[key] for key in logical_keys}
        )
        manifest.pop("manifest_sha256")
        manifest["manifest_sha256"] = sha256_json(manifest)
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
        )
    elif failure == "shard_traversal":
        metadata_path = fixture["source_corpus_dir"] / "pilot_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["shards"][0]["path"] = "../outside.bin"
        metadata.pop("metadata_sha256")
        metadata["metadata_sha256"] = sha256_json(metadata)
        metadata_path.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        manifest_path = fixture["source_corpus_dir"] / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        record = manifest["split_metadata"]["pilot"]
        record["size"] = metadata_path.stat().st_size
        record["sha256"] = sha256_file(metadata_path)
        record["metadata_sha256"] = metadata["metadata_sha256"]
        manifest.pop("manifest_sha256")
        manifest["manifest_sha256"] = sha256_json(manifest)
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
        )

    namespace = _notebook_namespace("## 8. Prepare tokenizer and shards")
    with pytest.raises((AssertionError, ValueError), match=message):
        target_corpus_dir = (
            tmp_path / "outside/prebuilt"
            if failure == "target_escape"
            else tmp_path / "content/pilot/prebuilt"
        )
        namespace["restore_prebuilt_shards"](
            runtime_root=tmp_path / "content",
            drive_root=fixture["drive_root"],
            source_corpus_dir=fixture["source_corpus_dir"],
            source_tokenizer_dir=fixture["source_tokenizer_dir"],
            target_corpus_dir=target_corpus_dir,
            target_tokenizer_dir=tmp_path / "content/pilot/tokenizer",
            selection_path=fixture["selection_path"],
            comparison_path=fixture["comparison_path"],
            pilot_refresh_path=fixture["pilot_refresh_path"],
            expected_fingerprints={
                key: fixture["manifest"]["fingerprints"][key]
                for key in (
                    "source_registry_sha256",
                    "plan_sha256",
                    "contamination_sha256",
                )
            },
            expected_splits=("pilot", "validation"),
            require_pilot_gates=failure == "pilot_refresh_mismatch",
        )


def test_prebuilt_full_restore_revalidates_pending_candidate_pilot_gates(
    tmp_path: Path,
):
    fixture = _synthetic_prebuilt_tree(tmp_path)
    refresh_path = fixture["pilot_refresh_path"]
    refresh = json.loads(refresh_path.read_text(encoding="utf-8"))
    refresh["refreshed_pilot_gates_passed"] = False
    refresh["pending_colab_gates"] = ["smoke", "pilot", "evaluation"]
    refresh.pop("pilot_refresh_sha256")
    refresh["pilot_refresh_sha256"] = sha256_json(refresh)
    refresh_path.write_text(
        json.dumps(refresh, sort_keys=True) + "\n", encoding="utf-8"
    )
    observed: dict[str, object] = {}

    def validate_current_pilot_gates(**kwargs):
        observed.update(kwargs)
        return {"status": "verified"}

    namespace = _notebook_namespace("## 8. Prepare tokenizer and shards")
    restored = namespace["restore_prebuilt_shards"](
        runtime_root=tmp_path / "content",
        drive_root=fixture["drive_root"],
        source_corpus_dir=fixture["source_corpus_dir"],
        source_tokenizer_dir=fixture["source_tokenizer_dir"],
        target_corpus_dir=tmp_path / "content/full/prebuilt",
        target_tokenizer_dir=tmp_path / "content/full/tokenizer",
        selection_path=fixture["selection_path"],
        comparison_path=fixture["comparison_path"],
        pilot_refresh_path=refresh_path,
        expected_fingerprints={
            key: fixture["manifest"]["fingerprints"][key]
            for key in (
                "source_registry_sha256",
                "plan_sha256",
                "contamination_sha256",
            )
        },
        expected_splits=("pilot", "validation"),
        require_pilot_gates=True,
        pilot_gate_validator=validate_current_pilot_gates,
    )

    gate_root = (
        fixture["drive_root"]
        / "evidence/tokenizers"
        / fixture["tokenizer_sha"]
        / "pilot/colab"
    )
    assert observed == {
        "drive_dir": fixture["drive_root"],
        "gate_root": gate_root,
        "evaluation_root": gate_root / "evaluation",
        "tokenizer_sha256": fixture["tokenizer_sha"],
        "build_identity_sha256": refresh["build_identity_sha256"],
    }
    assert restored["pilot_gates_validated"] is True


@pytest.mark.parametrize("artifacts_match", [True, False])
def test_prebuilt_full_restore_revalidates_baseline_reuse_artifacts(
    tmp_path: Path, artifacts_match: bool
):
    fixture = _synthetic_prebuilt_tree(tmp_path)
    refresh_path = fixture["pilot_refresh_path"]
    refresh = json.loads(refresh_path.read_text(encoding="utf-8"))
    refresh["action"] = "reuse"
    refresh["refreshed_pilot_gates_passed"] = True
    refresh["pending_colab_gates"] = []
    refresh["artifacts"] = {"proof": "current"}
    refresh.pop("pilot_refresh_sha256")
    refresh["pilot_refresh_sha256"] = sha256_json(refresh)
    refresh_path.write_text(
        json.dumps(refresh, sort_keys=True) + "\n", encoding="utf-8"
    )

    namespace = _notebook_namespace("## 8. Prepare tokenizer and shards")
    restore = lambda: namespace["restore_prebuilt_shards"](
        runtime_root=tmp_path / "content",
        drive_root=fixture["drive_root"],
        source_corpus_dir=fixture["source_corpus_dir"],
        source_tokenizer_dir=fixture["source_tokenizer_dir"],
        target_corpus_dir=tmp_path / "content/full/prebuilt",
        target_tokenizer_dir=tmp_path / "content/full/tokenizer",
        selection_path=fixture["selection_path"],
        comparison_path=fixture["comparison_path"],
        pilot_refresh_path=refresh_path,
        expected_fingerprints={
            key: fixture["manifest"]["fingerprints"][key]
            for key in (
                "source_registry_sha256",
                "plan_sha256",
                "contamination_sha256",
            )
        },
        expected_splits=("pilot", "validation"),
        require_pilot_gates=True,
        pilot_reuse_validator=lambda _root, _sha: {
            "proof": "current" if artifacts_match else "changed"
        },
    )

    if artifacts_match:
        assert restore()["pilot_gates_validated"] is True
    else:
        with pytest.raises(ValueError, match="recorded artifact fingerprints changed"):
            restore()


def test_prebuilt_routes_colab_outputs_under_selected_tokenizer_namespace():
    paths = _code_after_heading("## 6. Build fixed local and Drive paths")
    prepare = _code_after_heading("## 8. Prepare tokenizer and shards")

    assert 'COLAB_GATE_ROOT = DRIVE_ROOT / "evidence/tokenizers"' in paths
    assert 'COLAB_GATE_ROOT / DATA_PLAN / "colab"' in paths
    assert "EVIDENCE_DIR = COLAB_GATE_ROOT" in paths
    assert "RUN_DIR = COLAB_GATE_ROOT" in paths
    assert 'EVIDENCE_DIR / "config.yaml"' in prepare


def test_candidate_pilot_producer_uses_prebuilt_gate_config_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from matgpt.preflight import CHECK_IDS
    from scripts import prepare_telco_local

    drive_root = tmp_path / "drive"
    gate_root = drive_root / "evidence/tokenizers" / ("a" * 64) / "pilot/colab"
    gate_root.mkdir(parents=True)
    (gate_root / "preflight.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "checks": [
                    {"name": name, "status": "pass", "message": "ok", "details": {}}
                    for name in CHECK_IDS
                ],
            }
        ),
        encoding="utf-8",
    )
    observed: list[Path] = []

    def stop_after_config_path(path):
        observed.append(Path(path))
        raise RuntimeError("path observed")

    monkeypatch.setattr(prepare_telco_local, "load_config", stop_after_config_path)
    with pytest.raises(RuntimeError, match="path observed"):
        prepare_telco_local._pilot_colab_evidence(
            drive_dir=drive_root,
            gate_root=gate_root,
            evaluation_root=gate_root / "evaluation",
            tokenizer_sha256="a" * 64,
            build_identity_sha256="b" * 64,
        )

    assert observed == [gate_root / "config.yaml"]


def test_candidate_pilot_checkpoint_reference_rebases_colab_mount(
    tmp_path: Path,
):
    from scripts import prepare_telco_local

    drive_root = tmp_path / "drive"
    relative_root = (
        Path("evidence/tokenizers")
        / ("a" * 64)
        / "pilot/colab/checkpoints"
    )
    checkpoint_root = drive_root / relative_root
    checkpoint_root.mkdir(parents=True)
    checkpoint = checkpoint_root / f"smoke-{'b' * 64}.pt"
    checkpoint.write_bytes(b"immutable checkpoint")
    colab_reference = (
        Path("/content/drive/MyDrive/matgpt_artifacts/matgpt_telco_300m")
        / relative_root
        / checkpoint.name
    )

    resolved = prepare_telco_local._checkpoint_from_canonical_reference(
        str(colab_reference),
        drive_dir=drive_root,
        checkpoint_root=checkpoint_root,
    )

    assert resolved == checkpoint


def test_prebuilt_full_gate_keeps_manual_approval_after_restore():
    namespace = _notebook_namespace("## 9. Verify evidence gates")

    with pytest.raises(AssertionError, match="FULL_APPROVED=True"):
        namespace["require_full_training_approval"](False)


def test_prepare_stage_freezes_tokenizer_then_rebuilds_exact_pilot():
    source = _code_after_heading("## 8. Prepare tokenizer and shards")

    freeze_position = source.index(
        "atomic_snapshot(TOKENIZER_DIR, frozen_tokenizer_dir)"
    )
    exact_gate_position = source.index("corpus_has_exact_token_quotas")
    audit_position = source.index("scripts/audit_telco_corpus.py")
    assert freeze_position < exact_gate_position < audit_position
    assert "tokenizer_dir=TOKENIZER_DIR" in source
    assert "force=True" in source
    assert "Frozen tokenizer:" in source


def test_training_cell_has_only_explicit_smoke_pilot_and_full_branches():
    source = _code_after_heading("## 10. Run the selected stage")
    tree = ast.parse(source)
    stage_values = {
        comparator.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == "RUN_STAGE"
        for comparator in node.comparators
        if isinstance(comparator, ast.Constant)
        and isinstance(comparator.value, str)
    }

    assert stage_values == {"smoke", "pilot", "full"}
    assert "SMOKE_MAX_STEPS = 20" in source
    assert "SMOKE_RESUME_STEPS = 5" in source
    assert "FULL_APPROVED" in source
    assert "pilot_complete.json" in source
    assert 'RUN_STAGE = "full"' not in source


def test_training_cell_writes_distinct_immutable_smoke_and_pilot_snapshots():
    source = _code_after_heading("## 10. Run the selected stage")

    assert "snapshot_checkpoint" in source
    assert 'label="smoke"' in source
    assert 'label="pilot-latest"' in source
    assert '"checkpoint_binding": smoke_binding' in source
    assert '"checkpoint_binding": pilot_binding' in source
    assert 'smoke_binding["sha256"] != pilot_binding["sha256"]' in source


def test_training_gate_revalidates_artifacts_and_binds_evidence_to_config():
    source = _code_after_heading("## 9. Verify evidence gates")

    assert "CURRENT_CONFIG_SHA" in source
    assert "config_sha256" in source
    assert "scripts/preflight_t4.py" in source
    assert "preflight_{RUN_STAGE}.json" in source
    assert '"--min-free-disk-gb", "0"' in source


def test_evaluation_uses_open_telco_and_fifty_blinded_llm_reviews():
    source = _code_after_heading("## 11. Evaluate checkpoints")

    assert "scripts/evaluate.py" in source
    assert "scripts/evaluate_tasks.py" in source
    assert "scripts/compare_checkpoints.py" in source
    assert '"--review-per-checkpoint", "50"' in source
    assert "llm_judge" in source
    assert "this Codex task" in source
    assert "Human review is optional" in source
    assert "pilot_complete.json" in source
    assert 'pilot_gate["checkpoint_bindings"]' in source
    assert "checkpoint_binding(checkpoint) == declared_binding" in source
    assert 'glob("pilot-*.pt")' not in source
    assert 'glob("ckpt_*.pt")' not in source
    assert 'checkpoint_dir / "latest.pt"' not in source


def test_notebook_uses_dedicated_config_and_drive_directory():
    paths = _code_after_heading("## 6. Build fixed local and Drive paths")

    assert "configs/matgpt_telco_300m.yaml" in paths
    assert 'Path("/content/matgpt_work")' in paths
    assert "matgpt_telco_300m" in paths
    assert "MyDrive/matgpt_artifacts" in paths
    assert "training_splits" in paths
    assert "data_phases" in paths
    assert "DATA_RECIPE_SHA256" in paths
    assert "SOURCE_REGISTRY.read_bytes()" in paths
    assert "MIXTURE_CONFIG.read_bytes()" in paths
    assert "CHECKED_CONFIG.read_bytes()" in paths
    assert 'RECIPE_ROOT = DRIVE_ROOT / "recipes" / DATA_RECIPE_SHA256[:12]' in paths
    assert 'WORK_ROOT = Path("/content/matgpt_work") / "matgpt_telco_300m" / DATA_RECIPE_SHA256[:12]' in paths


def test_full_gate_requires_pilot_from_same_data_recipe():
    source = _code_after_heading("## 9. Verify evidence gates")

    assert 'pilot_gate = RECIPE_ROOT / "evidence/pilot/pilot_complete.json"' in source
