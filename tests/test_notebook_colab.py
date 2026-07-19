import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from matgpt.config import load_config


NOTEBOOK_PATH = Path("notebooks/train_matgpt_t4_base_colab.ipynb")
APPROVED_DATASET_REVISIONS = {
    Path("configs/matgpt_mini_8m.yaml"): (
        "roneneldan/TinyStories",
        "f54c09fd23315a6f9c86f9dc80f725de7d8f9c64",
    ),
    Path("configs/matgpt_tiny_59m.yaml"): (
        "BabyLM-community/BabyLM-2026-Strict",
        "9e57baaaa91ac3c638746be14d1d5fa6c789f4cf",
    ),
}


def notebook_cells() -> list[dict]:
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))["cells"]


def cell_source(cell: dict) -> str:
    return "".join(cell.get("source", []))


def code_source_after_heading(heading: str) -> str:
    cells = notebook_cells()
    for index, cell in enumerate(cells):
        if cell.get("cell_type") != "markdown":
            continue
        if cell_source(cell).splitlines()[0] != heading:
            continue
        for following in cells[index + 1 :]:
            if following.get("cell_type") == "code":
                return cell_source(following)
            if following.get("cell_type") == "markdown":
                break
    raise AssertionError(f"No code cell follows notebook heading {heading!r}")


def notebook_function(source: str, name: str):
    tree = ast.parse(source)
    function_nodes = [
        node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert any(node.name == name for node in function_nodes), f"Missing function {name}"
    import_nodes = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    module = ast.Module(body=[*import_nodes, *function_nodes], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict = {}
    exec(compile(module, NOTEBOOK_PATH.as_posix(), "exec"), namespace)
    return namespace[name]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_json(payload: dict) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def create_complete_tokenizer(root: Path) -> str:
    root.mkdir(parents=True)
    tokenizer_path = root / "tokenizer.json"
    write_json(tokenizer_path, {"model": {"type": "BPE"}})
    digest = sha256_file(tokenizer_path)
    write_json(root / "special_tokens.json", {"tokenizer_sha256": digest})
    return digest


def create_complete_shards(
    payload_root: Path,
    metadata_root: Path,
    tokenizer_sha256: str,
    splits: tuple[str, ...] = ("train", "validation"),
) -> None:
    payload_root.mkdir(parents=True)
    split_payloads = {}
    for split in splits:
        shard_name = f"{split}_00000.bin"
        shard_path = payload_root / shard_name
        shard_path.write_bytes(b"\x01\x00\x02\x00")
        metadata = {
            "split": split,
            "tokenizer_sha256": tokenizer_sha256,
            "dtype": "uint16",
            "total_tokens": 2,
            "shards": [
                {
                    "path": str(metadata_root / shard_name),
                    "num_tokens": 2,
                    "sha256": sha256_file(shard_path),
                }
            ],
        }
        metadata["metadata_sha256"] = sha256_json(metadata)
        write_json(payload_root / f"{split}_metadata.json", metadata)
        split_payloads[split] = metadata
    combined = {"splits": split_payloads}
    combined["metadata_sha256"] = sha256_json(combined)
    write_json(payload_root / "metadata.json", combined)


def test_colab_stage_cells_remain_in_operator_order():
    headings = [
        cell_source(cell).splitlines()[0]
        for cell in notebook_cells()
        if cell.get("cell_type") == "markdown" and cell_source(cell).strip()
    ]

    expected = [
        "## 1. Choose one stage",
        "## 2. Mount Google Drive",
        "## 3. Locate or clone the project",
        "## 4. Install dependencies",
        "## 5. Authenticate Hugging Face and W&B",
        "## 6. Gate storage and the GPU",
        "## 7. Build the fixed-path Colab config",
        "## 8. Prepare once, then synchronize",
        "## 9. Gate training with preflight and benchmark evidence",
        "## 10. Run the selected training stage",
        "## 11. Evaluate every available review checkpoint",
        "## 12. Review the persisted gate evidence",
        "## 13. Generate from the checkpoint",
    ]
    assert [heading for heading in headings if heading in expected] == expected


def test_colab_clone_cell_reports_git_errors_and_supports_private_repo_token():
    source = code_source_after_heading("## 3. Locate or clone the project")

    assert "GITHUB_TOKEN" in source
    assert "capture_output=True" in source
    assert "Git clone failed" in source
    assert "git_pull" in source


def test_colab_run_command_reports_subprocess_stdout_and_stderr():
    source = code_source_after_heading("## 8. Prepare once, then synchronize")

    assert "def run_command(command):" in source
    assert "capture_output=True" in source
    assert "Command failed" in source
    assert "result.stderr" in source


def test_colab_selectable_configs_exist_validate_and_are_pinned():
    source = code_source_after_heading("## 7. Build the fixed-path Colab config")
    tree = ast.parse(source)
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "base_config_path" for target in node.targets)
    )
    selectable_paths = {
        Path(node.value)
        for node in ast.walk(assignment.value)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.endswith(".yaml")
    }

    assert selectable_paths == set(APPROVED_DATASET_REVISIONS)
    for path in selectable_paths:
        assert path.is_file(), f"Notebook-selectable config is not tracked locally: {path}"
        cfg = load_config(path)
        expected_dataset, expected_revision = APPROVED_DATASET_REVISIONS[path]
        assert cfg["dataset"]["hf_name"] == expected_dataset
        assert cfg["dataset"]["revision"] == expected_revision


def test_colab_uses_full_schedule_and_structured_stage_branches():
    settings = code_source_after_heading("## 1. Choose one stage")
    gate_source = code_source_after_heading(
        "## 9. Gate training with preflight and benchmark evidence"
    )
    training_source = code_source_after_heading("## 10. Run the selected training stage")
    training_tree = ast.parse(training_source)

    stage_values = [
        node.comparators[0].value
        for node in ast.walk(training_tree)
        if isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == "RUN_STAGE"
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.Eq)
        and len(node.comparators) == 1
        and isinstance(node.comparators[0], ast.Constant)
    ]

    assert 'RUN_STAGE = "prepare"' in settings
    assert '"smoke", "pilot", "full", "evaluate"' in settings
    assert "SMOKE_MAX_STEPS = 20" in settings
    assert "PILOT_STOP_STEP = 306" in settings
    assert 'cfg["training"]["max_tokens"] = 200_000' not in settings
    assert "scripts/preflight_t4.py" in gate_source
    assert "--require-t4" in gate_source
    assert stage_values == ["smoke", "pilot", "full"]


def test_colab_prepare_produces_t4_gate_evidence_without_pretraining(
    tmp_path: Path,
):
    device_source = code_source_after_heading("## 6. Gate storage and the GPU")
    prepare_source = code_source_after_heading("## 8. Prepare once, then synchronize")
    gate_source = code_source_after_heading(
        "## 9. Gate training with preflight and benchmark evidence"
    )
    training_source = code_source_after_heading("## 10. Run the selected training stage")
    prepare_artifacts_for_stage = notebook_function(
        prepare_source, "prepare_artifacts_for_stage"
    )
    run_evidence_gate = notebook_function(gate_source, "run_evidence_gate")
    run_dir = tmp_path / "run"
    commands: list[list[str]] = []
    messages: list[str] = []
    lifecycle: list[str] = []

    benchmark_payload = {
        "results": [
            {
                "batch_size": 8,
                "status": "ok",
                "loss": 1.0,
                "grad_norm": 0.5,
                "tokens_per_second": 100.0,
                "memory_fraction": 0.5,
            }
        ]
    }

    def command_spy(command):
        commands.append(command)
        if "scripts/preflight_t4.py" in command:
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "preflight.json").write_text(
                json.dumps({"status": "pass"}), encoding="utf-8"
            )
        stdout = (
            json.dumps(benchmark_payload)
            if "scripts/benchmark_t4.py" in command
            else ""
        )
        return SimpleNamespace(stdout=stdout)

    prepare_artifacts_for_stage(
        run_stage="prepare",
        preparation_steps=[
            (
                "normalized",
                "normalized dataset",
                ["python", "scripts/prepare_dataset.py", "--config", "colab.yaml"],
            ),
            (
                "tokenizer",
                "tokenizer",
                ["python", "scripts/train_tokenizer.py", "--config", "colab.yaml"],
            ),
            (
                "shards",
                "token shards",
                ["python", "scripts/tokenize_and_shard.py", "--config", "colab.yaml"],
            ),
        ],
        local_root=tmp_path / "local",
        artifact_status_fn=lambda _name, _path: (False, "missing"),
        run_command_fn=command_spy,
        validate_artifact_fn=lambda _name, _path: lifecycle.append("validate"),
        validate_all_fn=lambda: lifecycle.append("validate_all"),
        sync_fn=lambda: lifecycle.append("sync"),
        emit=messages.append,
    )
    run_evidence_gate(
        run_stage="prepare",
        config_path=Path("colab.yaml"),
        run_output_dir=run_dir,
        batch_sizes="8,16,24,32",
        micro_batch_size=8,
        run_command_fn=command_spy,
        emit=messages.append,
    )
    exec(
        compile(training_source, NOTEBOOK_PATH.as_posix(), "exec"),
        {
            "RUN_STAGE": "prepare",
            "cfg": {"run": {"output_dir": str(run_dir)}},
            "colab_config_path": Path("colab.yaml"),
            "SMOKE_MAX_STEPS": 20,
            "RESUME_CHECK_STEPS": 5,
            "PILOT_STOP_STEP": 306,
            "run_command": command_spy,
            "torch": SimpleNamespace(),
            "Path": Path,
        },
    )

    assert [command[1] for command in commands] == [
        "scripts/prepare_dataset.py",
        "scripts/train_tokenizer.py",
        "scripts/tokenize_and_shard.py",
        "scripts/preflight_t4.py",
        "scripts/benchmark_t4.py",
    ]
    assert lifecycle == ["validate", "validate", "validate", "validate_all", "sync"]
    assert json.loads((run_dir / "preflight.json").read_text()) == {"status": "pass"}
    assert json.loads((run_dir / "benchmark.json").read_text()) == benchmark_payload
    assert any("Stop here" in message and "before selecting smoke" in message for message in messages)
    assert not any("scripts/pretrain.py" in command for command in commands)
    assert not (run_dir / "checkpoints").exists()

    assert 'if RUN_STAGE in {"prepare", "smoke", "pilot", "full"}:' in device_source
    assert prepare_source.count("prepare_artifacts_for_stage(") == 2
    assert gate_source.count("run_evidence_gate(") == 2
    assert "scripts/pretrain.py" not in prepare_source
    assert "scripts/pretrain.py" not in gate_source
    assert 'if RUN_STAGE == "prepare"' not in training_source


@pytest.mark.parametrize(
    ("run_stage", "expects_evidence"),
    [
        ("prepare", True),
        ("smoke", True),
        ("pilot", True),
        ("full", True),
        ("evaluate", False),
    ],
)
def test_colab_evidence_gate_covers_every_stage(
    tmp_path: Path,
    run_stage: str,
    expects_evidence: bool,
):
    gate_source = code_source_after_heading(
        "## 9. Gate training with preflight and benchmark evidence"
    )
    run_evidence_gate = notebook_function(gate_source, "run_evidence_gate")
    run_dir = tmp_path / run_stage
    commands: list[list[str]] = []
    messages: list[str] = []
    benchmark_payload = {
        "results": [
            {
                "batch_size": 8,
                "status": "ok",
                "loss": 1.0,
                "grad_norm": 0.5,
                "tokens_per_second": 100.0,
                "memory_fraction": 0.5,
            }
        ]
    }

    def command_spy(command):
        commands.append(command)
        if "scripts/preflight_t4.py" in command:
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "preflight.json").write_text(
                json.dumps({"status": "pass"}), encoding="utf-8"
            )
        stdout = (
            json.dumps(benchmark_payload)
            if "scripts/benchmark_t4.py" in command
            else ""
        )
        return SimpleNamespace(stdout=stdout)

    result = run_evidence_gate(
        run_stage=run_stage,
        config_path=Path("colab.yaml"),
        run_output_dir=run_dir,
        batch_sizes="8,16,24,32",
        micro_batch_size=8,
        run_command_fn=command_spy,
        emit=messages.append,
    )

    if expects_evidence:
        assert [command[1] for command in commands] == [
            "scripts/preflight_t4.py",
            "scripts/benchmark_t4.py",
        ]
        assert result is not None
        assert (run_dir / "preflight.json").is_file()
        assert (run_dir / "benchmark.json").is_file()
    else:
        assert commands == []
        assert result is None
        assert messages == [
            "Preflight and benchmark evidence gates skipped for 'evaluate'."
        ]


def test_colab_smoke_recovery_plans_absent_step_20_and_step_25_lineages():
    source = code_source_after_heading("## 10. Run the selected training stage")
    smoke_actions_for_step = notebook_function(source, "smoke_actions_for_step")

    assert smoke_actions_for_step(None) == ("initial", "resume_check")
    assert smoke_actions_for_step(20) == ("resume_check",)
    assert smoke_actions_for_step(25) == ()


@pytest.mark.parametrize("invalid_step", [-1, 0, 19, 21, 24, 26, 306])
def test_colab_smoke_recovery_rejects_every_other_checkpoint_lineage(invalid_step):
    source = code_source_after_heading("## 10. Run the selected training stage")
    smoke_actions_for_step = notebook_function(source, "smoke_actions_for_step")

    with pytest.raises(AssertionError, match="Unexpected smoke checkpoint lineage"):
        smoke_actions_for_step(invalid_step)


def test_colab_smoke_branch_asserts_exact_post_command_steps():
    source = code_source_after_heading("## 10. Run the selected training stage")
    tree = ast.parse(source)
    called_functions = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assertion_calls = sorted(
        [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "assert_checkpoint_step"
        ],
        key=lambda node: node.lineno,
    )
    asserted_steps = [
        argument.value
        for node in assertion_calls
        for argument in node.args[1:2]
        if isinstance(argument, ast.Constant)
    ]

    assert "smoke_actions_for_step" in called_functions
    assert asserted_steps == [20, 20, 25, 306]


def test_colab_full_stage_asserts_configured_schedule_completion(tmp_path: Path):
    source = code_source_after_heading("## 10. Run the selected training stage")
    run_dir = tmp_path / "run"
    latest = run_dir / "checkpoints" / "latest.pt"
    latest.parent.mkdir(parents=True)
    latest.write_bytes(b"checkpoint")
    current_step = {"value": 306}
    observed_checkpoint_steps: list[int] = []
    cfg = {
        "run": {"output_dir": str(run_dir)},
        "model": {"context_length": 256},
        "training": {
            "micro_batch_size": 16,
            "gradient_accumulation_steps": 8,
            "max_tokens": 200_000_000,
            "warmup_ratio": 0.02,
        },
    }

    def load_checkpoint_step(*args, **kwargs):
        observed_checkpoint_steps.append(current_step["value"])
        return {"state": {"global_step": current_step["value"]}}

    def run_command_spy(command):
        assert "scripts/pretrain.py" in command
        current_step["value"] = 6104
        return SimpleNamespace(stdout="")

    exec(
        compile(source, NOTEBOOK_PATH.as_posix(), "exec"),
        {
            "RUN_STAGE": "full",
            "cfg": cfg,
            "colab_config_path": Path("colab.yaml"),
            "SMOKE_MAX_STEPS": 20,
            "RESUME_CHECK_STEPS": 5,
            "PILOT_STOP_STEP": 306,
            "run_command": run_command_spy,
            "torch": SimpleNamespace(load=load_checkpoint_step),
            "Path": Path,
        },
    )

    assert observed_checkpoint_steps == [306, 6104]


def test_colab_evaluate_requires_latest_and_best_checkpoints(tmp_path: Path):
    source = code_source_after_heading("## 11. Evaluate every available review checkpoint")
    run_dir = tmp_path / "run"
    latest = run_dir / "checkpoints" / "latest.pt"
    latest.parent.mkdir(parents=True)
    latest.write_bytes(b"checkpoint")

    with pytest.raises(AssertionError, match="best.pt"):
        exec(
            compile(source, NOTEBOOK_PATH.as_posix(), "exec"),
            {
                "RUN_STAGE": "evaluate",
                "cfg": {"run": {"output_dir": str(run_dir)}},
                "colab_config_path": Path("colab.yaml"),
                "run_command": lambda command: SimpleNamespace(stdout=""),
                "Path": Path,
            },
        )


def test_colab_evaluate_verifies_resume_before_summary(tmp_path: Path):
    source = code_source_after_heading("## 11. Evaluate every available review checkpoint")
    run_dir = tmp_path / "run"
    checkpoint_dir = run_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True)
    latest = checkpoint_dir / "latest.pt"
    best = checkpoint_dir / "best.pt"
    latest.write_bytes(b"latest")
    best.write_bytes(b"best")
    commands: list[list[str]] = []

    def run_command_spy(command):
        commands.append(command)
        if "--verify-only" in command:
            return SimpleNamespace(
                stdout=json.dumps(
                    {"resume_verified": True, "state": {"global_step": 306}}
                )
            )
        return SimpleNamespace(stdout="")

    exec(
        compile(source, NOTEBOOK_PATH.as_posix(), "exec"),
        {
            "RUN_STAGE": "evaluate",
            "cfg": {"run": {"output_dir": str(run_dir)}},
            "colab_config_path": Path("colab.yaml"),
            "run_command": run_command_spy,
            "Path": Path,
        },
    )

    assert [command[1] for command in commands] == [
        "scripts/evaluate.py",
        "scripts/evaluate.py",
        "scripts/pretrain.py",
        "scripts/summarize_run.py",
    ]
    assert commands[2][-3:] == ["--resume-from", str(latest), "--verify-only"]
    resume_report = json.loads((run_dir / "resume_verification.json").read_text())
    assert resume_report["resume_verified"] is True
    assert resume_report["state"]["global_step"] == 306


def test_colab_separates_fast_local_data_from_persistent_drive_artifacts():
    source = code_source_after_heading("## 7. Build the fixed-path Colab config")

    assert 'LOCAL_ROOT = Path("/content/matgpt_work")' in source
    assert 'DRIVE_ROOT = Path("/content/drive/MyDrive/matgpt_artifacts")' in source
    assert "restore_artifacts_from_drive" in source
    assert "sync_artifacts_to_drive" in source


def test_colab_tokenizer_and_shard_completeness_checks_payload_integrity(tmp_path: Path):
    source = code_source_after_heading("## 7. Build the fixed-path Colab config")
    validate_tokenizer_artifacts = notebook_function(source, "validate_tokenizer_artifacts")
    validate_shard_artifacts = notebook_function(source, "validate_shard_artifacts")
    tokenizer_root = tmp_path / "tokenizer"
    tokenizer_sha256 = create_complete_tokenizer(tokenizer_root)
    metadata_root = tmp_path / "expected-local-shards"
    shard_root = tmp_path / "shard-snapshot"
    create_complete_shards(shard_root, metadata_root, tokenizer_sha256)

    validate_tokenizer_artifacts(tokenizer_root)
    validate_shard_artifacts(
        shard_root,
        metadata_root=metadata_root,
        splits=("train", "validation"),
        tokenizer_sha256=tokenizer_sha256,
    )

    (shard_root / "validation_00000.bin").unlink()
    with pytest.raises(ValueError, match="Referenced shard payload is missing"):
        validate_shard_artifacts(
            shard_root,
            metadata_root=metadata_root,
            splits=("train", "validation"),
            tokenizer_sha256=tokenizer_sha256,
        )


def test_colab_sync_publishes_a_validated_replacement_without_merging(tmp_path: Path):
    source = code_source_after_heading("## 7. Build the fixed-path Colab config")
    publish_directory_snapshot = notebook_function(source, "publish_directory_snapshot")
    local = tmp_path / "local"
    drive = tmp_path / "drive" / "artifact"
    local.mkdir()
    drive.mkdir(parents=True)
    (local / "complete.json").write_text("{}", encoding="utf-8")
    (drive / "stale.bin").write_bytes(b"stale")

    def validate_snapshot(path: Path) -> None:
        assert (path / "complete.json").is_file()

    publish_directory_snapshot(local, drive, validate_snapshot)

    assert (drive / "complete.json").is_file()
    assert not (drive / "stale.bin").exists()
    assert not list(drive.parent.glob(".artifact.syncing-*"))
    assert not list(drive.parent.glob(".artifact.backup-*"))


def test_colab_preparation_uses_force_rebuild_completeness_and_temp_snapshots():
    settings = code_source_after_heading("## 1. Choose one stage")
    config_source = code_source_after_heading("## 7. Build the fixed-path Colab config")
    prepare_source = code_source_after_heading("## 8. Prepare once, then synchronize")
    prepare_tree = ast.parse(prepare_source)
    call_lines = {
        node.func.id: node.lineno
        for node in ast.walk(prepare_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "FORCE_REBUILD_PREPARED = False" in settings
    assert 'assert not FORCE_REBUILD_PREPARED or RUN_STAGE == "prepare"' in settings
    assert "def remove_ephemeral_artifact" in config_source
    assert "relative_to(LOCAL_ROOT.resolve())" in config_source
    assert ".syncing-" in config_source
    assert ".restoring-" in config_source
    assert "dirs_exist_ok=True" not in config_source
    assert "validate_all_fn" in call_lines
    assert "sync_fn" in call_lines
    assert call_lines["validate_all_fn"] < call_lines["sync_fn"]
    assert "validate_all_fn=validate_all_prepared_artifacts" in prepare_source
    assert "sync_fn=sync_artifacts_to_drive" in prepare_source
