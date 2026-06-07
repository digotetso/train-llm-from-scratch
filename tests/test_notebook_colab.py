import json
from pathlib import Path


def test_colab_clone_cell_reports_git_errors_and_supports_private_repo_token():
    notebook = json.loads(Path("notebooks/train_matgpt_t4_base_colab.ipynb").read_text(encoding="utf-8"))
    source = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )

    assert "GITHUB_TOKEN" in source
    assert "capture_output=True" in source
    assert "Git clone failed" in source
    assert "git_pull" in source
