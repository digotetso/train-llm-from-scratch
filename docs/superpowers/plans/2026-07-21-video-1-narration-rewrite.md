# Video 1 Narration Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite Video 1 as warm, confident, beginner-friendly spoken narration while preserving its verified technical meaning, code, lab, scope, and course contract.

**Architecture:** Treat the existing companion lesson, repository source, and course tests as fixed sources of truth. Rewrite only the narration script in its existing eight-section sequence, restoring the required `Analogy` heading and improving each transition without changing implementation behavior or introducing deferred vocabulary.

**Tech Stack:** Markdown, Python 3, pytest, repository-standard shell commands

## Global Constraints

- Modify only `course/videos/001-computer-learning-from-text/script.md` during implementation.
- Do not modify `og_script_v1.md`, `course/labs/`, companion Video 1 artifacts, production code, or tests.
- Preserve the learning objective and approximate timestamps.
- Preserve the Unicode/code-point/UTF-8 distinctions and the ASCII limitation of the `Cat` example.
- Preserve the exact mini-lab command, source, expected values, and raw-string prompt.
- Preserve the NFKC wording required by the course contract: `deliberate cleaning policy`, `not lossless`, `①`, plain `1`, `change character count`, and `Video 5`.
- Keep token, tensor, logit, gradient, and attention deferred.
- Use warm, conversational, confident, clear, patient spoken language.

---

### Task 1: Rewrite And Verify Video 1 Narration

**Files:**
- Modify: `course/videos/001-computer-learning-from-text/script.md`
- Reference: `course/videos/001-computer-learning-from-text/lesson.md`
- Reference: `course/videos/001-computer-learning-from-text/quiz.md`
- Reference: `course/videos/001-computer-learning-from-text/answer-key.md`
- Reference: `course/videos/001-computer-learning-from-text/evidence.md`
- Reference: `matgpt/data/normalize.py`
- Reference: `matgpt/data/prepare.py`
- Test: `tests/test_course_structure.py`

**Interfaces:**
- Consumes: the approved eight-heading Video 1 structure, verified repository behavior, exact lab output, and deferred-vocabulary boundary.
- Produces: a complete `script.md` suitable for spoken delivery and compatible with all existing Video 1 tests.

- [ ] **Step 1: Confirm the existing structural failure**

Run:

```bash
/Users/digotetsomatema/venvs/ai/bin/pytest -q \
  tests/test_course_structure.py::test_video_one_artifacts_have_required_headings
```

Expected: FAIL because the current script uses `## 00:45 Direct Explanation`
where the course contract requires `## 00:45 Analogy`.

- [ ] **Step 2: Rewrite the hook and analogy**

In `script.md`:

- Keep `# Video 1: What Does It Mean for a Computer to Learn From Text?`.
- Keep `## 00:00 Hook` and replace dense opening language with the direct idea:
  the computer receives the text, not the thoughts, feelings, memories, or
  experiences a person connects to it.
- Use `## 00:45 Analogy` as the second heading.
- Explain the library identifier analogy: an identifier helps a system store
  and find a book but does not contain its story or emotional meaning.
- State the analogy's limit: character representation is not the whole text
  pipeline and does not explain how learning works.
- Transition with the question of how software represents a character such as
  `A` consistently.

- [ ] **Step 3: Rewrite the technical meaning and tiny example**

Keep `## 02:00 Technical Meaning` and `## 04:00 Tiny Example` in place.

- Introduce character, Unicode, code point, byte, UTF-8, model, parameter,
  prediction, learning, and pattern only after a plain-language sentence.
- Keep `ord("C") == 67`, `ord("a") == 97`, and `ord("t") == 116`.
- Explain that the code point identifies a character but does not contain its
  contextual meaning.
- Explain why the Unicode values and UTF-8 bytes match for the ASCII-range
  letters in `Cat`, and explicitly say this does not hold for every character.
- Preserve the three examples `cat sat`, `cat ran`, and `cat slept`.
- Preserve the ten-prediction illustration, clearly labeling it as intuition
  rather than the repository's full loss calculation.
- End with the distinction between fixed representation numbers and adjustable
  model parameters.

- [ ] **Step 4: Rewrite the repository walkthrough and mini-lab narration**

Keep `## 06:00 Repository Walkthrough` and `## 09:00 Live Mini-Lab`.

- Preserve the simplified `normalize_text` and `prepare.py` excerpts.
- Explain the excerpts top to bottom in short spoken sentences.
- Preserve the exact NFKC warning phrases listed in Global Constraints.
- State clearly that normalization prepares data and does not update model
  parameters.
- Preserve the complete `lab.py` excerpt and this exact command:

```bash
python course/videos/001-computer-learning-from-text/lab.py
```

- Preserve `[67, 97, 116]`, the `A` extension with `[65]`, and the instruction
  to restore `Cat` afterward.
- Preserve this exact output sentence:
  `Can the mathematical model use this raw Python string as numeric input? No`.

- [ ] **Step 5: Rewrite misconceptions, recap, and transitions**

Keep `## 12:00 Common Mistake` and `## 13:00 Recap And Exercise`.

- Explain conversationally why `65` represents `A` without being the meaning
  of `A`.
- Explain why calling `ord` is fixed conversion rather than learning.
- Preserve the five learner-check topics aligned with the approved quiz.
- Preserve the exercise using `A` and the sentence frame about what `65` is
  assigned to and what it does not encode.
- End with: representing text gives the computer numbers to work with;
  learning changes the model's internal numbers so its predictions improve.
- Retain `### Vocabulary Deferred to Later Videos` and all five deferred terms.

- [ ] **Step 6: Perform a read-aloud and source-accuracy review**

Read every narration paragraph aloud and revise any sentence that:

- requires more than one breath;
- introduces an unexplained term;
- repeats the preceding sentence without adding meaning;
- stacks multiple caveats before stating the main idea;
- sounds like formal documentation instead of a teacher speaking.

Compare the two code excerpts with `matgpt/data/normalize.py` and
`matgpt/data/prepare.py`. Confirm the script labels omitted behavior and does
not claim that normalization performs learning.

- [ ] **Step 7: Run the lab and focused tests**

Run:

```bash
python course/videos/001-computer-learning-from-text/lab.py
/Users/digotetsomatema/venvs/ai/bin/pytest -q tests/test_course_structure.py
```

Expected lab output:

```text
Human text: Cat
Character numbers: [67, 97, 116]
UTF-8 bytes: [67, 97, 116]
Can the mathematical model use this raw Python string as numeric input? No
Learning begins after text is represented as numbers.
```

Expected test result: all tests in `tests/test_course_structure.py` PASS.

- [ ] **Step 8: Run full verification**

Run:

```bash
git diff --check
/Users/digotetsomatema/venvs/ai/bin/pytest -q
```

Expected: no whitespace errors and all 191 repository tests PASS.

- [ ] **Step 9: Review and commit only the script**

Run:

```bash
git diff -- course/videos/001-computer-learning-from-text/script.md
git status --short
git add course/videos/001-computer-learning-from-text/script.md
git commit -m "docs: improve Video 1 narration flow"
```

Confirm that `og_script_v1.md` and `course/labs/` remain untracked and are not
included in the commit.
