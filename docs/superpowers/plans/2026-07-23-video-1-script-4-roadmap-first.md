# Video 1 Script 4 Roadmap-First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a verified fourth Video 1 narration that first shows the complete text-to-training roadmap, keeps later mechanisms closed as brief signposts, and then fully teaches text representation through the repository and canonical mini-lab.

**Architecture:** Implement one standalone Markdown narration in three independently reviewable increments: roadmap orientation, the fully opened representation mechanism, and repository/lab application with a return to the roadmap. Execute in an isolated worktree because the primary `main` checkout contains protected uncommitted work. Finish with conversational, cognitive-load, technical, test, and preservation gates before local integration.

**Tech Stack:** Markdown, Python 3 standard library, pytest, existing repository course artifacts.

## Global Constraints

- Treat `docs/superpowers/specs/2026-07-23-video-1-script-4-roadmap-first-design.md` as the approved source of truth.
- At execution time, invoke `superpowers:using-git-worktrees` and create or verify an isolated worktree on branch `codex/video-1-script-4-roadmap-first`; never draft on dirty `main`.
- Read the untracked source draft from `/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/script_video1_draft.md`; it will not be copied into a linked worktree.
- Preserve the source draft unchanged and create only `course/video_1_script_4.md` as the narration deliverable.
- Preserve the approximately fourteen-to-fifteen-minute scope, 1,900-2,200 words, and exactly eight timestamped sections.
- Use the corrected roadmap order: training text -> token signpost -> token ID signpost -> ID selects embedding signpost -> model calculation -> prediction -> known target comparison -> measured error -> closed update method -> parameter change -> repeat.
- Give each later stage one plain-language job and one technical label in no
  more than one or two spoken sentences; do not teach tokenization, embedding
  lookup, probability calculation, loss, gradients, backpropagation,
  optimizers, tensors, or softmax.
- State explicitly that a token ID is an integer identifier used to select an embedding; it does not become or get represented by an embedding.
- Use **text representation** as the stable building-block name and fully teach the character/code-point/UTF-8 boundary.
- Keep Unicode code points, UTF-8 bytes, token IDs, and embeddings distinct.
- Preserve the verified repository normalization order, non-lossless NFKC warning, lab source, invocation command, five-line output, and changed `A` case.
- Write connected conversational paragraphs rather than a sequence of isolated declarations or quiz prompts.
- Do not modify, stage, or commit `script_video1_draft.md`, `course/videos/001-computer-learning-from-text/script.md`, `course/video_1_improved_script.md`, `course/video_1_script_2.md`, or `course/video_1_script_3.md`.
- Do not modify, stage, or commit repository source, tests, `.playwright-mcp/`, media, video, audio, animation, render, font, or Adobe project files.
- Stage explicit paths only and inspect the staged name list before each commit.

---

## File Map

- `docs/superpowers/specs/2026-07-23-video-1-script-4-roadmap-first-design.md` is the approved narrative, technical, voice, preservation, and acceptance contract.
- `docs/superpowers/plans/2026-07-23-video-1-script-4-roadmap-first.md` is this implementation plan.
- `/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/script_video1_draft.md` is the untracked user source whose core angle must be preserved without editing the file.
- `course/video_1_script_4.md` will be the only new narration deliverable.
- `course/outline.md` is the source of later lesson ownership for tokens, embeddings, predictions, and parameter updates.
- `course/videos/001-computer-learning-from-text/lesson.md` is the canonical conceptual and factual reference.
- `course/videos/001-computer-learning-from-text/evidence.md` distinguishes verified repository facts, observed behavior, teaching examples, and deferred claims.
- `course/videos/001-computer-learning-from-text/lab.py` is the exact executable proof embedded and explained by Script 4.
- `matgpt/data/normalize.py` is the authoritative normalization sequence.
- `matgpt/data/prepare.py` is the authoritative normalized-text storage and `num_chars` source.
- `tests/test_course_structure.py` is the focused canonical course contract.

---

### Task 1: Build The Roadmap Orientation

**Files:**

- Create: `course/video_1_script_4.md`
- Read: `/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/script_video1_draft.md`
- Read: `docs/superpowers/specs/2026-07-23-video-1-script-4-roadmap-first-design.md`
- Read: `course/outline.md`

**Interfaces:**

- Consumes: the user's whole-journey-first angle, the approved corrected roadmap, and the course's later-lesson ownership.
- Produces: the title and first three timestamped sections, ending with all future boxes closed and one explicit Video 1 question ready to open.

- [ ] **Step 1: Verify isolation and record protected primary-checkout hashes**

From the isolated worktree, run:

```bash
pwd -P
git branch --show-current
git status --short
shasum -a 256 \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/script_video1_draft.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/script.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_improved_script.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_script_2.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_script_3.md
test ! -e course/video_1_script_4.md
```

Expected branch:

```text
codex/video-1-script-4-roadmap-first
```

Expected hashes:

```text
732560ab1c9fbaa9ad98a508bf0148d72682b85bdc04ad4eb49cdaa57725a10f  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/script_video1_draft.md
33bd5437b98f329b4755591b091b8b5be890be45dd8855d16e74c48426e446fe  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/script.md
2d367e1885b8f097466e24dbe115c075aad581580975bb58a91a7320c21f0de0  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_improved_script.md
89d5b7e82307780f2c4a2bcb55c81d72cd4c2b5a2f36a2064d94c143fd7dba26  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_script_2.md
2a18abc729ae7cf61080ef9fbb8bbe71d487a794149f2b11a74d16d55d7821df  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_script_3.md
```

Expected: the isolated worktree is clean and the target-file check exits `0`. If a protected primary hash differs, report the new user state and update the preservation baseline without reverting it.

- [ ] **Step 2: Run the clean-worktree baseline suite**

Run:

```bash
uv run pytest -v
```

Expected: all collected tests pass before Script 4 exists. Stop and report any baseline failure rather than attributing it to the new narration.

- [ ] **Step 3: Run the structural check before creating the target**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

path = Path("course/video_1_script_4.md")
text = path.read_text(encoding="utf-8")
print(text)
PY
```

Expected: `FileNotFoundError` for `course/video_1_script_4.md`.

- [ ] **Step 4: Create the roadmap-first opening**

Use `apply_patch` to create `course/video_1_script_4.md` with exactly this title and heading order:

```markdown
# Video 1 — Script 4: What Does It Mean for a Computer to Learn From Text?

## 00:00 The Result and the Question
## 00:50 The Whole Journey in One Map
## 03:00 Close the Boxes We Have Not Opened
```

Write connected spoken paragraphs with this exact conceptual load:

```text
00:00
- Begin with AI clarifying an email, improving an essay sentence, and suggesting
  code.
- Ask how a system can improve at those tasks from written examples.
- Say that language models can learn from many text examples; large scale is
  common but is not the definition of learning.
- Separate the learner's experience of useful output from knowledge of the
  internal mechanism.
- Promise a whole-course map followed by one fully opened first step.

00:50
- Present this exact dependency map outside the spoken paragraph:
  Training text
  -> reusable text pieces [token]
  -> one identifier per piece [token ID]
  -> use the ID to select a learned number list [embedding]
  -> model calculations
  -> prediction
  -> compare with the known training target
  -> measured error
  -> closed update method
  -> changed parameters
  -> repeat across examples
- Describe each stage's job in ordinary language before naming its signpost.
- Use `Cat` only as a label moving across the map; do not invent token IDs,
  embedding values, probabilities, or loss values for it.
- Explain that the map shows dependency order and that each arrow can hide a
  later lesson.

03:00
- Distinguish locating a labeled box from understanding its mechanism.
- Explicitly close the dividing rule, token IDs, embeddings, model
  calculations, prediction math, target comparison, measured error, and update
  method.
- Correct the draft locally with this relationship:
  token -> token ID -> use the ID to select an embedding.
- State clearly that a token ID does not become an embedding and is not
  represented by one.
- Point to Videos 11, 23, and 37-40 as later boxes without teaching them.
- Carry the learner to today's one openable question: why must written text
  receive a numerical form before any later mathematical box can use it?
```

Do not use a decorative analogy. The map itself is orientation, while the later `A` and `Cat` traces will be evidence.

- [ ] **Step 5: Verify the roadmap-orientation contract**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re

path = Path("course/video_1_script_4.md")
text = path.read_text(encoding="utf-8")
headings = [line for line in text.splitlines() if line.startswith("## ")]
expected = [
    "## 00:00 The Result and the Question",
    "## 00:50 The Whole Journey in One Map",
    "## 03:00 Close the Boxes We Have Not Opened",
]
assert headings == expected, headings
words = len(text.split())
assert 500 <= words <= 850, words
ordered = [
    "Training text",
    "reusable text pieces",
    "token ID",
    "select a learned number list",
    "model calculations",
    "prediction",
    "known training target",
    "measured error",
    "closed update method",
    "changed parameters",
    "repeat across examples",
]
positions = [text.index(item) for item in ordered]
assert positions == sorted(positions), positions
assert "token ID does not become an embedding" in text
assert "not represented by an embedding" in text
for prohibited in [
    "tensor",
    "softmax",
    "gradient",
    "backpropagation",
    "optimizer",
    "cross-entropy",
    "probability",
]:
    assert not re.search(rf"\b{prohibited}s?\b", text, re.IGNORECASE), prohibited
print(f"PASS: roadmap opening has three headings and {words} words")
PY
```

Expected: one `PASS` line with a word count from `500` through `850`.

- [ ] **Step 6: Commit only the roadmap opening**

Run:

```bash
git add course/video_1_script_4.md
git diff --cached --name-status
git diff --cached --check
git commit -m "docs: draft roadmap-first video one opening"
```

Expected staged name list before commit:

```text
A  course/video_1_script_4.md
```

---

### Task 2: Fully Open Text Representation And Learning

**Files:**

- Modify: `course/video_1_script_4.md`
- Read: `course/videos/001-computer-learning-from-text/lesson.md`
- Read: `course/videos/001-computer-learning-from-text/evidence.md`

**Interfaces:**

- Consumes: the closed-box question produced by Task 1 and the canonical character/byte and learning boundaries.
- Produces: two additional sections that completely trace text representation and use it to construct the representation-learning distinction.

- [ ] **Step 1: Append the fully opened mechanism**

Use `apply_patch` to append exactly these headings:

```markdown
## 04:00 Why Text Needs a Numerical Form
## 06:30 Representation Is Not Learning
```

Write connected narration with this exact conceptual load:

```text
04:00
- Start with one written `A` and ask whether `ord("A")` invents a value or
  follows a stable standard.
- Reveal `ord("A") == 65` after the prediction.
- Explain the observable behavior before introducing character, Unicode, and
  code point one at a time.
- Correct identifier versus meaning: `65` stays fixed while `A` can mean a
  grade, musical note, blood type, or part of a name.
- Expand to the complete hand-checkable trace `C -> 67`, `a -> 97`, `t -> 116`.
- Introduce byte and UTF-8 after the code-point trace.
- Ask whether the `Cat` byte list will match, then explain the ASCII-range
  single-byte match and its non-universal boundary.
- Name the earned mechanism with this exact sentence:
  `Text representation changes text into a numerical form that software can store and process.`
- Explain that this is an early representation layer, not a token ID or
  embedding and not yet the model's precise numerical input.

06:30
- Ask what changed and what stayed fixed during character and byte conversion.
- Use the opening roadmap to identify the still-closed learning actions:
  model answer -> known target -> measured error -> closed update method ->
  changed parameters -> later answer.
- Define model and parameters operationally only after that behavior is visible.
- Use seven mistakes becoming five as a small picture of possible improvement
  after an update.
- State that the count is not the repository's training calculation and cannot
  prove performance on unseen examples; mention separate examples briefly.
- End with these exact reusable sentences:
  `Representation changes the form of the data.`
  `Learning changes adjustable model parameters using examples and measured error.`
- Spend the completed distinction on the next question: which side does
  repository normalization belong to?
```

- [ ] **Step 2: Verify the opened-mechanism contract**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re

text = Path("course/video_1_script_4.md").read_text(encoding="utf-8")
headings = [line for line in text.splitlines() if line.startswith("## ")]
expected = [
    "## 00:00 The Result and the Question",
    "## 00:50 The Whole Journey in One Map",
    "## 03:00 Close the Boxes We Have Not Opened",
    "## 04:00 Why Text Needs a Numerical Form",
    "## 06:30 Representation Is Not Learning",
]
assert headings == expected, headings
words = len(text.split())
assert 1050 <= words <= 1450, words
for required in [
    'ord("A")',
    "65",
    "67",
    "97",
    "116",
    "Unicode",
    "code point",
    "UTF-8",
    "ASCII",
    "Text representation changes text into a numerical form that software can store and process.",
    "Representation changes the form of the data.",
    "Learning changes adjustable model parameters using examples and measured error.",
    "seven",
    "five",
    "unseen examples",
]:
    assert required in text, required
for prohibited in [
    "tensor",
    "softmax",
    "gradient",
    "backpropagation",
    "optimizer",
    "cross-entropy",
    "probability",
]:
    assert not re.search(rf"\b{prohibited}s?\b", text, re.IGNORECASE), prohibited
print(f"PASS: roadmap plus opened mechanism has five headings and {words} words")
PY
```

Expected: one `PASS` line with a word count from `1050` through `1450`.

- [ ] **Step 3: Commit only the opened mechanism**

Run:

```bash
git add course/video_1_script_4.md
git diff --cached --name-status
git diff --cached --check
git commit -m "docs: teach representation in roadmap-first video one"
```

Expected staged name list before commit:

```text
M  course/video_1_script_4.md
```

---

### Task 3: Apply The Distinction And Return To The Map

**Files:**

- Modify: `course/video_1_script_4.md`
- Read: `matgpt/data/normalize.py`
- Read: `matgpt/data/prepare.py`
- Read: `course/videos/001-computer-learning-from-text/lab.py`
- Read: `course/videos/001-computer-learning-from-text/evidence.md`

**Interfaces:**

- Consumes: the stable text-representation and representation-learning building blocks produced by Task 2.
- Produces: the complete eight-section script with exact repository trace, exact mini-lab, changed case, roadmap payoff, and transfer exercise.

- [ ] **Step 1: Append the repository, lab, and roadmap payoff**

Use `apply_patch` to append exactly these headings:

```markdown
## 08:00 Apply the Distinction to the Repository
## 10:30 Predict, Run, and Explain
## 13:00 Return to the Whole Map
```

Write connected narration with this exact conceptual load:

```text
08:00
- Ask whether `normalize_text` changes data, model parameters, or both.
- Embed the complete current `normalize_text` function as an exact code excerpt.
- Trace `str(text)` -> NFKC -> newline standardization -> selected control-
  character removal -> per-line trailing-whitespace removal -> outer stripping ->
  blank-line-run limiting -> return.
- Explain that `text: str` and `-> str` communicate intended types without
  automatic runtime enforcement.
- State the NFKC boundary at the point of use: deliberate, non-lossless, `①`
  can become `1`, a source distinction can collapse, and character count can
  change.
- Show exact `prepare.py` lines for `normalized = normalize_text(text)`,
  `"text": normalized`, and `"num_chars": len(normalized)`.
- Classify the operation as preparation on the text-representation side because
  data changed while no measured error changed a model parameter.

10:30
- Embed the current `lab.py` source exactly.
- Ask for both `Cat` lists before revealing output.
- Preserve the exact command
  `python course/videos/001-computer-learning-from-text/lab.py`.
- Show the exact five-line observed output.
- Explain `ord`, `encode("utf-8")`, and `list` line by line.
- Change only `Cat` to `A`, ask the learner to apply the rule to `[65]`, rerun,
  explain, and restore `Cat`.
- Say this exact correction:
  `These character numbers are not token IDs or embeddings.`
- Return the learner to the map rather than opening those later boxes.

13:00
- Rebuild the complete roadmap once in ordinary language.
- Mark the exact path earned today: written character -> stable code point ->
  stored UTF-8 bytes -> prepared numerical data.
- Explain that later boxes now have a valid input dependency but remain closed.
- Repeat the representation-learning distinction once.
- Give a transfer exercise that classifies a fixed representation action and a
  parameter-changing learning action.
- Use text representation to create Video 2's question about stable character
  numbers.
```

- [ ] **Step 2: Verify complete structure, scope, and roadmap payoff**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re

text = Path("course/video_1_script_4.md").read_text(encoding="utf-8")
headings = [line for line in text.splitlines() if line.startswith("## ")]
expected = [
    "## 00:00 The Result and the Question",
    "## 00:50 The Whole Journey in One Map",
    "## 03:00 Close the Boxes We Have Not Opened",
    "## 04:00 Why Text Needs a Numerical Form",
    "## 06:30 Representation Is Not Learning",
    "## 08:00 Apply the Distinction to the Repository",
    "## 10:30 Predict, Run, and Explain",
    "## 13:00 Return to the Whole Map",
]
assert headings == expected, headings
words = len(text.split())
assert 1900 <= words <= 2200, words
for required in [
    "token ID does not become an embedding",
    "not represented by an embedding",
    "closed update method",
    "Text representation changes text into a numerical form that software can store and process.",
    "Representation changes the form of the data.",
    "Learning changes adjustable model parameters using examples and measured error.",
    "These character numbers are not token IDs or embeddings.",
    "written character",
    "stable code point",
    "stored UTF-8 bytes",
    "prepared numerical data",
]:
    assert required in text, required
for prohibited in [
    "tensor",
    "softmax",
    "gradient",
    "backpropagation",
    "optimizer",
    "cross-entropy",
    "probability",
]:
    assert not re.search(rf"\b{prohibited}s?\b", text, re.IGNORECASE), prohibited
print(f"PASS: complete roadmap-first script has eight headings and {words} words")
PY
```

Expected: one `PASS` line with a word count from `1900` through `2200`.

- [ ] **Step 3: Verify exact repository and lab evidence**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import subprocess

script = Path("course/video_1_script_4.md").read_text(encoding="utf-8")
normalize_source = Path("matgpt/data/normalize.py").read_text(encoding="utf-8")
start = normalize_source.index("def normalize_text")
assert normalize_source[start:].strip() in script
for exact_line in [
    "normalized = normalize_text(text)",
    '"text": normalized,',
    '"num_chars": len(normalized),',
]:
    assert exact_line in script, exact_line

lab_path = Path("course/videos/001-computer-learning-from-text/lab.py")
assert lab_path.read_text(encoding="utf-8").strip() in script
assert "python course/videos/001-computer-learning-from-text/lab.py" in script
result = subprocess.run(["python", str(lab_path)], check=True, capture_output=True, text=True)
assert result.stdout.strip() in script
assert "①" in script
assert "not lossless" in script.lower() or "non-lossless" in script.lower()
assert "character count can change" in script.lower()
print("PASS: normalization, preparation, lab source, command, output, and policy boundary are exact")
PY
```

Expected: `PASS: normalization, preparation, lab source, command, output, and policy boundary are exact`.

- [ ] **Step 4: Run the focused existing course contract**

Run:

```bash
uv run pytest tests/test_course_structure.py -v
```

Expected: all focused course-structure tests pass.

- [ ] **Step 5: Commit only the complete narration**

Run:

```bash
git add course/video_1_script_4.md
git diff --cached --name-status
git diff --cached --check
git commit -m "docs: complete roadmap-first video one script"
```

Expected staged name list before commit:

```text
M  course/video_1_script_4.md
```

---

### Task 4: Perform Conversational, Cognitive-Load, And Final Verification

**Files:**

- Modify if required by review: `course/video_1_script_4.md`
- Verify unchanged in the primary checkout: `script_video1_draft.md`
- Verify unchanged in the primary checkout: `course/videos/001-computer-learning-from-text/script.md`
- Verify unchanged in the primary checkout: `course/video_1_improved_script.md`
- Verify unchanged: `course/video_1_script_2.md`
- Verify unchanged: `course/video_1_script_3.md`

**Interfaces:**

- Consumes: the complete Script 4 and all approved teaching, technical, and preservation constraints.
- Produces: a read-aloud-ready, technically exact narration with fresh test evidence and a protected-path audit suitable for local integration.

- [ ] **Step 1: Scan for premature mechanism teaching and roadmap overuse**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re

text = Path("course/video_1_script_4.md").read_text(encoding="utf-8")
for prohibited in [
    "tensor",
    "softmax",
    "gradient",
    "backpropagation",
    "optimizer",
    "cross-entropy",
    "probability",
]:
    assert not re.search(rf"\b{prohibited}s?\b", text, re.IGNORECASE), prohibited
counts = {
    "token ID": len(re.findall(r"\btoken IDs?\b", text, re.IGNORECASE)),
    "embedding": len(re.findall(r"\bembeddings?\b", text, re.IGNORECASE)),
    "roadmap": len(re.findall(r"\broadmaps?\b", text, re.IGNORECASE)),
}
assert counts["token ID"] <= 12, counts
assert counts["embedding"] <= 12, counts
assert counts["roadmap"] <= 12, counts
assert "token ID does not become an embedding" in text
assert "not represented by an embedding" in text
print(f"PASS: future mechanisms stay closed and signpost counts remain bounded: {counts}")
PY
```

Expected: one `PASS` line; no later mechanism term appears and no signpost is repeated more than twelve times across narration, code, headings, and recap.

- [ ] **Step 2: Identify spoken sentences requiring a read-aloud decision**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re

text = Path("course/video_1_script_4.md").read_text(encoding="utf-8")
spoken_lines = []
in_fence = False
for line in text.splitlines():
    if line.startswith("```"):
        in_fence = not in_fence
        continue
    if in_fence or not line or line.startswith(("#", "[")):
        continue
    spoken_lines.append(line)
sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", " ".join(spoken_lines)) if part.strip()]
long = [(len(sentence.split()), sentence) for sentence in sentences if len(sentence.split()) > 40]
for count, sentence in long:
    print(f"{count}: {sentence}")
assert not long, f"{len(long)} spoken sentences exceed 40 words"
print(f"PASS: {len(sentences)} spoken sentences are at most 40 words")
PY
```

Expected on the polished narration: no spoken sentence exceeds 40 words.

- [ ] **Step 3: Conduct the deliberate read-aloud and teaching-rubric pass**

Read every spoken paragraph aloud and use `apply_patch` only for evidence-driven revisions:

```text
- Join runs of isolated short statements when a connective sentence makes their
  causal relationship clearer.
- Split any sentence that loses its subject or requires more than one breath.
- Keep each roadmap signpost to one ordinary-language job and one technical
  label; remove any sentence that starts teaching its internals.
- Ensure the opening map creates the closed-box question, the representation
  distinction creates the repository question, and the lab result creates the
  final return to the map.
- Keep `text representation` closed as a stable building block after it is
  earned.
- Preserve all exact code, commands, outputs, numerical values, policy caveats,
  corrected ID/embedding relationship, and reusable mental-model sentences.
- Ensure Script 4 still reads as roadmap-first rather than Script 3 with an
  extended introduction.
```

- [ ] **Step 4: Run the complete fresh Script 4 contract**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re
import subprocess

path = Path("course/video_1_script_4.md")
text = path.read_text(encoding="utf-8")
headings = [line for line in text.splitlines() if line.startswith("## ")]
expected = [
    "## 00:00 The Result and the Question",
    "## 00:50 The Whole Journey in One Map",
    "## 03:00 Close the Boxes We Have Not Opened",
    "## 04:00 Why Text Needs a Numerical Form",
    "## 06:30 Representation Is Not Learning",
    "## 08:00 Apply the Distinction to the Repository",
    "## 10:30 Predict, Run, and Explain",
    "## 13:00 Return to the Whole Map",
]
assert headings == expected
words = len(text.split())
assert 1900 <= words <= 2200
for exact in [
    "token ID does not become an embedding",
    "not represented by an embedding",
    "closed update method",
    "Text representation changes text into a numerical form that software can store and process.",
    "Representation changes the form of the data.",
    "Learning changes adjustable model parameters using examples and measured error.",
    "These character numbers are not token IDs or embeddings.",
]:
    assert exact in text, exact
for prohibited in [
    "tensor",
    "softmax",
    "gradient",
    "backpropagation",
    "optimizer",
    "cross-entropy",
    "probability",
]:
    assert not re.search(rf"\b{prohibited}s?\b", text, re.IGNORECASE), prohibited

normalize_source = Path("matgpt/data/normalize.py").read_text(encoding="utf-8")
assert normalize_source[normalize_source.index("def normalize_text"):].strip() in text
for exact_line in [
    "normalized = normalize_text(text)",
    '"text": normalized,',
    '"num_chars": len(normalized),',
]:
    assert exact_line in text
lab_path = Path("course/videos/001-computer-learning-from-text/lab.py")
assert lab_path.read_text(encoding="utf-8").strip() in text
result = subprocess.run(["python", str(lab_path)], check=True, capture_output=True, text=True)
assert result.stdout.strip() in text
print(f"PASS: complete Script 4 contract with {words} words and eight sections")
PY
```

Expected: one `PASS` line with a word count from `1900` through `2200`.

- [ ] **Step 5: Run focused and full repository tests**

Run the narrow suite first:

```bash
uv run pytest tests/test_course_structure.py -v
```

Then run the complete suite:

```bash
uv run pytest -v
```

Expected: both commands exit `0`. Do not weaken or modify tests if a failure appears; identify the cause before changing narration.

- [ ] **Step 6: Commit a final polish only when review changed the narration**

If Step 3 changed Script 4, run:

```bash
git add course/video_1_script_4.md
git diff --cached --name-status
git diff --cached --check
git commit -m "docs: polish roadmap-first video one narration"
```

Expected staged name list:

```text
M  course/video_1_script_4.md
```

If Step 3 required no edit, do not create an empty commit.

- [ ] **Step 7: Verify protected primary files and committed scope**

Run from the isolated worktree:

```bash
shasum -a 256 \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/script_video1_draft.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/script.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_improved_script.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_script_2.md \
  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_script_3.md
git diff --check
git status --short
git diff --name-only main...HEAD
```

Expected protected hashes remain:

```text
732560ab1c9fbaa9ad98a508bf0148d72682b85bdc04ad4eb49cdaa57725a10f  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/script_video1_draft.md
33bd5437b98f329b4755591b091b8b5be890be45dd8855d16e74c48426e446fe  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/videos/001-computer-learning-from-text/script.md
2d367e1885b8f097466e24dbe115c075aad581580975bb58a91a7320c21f0de0  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_improved_script.md
89d5b7e82307780f2c4a2bcb55c81d72cd4c2b5a2f36a2064d94c143fd7dba26  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_script_2.md
2a18abc729ae7cf61080ef9fbb8bbe71d487a794149f2b11a74d16d55d7821df  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_script_3.md
```

Expected isolated-worktree status: clean.

Expected committed feature path:

```text
course/video_1_script_4.md
```

No protected script, source, test, `.playwright-mcp/`, or media path may appear in the feature commit range.
