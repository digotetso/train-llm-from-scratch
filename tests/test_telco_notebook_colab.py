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


def test_prepare_data_materializes_benchmarks_before_training_corpus():
    source = _code_after_heading(
        "## 7. Prepare isolated evaluation and training data"
    )

    eval_position = source.index("scripts/prepare_open_telco_evals.py")
    corpus_position = source.index("scripts/prepare_telco_corpus.py")
    assert eval_position < corpus_position
    assert "--contamination-patterns" in source
    assert "--allow-full-data" in source
    assert "ALLOW_FULL_DATA" in source
    assert "scripts/pretrain.py" not in source


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


def test_training_gate_revalidates_artifacts_and_binds_evidence_to_config():
    source = _code_after_heading("## 9. Verify evidence gates")

    assert "CURRENT_CONFIG_SHA" in source
    assert "config_sha256" in source
    assert "scripts/preflight_t4.py" in source
    assert "preflight_{RUN_STAGE}.json" in source


def test_evaluation_uses_open_telco_and_fifty_blinded_llm_reviews():
    source = _code_after_heading("## 11. Evaluate checkpoints")

    assert "scripts/evaluate.py" in source
    assert "scripts/evaluate_tasks.py" in source
    assert "scripts/compare_checkpoints.py" in source
    assert '"--review-per-checkpoint", "50"' in source
    assert "llm_judge" in source
    assert "this Codex task" in source
    assert "Human review is optional" in source


def test_notebook_uses_dedicated_config_and_drive_directory():
    paths = _code_after_heading("## 6. Build fixed local and Drive paths")

    assert "configs/matgpt_telco_300m.yaml" in paths
    assert 'Path("/content/matgpt_work")' in paths
    assert "matgpt_telco_300m" in paths
    assert "MyDrive/matgpt_artifacts" in paths
    assert "training_splits" in paths
    assert "data_phases" in paths
