# Video 001 Manim Animation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, verify, and render a timestamp-aligned 14-minute ManimCE animation for Video 001.

**Architecture:** A single `Video001ComputerLearningFromText` scene owns eight named Manim sections and delegates each timestamped segment to a focused method. Literal timeline and copy contracts remain inspectable without importing the optional Manim dependency; runtime helpers validate timing, scale development previews, and keep every section within its declared budget.

**Tech Stack:** Python 3.11+ for video work, Manim Community 0.20.1, Pango text rendering, pytest 8+, uv, FFmpeg/ffprobe, Markdown. The repository's non-video workflows retain their Python 3.10+ support.

## Global Constraints

- Preserve the user's modified `course/videos/001-computer-learning-from-text/script.md`, untracked `course/labs/`, and untracked `og_script_v1.md`.
- Use Manim Community Edition 0.20.1, not ManimGL.
- Keep Manim in the optional `video` dependency group with a Python 3.11+ environment marker; training and ordinary course workflows must retain Python 3.10+ support and must not require video tooling.
- Produce one silent 1920x1080, 30 fps, 16:9 MP4.
- Normal timing must total exactly 840 seconds with boundaries at 0, 45, 120, 240, 360, 540, 720, 780, and 840 seconds.
- Preview timing must preserve content and order while applying `VIDEO001_TIMING_SCALE=0.05`.
- Use only generated vector shapes and rendered text/code; add no stock media.
- Keep fixed representation cyan `#58C4DD`, learning green `#83C167`, context amber `#F5C451`, error coral `#FF6B6B`, primary text `#F3F6FA`, detail `#8B95A7`, and background `#0B1020`.
- Do not use token, tensor, logit, gradient, attention, or token embedding as an on-screen explanation.
- Label the 7-to-5 error sequence `Illustration—not observed training output`.
- Show NFKC as `① -> 1` with `Policy choice—not lossless cleanup`.
- Do not execute or mutate `lab.py` during rendering; display its verified output as immutable copy.
- Follow test-driven development and commit only intentional files after each task.

---

## File Structure

- Create `course/videos/001-computer-learning-from-text/animation.py`: literal content contracts, timing validation, visual helpers, and all eight scene methods.
- Create `course/videos/001-computer-learning-from-text/manim.cfg`: final resolution, frame rate, colors, output name, and media directory.
- Create `tests/test_video_001_animation.py`: standard-library contract tests plus Manim-enabled runtime tests.
- Modify `tests/test_course_structure.py`: include the approved animation artifacts in the exact Video 001 file contract.
- Modify `pyproject.toml`: add the optional pinned Manim dependency.
- Modify `uv.lock`: lock Manim and transitive packages reproducibly.
- Modify `.gitignore`: exclude generated Video 001 media.
- Modify `course/videos/001-computer-learning-from-text/evidence.md`: record exact render commands and observed media metadata.

---

### Task 1: Reproducible Toolchain and Static Animation Contract

**Files:**
- Create: `tests/test_video_001_animation.py`
- Create: `course/videos/001-computer-learning-from-text/animation.py`
- Create: `course/videos/001-computer-learning-from-text/manim.cfg`
- Modify: `tests/test_course_structure.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: the approved timestamp anchors and palette from `scenes.md`.
- Produces: `TIMELINE_DATA`, `PALETTE`, `LAB_OUTPUT_LINES`, `NORMALIZE_CODE_LINES`, `PREPARE_CODE_LINES`, and a locked `video` dependency group.

- [ ] **Step 1: Extend the exact course artifact contract and write failing static tests**

Add the three animation artifacts to `REQUIRED_VIDEO_FILES` in `tests/test_course_structure.py`:

```python
REQUIRED_VIDEO_FILES = {
    "animation.py",
    "answer-key.md",
    "evidence.md",
    "lab.md",
    "lab.py",
    "lesson.md",
    "manim.cfg",
    "quiz.md",
    "scenes.md",
    "script.md",
}
```

Create `tests/test_video_001_animation.py` with:

```python
import ast
import configparser
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest


VIDEO_DIR = Path("course/videos/001-computer-learning-from-text")
ANIMATION_PATH = VIDEO_DIR / "animation.py"
CONFIG_PATH = VIDEO_DIR / "manim.cfg"


def literal_assignment(name: str):
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
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    cli = config["CLI"]
    assert cli.getint("pixel_width") == 1920
    assert cli.getint("pixel_height") == 1080
    assert cli.getint("frame_rate") == 30
    assert cli["background_color"] == "#0B1020"
    assert cli["output_file"] == "video-001-computer-learning-from-text"
    assert cli["media_dir"] == "course/videos/001-computer-learning-from-text/media"
```

- [ ] **Step 2: Run the new tests and verify the intended RED state**

Run:

```bash
python -m pytest tests/test_course_structure.py::test_video_one_has_exact_required_artifacts tests/test_video_001_animation.py -v
```

Expected: failure because `animation.py`, `manim.cfg`, and the optional `video` dependency do not exist.

- [ ] **Step 3: Add the optional dependency and media ignore rule**

Add to `[project.optional-dependencies]` in `pyproject.toml`:

```toml
video = [
  "manim==0.20.1; python_version >= '3.11'",
]
```

Append to `.gitignore`:

```gitignore

# Generated Manim video output
course/videos/001-computer-learning-from-text/media/
```

Refresh the lock file:

```bash
uv lock
```

Expected: exit 0 and `uv.lock` contains `name = "manim"` with version `0.20.1` in the optional video resolution.

- [ ] **Step 4: Create the literal animation contract**

Create `course/videos/001-computer-learning-from-text/animation.py` with:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Mapping

from manim import *


PALETTE = {
    "background": "#0B1020",
    "fixed": "#58C4DD",
    "learning": "#83C167",
    "context": "#F5C451",
    "error": "#FF6B6B",
    "text": "#F3F6FA",
    "detail": "#8B95A7",
}

TIMELINE_DATA = (
    {"slug": "hook", "name": "00:00 Hook", "start": 0, "duration": 45, "method": "show_hook"},
    {
        "slug": "fixed-versus-adjustable",
        "name": "00:45 Fixed versus adjustable",
        "start": 45,
        "duration": 75,
        "method": "show_fixed_versus_adjustable",
    },
    {
        "slug": "technical-meaning",
        "name": "02:00 Technical meaning",
        "start": 120,
        "duration": 120,
        "method": "show_technical_meaning",
    },
    {
        "slug": "tiny-example",
        "name": "04:00 Tiny example",
        "start": 240,
        "duration": 120,
        "method": "show_tiny_example",
    },
    {
        "slug": "repository-walkthrough",
        "name": "06:00 Repository walkthrough",
        "start": 360,
        "duration": 180,
        "method": "show_repository_walkthrough",
    },
    {
        "slug": "live-mini-lab",
        "name": "09:00 Live mini-lab",
        "start": 540,
        "duration": 180,
        "method": "show_live_mini_lab",
    },
    {
        "slug": "common-mistake",
        "name": "12:00 Common mistake",
        "start": 720,
        "duration": 60,
        "method": "show_common_mistake",
    },
    {
        "slug": "recap-and-exercise",
        "name": "13:00 Recap and exercise",
        "start": 780,
        "duration": 60,
        "method": "show_recap_and_exercise",
    },
)

LAB_OUTPUT_LINES = (
    "Human text: Cat",
    "Character numbers: [67, 97, 116]",
    "UTF-8 bytes: [67, 97, 116]",
    "Can the mathematical model use this raw Python string as numeric input? No",
    "Learning begins after text is represented as numbers.",
)

NORMALIZE_CODE_LINES = (
    "def normalize_text(text: str) -> str:",
    "    text = unicodedata.normalize(\"NFKC\", str(text))",
    r'    text = text.replace("\r\n", "\n").replace("\r", "\n")',
    r'    lines = [line.rstrip() for line in text.split("\n")]',
    r'    text = "\n".join(lines).strip()',
    "    return text",
)

PREPARE_CODE_LINES = (
    "normalized = normalize_text(text)",
    "return {",
    "    \"text\": normalized,",
    "    \"num_chars\": len(normalized),",
    "}",
)
```

- [ ] **Step 5: Create the final render configuration**

Create `course/videos/001-computer-learning-from-text/manim.cfg` with:

```ini
[CLI]
pixel_width = 1920
pixel_height = 1080
frame_rate = 30
background_color = #0B1020
media_dir = course/videos/001-computer-learning-from-text/media
output_file = video-001-computer-learning-from-text
disable_caching = False
write_to_movie = True
```

- [ ] **Step 6: Run the static contract tests**

Run:

```bash
python -m pytest tests/test_course_structure.py::test_video_one_has_exact_required_artifacts tests/test_video_001_animation.py -v
```

Expected: all static tests pass. The module is parsed but not imported, so this command remains valid without the optional video environment.

- [ ] **Step 7: Commit the toolchain and contract**

```bash
git add .gitignore pyproject.toml uv.lock tests/test_course_structure.py tests/test_video_001_animation.py course/videos/001-computer-learning-from-text/animation.py course/videos/001-computer-learning-from-text/manim.cfg
git commit -m "feat: add Video 001 animation contract"
```

---

### Task 2: Validated Timing Runtime and Shared Visual System

**Files:**
- Modify: `tests/test_video_001_animation.py`
- Modify: `course/videos/001-computer-learning-from-text/animation.py`

**Interfaces:**
- Consumes: `TIMELINE_DATA`, `PALETTE`, and `VIDEO001_TIMING_SCALE`.
- Produces: `SectionSpec`, `timeline()`, `validate_timeline()`, `timing_scale()`, `select_sections()`, `SectionClock`, `make_text()`, `make_card()`, `make_panel()`, `make_value_row()`, `make_pipeline()`, and `TimedLessonScene`.

- [ ] **Step 1: Write failing runtime and layout tests**

Append to `tests/test_video_001_animation.py`:

```python
import importlib.util


def load_animation_module():
    pytest.importorskip("manim")
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


def test_shared_cards_fit_the_safe_frame_width():
    animation = load_animation_module()
    card = animation.make_card("A deliberately long beginner-facing label", color=animation.PALETTE["fixed"])
    animation.fit_to_frame(card)
    assert card.width <= animation.config.frame_width - 0.7
    assert card.height <= animation.config.frame_height - 0.7
```

- [ ] **Step 2: Run the focused tests and verify the intended failures**

Run:

```bash
python -m pytest tests/test_video_001_animation.py::test_runtime_timeline_validation_and_selection tests/test_video_001_animation.py::test_timing_scale_is_positive_and_no_greater_than_one tests/test_video_001_animation.py::test_section_clock_rejects_overspending_and_reports_remainder tests/test_video_001_animation.py::test_shared_cards_fit_the_safe_frame_width -v
```

Expected: failure because the runtime and visual helper interfaces are absent.

- [ ] **Step 3: Add validated timing and selection interfaces**

Append below the literal constants in `animation.py`:

```python
@dataclass(frozen=True)
class SectionSpec:
    slug: str
    name: str
    start: float
    duration: float
    method: str

    @property
    def end(self) -> float:
        return self.start + self.duration


def timeline() -> tuple[SectionSpec, ...]:
    return tuple(SectionSpec(**item) for item in TIMELINE_DATA)


def validate_timeline(specs: Iterable[SectionSpec]) -> None:
    items = tuple(specs)
    if not items:
        raise ValueError("Video 001 timeline must not be empty")
    if len({item.slug for item in items}) != len(items):
        raise ValueError("Video 001 section slugs must be unique")
    expected_start = 0.0
    for item in items:
        if item.duration <= 0:
            raise ValueError(f"Section {item.slug} must have positive duration")
        if item.start != expected_start:
            raise ValueError(f"Section {item.slug} is not contiguous at {expected_start:g}s")
        expected_start = item.end
    if expected_start != 840:
        raise ValueError(f"Video 001 must total 840s, got {expected_start:g}s")


def timing_scale(raw: str | None = None) -> float:
    value = os.getenv("VIDEO001_TIMING_SCALE", "1") if raw is None else raw
    try:
        scale = float(value)
    except ValueError as exc:
        raise ValueError("VIDEO001_TIMING_SCALE must be a number in (0, 1]") from exc
    if not 0 < scale <= 1:
        raise ValueError("VIDEO001_TIMING_SCALE must be a number in (0, 1]")
    return scale


def select_sections(slug: str | None = None) -> tuple[SectionSpec, ...]:
    specs = timeline()
    validate_timeline(specs)
    requested = os.getenv("VIDEO001_SECTION") if slug is None else slug
    if not requested:
        return specs
    selected = tuple(item for item in specs if item.slug == requested)
    if not selected:
        raise ValueError(f"Unknown Video 001 section: {requested}")
    return selected


@dataclass
class SectionClock:
    budget: float
    used: float = 0.0

    def consume(self, seconds: float) -> None:
        if seconds <= 0:
            raise ValueError("Timed beats must be positive")
        if self.used + seconds > self.budget + 1e-9:
            raise ValueError(
                f"Timed beat exceeds section budget: {self.used + seconds:g}s > {self.budget:g}s"
            )
        self.used += seconds

    @property
    def remaining(self) -> float:
        return max(0.0, self.budget - self.used)
```

- [ ] **Step 4: Add shared frame-safe visual helpers**

Append:

```python
def fit_to_frame(mobject: Mobject, margin: float = 0.35) -> Mobject:
    max_width = config.frame_width - 2 * margin
    max_height = config.frame_height - 2 * margin
    if mobject.width > max_width:
        mobject.scale_to_fit_width(max_width)
    if mobject.height > max_height:
        mobject.scale_to_fit_height(max_height)
    return mobject


def make_text(
    content: str,
    *,
    font_size: float = 36,
    color: str | ManimColor | None = None,
    weight: str = NORMAL,
) -> Text:
    return Text(
        content,
        font="Sans",
        font_size=font_size,
        color=color or PALETTE["text"],
        weight=weight,
    )


def make_card(
    content: str,
    *,
    color: str,
    width: float = 3.2,
    height: float = 1.25,
    font_size: float = 32,
) -> VGroup:
    box = RoundedRectangle(
        width=width,
        height=height,
        corner_radius=0.18,
        stroke_color=color,
        stroke_width=3,
        fill_color=PALETTE["background"],
        fill_opacity=0.92,
    )
    label = make_text(content, font_size=font_size)
    if label.width > width - 0.35:
        label.scale_to_fit_width(width - 0.35)
    return VGroup(box, label.move_to(box))


def make_panel(
    title: str,
    lines: Iterable[str],
    *,
    accent: str,
    width: float = 12.5,
    height: float = 6.1,
    line_font_size: float = 24,
) -> tuple[VGroup, VGroup]:
    background = RoundedRectangle(
        width=width,
        height=height,
        corner_radius=0.2,
        stroke_color=accent,
        stroke_width=2.5,
        fill_color="#11182A",
        fill_opacity=0.98,
    )
    heading = make_text(title, font_size=26, color=accent, weight=BOLD)
    heading.next_to(background.get_top(), DOWN, buff=0.28).align_to(background, LEFT).shift(0.3 * RIGHT)
    code_lines = VGroup(
        *(Text(line or " ", font="Monospace", font_size=line_font_size, color=PALETTE["text"]) for line in lines)
    ).arrange(DOWN, aligned_edge=LEFT, buff=0.13)
    if code_lines.width > width - 0.7:
        code_lines.scale_to_fit_width(width - 0.7)
    if code_lines.height > height - 1.05:
        code_lines.scale_to_fit_height(height - 1.05)
    code_lines.next_to(heading, DOWN, buff=0.3).align_to(heading, LEFT)
    return VGroup(background, heading, code_lines), code_lines


def make_value_row(values: Iterable[str | int], *, color: str, width: float = 1.55) -> VGroup:
    return VGroup(
        *(make_card(str(value), color=color, width=width, height=1.05, font_size=30) for value in values)
    ).arrange(RIGHT, buff=0.25)


def make_pipeline(labels: Iterable[str]) -> VGroup:
    nodes = [make_card(label, color=PALETTE["fixed" if index < 2 else "learning"], width=2.15, height=0.95, font_size=24) for index, label in enumerate(labels)]
    parts: list[Mobject] = []
    for index, node in enumerate(nodes):
        parts.append(node)
        if index < len(nodes) - 1:
            parts.append(Arrow(LEFT, RIGHT, color=PALETTE["detail"], buff=0, stroke_width=3).scale(0.45))
    return fit_to_frame(VGroup(*parts).arrange(RIGHT, buff=0.2))
```

- [ ] **Step 5: Add the timed scene base class**

Append:

```python
class TimedLessonScene(Scene):
    def setup(self) -> None:
        self._timing_scale = timing_scale()
        self._section_clock: SectionClock | None = None
        self.camera.background_color = PALETTE["background"]

    def begin_timed_section(self, spec: SectionSpec) -> None:
        self._section_clock = SectionClock(spec.duration)

    def beat(self, seconds: float, *animations: Animation) -> None:
        if self._section_clock is None:
            raise RuntimeError("begin_timed_section must run before beat")
        self._section_clock.consume(seconds)
        self.play(*animations, run_time=seconds * self._timing_scale)

    def hold(self, seconds: float) -> None:
        if self._section_clock is None:
            raise RuntimeError("begin_timed_section must run before hold")
        self._section_clock.consume(seconds)
        self.wait(seconds * self._timing_scale)

    def finish_timed_section(self) -> None:
        if self._section_clock is None:
            raise RuntimeError("No active timed section")
        remaining = self._section_clock.remaining
        if remaining:
            self._section_clock.consume(remaining)
            self.wait(remaining * self._timing_scale)
        self._section_clock = None

    def clear_stage(self, seconds: float = 2) -> None:
        if self.mobjects:
            self.beat(seconds, FadeOut(VGroup(*self.mobjects)))
        else:
            self.hold(seconds)

    def section_title(self, text: str) -> Text:
        title = make_text(text, font_size=30, color=PALETTE["detail"], weight=BOLD)
        return title.to_edge(UP, buff=0.28)
```

- [ ] **Step 6: Run runtime tests and import the module with the video environment**

Run:

```bash
uv run --extra test --extra video pytest tests/test_video_001_animation.py -v
uv run --extra video python -c 'import importlib.util; p="course/videos/001-computer-learning-from-text/animation.py"; s=importlib.util.spec_from_file_location("video001", p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.timeline()[-1].end)'
```

Expected: tests pass and the import command prints `840`.

- [ ] **Step 7: Commit the timing runtime and visual helpers**

```bash
git add tests/test_video_001_animation.py course/videos/001-computer-learning-from-text/animation.py
git commit -m "feat: add timed Manim visual system"
```

---

### Task 3: Hook Through Tiny Example

**Files:**
- Modify: `tests/test_video_001_animation.py`
- Modify: `course/videos/001-computer-learning-from-text/animation.py`

**Interfaces:**
- Consumes: `TimedLessonScene` and all shared visual helpers.
- Produces: `ON_SCREEN_COPY` plus complete section methods for `hook`, `fixed-versus-adjustable`, `technical-meaning`, and `tiny-example`.

- [ ] **Step 1: Write failing copy and section-dispatch tests**

Append to `tests/test_video_001_animation.py`:

```python
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


def test_first_four_section_methods_exist():
    animation = load_animation_module()
    for method in [
        "show_hook",
        "show_fixed_versus_adjustable",
        "show_technical_meaning",
        "show_tiny_example",
    ]:
        assert callable(getattr(animation.Video001PartOnePreview, method))
```

- [ ] **Step 2: Run the focused tests and verify the intended failures**

Run:

```bash
uv run --extra test --extra video pytest tests/test_video_001_animation.py::test_on_screen_copy_contains_required_distinctions_without_deferred_explanations tests/test_video_001_animation.py::test_first_four_section_methods_exist -v
```

Expected: failure because `ON_SCREEN_COPY` and `Video001PartOnePreview` are absent.

- [ ] **Step 3: Add the immutable on-screen copy contract**

Add above `SectionSpec` in `animation.py`:

```python
ON_SCREEN_COPY = {
    "hook": (
        "cat",
        "PERSON",
        "PYTHON PROGRAM",
        "Why must text become numbers before a model can learn patterns?",
    ),
    "fixed-versus-adjustable": (
        "A",
        "U+0041",
        "65",
        "FIXED REPRESENTATION",
        "ADJUSTABLE PARAMETERS",
    ),
    "technical-meaning": (
        "character",
        "code point",
        "byte: 0–255",
        "These match here—not for every character",
        "prediction",
        "error",
    ),
    "tiny-example": (
        "cat sat",
        "cat ran",
        "cat slept",
        "numeric processing ≠ human meaning",
        "Illustration—not observed training output",
    ),
    "repository-walkthrough": (
        "Policy choice—not lossless cleanup",
        "PREPARATION ≠ LEARNING",
    ),
    "live-mini-lab": (
        "Predict first",
        "Cat",
        "A",
    ),
    "common-mistake": (
        "65 = meaning of A",
        "representation ≠ meaning",
        "fixed mapping",
        "learning update",
    ),
    "recap-and-exercise": (
        "TEXT",
        "NUMBERS",
        "PREDICTION",
        "ERROR",
        "PARAMETER UPDATE",
        "The number 65 is assigned to ___, but it does not encode ___.",
    ),
}
```

- [ ] **Step 4: Implement the first four timestamped sections**

Append the class below `TimedLessonScene`:

```python
class Video001PartOnePreview(TimedLessonScene):
    def construct(self) -> None:
        for spec in select_sections():
            if spec.start >= 360:
                continue
            self.next_section(spec.name)
            self.begin_timed_section(spec)
            getattr(self, spec.method)()
            self.finish_timed_section()

    def show_hook(self) -> None:
        word = make_text("cat", font_size=96, weight=BOLD)
        self.beat(4, Write(word))
        self.hold(6)

        human_word = word.copy().move_to(3.4 * LEFT + 1.3 * UP)
        program_word = word.copy().move_to(3.4 * RIGHT + 1.3 * UP)
        divider = Line(3.1 * UP, 3.1 * DOWN, color=PALETTE["detail"], stroke_opacity=0.5)
        self.beat(6, Transform(word, human_word), TransformFromCopy(word, program_word), Create(divider))

        human, _ = make_panel("PERSON", ["animal", "memory", "sound"], accent=PALETTE["context"], width=5.5, height=3.4, line_font_size=28)
        human.move_to(3.4 * LEFT + 0.7 * DOWN)
        program, _ = make_panel("PYTHON PROGRAM", ['text = "cat"', "c    a    t"], accent=PALETTE["fixed"], width=5.5, height=3.4, line_font_size=28)
        program.move_to(3.4 * RIGHT + 0.7 * DOWN)
        self.beat(8, FadeIn(human, shift=UP), FadeIn(program, shift=UP))
        self.hold(8)

        objective = make_card(
            "Why must text become numbers before a model can learn patterns?",
            color=PALETTE["fixed"],
            width=11.8,
            height=1.55,
            font_size=34,
        )
        self.beat(5, FadeOut(VGroup(*self.mobjects)))
        self.beat(4, FadeIn(objective, scale=0.95))
        self.hold(4)

    def show_fixed_versus_adjustable(self) -> None:
        self.clear_stage(2)
        title = self.section_title("Fixed representation and adjustable parameters")
        mapping = VGroup(
            make_card("A", color=PALETTE["context"], width=1.5),
            Arrow(LEFT, RIGHT, color=PALETTE["detail"], buff=0).scale(0.6),
            make_card("U+0041", color=PALETTE["fixed"], width=2.4),
            make_card("65", color=PALETTE["fixed"], width=1.5),
        ).arrange(RIGHT, buff=0.35).shift(1.4 * UP)
        self.beat(8, FadeIn(title), LaggedStart(*(FadeIn(item) for item in mapping), lag_ratio=0.15))

        contexts = VGroup(
            *(make_card(label, color=PALETTE["context"], width=2.2, height=0.9, font_size=25) for label in ["grade", "musical note", "blood type", "inside a word"])
        ).arrange(RIGHT, buff=0.25).next_to(mapping, DOWN, buff=0.7)
        self.beat(12, LaggedStart(*(FadeIn(card, shift=UP) for card in contexts), lag_ratio=0.2))
        self.hold(8)

        fixed_lane, _ = make_panel("FIXED REPRESENTATION", ["A  →  65", "same rule every time"], accent=PALETTE["fixed"], width=5.8, height=2.6, line_font_size=27)
        learning_lane, _ = make_panel("ADJUSTABLE PARAMETERS", ["values change", "when error guides an update"], accent=PALETTE["learning"], width=5.8, height=2.6, line_font_size=27)
        lanes = VGroup(fixed_lane, learning_lane).arrange(RIGHT, buff=0.45)
        self.beat(10, FadeTransform(VGroup(mapping, contexts), lanes), FadeOut(title))

        slider_lines = VGroup(*(Line(ORIGIN, 1.3 * RIGHT, color=PALETTE["learning"]) for _ in range(3))).arrange(DOWN, buff=0.28)
        slider_dots = VGroup(*(Dot(line.get_start(), color=PALETTE["learning"]) for line in slider_lines))
        sliders = VGroup(slider_lines, slider_dots).move_to(learning_lane).shift(0.55 * DOWN)
        self.beat(8, FadeIn(sliders))
        self.beat(8, *[dot.animate.move_to(line.get_end()) for dot, line in zip(slider_dots, slider_lines)])
        self.hold(19)

    def show_technical_meaning(self) -> None:
        self.clear_stage(2)
        title = self.section_title("Characters become numeric representations")
        characters = make_value_row(["C", "a", "t"], color=PALETTE["context"]).shift(2.0 * UP)
        numbers = make_value_row([67, 97, 116], color=PALETTE["fixed"]).shift(0.3 * UP)
        ord_label = make_card("ord(character)", color=PALETTE["fixed"], width=3.2, height=0.9, font_size=26).move_to(0.85 * UP)
        self.beat(4, FadeIn(title))
        self.beat(6, LaggedStart(*(FadeIn(card) for card in characters), lag_ratio=0.2))
        self.beat(15, FadeIn(ord_label), LaggedStart(*(TransformFromCopy(source, target) for source, target in zip(characters, numbers)), lag_ratio=0.25))
        self.hold(8)

        bits = VGroup(*(Square(0.45, stroke_color=PALETTE["fixed"], fill_color=PALETTE["background"], fill_opacity=1) for _ in range(8))).arrange(RIGHT, buff=0.08)
        bit_values = VGroup(*(make_text(bit, font_size=20) for bit in "01000011"))
        for bit, cell in zip(bit_values, bits):
            bit.move_to(cell)
        byte = VGroup(bits, bit_values).next_to(numbers, DOWN, buff=0.7)
        byte_label = make_text("byte: 0–255", font_size=28, color=PALETTE["fixed"]).next_to(byte, DOWN, buff=0.25)
        self.beat(8, FadeIn(byte))
        self.beat(5, FadeIn(byte_label))

        bytes_row = numbers.copy().set_color(PALETTE["fixed"]).shift(2.2 * DOWN)
        warning = make_card("These match here—not for every character", color=PALETTE["error"], width=8.1, height=0.85, font_size=25).to_edge(DOWN, buff=0.28)
        self.beat(10, TransformFromCopy(numbers, bytes_row))
        self.beat(6, FadeIn(warning))
        self.hold(8)

        model, _ = make_panel("SMALLEST USEFUL MODEL", ["numeric input", "prediction", "measured error", "adjustable parameters"], accent=PALETTE["learning"], width=7.8, height=4.1, line_font_size=30)
        self.beat(8, FadeOut(VGroup(*self.mobjects)), FadeIn(model))
        prediction = make_card("prediction", color=PALETTE["learning"], width=2.6).next_to(model, RIGHT, buff=0.35)
        error = make_card("error", color=PALETTE["error"], width=2.0).next_to(prediction, DOWN, buff=0.4)
        parameters = make_card("adjustable parameters", color=PALETTE["learning"], width=3.6).next_to(model, DOWN, buff=0.35)
        self.beat(6, FadeIn(prediction))
        self.beat(6, FadeIn(error))
        self.beat(6, FadeIn(parameters))
        self.hold(22)

    def show_tiny_example(self) -> None:
        self.clear_stage(2)
        title = self.section_title("A repeatable relationship in examples")
        examples = VGroup(*(make_text(line, font_size=42) for line in ["cat sat", "cat ran", "cat slept"])).arrange(DOWN, aligned_edge=LEFT, buff=0.32).shift(2.8 * LEFT)
        self.beat(4, FadeIn(title))
        self.beat(12, LaggedStart(*(Write(line) for line in examples), lag_ratio=0.3))

        highlights = VGroup(*(SurroundingRectangle(line[:3], color=PALETTE["fixed"], buff=0.08) for line in examples))
        self.beat(8, LaggedStart(*(Create(box) for box in highlights), lag_ratio=0.2))
        self.hold(8)

        hand_check, _ = make_panel("HAND CHECK", ["C     a     t", "67    97    116", "length = 3", "sequences can be compared"], accent=PALETTE["fixed"], width=5.5, height=3.9, line_font_size=28)
        hand_check.shift(3.1 * RIGHT + 0.4 * DOWN)
        self.beat(10, FadeIn(hand_check, shift=LEFT))
        misconception = make_card("numeric processing ≠ human meaning", color=PALETTE["error"], width=6.2, height=0.9, font_size=26).to_edge(DOWN, buff=0.3)
        self.beat(8, FadeIn(misconception))

        before_cells = VGroup(*(Square(0.5, stroke_color=PALETTE["detail"], fill_color=PALETTE["error"] if index < 7 else PALETTE["learning"], fill_opacity=0.85) for index in range(10))).arrange(RIGHT, buff=0.1)
        after_cells = VGroup(*(Square(0.5, stroke_color=PALETTE["detail"], fill_color=PALETTE["error"] if index < 5 else PALETTE["learning"], fill_opacity=0.85) for index in range(10))).arrange(RIGHT, buff=0.1)
        boards = VGroup(VGroup(make_text("before: 7/10 errors", font_size=27), before_cells).arrange(DOWN), VGroup(make_text("after: 5/10 errors", font_size=27), after_cells).arrange(DOWN)).arrange(DOWN, buff=0.55)
        disclaimer = make_card("Illustration—not observed training output", color=PALETTE["error"], width=7.2, height=0.8, font_size=24).to_edge(DOWN, buff=0.25)
        self.beat(10, FadeOut(VGroup(*self.mobjects)), FadeIn(boards), FadeIn(disclaimer))
        self.beat(10, Indicate(after_cells, color=PALETTE["learning"]))

        loop = make_pipeline(["examples", "prediction", "error", "update", "evaluate later"]).shift(1.3 * UP)
        self.beat(12, FadeTransform(boards, loop))
        self.hold(36)
```

- [ ] **Step 5: Run the content tests and render each first-half section in preview mode**

Run:

```bash
uv run --extra test --extra video pytest tests/test_video_001_animation.py -v
VIDEO001_SECTION=hook VIDEO001_TIMING_SCALE=0.05 manim -ql --config_file course/videos/001-computer-learning-from-text/manim.cfg course/videos/001-computer-learning-from-text/animation.py Video001PartOnePreview
VIDEO001_SECTION=fixed-versus-adjustable VIDEO001_TIMING_SCALE=0.05 manim -ql --config_file course/videos/001-computer-learning-from-text/manim.cfg course/videos/001-computer-learning-from-text/animation.py Video001PartOnePreview
VIDEO001_SECTION=technical-meaning VIDEO001_TIMING_SCALE=0.05 manim -ql --config_file course/videos/001-computer-learning-from-text/manim.cfg course/videos/001-computer-learning-from-text/animation.py Video001PartOnePreview
VIDEO001_SECTION=tiny-example VIDEO001_TIMING_SCALE=0.05 manim -ql --config_file course/videos/001-computer-learning-from-text/manim.cfg course/videos/001-computer-learning-from-text/animation.py Video001PartOnePreview
```

Expected: tests pass; each render exits 0 and writes a non-empty low-quality MP4 under `course/videos/001-computer-learning-from-text/media/videos/animation/480p15/`.

- [ ] **Step 6: Commit the first four sections**

```bash
git add tests/test_video_001_animation.py course/videos/001-computer-learning-from-text/animation.py
git commit -m "feat: animate Video 001 foundations"
```

---

### Task 4: Repository Walkthrough Through Recap

**Files:**
- Modify: `tests/test_video_001_animation.py`
- Modify: `course/videos/001-computer-learning-from-text/animation.py`

**Interfaces:**
- Consumes: the part-one section methods, literal code/output contracts, and shared helpers.
- Produces: the final `Video001ComputerLearningFromText` scene with all eight section methods.

- [ ] **Step 1: Write failing full-scene and source-accuracy tests**

Append to `tests/test_video_001_animation.py`:

```python
def test_repository_excerpt_lines_are_present_in_the_approved_script():
    script = (VIDEO_DIR / "script.md").read_text(encoding="utf-8")
    for line in (*literal_assignment("NORMALIZE_CODE_LINES"), *literal_assignment("PREPARE_CODE_LINES")):
        assert line.strip() in script


def test_final_scene_implements_every_timeline_method():
    animation = load_animation_module()
    for spec in animation.timeline():
        assert callable(getattr(animation.Video001ComputerLearningFromText, spec.method))


def test_final_scene_is_the_only_non_preview_delivery_scene():
    animation = load_animation_module()
    assert issubclass(animation.Video001ComputerLearningFromText, animation.TimedLessonScene)
    assert not hasattr(animation, "Video001PartOnePreview")
```

- [ ] **Step 2: Run the tests and verify the intended failures**

Run:

```bash
uv run --extra test --extra video pytest tests/test_video_001_animation.py::test_repository_excerpt_lines_are_present_in_the_approved_script tests/test_video_001_animation.py::test_final_scene_implements_every_timeline_method tests/test_video_001_animation.py::test_final_scene_is_the_only_non_preview_delivery_scene -v
```

Expected: failure because the final delivery scene and its last four methods are absent.

- [ ] **Step 3: Rename the part-one class and add full-scene dispatch**

Rename `Video001PartOnePreview` to `_Video001PartOne`. Replace its `construct` method with:

```python
    def construct(self) -> None:
        for spec in select_sections():
            self.next_section(spec.name)
            self.begin_timed_section(spec)
            getattr(self, spec.method)()
            self.finish_timed_section()
```

Then append:

```python
class Video001ComputerLearningFromText(_Video001PartOne):
    pass
```

The following steps replace `pass` by adding the last four methods directly to this class.

- [ ] **Step 4: Implement the repository walkthrough**

Replace `pass` with:

```python
    def show_repository_walkthrough(self) -> None:
        self.clear_stage(2)
        title = self.section_title("Repository walkthrough: preparation before learning")
        normalize_panel, normalize_lines = make_panel(
            "matgpt/data/normalize.py",
            NORMALIZE_CODE_LINES,
            accent=PALETTE["fixed"],
            width=12.4,
            height=5.7,
            line_font_size=23,
        )
        normalize_panel.shift(0.25 * DOWN)
        self.beat(4, FadeIn(title))
        self.beat(10, FadeIn(normalize_panel, shift=UP))

        marker = SurroundingRectangle(normalize_lines[0], color=PALETTE["context"], buff=0.07)
        self.beat(8, Create(marker))
        for line in normalize_lines[1:]:
            target = SurroundingRectangle(line, color=PALETTE["context"], buff=0.07)
            self.beat(10, Transform(marker, target))
            self.hold(3)

        nfkc = VGroup(
            make_card("①", color=PALETTE["context"], width=1.4),
            Arrow(LEFT, RIGHT, color=PALETTE["detail"], buff=0).scale(0.6),
            make_card("1", color=PALETTE["fixed"], width=1.4),
        ).arrange(RIGHT, buff=0.35).shift(0.8 * UP)
        warning = make_card("Policy choice—not lossless cleanup", color=PALETTE["error"], width=7.2, height=0.95, font_size=27).next_to(nfkc, DOWN, buff=0.55)
        self.beat(10, FadeOut(VGroup(normalize_panel, marker, title)), FadeIn(nfkc))
        self.beat(8, FadeIn(warning))
        self.hold(8)

        prepare_panel, _ = make_panel(
            "matgpt/data/prepare.py",
            PREPARE_CODE_LINES,
            accent=PALETTE["fixed"],
            width=7.0,
            height=4.1,
            line_font_size=25,
        )
        record = make_card('{"text": normalized, "num_chars": len(normalized)}', color=PALETTE["fixed"], width=5.1, height=1.45, font_size=23)
        record.next_to(prepare_panel, RIGHT, buff=0.35)
        self.beat(10, FadeOut(VGroup(nfkc, warning)), FadeIn(prepare_panel))
        self.beat(12, FadeIn(record, shift=RIGHT))
        separation = make_card("PREPARATION ≠ LEARNING", color=PALETTE["error"], width=6.2, height=0.95, font_size=29).to_edge(DOWN, buff=0.3)
        self.beat(8, FadeIn(separation))
        self.hold(30)
```

- [ ] **Step 5: Implement the live mini-lab**

Add to `Video001ComputerLearningFromText`:

```python
    def show_live_mini_lab(self) -> None:
        self.clear_stage(2)
        title = self.section_title("Live mini-lab: predict, run, explain")
        source_lines = (
            'text = "Cat"',
            'print("Human text:", text)',
            'print("Character numbers:", [ord(character) for character in text])',
            'print("UTF-8 bytes:", list(text.encode("utf-8")))',
            'print("Can the mathematical model use this raw Python string as numeric input? No")',
            'print("Learning begins after text is represented as numbers.")',
        )
        source_panel, source = make_panel("lab.py", source_lines, accent=PALETTE["fixed"], width=12.5, height=5.8, line_font_size=21)
        source_panel.shift(0.25 * DOWN)
        self.beat(4, FadeIn(title))
        self.beat(10, FadeIn(source_panel))
        self.beat(8, Indicate(source[0], color=PALETTE["context"]))

        predict = VGroup(
            make_card("Predict first", color=PALETTE["context"], width=3.0),
            make_card("[67, 97, 116]", color=PALETTE["fixed"], width=3.5),
            make_card("[67, 97, 116]", color=PALETTE["fixed"], width=3.5),
        ).arrange(DOWN, buff=0.3)
        self.beat(10, FadeOut(VGroup(source_panel, title)), FadeIn(predict))
        self.hold(10)

        command = "python course/videos/001-computer-learning-from-text/lab.py"
        terminal_panel, terminal_lines = make_panel(
            "TERMINAL",
            (f"$ {command}", *LAB_OUTPUT_LINES),
            accent=PALETTE["learning"],
            width=12.7,
            height=6.2,
            line_font_size=21,
        )
        self.beat(12, FadeTransform(predict, terminal_panel))
        for line in terminal_lines[1:]:
            self.beat(7, Indicate(line, color=PALETTE["fixed"]))
        self.hold(10)

        edit = VGroup(
            make_card('text = "Cat"', color=PALETTE["fixed"], width=3.6),
            Arrow(LEFT, RIGHT, color=PALETTE["detail"], buff=0).scale(0.6),
            make_card('text = "A"', color=PALETTE["context"], width=3.6),
            make_card("[65]", color=PALETTE["fixed"], width=2.0),
        ).arrange(RIGHT, buff=0.35)
        self.beat(12, FadeOut(terminal_panel), FadeIn(edit))
        restore = make_card('restore: text = "Cat"', color=PALETTE["learning"], width=4.8).next_to(edit, DOWN, buff=0.7)
        self.beat(8, FadeIn(restore))
        self.hold(45)
```

- [ ] **Step 6: Implement the common-mistake correction**

Add:

```python
    def show_common_mistake(self) -> None:
        self.clear_stage(2)
        fixed = VGroup(
            make_card("A", color=PALETTE["context"], width=1.5),
            make_card("65", color=PALETTE["fixed"], width=1.5),
        ).arrange(RIGHT, buff=0.5).shift(1.5 * UP)
        contexts = VGroup(*(make_card(label, color=PALETTE["context"], width=2.3, height=0.85, font_size=24) for label in ["grade", "note", "blood type", "word"])).arrange(RIGHT, buff=0.25)
        self.beat(6, FadeIn(fixed))
        self.beat(8, LaggedStart(*(FadeIn(card, shift=UP) for card in contexts), lag_ratio=0.2))
        self.beat(6, Indicate(fixed[1], color=PALETTE["fixed"]))

        false_claim = make_card("65 = meaning of A", color=PALETTE["error"], width=4.4).shift(1.6 * DOWN)
        strike = Line(false_claim.get_corner(LEFT + DOWN), false_claim.get_corner(RIGHT + UP), color=PALETTE["error"], stroke_width=6)
        self.beat(6, FadeIn(false_claim))
        self.beat(4, Create(strike))

        comparison = VGroup(
            make_card("fixed mapping", color=PALETTE["fixed"], width=3.0),
            make_card("learning update", color=PALETTE["learning"], width=3.0),
        ).arrange(RIGHT, buff=1.1)
        self.beat(8, FadeOut(VGroup(*self.mobjects)), FadeIn(comparison))
        self.hold(20)
```

- [ ] **Step 7: Implement the recap and exercise**

Add:

```python
    def show_recap_and_exercise(self) -> None:
        self.clear_stage(2)
        pipeline = make_pipeline(["TEXT", "NUMBERS", "PREDICTION", "ERROR", "PARAMETER UPDATE"]).shift(1.8 * UP)
        self.beat(8, LaggedStart(*(FadeIn(part, shift=RIGHT) for part in pipeline), lag_ratio=0.1))

        recap = VGroup(
            make_text("1  Programs receive represented data.", font_size=29),
            make_text("2  Unicode and UTF-8 define numeric representations.", font_size=29),
            make_text("3  Representation is not human meaning or learning.", font_size=29),
            make_text("4  Learning updates parameters to reduce prediction error.", font_size=29),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.24).next_to(pipeline, DOWN, buff=0.65)
        self.beat(10, LaggedStart(*(FadeIn(line, shift=UP) for line in recap), lag_ratio=0.18))
        self.hold(8)

        exercise = make_card(
            "The number 65 is assigned to ___, but it does not encode ___.",
            color=PALETTE["context"],
            width=11.8,
            height=1.35,
            font_size=31,
        ).shift(0.5 * UP)
        restore = make_card('Return lab.py to text = "Cat"', color=PALETTE["learning"], width=6.0, height=0.9, font_size=26).next_to(exercise, DOWN, buff=0.55)
        next_video = make_text("Next: assigned character numbers in more detail", font_size=27, color=PALETTE["detail"]).to_edge(DOWN, buff=0.35)
        self.beat(8, FadeOut(VGroup(pipeline, recap)), FadeIn(exercise))
        self.beat(6, FadeIn(restore))
        self.beat(4, FadeIn(next_video))
        self.hold(14)
```

- [ ] **Step 8: Run all animation tests and render the second-half sections**

Run:

```bash
uv run --extra test --extra video pytest tests/test_video_001_animation.py -v
VIDEO001_SECTION=repository-walkthrough VIDEO001_TIMING_SCALE=0.05 manim -ql --config_file course/videos/001-computer-learning-from-text/manim.cfg course/videos/001-computer-learning-from-text/animation.py Video001ComputerLearningFromText
VIDEO001_SECTION=live-mini-lab VIDEO001_TIMING_SCALE=0.05 manim -ql --config_file course/videos/001-computer-learning-from-text/manim.cfg course/videos/001-computer-learning-from-text/animation.py Video001ComputerLearningFromText
VIDEO001_SECTION=common-mistake VIDEO001_TIMING_SCALE=0.05 manim -ql --config_file course/videos/001-computer-learning-from-text/manim.cfg course/videos/001-computer-learning-from-text/animation.py Video001ComputerLearningFromText
VIDEO001_SECTION=recap-and-exercise VIDEO001_TIMING_SCALE=0.05 manim -ql --config_file course/videos/001-computer-learning-from-text/manim.cfg course/videos/001-computer-learning-from-text/animation.py Video001ComputerLearningFromText
```

Expected: tests pass and all four preview renders exit 0.

- [ ] **Step 9: Commit the complete scene**

```bash
git add tests/test_video_001_animation.py course/videos/001-computer-learning-from-text/animation.py
git commit -m "feat: complete Video 001 Manim scene"
```

---

### Task 5: Full Preview Render and Visual QA

**Files:**
- Modify: `course/videos/001-computer-learning-from-text/animation.py` only if an exact safe-frame assertion fails.

**Interfaces:**
- Consumes: `Video001ComputerLearningFromText` and `VIDEO001_TIMING_SCALE=0.05`.
- Produces: one 42-second low-quality full preview and four representative PNG frames.

- [ ] **Step 1: Render the full accelerated master scene with saved sections**

Run:

```bash
VIDEO001_TIMING_SCALE=0.05 manim -ql --save_sections --config_file course/videos/001-computer-learning-from-text/manim.cfg course/videos/001-computer-learning-from-text/animation.py Video001ComputerLearningFromText
```

Expected: exit 0, one full preview MP4, and eight named section clips.

- [ ] **Step 2: Verify preview duration and media integrity**

Run:

```bash
ffprobe -v error -show_entries format=duration -show_entries stream=codec_name,width,height,r_frame_rate -of json course/videos/001-computer-learning-from-text/media/videos/animation/480p15/video-001-computer-learning-from-text.mp4
```

Expected JSON values: H.264, 854x480, 15 fps, and a duration between 41.5 and
42.5 seconds. The tolerance accounts for frame quantization at the accelerated
15 fps preview rate. A representative result has this shape:

```json
{
  "streams": [
    {
      "codec_name": "h264",
      "width": 854,
      "height": 480,
      "r_frame_rate": "15/1"
    }
  ],
  "format": {
    "duration": "approximately 42 seconds"
  }
}
```

- [ ] **Step 3: Extract four representative frames**

Run:

```bash
ffmpeg -y -ss 1.5 -i course/videos/001-computer-learning-from-text/media/videos/animation/480p15/video-001-computer-learning-from-text.mp4 -frames:v 1 /tmp/video001-hook.png
ffmpeg -y -ss 19.5 -i course/videos/001-computer-learning-from-text/media/videos/animation/480p15/video-001-computer-learning-from-text.mp4 -frames:v 1 /tmp/video001-code.png
ffmpeg -y -ss 29.5 -i course/videos/001-computer-learning-from-text/media/videos/animation/480p15/video-001-computer-learning-from-text.mp4 -frames:v 1 /tmp/video001-lab.png
ffmpeg -y -ss 40.5 -i course/videos/001-computer-learning-from-text/media/videos/animation/480p15/video-001-computer-learning-from-text.mp4 -frames:v 1 /tmp/video001-recap.png
```

Expected: four non-empty PNG files.

- [ ] **Step 4: Inspect the frames against deterministic visual criteria**

Open all four frames. Each must satisfy:

- no glyph or border intersects the image edge;
- no two text objects overlap;
- code and terminal lines remain distinguishable at 854x480;
- cyan and green lanes remain labeled, not color-only;
- warning and illustration labels remain visible whenever their claim is shown;
- the recap pipeline fits on one line.

If a panel violates the safe edge, pass it through `fit_to_frame(panel, margin=0.45)`. If a code or terminal line is illegible, change the corresponding `line_font_size` from `23` or `21` to `25` and reduce that panel to at most five simultaneously visible body lines. Re-render the affected section and repeat this inspection.

- [ ] **Step 5: Run the complete automated suite**

Run:

```bash
uv run --extra test --extra video pytest tests/test_video_001_animation.py tests/test_course_structure.py -v
uv run --extra test --extra video pytest -v
```

Expected: all focused and repository tests pass.

- [ ] **Step 6: Commit any exact visual-QA correction**

If Step 4 required a correction:

```bash
git add course/videos/001-computer-learning-from-text/animation.py
git commit -m "fix: keep Video 001 visuals frame safe"
```

If Step 4 passed without source changes, do not create an empty commit.

---

### Task 6: Final 1080p Render, Evidence, and Preflight

**Files:**
- Modify: `course/videos/001-computer-learning-from-text/evidence.md`

**Interfaces:**
- Consumes: the visually approved master scene at timing scale 1.
- Produces: the final 840-second 1920x1080 30 fps MP4 plus an evidence-backed verification record.

- [ ] **Step 1: Render the final movie at normal timing**

Run without `VIDEO001_TIMING_SCALE` and without a quality override:

```bash
manim --config_file course/videos/001-computer-learning-from-text/manim.cfg course/videos/001-computer-learning-from-text/animation.py Video001ComputerLearningFromText
```

Expected: exit 0 and the final movie at:

```text
course/videos/001-computer-learning-from-text/media/videos/animation/1080p30/video-001-computer-learning-from-text.mp4
```

- [ ] **Step 2: Verify final metadata and duration**

Run:

```bash
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height,r_frame_rate -of json course/videos/001-computer-learning-from-text/media/videos/animation/1080p30/video-001-computer-learning-from-text.mp4
```

Expected: H.264 video, width `1920`, height `1080`, frame rate `30/1`, duration `840.000000`, and a non-zero file size.

- [ ] **Step 3: Record render evidence**

Append to `course/videos/001-computer-learning-from-text/evidence.md` under `## Commands Run`:

```markdown
VIDEO001_TIMING_SCALE=0.05 manim -ql --save_sections --config_file course/videos/001-computer-learning-from-text/manim.cfg course/videos/001-computer-learning-from-text/animation.py Video001ComputerLearningFromText
manim --config_file course/videos/001-computer-learning-from-text/manim.cfg course/videos/001-computer-learning-from-text/animation.py Video001ComputerLearningFromText
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height,r_frame_rate -of json course/videos/001-computer-learning-from-text/media/videos/animation/1080p30/video-001-computer-learning-from-text.mp4
uv run --extra test --extra video pytest tests/test_video_001_animation.py tests/test_course_structure.py -v
uv run --extra test --extra video pytest -v
```

Append a dated paragraph to `## Observed Output` using the actual `ffprobe` size while preserving these verified fields:

```markdown
- On 2026-07-21, the accelerated full preview rendered all eight named sections successfully. The final render produced one H.264 MP4 at 1920x1080, 30 fps, with a duration of 840 seconds. `ffprobe` reported a non-zero file size. The focused animation/course tests and the complete repository suite passed with the `test` and `video` extras enabled.
```

- [ ] **Step 4: Run final verification from a clean command path**

Run:

```bash
git diff --check
uv run --extra test --extra video pytest tests/test_video_001_animation.py tests/test_course_structure.py -v
uv run --extra test --extra video pytest -v
python course/videos/001-computer-learning-from-text/lab.py
git status --short
```

Expected:

- `git diff --check` prints nothing and exits 0;
- both pytest commands pass;
- the lab prints the five verified lines;
- generated media is ignored;
- the user's pre-existing `script.md`, `course/labs/`, and `og_script_v1.md` changes remain present and unstaged.

- [ ] **Step 5: Commit evidence and final implementation state**

Stage only intentional tracked files that remain after the prior commits:

```bash
git add course/videos/001-computer-learning-from-text/evidence.md
git commit -m "docs: record Video 001 render evidence"
```

- [ ] **Step 6: Report the final artifact and residual risk**

Report:

- the absolute path to the final MP4;
- the exact duration, resolution, frame rate, codec, and file size from `ffprobe`;
- focused and full-suite pass counts;
- the commits created;
- confirmation that user changes remained untouched; and
- the residual pacing risk: sentence-level timing may need adjustment when recorded narration becomes available.
