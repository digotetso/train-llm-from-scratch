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
