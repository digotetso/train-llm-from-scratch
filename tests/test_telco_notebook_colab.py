import ast
import json
from pathlib import Path


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
    assert source.count('"--min-free-disk-gb", "0"') == 1


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
    assert "smoke_binding != pilot_binding" in source


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
    assert 'pilot_gate["checkpoint_binding"]["path"]' in source
    assert 'glob("pilot-*.pt")' in source
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
