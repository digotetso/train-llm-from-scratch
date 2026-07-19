import json
from pathlib import Path


def notebook_code_source() -> str:
    notebook = json.loads(Path("notebooks/train_matgpt_t4_base_colab.ipynb").read_text(encoding="utf-8"))
    return "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )


def test_colab_clone_cell_reports_git_errors_and_supports_private_repo_token():
    source = notebook_code_source()

    assert "GITHUB_TOKEN" in source
    assert "capture_output=True" in source
    assert "Git clone failed" in source
    assert "git_pull" in source


def test_colab_run_command_reports_subprocess_stdout_and_stderr():
    source = notebook_code_source()

    assert "def run_command(command):" in source
    assert "capture_output=True" in source
    assert "Command failed" in source
    assert "result.stderr" in source


def test_colab_model_picker_uses_59m_config_name():
    source = notebook_code_source()

    assert '"tiny_59m"' in source
    assert "configs/matgpt_tiny_59m.yaml" in source


def test_colab_uses_full_schedule_for_smoke_and_stage_gates():
    source = notebook_code_source()
    assert 'RUN_STAGE = "prepare"' in source
    assert '"smoke", "pilot", "full", "evaluate"' in source
    assert "SMOKE_MAX_STEPS = 20" in source
    assert "PILOT_STOP_STEP = 306" in source
    assert 'cfg["training"]["max_tokens"] = 200_000' not in source
    assert "scripts/preflight_t4.py" in source
    assert "--require-t4" in source


def test_colab_separates_fast_local_data_from_persistent_drive_artifacts():
    source = notebook_code_source()
    assert 'LOCAL_ROOT = Path("/content/matgpt_work")' in source
    assert 'DRIVE_ROOT = Path("/content/drive/MyDrive/matgpt_artifacts")' in source
    assert "restore_artifacts_from_drive" in source
    assert "sync_artifacts_to_drive" in source
