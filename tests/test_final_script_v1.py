import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "course/templates/video/final_script_v1.md"
CHARACTER_PATH = ROOT / "course/templates/video/character_representation.py"
PREPARATION_PATH = ROOT / "course/templates/video/text_preparation.py"
OLD_LAB_PATH = ROOT / "course/templates/video/final_script_v1_lab.py"
EXPECTED_VIDEO_DURATION_SECONDS = 15 * 60

EXPECTED_CHARACTER_SOURCE = '''text = "Cat"
print("Text:", text)
print("Code-point numbers:", [ord(character) for character in text])
print("UTF-8 byte numbers:", list(text.encode("utf-8")))

print()

text = "🐱"
print("Text:", text)
print("Code-point numbers:", [ord(character) for character in text])
print("UTF-8 byte numbers:", list(text.encode("utf-8")))'''

EXPECTED_CHARACTER_OUTPUT = """Text: Cat
Code-point numbers: [67, 97, 116]
UTF-8 byte numbers: [67, 97, 116]

Text: 🐱
Code-point numbers: [128049]
UTF-8 byte numbers: [240, 159, 144, 177]"""

EXPECTED_PREPARATION_SOURCE = r'''import unicodedata


def prepare_text(text):
    text = unicodedata.normalize("NFKC", text)
    lines = [line.strip() for line in text.splitlines()]
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines)


source = "  ① cat ﬀ  \r\n\r\n  second line  "

print("Source text:", repr(source))
print("Prepared text:", repr(prepare_text(source)))'''

EXPECTED_PREPARATION_OUTPUT = r"""Source text: '  ① cat ﬀ  \r\n\r\n  second line  '
Prepared text: '1 cat ff\nsecond line'"""

EXPECTED_HEADINGS = [
    "## 00:00 The Big Question and Today’s First Step",
    "## 01:20 Three Foundations We Need First",
    "## 02:20 Three Questions About Written Text",
    "## 03:10 How Can Software Identify a Character?",
    "## 04:45 How Can Software Store or Send Text?",
    "## 06:45 How Can We Prepare Text Consistently?",
    "## 08:50 Build a Complete Text-Preparation Example",
    "## 10:50 Predict, Run, and Explain",
    "## 13:30 What These Foundations Let Us Explain",
]

# Intentionally scan the complete learner artifact, including metadata and
# code fences, so prohibited prerequisite language cannot leak on screen.
PROHIBITED_SCRIPT_CONTENT = re.compile(
    r"\b(repository|project|tokenization|tokenizer|signposts?|unsigned|"
    r"integers?|polic(?:y|ies)|ASCII|models?|parameters?|divide|divided|"
    r"dividing|jobs?|tokens?|embeddings?)\b|"
    r"(?:longer|whole) (?:path|route)|part of (?:that|the) (?:path|route)|"
    r"compress the (?:path|route)|"
    r"shared system|preparation policy|normalize_text|"
    r"_CONTROL_RE|_BLANK_LINES_RE",
    re.IGNORECASE,
)


def run_example(path: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=path.parent,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stderr == ""
    return result.stdout


def spoken_sentences(script: str) -> list[str]:
    blocks = []
    paragraph = []
    in_fence = False

    def flush_paragraph():
        if paragraph:
            blocks.append(" ".join(paragraph))
            paragraph.clear()

    for raw_line in script.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            flush_paragraph()
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not line:
            flush_paragraph()
            continue
        if (
            line.startswith(("#", "[", "---"))
            or line == "*Script 4*"
            or line.startswith("**Subtitle:**")
        ):
            flush_paragraph()
            continue

        item = re.match(r"^(?:>\s*|[-+*]\s+|\d+[.)]\s+)(.*)$", line)
        if item:
            flush_paragraph()
            blocks.append(item.group(1))
        else:
            paragraph.append(line)

    flush_paragraph()
    return [
        part.strip()
        for block in blocks
        for part in re.split(
            r"(?<=[.!?])\s+",
            re.sub(r"[*_`]", "", block),
        )
        if part.strip()
    ]


def spoken_text(script: str) -> str:
    return "\n".join(spoken_sentences(script))


def assert_in_order(text: str, *parts: str):
    position = -1
    for part in parts:
        next_position = text.find(part, position + 1)
        assert next_position != -1, f"missing or out of order: {part!r}"
        position = next_position


def test_character_example_is_exact_and_runnable():
    assert (
        CHARACTER_PATH.read_text(encoding="utf-8")
        == EXPECTED_CHARACTER_SOURCE + "\n"
    )
    assert run_example(CHARACTER_PATH) == EXPECTED_CHARACTER_OUTPUT + "\n"


def test_character_example_is_embedded_with_local_command_and_output():
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    assert f"```python\n{EXPECTED_CHARACTER_SOURCE}\n```" in script
    assert f"```text\n{EXPECTED_CHARACTER_OUTPUT}\n```" in script
    assert (
        script.count("```bash\npython character_representation.py\n```")
        == 1
    )
    assert "python course/" not in script


def test_preparation_example_is_exact_and_runnable():
    assert (
        PREPARATION_PATH.read_text(encoding="utf-8")
        == EXPECTED_PREPARATION_SOURCE + "\n"
    )
    assert run_example(PREPARATION_PATH) == EXPECTED_PREPARATION_OUTPUT + "\n"

    namespace = {}
    source = PREPARATION_PATH.read_text(encoding="utf-8")
    exec(compile(source, str(PREPARATION_PATH), "exec"), namespace)
    prepare_text = namespace["prepare_text"]
    assert prepare_text("①") == "1"
    assert prepare_text("ﬀ") == "ff"
    assert prepare_text("Cat") == "Cat"
    assert (
        prepare_text("  Cat cat ﬀ  \r\n\r\n  second line  ")
        == "Cat cat ff\nsecond line"
    )


def test_preparation_example_is_embedded_and_old_lab_is_removed():
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    assert f"```python\n{EXPECTED_PREPARATION_SOURCE}\n```" in script
    assert f"```text\n{EXPECTED_PREPARATION_OUTPUT}\n```" in script
    assert script.count("```bash\npython text_preparation.py\n```") == 1
    assert not OLD_LAB_PATH.exists()


def test_script_structure_vocabulary_and_voice():
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    headings = [
        line for line in script.splitlines() if line.startswith("## ")
    ]
    assert headings == EXPECTED_HEADINGS
    assert 1650 <= len(spoken_text(script).split()) <= 1850
    assert not PROHIBITED_SCRIPT_CONTENT.search(script)
    assert "python course/" not in script
    assert all(line == line.rstrip() for line in script.splitlines())

    long_sentences = [
        sentence
        for sentence in spoken_sentences(script)
        if len(sentence.split()) > 40
    ]
    assert not long_sentences


def test_script_timing_allows_conversational_delivery():
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    matches = list(
        re.finditer(
            r"^## (?P<minutes>\d{2}):(?P<seconds>\d{2}) .+$",
            script,
            re.MULTILINE,
        )
    )
    starts = [
        int(match.group("minutes")) * 60 + int(match.group("seconds"))
        for match in matches
    ]
    assert starts == sorted(starts)

    boundaries = starts[1:] + [EXPECTED_VIDEO_DURATION_SECONDS]
    for index, (match, start, end) in enumerate(
        zip(matches, starts, boundaries, strict=True)
    ):
        body_start = match.end()
        body_end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(script)
        )
        words = len(spoken_text(script[body_start:body_end]).split())
        words_per_minute = words * 60 / (end - start)
        assert 85 <= words_per_minute <= 145


def test_script_builds_foundations_from_questions_before_terms():
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    required = [
        "Before we study how AI learns from written text, we need three foundations.",
        "Each foundation answers a different question about the same text.",
        "They are related, but they do not form one fixed sequence.",
        "Different programs use them in different ways.",
        "For today, keep these three questions in view:",
        "Which characters are present?",
        "How can the text be stored or sent?",
        "Which source differences should we preserve or change?",
        "Before we name the rule, make a prediction: does Python invent a new number for `A`, or follow a number fixed by an agreed standard?",
        "Unicode is a character-numbering standard. In our examples, each character has a fixed number called a **code point**.",
        "Python already has a function that reports the code point for a one-character string. It is named `ord`.",
        "Before we name the storage method, predict: will every character in our examples fit into exactly one small storage unit?",
        "Software stores data in small units called **bytes**.",
        "To turn text into an ordered byte sequence, we will use a standard called **UTF-8**.",
        "Suppose we want two non-empty lines, with surrounding whitespace removed from each line.",
        "When several chosen cleanup steps are applied together, we call the whole process **text preparation**.",
        "First, look only at this change: `①` becomes `1`.",
        "When a rule maps selected alternate character forms to a consistent Unicode representation, that step is called **normalization**.",
        "**NFKC** is the name of one Unicode normalization form.",
        "Python can make hidden marks such as `\\r\\n` and surrounding spaces visible in the terminal. The function that gives us this view is `repr`.",
        "Open a terminal in the folder containing the two files.",
    ]
    for sentence in required:
        assert sentence in script

    spoken = spoken_text(script)
    assert_in_order(
        spoken,
        "Before we name the rule, make a prediction",
        "Unicode is a character-numbering standard.",
        "called a code point",
        "It is named ord.",
    )
    assert_in_order(
        spoken,
        "Before we name the storage method, predict",
        "Software stores data in small units",
        "called bytes.",
        "a standard called UTF-8.",
    )
    assert_in_order(
        spoken,
        "with surrounding whitespace removed from each line.",
        "call the whole process text preparation.",
    )
    assert_in_order(
        spoken,
        "First, look only at this change: ① becomes 1.",
        "that step is called normalization.",
        "NFKC is the name of one Unicode normalization form.",
    )
    assert_in_order(
        script,
        "**NFKC** is the name of one Unicode normalization form.",
        EXPECTED_PREPARATION_SOURCE,
        EXPECTED_PREPARATION_OUTPUT,
    )
    assert_in_order(
        script,
        "The function that gives us this view is `repr`.",
        EXPECTED_PREPARATION_SOURCE,
        EXPECTED_PREPARATION_OUTPUT,
    )


def test_script_contains_transfer_cases_and_no_context_dependent_command():
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    for exact in [
        "Code-point numbers: [65]",
        "UTF-8 byte numbers: [65]",
        "replace `①` with `Cat`",
        "restore `Cat`",
        "restore `①`",
        "https://www.python.org/downloads/",
        "[On screen: a short text sample with extra spaces, two consecutive line endings, `①`, and `ﬀ`]",
        "Python already has a function that reports the code point for a one-character string. It is named `ord`.",
        "① -> 1",
        "length 1 -> 1",
        "ﬀ -> ff",
        "length 1 -> 2",
    ]:
        assert exact in script

    assert_in_order(
        script,
        EXPECTED_CHARACTER_SOURCE,
        "Before we run the file, predict both lists for `Cat`.",
        "```bash\npython character_representation.py\n```",
        f"```text\n{EXPECTED_CHARACTER_OUTPUT}\n```",
    )
    assert_in_order(
        script,
        'Now change the first assignment, `text = "Cat"`, to `text = "A"`.',
        "Code-point numbers: [65]",
        "UTF-8 byte numbers: [65]",
        "restore `Cat`",
    )
    assert_in_order(
        script,
        EXPECTED_PREPARATION_SOURCE,
        "Before we run the second file, write the exact prepared string you expect.",
        "```bash\npython text_preparation.py\n```",
        f"```text\n{EXPECTED_PREPARATION_OUTPUT}\n```",
        "replace `①` with `Cat`",
        "restore `①`",
    )
    assert "course/templates/video" not in script
