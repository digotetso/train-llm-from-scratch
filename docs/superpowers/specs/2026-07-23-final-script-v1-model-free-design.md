# Final Video 1 Script Model-Free Revision Design

**Date:** 2026-07-23
**Status:** Approved in conversation on 2026-07-23

## Goal

Revise the user's final Video 1 narration so it no longer uses **model** before
that concept has been taught. The word and its related compound phrases will be
deferred throughout the entire video, not merely in the opening.

The revised lesson will continue to answer:

> How do computers represent and prepare text before AI can learn from it?

It will teach only the mechanisms needed for that answer: Unicode code points,
UTF-8 bytes, and the repository's text-preparation policy. Later training
mechanisms remain visible only as brief, closed roadmap signposts.

## Source And Artifacts

Modify the user's current final narration:

```text
course/templates/video/final_script_v1.md
```

Create one self-contained companion lab:

```text
course/templates/video/final_script_v1_lab.py
```

The source narration currently contains 2,149 whitespace-delimited words and
nine timestamped sections. Its pre-revision SHA-256 is:

```text
0b8723d48353e80c8915326e232a44566c8151fb776d5412c4ef4f120edc94ed
```

The revision may change wording throughout this final script while preserving
its topic, overall duration, timestamp structure, repository walkthrough, and
predict-run-explain teaching loop.

## Preservation Boundary

Do not modify:

- `course/videos/001-computer-learning-from-text/lab.py`;
- any other established Video 1 course artifact;
- repository source code or tests;
- `course/video_1_script_4.md`;
- `course/video_1_improved_script.md`;
- `script_video1_draft.md`;
- `.playwright-mcp/`;
- media, video, audio, animation, render, font, After Effects, Premiere, or
  other production files.

The existing course lab deliberately retains its established contract. The
final template receives a separate companion file so its displayed program,
command, and observed output can be exact without rewriting the existing
course.

## Learner And Objective

The learner can:

- recognize familiar AI uses such as rewriting an email or suggesting code;
- run a short Python file;
- read a string, list, function call, and printed output;
- compare a few small integers.

The learner is not assumed to understand models, parameters, tokenization,
embeddings, prediction mathematics, or training updates.

By the end, the learner should be able to:

1. explain what a Unicode code point does;
2. explain what UTF-8 bytes do;
3. trace the repository's preparation rules in source order;
4. distinguish code points, bytes, prepared text, token IDs, and embeddings;
5. predict and explain the `Cat` and changed `A` lab outputs.

## Terminology Boundary

The revised narration and companion lab must contain no case-insensitive
standalone occurrence of:

```text
model
models
parameter
parameters
model-ready
model-input
model calculations
model learning
```

Use ordinary-language replacements:

- `later AI-training stages`;
- `numerical input used during later training`;
- `later training calculations`;
- `an answer produced during training`;
- `adjustable internal numbers`.

`Learning` remains in the course's central question because learners recognize
the visible outcome being investigated. The internal learning mechanism is not
taught or given its later technical labels.

Tokens, token IDs, and embeddings may remain as roadmap signposts because the
lesson must distinguish them from character numbers and bytes. Apply the
job-before-label rule:

```text
reusable text piece [token]
integer identifier for one piece [token ID]
learned number list selected using that identifier [embedding]
```

Do not teach how text is divided, how the lookup works, how predictions are
calculated, or how adjustable numbers are updated.

## Opening Revision

Replace the prerequisite-leaking opening with this conceptual sequence:

```text
familiar AI output
-> larger question: how can AI learn from written examples?
-> software must first identify, store, and prepare text
-> later stages turn prepared text into numerical input used during training
-> today's question about representation and preparation
```

Use this approved core wording:

> We will build the answer one step at a time. Before AI can learn from text,
> software must first be able to identify the characters, store the text, and
> prepare it consistently. Later stages can divide the prepared text into
> reusable pieces and turn those pieces into the numerical input used during
> training.

## Roadmap Revision

Keep the whole-course orientation but compress its untaught tail:

```text
written source text
├── represented in software
│   ├── characters have Unicode code points
│   └── UTF-8 represents the text as bytes
│
└── prepared for later processing
    └── normalize and clean source text
        -> prepared training text
        -> reusable text pieces [tokens]
        -> one identifier per piece [token ID]
        -> use the ID to select a learned number list [embedding]
        -> later AI-training stages [closed]
```

In spoken narration:

- explain each visible job before or with its label;
- say that every later arrow hides a mechanism for another lesson;
- do not expand the closed training box into predictions, errors, or updates;
- open only character representation, byte storage, and text preparation.

## Targeted Teaching Corrections

### Byte

Replace “a byte is a stored number” with:

> A byte is a small unit of storage. When we display its unsigned value, it is
> a number from 0 through 255.

Explain the observed equality for `Cat` before naming the ASCII-range boundary.

### NFKC Evidence

Keep:

```text
① -> 1
```

Use it only to demonstrate that a source distinction can collapse. Both sides
contain one Python character.

Add a separate hand-checkable count-changing example:

```text
ﬀ -> ff
length 1 -> 2
```

Python's current `unicodedata.normalize("NFKC", ...)` behavior must verify both
examples before the narration is committed.

### Function Annotations

Do not detour into Python's complete runtime type behavior. Use no more than
one short clarification:

> The annotations tell readers that this function expects and returns text;
> `str(text)` is the operation that explicitly asks Python for a string.

Then immediately continue the input-to-output normalization trace.

### Spoken Flow

Remove editorial phrases such as “this is where the brief boundary belongs.”
Address the learner directly and turn the fixed-rule conclusion into the final
classification exercise and Video 2 question.

## Self-Contained Companion Lab

Create this standard-library-only file:

```python
text = "Cat"

print("Human-readable text:", text)
print("Unicode code points:", [ord(character) for character in text])
print("UTF-8 bytes:", list(text.encode("utf-8")))
print("Ready for later AI training? Not yet")
print("Tokens, token IDs, and embeddings belong to later stages.")
```

Embed that source exactly in the narration and use this command:

```bash
python course/templates/video/final_script_v1_lab.py
```

The freshly observed output must appear exactly:

```text
Human-readable text: Cat
Unicode code points: [67, 97, 116]
UTF-8 bytes: [67, 97, 116]
Ready for later AI training? Not yet
Tokens, token IDs, and embeddings belong to later stages.
```

Preserve the complete learning loop:

```text
predict Cat
-> run
-> observe
-> explain
-> change only Cat to A
-> predict [65] and [65]
-> run and compare
-> restore Cat
```

The script may separately ask the learner to predict the repository's NFKC
examples, but must not claim that the character-representation lab executes
`normalize_text`.

## Narrative Structure And Voice

Preserve exactly these nine timestamped sections:

```text
00:00 The Big Question and Today’s First Step
01:00 Where This Video Fits in AI Training
03:00 Three Jobs Before Tokenization
04:20 Representing Characters with Unicode
05:50 Storing Unicode Text with UTF-8
07:00 Preparing Text Consistently
08:15 Apply Text Preparation in the Repository
10:45 Predict, Run, and Explain
13:20 Return to the Whole Route
```

Keep the final script between 2,000 and 2,250 whitespace-delimited words.

The narration must:

- sound like a patient teacher reasoning with the learner;
- use connected paragraphs instead of a list of declarations;
- ask for predictions before displaying results;
- introduce behavior before terminology;
- distinguish identifiers from meaning and fixed rules from later learning;
- keep code, commands, and displayed output outside spoken paragraphs;
- use each completed idea to construct the next question;
- keep spoken sentences at forty words or fewer.

## Verification

The revision is complete only when:

1. the narration and companion lab contain no prohibited terminology;
2. the nine headings and their order are exact;
3. the narration contains 2,000-2,250 words;
4. no spoken sentence exceeds forty words;
5. the displayed companion source exactly matches the new `.py` file;
6. running the displayed command produces the displayed output exactly;
7. `Cat` and changed `A` predictions are present and correct;
8. both NFKC examples are verified with Python and accurately described;
9. the repository normalization source and preparation lines remain exact;
10. all established course artifacts outside the final script remain
    unchanged;
11. focused and full repository tests pass;
12. the committed change contains no media or production files.

## Risks And Controls

- **Risk: ordinary-language replacements become vague.** Preserve each causal
  job while deferring only its technical label.
- **Risk: the roadmap remains a disguised later lesson.** Collapse the untaught
  tail into one visibly closed box.
- **Risk: the new lab diverges from narration.** Compare exact source and
  freshly executed output automatically.
- **Risk: removing one prerequisite term introduces another.** Run a
  terminology audit and teaching-dependency review across the complete script.
- **Risk: the count-change claim overreaches its example.** Use separate
  verified examples for distinction collapse and length change.
- **Risk: existing course work is overwritten.** Stage explicit paths only and
  audit committed scope before integration.
