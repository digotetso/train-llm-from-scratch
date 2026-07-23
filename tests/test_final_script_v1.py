import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "course/templates/video/final_script_v1.md"
CHARACTER_PATH = ROOT / "course/templates/video/character_representation.py"
PREPARATION_PATH = ROOT / "course/templates/video/text_preparation.py"
OLD_LAB_PATH = ROOT / "course/templates/video/final_script_v1_lab.py"

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
    "## 01:00 Where This Video Fits",
    "## 03:00 Three Jobs Before Text Can Be Split into Pieces",
    "## 04:20 Identifying Characters with Code-Point Numbers",
    "## 05:50 Representing Text with UTF-8 Bytes",
    "## 07:00 Preparing Text with Explicit Cleanup Steps",
    "## 08:15 Build a Self-Contained Text-Preparation Example",
    "## 10:45 Predict, Run, and Explain",
    "## 13:20 Return to the Whole Route",
]

# Intentionally scan the complete learner artifact, including metadata and
# code fences, so prohibited prerequisite language cannot leak on screen.
PROHIBITED_SCRIPT_CONTENT = re.compile(
    r"\b(repository|project|tokenization|tokenizer|signposts?|unsigned|"
    r"integers?|polic(?:y|ies)|ASCII|models?|parameters?|divide|divided|"
    r"dividing)\b|shared system|preparation policy|normalize_text|"
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
    assert 2000 <= len(script.split()) <= 2250
    assert not PROHIBITED_SCRIPT_CONTENT.search(script)
    assert "python course/" not in script

    long_sentences = [
        sentence
        for sentence in spoken_sentences(script)
        if len(sentence.split()) > 40
    ]
    assert not long_sentences


def test_script_introduces_jobs_before_later_labels():
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    required = [
        "Before we name the rule, make a prediction: does Python invent a new number for `A`, or follow a fixed number?",
        "Unicode is a character-numbering standard. For each single character in today’s examples, it assigns a code-point number.",
        "Before we name the storage method, predict: will every single character always need exactly one small storage unit?",
        "A byte is a small unit of storage. Python displays each byte as a non-negative number from `0` through `255`.",
        "UTF-8 turns text into an ordered sequence of bytes that software can store or send.",
        "We can choose one fixed cleanup step, such as removing the extra spaces around a line.",
        "Each cleanup step follows a fixed choice. The complete sequence of steps is called **text preparation**.",
        "First, look only at this change: `①` becomes `1`.",
        "Text is split into reusable pieces. Each piece is called a **token**.",
        "Each token receives a number. That number is called a **token ID**.",
        "That token ID is linked to an **embedding**—a learned list of numbers used to represent useful features of the token during later processing.",
        "An embedding is not a dictionary definition of the token.",
        "These are names for later steps. We have not explained how they work yet, so we will leave them for later and focus on the three jobs in front of us.",
        "Changing text into a chosen standard form is called **normalization**.",
        "**NFKC** is the name of one Unicode normalization rule.",
        "`repr` makes hidden marks such as `\\r\\n` and surrounding spaces visible in the terminal.",
        "Open a terminal in the folder containing the two files.",
    ]
    for sentence in required:
        assert sentence in script

    spoken = spoken_text(script)
    assert_in_order(
        spoken,
        "Before we name the rule, make a prediction",
        "Unicode is a character-numbering standard.",
        "code-point number.",
    )
    assert_in_order(
        spoken,
        "Before we name the storage method, predict",
        "A byte is a small unit of storage.",
        "UTF-8 turns text into an ordered sequence of bytes",
    )
    assert_in_order(
        spoken,
        "We can choose one fixed cleanup step",
        "called text preparation.",
    )
    assert_in_order(
        spoken,
        "First, look only at this change: ① becomes 1.",
        "Changing text into a chosen standard form is called normalization.",
        "NFKC is the name of one Unicode normalization rule.",
    )
    assert_in_order(
        spoken,
        "Text is split into reusable pieces.",
        "Each piece is called a token.",
        "Each token receives a number.",
        "That number is called a token ID.",
        "That token ID is linked to an embedding",
    )
    assert_in_order(
        script,
        "**NFKC** is the name of one Unicode normalization rule.",
        EXPECTED_PREPARATION_SOURCE,
        EXPECTED_PREPARATION_OUTPUT,
    )
    assert_in_order(
        script,
        "`repr` makes hidden marks such as `\\r\\n`",
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
        "[On screen: a short text sample with extra spaces, mixed line endings, `①`, and `ﬀ`]",
        "Python already includes a function named `ord`. It reports the code-point number for one character.",
        "① -> 1",
        "length 1 -> 1",
        "ﬀ -> ff",
        "length 1 -> 2",
    ]:
        assert exact in script

    assert_in_order(
        script,
        "Before we run the file, predict both lists for `Cat`.",
        f"```text\n{EXPECTED_CHARACTER_OUTPUT}\n```",
    )
    assert_in_order(
        script,
        "Now replace the first `Cat` with `A`.",
        "Code-point numbers: [65]",
        "UTF-8 byte numbers: [65]",
        "restore `Cat`",
    )
    assert_in_order(
        script,
        "Before we run the second file, predict which parts of the source text will change.",
        f"```text\n{EXPECTED_PREPARATION_OUTPUT}\n```",
        "replace `①` with `Cat`",
        "restore `①`",
    )
    assert "course/templates/video" not in script
