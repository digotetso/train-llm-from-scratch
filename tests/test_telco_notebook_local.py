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
        "pilot_refresh",
        "full_calibration",
        "full_resume",
        "status",
    ):
        assert stage in source
    assert "STOP_AFTER_QUOTA_TOKENS = 100_000_000" in source
    assert "ACCEPT_CALIBRATION = False" in source
    assert "OVERRIDE_CALIBRATION_GUARD = False" in source
    assert "MIGRATE_LEGACY_PILOT_PROVENANCE = False" in source
    assert 'OVERRIDE_REASON = ""' in source
    assert "scripts/train.py" not in source
    assert "scripts/pretrain.py" not in source
    assert "run_pretraining" not in source
    assert "FULL_APPROVED" not in source
    assert 'DRIVE_PUBLISH_ROOT / "recipes"' in source


def test_local_notebook_requires_distinct_local_and_drive_roots():
    source = "\n".join(_source(cell) for cell in _cells())

    assert "LOCAL_WORK_ROOT.resolve() != DRIVE_PUBLISH_ROOT.resolve()" in source
    assert "Stream files" in source
    assert "Available offline" in source


def test_local_notebook_setup_resolves_repo_when_started_from_notebooks(monkeypatch):
    setup_source = _code_after_heading("## Setup")
    expected_repo_root = Path.cwd().resolve()
    monkeypatch.chdir(NOTEBOOK.parent)

    namespace: dict = {}
    exec(compile(setup_source, str(NOTEBOOK), "exec"), namespace)

    assert namespace["REPO_ROOT"] == expected_repo_root
    assert namespace["MODEL_CONFIG"] == (
        expected_repo_root / "configs/matgpt_telco_300m.yaml"
    )


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
        "pilot_refresh",
        "full_calibration",
        "full_resume",
        "status",
    }.issubset(stage_values)
    assert "scripts/prepare_telco_local.py" in source
    assert "--baseline-provenance" in source
    assert "--migrate-legacy-pilot-provenance" in source
    assert "--stop-after-quota-tokens" in source
    assert "--accept-calibration" in source
    assert "--override-calibration-guard" in source
    assert "--override-reason" in source
    assert "shlex.join(command)" in source


def test_local_notebook_streams_live_output_without_capture():
    source = _code_after_heading("### 3. Run the selected stage")

    assert "subprocess.Popen" in source
    assert "stdout=subprocess.PIPE" in source
    assert "stderr=subprocess.STDOUT" in source
    assert "for line in process.stdout" in source
    assert "capture_output=True" not in source


def test_local_notebook_shows_current_progress_and_process_lifecycle():
    notebook_source = "\n".join(_source(cell) for cell in _cells())
    checks_source = _code_after_heading("## Checks")

    assert (
        "closing this notebook kernel stops the local process"
        in notebook_source.lower()
    )
    assert 'LOCAL_WORK_ROOT / "corpus/full"' in checks_source
    assert 'progress.json' in checks_source
    assert "json.loads" in checks_source
    assert 'selection["selected_tokenizer_sha256"]' in checks_source
    assert ".glob(" not in checks_source


def test_local_notebook_probes_configured_filesystem_and_guards_file_links():
    environment_source = _code_after_heading("### Environment and storage evidence")
    checks_source = _code_after_heading("## Checks")

    assert "storage_probe = LOCAL_WORK_ROOT" in environment_source
    assert "while not storage_probe.exists()" in environment_source
    assert "shutil.disk_usage(storage_probe)" in environment_source
    assert "shutil.disk_usage(Path.home())" not in environment_source
    assert "from IPython.display import FileLink, display" in checks_source
    assert "except ImportError" in checks_source
    assert "display(FileLink(str(result_path)))" in checks_source
