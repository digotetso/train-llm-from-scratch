from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

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
    '    text = unicodedata.normalize("NFKC", str(text))',
    r'    text = text.replace("\r\n", "\n").replace("\r", "\n")',
    r'    lines = [line.rstrip() for line in text.split("\n")]',
    r'    text = "\n".join(lines).strip()',
    "    return text",
)

PREPARE_CODE_LINES = (
    "normalized = normalize_text(text)",
    "return {",
    '    "text": normalized,',
    '    "num_chars": len(normalized),',
    "}",
)


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
    heading.next_to(background.get_top(), DOWN, buff=0.28)
    heading.align_to(background, LEFT).shift(0.3 * RIGHT)
    code_lines = VGroup(
        *(
            Text(
                line or " ",
                font="Monospace",
                font_size=line_font_size,
                color=PALETTE["text"],
            )
            for line in lines
        )
    ).arrange(DOWN, aligned_edge=LEFT, buff=0.13)
    if code_lines.width > width - 0.7:
        code_lines.scale_to_fit_width(width - 0.7)
    if code_lines.height > height - 1.05:
        code_lines.scale_to_fit_height(height - 1.05)
    code_lines.next_to(heading, DOWN, buff=0.3).align_to(heading, LEFT)
    return VGroup(background, heading, code_lines), code_lines


def make_value_row(values: Iterable[str | int], *, color: str, width: float = 1.55) -> VGroup:
    return VGroup(
        *(
            make_card(str(value), color=color, width=width, height=1.05, font_size=30)
            for value in values
        )
    ).arrange(RIGHT, buff=0.25)


def make_pipeline(labels: Iterable[str]) -> VGroup:
    nodes = []
    for index, label in enumerate(labels):
        role = "fixed" if index < 2 else "learning"
        if label.casefold() == "error":
            role = "error"
        nodes.append(
            make_card(
                label,
                color=PALETTE[role],
                width=2.15,
                height=0.95,
                font_size=24,
            )
        )

    parts: list[Mobject] = []
    for index, node in enumerate(nodes):
        parts.append(node)
        if index < len(nodes) - 1:
            parts.append(
                Arrow(
                    LEFT,
                    RIGHT,
                    color=PALETTE["detail"],
                    buff=0,
                    stroke_width=3,
                ).scale(0.45)
            )
    return fit_to_frame(VGroup(*parts).arrange(RIGHT, buff=0.2))


class TimedLessonScene(Scene):
    def setup(self) -> None:
        super().setup()
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
            self.beat(seconds, *(FadeOut(mobject) for mobject in tuple(self.mobjects)))
        else:
            self.hold(seconds)

    def section_title(self, text: str) -> Text:
        title = make_text(text, font_size=30, color=PALETTE["detail"], weight=BOLD)
        return title.to_edge(UP, buff=0.28)
