import ast
import configparser
import subprocess
import sys
import tomllib
from pathlib import Path


VIDEO_DIR = Path("course/videos/001-computer-learning-from-text")
ANIMATION_PATH = VIDEO_DIR / "animation.py"
CONFIG_PATH = VIDEO_DIR / "manim.cfg"


def literal_assignment(name: str):
    assert ANIMATION_PATH.exists(), "animation.py must define the video contract"
    tree = ast.parse(ANIMATION_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return ast.literal_eval(node.value)
    raise AssertionError(f"Missing literal assignment: {name}")


def test_video_dependency_is_optional_and_pinned():
    with Path("pyproject.toml").open("rb") as file:
        project = tomllib.load(file)
    assert project["project"]["optional-dependencies"]["video"] == [
        "manim==0.20.1; python_version >= '3.11'"
    ]


def test_timeline_matches_every_approved_script_boundary():
    timeline = literal_assignment("TIMELINE_DATA")
    assert [(item["slug"], item["start"], item["duration"]) for item in timeline] == [
        ("hook", 0, 45),
        ("fixed-versus-adjustable", 45, 75),
        ("technical-meaning", 120, 120),
        ("tiny-example", 240, 120),
        ("repository-walkthrough", 360, 180),
        ("live-mini-lab", 540, 180),
        ("common-mistake", 720, 60),
        ("recap-and-exercise", 780, 60),
    ]
    assert sum(item["duration"] for item in timeline) == 840


def test_palette_has_stable_semantic_roles():
    assert literal_assignment("PALETTE") == {
        "background": "#0B1020",
        "fixed": "#58C4DD",
        "learning": "#83C167",
        "context": "#F5C451",
        "error": "#FF6B6B",
        "text": "#F3F6FA",
        "detail": "#8B95A7",
    }


def test_displayed_lab_output_matches_the_runnable_lab():
    expected = literal_assignment("LAB_OUTPUT_LINES")
    result = subprocess.run(
        [sys.executable, str(VIDEO_DIR / "lab.py")],
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stderr == ""
    assert tuple(result.stdout.splitlines()) == expected


def test_manim_config_targets_the_final_delivery_format():
    assert CONFIG_PATH.exists(), "manim.cfg must define the final render contract"
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    cli = config["CLI"]
    assert cli.getint("pixel_width") == 1920
    assert cli.getint("pixel_height") == 1080
    assert cli.getint("frame_rate") == 30
    assert cli["background_color"] == "#0B1020"
    assert cli["output_file"] == "video-001-computer-learning-from-text"
    assert cli["media_dir"] == "course/videos/001-computer-learning-from-text/media"
