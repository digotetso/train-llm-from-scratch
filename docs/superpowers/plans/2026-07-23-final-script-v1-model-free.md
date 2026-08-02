# Final Video 1 Model-Free Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Revise the final Video 1 narration so it defers `model` and `parameter` terminology completely, preserves the text-representation lesson, and supplies an exact independently runnable companion lab.

**Architecture:** Build the revision in an isolated worktree because the primary checkout contains protected uncommitted work and the source narration is currently untracked. Reproduce the approved source exactly in the worktree before changing it, revise the teaching dependency chain in two reviewed increments, then add and verify a dedicated companion lab. Finish with a complete read-aloud, terminology, evidence, test, and preservation audit.

**Tech Stack:** Markdown, Python 3 standard library, pytest, Git worktrees, existing repository source and course artifacts.

## Global Constraints

- Treat `docs/superpowers/specs/2026-07-23-final-script-v1-model-free-design.md` as the approved source of truth.
- At execution time, invoke `superpowers:using-git-worktrees` and create or verify branch `codex/final-script-v1-model-free` in `.worktrees/final-script-v1-model-free`.
- Read the untracked source from `/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/templates/video/final_script_v1.md`; its approved baseline SHA-256 is `0b8723d48353e80c8915326e232a44566c8151fb776d5412c4ef4f120edc94ed`.
- Modify only `course/templates/video/final_script_v1.md` and create only `course/templates/video/final_script_v1_lab.py` as implementation artifacts.
- Do not modify established Video 1 artifacts, repository source, repository tests, `course/video_1_script_4.md`, `course/video_1_improved_script.md`, `script_video1_draft.md`, `.playwright-mcp/`, or any media/production file.
- The narration and companion lab must contain no case-insensitive standalone `model`, `models`, `parameter`, or `parameters`, including compound phrases such as `model-ready` and `model-input`.
- Use ordinary-language replacements such as `later AI-training stages`, `numerical input used during later training`, and `adjustable internal numbers`.
- Keep token, token ID, and embedding only as brief job-before-label roadmap signposts; do not teach their internal mechanisms.
- Collapse the untaught roadmap tail into one visibly closed `later AI-training stages` box.
- Preserve exactly nine timestamped sections and keep the narration between 2,000 and 2,250 whitespace-delimited words.
- Keep every spoken sentence at forty words or fewer.
- Preserve the exact current `normalize_text` source excerpt and the exact `prepare.py` lines that normalize, store, and count text.
- Use separate verified NFKC examples: `① -> 1` for collapsed source distinction and `ﬀ -> ff` for length `1 -> 2`.
- Embed the new companion lab source, invocation command, and freshly observed output exactly.
- Use `apply_patch` for all content changes, stage explicit paths only, and inspect the staged name list before every commit.
- Do not create, modify, stage, or commit media, video, audio, animation, render, font, After Effects, Premiere, or browser-capture files.

---

## File Map

- `docs/superpowers/specs/2026-07-23-final-script-v1-model-free-design.md` is the approved narrative, terminology, lab, preservation, and acceptance contract.
- `/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/templates/video/final_script_v1.md` is the untracked primary-checkout source.
- `course/templates/video/final_script_v1.md` is the worktree target and final narration deliverable.
- `course/templates/video/final_script_v1_lab.py` is the new self-contained standard-library lab.
- `matgpt/data/normalize.py` is the source of the exact normalization function and operation order.
- `matgpt/data/prepare.py` is the source of the exact normalized-text storage and `num_chars` lines.
- `course/videos/001-computer-learning-from-text/` contains protected established course artifacts used only for factual comparison.
- `tests/test_course_structure.py` is the focused existing course contract and remains unchanged.

---

### Task 1: Reproduce The Source And Revise The Opening Roadmap

**Files:**

- Create: `course/templates/video/final_script_v1.md`
- Read: `/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/templates/video/final_script_v1.md`
- Read: `docs/superpowers/specs/2026-07-23-final-script-v1-model-free-design.md`

**Interfaces:**

- Consumes: the approved untracked source narration and model-free terminology boundary.
- Produces: a complete worktree copy whose `00:00` and `01:00` sections are model-free while every section from `03:00` onward still exactly matches the source.

- [ ] **Step 1: Verify isolation, source, and protected baselines**

Run from the isolated worktree:

```bash
pwd -P
git branch --show-current
git status --short
test ! -e course/templates/video/final_script_v1.md
test ! -e course/templates/video/final_script_v1_lab.py
shasum -a 256 \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/templates/video/final_script_v1.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/lab.py \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/lab.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/script.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/lesson.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/quiz.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/answer-key.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/evidence.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/tests/test_course_structure.py \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_script_4.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_improved_script.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/script_video1_draft.md
```

Expected branch:

```text
codex/final-script-v1-model-free
```

Expected hashes, in command order:

```text
0b8723d48353e80c8915326e232a44566c8151fb776d5412c4ef4f120edc94ed
a4a7723384380147b7bb4c28f153a3ead6165957ed08f49806c8f0fc3d1e2342
9d2d99f336eb37fe791eb7fc693ceb20346935d0b0731e2e7c5f7206cb919905
33bd5437b98f329b4755591b091b8b5be890be45dd8855d16e74c48426e446fe
b46d13b3c131412d111d8e1006eefe591ff3f9f56e997074a04eb3bb9080ce9e
7da0c8ffff7b0a5e4451a3a9ed0605a72e4c74a55be6487769849bd54e9d1f82
e35187579f09bdd1975c698c6ca7f8a16afadb14694c34ef6bb1a0c5d41c89aa
25472b46c9e1b06cd92f012bbd50001469130455329a9b0d67e5a42f01fcfbed
47b2c77b915b329e570c90846eca354495c2b1cdb73e410701cb19c8cef38b12
6e837a036829b548c1c5ee55f78e40855b8f017d4328e604df708d536f343414
2d367e1885b8f097466e24dbe115c075aad581580975bb58a91a7320c21f0de0
732560ab1c9fbaa9ad98a508bf0148d72682b85bdc04ad4eb49cdaa57725a10f
```

If a protected hash differs, record the user's new state and update the preservation baseline without reverting it.

- [ ] **Step 2: Run the clean-worktree baseline suite**

Run:

```bash
uv run pytest -v
```

Expected: all collected tests pass before either new final-script artifact exists.

- [ ] **Step 3: Demonstrate the target is absent**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

path = Path("course/templates/video/final_script_v1.md")
text = path.read_text(encoding="utf-8")
print(text)
PY
```

Expected: `FileNotFoundError` for `course/templates/video/final_script_v1.md`.

- [ ] **Step 4: Reproduce the approved source exactly**

Read the primary source by absolute path. Use `apply_patch` with `*** Add File`
to reproduce the complete 421-line narration at
`course/templates/video/final_script_v1.md`. Before making any wording change,
run:

```bash
shasum -a 256 course/templates/video/final_script_v1.md
```

Expected:

```text
0b8723d48353e80c8915326e232a44566c8151fb776d5412c4ef4f120edc94ed  course/templates/video/final_script_v1.md
```

Do not use `cp`, shell redirection, Python file writes, or another write
mechanism to bypass the required patch workflow.

- [ ] **Step 5: Replace the `00:00` opening**

Use `apply_patch` so the opening preserves the familiar AI experience and
larger course question, then uses this exact approved paragraph:

```markdown
We will build the answer one step at a time. Before AI can learn from text, software must first be able to identify the characters, store the text, and prepare it consistently. Later stages can divide the prepared text into reusable pieces and turn those pieces into the numerical input used during training.
```

Keep the existing prerequisite question and four learner outcomes, except
replace outcome 4 with:

```markdown
4. why these early numerical forms are not yet token IDs, embeddings, or the numerical input used during later training.
```

- [ ] **Step 6: Compress the `01:00` roadmap**

Use this exact displayed map:

```text
Written source text
├── represented in software
│   ├── characters have Unicode code points
│   └── UTF-8 represents the text as bytes
│
└── prepared for later processing
    └── normalize and clean the source text
        -> prepared training text
        -> reusable text pieces [tokens]
        -> one identifier per piece [token ID]
        -> use the ID to select a learned number list [embedding]
        -> later AI-training stages [closed]
```

Write connected spoken paragraphs that:

```text
- explain that the map shows dependencies, not mechanisms;
- explain representation and preparation jobs first;
- describe reusable piece, integer identifier, and selected learned number
  list before or with token, token ID, and embedding;
- state that every later arrow can hide another lesson;
- close all later training stages without naming prediction, error, update, or
  adjustable-number mechanisms in this section;
- carry the learner to the three jobs opened at 03:00.
```

- [ ] **Step 7: Verify Task 1's bounded change**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re

primary = Path(
    "/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/"
    "course/templates/video/final_script_v1.md"
).read_text(encoding="utf-8")
target = Path("course/templates/video/final_script_v1.md").read_text(encoding="utf-8")

primary_tail = primary.split("## 03:00 Three Jobs Before Tokenization", 1)[1]
target_tail = target.split("## 03:00 Three Jobs Before Tokenization", 1)[1]
assert target_tail == primary_tail

prefix = target.split("## 03:00 Three Jobs Before Tokenization", 1)[0]
assert not re.search(r"\bmodels?\b|\bparameters?\b|model[- ]?(ready|input)", prefix, re.IGNORECASE)
assert "later AI-training stages [closed]" in prefix
assert "reusable text pieces [tokens]" in prefix
assert "one identifier per piece [token ID]" in prefix
assert "use the ID to select a learned number list [embedding]" in prefix
assert len([line for line in target.splitlines() if line.startswith("## ")]) == 9
print("PASS: opening and roadmap are model-free; the source tail is unchanged")
PY
```

Expected:

```text
PASS: opening and roadmap are model-free; the source tail is unchanged
```

- [ ] **Step 8: Commit only the opening revision**

Run:

```bash
git add course/templates/video/final_script_v1.md
git diff --cached --name-status
git diff --cached --check
git commit -m "docs: revise final video one opening"
```

Expected staged name list:

```text
A  course/templates/video/final_script_v1.md
```

---

### Task 2: Remove Premature Terminology And Tighten The Mechanisms

**Files:**

- Modify: `course/templates/video/final_script_v1.md`
- Read: `matgpt/data/normalize.py`
- Read: `matgpt/data/prepare.py`

**Interfaces:**

- Consumes: the reviewed model-free opening and roadmap from Task 1.
- Produces: all non-lab sections with deferred terminology, corrected byte and NFKC evidence, a concise annotation explanation, and a model-free recap.

- [ ] **Step 1: Demonstrate remaining prohibited terminology**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re

text = Path("course/templates/video/final_script_v1.md").read_text(encoding="utf-8")
matches = [
    (number, line)
    for number, line in enumerate(text.splitlines(), 1)
    if re.search(r"\bmodels?\b|\bparameters?\b|model[- ]?(ready|input)", line, re.IGNORECASE)
]
assert matches, "expected later sections to retain prohibited terminology before Task 2"
for number, line in matches:
    print(f"{number}: {line}")
PY
```

Expected: one or more lines from the `04:20`, `08:15`, `10:45`, or `13:20`
sections. The `10:45` displayed lab is intentionally fixed in Task 3.

- [ ] **Step 2: Tighten the byte explanation**

Use `apply_patch` to replace the loose byte definition with this exact
spoken text:

```markdown
A byte is a small unit of storage. When we display its unsigned value, it is a number from `0` through `255`. UTF-8 is a common rule for representing Unicode text as one or more bytes.
```

After revealing the `Cat` byte values, explain their equality first:

```markdown
For these basic Latin characters, UTF-8 uses one byte with the same value as the code point.
```

Then name the boundary:

```markdown
These characters are in a range historically called ASCII. The matching values are convenient, but they are not a universal rule.
```

- [ ] **Step 3: Separate the two NFKC claims**

Use `apply_patch` to teach:

```markdown
For example, NFKC changes the circled digit `①` into the ordinary digit `1`. Both results contain one Python character, but a distinction in the source has disappeared.

Character count can change in a different example. NFKC changes the single typographic ligature `ﬀ` into the two characters `ff`, so the Python string length changes from `1` to `2`.
```

Immediately compress the policy:

```markdown
> **Prepared text follows a chosen policy. It is not necessarily a lossless copy of the source.**
```

- [ ] **Step 4: Simplify the annotation aside**

Keep the exact `normalize_text` function excerpt. Replace the multi-sentence
typing detour with:

```markdown
The annotations tell readers that this function expects and returns text; `str(text)` is the operation that explicitly asks Python for a string.
```

Continue immediately with NFKC and the source-order trace:

```text
str(text)
-> NFKC
-> newline standardization
-> selected control-character removal
-> per-line trailing-whitespace removal
-> outer stripping
-> blank-line-run limiting
-> return prepared string
```

- [ ] **Step 5: Remove deferred terminology outside the lab**

Use ordinary-language replacements throughout `03:00` through `08:15` and
`13:20`.

Required exact boundary sentences:

```markdown
This is an early numerical representation of the text. It is not yet the numerical input used during later AI training.
```

```markdown
The output of `normalize_text` is still Unicode text. It has been prepared according to the repository's policy, but later stages have not yet divided it into reusable pieces or produced the numerical input used during training.
```

Use this final compact distinction:

```markdown
> **Representing and preparing text changes the data according to fixed rules. Later training uses examples and measured error to change adjustable internal numbers.**
```

Replace the final route with:

```text
prepared text
-> reusable text pieces [tokens]
-> one identifier per piece [token ID]
-> learned number list selected using that ID [embedding]
-> later AI-training stages [closed]
```

In the classification exercise, use:

```markdown
5. A later training step changes adjustable internal numbers after measuring error.
```

Answer items 4 and 5 as:

```markdown
4. a later AI-training input step; and
5. a later training change.
```

Remove the editorial sentence beginning `This is where the brief boundary`.
Replace it with a direct learner-facing transition from fixed rules to the
classification exercise.

- [ ] **Step 6: Verify all non-lab sections and repository evidence**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re
import unicodedata

path = Path("course/templates/video/final_script_v1.md")
text = path.read_text(encoding="utf-8")
before_lab, remainder = text.split("## 10:45 Predict, Run, and Explain", 1)
lab_body, recap = remainder.split("## 13:20 Return to the Whole Route", 1)
non_lab = before_lab + recap

assert not re.search(r"\bmodels?\b|\bparameters?\b|model[- ]?(ready|input)", non_lab, re.IGNORECASE)
assert unicodedata.normalize("NFKC", "①") == "1"
assert len("①") == len("1") == 1
assert unicodedata.normalize("NFKC", "ﬀ") == "ff"
assert len("ﬀ") == 1 and len("ff") == 2
for exact in [
    "Both results contain one Python character",
    "the Python string length changes from `1` to `2`",
    "A byte is a small unit of storage.",
    "later AI-training stages [closed]",
    "adjustable internal numbers",
]:
    assert exact in text, exact

normalize_source = Path("matgpt/data/normalize.py").read_text(encoding="utf-8")
assert normalize_source[normalize_source.index("def normalize_text"):].strip() in text
for exact_line in [
    "normalized = normalize_text(text)",
    '"text": normalized,',
    '"num_chars": len(normalized),',
]:
    assert exact_line in text, exact_line
print("PASS: non-lab narration is model-free and all fixed mechanisms are exact")
PY
```

Expected:

```text
PASS: non-lab narration is model-free and all fixed mechanisms are exact
```

- [ ] **Step 7: Commit only the terminology and mechanism revision**

Run:

```bash
git add course/templates/video/final_script_v1.md
git diff --cached --name-status
git diff --cached --check
git commit -m "docs: remove premature terminology from final video one"
```

Expected staged name list:

```text
M  course/templates/video/final_script_v1.md
```

---

### Task 3: Add And Align The Self-Contained Companion Lab

**Files:**

- Modify: `course/templates/video/final_script_v1.md`
- Create: `course/templates/video/final_script_v1_lab.py`

**Interfaces:**

- Consumes: the reviewed model-free explanation and exact Unicode/UTF-8 rules.
- Produces: an independently runnable companion whose source, command, output, changed case, and narration agree exactly.

- [ ] **Step 1: Demonstrate that the companion is absent and the displayed lab is stale**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re

script = Path("course/templates/video/final_script_v1.md").read_text(encoding="utf-8")
lab = Path("course/templates/video/final_script_v1_lab.py")
assert not lab.exists()
lab_section = script.split("## 10:45 Predict, Run, and Explain", 1)[1].split(
    "## 13:20 Return to the Whole Route", 1
)[0]
assert re.search(r"\bmodels?\b|model[- ]?(ready|input)", lab_section, re.IGNORECASE)
print("RED: companion file is absent and the displayed lab retains deferred terminology")
PY
```

Expected:

```text
RED: companion file is absent and the displayed lab retains deferred terminology
```

- [ ] **Step 2: Create the companion lab**

Use `apply_patch` to add exactly:

```python
text = "Cat"

print("Human-readable text:", text)
print("Unicode code points:", [ord(character) for character in text])
print("UTF-8 bytes:", list(text.encode("utf-8")))
print("Ready for later AI training? Not yet")
print("Tokens, token IDs, and embeddings belong to later stages.")
```

- [ ] **Step 3: Replace the displayed source, command, and output**

Embed the complete companion source exactly. Use:

```bash
python course/templates/video/final_script_v1_lab.py
```

Show exactly:

```text
Human-readable text: Cat
Unicode code points: [67, 97, 116]
UTF-8 bytes: [67, 97, 116]
Ready for later AI training? Not yet
Tokens, token IDs, and embeddings belong to later stages.
```

Preserve this spoken sequence:

```text
ask learner to predict both Cat lists
-> run the exact command
-> observe five lines
-> explain ord, encode, and list
-> change only Cat to A in the companion file
-> predict [65] and [65]
-> rerun and compare
-> restore Cat
```

Keep the NFKC prediction separate and explicitly state that the companion lab
does not call `normalize_text`.

- [ ] **Step 4: Verify complete terminology, lab, and script contracts**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re
import subprocess

script_path = Path("course/templates/video/final_script_v1.md")
lab_path = Path("course/templates/video/final_script_v1_lab.py")
script = script_path.read_text(encoding="utf-8")
lab = lab_path.read_text(encoding="utf-8")

prohibited = re.compile(
    r"\bmodels?\b|\bparameters?\b|model[- ]?(ready|input)",
    re.IGNORECASE,
)
assert not prohibited.search(script)
assert not prohibited.search(lab)

expected_headings = [
    "## 00:00 The Big Question and Today’s First Step",
    "## 01:00 Where This Video Fits in AI Training",
    "## 03:00 Three Jobs Before Tokenization",
    "## 04:20 Representing Characters with Unicode",
    "## 05:50 Storing Unicode Text with UTF-8",
    "## 07:00 Preparing Text Consistently",
    "## 08:15 Apply Text Preparation in the Repository",
    "## 10:45 Predict, Run, and Explain",
    "## 13:20 Return to the Whole Route",
]
headings = [line for line in script.splitlines() if line.startswith("## ")]
assert headings == expected_headings, headings
words = len(script.split())
assert 2000 <= words <= 2250, words

assert lab.strip() in script
assert "python course/templates/video/final_script_v1_lab.py" in script
result = subprocess.run(
    ["python", str(lab_path)],
    check=True,
    capture_output=True,
    text=True,
)
assert result.stderr == ""
assert result.stdout.strip() in script
for exact in [
    "Unicode code points: [65]",
    "UTF-8 bytes: [65]",
    "Then restore `Cat`.",
    "does not call `normalize_text`",
]:
    assert exact in script, exact
print(f"PASS: model-free final script has nine sections and {words} words; companion output is exact")
PY
```

Expected: one `PASS` line with a word count from `2000` through `2250`.

- [ ] **Step 5: Run the focused existing course contract**

Run:

```bash
uv run pytest tests/test_course_structure.py -v
```

Expected: all focused tests pass without changing the test or established
course artifacts.

- [ ] **Step 6: Commit only the final script and companion**

Run:

```bash
git add \
  course/templates/video/final_script_v1.md \
  course/templates/video/final_script_v1_lab.py
git diff --cached --name-status
git diff --cached --check
git commit -m "docs: add standalone final video one lab"
```

Expected staged name list:

```text
M  course/templates/video/final_script_v1.md
A  course/templates/video/final_script_v1_lab.py
```

---

### Task 4: Perform The Complete Read-Aloud And Preservation Audit

**Files:**

- Modify if required by review: `course/templates/video/final_script_v1.md`
- Verify: `course/templates/video/final_script_v1_lab.py`
- Verify unchanged: all protected paths in Global Constraints

**Interfaces:**

- Consumes: the complete revised narration and exact companion lab.
- Produces: a reviewed, conversational, model-free Video 1 package with fresh repository test and preservation evidence.

- [ ] **Step 1: Scan spoken sentence length**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re

text = Path("course/templates/video/final_script_v1.md").read_text(encoding="utf-8")
blocks = []
paragraph = []
in_fence = False

def flush_paragraph():
    if paragraph:
        blocks.append(" ".join(paragraph))
        paragraph.clear()

for raw_line in text.splitlines():
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
sentences = [
    part.strip()
    for block in blocks
    for part in re.split(
        r"(?<=[.!?])\s+",
        re.sub(r"[*_`]", "", block),
    )
    if part.strip()
]
long = [
    (len(sentence.split()), sentence)
    for sentence in sentences
    if len(sentence.split()) > 40
]
for count, sentence in long:
    print(f"{count}: {sentence}")
assert not long, f"{len(long)} spoken sentences exceed forty words"
print(f"PASS: {len(sentences)} spoken sentences are at most forty words")
PY
```

Expected: no spoken sentence exceeds forty words.

- [ ] **Step 2: Conduct the deliberate teaching and read-aloud review**

Read every spoken paragraph aloud and use `apply_patch` only for revisions
supported by one of these findings:

```text
- a sentence loses its subject or needs more than one breath;
- several independent short statements sound like a list rather than a
  connected explanation;
- an untaught term is doing explanatory work;
- a roadmap signpost begins teaching a deferred mechanism;
- a displayed result appears before the learner can predict it;
- the completed Unicode idea does not create the UTF-8 question;
- the completed representation idea does not create the preparation question;
- the preparation trace does not create the companion-lab question;
- the final recap repeats facts without enabling the transfer exercise or
  Video 2 question;
- code, commands, displayed output, or numerical values diverge from verified
  behavior.
```

Preserve all exact source, lab, output, heading, terminology, and NFKC
contracts while revising spoken flow.

- [ ] **Step 3: Run the complete final-script contract**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re
import subprocess
import unicodedata

script_path = Path("course/templates/video/final_script_v1.md")
lab_path = Path("course/templates/video/final_script_v1_lab.py")
script = script_path.read_text(encoding="utf-8")
lab = lab_path.read_text(encoding="utf-8")

prohibited = re.compile(
    r"\bmodels?\b|\bparameters?\b|model[- ]?(ready|input)",
    re.IGNORECASE,
)
assert not prohibited.search(script)
assert not prohibited.search(lab)

headings = [line for line in script.splitlines() if line.startswith("## ")]
assert headings == [
    "## 00:00 The Big Question and Today’s First Step",
    "## 01:00 Where This Video Fits in AI Training",
    "## 03:00 Three Jobs Before Tokenization",
    "## 04:20 Representing Characters with Unicode",
    "## 05:50 Storing Unicode Text with UTF-8",
    "## 07:00 Preparing Text Consistently",
    "## 08:15 Apply Text Preparation in the Repository",
    "## 10:45 Predict, Run, and Explain",
    "## 13:20 Return to the Whole Route",
]
words = len(script.split())
assert 2000 <= words <= 2250, words

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
sentences = [
    part.strip()
    for block in blocks
    for part in re.split(
        r"(?<=[.!?])\s+",
        re.sub(r"[*_`]", "", block),
    )
    if part.strip()
]
long = [
    (len(sentence.split()), sentence)
    for sentence in sentences
    if len(sentence.split()) > 40
]
assert not long, long

assert unicodedata.normalize("NFKC", "①") == "1"
assert len("①") == len("1") == 1
assert unicodedata.normalize("NFKC", "ﬀ") == "ff"
assert len("ﬀ") == 1 and len("ff") == 2

normalize_source = Path("matgpt/data/normalize.py").read_text(encoding="utf-8")
assert normalize_source[normalize_source.index("def normalize_text"):].strip() in script
for exact_line in [
    "normalized = normalize_text(text)",
    '"text": normalized,',
    '"num_chars": len(normalized),',
]:
    assert exact_line in script

assert f"```python\n{lab.strip()}\n```" in script
result = subprocess.run(
    ["python", str(lab_path)],
    check=True,
    capture_output=True,
    text=True,
)
assert result.stderr == ""
assert f"```text\n{result.stdout.strip()}\n```" in script
assert "python course/templates/video/final_script_v1_lab.py" in script
for exact in [
    "Before AI can learn from text, software must first be able to identify the characters, store the text, and prepare it consistently.",
    "reusable text pieces [tokens]",
    "one identifier per piece [token ID]",
    "use the ID to select a learned number list [embedding]",
    "later AI-training stages [closed]",
    "Both results contain one Python character",
    "the Python string length changes from `1` to `2`",
    "A byte is a small unit of storage.",
    "For these basic Latin characters, UTF-8 uses one byte with the same value as the code point.",
    "These characters are in a range historically called ASCII.",
    "The annotations tell readers that this function expects and returns text; `str(text)` is the operation that explicitly asks Python for a string.",
    "Representing and preparing text changes the data according to fixed rules. Later training uses examples and measured error to change adjustable internal numbers.",
    "Unicode code points: [65]",
    "UTF-8 bytes: [65]",
    "Then restore `Cat`.",
    "does not call `normalize_text`",
]:
    assert exact in script, exact
print(
    f"PASS: complete final-script contract with {words} words, "
    f"nine sections, and {len(sentences)} spoken sentences"
)
PY
```

Expected: one `PASS` line with a word count from `2000` through `2250`, nine
sections, and no spoken sentence over forty words.

- [ ] **Step 4: Run focused and full repository tests**

Run:

```bash
uv run pytest tests/test_course_structure.py -v
uv run pytest -v
```

Expected: both commands exit `0`; do not modify or weaken tests in response to
a failure.

- [ ] **Step 5: Commit a final polish only when review changed narration**

If Step 2 changed the narration, run:

```bash
git add course/templates/video/final_script_v1.md
git diff --cached --name-status
git diff --cached --check
git commit -m "docs: polish model-free final video one script"
```

Expected staged name list:

```text
M  course/templates/video/final_script_v1.md
```

If Step 2 made no edit, do not create an empty commit.

- [ ] **Step 6: Verify protected primary files and feature scope**

Run from the isolated worktree:

```bash
shasum -a 256 \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/templates/video/final_script_v1.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/lab.py \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/lab.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/script.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/lesson.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/quiz.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/answer-key.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/evidence.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/tests/test_course_structure.py \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_script_4.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_improved_script.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/script_video1_draft.md
git diff --check
git status --short
git diff --name-only main...HEAD
```

Expected hashes remain the Task 1 baselines.

Expected isolated-worktree status: clean.

Expected committed feature paths:

```text
course/templates/video/final_script_v1.md
course/templates/video/final_script_v1_lab.py
```

No established course artifact, source, test, `.playwright-mcp`, or
media/production path may appear in the feature range.

---

## Local Integration Note

The primary checkout contains the approved source as an untracked file at the
same path the feature branch will add. A direct local merge would therefore
refuse to overwrite it.

If the user chooses local merge after final review:

1. Verify that the primary checkout is still on `main`, the source still has
   SHA-256
   `0b8723d48353e80c8915326e232a44566c8151fb776d5412c4ef4f120edc94ed`,
   and this explicit recoverable backup path does not already exist:

   ```text
   /private/tmp/final_script_v1-original-0b8723d48353e80c8915326e232a44566.md
   ```

   Run:

   ```bash
   git -C /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch branch --show-current
   shasum -a 256 /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/templates/video/final_script_v1.md
   test ! -e /private/tmp/final_script_v1-original-0b8723d48353e80c8915326e232a44566.md
   ```

   Expected branch: `main`. Expected hash: the approved source hash above.

2. Move the untracked original to the backup path; do not delete it:

   ```bash
   mv /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/templates/video/final_script_v1.md /private/tmp/final_script_v1-original-0b8723d48353e80c8915326e232a44566.md
   ```

3. Fast-forward the feature branch into local `main`:

   ```bash
   git -C /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch merge --ff-only codex/final-script-v1-model-free
   ```

   If the merge fails, first verify that the original path is absent, then
   restore the backup with:

   ```bash
   test ! -e /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/templates/video/final_script_v1.md
   mv /private/tmp/final_script_v1-original-0b8723d48353e80c8915326e232a44566.md /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/templates/video/final_script_v1.md
   ```

   Stop after restoration and report the merge failure. Do not alter the
   user's remaining dirty files.

4. Run the complete final-script contract and full repository suite on merged
   `main`.
5. Confirm the tracked final script and companion lab are present, all other
   dirty primary-checkout files remain unchanged, and the backup remains
   readable.
6. Only after successful merged-state verification, remove the owned worktree
   and delete the merged feature branch:

   ```bash
   git -C /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch worktree remove /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/.worktrees/final-script-v1-model-free
   git -C /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch branch -d codex/final-script-v1-model-free
   ```

If any precondition fails, stop before moving the source or merging.
