# Video 1 Script 2 Book-Method Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a verified alternate Video 1 narration that follows the
approved causal-ladder teaching design derived from *But How Do It Know?*
without changing either existing script.

**Architecture:** Keep the alternate outside the strict produced-video
directory as a standalone Markdown narration. Build numeric text representation
from one fixed character mapping, use that completed abstraction to construct
the smallest accurate account of learning, and apply the resulting distinction
to the repository walkthrough and existing mini-lab.

**Tech Stack:** Markdown, Python 3 standard library, pytest, existing repository
course artifacts.

## Global Constraints

- Treat
  `docs/superpowers/specs/2026-07-22-video-1-script-2-book-method-design.md`
  as the approved source of truth.
- Create only `course/video_1_script_2.md` as the narration deliverable.
- Do not modify or stage
  `course/videos/001-computer-learning-from-text/script.md`.
- Do not modify or stage the user-owned untracked file
  `course/video_1_improved_script.md`.
- Do not create, modify, stage, or commit media, video, audio, render, or Adobe
  project files.
- Preserve the existing learning objective, repository behavior, lab command,
  lab output, NFKC warning, and deferred-vocabulary boundary.
- Keep Unicode code points distinct from UTF-8 bytes and representation
  distinct from learning.
- Build behavior before terminology, ask for predictions, trace every central
  cause, compress each mechanism, and use it as the next building block.
- Write connected conversational narration, not a list of isolated sentences.
- Do not reproduce or closely imitate the source author's wording.

---

## File Map

- `docs/superpowers/specs/2026-07-22-video-1-script-2-book-method-design.md`
  contains the approved assessment, narrative spine, factual constraints, and
  acceptance criteria.
- `docs/superpowers/plans/2026-07-22-video-1-script-2-book-method.md` is this
  execution plan.
- `course/video_1_script_2.md` will contain the alternate timestamped
  narration, code excerpts, learner predictions, and deferred-vocabulary note.
- `course/videos/001-computer-learning-from-text/lesson.md` is the canonical
  conceptual and factual reference.
- `course/videos/001-computer-learning-from-text/evidence.md` distinguishes
  repository facts, observed behavior, teaching examples, and unverified
  claims.
- `course/videos/001-computer-learning-from-text/lab.py` is the existing
  executable proof used by Script 2.
- `matgpt/data/normalize.py` and `matgpt/data/prepare.py` are the authoritative
  repository sources for the walkthrough.
- `tests/test_course_structure.py` protects the produced-video artifact set and
  canonical course contract.

---

### Task 1: Draft The Causal-Ladder Narration

**Files:**

- Create: `course/video_1_script_2.md`
- Read:
  `docs/superpowers/specs/2026-07-22-video-1-script-2-book-method-design.md`
- Read: `course/videos/001-computer-learning-from-text/lesson.md`
- Read: `course/videos/001-computer-learning-from-text/evidence.md`
- Read: `course/videos/001-computer-learning-from-text/lab.py`
- Read: `matgpt/data/normalize.py`
- Read: `matgpt/data/prepare.py`

**Interfaces:**

- Consumes: the approved narrative spine, canonical technical definitions,
  verified repository behavior, and deterministic lab output.
- Produces: a standalone Markdown narration with the exact eight-section Video
  1 shape and approximately 1,900-2,100 total words.

- [ ] **Step 1: Establish the preservation baseline**

Run:

```bash
git status --short
shasum -a 256 course/videos/001-computer-learning-from-text/script.md
shasum -a 256 /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_improved_script.md
test ! -e course/video_1_script_2.md
```

Expected:

- the isolated worktree is clean before the target is created;
- both hashes are recorded for the final preservation check;
- the target-file check exits `0`.

The second hash deliberately reads the user-owned draft from the primary
checkout because untracked files are not copied into a linked worktree.

- [ ] **Step 2: Create the alternate with the exact section structure**

Use `apply_patch` to create `course/video_1_script_2.md` with exactly these
top-level and second-level headings, in this order:

```markdown
# Video 1 — Script 2: What Does It Mean for a Computer to Learn From Text?

## 00:00 Hook
## 00:45 One Character, One Stable Number
## 02:00 From One Character to Numeric Text
## 04:00 What Representation Still Cannot Do
## 06:00 Repository Walkthrough
## 09:00 Live Mini-Lab
## 12:00 Test the Distinction
## 13:00 Rebuild the Complete Chain
```

The sections must carry this exact conceptual load:

```text
00:00
- Familiar AI uses: coherent email rewriting, essay improvement, or code.
- Apparent mystery: the learner sees meaningful text; the model calculates with
  numerical inputs.
- First small question: how can one character receive a stable number without
  that number containing its meaning?

00:45
- Use A as the single case.
- Ask whether Python invents a number or follows a fixed agreement.
- Reveal ord("A") == 65 after the prediction.
- Explain behavior before naming character, Unicode, and code point.
- Correct identifier versus meaning immediately.

02:00
- Return to Cat and trace C, a, t to 67, 97, 116.
- Introduce byte and UTF-8 only after the code-point sequence is clear.
- Explain the ASCII-range match and its non-universal boundary.
- Name and compress numeric text representation.

04:00
- Ask what changed and what did not change during representation.
- Let that missing capability create the learning question.
- Trace examples -> prediction -> measured error -> parameter change -> later
  prediction.
- Use seven mistakes becoming five as qualified intuition.
- Name model, parameter, and learning after the behavior is clear.
- Compress and name the representation-learning distinction.

06:00
- Use the distinction as the question applied to normalize.py and prepare.py.
- Trace NFKC, newline replacement, line-edge cleanup, outer stripping, return,
  stored text, and num_chars.
- State that annotations communicate intended types without runtime enforcement.
- Preserve the deliberate non-lossless policy warning: ① -> 1 and possible
  character-count change.
- Conclude that data changed while no model parameter changed.

09:00
- Use the canonical lab.py verbatim.
- Ask for both list predictions before the command.
- Preserve the existing command and exact five-line output.
- Explain ord, encode("utf-8"), and list line by line.
- Change only Cat to A, predict [65], rerun, explain fixed behavior, and restore
  Cat.

12:00
- Test identifier versus meaning with a changed agreement/context question.
- Test representation versus learning by asking what adjustable value changed.
- Keep the section conversational rather than presenting detached warnings.

13:00
- Reconstruct the full causal chain in ordinary language.
- Restate the durable representation-learning distinction.
- Give a transfer exercise using A and a parameter-change question.
- Spend numeric text representation on Video 2's question about stable
  character numbers.
```

Keep stage directions and code outside spoken sentences. Use paragraphs of
related thought; do not turn the conceptual-load list above into narrated
bullets.

- [ ] **Step 3: Run the structural content check**

Run:

```bash
python - <<'PY'
from pathlib import Path

path = Path("course/video_1_script_2.md")
text = path.read_text(encoding="utf-8")
headings = [line for line in text.splitlines() if line.startswith("## ")]
expected = [
    "## 00:00 Hook",
    "## 00:45 One Character, One Stable Number",
    "## 02:00 From One Character to Numeric Text",
    "## 04:00 What Representation Still Cannot Do",
    "## 06:00 Repository Walkthrough",
    "## 09:00 Live Mini-Lab",
    "## 12:00 Test the Distinction",
    "## 13:00 Rebuild the Complete Chain",
]
assert headings == expected, headings
words = len(text.split())
assert 1900 <= words <= 2100, words
for required in [
    'ord("A")',
    "67",
    "97",
    "116",
    "Unicode",
    "code point",
    "UTF-8",
    "numeric text representation",
    "parameters",
    "measured error",
    "deliberate cleaning policy",
    "not lossless",
    "①",
    "change character count",
    "Representation changes",
    "Learning changes",
]:
    assert required in text, required
print(f"PASS: headings, required concepts, and {words} words")
PY
```

Expected: one `PASS` line with a word count from `1900` through `2100`.

- [ ] **Step 4: Check prohibited explanatory vocabulary**

Run:

```bash
rg -n -i '\b(token|tensor|logit|gradient|attention|embedding)\b' course/video_1_script_2.md
```

Expected: terms appear only in the final explicit deferred-vocabulary boundary,
not in the spoken explanation. If any term appears earlier, remove it rather
than trying to define it in Video 1.

- [ ] **Step 5: Commit the complete first draft**

Run:

```bash
git add course/video_1_script_2.md
git commit -m "docs: draft book-method video one script"
```

Expected: a commit containing only `course/video_1_script_2.md`.

---

### Task 2: Verify Technical Accuracy And Repository Alignment

**Files:**

- Modify if evidence requires correction: `course/video_1_script_2.md`
- Verify: `course/videos/001-computer-learning-from-text/lab.py`
- Verify: `matgpt/data/normalize.py`
- Verify: `matgpt/data/prepare.py`
- Test: `tests/test_course_structure.py`

**Interfaces:**

- Consumes: the complete first draft from Task 1 and repository-grounded
  evidence.
- Produces: a technically accurate alternate whose examples, code, output, and
  production-directory placement are verified.

- [ ] **Step 1: Compare the walkthrough excerpts with source**

Run:

```bash
sed -n '1,240p' matgpt/data/normalize.py
sed -n '1,260p' matgpt/data/prepare.py
sed -n '/## 06:00 Repository Walkthrough/,/## 09:00 Live Mini-Lab/p' course/video_1_script_2.md
```

Verify every shown statement in order:

```text
normalize_text calls str(text), then NFKC normalization;
CRLF and CR become LF;
trailing whitespace is removed per line;
outer whitespace is stripped;
the simplified excerpt does not claim to show every full-function operation;
make_document_record stores normalized text and len(normalized);
len(normalized) is Python's string length, not a guaranteed count of visible
symbols;
none of these operations updates model parameters.
```

If any statement or code excerpt differs from the source, correct Script 2 with
`apply_patch` before continuing.

- [ ] **Step 2: Run and compare the mini-lab**

Run:

```bash
python course/videos/001-computer-learning-from-text/lab.py
```

Expected exactly:

```text
Human text: Cat
Character numbers: [67, 97, 116]
UTF-8 bytes: [67, 97, 116]
Can the mathematical model use this raw Python string as numeric input? No
Learning begins after text is represented as numbers.
```

Compare that output with the `09:00` section. Correct any discrepancy in the
alternate; do not change the lab.

- [ ] **Step 3: Run the focused course contract**

Run:

```bash
uv run pytest tests/test_course_structure.py -v
```

Expected: all tests in `tests/test_course_structure.py` pass. In particular,
the exact produced-video artifact test must remain green because Script 2 lives
at `course/video_1_script_2.md`.

- [ ] **Step 4: Inspect the factual diff**

Run:

```bash
git diff HEAD^ -- course/video_1_script_2.md
```

Audit each factual claim under one of these labels:

```text
fixed standard or Python behavior;
repository source behavior;
teaching illustration;
bounded inference;
future mechanism explicitly deferred.
```

Remove unsupported universal claims. Preserve immediate qualifications for the
ASCII-range match, NFKC policy, mistake-count illustration, and unseen-example
evaluation.

- [ ] **Step 5: Commit evidence-driven corrections if any exist**

If Script 2 changed during this task, run:

```bash
git add course/video_1_script_2.md
git commit -m "docs: align alternate script with repository evidence"
```

Expected: a commit containing only the corrected alternate. If no correction
was necessary, do not create an empty commit.

---

### Task 3: Perform The Teaching And Read-Aloud Review

**Files:**

- Modify: `course/video_1_script_2.md`
- Verify:
  `docs/superpowers/specs/2026-07-22-video-1-script-2-book-method-design.md`

**Interfaces:**

- Consumes: the technically verified alternate from Task 2.
- Produces: a conversational final narration that satisfies the approved book-
  method teaching contract without sounding like a sentence list.

- [ ] **Step 1: Review every concept against the causal-ladder rubric**

For each of these two concepts—numeric text representation and learning—mark
all eleven checks before accepting the section:

```text
[ ] Begins with a real question.
[ ] Connects to familiar experience or an earned prior concept.
[ ] Exposes a gap in the current explanation.
[ ] Adds only the smallest necessary mechanism.
[ ] Gives the learner a prediction or trace.
[ ] Introduces the technical name after behavior.
[ ] Traces input through operation to output.
[ ] Proves the mechanism with a hand-checkable example.
[ ] Answers the careful beginner's question where it arises.
[ ] Compresses the concept into a reusable mental model.
[ ] Uses that named model to construct or classify the next concept.
```

Revise with `apply_patch` wherever a box cannot be checked from the actual
narration.

- [ ] **Step 2: Run the conversational-flow audit**

Read the spoken paragraphs aloud and inspect each transition. Revise any place
that exhibits one of these exact failures:

```text
three or more consecutive slogan-like one-sentence paragraphs;
a paragraph performing more than one new conceptual job;
a heading followed by an unconnected restatement of the objective;
a rhetorical question answered before a natural prediction pause;
a conclusion repeated without being used in the next question;
a technical term appearing before the behavior it names;
stage direction or code syntax embedded as awkward spoken narration;
repeated "it does not" constructions where positive causal wording is clearer;
patronizing reassurance that tells the learner the idea is easy.
```

The final transitions must form this audible chain:

```text
familiar AI output
-> one character needs a stable number
-> three characters form numeric text
-> numeric form still changes no model parameter
-> learning requires an adjustable mechanism
-> the distinction classifies repository preparation
-> the lab proves the fixed side
-> diagnostic questions test transfer
-> the completed representation block creates Video 2's question
```

- [ ] **Step 3: Re-run the automated content checks**

Run:

```bash
python - <<'PY'
from pathlib import Path

path = Path("course/video_1_script_2.md")
text = path.read_text(encoding="utf-8")
words = len(text.split())
assert 1900 <= words <= 2100, words
assert text.count("numeric text representation") >= 2
assert "Representation changes the form of the data." in text
assert "Learning changes the model's adjustable parameters" in text
assert "does not prove" in text or "doesn't prove" in text
assert "separate examples" in text or "examples it did not train on" in text
print(f"PASS: final teaching contract and {words} words")
PY

rg -n -i '\b(token|tensor|logit|gradient|attention|embedding)\b' course/video_1_script_2.md
```

Expected: the Python check passes; deferred terms occur only in the explicit
final boundary.

- [ ] **Step 4: Verify preservation and repository cleanliness**

Run:

```bash
shasum -a 256 course/videos/001-computer-learning-from-text/script.md
shasum -a 256 /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/course/video_1_improved_script.md
git diff --check
git status --short
git diff --name-only HEAD
```

Expected:

- both existing-script hashes match Task 1;
- `git diff --check` reports no errors;
- no media, video, audio, render, Adobe project, source, test, canonical-script,
  or user-draft path appears in the working diff;
- only `course/video_1_script_2.md` may be modified after the most recent
  content commit; the implementation plan is committed before the isolated
  worktree is created.

- [ ] **Step 5: Commit the read-aloud refinements**

Run:

```bash
git add course/video_1_script_2.md
git commit -m "docs: finalize book-method video one script"
```

Expected: the commit contains only Script 2. If Script 2 has no changes after
its previous commit, do not create an empty commit.

---

### Task 4: Final Verification

**Files:**

- Verify: `course/video_1_script_2.md`
- Test: `tests/test_course_structure.py`

**Interfaces:**

- Consumes: the final committed narration and plan.
- Produces: current command evidence supporting the completion report.

- [ ] **Step 1: Run the deterministic lab again**

Run:

```bash
python course/videos/001-computer-learning-from-text/lab.py
```

Expected: the canonical five output lines documented in Task 2.

- [ ] **Step 2: Run the focused course tests again**

Run:

```bash
uv run pytest tests/test_course_structure.py -v
```

Expected: all focused course-structure tests pass.

- [ ] **Step 3: Inspect final history, status, and changed paths**

Run:

```bash
git log --oneline -4
git status --short --branch
git show --stat --oneline HEAD
git show --stat --oneline HEAD^
git -C /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch status --short --branch
```

Expected:

- history contains the approved design, Script 2 draft/finalization, and plan;
- the isolated worktree is clean, while the primary checkout still shows only
  the untouched user-owned `course/video_1_improved_script.md`;
- no media or video file appears in either new content commit.
