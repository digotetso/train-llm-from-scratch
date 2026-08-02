# Final Video 1 Standalone Examples Revision Design

**Date:** 2026-07-23
**Status:** Approved in conversation on 2026-07-23

## Goal

Revise the final Video 1 script so a learner can understand and run every
example without knowing that a repository exists. Remove context-dependent
fragments, explain each concept before relying on its name, and use two small
Python files as direct evidence for the lesson.

The lesson continues to answer:

> How do computers represent and prepare text before AI can learn from it?

The revised lesson teaches:

1. character identification with Unicode code-point numbers;
2. text representation as UTF-8 byte numbers;
3. the difference between code points and bytes;
4. text preparation as a chosen sequence of fixed cleanup steps; and
5. NFKC as one specific normalization step within text preparation.

Repository ingestion, stored record fields, the complete data pipeline, and
the internal mechanisms of later AI training remain deferred.

## Source State And User Edits

The implementation source is the current working copy:

```text
course/templates/video/final_script_v1.md
```

Its approved pre-implementation SHA-256 is:

```text
4031ae35da3123c0022a0613b4ba55cf93716502173041f16d4bf50c4dc601be
```

That working copy contains user-authored changes that are not in `HEAD`.
Preserve their intent:

- use `split` rather than `divide`;
- include a messy-text stage direction;
- include a short Python-download stage direction;
- introduce the first Python check conversationally.

Correct their draft grammar and integrate them into the final causal flow.
Do not overwrite the working copy from `HEAD`.

## Artifact Design

Modify:

```text
course/templates/video/final_script_v1.md
```

Create:

```text
course/templates/video/character_representation.py
course/templates/video/text_preparation.py
tests/test_final_script_v1.py
```

Remove the superseded generic companion:

```text
course/templates/video/final_script_v1_lab.py
```

No media, video, audio, animation, image, font, render, browser capture, or
production project file belongs in this change.

## Learner Prerequisites

The learner can:

- install or launch Python;
- open a terminal in the folder containing a file;
- run `python filename.py`;
- read a string, a list of small numbers, a function call, and printed output;
- compare two short lists; and
- follow a short function from top to bottom.

The learner is not assumed to understand:

- repositories or data-ingestion code;
- Unicode normalization;
- tokenization or tokenizers;
- token IDs or embeddings;
- model terminology;
- regular expressions;
- Python type annotations; or
- the mathematics of AI training.

## Teaching Dependency Order

Every major concept follows this sequence:

```text
observable question
-> familiar text example
-> apparent mismatch
-> smallest fixed mechanism
-> learner prediction
-> accepted technical name
-> complete input-to-output trace
-> runnable evidence
-> likely misconception
-> compact mental model
-> named building block used by the next concept
```

The complete lesson chain is:

```text
written text
-> identify each example character with a code-point number
-> represent the text as an ordered UTF-8 byte sequence
-> choose and apply explicit cleanup steps
-> prepared text
-> later text and AI-learning steps [closed]
```

The later vocabulary preview may show this job-before-label sequence once:

```text
split prepared text into reusable pieces [tokens]
-> give each piece a number [token ID]
-> link that number to a learned list of numbers used to represent useful
   features of the token [embedding]
-> later AI-learning steps [closed]
```

Immediately state that these are names for later steps and have not yet been
explained. Do not expand their internal mechanisms in Video 1.

## Vocabulary And Wording Contract

Use:

- `split`, not `divide`;
- `number`, not `integer`;
- `preview` or `names for later steps`, not `signpost`;
- `non-negative number from 0 through 255`, not `unsigned value`;
- `fixed cleanup steps we chose`, not `preparation policy`;
- `character-numbering standard`, not `shared system`;
- `ordered UTF-8 byte sequence`, not `a byte stores part of its
  representation`.

Use this beginner-safe Unicode explanation:

> Unicode is a character-numbering standard. For each single character in
> today’s examples, it assigns a code-point number.

Add one short scope limit after the learner understands the example:

> Some visible symbols are built from several code points. We will leave that
> case for a later lesson.

Use this embedding preview:

> A later step gives each token a number called a token ID. That number is
> linked to an embedding—a learned list of numbers used to represent useful
> features of the token during later processing.

Add this limit:

> An embedding is not a dictionary definition of the token.

Do not use these words or phrases in learner-facing narration:

```text
repository
project
tokenization
tokenizer
signpost
unsigned
integer
preparation policy
shared system
model
parameter
```

Do not use `divide`, `divided`, or `dividing` for splitting text.

## Section Structure

Use this subtitle:

```text
How character numbers, UTF-8 bytes, and simple cleanup prepare written text
for later AI work
```

Preserve nine timestamped sections in this order:

```text
00:00 The Big Question and Today’s First Step
01:00 Where This Video Fits
03:00 Three Jobs Before Text Can Be Split into Pieces
04:20 Identifying Characters with Code-Point Numbers
05:50 Representing Text with UTF-8 Bytes
07:00 Preparing Text with Explicit Cleanup Steps
08:15 Build a Self-Contained Text-Preparation Example
10:45 Predict, Run, and Explain
13:20 Return to the Whole Route
```

### 00:00

Keep the familiar AI-output hook and central question. Replace the
repository-specific outcome with behavior the learner can demonstrate:

```text
trace how a short function normalizes and cleans an example string
```

Do not use token IDs or embeddings in the outcome list.

### 01:00

Use an ordinary-language route. Explain the later jobs before naming tokens,
token IDs, and embeddings. End with:

> These are names for later steps. We have not explained how they work yet, so
> we will leave them for later and focus on the three jobs in front of us.

### 03:00

Introduce only three current jobs:

```text
identify a character
represent text as bytes
apply explicit cleanup steps
```

Replace “Keep this boundary visible” with:

> These numbers are not interchangeable.

Do not repeat future vocabulary in this section.

Keep the user’s messy-text idea as a production note, rewritten clearly:

```text
[On screen: a short text sample with extra spaces, mixed line endings, ①,
and ﬀ]
```

### 04:20

Explain behavior before terminology:

```text
software needs a stable number for the example character
-> Unicode supplies the character-numbering standard
-> the assigned number is called a code point
```

Python’s `ord` function may be explained in speech, but do not leave a partial
Python program in the narration. The complete runnable evidence belongs to
`character_representation.py`.

Preserve the user’s setup note in corrected form:

```text
[On screen: If Python is not installed, visit
https://www.python.org/downloads/]
```

The Python-installation process itself is not part of this lesson.

### 05:50

Use:

> A byte is a small unit of storage. Python displays each byte as a
> non-negative number from `0` through `255`.

Explain that UTF-8 produces an ordered sequence of bytes used to store or send
the text. Compare `Cat` with `🐱`:

```text
Cat
code-point numbers -> [67, 97, 116]
UTF-8 byte numbers -> [67, 97, 116]

🐱
code-point numbers -> [128049]
UTF-8 byte numbers -> [240, 159, 144, 177]
```

The conclusion is:

```text
some code-point and byte values happen to match
-> the match is not a rule
-> one character can become several UTF-8 bytes
-> code points identify example characters
-> UTF-8 gives the byte sequence used to store or send the text
```

Do not introduce ASCII.

### 07:00

Begin with the messy text the learner can observe. Explain:

```text
we may choose to make known differences consistent
-> each choice is one fixed cleanup step
-> the full sequence of cleanup steps is text preparation
```

Explain normalization before NFKC:

> One possible cleanup step replaces certain special-looking characters with
> simpler equivalents. Changing text into a chosen standard form is called
> normalization.

Then name the specific rule:

> NFKC is the name of one Unicode normalization rule. In these examples, it
> changes `①` to `1` and `ﬀ` to `ff`.

Preserve both verified facts:

```text
① -> 1
length 1 -> 1

ﬀ -> ff
length 1 -> 2
```

State that normalization is one preparation step, not the whole job. State
that fixed cleanup steps can change or remove details from the original text.

### 08:15

Replace the incomplete repository function and stored-record fragments with
the complete `text_preparation.py` file. Explain `repr` before using its
output:

> `repr` makes hidden marks such as `\r\n` and surrounding spaces visible in
> the terminal.

Trace every operation:

```text
source string
-> NFKC normalization
-> split into lines using common line-ending markers
-> remove spaces around each line
-> remove empty lines
-> join the remaining lines with \n
-> prepared string
```

Explicitly say these are the choices in this example, not universal cleanup
rules. Text such as code or poetry may need different choices.

### 10:45

Use both standalone files in predict-run-explain loops:

```text
predict Cat and 🐱
-> run character_representation.py
-> observe
-> explain
-> change Cat to A
-> predict
-> run and compare

predict the messy string
-> run text_preparation.py
-> observe
-> trace each fixed step
-> change ① to Cat
-> predict which parts change and which remain
-> run and compare
```

Commands:

```bash
python character_representation.py
python text_preparation.py
```

Tell the learner to open the terminal in the folder containing the two files.
Do not use a course or repository path in either command.

### 13:20

Compress the lesson to:

```text
code-point number -> identifies an example character
UTF-8 byte sequence -> stores or sends the text
fixed cleanup step -> changes one chosen text feature
text preparation -> applies the chosen cleanup steps in order
```

Use a transfer exercise with `Cat`, `🐱`, `①`, `ﬀ`, surrounding spaces, and
line endings. Do not introduce `tokenizer`, measured error, parameters, or
other closed training mechanisms.

Build Video 2 from the code-point building block in ordinary language:

> Stable character numbers let software decide which characters belong in a
> collection. Video 2 asks how to build that collection dependably.

## Standalone File 1

`course/templates/video/character_representation.py` contains exactly:

```python
text = "Cat"
print("Text:", text)
print("Code-point numbers:", [ord(character) for character in text])
print("UTF-8 byte numbers:", list(text.encode("utf-8")))

print()

text = "🐱"
print("Text:", text)
print("Code-point numbers:", [ord(character) for character in text])
print("UTF-8 byte numbers:", list(text.encode("utf-8")))
```

Verified output:

```text
Text: Cat
Code-point numbers: [67, 97, 116]
UTF-8 byte numbers: [67, 97, 116]

Text: 🐱
Code-point numbers: [128049]
UTF-8 byte numbers: [240, 159, 144, 177]
```

## Standalone File 2

`course/templates/video/text_preparation.py` contains exactly:

```python
import unicodedata


def prepare_text(text):
    text = unicodedata.normalize("NFKC", text)
    lines = [line.strip() for line in text.splitlines()]
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines)


source = "  ① cat ﬀ  \r\n\r\n  second line  "

print("Source text:", repr(source))
print("Prepared text:", repr(prepare_text(source)))
```

Verified output:

```text
Source text: '  ① cat ﬀ  \r\n\r\n  second line  '
Prepared text: '1 cat ff\nsecond line'
```

## Automated Consistency Contract

Add `tests/test_final_script_v1.py`. It must verify:

1. the nine headings and order are exact;
2. the script has 2,000–2,250 whitespace-delimited words;
3. every spoken sentence is at most forty words;
4. learner-facing narration contains none of the prohibited words;
5. the two Python files appear exactly in Python fences;
6. the two local commands appear exactly;
7. running each file produces the displayed output exactly;
8. `Cat`, `🐱`, `A`, `①`, and `ﬀ` predictions are correct;
9. NFKC and `repr` are explained before their output is interpreted;
10. no course or repository path appears in a learner command.

Run the focused new contract, the existing course contract, and the complete
repository test suite. Separately inspect the committed path list and reject
any media or production file.

## Preservation Boundary

Do not modify:

- `course/videos/001-computer-learning-from-text/`;
- `course/video_1_script_4.md`;
- `course/video_1_improved_script.md`;
- `script_video1_draft.md`;
- `.playwright-mcp/`;
- repository source outside the two standalone examples;
- existing tests other than adding the new focused contract; or
- any media or production file.

The current dirty working tree belongs to the user. Stage explicit paths only
and verify the staged name list before every commit.

Implement in a task-owned worktree. Reproduce the approved dirty script
snapshot there before revising it. If the primary script hash changes before
implementation begins, stop, preserve the newer user state, and update the
baseline instead of overwriting it. After review and merged-state verification,
merge the finished branch into local `main` and remove only the task-owned
worktree and branch.

## Acceptance Criteria

The revision is complete when:

1. a learner can understand the script without knowing what a repository is;
2. every technical name follows an ordinary-language job explanation;
3. `Cat` and `🐱` clearly demonstrate that code points and UTF-8 bytes are
   different kinds of numbers;
4. NFKC is explained behavior-first and demonstrated by runnable code;
5. text preparation is clearly larger than normalization;
6. both standalone files run independently with exact displayed output;
7. the script remains conversational, causal, and within its length limits;
8. the learner predicts before each revealed result and tests a changed case;
9. the recap produces reusable building blocks instead of a list of terms;
10. the user’s in-progress edits are preserved in polished form;
11. focused and full tests pass; and
12. the final committed scope contains no media.
