# Video 1 Spoken-English Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `final_final copy` so it sounds like a patient teacher speaking in simple, common English while preserving the approved lesson, examples, and 10-to-15-minute runtime.

**Architecture:** Keep the eight-section teaching sequence, code blocks, and expected outputs as the stable lesson structure. Rewrite only the narration and transitions, then verify the spoken voice, terminology order, technical facts, examples, and runtime.

**Tech Stack:** Markdown, Python 3 standard library, pytest, Git

## Global Constraints

- Use simple, common English.
- Use short and medium sentences that sound natural aloud.
- Explain an idea in ordinary language before giving it a technical name.
- Keep the existing eight-section concept order.
- Keep the video between 10 and 15 minutes, aiming for about 13 minutes.
- Keep stage directions, code, headings, and displayed text outside spoken narration.
- Do not add media, video, animation, or production assets.
- Do not edit `final_final copy.pre-13-minute-original.md`.
- Leave unrelated working-tree changes untouched.

---

### Task 1: Rewrite and verify the spoken narration

**Files:**
- Modify: `final_final copy`
- Preserve: `final_final copy.pre-13-minute-original.md`
- Reference: `docs/superpowers/specs/2026-07-24-final-script-spoken-english-rewrite-design.md`

**Interfaces:**
- Consumes: the approved eight-section script, its Python examples, and expected outputs.
- Produces: a complete beginner-facing video script written in natural spoken English.

- [ ] **Step 1: Record the protected backup and stable lesson structure**

Run:

```bash
shasum -a 256 "final_final copy.pre-13-minute-original.md"
rg '^## [0-9]{2}:[0-9]{2}' "final_final copy"
```

Expected:

- The backup hash is recorded before editing.
- The script has eight timed sections beginning at `00:00`, `02:20`, `03:45`, `05:00`, `06:25`, `08:00`, `10:20`, and `12:10`.

- [ ] **Step 2: Rewrite every narration paragraph**

Edit `final_final copy` section by section.

For each paragraph:

1. Say the main point using words a learner hears in everyday conversation.
2. Split sentences that carry more than one main thought.
3. Use `you`, `we`, `let's`, and contractions when they sound natural.
4. Explain observable behavior before naming a technical term.
5. Carry the result of the current paragraph into the next question.
6. Remove document-like phrases such as:
   - `purpose-dependent`;
   - `retained values`;
   - `storage evidence`;
   - `causal model`;
   - `trace diverged`;
   - `selected transformation`;
   - `identification agreement`.
7. Preserve the exact meaning of code points, inspection, NFKC, normalization, and text preparation.
8. Keep code, outputs, and stage directions separate from spoken narration.

- [ ] **Step 3: Check the spoken-language contract**

Run a narration audit that ignores headings, fenced code, and stage directions. Confirm:

- no spoken sentence exceeds 30 words unless splitting it would make the idea less clear;
- the narration uses contractions naturally;
- the rejected formal phrases do not appear in narration;
- each technical term is explained in plain language before or when it is named;
- every transition continues the current line of reasoning.

Read the narration aloud once. Rewrite any sentence that needs more than one comfortable breath or sounds like written documentation.

- [ ] **Step 4: Verify the examples and expected outputs**

Run:

```bash
python - <<'PY'
import unicodedata

def prepare_text(text):
    text = unicodedata.normalize("NFKC", text)
    lines = text.splitlines()
    prepared_lines = []

    for line in lines:
        line = line.strip()
        if line != "":
            prepared_lines.append(line)

    return "\n".join(prepared_lines)

examples = [
    (
        "  Lesson ①: Ａ cat ﬀ  \r\n\r\n\tsecond line  ",
        "Lesson 1: A cat ff\nsecond line",
    ),
    (
        "  Chapter ②: Ｂig oﬀice  \n\n  final line  ",
        "Chapter 2: Big office\nfinal line",
    ),
]

for source, expected in examples:
    actual = prepare_text(source)
    assert actual == expected, (actual, expected)
    print(repr(actual))
PY
```

Expected:

```text
'Lesson 1: A cat ff\nsecond line'
'Chapter 2: Big office\nfinal line'
```

- [ ] **Step 5: Verify runtime, protected files, tests, and diff**

Confirm the narration remains between 10 and 15 minutes at a calm teaching pace and that no section is rushed.

Run:

```bash
shasum -a 256 "final_final copy.pre-13-minute-original.md"
.venv/bin/pytest -q -p no:cacheprovider
git diff --check -- "final_final copy"
git diff -- "final_final copy"
git status --short
```

Expected:

- The protected backup hash is unchanged.
- The full test suite passes.
- The Markdown diff has no whitespace errors.
- Only the intended script and planning artifacts belong to this rewrite.
- Pre-existing unrelated changes remain present and untouched.

- [ ] **Step 6: Commit the rewritten script**

Run:

```bash
git add -- "final_final copy"
git commit -m "docs: rewrite video one in spoken English"
```

Expected:

- The commit contains only `final_final copy`.
- The exact main-project file now contains the spoken-English rewrite.
