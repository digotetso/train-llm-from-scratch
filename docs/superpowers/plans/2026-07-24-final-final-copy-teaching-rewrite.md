# Video 1 `final_final copy` Teaching Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `final_final copy` into a focused, fact-checked, approximately 15-minute beginner lesson that teaches learners to inspect and prepare source text before later AI work.

**Architecture:** Keep one self-contained Markdown narration artifact. Build one causal chain from messy source text through inspection, code-point identification, chosen normalization, and a complete preparation function; close all later AI mechanisms. Verify the narration contract with temporary read-only scripts and execute every complete Python example shown in the lesson.

**Tech Stack:** Markdown, Python 3 standard library, `unicodedata`, `pytest` for repository regression verification, Git.

## Global Constraints

- Modify only `final_final copy` during implementation.
- Preserve `final_final`, established course scripts, tests, media, animation, rendering, and production files.
- Target 1,800-1,950 spoken words and approximately 15 minutes.
- Keep every spoken sentence at 40 words or fewer.
- Use nine connected timestamped sections.
- Explain behavior before naming code point, `repr`, normalization, NFKC, `splitlines`, `strip`, or `join`.
- Defer LLM internals, tokenizers, tokens, token IDs, vocabularies, embeddings, vectors, tokenizer normalization, compatibility decomposition, and canonical composition.
- Use `number`, not `integer`, and `split`, not `divide`, in learner-facing narration.
- Do not use “job,” “path,” or “compress” as spoken editorial metaphors.
- Include the messy source text, `repr`, `ord`, `① -> 1`, `Ａ -> A`, `ﬀ -> ff`, the length-changing ligature case, the NFKC boundary, one complete `prepare_text` function, and one changed-input transfer test.
- Do not add media or production files.

---

### Task 1: Establish The Rewrite Contract And Protected Baseline

**Files:**
- Read: `final_final copy`
- Read: `final_final`
- Read: `docs/superpowers/specs/2026-07-24-final-final-copy-teaching-rewrite-design.md`
- Modify: none

**Interfaces:**
- Consumes: the approved target hash `d2fe39c1250de1c679232a5bfa118966b3d05e04e0cd63c25395dbf00f6b8441`
- Produces: a verified baseline and a failing narration contract for the current 3,895-word draft

- [ ] **Step 1: Verify the approved target and protected-source hashes**

Run:

```bash
shasum -a 256 "final_final copy" final_final
```

Expected first line:

```text
d2fe39c1250de1c679232a5bfa118966b3d05e04e0cd63c25395dbf00f6b8441  final_final copy
```

Record the second line's hash exactly as the protected `final_final` baseline
for Task 4.

- [ ] **Step 2: Record the pre-rewrite worktree without changing it**

Run:

```bash
git status --short
```

Expected: existing unrelated modifications and untracked files may appear.
Confirm that no unrelated path is staged.

- [ ] **Step 3: Run the narration contract and verify that the current draft fails**

Run:

```bash
python - <<'PY'
import re
from pathlib import Path

path = Path("final_final copy")
script = path.read_text(encoding="utf-8")

headings = re.findall(r"^## \d{2}:\d{2} .+$", script, re.MULTILINE)
assert len(headings) == 9, headings

in_fence = False
spoken_lines = []
for raw_line in script.splitlines():
    line = raw_line.strip()
    if line.startswith("```"):
        in_fence = not in_fence
        continue
    if in_fence or not line:
        continue
    if line.startswith(("#", "[", "---")):
        continue
    spoken_lines.append(re.sub(r"[*_`>]", "", line))

spoken = " ".join(spoken_lines)
word_count = len(spoken.split())
assert 1800 <= word_count <= 1950, word_count

for term in (
    "large language model",
    "tokenizer",
    "token ID",
    "embedding",
    "neural network",
    "compatibility decomposition",
    "canonical composition",
):
    assert term.casefold() not in spoken.casefold(), term

assert (
    "How can we find out exactly what a piece of text contains and change it consistently before later AI work?"
    in script
)
PY
```

Expected: FAIL on the heading-count assertion because the current draft has
far more than nine timestamped sections. Its spoken-word count also exceeds
1,950 and will fail after the section structure is corrected.

---

### Task 2: Rewrite The Lesson Around One Causal Chain

**Files:**
- Modify: `final_final copy:1-1208`
- Reference: `docs/superpowers/specs/2026-07-24-final-final-copy-teaching-rewrite-design.md`

**Interfaces:**
- Consumes: the approved learner prerequisites, central question, scope, voice rules, and preservation boundary
- Produces: a complete nine-section narration with one central question and no prerequisite leakage

- [ ] **Step 1: Replace the existing section structure with the approved nine-section sequence**

Use exactly these headings:

```markdown
## 00:00 The Text Looks Simple
## 01:54 Reveal What Is Really There
## 03:38 Similar-Looking Marks Can Still Differ
## 04:30 Where Do the Agreed Numbers Come From?
## 06:05 Which Differences Should We Preserve?
## 07:30 Apply One Chosen Rule Consistently
## 09:05 Put the Chosen Steps Into One Recipe
## 11:40 Predict, Run, and Change the Starting Text
## 13:30 Carry the Explanation Forward
```

The final section is paced to end at approximately `15:00`.

- [ ] **Step 2: Write the hook and central question without future vocabulary**

Begin with this inspectable source:

```text
  Lesson ①: Ａ cat ﬀ

  second line
```

Connect it to the familiar experience of entering text into an AI tool, then
state that the course goal is to train an LLM from scratch, starting before
those abilities exist. Treat `LLM` only as the name of the system being built
and promise to explain its technical meaning later.

Identify the following as a big-picture map of the whole course, not a full
explanation of its stages:

```text
collect writing
-> make it consistent
-> split it into smaller pieces
-> give the pieces numbers
-> create learning exercises
-> build an adjustable mathematical system
-> improve it through practice
-> test the result
```

Tell learners that the stages have proper technical names and that each name
will be introduced later, only after its behavior makes sense. Do not define
LLMs, tokenizers, or training internals here.

Narrow the map to Video 1's focus: the first handoff from collected writing to
reliable starting material. Then establish this exact central question:

> **How can we find out exactly what a piece of text contains and change it consistently before later AI work?**

State learner success in observable terms: inspect hidden marks, distinguish
character identity from preparation, trace every transformation, and predict a
changed case.

- [ ] **Step 3: Make inspection the first mechanism**

Use this exact source string:

```python
source = "  Lesson ①: Ａ cat ﬀ  \r\n\r\n\tsecond line  "
```

Ask what normal printing may hide before naming `repr`. Then show:

```python
print(repr(source))
```

with exact output:

```text
'  Lesson ①: Ａ cat ﬀ  \r\n\r\n\tsecond line  '
```

Explain only the details needed later:

```text
\t     -> a tab
\r\n   -> one line ending
\r\n\r\n -> two consecutive line endings with an empty line between them
```

State that inspection does not change the source.

- [ ] **Step 4: Build character identification from a prediction**

Compare `①` and `1`. Ask whether similar appearance requires the same fixed
identifier. Reveal the observed values only after the prediction:

```python
print(ord("①"))
print(ord("1"))
```

```text
9312
49
```

Explain the mechanism in ordinary language, then introduce:

```text
Unicode
code point
ord
```

Use this compact operational definition:

> In today’s examples, a code point is the fixed number Unicode uses to
> identify one character.

Immediately add the scope boundary:

> Some visible symbols contain several code points. Today’s examples each use
> one, so we can trace them one at a time.

- [ ] **Step 5: Carry identification into the preparation decision**

Use these verified distinctions:

```text
① -> 9312
1 -> 49

Ａ -> 65313
A -> 65

ﬀ -> [64256]
ff -> [102, 102]
```

Do not expand hexadecimal notation into a separate lesson. Ask which
differences matter for the stated example, then establish that preparation
rules depend on purpose. Include code, poetry, mathematical notation, and
historical text only as a single short boundary sentence rather than a list.

- [ ] **Step 6: Explain the selected behavior before naming normalization**

Reveal the chosen transformations:

```text
① -> 1
Ａ -> A
ﬀ -> ff
```

Only then name the behavior:

> Mapping selected alternate Unicode forms to a chosen consistent
> representation is called normalization.

Introduce NFKC as one Unicode normalization form. Do not teach compatibility
decomposition or canonical composition.

Show the length distinction:

```text
① -> 1
length 1 -> 1

ﬀ -> ff
length 1 -> 2
```

State the immediate boundary:

> NFKC can remove distinctions that matter, so it is a chosen rule for this
> example—not a universal definition of clean text.

- [ ] **Step 7: Connect every section through its conclusion**

Use transitions with this logic:

```text
inspection reveals hidden differences
-> visible forms may also hide different identifiers
-> code points expose those identifiers
-> different identifiers create a preservation choice
-> the chosen behavior earns the name normalization
-> normalization handles only one part of preparation
-> the complete function combines all chosen steps
-> the changed source tests whether the explanation transfers
```

Remove transitions that only say what the next section will discuss.

---

### Task 3: Build The Complete Example, Transfer Case, And Recap

**Files:**
- Modify: `final_final copy`

**Interfaces:**
- Consumes: the established meanings of code point, preparation, normalization, and NFKC from Task 2
- Produces: one runnable program, exact observed output, one changed case, and a compact reusable closing explanation

- [ ] **Step 1: Embed one complete preparation program**

Use this exact program:

```python
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


source = "  Lesson ①: Ａ cat ﬀ  \r\n\r\n\tsecond line  "

print("Source text:", repr(source))
print("Prepared text:", repr(prepare_text(source)))
```

The displayed run command must be:

```bash
python inspect_and_prepare_text.py
```

The displayed output must be:

```text
Source text: '  Lesson ①: Ａ cat ﬀ  \r\n\r\n\tsecond line  '
Prepared text: 'Lesson 1: A cat ff\nsecond line'
```

- [ ] **Step 2: Trace the program without hidden jumps**

Explain the program in this exact causal order:

```text
source string
-> NFKC changes ①, Ａ, and ﬀ
-> splitlines creates a three-item list
-> a loop visits each line
-> strip removes surrounding whitespace from the current line
-> if line != "" rejects the empty string
-> append keeps each non-empty line
-> join rebuilds two lines with one \n
-> prepared string
```

Explain each behavior before relying on its name. Before showing the complete
program, establish assignment, list boundaries, loop behavior, the `!=` check,
`append`, function input-to-parameter flow, indentation, and `return`.

- [ ] **Step 3: Put prediction before execution**

Before the displayed command or output, ask the learner to predict:

```text
which Unicode forms change
which whitespace disappears
whether the empty line remains
which line separator remains
```

After the output, trace every observed difference back to one line of the
function.

- [ ] **Step 4: Add one changed-input transfer case**

Change only the source string:

```python
source = "  Chapter ②: Ｂig oﬀice  \n\n  final line  "
```

Ask for the complete prediction before revealing:

```text
'Chapter 2: Big office\nfinal line'
```

Require the learner to identify which operations behaved exactly as before.

- [ ] **Step 5: End with one compact reusable explanation**

Use the established mechanisms:

```text
code point -> identifies a character in today’s examples
inspection -> reveals what the source actually contains
normalization -> applies one chosen Unicode consistency rule
text preparation -> combines the chosen transformations
```

Close by stating that prepared text is now a dependable building block for the
next lesson. Do not mention tokenizers, tokens, token IDs, vocabularies,
embeddings, vectors, neural networks, or training calculations.

---

### Task 4: Verify Facts, Executable Evidence, Voice, Timing, And Scope

**Files:**
- Verify: `final_final copy`
- Protect: `final_final`
- Verify repository regression suite without modifying tests

**Interfaces:**
- Consumes: the complete rewritten artifact from Tasks 2 and 3
- Produces: evidence that the artifact is accurate, runnable, conversational, appropriately scoped, and isolated from unrelated work

- [ ] **Step 1: Verify the Unicode and Python facts against primary sources**

Check:

```text
https://docs.python.org/3/library/functions.html#ord
https://docs.python.org/3/library/stdtypes.html#str.splitlines
https://docs.python.org/3/library/stdtypes.html#str.strip
https://docs.python.org/3/library/stdtypes.html#str.join
https://docs.python.org/3/library/unicodedata.html#unicodedata.normalize
https://www.unicode.org/versions/Unicode16.0.0/core-spec/chapter-3/
https://www.unicode.org/reports/tr15/
```

Confirm that every simplified claim remains accurate within the lesson’s
declared examples.

- [ ] **Step 2: Execute the complete preparation program**

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


source = "  Lesson ①: Ａ cat ﬀ  \r\n\r\n\tsecond line  "
print("Source text:", repr(source))
print("Prepared text:", repr(prepare_text(source)))
print("Transfer text:", repr(prepare_text(
    "  Chapter ②: Ｂig oﬀice  \n\n  final line  "
)))
PY
```

Expected:

```text
Source text: '  Lesson ①: Ａ cat ﬀ  \r\n\r\n\tsecond line  '
Prepared text: 'Lesson 1: A cat ff\nsecond line'
Transfer text: 'Chapter 2: Big office\nfinal line'
```

- [ ] **Step 3: Execute the code-point and length checks**

Run:

```bash
python - <<'PY'
import unicodedata

print(ord("①"), ord("1"))
print(ord("Ａ"), ord("A"))
print([ord(character) for character in "ﬀ"])
print([ord(character) for character in "ff"])
print(len("①"), len(unicodedata.normalize("NFKC", "①")))
print(len("ﬀ"), len(unicodedata.normalize("NFKC", "ﬀ")))
PY
```

Expected:

```text
9312 49
65313 65
[64256]
[102, 102]
1 1
1 2
```

- [ ] **Step 4: Run the final narration contract**

Run:

```bash
python - <<'PY'
import re
from pathlib import Path

path = Path("final_final copy")
script = path.read_text(encoding="utf-8")

expected_headings = [
    "## 00:00 The Text Looks Simple",
    "## 01:54 Reveal What Is Really There",
    "## 03:38 Similar-Looking Marks Can Still Differ",
    "## 04:30 Where Do the Agreed Numbers Come From?",
    "## 06:05 Which Differences Should We Preserve?",
    "## 07:30 Apply One Chosen Rule Consistently",
    "## 09:05 Put the Chosen Steps Into One Recipe",
    "## 11:40 Predict, Run, and Change the Starting Text",
    "## 13:30 Carry the Explanation Forward",
]
actual_headings = re.findall(r"^## \d{2}:\d{2} .+$", script, re.MULTILINE)
assert actual_headings == expected_headings

in_fence = False
spoken_blocks = []
paragraph = []

def flush():
    if paragraph:
        spoken_blocks.append(" ".join(paragraph))
        paragraph.clear()

for raw_line in script.splitlines():
    line = raw_line.strip()
    if line.startswith("```"):
        flush()
        in_fence = not in_fence
        continue
    if in_fence or not line:
        flush()
        continue
    if line.startswith(("#", "[", "---")):
        flush()
        continue
    item = re.match(r"^(?:>\s*|\d+[.)]\s+|[-+*]\s+)(.*)$", line)
    if item:
        flush()
        spoken_blocks.append(item.group(1))
    else:
        paragraph.append(line)
flush()

spoken = "\n".join(spoken_blocks)
word_count = len(re.sub(r"[*_`]", "", spoken).split())
assert 1800 <= word_count <= 1950, word_count

sentences = [
    sentence.strip()
    for block in spoken_blocks
    for sentence in re.split(
        r"(?<=[.!?])\s+",
        re.sub(r"[*_`]", "", block),
    )
    if sentence.strip()
]
long_sentences = [
    sentence for sentence in sentences if len(sentence.split()) > 40
]
assert not long_sentences, long_sentences

for term in (
    "large language model",
    "tokenizer",
    "token ID",
    "vocabulary",
    "embedding",
    "numerical vector",
    "neural network",
    "compatibility decomposition",
    "canonical composition",
):
    assert term.casefold() not in spoken.casefold(), term

required = [
    "How can we find out exactly what a piece of text contains and change it consistently before later AI work?",
    "In today’s examples, a code point is the fixed number Unicode uses to identify one character.",
    "NFKC can remove distinctions that matter",
    "python inspect_and_prepare_text.py",
    "Prepared text: 'Lesson 1: A cat ff\\nsecond line'",
    "'Chapter 2: Big office\\nfinal line'",
]
for text in required:
    assert text in script, text
PY
```

Expected: PASS with no output.

- [ ] **Step 5: Verify plausible section density**

Run:

```bash
python - <<'PY'
import re
from pathlib import Path

script = Path("final_final copy").read_text(encoding="utf-8")
matches = list(re.finditer(
    r"^## (?P<minutes>\d{2}):(?P<seconds>\d{2}) .+$",
    script,
    re.MULTILINE,
))
starts = [
    int(match.group("minutes")) * 60 + int(match.group("seconds"))
    for match in matches
]
ends = starts[1:] + [15 * 60]

for index, (match, start, end) in enumerate(
    zip(matches, starts, ends, strict=True)
):
    body_start = match.end()
    body_end = (
        matches[index + 1].start()
        if index + 1 < len(matches)
        else len(script)
    )
    body = script[body_start:body_end]
    body = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    body = re.sub(r"^\s*(?:#|\[|---).*$", "", body, flags=re.MULTILINE)
    words = len(body.split())
    words_per_minute = words * 60 / (end - start)
    assert 80 <= words_per_minute <= 145, (
        match.group(0),
        words_per_minute,
    )
PY
```

Expected: PASS with no output. If a section fails, rebalance narration or its
provisional timestamp without exceeding the 15-minute total.

- [ ] **Step 6: Run repository regression tests**

Run:

```bash
.venv/bin/pytest -q -p no:cacheprovider
```

Expected: the full collected suite passes.

- [ ] **Step 7: Verify the preservation boundary**

Run:

```bash
shasum -a 256 final_final
git status --short
```

Run:

```bash
python - <<'PY'
from pathlib import Path

path = Path("final_final copy")
bad_lines = [
    number
    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    )
    if line != line.rstrip()
]
assert not bad_lines, bad_lines
PY
```

Expected:

- the `final_final` hash exactly matches the value recorded in Task 1;
- the trailing-whitespace check passes;
- no unrelated file has been staged or modified by this implementation.

- [ ] **Step 8: Commit only the rewritten learner artifact**

Run:

```bash
git add -- "final_final copy"
git diff --cached --check
git diff --cached --stat
git commit -m "docs: rewrite final text preparation lesson"
```

Expected staged scope before commit:

```text
final_final copy
```

Expected: one commit containing only the rewritten lesson.
