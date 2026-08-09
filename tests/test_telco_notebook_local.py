import ast
import json
from pathlib import Path


NOTEBOOK = Path("notebooks/prepare_matgpt_telco_300m_local.ipynb")


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


def test_local_notebook_exposes_only_data_and_tokenizer_stages():
    source = "\n".join(_source(cell) for cell in _cells())
    for stage in (
        "tokenizer_sample",
        "tokenizer_candidate",
        "tokenizer_compare",
        "tokenizer_select",
    ):
        assert stage in source
    assert "scripts/train.py" not in source
    assert "scripts/pretrain.py" not in source
    assert "run_pretraining" not in source
    assert "FULL_APPROVED" not in source


def test_local_notebook_requires_distinct_local_and_drive_roots():
    source = "\n".join(_source(cell) for cell in _cells())

    assert "LOCAL_WORK_ROOT.resolve() != DRIVE_PUBLISH_ROOT.resolve()" in source
    assert "Stream files" in source
    assert "Available offline" in source


def test_local_notebook_has_tutorial_handoff_flow():
    headings = [
        _source(cell).splitlines()[0]
        for cell in _cells()
        if cell.get("cell_type") == "markdown" and _source(cell).strip()
    ]

    assert [
        heading
        for heading in headings
        if heading in {"## Goal", "## Setup", "## Steps", "## Checks", "## Next Steps"}
    ] == ["## Goal", "## Setup", "## Steps", "## Checks", "## Next Steps"]


def test_local_notebook_builds_one_deterministic_cli_command():
    source = _code_after_heading("### 2. Build and preview the command")
    tree = ast.parse(source)
    stage_values = {
        key.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        for key in node.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }

    assert {
        "tokenizer_sample",
        "tokenizer_candidate",
        "tokenizer_compare",
        "tokenizer_select",
    }.issubset(stage_values)
    assert "scripts/prepare_telco_local.py" in source
    assert "shlex.join(command)" in source


def test_local_notebook_streams_live_output_without_capture():
    source = _code_after_heading("### 3. Run the selected stage")

    assert "subprocess.Popen" in source
    assert "stdout=subprocess.PIPE" in source
    assert "stderr=subprocess.STDOUT" in source
    assert "for line in process.stdout" in source
    assert "capture_output=True" not in source
