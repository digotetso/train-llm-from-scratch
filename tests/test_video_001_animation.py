import ast
import configparser
import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest


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


def load_animation_module(media_dir: Path | None = None):
    manim = pytest.importorskip("manim")
    if media_dir is not None:
        manim.config.media_dir = str(media_dir)
    spec = importlib.util.spec_from_file_location("video001_animation", ANIMATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_runtime_timeline_validation_and_selection():
    animation = load_animation_module()
    specs = animation.timeline()
    animation.validate_timeline(specs)
    assert specs[-1].end == 840
    assert [item.slug for item in animation.select_sections("live-mini-lab")] == ["live-mini-lab"]
    with pytest.raises(ValueError, match="Unknown Video 001 section"):
        animation.select_sections("missing")


def test_timing_scale_is_positive_and_no_greater_than_one():
    animation = load_animation_module()
    assert animation.timing_scale("0.05") == pytest.approx(0.05)
    assert animation.timing_scale("1") == pytest.approx(1.0)
    for invalid in ["0", "-0.1", "1.01", "not-a-number"]:
        with pytest.raises(ValueError, match="VIDEO001_TIMING_SCALE"):
            animation.timing_scale(invalid)


def test_section_clock_rejects_overspending_and_reports_remainder():
    animation = load_animation_module()
    clock = animation.SectionClock(budget=45)
    clock.consume(12)
    assert clock.remaining == pytest.approx(33)
    with pytest.raises(ValueError, match="exceeds section budget"):
        clock.consume(34)


def test_shared_cards_fit_the_safe_frame_width(tmp_path):
    animation = load_animation_module(tmp_path / "manim-media")
    card = animation.make_card(
        "A deliberately long beginner-facing label",
        color=animation.PALETTE["fixed"],
    )
    animation.fit_to_frame(card)
    assert card.width <= animation.config.frame_width - 0.7
    assert card.height <= animation.config.frame_height - 0.7


def test_panel_value_row_and_pipeline_helpers_have_stable_hierarchies(tmp_path):
    animation = load_animation_module(tmp_path / "manim-media")
    panel, lines = animation.make_panel(
        "TERMINAL",
        ["first", "second"],
        accent=animation.PALETTE["fixed"],
    )
    values = animation.make_value_row([67, 97, 116], color=animation.PALETTE["fixed"])
    pipeline = animation.make_pipeline(["TEXT", "NUMBERS", "PREDICTION", "ERROR"])
    assert len(lines) == 2
    assert len(values) == 3
    assert len(pipeline) == 7
    assert pipeline[6][0].get_stroke_color().to_hex() == animation.PALETTE["error"]
    for mobject in [panel, values, pipeline]:
        animation.fit_to_frame(mobject)
        assert mobject.width <= animation.config.frame_width - 0.7


def test_timed_scene_rejects_beats_without_an_active_section():
    animation = load_animation_module()
    scene = animation.TimedLessonScene()
    scene._section_clock = None
    with pytest.raises(RuntimeError, match="begin_timed_section"):
        scene.hold(1)


def test_visual_helpers_use_supplied_temporary_media_directory(tmp_path):
    animation = load_animation_module(tmp_path / "manim-media")
    animation.make_card("cache probe", color=animation.PALETTE["fixed"])
    assert list((tmp_path / "manim-media" / "texts").glob("*.svg"))
    assert not Path("media").exists()


def test_on_screen_copy_contains_required_distinctions_without_deferred_explanations():
    copy = literal_assignment("ON_SCREEN_COPY")
    flattened = "\n".join(text for items in copy.values() for text in items).lower()
    for required in [
        "fixed representation",
        "adjustable parameters",
        "these match here—not for every character",
        "illustration—not observed training output",
        "preparation ≠ learning",
        "policy choice—not lossless cleanup",
    ]:
        assert required in flattened
    for forbidden in ["token embedding", "tensor", "logit", "gradient", "attention"]:
        assert forbidden not in flattened


def test_first_four_section_methods_remain_available_to_the_final_scene():
    animation = load_animation_module()
    for method in [
        "show_hook",
        "show_fixed_versus_adjustable",
        "show_technical_meaning",
        "show_tiny_example",
    ]:
        assert callable(getattr(animation._Video001PartOne, method))


def test_repository_excerpt_lines_are_present_in_the_approved_script():
    script = (VIDEO_DIR / "script.md").read_text(encoding="utf-8")
    for line in (
        *literal_assignment("NORMALIZE_CODE_LINES"),
        *literal_assignment("PREPARE_CODE_LINES"),
    ):
        assert line.strip() in script


def test_final_scene_implements_every_timeline_method():
    animation = load_animation_module()
    for spec in animation.timeline():
        assert callable(getattr(animation.Video001ComputerLearningFromText, spec.method))


def test_final_scene_is_the_only_non_preview_delivery_scene():
    animation = load_animation_module()
    assert issubclass(animation.Video001ComputerLearningFromText, animation.TimedLessonScene)
    assert not hasattr(animation, "Video001PartOnePreview")
