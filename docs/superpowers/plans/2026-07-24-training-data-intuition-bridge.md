# Training-Data Intuition Bridge Implementation Plan

> **Superseded status — do not apply to the current artifact.** This historical
> plan is superseded by the
> [Thirteen-Minute Video 1 Compression Design](../specs/2026-07-24-thirteen-minute-video-one-design.md)
> and the [Thirteen-Minute Video 1 Implementation Plan](2026-07-24-thirteen-minute-video-one.md).
> Its older 15-minute/nine-section/1,800–1,950-word validators are historical
> and must not be applied to the current artifact.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the approved training-dataset and text-to-numbers intuition into `final_final copy` while preserving the existing hook, keeping Video 1 focused on text inspection and preparation, and preventing code-point identifiers from being mistaken for LLM training numbers.

**Architecture:** Modify one self-contained Markdown narration artifact. Preserve the familiar hook, add a short course-level causal bridge, strengthen the similar-character comparison, and add an explicit boundary after code points are understood; do not open the deferred mechanisms that split prepared text or assign later training numbers.

**Tech Stack:** Markdown, Python 3 standard library, `unicodedata`, `pytest`, Git.

## Global Constraints

- Modify only `final_final copy` during narration implementation.
- Preserve `final_final`, course scripts, tests, media, animation, rendering, and production files.
- Preserve the existing familiar-experience hook and small-text mystery.
- Explain the organized collection of learning examples before naming **training dataset**.
- Explain why mathematical operations require numerical representations without teaching the deferred conversion mechanism.
- State that Unicode code points identify characters and are not the later numbers used to train the LLM.
- Keep `tokenizer`, `token`, `token ID`, `vocabulary`, `embedding`, `vector`, `neural network`, compatibility decomposition, and canonical composition out of spoken narration.
- Use the comparisons `①`/`1`, `Ａ`/`A`, and `ﬀ`/`ff`.
- Describe source inconsistencies as choices that depend on purpose, not as universal errors.
- Keep the complete standalone Python lab and its observed outputs unchanged unless a verified defect requires correction.
- Target 1,800-1,950 spoken words, approximately 15 minutes, no spoken sentence over 40 words, and 80-145 spoken words per minute per section.
- Do not add media or production files.

---

### Task 1: Establish The New Teaching Contract

**Files:**
- Read: `final_final copy`
- Read: `final_final`
- Read: `docs/superpowers/specs/2026-07-24-final-final-copy-teaching-rewrite-design.md`
- Modify: none

**Interfaces:**
- Consumes: target SHA-256 `8ff06138182c8924f3685d002aa9f2e8949e22cac4fdf513f6ee7cbca41c5ac8`
- Produces: a verified preservation baseline and an intentionally failing training-intuition contract

- [ ] **Step 1: Verify the approved target and protected reference**

Run:

```bash
shasum -a 256 "final_final copy" final_final
```

Expected:

```text
8ff06138182c8924f3685d002aa9f2e8949e22cac4fdf513f6ee7cbca41c5ac8  final_final copy
58545849266136ee72773936ca814bb074fcb009ca1720c9bf687a517b34bbd5  final_final
```

- [ ] **Step 2: Verify that no unrelated path is staged**

Run:

```bash
git status --short
git diff --cached --name-only
```

Expected: `final_final` may appear as the pre-existing untracked protected
artifact; the staged-path command produces no output.

- [ ] **Step 3: Run the deliberately failing bridge contract**

Run:

```bash
python - <<'PY'
from pathlib import Path

script = Path("final_final copy").read_text(encoding="utf-8")

required = [
    "How do we take writing like this and eventually use it to train an LLM?",
    "we call the collection a **training dataset**",
    "mathematical operations",
    "those operations work with numbers",
    "“Turn text into numbers” is not one step",
    "not the later numbers used to train the LLM",
    "web pages, books, code, and other sources",
    "extra spaces",
    "repeated blank lines",
    "different ways of ending lines",
    "A quote style, dash, space, or symbol",
]

missing = [text for text in required if text not in script]
assert not missing, missing
PY
```

Expected: FAIL with a list that includes at least `training dataset`,
`mathematical operations`, and the code-point-versus-training-number boundary.

---

### Task 2: Integrate The Course-Level Intuition And Character Evidence

**Files:**
- Modify: `final_final copy`
- Reference: `docs/superpowers/specs/2026-07-24-final-final-copy-teaching-rewrite-design.md`

**Interfaces:**
- Consumes: the existing familiar hook, LLM label boundary, source example, `repr` inspection, and code-point lesson
- Produces: a compact causal bridge from collected writing to a prepared training dataset, plus a clear identifier-versus-training-number distinction

- [ ] **Step 1: Preserve the familiar hook verbatim**

Keep these opening paragraphs:

```markdown
You may have pasted text into an AI tool to improve an email, reshape a paragraph, or suggest code. To us, the text can look simple: a few words, a blank line, perhaps an unusual symbol. Yet the software receives every mark that was entered, including marks our eyes may skip over.

This sample gives us a useful mystery. We can see spaces around the words, an empty line, a circled number, a wide letter, and a joined-looking symbol. There is also a mark before the second line that creates a gap but is difficult to see. Some marks even look interchangeable although software can tell them apart.
```

- [ ] **Step 2: Add the polished training-data intuition after the hook**

Use this narration as the source text for the bridge, shortening only where the
final spoken-word or density validators require it:

```markdown
Large collections used for training may combine writing from web pages, books, code, and other sources. Alongside what we see here, they can contain extra spaces, tabs, repeated blank lines, different ways of ending lines, hidden marks, or several symbols used for the same intended role.

Now let’s place that mystery inside the larger goal. How do we take writing like this and eventually use it to train an LLM?

Training needs many text examples arranged so the system can learn from them. Once those examples are organized, we call the collection a **training dataset**.

Here is the whole-course map, not a full explanation. We collect writing, organize the training dataset, inspect and prepare the text, split it into pieces, give the pieces numbers, create learning exercises, and then train and test the system. Each later stage has a proper technical name. We will introduce each name only after its behavior makes sense.

Why must the text eventually become numbers? The system we are building performs mathematical operations, and those operations work with numbers. Therefore, a later stage must represent the writing using numbers.

But “turn text into numbers” is not one step. This video focuses on what must happen before we split the text and give its pieces numbers. We first reveal exactly what the collected text contains, decide which differences matter for our purpose, and apply those decisions consistently. That gives the next stage reliable starting material.

Not every difference is an error. A quote style, dash, space, or symbol may be meaningful in one collection and accidental in another. That is why we inspect first and change only according to a stated purpose.
```

Retain the existing lesson question after this bridge:

```markdown
So here is our question: **How can we find out exactly what a piece of text contains and change it consistently before later AI work?**
```

- [ ] **Step 3: Expand the prediction comparison without teaching future mechanisms**

Before the first `ord` result, use this compact comparison:

```text
①    1
Ａ    A
ﬀ    ff
```

Use conversational reasoning with this behavior-first sequence:

```markdown
A reader can understand the intended role of each pair. But does similar appearance or use force software to store both sides as the same character? Pause for a prediction.

Python can ask for the agreed number used to identify one stored character. It calls this tool `ord`. We will begin with the circled and ordinary forms of one.
```

Keep the existing `ord("①")`, `ord("1")`, `9312`, and `49` evidence before
introducing Unicode or code point.

- [ ] **Step 4: Add the identifier-versus-training-number boundary**

Immediately after code point has been explained and named, add:

```markdown
Keep one boundary clear. A code point number identifies a character. It is useful here because it proves that two similar-looking forms can be different stored characters. It is not yet the kind of number used to train the LLM. A later lesson will explain how prepared text becomes those training numbers.
```

Do not mention tokens, token IDs, vocabularies, embeddings, or vectors.

- [ ] **Step 5: Make the selected consistency choices concrete**

In the preservation-decision section, state:

```markdown
For this lesson’s purpose, we choose the ordinary digit `1`, the basic letter `A`, and the two separate letters `ff`. That is a choice for this source—not proof that the other forms are universally wrong.
```

Retain the existing immediate warning that code, poetry, mathematical notation,
or historical text may require preserving a distinction.

- [ ] **Step 6: Rebalance without sacrificing the causal bridge**

Remove repeated big-picture wording that the new bridge replaces. Preserve all
mechanisms and prediction pauses. Adjust only provisional timestamp numbers if
needed to keep every section between 80 and 145 spoken words per minute and
the complete lesson at approximately 15 minutes.

---

### Task 3: Verify Terminology, Facts, Executable Evidence, Timing, And Scope

**Files:**
- Verify: `final_final copy`
- Protect: `final_final`
- Verify repository tests without modifying them

**Interfaces:**
- Consumes: the integrated narration from Task 2
- Produces: evidence that the lesson is accurate, compact, runnable, and isolated

- [ ] **Step 1: Run the final narration and intuition contract**

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
assert not [
    sentence for sentence in sentences if len(sentence.split()) > 40
]

required = [
    "How do we take writing like this and eventually use it to train an LLM?",
    "we call the collection a **training dataset**",
    "mathematical operations",
    "those operations work with numbers",
    "“turn text into numbers” is not one step",
    "not yet the kind of number used to train the LLM",
    "web pages, books, code, and other sources",
    "①    1",
    "Ａ    A",
    "ﬀ    ff",
]
for text in required:
    assert text.casefold() in script.casefold(), text

for term in (
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
PY
```

Expected: PASS with no output.

- [ ] **Step 2: Verify plausible section density**

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

assert len(matches) == 9, len(matches)
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

Expected: PASS with no output.

- [ ] **Step 3: Execute the complete preparation and transfer cases**

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

assert repr(prepare_text(source)) == "'Lesson 1: A cat ff\\nsecond line'"
assert repr(prepare_text(
    "  Chapter ②: Ｂig oﬀice  \n\n  final line  "
)) == "'Chapter 2: Big office\\nfinal line'"
PY
```

Expected: PASS with no output.

- [ ] **Step 4: Verify hashes, whitespace, scope, and regression tests**

Run:

```bash
shasum -a 256 final_final
git diff --check
git status --short
../../.venv/bin/pytest -q -p no:cacheprovider
```

Expected:

- `final_final` remains
  `58545849266136ee72773936ca814bb074fcb009ca1720c9bf687a517b34bbd5`;
- `git diff --check` produces no output;
- only `final_final copy` is modified by the narration implementation;
- all 239 tests pass.

- [ ] **Step 5: Commit only the learner artifact**

Run:

```bash
git add -- "final_final copy"
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: add training-data intuition to video one"
```

Expected staged path:

```text
final_final copy
```
