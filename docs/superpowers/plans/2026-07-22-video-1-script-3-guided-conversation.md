# Video 1 Script 3 Guided-Conversation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a verified third Video 1 narration that preserves the existing lesson and lab while using an oriented, conversational, concept-led teaching flow derived from the approved source analysis.

**Architecture:** Build one standalone Markdown script in two reviewable increments. The first increment establishes the learner contract, text representation, and the representation-learning distinction; the second spends those building blocks on the repository walkthrough, mini-lab, misconceptions, and transfer. A final narration pass verifies spoken flow and source independence before repository-wide checks verify factual accuracy and preservation.

**Tech Stack:** Markdown, Python 3 standard library, pytest, existing repository course artifacts.

## Global Constraints

- Treat `docs/superpowers/specs/2026-07-22-video-1-script-3-guided-conversation-design.md` as the approved source of truth.
- Create only `course/video_1_script_3.md` as the narration deliverable.
- Planning documentation may be added under `docs/superpowers/`; do not create a new persistent test file.
- Preserve the approximately fourteen-minute scope and exactly eight timestamped sections.
- Use **text representation** as the single stable building-block name; do not introduce `numeric text representation` as a second label.
- Preserve the verified learning objective, repository behavior, lab source, invocation command, five-line output, NFKC warning, and deferred-vocabulary boundary.
- Keep Unicode code points distinct from UTF-8 bytes and text representation distinct from learning.
- Preserve exactly three high-value prediction moments: stable `ord("A")`, matching `Cat` lists, and classification of repository normalization.
- Keep terminology pauses short, operational, and attached to observable behavior.
- Write connected conversational paragraphs, not a list of sentences or a series of quiz prompts.
- Borrow the source's general instructional architecture without copying its wording, signature labels, slogans, or mannerisms.
- Do not create, modify, stage, or commit media, video, audio, render, font, or Adobe project files.
- Do not modify, stage, or commit `course/videos/001-computer-learning-from-text/script.md`.
- Do not modify, stage, or commit the current user-owned changes in `course/video_1_script_2.md`, `course/video_1_script_2_lab.md`, `course/video_1_script_2_lab.py`, or `tests/test_video_001_script_2.py`.
- Do not modify, stage, or commit the primary-checkout user draft at `/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_improved_script.md`.
- Stage explicit paths only and inspect the staged name list before every commit.

---

## File Map

- `docs/superpowers/specs/2026-07-22-video-1-script-3-guided-conversation-design.md` is the approved style assessment, narrative contract, technical boundary, and acceptance source.
- `docs/superpowers/plans/2026-07-22-video-1-script-3-guided-conversation.md` is this execution plan.
- `course/video_1_script_3.md` will be the only new narration deliverable.
- `course/videos/001-computer-learning-from-text/script.md` is the canonical narration and must remain unchanged.
- `course/video_1_script_2.md` is the alternate book-method narration and currently contains user-owned edits that must remain unchanged and unstaged.
- `course/videos/001-computer-learning-from-text/lesson.md` is the canonical conceptual reference.
- `course/videos/001-computer-learning-from-text/evidence.md` separates source facts, observed behavior, analogies, and deferred claims.
- `course/videos/001-computer-learning-from-text/lab.py` is the exact executable proof that Script 3 must embed and explain.
- `matgpt/data/normalize.py` is the authoritative normalization sequence.
- `matgpt/data/prepare.py` is the authoritative normalized-text storage and `num_chars` source.
- `tests/test_course_structure.py` is the focused existing course contract.

---

### Task 1: Build The Guided Conceptual Core

**Files:**

- Create: `course/video_1_script_3.md`
- Read: `docs/superpowers/specs/2026-07-22-video-1-script-3-guided-conversation-design.md`
- Read: `course/videos/001-computer-learning-from-text/lesson.md`
- Read: `course/videos/001-computer-learning-from-text/evidence.md`
- Preserve: `course/videos/001-computer-learning-from-text/script.md`
- Preserve: `course/video_1_script_2.md`

**Interfaces:**

- Consumes: the approved learner contract, narrative spine, canonical terminology, and verified `A`/`Cat` facts.
- Produces: the title and first four timestamped sections, ending with the stable representation-learning distinction that Task 2 will apply.

- [ ] **Step 1: Record the preservation baseline**

Run:

```bash
git status --short
shasum -a 256 course/videos/001-computer-learning-from-text/script.md course/video_1_script_2.md course/video_1_script_2_lab.md course/video_1_script_2_lab.py tests/test_video_001_script_2.py /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_improved_script.md
test ! -e course/video_1_script_3.md
```

Expected hashes:

```text
c8127b5a9e66a2d92d192d7e983633f511e1f0d95d09fed38991307cae54939f  course/videos/001-computer-learning-from-text/script.md
92ee6339e7514496e3d550217d4f69568fb948f0def04e62da7e1774cf0af8d6  course/video_1_script_2.md
aba5b93178f6909da2a079c5c1eb7bfa8b0c6d4c48753ddeca7fd13bdc479185  course/video_1_script_2_lab.md
a2e345f481ee2e9748995dc9da580788092379c067d909754c8b007bd4c682bc  course/video_1_script_2_lab.py
62280a23dfb16f5be848cc9a2e6f3e02609af88699ea8b4c15d3dc871341abcb  tests/test_video_001_script_2.py
ead2f3a346c93e9229071ad2dca2463040425f3b7cdb7f3587a8df36fdbcb881  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_improved_script.md
```

Expected status: the modified Script 2 and its three untracked companion files are visible; the target-file check exits `0`. Stop if any protected hash differs before Task 1 begins, report the new state, and do not revert it.

- [ ] **Step 2: Run the structural check before the target exists**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

path = Path("course/video_1_script_3.md")
text = path.read_text(encoding="utf-8")
print(text)
PY
```

Expected: fail with `FileNotFoundError` for `course/video_1_script_3.md`, proving the new artifact does not already satisfy the contract.

- [ ] **Step 3: Create the first four sections**

Use `apply_patch` to create `course/video_1_script_3.md` with exactly this title and heading order:

```markdown
# Video 1 — Script 3: What Does It Mean for a Computer to Learn From Text?

## 00:00 The Question Under the Text Box
## 00:45 One Character, One Stable Number
## 02:00 From One Character to Text Representation
## 04:00 What Representation Still Cannot Explain
```

Write connected narration with this exact conceptual load:

```text
00:00
- Begin with familiar coherent AI results: rewriting an email, improving an
  essay, or suggesting code.
- Separate having used those results from knowing their internal mechanism.
- Expose the surface puzzle: the learner sees meaningful text while the model's
  calculations require numerical input.
- Scope the lesson to the first bridge beneath the text box, not every mechanism
  behind generated language.
- State the testable outcome: trace text into a numerical form and explain why
  that conversion is not yet learning.
- Carry the puzzle into one small character rather than introducing a glossary.

00:45
- Put `A` on screen and ask the first genuine prediction: does Python invent a
  number on each run or follow a stable standard?
- Reveal `ord("A") == 65` only after the prediction.
- Explain the observable behavior, then introduce one operational term at a
  time: character, Unicode, and code point.
- Correct identifier versus meaning immediately. `65` identifies the character
  under the standard; it does not contain every human meaning of `A`.
- Use the stable single-character mechanism to ask what happens with `Cat`.

02:00
- Trace `C -> 67`, `a -> 97`, and `t -> 116` completely.
- Introduce byte and UTF-8 only after the code-point sequence is understood.
- Ask the second genuine prediction before revealing the UTF-8 list.
- Explain that both lists match for ASCII-range `Cat` because UTF-8 stores each
  of these characters as one byte with the same value.
- State immediately that the match is not universal; other characters can use
  multiple UTF-8 bytes.
- Name the earned building block **text representation** and define it as
  changing text into a numerical form software can store and process.
- Use that building block to ask what, if anything, learned during conversion.

04:00
- Compare what changed with what stayed fixed when `Cat` became numbers.
- Show that the data form changed while no prediction was compared with an
  outcome and no adjustable value changed.
- Introduce the smallest learning behavior before its terminology: numerical
  input -> prediction -> measured error -> change to adjustable internal
  numbers -> later prediction.
- Use seven mistakes becoming five only as a small intuition for improvement.
- State that the count is not the repository's loss calculation and does not
  prove performance on unseen examples; mention separate examples briefly.
- After the mechanism is visible, name model, parameters, and learning with
  operational definitions.
- End with these exact reusable sentences:
  `Representation changes the form of the data.`
  `Learning changes adjustable model parameters using examples and measured error.`
- Carry the distinction into the question that opens Task 2: which side does
  repository normalization belong to?
```

Keep stage directions and code outside spoken paragraphs. Do not use an analogy in these sections because the inspectable `A` and `Cat` cases are already simpler.

- [ ] **Step 4: Verify the conceptual-core contract**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re

path = Path("course/video_1_script_3.md")
text = path.read_text(encoding="utf-8")
headings = [line for line in text.splitlines() if line.startswith("## ")]
expected = [
    "## 00:00 The Question Under the Text Box",
    "## 00:45 One Character, One Stable Number",
    "## 02:00 From One Character to Text Representation",
    "## 04:00 What Representation Still Cannot Explain",
]
assert headings == expected, headings
words = len(text.split())
assert 900 <= words <= 1200, words
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
    "text representation",
    "measured error",
    "parameters",
    "Representation changes the form of the data.",
    "Learning changes adjustable model parameters using examples and measured error.",
]:
    assert required in text, required
assert "numeric text representation" not in text.lower()
for prohibited in ["token", "tensor", "logit", "gradient", "attention", "embedding"]:
    assert not re.search(rf"\b{prohibited}s?\b", text, re.IGNORECASE), prohibited
print(f"PASS: conceptual core has four headings and {words} words")
PY
```

Expected: `PASS` with four exact headings and a word count from `900` through `1200`.

- [ ] **Step 5: Commit the conceptual core only**

Run:

```bash
git add course/video_1_script_3.md
git diff --cached --name-status
git diff --cached --check
git commit -m "docs: draft guided-conversation video one core"
```

Expected staged name list before commit:

```text
A  course/video_1_script_3.md
```

---

### Task 2: Apply The Mental Model To The Repository And Lab

**Files:**

- Modify: `course/video_1_script_3.md`
- Read: `matgpt/data/normalize.py`
- Read: `matgpt/data/prepare.py`
- Read: `course/videos/001-computer-learning-from-text/lab.py`
- Read: `course/videos/001-computer-learning-from-text/evidence.md`

**Interfaces:**

- Consumes: the exact representation-learning distinction produced by Task 1 and the authoritative repository/lab sources.
- Produces: a complete eight-section narration, exact repository trace, exact mini-lab, misconception repair, recap, and Video 2 transfer.

- [ ] **Step 1: Append the final four sections**

Use `apply_patch` to append exactly these headings:

```markdown
## 06:00 Apply the Distinction to the Repository
## 09:00 Predict, Run, Explain
## 12:00 Two Questions That Keep the Model Honest
## 13:00 Rebuild the Complete Chain
```

Write connected narration with this exact conceptual load:

```text
06:00
- Open with the third genuine prediction: does `normalize_text` change data,
  model parameters, or both?
- Show the complete current `normalize_text` function from
  `matgpt/data/normalize.py` as an exact code excerpt.
- Trace the actual order: `str(text)` -> NFKC -> newline standardization ->
  selected control-character removal -> per-line trailing-whitespace removal ->
  outer stripping -> blank-line-run limiting -> return.
- Explain that `text: str` and `-> str` communicate intended types but Python
  does not enforce them at runtime.
- Show the exact relevant `prepare.py` lines for `normalized =
  normalize_text(text)`, `"text": normalized`, and `"num_chars":
  len(normalized)`.
- State the NFKC policy boundary at the point of use: it is deliberate and
  non-lossless; `①` can become `1`, a source distinction can collapse, and
  character count can change.
- Answer the prediction with the established building block: data changed and
  was stored; no model parameter changed, so this is preparation on the text-
  representation side.
- Carry that classification into the existing lab as a smaller observable test.

09:00
- Embed the current `lab.py` source exactly and preserve the exact repository-
  root command `python course/videos/001-computer-learning-from-text/lab.py`.
- Reuse the earlier `Cat` prediction rather than asking a fourth formal
  prediction question.
- Show the exact five-line observed output.
- Explain each line: human-readable string, `ord` code points,
  `encode("utf-8")` bytes, `list` displaying byte values as integers, and the
  representation-learning boundary.
- Change only `text = "Cat"` to `text = "A"`, ask the learner to apply the
  already-built rule, and state that both lists should be `[65]`.
- Explain why the changed result follows from the same stable standard and then
  instruct the learner to restore `Cat`.

12:00
- Resolve identifier versus meaning conversationally with `A` used in two human
  contexts while code point `65` remains fixed.
- Resolve representation versus learning by asking what adjustable value changed
  after repeated calls to `ord("A")`; answer that none changed through measured
  error.
- Avoid a detached checklist. Use the first answer to set up the second and then
  return to the lesson's central puzzle.

13:00
- Reconstruct the complete chain in ordinary language from meaningful text as a
  human experience through character identifiers, UTF-8 storage, numerical
  model input, prediction, measured error, parameter change, and possible later
  improvement.
- Repeat the two exact building-block sentences from Task 1 once, not several
  times.
- Give a transfer exercise using `A`: explain why `65` is stable and identify
  the evidence required before claiming learning.
- Use text representation immediately to create Video 2's question about how
  stable character numbers are assigned.
- End with a non-spoken deferred-vocabulary boundary containing token, tensor,
  logit, gradient, attention, and embedding.
```

- [ ] **Step 2: Verify the complete structural and vocabulary contract**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re

path = Path("course/video_1_script_3.md")
text = path.read_text(encoding="utf-8")
headings = [line for line in text.splitlines() if line.startswith("## ")]
expected = [
    "## 00:00 The Question Under the Text Box",
    "## 00:45 One Character, One Stable Number",
    "## 02:00 From One Character to Text Representation",
    "## 04:00 What Representation Still Cannot Explain",
    "## 06:00 Apply the Distinction to the Repository",
    "## 09:00 Predict, Run, Explain",
    "## 12:00 Two Questions That Keep the Model Honest",
    "## 13:00 Rebuild the Complete Chain",
]
assert headings == expected, headings
words = len(text.split())
assert 1900 <= words <= 2100, words
assert text.count("Representation changes the form of the data.") == 2
assert text.count("Learning changes adjustable model parameters using examples and measured error.") == 2
assert "numeric text representation" not in text.lower()
boundary = "**Deferred vocabulary boundary:**"
assert boundary in text
spoken, deferred = text.split(boundary, 1)
for prohibited in ["token", "tensor", "logit", "gradient", "attention", "embedding"]:
    assert not re.search(rf"\b{prohibited}s?\b", spoken, re.IGNORECASE), prohibited
    assert re.search(rf"\b{prohibited}s?\b", deferred, re.IGNORECASE), prohibited
print(f"PASS: complete script has eight headings and {words} words")
PY
```

Expected: `PASS` with eight exact headings and a word count from `1900` through `2100`.

- [ ] **Step 3: Verify the exact repository and lab evidence**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import subprocess

script = Path("course/video_1_script_3.md").read_text(encoding="utf-8")
normalize_source = Path("matgpt/data/normalize.py").read_text(encoding="utf-8")
start = normalize_source.index("def normalize_text")
normalize_function = normalize_source[start:].strip()
assert normalize_function in script

for exact_line in [
    "normalized = normalize_text(text)",
    '"text": normalized,',
    '"num_chars": len(normalized),',
]:
    assert exact_line in script, exact_line

lab_path = Path("course/videos/001-computer-learning-from-text/lab.py")
lab_source = lab_path.read_text(encoding="utf-8").strip()
assert lab_source in script
command = "python course/videos/001-computer-learning-from-text/lab.py"
assert command in script
result = subprocess.run(
    ["python", str(lab_path)],
    check=True,
    capture_output=True,
    text=True,
)
observed = result.stdout.strip()
assert observed in script
assert "①" in script
assert "not lossless" in script.lower() or "non-lossless" in script.lower()
assert "character count can change" in script.lower()
print("PASS: repository trace, lab source, command, output, and NFKC boundary are exact")
PY
```

Expected: `PASS: repository trace, lab source, command, output, and NFKC boundary are exact`.

- [ ] **Step 4: Run the focused existing course contract**

Run:

```bash
uv run pytest tests/test_course_structure.py -v
```

Expected: all focused course-structure tests pass. This confirms that adding a standalone alternate did not change the canonical produced-video contract.

- [ ] **Step 5: Commit the complete narration only**

Run:

```bash
git add course/video_1_script_3.md
git diff --cached --name-status
git diff --cached --check
git commit -m "docs: complete guided-conversation video one script"
```

Expected staged name list before commit:

```text
M  course/video_1_script_3.md
```

---

### Task 3: Perform The Conversational And Source-Independence Pass

**Files:**

- Modify: `course/video_1_script_3.md`
- Read: `docs/superpowers/specs/2026-07-22-video-1-script-3-guided-conversation-design.md`
- Compare: `course/video_1_script_2.md`

**Interfaces:**

- Consumes: the complete, technically verified narration from Task 2.
- Produces: a read-aloud-ready Script 3 whose orientation, terminology pauses, callbacks, and transitions are observably distinct from Script 2 without imitating the source instructor.

- [ ] **Step 1: Scan for author-specific phrasing and excessive prediction prompts**

Run:

```bash
rg -n -i "big word alert|break glass|don't imitate|do not imitate|understanding the weird parts|Tony Alicea" course/video_1_script_3.md
python3 - <<'PY'
from pathlib import Path
import re

text = Path("course/video_1_script_3.md").read_text(encoding="utf-8")
count = len(re.findall(r"\bpredict\b", text, re.IGNORECASE))
assert 3 <= count <= 6, count
print(f"PASS: {count} uses of predict support three deliberate prediction moments")
PY
```

Expected: `rg` returns no matches; the prediction check passes with three to six uses of the word because one prediction moment can require both a prompt and a callback.

- [ ] **Step 2: Identify sentences that need a read-aloud decision**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re

text = Path("course/video_1_script_3.md").read_text(encoding="utf-8")
spoken_lines = []
in_fence = False
for line in text.splitlines():
    if line.startswith("```"):
        in_fence = not in_fence
        continue
    if in_fence or not line or line.startswith(("#", "[", "**Deferred")):
        continue
    spoken_lines.append(line)
spoken = " ".join(spoken_lines)
sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", spoken) if part.strip()]
long = [(len(sentence.split()), sentence) for sentence in sentences if len(sentence.split()) > 40]
for count, sentence in long:
    print(f"{count}: {sentence}")
assert not long, f"{len(long)} spoken sentences exceed 40 words"
print(f"PASS: {len(sentences)} spoken sentences are at most 40 words")
PY
```

Expected on the polished narration: `PASS` with no spoken sentence over 40 words. Treat code, headings, stage directions, and the deferred note as non-spoken material.

- [ ] **Step 3: Conduct the deliberate read-aloud revision**

Read every spoken paragraph aloud and use `apply_patch` to make only these evidence-driven revisions:

```text
- Split any sentence that loses its subject or requires more than one breath.
- Join runs of isolated short claims when one connective sentence makes their
  causal relationship clearer.
- Ensure every terminology pause returns to the central text-versus-numbers
  question in the same paragraph or the next paragraph.
- Ensure the end of each section spends its conclusion on the opening question
  of the following section.
- Preserve only the three approved prediction moments; turn decorative questions
  into direct conversational transitions.
- Keep `text representation` closed as a stable building block after it is named.
- Preserve all exact code, command, output, numerical values, caveats, and the two
  exact building-block sentences.
```

Do not make the prose more source-like. The target is the approved functional pattern—orientation, operational vocabulary, causal walkthrough, callback—not recognizable author phrasing.

- [ ] **Step 4: Re-run the source-independence and sentence checks**

Run:

```bash
rg -n -i "big word alert|break glass|don't imitate|do not imitate|understanding the weird parts|Tony Alicea" course/video_1_script_3.md
python3 - <<'PY'
from pathlib import Path
import re

text = Path("course/video_1_script_3.md").read_text(encoding="utf-8")
assert 1900 <= len(text.split()) <= 2100
assert len(re.findall(r"\bpredict\b", text, re.IGNORECASE)) in range(3, 7)
assert "numeric text representation" not in text.lower()
spoken_lines = []
in_fence = False
for line in text.splitlines():
    if line.startswith("```"):
        in_fence = not in_fence
        continue
    if in_fence or not line or line.startswith(("#", "[", "**Deferred")):
        continue
    spoken_lines.append(line)
sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", " ".join(spoken_lines)) if part.strip()]
assert all(len(sentence.split()) <= 40 for sentence in sentences)
print("PASS: narration length, prediction count, stable name, and spoken sentence rhythm")
PY
```

Expected: no source-phrase matches and one `PASS` line.

- [ ] **Step 5: Commit the narration polish only**

Run:

```bash
git add course/video_1_script_3.md
git diff --cached --name-status
git diff --cached --check
git commit -m "docs: polish guided-conversation video one narration"
```

Expected staged name list before commit:

```text
M  course/video_1_script_3.md
```

If the read-aloud pass requires no edit, do not create an empty commit; record the clean review result in the final verification report instead.

---

### Task 4: Final Verification And Preservation Audit

**Files:**

- Verify: `course/video_1_script_3.md`
- Verify unchanged: `course/videos/001-computer-learning-from-text/script.md`
- Verify unchanged: `course/video_1_script_2.md`
- Verify unchanged: `course/video_1_script_2_lab.md`
- Verify unchanged: `course/video_1_script_2_lab.py`
- Verify unchanged: `tests/test_video_001_script_2.py`
- Verify unchanged: `/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_improved_script.md`

**Interfaces:**

- Consumes: the reviewed Script 3 and all protected-path baseline hashes.
- Produces: evidence that Script 3 meets the teaching and technical contracts, the tracked test suite passes, and no protected user or media artifact changed.

- [ ] **Step 1: Run the complete narration contract**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re
import subprocess

path = Path("course/video_1_script_3.md")
text = path.read_text(encoding="utf-8")
headings = [line for line in text.splitlines() if line.startswith("## ")]
expected = [
    "## 00:00 The Question Under the Text Box",
    "## 00:45 One Character, One Stable Number",
    "## 02:00 From One Character to Text Representation",
    "## 04:00 What Representation Still Cannot Explain",
    "## 06:00 Apply the Distinction to the Repository",
    "## 09:00 Predict, Run, Explain",
    "## 12:00 Two Questions That Keep the Model Honest",
    "## 13:00 Rebuild the Complete Chain",
]
assert headings == expected
assert 1900 <= len(text.split()) <= 2100
assert text.count("Representation changes the form of the data.") == 2
assert text.count("Learning changes adjustable model parameters using examples and measured error.") == 2
assert "numeric text representation" not in text.lower()

boundary = "**Deferred vocabulary boundary:**"
spoken, deferred = text.split(boundary, 1)
for term in ["token", "tensor", "logit", "gradient", "attention", "embedding"]:
    assert not re.search(rf"\b{term}s?\b", spoken, re.IGNORECASE)
    assert re.search(rf"\b{term}s?\b", deferred, re.IGNORECASE)

normalize_source = Path("matgpt/data/normalize.py").read_text(encoding="utf-8")
start = normalize_source.index("def normalize_text")
assert normalize_source[start:].strip() in text
for exact_line in [
    "normalized = normalize_text(text)",
    '"text": normalized,',
    '"num_chars": len(normalized),',
]:
    assert exact_line in text

lab_path = Path("course/videos/001-computer-learning-from-text/lab.py")
assert lab_path.read_text(encoding="utf-8").strip() in text
assert "python course/videos/001-computer-learning-from-text/lab.py" in text
result = subprocess.run(["python", str(lab_path)], check=True, capture_output=True, text=True)
assert result.stdout.strip() in text
print(f"PASS: complete Script 3 contract with {len(text.split())} words")
PY
```

Expected: one `PASS` line with a word count from `1900` through `2100`.

- [ ] **Step 2: Run focused and full repository tests**

Run the narrowest test first:

```bash
uv run pytest tests/test_course_structure.py -v
```

Then run the complete repository suite:

```bash
uv run pytest -v
```

Expected: both commands exit `0`. Do not weaken or edit tests if a failure appears; identify whether it comes from Script 3, existing tracked state, or one of the protected user-owned files before taking any action.

- [ ] **Step 3: Verify protected hashes and the absence of media changes**

Run:

```bash
shasum -a 256 course/videos/001-computer-learning-from-text/script.md course/video_1_script_2.md course/video_1_script_2_lab.md course/video_1_script_2_lab.py tests/test_video_001_script_2.py /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_improved_script.md
git diff --check
git diff --name-only 7af23bb..HEAD
git status --short
```

Expected hashes remain:

```text
c8127b5a9e66a2d92d192d7e983633f511e1f0d95d09fed38991307cae54939f  course/videos/001-computer-learning-from-text/script.md
92ee6339e7514496e3d550217d4f69568fb948f0def04e62da7e1774cf0af8d6  course/video_1_script_2.md
aba5b93178f6909da2a079c5c1eb7bfa8b0c6d4c48753ddeca7fd13bdc479185  course/video_1_script_2_lab.md
a2e345f481ee2e9748995dc9da580788092379c067d909754c8b007bd4c682bc  course/video_1_script_2_lab.py
62280a23dfb16f5be848cc9a2e6f3e02609af88699ea8b4c15d3dc871341abcb  tests/test_video_001_script_2.py
ead2f3a346c93e9229071ad2dca2463040425f3b7cdb7f3587a8df36fdbcb881  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_improved_script.md
```

Expected committed changed paths after `7af23bb`:

```text
course/video_1_script_3.md
docs/superpowers/plans/2026-07-22-video-1-script-3-guided-conversation.md
```

Expected status retains the pre-existing user-owned Script 2 modification and its three untracked companion files. No media path may appear in the committed-path list or as a new Script 3 change.

- [ ] **Step 4: Inspect the final commit range**

Run:

```bash
git log --oneline 7af23bb..HEAD
git diff --stat 7af23bb..HEAD
git diff -- course/video_1_script_3.md
```

Expected: the plan and Script 3 narration commits are present; the target has no uncommitted diff; no protected source, canonical script, Script 2 artifact, test, or media file appears in the commit range.
