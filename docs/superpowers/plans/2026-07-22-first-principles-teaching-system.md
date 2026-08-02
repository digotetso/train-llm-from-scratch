# First-Principles Teaching System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create and validate a reusable Codex teaching skill, then rewrite
Video 1 so its spoken narration applies the approved first-principles teaching
system.

**Architecture:** Keep the course-specific teaching contract in the repository
specification and install a reusable, project-independent skill in the personal
Codex skills directory. Validate the skill with a no-skill baseline followed by
the same task with the skill loaded. Protect the Video 1 rewrite with structural
and factual tests, then verify the complete repository.

**Tech Stack:** Markdown, Codex Skills (`SKILL.md` and `agents/openai.yaml`),
Python 3, pytest, repository course artifacts.

## Global Constraints

- Preserve the Video 1 objective, commands, repository behavior, NFKC warning,
  and deferred-vocabulary boundary.
- Build intuition before terminology and examples before general claims.
- Keep code points distinct from UTF-8 bytes and representation distinct from
  learning.
- Do not imitate or reproduce either reference author's wording.
- Do not modify production model, tokenizer, data, or training code.
- Do not stage or change unrelated user work.
- Create the personal skill at
  `/Users/digotetsomatema/.codex/skills/teaching-technical-concepts`.

---

## File Map

### Repository Files

- `docs/superpowers/specs/2026-07-22-first-principles-teaching-system-design.md`
  is the approved source of truth.
- `docs/superpowers/plans/2026-07-22-first-principles-teaching-system.md`
  is this execution plan.
- `tests/test_course_structure.py` owns the required Video 1 heading sequence.
- `tests/test_video_001_teaching_style.py` will own focused teaching-contract
  tests without duplicating repository-wide course tests.
- `course/videos/001-computer-learning-from-text/script.md` will contain the
  final spoken narration and stage directions.

### Personal Skill Files

- `/Users/digotetsomatema/.codex/skills/teaching-technical-concepts/SKILL.md`
  will contain the concise reusable workflow.
- `/Users/digotetsomatema/.codex/skills/teaching-technical-concepts/references/technical-teaching-standard.md`
  will contain detailed voice, example, analogy, accuracy, and review rules.
- `/Users/digotetsomatema/.codex/skills/teaching-technical-concepts/agents/openai.yaml`
  will contain generated UI metadata.

---

### Task 1: Establish The No-Skill Baseline

**Files:**

- Read:
  `docs/superpowers/specs/2026-07-22-first-principles-teaching-system-design.md`
- Do not create or modify skill files during this task.

**Interfaces:**

- Consumes: the approved teaching contract and a dense technical source
  paragraph.
- Produces: raw baseline outputs and a short failure summary used to constrain
  the minimum skill content.

- [ ] **Step 1: Run five fresh-context baseline repetitions**

Use fresh agents without the proposed skill. Give each agent this task without
describing the expected teaching sequence:

```text
Rewrite the following as 60-90 seconds of narration for a true beginner who can
read basic Python but knows no machine learning. Preserve technical accuracy.

Programs represent written characters according to fixed standards. Unicode
assigns each encoded character an integer code point. A code point identifies a
character but does not encode its contextual meaning. Mathematical models need
numeric input, but converting text to numbers is not learning; learning changes
adjustable model parameters in response to measured prediction error.
```

Collect five independent outputs. Do not provide the design specification,
reference sources, desired answer, or suspected failures.

- [ ] **Step 2: Score every baseline output manually**

Use this exact rubric, one point per item:

```text
[ ] Begins with a meaningful learner question or familiar experience.
[ ] Makes representation understandable before naming Unicode/code point.
[ ] Contains a prediction, comparison, or reasoning prompt.
[ ] Traces the distinction between fixed mapping and parameter change.
[ ] Uses a tiny example as evidence rather than decoration.
[ ] Anticipates the identifier-versus-meaning misconception.
[ ] Ends with a compact transferable mental model.
[ ] Sounds natural when read aloud.
```

Record the missing behaviors and any repeated failure pattern. The RED phase is
valid only if at least one meaningful contract item is missing from the
no-skill outputs.

- [ ] **Step 3: Run one baseline drafting task and one review task**

Drafting task:

```text
Outline a ten-minute beginner lesson explaining why an LLM needs numeric input
before it can train. Include a small Python demonstration.
```

Review task:

```text
Review this beginner narration and identify the three most important teaching
problems: "Unicode assigns code points. UTF-8 turns them into bytes. A model
uses tensors and embeddings, then gradient descent updates parameters. Run
ord('A') and you will understand how language models learn."
```

Record omissions and wrong priorities. Do not revise the prompts after seeing
the results.

---

### Task 2: Initialize And Author The Personal Codex Skill

**Files:**

- Create:
  `/Users/digotetsomatema/.codex/skills/teaching-technical-concepts/SKILL.md`
- Create:
  `/Users/digotetsomatema/.codex/skills/teaching-technical-concepts/references/technical-teaching-standard.md`
- Generate:
  `/Users/digotetsomatema/.codex/skills/teaching-technical-concepts/agents/openai.yaml`

**Interfaces:**

- Consumes: the baseline failures from Task 1 and the approved repository
  specification.
- Produces: a discoverable `$teaching-technical-concepts` skill usable across
  projects.

- [ ] **Step 1: Confirm the destination does not already exist**

Run:

```bash
test ! -e /Users/digotetsomatema/.codex/skills/teaching-technical-concepts
```

Expected: exit status `0`. If it exists, stop and inspect it instead of
overwriting it.

- [ ] **Step 2: Initialize the skill with the official generator**

Run with approval to write to the personal Codex directory:

```bash
python3 /Users/digotetsomatema/.codex/skills/.system/skill-creator/scripts/init_skill.py teaching-technical-concepts --path /Users/digotetsomatema/.codex/skills --resources references --interface 'display_name=Teaching Technical Concepts' --interface 'short_description=First-principles technical lesson design' --interface 'default_prompt=Use $teaching-technical-concepts to turn this technical material into a clear beginner lesson.'
```

Expected: a new skill directory containing `SKILL.md`, `agents/openai.yaml`, and
`references/`.

- [ ] **Step 3: Write the minimum `SKILL.md` that addresses baseline failures**

Use exactly two YAML keys:

```yaml
---
name: teaching-technical-concepts
description: Use when writing, rewriting, structuring, or reviewing beginner-facing technical lessons, course material, video narration, labs, or explanatory documentation.
---
```

The body must use imperative language and contain these sections:

```markdown
# Teaching Technical Concepts

## Overview

Build a causal mental model before asking the learner to remember terminology
or imitate code. Keep spoken explanations conversational while preserving every
cause needed to explain the observed result.

## Required Preparation

Read `references/technical-teaching-standard.md` before drafting or reviewing a
lesson. Identify the learner's prerequisites, the one lesson objective, verified
source facts, and vocabulary already taught.

## Teaching Sequence

1. Begin with a real learner question.
2. Activate familiar knowledge.
3. Expose the gap between appearance and mechanism.
4. Isolate the smallest mechanism.
5. Ask for a prediction or trace.
6. Name the technical concept.
7. Trace input through operation to output.
8. Prove the mechanism with a hand-checkable example.
9. Correct the likely category error.
10. Compress the idea into a reusable mental model.
11. Connect that model to the next concept.

## Output Contract

For narration, separate stage directions and code from spoken words. Carry each
section's conclusion into the next question. Use analogies only as bounded
bridges. Treat examples as evidence, not copying exercises. State a short caveat
immediately after the simplified claim only when omission would mislead.

## Review Gate

Verify that the learner can explain, predict, trace, distinguish, and transfer
the concept. Reject terminology-first explanations, hidden causal jumps,
unbounded analogies, decorative examples, future jargon, unsupported claims,
and document-like spoken instructions.

## Common Mistakes

- Making the analogy carry the technical conclusion.
- Naming several terms before making any behavior understandable.
- Showing code without asking for or explaining a prediction.
- Removing a necessary cause in the name of simplification.
- Repeating the recap without creating a transferable mental model.
```

- [ ] **Step 4: Write the detailed teaching standard reference**

Create `references/technical-teaching-standard.md` with these complete sections:

```text
# Technical Teaching Standard
## Learner And Objective
## Concept Dependency Ladder
## Spoken Voice
## Terminology
## Analogies
## Examples And Labs
## Simplification And Caveats
## Evidence And Accuracy
## Lesson-Level Flow
## Review Rubric
```

Translate the approved repository specification into reusable guidance. Exclude
Video 1 names, paths, source-author mannerisms, and project-specific terms. The
review rubric must check explanation, prediction, causal trace, distinctions,
transfer, read-aloud quality, and factual grounding.

- [ ] **Step 5: Inspect generated UI metadata**

Run:

```bash
sed -n '1,120p' /Users/digotetsomatema/.codex/skills/teaching-technical-concepts/agents/openai.yaml
```

Expected:

```yaml
interface:
  display_name: "Teaching Technical Concepts"
  short_description: "First-principles technical lesson design"
  default_prompt: "Use $teaching-technical-concepts to turn this technical material into a clear beginner lesson."
```

---

### Task 3: Validate And Forward-Test The Skill

**Files:**

- Verify:
  `/Users/digotetsomatema/.codex/skills/teaching-technical-concepts/SKILL.md`
- Verify:
  `/Users/digotetsomatema/.codex/skills/teaching-technical-concepts/references/technical-teaching-standard.md`
- Verify:
  `/Users/digotetsomatema/.codex/skills/teaching-technical-concepts/agents/openai.yaml`

**Interfaces:**

- Consumes: the initialized skill and the exact baseline prompts from Task 1.
- Produces: validator output and forward-test evidence that the skill changes
  drafting, rewriting, and review behavior.

- [ ] **Step 1: Validate file structure and frontmatter**

Run:

```bash
python3 /Users/digotetsomatema/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/digotetsomatema/.codex/skills/teaching-technical-concepts
```

Expected: validation succeeds with no YAML, naming, or structure errors.

- [ ] **Step 2: Run the same rewriting prompt five times with the skill**

Use five fresh agents. Give each agent the personal skill path and the exact
rewriting prompt from Task 1. Do not include the expected answer or baseline
diagnosis.

Score every output with the unchanged eight-item rubric. Compare the distribution
with the no-skill control. The skill passes this gate when outputs consistently
follow the approved sequence and materially improve the missing baseline items.

- [ ] **Step 3: Forward-test drafting and review**

Run the unchanged drafting and review prompts from Task 1 with the skill. Verify:

```text
Drafting: objective, dependency order, prediction, tiny example, misconception,
and transfer task are present.

Review: terminology-first teaching, conflated representation/learning, future
jargon, unsupported inference, and lack of prediction are prioritized.
```

- [ ] **Step 4: Refactor only if testing exposes a concrete gap**

If an agent follows the wrong shape, add a positive required slot to the skill
or reference. If an agent skips a known rule under pressure, add the observed
rationalization and a direct counter. Re-run the affected scenario and
`quick_validate.py` after every revision.

---

### Task 4: Add Failing Video 1 Teaching-Contract Tests

**Files:**

- Modify: `tests/test_course_structure.py`
- Create: `tests/test_video_001_teaching_style.py`
- Test: `tests/test_course_structure.py`
- Test: `tests/test_video_001_teaching_style.py`

**Interfaces:**

- Consumes: the approved Video 1 rewrite contract.
- Produces: structural tests that fail against the current narration for the
  intended reasons and remain flexible about exact prose.

- [ ] **Step 1: Change the required Video 1 section heading**

In `VIDEO_HEADINGS["script.md"]`, replace:

```python
"## 00:45 Direct Explanation",
```

with:

```python
"## 00:45 Analogy",
```

- [ ] **Step 2: Add focused teaching-style tests**

Create `tests/test_video_001_teaching_style.py` with:

```python
from pathlib import Path


SCRIPT_PATH = Path("course/videos/001-computer-learning-from-text/script.md")


def read_script() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def section(markdown: str, heading: str) -> str:
    content = markdown.split(f"{heading}\n", maxsplit=1)[1]
    return content.split("\n## ", maxsplit=1)[0]


def test_video_one_builds_intuition_before_technical_vocabulary():
    script = read_script()
    hook = section(script, "## 00:00 Hook")
    analogy = section(script, "## 00:45 Analogy")
    technical = section(script, "## 02:00 Technical Meaning")

    assert "When you read" in hook
    assert "computer" in hook.lower() and "meaning" in hook.lower()
    assert "**Teaching analogy:**" in analogy
    assert "analogy" in analogy.lower() and "limit" in analogy.lower()
    for term in ["**character**", "**Unicode**", "**code point**", "**byte**", "**UTF-8**"]:
        assert term in technical


def test_video_one_uses_prediction_and_changed_case_as_evidence():
    script = read_script()
    lab = section(script, "## 09:00 Live Mini-Lab")

    prediction_index = lab.lower().index("predict")
    run_index = lab.index("python course/videos/001-computer-learning-from-text/lab.py")
    assert prediction_index < run_index
    assert 'text = "A"' in lab
    assert "Predict" in lab or "predict" in lab


def test_video_one_keeps_future_vocabulary_out_of_the_explanation():
    teaching_body = read_script().split("### Vocabulary Deferred to Later Videos", maxsplit=1)[0].lower()

    for term in ["token embedding", "tensor", "logit", "gradient", "attention"]:
        assert term not in teaching_body


def test_video_one_ends_with_a_spoken_transferable_distinction():
    script = read_script()
    recap = section(script, "## 13:00 Recap And Exercise")

    assert "Restate our objective" not in recap
    assert "representation" in recap.lower()
    assert "learning" in recap.lower()
    assert "parameters" in recap.lower()
    assert "prediction" in recap.lower() or "guesses" in recap.lower()


def test_video_one_preserves_source_and_observation_labels():
    script = read_script()

    assert "**Source fact:**" in script
    assert "**Observed code behavior:**" in script
    assert "**Teaching analogy:**" in script
```

- [ ] **Step 3: Run focused tests and verify RED**

Run:

```bash
uv run pytest tests/test_course_structure.py::test_video_one_artifacts_have_required_headings tests/test_video_001_teaching_style.py -v
```

Expected: failures because the current script uses `Direct Explanation`, lacks
the bounded teaching analogy, teaches `token embeddings` before the deferred
section, and uses document-like recap wording. Fix test errors if any test does
not reach the intended assertion; do not change the script during RED.

---

### Task 5: Rewrite Video 1 To Satisfy The Teaching Contract

**Files:**

- Modify: `course/videos/001-computer-learning-from-text/script.md`
- Test: `tests/test_course_structure.py`
- Test: `tests/test_video_001_teaching_style.py`

**Interfaces:**

- Consumes: the approved design, current verified script facts, companion
  lesson, lab, and repository source.
- Produces: a complete read-aloud narration with unchanged commands and factual
  boundaries.

- [ ] **Step 1: Rewrite the Hook and Analogy**

Use this content contract:

```text
Hook: Invite the learner to read `cat` and notice the memories or concept it
evokes. Contrast that human experience with the represented input the computer
receives. Ask what must happen before mathematics can work with the text. State
the one objective and promise the three-letter mini-lab.

Analogy: Use a library identifier as a bounded teaching analogy. Explain that an
identifier helps locate and distinguish a book without containing its story or
the reader's experience. State that character systems operate at a different
level and that the analogy does not explain learning. Lead into the question of
which agreed number Python reports for `A`.
```

- [ ] **Step 2: Rewrite Technical Meaning and Tiny Example**

Introduce `character`, Unicode, code point, `ord`, byte, and UTF-8 one at a time.
Preserve `ord("C")`, `ord("a")`, and `ord("t")`. Explain the ASCII-range match
between code points and UTF-8 bytes as a local property of `Cat`, not a universal
rule.

Define a model as a mathematical prediction system with adjustable parameters.
Keep this explicit contrast:

```text
Representation follows fixed agreements.
Learning changes adjustable model parameters using examples and measured error.
```

Use `cat sat`, `cat ran`, and `cat slept`, followed by the `Cat` number trace and
the seven-to-five mistake illustration. Remove `token embedding` from the
teaching body. Keep memorization and held-out evaluation as one short caveat
after the improvement intuition.

- [ ] **Step 3: Rewrite the repository walkthrough for speech**

Preserve both code excerpts and their comments. Keep these facts:

```text
- normalize_text applies NFKC, newline normalization, per-line rstrip, and
  outer strip in the displayed excerpt.
- Type annotations communicate expectations but do not enforce runtime types.
- NFKC is a deliberate cleaning policy and is not lossless.
- `①` can become `1`, and character count can change.
- The full implementation also removes selected controls and limits blank lines.
- prepare.py stores normalized text and Python's string length.
- Preparation does not update model parameters.
```

Break the current paragraph-long code explanation into spoken steps and use its
conclusion to introduce the lab.

- [ ] **Step 4: Rewrite the lab, mistakes, and recap**

Preserve the exact runnable command, displayed Python, expected numeric lists,
raw-string prompt, and reset to `Cat`. Ask for predictions before each run and
explain why the observed output follows.

Correct both misconceptions:

```text
65 identifies `A` under an agreement; it is not every human meaning of `A`.
ord applies a fixed mapping; it does not learn from practice or error.
```

End with learner-directed questions, the existing fill-in exercise, and this
semantic conclusion in natural spoken prose:

```text
Representation gives the model numbers it can work with. Learning changes the
model's adjustable numbers so later predictions can improve.
```

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```bash
uv run pytest tests/test_course_structure.py::test_video_one_artifacts_have_required_headings tests/test_course_structure.py::test_video_one_warns_that_nfkc_is_a_non_lossless_cleaning_policy tests/test_course_structure.py::test_video_one_uses_one_precise_raw_string_prompt_everywhere tests/test_video_001_teaching_style.py -v
```

Expected: all selected tests pass.

- [ ] **Step 6: Perform a read-aloud review**

Read only spoken paragraphs, excluding headings, code, and stage directions.
Revise any sentence that:

```text
- introduces more than one unexplained term;
- carries several caveats before its main claim;
- sounds like an instruction to a document author rather than a learner;
- repeats a conclusion without connecting it to the next question;
- cannot be spoken naturally in one breath without losing the subject.
```

Re-run the focused tests after prose refactoring.

---

### Task 6: Verify, Review, And Commit The Repository Changes

**Files:**

- Verify: `tests/test_course_structure.py`
- Verify: `tests/test_video_001_teaching_style.py`
- Verify: `course/videos/001-computer-learning-from-text/script.md`
- Do not stage personal skill files with the repository.

**Interfaces:**

- Consumes: green focused tests, validated personal skill, and final narration.
- Produces: complete test evidence, a clean diff, and an isolated repository
  commit containing only the plan, teaching tests, and Video 1 rewrite.

- [ ] **Step 1: Run the lab directly**

Run:

```bash
python course/videos/001-computer-learning-from-text/lab.py
```

Expected:

```text
Human text: Cat
Character numbers: [67, 97, 116]
UTF-8 bytes: [67, 97, 116]
Can the mathematical model use this raw Python string as numeric input? No
Learning begins after text is represented as numbers.
```

- [ ] **Step 2: Run course-focused verification**

Run:

```bash
uv run pytest tests/test_course_structure.py tests/test_video_001_teaching_style.py -v
```

Expected: all course and teaching-contract tests pass.

- [ ] **Step 3: Run the complete repository suite**

Run:

```bash
uv run pytest -v
```

Expected: all repository tests pass with no unexpected warnings or errors.

- [ ] **Step 4: Review formatting and scope**

Run:

```bash
git diff --check
git diff -- tests/test_course_structure.py tests/test_video_001_teaching_style.py course/videos/001-computer-learning-from-text/script.md docs/superpowers/plans/2026-07-22-first-principles-teaching-system.md
git status --short
```

Expected: no whitespace errors; only requested files appear in the task diff;
unrelated pre-existing user files remain untouched.

- [ ] **Step 5: Commit only repository deliverables**

Run:

```bash
git add docs/superpowers/plans/2026-07-22-first-principles-teaching-system.md tests/test_course_structure.py tests/test_video_001_teaching_style.py course/videos/001-computer-learning-from-text/script.md
git commit -m "feat: apply first-principles teaching system"
```

Expected: one commit containing the implementation plan, focused tests, and
Video 1 rewrite. Personal skill installation remains outside this repository.

---

## Plan Self-Review

- Every acceptance criterion in the approved specification maps to a task.
- The personal skill and repository artifacts have separate ownership.
- The skill follows RED-GREEN-REFACTOR with a no-guidance control.
- The script change follows RED-GREEN-REFACTOR with focused repository tests.
- Exact paths, commands, expected outcomes, metadata, and test code are present.
- No production model, tokenizer, data, or training file is in scope.
- No placeholder or deferred implementation step remains.

