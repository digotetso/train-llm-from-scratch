# Thirteen-Minute Video 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compress the approved 27:50 Video 1 source into a conversational, causally complete 12:30–13:30 lesson with one runnable Python lab.

**Architecture:** Treat the untracked main-checkout script as a protected content source and edit only the tracked `final_final copy` artifact in the isolated worktree. Consolidate 24 sections into eight dependency-ordered sections, preserve one complete inspection-and-preparation mechanism, and validate narration, timing, terminology, Python evidence, source preservation, and repository regressions before branch completion.

**Tech Stack:** Markdown, Python 3 standard library, `unicodedata`, Git, pytest.

## Global Constraints

- Use `/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/final_final copy` as the long content source.
- Preserve that main-checkout source at SHA-256 `d2fe39c1250de1c679232a5bfa118966b3d05e04e0cd63c25395dbf00f6b8441` throughout implementation and review.
- Modify only the isolated worktree’s tracked `final_final copy` during the narration rewrite.
- Preserve the protected `final_final` artifact at SHA-256 `58545849266136ee72773936ca814bb074fcb009ca1720c9bf687a517b34bbd5`.
- Do not modify the main checkout, course scripts, tests, media, animation, rendering, or production files.
- Target an endpoint of approximately `13:00`, within an acceptable range of 12:30–13:30.
- Target 1,550–1,700 spoken words across exactly eight timed sections.
- Keep every section between 105 and 145 spoken words per minute, using `13:00` as the final endpoint.
- Keep every spoken sentence at 40 words or fewer.
- Preserve the familiar AI hook, the from-scratch course context, and the compact LLM-label explanation.
- Explain an organized collection of learning examples before naming **training dataset**.
- Explain why later mathematical operations require numbers without teaching the deferred conversion mechanism.
- Explain observable behavior before naming **string**, **whitespace**, **inspection**, **character**, **Unicode**, **code point**, **normalization**, **NFKC**, or the Python operations used by the complete function.
- State that Unicode code points identify characters and are not the later numbers used to train the LLM.
- Use `①`/`1`, `Ａ`/`A`, and `ﬀ`/`ff` as the similar-form evidence.
- Describe every preparation rule as a purpose-dependent choice, not a universal correction.
- Preserve one complete standalone lab, its exact observed output, and one changed-input transfer case.
- Keep `tokenizer`, `token`, `token ID`, `vocabulary`, `embedding`, `vector`, `neural network`, compatibility decomposition, and canonical composition out of spoken narration.
- Do not add media or video files.
- Before any eventual local merge, preserve the original long source recoverably as `final_final copy.pre-13-minute-original.md`; that merge-preservation action is outside implementation and must not occur during these tasks.

---

### Task 1: Establish The Protected Source And Failing Compression Contract

**Files:**
- Read: `/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/final_final copy`
- Read: `final_final copy`
- Read: `final_final`
- Read: `docs/superpowers/specs/2026-07-24-thirteen-minute-video-one-design.md`
- Modify: none

**Interfaces:**
- Consumes: long source SHA-256 `d2fe39c1250de1c679232a5bfa118966b3d05e04e0cd63c25395dbf00f6b8441`
- Consumes: current worktree target SHA-256 `d72ebb522ee6621a59fa7eda4bfe9c4a32f596794344a05cb6417688c0001a3e`
- Produces: a verified preservation baseline and an intentionally failing 13-minute narration contract

- [ ] **Step 1: Verify the three protected starting artifacts**

Run:

```bash
shasum -a 256 \
  "/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/final_final copy" \
  "final_final copy" \
  final_final
```

Expected:

```text
d2fe39c1250de1c679232a5bfa118966b3d05e04e0cd63c25395dbf00f6b8441  /Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/final_final copy
d72ebb522ee6621a59fa7eda4bfe9c4a32f596794344a05cb6417688c0001a3e  final_final copy
58545849266136ee72773936ca814bb074fcb009ca1720c9bf687a517b34bbd5  final_final
```

- [ ] **Step 2: Verify the long source is the 27:50 artifact**

Run:

```bash
python - <<'PY'
import re
from pathlib import Path

path = Path(
    "/Users/digotetsomatema/AI-Projects-2026/"
    "train-llm-from-scratch/final_final copy"
)
script = path.read_text(encoding="utf-8")
headings = re.findall(
    r"^## (?P<time>\d{2}:\d{2}) (?P<title>.+)$",
    script,
    flags=re.MULTILINE,
)

assert len(headings) == 24, len(headings)
assert headings[-1][0] == "27:50", headings[-1]
assert headings[-1][1] == "Code Points Are Not Token IDs", headings[-1]
print(
    "protected long source: PASS "
    f"({len(headings)} sections; last timestamp {headings[-1][0]})"
)
PY
```

Expected:

```text
protected long source: PASS (24 sections; last timestamp 27:50)
```

- [ ] **Step 3: Verify the index is empty**

Run:

```bash
git diff --cached --name-only
git status --short
```

Expected:

- `git diff --cached --name-only` produces no output.
- `final_final` may appear as the known pre-existing untracked protected artifact.
- No main-checkout path is modified.

- [ ] **Step 4: Run the deliberately failing compression contract**

Run:

```bash
python - <<'PY'
import re
from pathlib import Path

script = Path("final_final copy").read_text(encoding="utf-8")
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
    item = re.match(
        r"^(?:>\s*|\d+[.)]\s+|[-+*]\s+)(.*)$",
        line,
    )
    if item:
        flush()
        spoken_blocks.append(item.group(1))
    else:
        paragraph.append(line)
flush()

spoken = "\n".join(spoken_blocks)
word_count = len(re.sub(r"[*_`]", "", spoken).split())
headings = re.findall(
    r"^## (?P<time>\d{2}:\d{2}) (?P<title>.+)$",
    script,
    flags=re.MULTILINE,
)

failures = []
if not 1550 <= word_count <= 1700:
    failures.append(f"spoken words: {word_count}")
if len(headings) != 8:
    failures.append(f"timed sections: {len(headings)}")
if headings[-1][0] != "12:10":
    failures.append(f"last timestamp: {headings[-1][0]}")

assert not failures, failures
PY
```

Expected: FAIL. The failure list must include at least:

```text
spoken words: 1908
timed sections: 9
last timestamp: 14:05
```

This is the correct red state: the current branch artifact is accurate but
still sits at the 15-minute ceiling rather than the approved 13-minute target.

---

### Task 2: Build And Verify The Thirteen-Minute Lesson

**Files:**
- Modify: `final_final copy`
- Reference: `/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/final_final copy`
- Reference: `docs/superpowers/specs/2026-07-24-thirteen-minute-video-one-design.md`

**Interfaces:**
- Consumes: the long source’s topic coverage, the reviewed branch lesson’s terminology order, and the protected Python inputs and outputs
- Produces: an eight-section Markdown lesson ending at `13:00`, with 1,550–1,700 spoken words and one runnable explicit-loop lab

- [ ] **Step 1: Preserve the title while removing future terminology from the subtitle**

Use:

```markdown
# Video 1 — Before AI Can Learn: How Computers Represent and Prepare Text

**Subtitle:** How to inspect source text, understand character identities, and prepare consistent text before later AI work
```

Do not use `tokenization`, `tokenizer`, `token ID`, `embedding`, or
`neural network` in the title or subtitle.

- [ ] **Step 2: Replace the 24-section structure with these exact eight headings**

Use:

```markdown
## 00:00 The Text Looks Simple
## 02:20 Reveal What Is Really There
## 03:45 Similar-Looking Text Can Still Be Different
## 05:00 The Numbers Identify Characters
## 06:25 Choose Which Differences to Change
## 08:00 Put the Preparation Steps Together
## 10:20 Predict, Run, and Change the Source
## 12:10 Carry the Explanation Forward
```

The intended endpoint is `13:00`.

- [ ] **Step 3: Write the opening as one causal bridge**

The `00:00` section must contain, in this order:

1. the familiar experience of using AI to improve an email, reshape text, or
   suggest code;
2. the small source-text mystery;
3. this exact question:

   ```markdown
   How do we take writing like this and eventually use it to train an LLM?
   ```

4. the exact from-scratch boundary:

   ```markdown
   In this course, we are training an LLM from scratch, before those familiar abilities exist.
   ```

5. this compact LLM-label explanation:

   ```markdown
   For now, LLM names the system we are building; we will explain its technical meaning later.
   ```

6. the behavior-level explanation of many organized text examples, followed
   by the name **training dataset**;
7. the whole-course map in ordinary language:

   ```text
   collect writing
   → organize the training dataset
   → inspect and prepare the text
   → split it into pieces
   → give the pieces numbers
   → create learning exercises
   → build an adjustable mathematical system
   → improve it through practice
   → test the result
   ```

8. the reason text eventually needs numerical representation:

   ```markdown
   The system performs mathematical operations, and those operations work with numbers.
   ```

9. the boundary:

   ```markdown
   But “turn text into numbers” is not one step.
   ```

10. the concrete messy-source examples: extra spaces, tabs, repeated blank
    lines, different line boundaries, hidden marks, and different symbols used
    for the same intended role;
11. the purpose-dependent caveat that not every difference is an error; and
12. this exact lesson question:

    ```markdown
    **How can we find out exactly what a piece of text contains and change it consistently before later AI work?**
    ```

Keep this section between 270 and 320 spoken words. Use paragraphs and causal
questions, not a spoken list of independent claims.

- [ ] **Step 4: Compress inspection into one prediction-and-evidence section**

The `02:20` section must:

- introduce the unchanged starting text as **source text**, then **source**;
- explain quotation marks before naming the stored value a **string**;
- explain `\t`, `\r\n`, and `=` before showing the assignment;
- use this exact source:

  ```python
  source = "  Lesson ①: Ａ cat ﬀ  \r\n\r\n\tsecond line  "
  ```

- ask what normal printing might hide before naming `repr`;
- show:

  ```python
  print(repr(source))
  ```

- preserve the exact output:

  ```text
  '  Lesson ①: Ａ cat ﬀ  \r\n\r\n\tsecond line  '
  ```

- explain the evidence before naming **whitespace** and **inspection**; and
- state that inspection reveals the source without changing it.

Keep this section between 160 and 200 spoken words.

- [ ] **Step 5: Combine the similar-form evidence before naming the mechanism**

The `03:45` section must show:

```text
①    1
Ａ    A
ﬀ    ff
```

Ask the learner to predict whether similar appearance or intended use forces
software to store both sides identically. Then explain that Python can ask for
the agreed number used to identify one stored character and name the tool
`ord`.

Use:

```python
print(ord("①"))
print(ord("1"))
```

Preserve:

```text
9312
49
```

Only after the numbers differ, name a stored written symbol a **character**.
State that the result proves different identities but does not decide which
form is better or whether either should change.

Keep this section between 150 and 180 spoken words.

- [ ] **Step 6: Name Unicode and code points, then close the category boundary**

The `05:00` section must:

- explain the need for a shared character-identification agreement before
  naming **Unicode**;
- name one character’s fixed identifying number a **code point**;
- define the code point narrowly as an identifier, not a meaning;
- preserve:

  ```text
  ① -> 9312
  1 -> 49

  Ａ -> 65313
  A -> 65

  ﬀ -> [64256]
  ff -> [102, 102]
  ```

- state:

  ```markdown
  `ord` receives one character at a time and returns that character’s code point here.
  ```

- state:

  ```markdown
  `ff` deliberately contains two characters and therefore two code points.
  ```

- include this category boundary:

  ```markdown
  A code point identifies a character. It is not the later kind of number used to train the LLM.
  ```

Do not explain the deferred training-number mechanism.

Keep this section between 160 and 200 spoken words.

- [ ] **Step 7: Merge policy, normalization, length change, and caveat**

The `06:25` section must:

- ask which differences should remain distinct for this source;
- choose the ordinary digit `1`, basic letter `A`, and two separate letters
  `ff`;
- state that the choice is purpose-dependent and that code, poetry,
  mathematical notation, or historical text may need to preserve differences;
- show the behavior:

  ```text
  ① -> 1
  Ａ -> A
  ﬀ -> ff
  ```

- name the repeatable selected transformation **normalization** only after
  showing the behavior;
- name **NFKC** as the selected rule for this example;
- preserve:

  ```text
  ① -> 1
  length 1 -> 1

  ﬀ -> ff
  length 1 -> 2
  ```

- warn that NFKC can remove distinctions that matter and is not a universal
  definition of clean or correct text; and
- use the understood normalization rule with the line and whitespace choices
  to introduce the building block **text preparation**.

Do not expand `NFKC` into compatibility decomposition or canonical
composition.

Keep this section between 180 and 220 spoken words.

- [ ] **Step 8: Trace the preparation mechanism before showing the whole program**

The `08:00` section must trace these exact states:

After NFKC and line separation:

```text
['  Lesson 1: A cat ff  ', '', '\tsecond line  ']
```

After trimming and empty-line removal:

```text
['Lesson 1: A cat ff', 'second line']
```

Explain behavior before naming each Python handle:

- ordered group, then **list**;
- line separation, then `splitlines`;
- repeated instructions, then **loop**;
- remove end whitespace, then `strip`;
- retain a non-empty line, then `if line != ""`;
- add a retained line, then `append`;
- rebuild with one separator, then `join`;
- named reusable instructions, then **function**, `def`, parameter, and
  `return`.

Then show this exact standalone program:

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

End with the causal trace:

```text
source
→ NFKC changes the selected forms
→ split into three lines
→ remove surrounding whitespace
→ reject the empty line
→ keep two lines
→ join them with one \n
→ return the prepared string
```

State precisely that the source used `\r\n` at two line boundaries, while
`splitlines` removed those boundary marks and `join` inserted one `\n` between
the surviving lines.

Keep this section between 280 and 330 spoken words.

- [ ] **Step 9: Keep one complete predict-run-transfer loop**

The `10:20` section must:

- tell the learner to save the complete program as
  `inspect_and_prepare_text.py`;
- ask for a complete prediction before execution;
- run:

  ```bash
  python inspect_and_prepare_text.py
  ```

- preserve:

  ```text
  Source text: '  Lesson ①: Ａ cat ﬀ  \r\n\r\n\tsecond line  '
  Prepared text: 'Lesson 1: A cat ff\nsecond line'
  ```

- explain every change using the already named operations;
- change only the source to:

  ```python
  source = "  Chapter ②: Ｂig oﬀice  \n\n  final line  "
  ```

- ask for a second prediction;
- preserve:

  ```text
  'Chapter 2: Big office\nfinal line'
  ```

- explain that the changed input tests whether the causal model transfers
  rather than whether the learner memorized the first output.

Keep this section between 220 and 260 spoken words.

- [ ] **Step 10: End with a compact mental model and building block**

The `12:10` section must:

- answer the central question;
- distinguish identification from preparation:

  ```markdown
  Identification tells us what is present. Preparation applies our purpose-dependent decisions.
  ```

- compress the sequence to:

  ```text
  source
  → inspect
  → identify relevant differences
  → choose rules for the purpose
  → apply and test those rules
  → prepared text
  ```

- prevent the common mistake that every real difference should disappear;
- state that prepared text is now the dependable building block for the next
  lesson; and
- avoid naming the deferred next mechanism.

Keep this section between 90 and 120 spoken words.

- [ ] **Step 11: Run the green narration, timing, terminology, and structure contract**

Run:

```bash
python - <<'PY'
import re
from pathlib import Path

script = Path("final_final copy").read_text(encoding="utf-8")
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
    item = re.match(
        r"^(?:>\s*|\d+[.)]\s+|[-+*]\s+)(.*)$",
        line,
    )
    if item:
        flush()
        spoken_blocks.append(item.group(1))
    else:
        paragraph.append(line)
flush()

spoken = "\n".join(spoken_blocks)
plain_spoken = re.sub(r"[*_`]", "", spoken)
word_count = len(plain_spoken.split())
assert 1550 <= word_count <= 1700, word_count

sentences = [
    sentence.strip()
    for block in spoken_blocks
    for sentence in re.split(
        r"(?<=[.!?])\s+",
        re.sub(r"[*_`]", "", block),
    )
    if sentence.strip()
]
too_long = [
    (len(sentence.split()), sentence)
    for sentence in sentences
    if len(sentence.split()) > 40
]
assert not too_long, too_long

expected_headings = [
    "00:00 The Text Looks Simple",
    "02:20 Reveal What Is Really There",
    "03:45 Similar-Looking Text Can Still Be Different",
    "05:00 The Numbers Identify Characters",
    "06:25 Choose Which Differences to Change",
    "08:00 Put the Preparation Steps Together",
    "10:20 Predict, Run, and Change the Source",
    "12:10 Carry the Explanation Forward",
]
headings = re.findall(
    r"^## (?P<time>\d{2}:\d{2}) (?P<title>.+)$",
    script,
    flags=re.MULTILINE,
)
actual_headings = [
    f"{time} {title}"
    for time, title in headings
]
assert actual_headings == expected_headings, actual_headings

required = [
    "How do we take writing like this and eventually use it to train an LLM?",
    "training an LLM from scratch",
    "we call the collection a **training dataset**",
    "mathematical operations",
    "those operations work with numbers",
    "“turn text into numbers” is not one step",
    "A code point identifies a character",
    "not the later kind of number used to train the LLM",
    "`ord` receives one character at a time",
    "`ff` deliberately contains two characters",
    "NFKC can remove distinctions that matter",
    "Identification tells us what is present",
    "Preparation applies our purpose-dependent decisions",
    "①    1",
    "Ａ    A",
    "ﬀ    ff",
    "Source text: '  Lesson ①: Ａ cat ﬀ  \\r\\n\\r\\n\\tsecond line  '",
    "Prepared text: 'Lesson 1: A cat ff\\nsecond line'",
    "'Chapter 2: Big office\\nfinal line'",
]
missing = [
    text
    for text in required
    if text.casefold() not in script.casefold()
]
assert not missing, missing

prohibited = [
    "large language model",
    "tokenizer",
    "token",
    "token ID",
    "vocabulary",
    "embedding",
    "vector",
    "neural network",
    "compatibility decomposition",
    "canonical composition",
]
found = [
    term
    for term in prohibited
    if re.search(
        rf"(?<!\w){re.escape(term)}(?!\w)",
        plain_spoken,
        flags=re.IGNORECASE,
    )
]
assert not found, found

matches = list(re.finditer(
    r"^## (?P<minutes>\d{2}):(?P<seconds>\d{2}) .+$",
    script,
    re.MULTILINE,
))
starts = [
    int(match.group("minutes")) * 60
    + int(match.group("seconds"))
    for match in matches
]
ends = starts[1:] + [13 * 60]
densities = []
for index, (match, start, end) in enumerate(
    zip(matches, starts, ends, strict=True)
):
    body_end = (
        matches[index + 1].start()
        if index + 1 < len(matches)
        else len(script)
    )
    body = script[match.end():body_end]
    body = re.sub(
        r"```.*?```",
        "",
        body,
        flags=re.DOTALL,
    )
    body = re.sub(
        r"^\s*(?:#|\[|---).*$",
        "",
        body,
        flags=re.MULTILINE,
    )
    words = len(body.split())
    words_per_minute = words * 60 / (end - start)
    assert 105 <= words_per_minute <= 145, (
        match.group(0),
        words_per_minute,
    )
    densities.append(round(words_per_minute, 1))

print(
    "compressed narration: PASS "
    f"({word_count} words; "
    f"max sentence {max(len(s.split()) for s in sentences)}; "
    f"WPM {densities})"
)
PY
```

Expected: PASS with 1,550–1,700 spoken words, eight exact headings, no sentence
over 40 words, no prohibited spoken terms, and eight section densities within
105–145 WPM.

- [ ] **Step 12: Execute the code-point, preparation, and transfer evidence**

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


assert ord("①") == 9312
assert ord("1") == 49
assert ord("Ａ") == 65313
assert ord("A") == 65
assert [ord(character) for character in "ﬀ"] == [64256]
assert [ord(character) for character in "ff"] == [102, 102]

assert unicodedata.normalize("NFKC", "①") == "1"
assert unicodedata.normalize("NFKC", "Ａ") == "A"
assert unicodedata.normalize("NFKC", "ﬀ") == "ff"
assert len("ﬀ") == 1
assert len(unicodedata.normalize("NFKC", "ﬀ")) == 2

source = "  Lesson ①: Ａ cat ﬀ  \r\n\r\n\tsecond line  "
transfer = "  Chapter ②: Ｂig oﬀice  \n\n  final line  "

assert repr(prepare_text(source)) == (
    "'Lesson 1: A cat ff\\nsecond line'"
)
assert repr(prepare_text(transfer)) == (
    "'Chapter 2: Big office\\nfinal line'"
)

print("code-point and preparation evidence: PASS")
PY
```

Expected:

```text
code-point and preparation evidence: PASS
```

- [ ] **Step 13: Perform the teaching-order and spoken-flow review**

Read the complete artifact aloud and verify all of the following:

```text
real question → familiar experience → apparent mystery
→ smallest mechanism → learner prediction → technical name
→ complete causal trace → tiny executable evidence
→ intelligent-beginner boundary → compact mental model
→ prepared-text building block
```

Reject and revise any paragraph that:

- sounds like independent bullet points read aloud;
- introduces a technical term before its behavior;
- repeats a conclusion without advancing the causal chain;
- removes a required cause in order to save words;
- implies that code points are training numbers;
- presents NFKC or blank-line removal as universally correct; or
- names the deferred next mechanism.

Confirm that every section’s conclusion creates the next section’s question.

- [ ] **Step 14: Verify preservation, scope, whitespace, and regressions**

Run:

```bash
shasum -a 256 \
  "/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/final_final copy" \
  final_final
git diff --check
git status --short
../../.venv/bin/pytest -q -p no:cacheprovider
```

Expected:

- the long source remains
  `d2fe39c1250de1c679232a5bfa118966b3d05e04e0cd63c25395dbf00f6b8441`;
- `final_final` remains
  `58545849266136ee72773936ca814bb074fcb009ca1720c9bf687a517b34bbd5`;
- `git diff --check` produces no output;
- only the isolated worktree’s `final_final copy` is modified by the rewrite;
- the known untracked protected `final_final` may remain visible; and
- all 239 repository tests pass.

- [ ] **Step 15: Commit only the compressed learner artifact**

Run:

```bash
git add -- "final_final copy"
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: compress video one to thirteen minutes"
```

Expected staged path:

```text
final_final copy
```

Do not stage the long main-checkout source, `final_final`, the design
specification, this plan, media, or any production artifact in this commit.
