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


def make_hook_split() -> tuple[Text, Text, VGroup, VGroup, Line]:
    human_word = make_text("cat", font_size=96, weight=BOLD).move_to(
        3.4 * LEFT + 2.1 * UP
    )
    program_word = human_word.copy().move_to(3.4 * RIGHT + 2.1 * UP)
    human_panel, _ = make_panel(
        "PERSON",
        ["animal", "memory", "sound"],
        accent=PALETTE["context"],
        width=5.5,
        height=3.4,
        line_font_size=28,
    )
    human_panel.move_to(3.4 * LEFT + 0.7 * DOWN)
    program_panel, _ = make_panel(
        "PYTHON PROGRAM",
        ['text = "cat"', "c    a    t"],
        accent=PALETTE["fixed"],
        width=5.5,
        height=3.4,
        line_font_size=28,
    )
    program_panel.move_to(3.4 * RIGHT + 0.7 * DOWN)
    divider = Line(
        3.1 * UP,
        3.1 * DOWN,
        color=PALETTE["detail"],
        stroke_opacity=0.5,
    )
    return human_word, program_word, human_panel, program_panel, divider


def make_line_focus(mobject: Mobject) -> Animation:
    return Circumscribe(
        mobject,
        color=PALETTE["fixed"],
        buff=0.08,
        fade_out=True,
    )


def make_prepare_repository_layout() -> tuple[VGroup, VGroup, VGroup]:
    prepare_panel, _ = make_panel(
        "matgpt/data/prepare.py",
        PREPARE_CODE_LINES,
        accent=PALETTE["fixed"],
        width=7.0,
        height=4.1,
        line_font_size=25,
    )
    record = make_card(
        '{"text": normalized, "num_chars": len(normalized)}',
        color=PALETTE["fixed"],
        width=5.1,
        height=1.45,
        font_size=23,
    )
    VGroup(prepare_panel, record).arrange(RIGHT, buff=0.35)
    separation = make_card(
        "PREPARATION ≠ LEARNING",
        color=PALETTE["error"],
        width=6.2,
        height=0.95,
        font_size=29,
    ).to_edge(DOWN, buff=0.3)
    return prepare_panel, record, separation


def make_recap_pipeline() -> VGroup:
    return make_pipeline(
        ["TEXT", "NUMBERS", "PREDICTION", "ERROR", "PARAMETER\nUPDATE"]
    )


def make_technical_representation_stages() -> tuple[VGroup, VGroup, VGroup]:
    """Build the three stable layouts used by the technical explanation."""
    title = make_text(
        "Characters become numeric representations",
        font_size=30,
        color=PALETTE["detail"],
        weight=BOLD,
    ).to_edge(UP, buff=0.28)
    characters = make_value_row(
        ["C", "a", "t"],
        color=PALETTE["context"],
    ).move_to(2.25 * UP)
    ord_label = make_card(
        "ord(character)",
        color=PALETTE["fixed"],
        width=3.2,
        height=0.9,
        font_size=26,
    ).move_to(1.15 * UP)
    numbers = make_value_row(
        [67, 97, 116],
        color=PALETTE["fixed"],
    ).move_to(0.05 * UP)

    bit_cells = VGroup(
        *(
            Square(
                side_length=0.45,
                stroke_color=PALETTE["fixed"],
                fill_color=PALETTE["background"],
                fill_opacity=1,
            )
            for _ in range(8)
        )
    ).arrange(RIGHT, buff=0.08)
    bit_values = VGroup(*(make_text(bit, font_size=20) for bit in "01000011"))
    for bit, cell in zip(bit_values, bit_cells):
        bit.move_to(cell)
    byte = VGroup(bit_cells, bit_values).next_to(numbers, DOWN, buff=0.4)
    byte_label = make_text(
        "byte: 0–255",
        font_size=28,
        color=PALETTE["fixed"],
    ).next_to(byte, DOWN, buff=0.18)

    bytes_row = numbers.copy().move_to(1.45 * DOWN)
    warning = make_card(
        "These match here—not for every character",
        color=PALETTE["error"],
        width=8.1,
        height=0.85,
        font_size=25,
    ).to_edge(DOWN, buff=0.28)

    numeric_stage = VGroup(title, characters, ord_label, numbers)
    binary_stage = VGroup(title, characters, ord_label, numbers, byte, byte_label)
    byte_values_stage = VGroup(title, characters, ord_label, numbers, bytes_row, warning)
    return numeric_stage, binary_stage, byte_values_stage


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


class _Video001PartOne(TimedLessonScene):
    def construct(self) -> None:
        for spec in select_sections():
            self.next_section(spec.name)
            self.begin_timed_section(spec)
            getattr(self, spec.method)()
            self.finish_timed_section()

    def show_hook(self) -> None:
        word = make_text("cat", font_size=96, weight=BOLD)
        self.beat(4, Write(word))
        self.hold(6)

        human_target, program_target, human, program, divider = make_hook_split()
        program_word = word.copy()
        self.add(program_word)
        self.beat(
            6,
            word.animate.move_to(human_target),
            program_word.animate.move_to(program_target),
            Create(divider),
        )

        self.beat(8, FadeIn(human, shift=UP), FadeIn(program, shift=UP))
        self.hold(8)

        objective = make_card(
            "Why must text become numbers before a model can learn patterns?",
            color=PALETTE["fixed"],
            width=11.8,
            height=1.55,
            font_size=34,
        )
        self.beat(5, *(FadeOut(mobject) for mobject in tuple(self.mobjects)))
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
        self.beat(
            8,
            FadeIn(title),
            LaggedStart(*(FadeIn(item) for item in mapping), lag_ratio=0.15),
        )

        contexts = VGroup(
            *(
                make_card(
                    label,
                    color=PALETTE["context"],
                    width=2.2,
                    height=0.9,
                    font_size=25,
                )
                for label in ["grade", "musical note", "blood type", "inside a word"]
            )
        ).arrange(RIGHT, buff=0.25).next_to(mapping, DOWN, buff=0.7)
        self.beat(
            12,
            LaggedStart(*(FadeIn(card, shift=UP) for card in contexts), lag_ratio=0.2),
        )
        self.hold(8)

        fixed_lane, _ = make_panel(
            "FIXED REPRESENTATION",
            ["A  →  65", "same rule every time"],
            accent=PALETTE["fixed"],
            width=5.8,
            height=2.6,
            line_font_size=27,
        )
        learning_lane, _ = make_panel(
            "ADJUSTABLE PARAMETERS",
            ["values change", "when error guides an update"],
            accent=PALETTE["learning"],
            width=5.8,
            height=2.6,
            line_font_size=27,
        )
        lanes = VGroup(fixed_lane, learning_lane).arrange(RIGHT, buff=0.45)
        self.beat(
            10,
            FadeOut(mapping),
            FadeOut(contexts),
            FadeOut(title),
            FadeIn(lanes),
        )

        slider_lines = VGroup(
            *(Line(ORIGIN, 1.3 * RIGHT, color=PALETTE["learning"]) for _ in range(3))
        ).arrange(DOWN, buff=0.28)
        slider_dots = VGroup(
            *(Dot(line.get_start(), color=PALETTE["learning"]) for line in slider_lines)
        )
        sliders = VGroup(slider_lines, slider_dots).move_to(learning_lane).shift(0.55 * DOWN)
        self.beat(8, FadeIn(sliders))
        self.beat(
            8,
            *(dot.animate.move_to(line.get_end()) for dot, line in zip(slider_dots, slider_lines)),
        )
        self.hold(19)

    def show_technical_meaning(self) -> None:
        self.clear_stage(2)
        numeric_stage, binary_stage, byte_values_stage = (
            make_technical_representation_stages()
        )
        title, characters, ord_label, numbers = numeric_stage
        byte, byte_label = binary_stage[-2:]
        bytes_row, warning = byte_values_stage[-2:]
        self.beat(4, FadeIn(title))
        self.beat(
            6,
            LaggedStart(*(FadeIn(card) for card in characters), lag_ratio=0.2),
        )
        self.beat(
            15,
            FadeIn(ord_label),
            LaggedStart(
                *(
                    TransformFromCopy(source, target)
                    for source, target in zip(characters, numbers)
                ),
                lag_ratio=0.25,
            ),
        )
        self.hold(8)

        self.beat(8, FadeIn(byte))
        self.beat(5, FadeIn(byte_label))

        self.beat(
            10,
            FadeOut(byte),
            FadeOut(byte_label),
            TransformFromCopy(numbers, bytes_row),
        )
        self.beat(6, FadeIn(warning))
        self.hold(8)

        model, _ = make_panel(
            "SMALLEST USEFUL MODEL",
            ["numeric input", "prediction", "measured error", "adjustable parameters"],
            accent=PALETTE["learning"],
            width=7.5,
            height=4.1,
            line_font_size=30,
        )
        model.shift(1.0 * LEFT)
        self.beat(
            8,
            *(FadeOut(mobject) for mobject in tuple(self.mobjects)),
            FadeIn(model),
        )
        prediction = make_card(
            "prediction",
            color=PALETTE["learning"],
            width=2.4,
        ).next_to(model, RIGHT, buff=0.25).shift(0.9 * UP)
        error = make_card(
            "error",
            color=PALETTE["error"],
            width=2.0,
        ).next_to(prediction, DOWN, buff=0.4)
        parameters = make_card(
            "adjustable parameters",
            color=PALETTE["learning"],
            width=3.6,
        ).next_to(model, DOWN, buff=0.25)
        self.beat(6, FadeIn(prediction))
        self.beat(6, FadeIn(error))
        self.beat(6, FadeIn(parameters))
        self.hold(22)

    def show_tiny_example(self) -> None:
        self.clear_stage(2)
        title = self.section_title("A repeatable relationship in examples")
        examples = VGroup(
            *(make_text(line, font_size=42) for line in ["cat sat", "cat ran", "cat slept"])
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.32).shift(2.8 * LEFT)
        self.beat(4, FadeIn(title))
        self.beat(
            12,
            LaggedStart(*(Write(line) for line in examples), lag_ratio=0.3),
        )

        highlights = VGroup(
            *(SurroundingRectangle(line[:3], color=PALETTE["fixed"], buff=0.08) for line in examples)
        )
        self.beat(
            8,
            LaggedStart(*(Create(box) for box in highlights), lag_ratio=0.2),
        )
        self.hold(8)

        hand_check, _ = make_panel(
            "HAND CHECK",
            ["C     a     t", "67    97    116", "length = 3", "sequences can be compared"],
            accent=PALETTE["fixed"],
            width=5.5,
            height=3.9,
            line_font_size=28,
        )
        hand_check.shift(3.1 * RIGHT + 0.4 * DOWN)
        self.beat(10, FadeIn(hand_check, shift=LEFT))
        misconception = make_card(
            "numeric processing ≠ human meaning",
            color=PALETTE["error"],
            width=6.2,
            height=0.9,
            font_size=26,
        ).to_edge(DOWN, buff=0.3)
        self.beat(8, FadeIn(misconception))

        before_cells = VGroup(
            *(
                Square(
                    side_length=0.5,
                    stroke_color=PALETTE["detail"],
                    fill_color=PALETTE["error"] if index < 7 else PALETTE["learning"],
                    fill_opacity=0.85,
                )
                for index in range(10)
            )
        ).arrange(RIGHT, buff=0.1)
        after_cells = VGroup(
            *(
                Square(
                    side_length=0.5,
                    stroke_color=PALETTE["detail"],
                    fill_color=PALETTE["error"] if index < 5 else PALETTE["learning"],
                    fill_opacity=0.85,
                )
                for index in range(10)
            )
        ).arrange(RIGHT, buff=0.1)
        boards = VGroup(
            VGroup(make_text("before: 7/10 errors", font_size=27), before_cells).arrange(DOWN),
            VGroup(make_text("after: 5/10 errors", font_size=27), after_cells).arrange(DOWN),
        ).arrange(DOWN, buff=0.55)
        disclaimer = make_card(
            "Illustration—not observed training output",
            color=PALETTE["error"],
            width=7.2,
            height=0.8,
            font_size=24,
        ).to_edge(DOWN, buff=0.25)
        self.beat(
            10,
            *(FadeOut(mobject) for mobject in tuple(self.mobjects)),
            FadeIn(boards),
            FadeIn(disclaimer),
        )
        self.beat(10, Indicate(after_cells, color=PALETTE["learning"]))

        loop = make_pipeline(
            ["examples", "prediction", "error", "update", "evaluate later"]
        ).shift(1.3 * UP)
        self.beat(12, FadeTransform(boards, loop))
        self.hold(36)


class Video001ComputerLearningFromText(_Video001PartOne):
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

        marker = SurroundingRectangle(
            normalize_lines[0],
            color=PALETTE["context"],
            buff=0.07,
        )
        self.beat(8, Create(marker))
        for line in normalize_lines[1:]:
            target = SurroundingRectangle(
                line,
                color=PALETTE["context"],
                buff=0.07,
            )
            self.beat(10, Transform(marker, target))
            self.hold(3)

        nfkc = VGroup(
            make_card("①", color=PALETTE["context"], width=1.4),
            Arrow(LEFT, RIGHT, color=PALETTE["detail"], buff=0).scale(0.6),
            make_card("1", color=PALETTE["fixed"], width=1.4),
        ).arrange(RIGHT, buff=0.35).shift(0.8 * UP)
        warning = make_card(
            "Policy choice—not lossless cleanup",
            color=PALETTE["error"],
            width=7.2,
            height=0.95,
            font_size=27,
        ).next_to(nfkc, DOWN, buff=0.55)
        self.beat(
            10,
            FadeOut(normalize_panel),
            FadeOut(marker),
            FadeOut(title),
            FadeIn(nfkc),
        )
        self.beat(8, FadeIn(warning))
        self.hold(8)

        prepare_panel, record, separation = make_prepare_repository_layout()
        self.beat(
            10,
            FadeOut(nfkc),
            FadeOut(warning),
            FadeIn(prepare_panel),
        )
        self.beat(12, FadeIn(record, shift=RIGHT))
        self.beat(8, FadeIn(separation))
        self.hold(30)

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
        source_panel, source = make_panel(
            "lab.py",
            source_lines,
            accent=PALETTE["fixed"],
            width=12.5,
            height=5.8,
            line_font_size=21,
        )
        source_panel.shift(0.25 * DOWN)
        self.beat(4, FadeIn(title))
        self.beat(10, FadeIn(source_panel))
        self.beat(8, Indicate(source[0], color=PALETTE["context"]))

        predict = VGroup(
            make_card("Predict first", color=PALETTE["context"], width=3.0),
            make_card("[67, 97, 116]", color=PALETTE["fixed"], width=3.5),
            make_card("[67, 97, 116]", color=PALETTE["fixed"], width=3.5),
        ).arrange(DOWN, buff=0.3)
        self.beat(
            10,
            FadeOut(source_panel),
            FadeOut(title),
            FadeIn(predict),
        )
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
            self.beat(7, make_line_focus(line))
        self.hold(10)

        edit = VGroup(
            make_card('text = "Cat"', color=PALETTE["fixed"], width=3.6),
            Arrow(LEFT, RIGHT, color=PALETTE["detail"], buff=0).scale(0.6),
            make_card('text = "A"', color=PALETTE["context"], width=3.6),
            make_card("[65]", color=PALETTE["fixed"], width=2.0),
        ).arrange(RIGHT, buff=0.35)
        self.beat(12, FadeOut(terminal_panel), FadeIn(edit))
        restore = make_card(
            'restore: text = "Cat"',
            color=PALETTE["learning"],
            width=4.8,
        ).next_to(edit, DOWN, buff=0.7)
        self.beat(8, FadeIn(restore))
        self.hold(45)

    def show_common_mistake(self) -> None:
        self.clear_stage(2)
        fixed = VGroup(
            make_card("A", color=PALETTE["context"], width=1.5),
            make_card("65", color=PALETTE["fixed"], width=1.5),
        ).arrange(RIGHT, buff=0.5).shift(1.5 * UP)
        contexts = VGroup(
            *(
                make_card(
                    label,
                    color=PALETTE["context"],
                    width=2.3,
                    height=0.85,
                    font_size=24,
                )
                for label in ["grade", "note", "blood type", "word"]
            )
        ).arrange(RIGHT, buff=0.25)
        self.beat(6, FadeIn(fixed))
        self.beat(
            8,
            LaggedStart(*(FadeIn(card, shift=UP) for card in contexts), lag_ratio=0.2),
        )
        self.beat(6, Indicate(fixed[1], color=PALETTE["fixed"]))

        false_claim = make_card(
            "65 = meaning of A",
            color=PALETTE["error"],
            width=4.4,
        ).shift(1.6 * DOWN)
        strike = Line(
            false_claim.get_corner(LEFT + DOWN),
            false_claim.get_corner(RIGHT + UP),
            color=PALETTE["error"],
            stroke_width=6,
        )
        self.beat(6, FadeIn(false_claim))
        self.beat(4, Create(strike))

        comparison = VGroup(
            make_card("fixed mapping", color=PALETTE["fixed"], width=3.0),
            make_card("learning update", color=PALETTE["learning"], width=3.0),
        ).arrange(RIGHT, buff=1.1)
        self.beat(
            8,
            *(FadeOut(mobject) for mobject in tuple(self.mobjects)),
            FadeIn(comparison),
        )
        self.hold(20)

    def show_recap_and_exercise(self) -> None:
        self.clear_stage(2)
        pipeline = make_recap_pipeline().shift(1.8 * UP)
        self.beat(
            8,
            LaggedStart(*(FadeIn(part, shift=RIGHT) for part in pipeline), lag_ratio=0.1),
        )

        recap = VGroup(
            make_text("1  Programs receive represented data.", font_size=29),
            make_text("2  Unicode and UTF-8 define numeric representations.", font_size=29),
            make_text("3  Representation is not human meaning or learning.", font_size=29),
            make_text(
                "4  Learning updates parameters to reduce prediction error.",
                font_size=29,
            ),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.24).next_to(pipeline, DOWN, buff=0.65)
        self.beat(
            10,
            LaggedStart(*(FadeIn(line, shift=UP) for line in recap), lag_ratio=0.18),
        )
        self.hold(8)

        exercise = make_card(
            "The number 65 is assigned to ___, but it does not encode ___.",
            color=PALETTE["context"],
            width=11.8,
            height=1.35,
            font_size=31,
        ).shift(0.5 * UP)
        restore = make_card(
            'Return lab.py to text = "Cat"',
            color=PALETTE["learning"],
            width=6.0,
            height=0.9,
            font_size=26,
        ).next_to(exercise, DOWN, buff=0.55)
        next_video = make_text(
            "Next: assigned character numbers in more detail",
            font_size=27,
            color=PALETTE["detail"],
        ).to_edge(DOWN, buff=0.35)
        self.beat(
            8,
            FadeOut(pipeline),
            FadeOut(recap),
            FadeIn(exercise),
        )
        self.beat(6, FadeIn(restore))
        self.beat(4, FadeIn(next_video))
        self.hold(14)
