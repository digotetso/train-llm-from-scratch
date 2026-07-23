# Final Video 1 Standalone Examples Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace repository-dependent Video 1 explanations with two exact standalone Python examples and revise the narration so every term follows a concrete, beginner-understandable job.

**Architecture:** Work in an isolated branch because the primary checkout contains protected user edits, including the approved source draft. Reproduce that dirty draft exactly in the worktree, add a focused test contract incrementally, then revise the lesson in three reviewed content batches. Finish with a complete read-aloud, full repository tests, protected-file audit, and recoverable local merge.

**Tech Stack:** Markdown, Python 3 standard library, pytest, Git worktrees, existing course templates.

## Global Constraints

- Treat `docs/superpowers/specs/2026-07-23-final-script-v1-standalone-examples-design.md` as the approved source of truth.
- At execution time, invoke `superpowers:using-git-worktrees`.
- Use branch `codex/final-script-v1-standalone-examples`.
- Use worktree `.worktrees/final-script-v1-standalone-examples`.
- The approved primary source is `course/templates/video/final_script_v1.md` with SHA-256 `4031ae35da3123c0022a0613b4ba55cf93716502173041f16d4bf50c4dc601be`.
- Preserve the user’s `split` change, messy-text stage direction, Python-download stage direction, and conversational Python-file setup in polished form.
- Modify only the final script, its two standalone examples, the superseded generic lab, and the new focused test.
- Do not modify established Video 1 artifacts, repository source, existing tests, `.playwright-mcp/`, drafts, or media/production files.
- Use `split`, `number`, `character-numbering standard`, `non-negative number`, `fixed cleanup steps`, and `ordered UTF-8 byte sequence`.
- Learner-facing narration must not contain case-insensitive standalone `repository`, `project`, `tokenization`, `tokenizer`, `signpost`, `unsigned`, `integer`, `policy`, `ASCII`, `model`, `parameter`, `divide`, `divided`, or `dividing`.
- Learner-facing narration must not contain `shared system`, `preparation policy`, `normalize_text`, `_CONTROL_RE`, or `_BLANK_LINES_RE`.
- In spoken narration, explain a job before naming Unicode, code point, UTF-8, byte, text preparation, normalization, NFKC, token, token ID, or embedding. The approved subtitle and section headings are navigation metadata and are the only exception.
- Use `🐱` to prove that code-point numbers and UTF-8 byte numbers do not generally match.
- Explain that an embedding represents useful learned features for later processing and is not a dictionary definition.
- Preserve exactly nine timestamped sections.
- Keep the complete Markdown file between 2,000 and 2,250 whitespace-delimited words.
- Keep every spoken sentence at forty words or fewer.
- Embed both standalone source files and both freshly observed outputs exactly.
- Use only folder-local learner commands: `python character_representation.py` and `python text_preparation.py`.
- Use `apply_patch` for all repository content changes.
- Stage explicit paths only and inspect the staged path list before every commit.
- Do not create, modify, stage, or commit media, video, audio, animation, image, render, font, After Effects, Premiere, browser-capture, or production-project files.

---

## File Map

- `course/templates/video/final_script_v1.md`: learner-facing narration and exact embedded examples.
- `course/templates/video/character_representation.py`: compares code-point and UTF-8 byte numbers for `Cat` and `🐱`.
- `course/templates/video/text_preparation.py`: demonstrates NFKC, line splitting, whitespace cleanup, empty-line removal, and joining.
- `course/templates/video/final_script_v1_lab.py`: superseded generic companion to remove.
- `tests/test_final_script_v1.py`: exact artifact, output, wording, dependency-order, structure, and voice contract.
- `docs/superpowers/specs/2026-07-23-final-script-v1-standalone-examples-design.md`: approved design.

---

### Task 1: Preserve The User Draft And Add Character Representation Evidence

**Files:**

- Modify: `course/templates/video/final_script_v1.md`
- Create: `course/templates/video/character_representation.py`
- Create: `tests/test_final_script_v1.py`
- Read: `/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/templates/video/final_script_v1.md`

**Interfaces:**

- Consumes: the approved dirty narration snapshot at SHA-256 `4031ae35...`.
- Produces: an exact runnable character example, embedded source/output, and a focused green contract for `Cat` versus `🐱`.

- [ ] **Step 1: Create and verify the isolated workspace**

After invoking `superpowers:using-git-worktrees`, run from the new worktree:

```bash
pwd -P
git branch --show-current
git status --short
test ! -e course/templates/video/character_representation.py
test ! -e course/templates/video/text_preparation.py
test ! -e tests/test_final_script_v1.py
```

Expected branch:

```text
codex/final-script-v1-standalone-examples
```

Expected worktree status: clean.

Verify the primary source and protected baselines:

```bash
shasum -a 256 \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/templates/video/final_script_v1.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/templates/video/final_script_v1_lab.py \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/script.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_script_4.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_improved_script.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/script_video1_draft.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/tests/test_course_structure.py
```

Expected hashes in command order:

```text
4031ae35da3123c0022a0613b4ba55cf93716502173041f16d4bf50c4dc601be
3a2b1a613c2e1c7734e61027588d6faff8bc7bfc9b351d34726c1da95fff9b9f
33bd5437b98f329b4755591b091b8b5be890be45dd8855d16e74c48426e446fe
6e837a036829b548c1c5ee55f78e40855b8f017d4328e604df708d536f343414
2d367e1885b8f097466e24dbe115c075aad581580975bb58a91a7320c21f0de0
732560ab1c9fbaa9ad98a508bf0148d72682b85bdc04ad4eb49cdaa57725a10f
47b2c77b915b329e570c90846eca354495c2b1cdb73e410701cb19c8cef38b12
```

If any primary hash differs, stop and preserve the newer user state rather
than reverting it.

- [ ] **Step 2: Run the clean baseline suite**

Run:

```bash
uv run pytest -v
```

Expected: all collected tests pass before the new focused contract exists.

- [ ] **Step 3: Reproduce the approved dirty script snapshot**

The isolated worktree starts from `HEAD`, so apply the user’s current draft
changes before rewriting. Use `apply_patch` with these exact changes. In the
displayed patch, `␠` marks the single trailing ASCII space that exists in the
approved snapshot; replace the marker with that literal space when applying:

```diff
-Later stages can divide the prepared text into reusable pieces
+Later stages can split the prepared text into reusable pieces

-1. how Unicode gives characters stable numerical identifiers;
+1. how Unicode gives characters  numerical identifiers;

-Treat this as a dependency map, not a complete explanation.
+Treat this as a dependency map, not a complete explanation. We will details of each stage as the course progresses.

 ### Job 3: Prepare the text
+
+[show messy text example]

 ## 04:20 Representing Characters with Unicode
-Consider the character `A`. Before checking, predict what Python will do with:
+Consider the character `A`.␠
+Im going create a python file to check this character's code point .  We can use the following python function for the task.
+
+Before checking, predict what Python will do with:
+
+[put download python from `https://www.python.org/` on screen text]
```

Verify:

```bash
shasum -a 256 course/templates/video/final_script_v1.md
```

Expected:

```text
4031ae35da3123c0022a0613b4ba55cf93716502173041f16d4bf50c4dc601be  course/templates/video/final_script_v1.md
```

This deliberately reproduces the draft before polishing its grammar.

- [ ] **Step 4: Add the failing character-example contract**

Use `apply_patch` to create `tests/test_final_script_v1.py` with:

```python
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "course/templates/video/final_script_v1.md"
CHARACTER_PATH = ROOT / "course/templates/video/character_representation.py"

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
    assert script.count(
        "```bash\npython character_representation.py\n```"
    ) == 1
    assert "python course/" not in script
```

- [ ] **Step 5: Run the character contract and verify RED**

Run:

```bash
uv run pytest tests/test_final_script_v1.py -v
```

Expected: both tests fail because `character_representation.py` is absent and
the script does not yet embed its exact source/output.

- [ ] **Step 6: Create the exact character example**

Use `apply_patch` to add:

```python
text = "Cat"
print("Text:", text)
print("Code-point numbers:", [ord(character) for character in text])
print("UTF-8 byte numbers:", list(text.encode("utf-8")))

print()

text = "🐱"
print("Text:", text)
print("Code-point numbers:", [ord(character) for character in text])
print("UTF-8 byte numbers:", list(text.encode("utf-8")))
```

- [ ] **Step 7: Revise the character and byte teaching sections**

Use `apply_patch` to replace the `04:20` and `05:50` sections and the
character half of `10:45`. Preserve this exact dependency order:

```text
need a stable number for an example character
-> ask whether Python invents a number or follows a fixed assignment
-> introduce Unicode as a character-numbering standard
-> name the assigned number a code point
-> predict Cat
-> show Cat code-point numbers
-> ask how those characters become bytes
-> predict whether every character always needs one small storage unit
-> define a byte as a small storage unit shown as a non-negative number
-> explain UTF-8 as an ordered byte sequence used to store or send text
-> predict Cat byte numbers
-> reveal the matching Cat lists
-> predict one code point or several for 🐱
-> reveal [128049]
-> predict one byte or several
-> reveal [240, 159, 144, 177]
-> state that matching values for Cat are not a general rule
```

Use this prediction before the first accepted technical label:

```markdown
Before we name the rule, make a prediction: does Python invent a new number for `A`, or follow a fixed number?
```

Use these exact learner-facing sentences:

```markdown
Unicode is a character-numbering standard. For each single character in today’s examples, it assigns a code-point number.

Some visible symbols are built from several code points. We will leave that case for a later lesson.

Before we name the storage method, predict: will every single character always need exactly one small storage unit?

A byte is a small unit of storage. Python displays each byte as a non-negative number from `0` through `255`.

UTF-8 turns text into an ordered sequence of bytes that software can store or send.

For `Cat`, the code-point numbers happen to match the UTF-8 byte numbers. The cat emoji proves that this match is not a rule.

The four byte numbers work together, in order, to store or send `🐱`.
```

Preserve the user’s Python setup intent as this non-spoken direction:

```markdown
[On screen: If Python is not installed, visit https://www.python.org/downloads/]
```

Introduce `ord` in plain language:

```markdown
Python already includes a function named `ord`. It reports the code-point number for one character.
```

Before the character output, use:

```markdown
Before we run the file, predict both lists for `Cat`. Then predict whether `🐱` will have one code-point number and whether it will use one byte or several.
```

Embed the complete `character_representation.py` source, its exact observed
output, and:

```bash
python character_representation.py
```

Ask for predictions before both outputs. In the changed case, use:

```markdown
Now replace the first `Cat` with `A`. Before you run it, predict the two lines:
```

Then show the prediction:

```text
Code-point numbers: [65]
UTF-8 byte numbers: [65]
```

Then tell them to restore `Cat`.

- [ ] **Step 8: Run the character contract and focused course tests**

Run:

```bash
uv run pytest tests/test_final_script_v1.py -v
uv run pytest tests/test_course_structure.py -v
```

Expected: both commands exit `0`.

- [ ] **Step 9: Commit the character evidence**

Run:

```bash
git add \
  course/templates/video/final_script_v1.md \
  course/templates/video/character_representation.py \
  tests/test_final_script_v1.py
git diff --cached --name-status
git diff --cached --check
git commit -m "docs: add standalone character representation example"
```

Expected staged paths:

```text
A  course/templates/video/character_representation.py
M  course/templates/video/final_script_v1.md
A  tests/test_final_script_v1.py
```

---

### Task 2: Add Self-Contained Text Preparation Evidence

**Files:**

- Modify: `course/templates/video/final_script_v1.md`
- Create: `course/templates/video/text_preparation.py`
- Delete: `course/templates/video/final_script_v1_lab.py`
- Modify: `tests/test_final_script_v1.py`

**Interfaces:**

- Consumes: the exact character example and `run_example` helper from Task 1.
- Produces: a complete runnable `prepare_text(text)` example, exact output, and no remaining generic lab.

- [ ] **Step 1: Extend the contract with preparation tests**

Use `apply_patch` to add these constants after the Task 1 path constants:

```python
PREPARATION_PATH = ROOT / "course/templates/video/text_preparation.py"
OLD_LAB_PATH = ROOT / "course/templates/video/final_script_v1_lab.py"

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
```

Add:

```python
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
    assert script.count(
        "```bash\npython text_preparation.py\n```"
    ) == 1
    assert not OLD_LAB_PATH.exists()
```

- [ ] **Step 2: Run the preparation tests and verify RED**

Run:

```bash
uv run pytest tests/test_final_script_v1.py -v
```

Expected: the two new preparation tests fail because the new file is absent,
its source/output are not embedded, and the old generic lab still exists.

- [ ] **Step 3: Create `text_preparation.py` exactly**

Use `apply_patch` to add:

```python
import unicodedata


def prepare_text(text):
    text = unicodedata.normalize("NFKC", text)
    lines = [line.strip() for line in text.splitlines()]
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines)


source = "  ① cat ﬀ  \r\n\r\n  second line  "

print("Source text:", repr(source))
print("Prepared text:", repr(prepare_text(source)))
```

- [ ] **Step 4: Remove the superseded generic lab**

Use `apply_patch` with:

```text
*** Delete File: course/templates/video/final_script_v1_lab.py
```

- [ ] **Step 5: Rewrite the preparation sections behavior-first**

Use `apply_patch` to replace `07:00` and `08:15`, then add the preparation
loop to `10:45`.

Preserve this exact teaching sequence:

```text
show messy text
-> ask which visible or hidden differences should change
-> explain one fixed cleanup change
-> name the full sequence text preparation
-> show ① becoming 1 before naming normalization
-> define normalization
-> name NFKC
-> trace ① and ﬀ with correct lengths
-> state normalization is one preparation step
-> explain repr before it appears in the source
-> show complete prepare_text source
-> predict
-> run
-> trace each operation
-> change one input
-> predict and compare
```

Use this non-spoken direction:

```markdown
[On screen: a short text sample with extra spaces, mixed line endings, `①`, and `ﬀ`]
```

Use these exact learner-facing explanations:

```markdown
We can choose one fixed cleanup step, such as removing the extra spaces around a line.

Each cleanup step follows a fixed choice. The complete sequence of steps is called **text preparation**.

First, look only at this change: `①` becomes `1`.

One possible cleanup step replaces certain special-looking characters with simpler equivalents. Changing text into a chosen standard form is called **normalization**.

**NFKC** is the name of one Unicode normalization rule. In these examples, it changes `①` to `1` and `ﬀ` to `ff`.

Normalization is one preparation step. It is not the whole preparation job.

These cleanup steps may change or remove details from the original text.

`repr` makes hidden marks such as `\r\n` and surrounding spaces visible in the terminal.

These are the cleanup choices in this example. Code, poetry, or other text may need different choices.
```

Before the preparation output, use:

```markdown
Before we run the second file, predict which parts of the source text will change.
```

Show:

```text
① -> 1
length 1 -> 1

ﬀ -> ff
length 1 -> 2
```

Embed the exact file, observed output, and folder-local command:

```bash
python text_preparation.py
```

Trace:

```text
source string
-> NFKC normalization
-> split into lines using common line-ending marks
-> remove surrounding whitespace from each line
-> remove empty lines
-> join the remaining lines with \n
-> prepared string
```

For transfer, ask the learner to replace `①` with `Cat`, predict which output
parts change, run again, compare, and restore `①`.

- [ ] **Step 6: Run the complete example contract**

Run:

```bash
uv run pytest tests/test_final_script_v1.py -v
python course/templates/video/character_representation.py
python course/templates/video/text_preparation.py
```

Expected: four focused tests pass and both command outputs exactly match the
constants in `tests/test_final_script_v1.py`.

- [ ] **Step 7: Commit the text-preparation evidence**

Run:

```bash
git add \
  course/templates/video/final_script_v1.md \
  course/templates/video/final_script_v1_lab.py \
  course/templates/video/text_preparation.py \
  tests/test_final_script_v1.py
git diff --cached --name-status
git diff --cached --check
git commit -m "docs: add standalone text preparation example"
```

Expected staged paths:

```text
M  course/templates/video/final_script_v1.md
D  course/templates/video/final_script_v1_lab.py
A  course/templates/video/text_preparation.py
M  tests/test_final_script_v1.py
```

---

### Task 3: Complete The Whole-Script Dependency And Language Audit

**Files:**

- Modify: `course/templates/video/final_script_v1.md`
- Modify: `tests/test_final_script_v1.py`

**Interfaces:**

- Consumes: both exact standalone examples and their green tests.
- Produces: a repository-free, job-before-label, nine-section narration with enforceable structure and voice constraints.

- [ ] **Step 1: Add the whole-script contract**

Add `import re` to the test imports.

Add:

```python
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
```

Add this helper:

```python
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
```

Add:

```python
def test_script_structure_vocabulary_and_voice():
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    headings = [line for line in script.splitlines() if line.startswith("## ")]
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
```

- [ ] **Step 2: Run the whole-script contract and verify RED**

Run:

```bash
uv run pytest tests/test_final_script_v1.py -v
```

Expected: the new tests fail on old headings, repository/context vocabulary,
future jargon, and missing required job-before-label sentences.

- [ ] **Step 3: Rewrite the opening and course route**

Use this exact subtitle:

```markdown
**Subtitle:** How character numbers, UTF-8 bytes, and simple cleanup prepare written text for later AI work
```

In `00:00`, preserve the familiar AI-output hook and central question. Use
these learner outcomes:

```markdown
By the end, you will be able to explain:

1. how a fixed number can identify each example character;
2. how the same text becomes a sequence of small storage numbers;
3. how a short function applies fixed cleanup steps to an example string; and
4. why character numbers, storage numbers, and prepared text have different jobs.
```

In `01:00`, introduce the later preview in this exact spoken order:

```markdown
Text is split into reusable pieces. Each piece is called a **token**.

Each token receives a number. That number is called a **token ID**.

That token ID is linked to an **embedding**—a learned list of numbers used to represent useful features of the token during later processing.

An embedding is not a dictionary definition of the token.

These are names for later steps. We have not explained how they work yet, so we will leave them for later and focus on the three jobs in front of us.
```

After that one future-vocabulary preview, use this ordinary-language
dependency map as a compact recap. Do not repeat token, token ID, embedding,
code point, UTF-8, or text preparation in the map:

```text
Written text
-> identify each example character with a number
-> represent the text as an ordered sequence of small storage units
-> apply fixed cleanup steps
-> prepared text
-> later text and AI-learning steps [closed]
```

- [ ] **Step 4: Rewrite the three-job section**

Use the exact heading:

```markdown
## 03:00 Three Jobs Before Text Can Be Split into Pieces
```

Open only these three current jobs:

```text
identify a character
turn text into small storage units
apply explicit cleanup steps
```

Use:

```markdown
These numbers are not interchangeable.
```

Do not repeat token, token ID, or embedding in this section. Preserve the
polished messy-text stage direction from Task 2.

- [ ] **Step 5: Rewrite the final recap and transfer**

In `10:45`, place this sentence before the first command and use it exactly
once:

```markdown
Open a terminal in the folder containing the two files.
```

Use:

```text
code-point number -> identifies an example character
UTF-8 byte sequence -> stores or sends the text
fixed cleanup step -> changes one chosen text feature
text preparation -> applies the chosen cleanup steps in order
```

The transfer exercise must ask the learner to classify or predict:

```text
Cat code-point numbers
Cat UTF-8 bytes
🐱 code-point number
🐱 UTF-8 bytes
① under NFKC
ﬀ under NFKC
surrounding spaces under prepare_text
mixed line endings under prepare_text
```

End with:

```markdown
Stable character numbers let software decide which characters belong in a collection. Video 2 asks how to build that collection dependably.
```

Do not mention a tokenizer, measured error, adjustable numbers, models, or
parameters.

- [ ] **Step 6: Run the complete focused contract**

Run:

```bash
uv run pytest tests/test_final_script_v1.py -v
```

Expected: all seven tests pass.

- [ ] **Step 7: Commit the complete narration audit**

Run:

```bash
git add \
  course/templates/video/final_script_v1.md \
  tests/test_final_script_v1.py
git diff --cached --name-status
git diff --cached --check
git commit -m "docs: make final video one fully self-contained"
```

Expected staged paths:

```text
M  course/templates/video/final_script_v1.md
M  tests/test_final_script_v1.py
```

---

### Task 4: Perform Read-Aloud, Verification, Review, And Preservation Audits

**Files:**

- Modify if required by review: `course/templates/video/final_script_v1.md`
- Verify: `course/templates/video/character_representation.py`
- Verify: `course/templates/video/text_preparation.py`
- Verify: `tests/test_final_script_v1.py`

**Interfaces:**

- Consumes: the complete self-contained lesson and its focused contract.
- Produces: a reviewed branch ready for recoverable local integration.

- [ ] **Step 1: Conduct the deliberate teaching review**

Read every spoken paragraph aloud. Use `apply_patch` only when one of these
specific findings occurs:

```text
- a sentence needs more than one breath;
- several short statements sound like a list rather than reasoning;
- a term appears before its observable job;
- a displayed answer appears before a prediction;
- Cat does not create the question answered by 🐱;
- code-point identity does not create the byte-storage question;
- the messy text does not create the cleanup question;
- normalization is described as all of text preparation;
- an example claims more than its output proves;
- a section transition announces rather than builds;
- the recap repeats labels without enabling transfer;
- source, command, output, or numerical values diverge.
```

Preserve exact file source, output, commands, headings, and required boundary
sentences while polishing.

- [ ] **Step 2: Run focused and full verification**

Run:

```bash
uv run pytest tests/test_final_script_v1.py -v
uv run pytest tests/test_course_structure.py -v
uv run pytest -v
python course/templates/video/character_representation.py
python course/templates/video/text_preparation.py
git diff --check
```

Expected:

```text
7 focused final-script tests pass
10 existing course-structure tests pass
239 collected repository tests pass with zero failures
both standalone outputs match the script exactly
no feature-branch whitespace errors
```

The verified baseline contains 232 tests. The seven new focused tests bring
the expected collection to 239.

- [ ] **Step 3: Commit final polish only if narration changed**

If Step 1 changed narration, run:

```bash
git add course/templates/video/final_script_v1.md
git diff --cached --name-status
git diff --cached --check
git commit -m "docs: polish standalone video one narration"
```

Expected staged path:

```text
M  course/templates/video/final_script_v1.md
```

If no narration changed, do not create an empty commit.

- [ ] **Step 4: Verify protected files and branch scope**

Run from the isolated worktree:

```bash
shasum -a 256 \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/script.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_script_4.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_improved_script.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/script_video1_draft.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/tests/test_course_structure.py
git status --short
git diff --check
git diff --name-status main...HEAD
```

Expected protected hashes:

```text
33bd5437b98f329b4755591b091b8b5be890be45dd8855d16e74c48426e446fe
6e837a036829b548c1c5ee55f78e40855b8f017d4328e604df708d536f343414
2d367e1885b8f097466e24dbe115c075aad581580975bb58a91a7320c21f0de0
732560ab1c9fbaa9ad98a508bf0148d72682b85bdc04ad4eb49cdaa57725a10f
47b2c77b915b329e570c90846eca354495c2b1cdb73e410701cb19c8cef38b12
```

Expected clean worktree and committed feature scope:

```text
A  course/templates/video/character_representation.py
M  course/templates/video/final_script_v1.md
D  course/templates/video/final_script_v1_lab.py
A  course/templates/video/text_preparation.py
A  tests/test_final_script_v1.py
```

Reject any established course artifact, draft, unrelated test, source,
`.playwright-mcp`, media, or production path.

---

## Local Integration Note

The primary checkout contains the approved source as a tracked, modified file.
The branch includes a polished version of that same user draft, so preserve a
recoverable copy before clearing the primary path for fast-forward integration.

1. Verify:

   ```bash
   git -C /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch branch --show-current
   shasum -a 256 /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/templates/video/final_script_v1.md
   test ! -e /private/tmp/final_script_v1-user-4031ae35da3123c0022a0613b4ba55cf.md
   ```

   Expected branch: `main`. Expected source hash:
   `4031ae35da3123c0022a0613b4ba55cf93716502173041f16d4bf50c4dc601be`.

2. Copy the dirty user draft to the explicit recoverable backup:

   ```bash
   cp /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/templates/video/final_script_v1.md /private/tmp/final_script_v1-user-4031ae35da3123c0022a0613b4ba55cf.md
   shasum -a 256 /private/tmp/final_script_v1-user-4031ae35da3123c0022a0613b4ba55cf.md
   ```

3. Restore only that tracked primary path to its current `HEAD` after the
   backup is verified:

   ```bash
   git -C /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch restore --worktree course/templates/video/final_script_v1.md
   ```

   Do not restore, stage, or alter any other dirty path.

4. Fast-forward local `main`:

   ```bash
   git -C /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch merge --ff-only codex/final-script-v1-standalone-examples
   ```

   If the merge fails, verify that the backup hash is exact, then restore the
   user draft:

   ```bash
   cp /private/tmp/final_script_v1-user-4031ae35da3123c0022a0613b4ba55cf.md /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/templates/video/final_script_v1.md
   ```

   Stop and report the failure without altering any other dirty path.

5. On merged `main`, rerun:

   ```bash
   uv run pytest tests/test_final_script_v1.py -v
   uv run pytest tests/test_course_structure.py -v
   uv run pytest -v
   python course/templates/video/character_representation.py
   python course/templates/video/text_preparation.py
   ```

6. Verify the original backup is readable and the other user-owned dirty
   paths retain their baseline hashes.

7. Only after merged-state verification, remove the task-owned worktree,
   prune worktree metadata, and delete the merged branch:

   ```bash
   git -C /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch worktree remove /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/.worktrees/final-script-v1-standalone-examples
   git -C /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch worktree prune
   git -C /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch branch -d codex/final-script-v1-standalone-examples
   ```

If any precondition fails, stop before clearing the primary script or merging.
