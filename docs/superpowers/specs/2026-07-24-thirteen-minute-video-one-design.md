# Thirteen-Minute Video 1 Compression Design

**Status:** Approved for specification
**Date:** 2026-07-24
**Target artifact:** `final_final copy`

## Problem

The source script at
`/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/final_final copy`
contains 24 timed sections, 2,705 spoken words, and a final timestamp of
`27:50`. It repeats several explanations, separates one causal walkthrough
into many small sections, and introduces later LLM-training terminology before
those mechanisms are taught.

The video should fit comfortably inside the requested 10–15 minute range
without turning the lesson into disconnected summary statements.

## Source Preservation

The long source is an untracked file in the main checkout with SHA-256:

```text
d2fe39c1250de1c679232a5bfa118966b3d05e04e0cd63c25395dbf00f6b8441
```

Implementation will use that file as the content source while editing only
the isolated worktree artifact. The main-checkout source must remain untouched
during drafting and review.

Before the compressed branch is merged locally, verify the hash again and
recoverably move the original to:

```text
final_final copy.pre-13-minute-original.md
```

The compressed script will then occupy the original `final_final copy` path.
No media or video files will be added.

## Learner And Objective

The learner has used an AI text box and can run a small Python file, but has
not yet learned the internal stages of LLM training or Unicode terminology.

By the end of Video 1, the learner should be able to:

1. explain why source text must be inspected before it is changed;
2. use observed code-point differences to explain why similar-looking text
   may be stored differently;
3. distinguish a Unicode code point from the later numbers used in LLM
   training;
4. trace every operation that changes the sample into prepared text; and
5. predict the result when the same preparation process receives new text.

## Runtime Contract

- Target endpoint: approximately `13:00`.
- Acceptable runtime: 12:30–13:30.
- Target spoken words: 1,550–1,700.
- Timed sections: 8 or 9.
- Section density: 105–145 spoken words per minute.
- Maximum spoken sentence: 40 words.
- Spoken delivery: conversational, causal, and readable aloud.

The timestamps describe the intended spoken pace. Code, stage directions, and
on-screen output are excluded from the spoken-word count.

## Teaching Chain

The compressed lesson will preserve this dependency order:

1. **Familiar experience:** AI can improve an email, reshape text, or suggest
   code.
2. **Larger question:** how can writing eventually be used to train an LLM
   from scratch?
3. **Course boundary:** use `LLM` as the label for the system being built and
   defer its proper technical meaning.
4. **Training collection:** explain an organized collection of learning
   examples before naming it a **training dataset**.
5. **Number motivation:** explain that the later system performs mathematical
   operations using numbers, without opening the deferred conversion
   mechanism.
6. **Source mystery:** reveal spaces, tabs, line endings, an empty line, and
   similar-looking forms.
7. **Inspection:** show the exact stored source with `repr` before naming
   **source**, **string**, **whitespace**, and **inspection**.
8. **Prediction and evidence:** compare `①`/`1`, `Ａ`/`A`, and `ﬀ`/`ff`;
   predict whether storage is identical; then use `ord` results as evidence.
9. **Technical names:** introduce **character**, **Unicode**, and **code point**
   only after the observed numbers differ.
10. **Category boundary:** state that code points identify characters and are
    not the later numbers used to train the LLM.
11. **Purpose-dependent decision:** choose `1`, `A`, and `ff` for this source
    while explaining that other sources may need to preserve the original
    forms.
12. **Normalization:** show the chosen changes before naming
    **normalization** and **NFKC**; include the `ﬀ` length change and the warning
    that NFKC can remove meaningful distinctions.
13. **Preparation mechanism:** trace normalization, line splitting, trimming,
    empty-line removal, and joining without a hidden causal step.
14. **Lab and transfer:** predict, run, observe, explain, change one source,
    predict again, and compare.
15. **Compression and building block:** end with a reusable distinction between
    identification and preparation, then use prepared text as the next
    lesson’s starting point.

## Section Architecture

The final timestamp values may move slightly during density validation, but
the intended structure is:

| Approximate time | Section purpose | Target spoken words |
| --- | --- | ---: |
| `00:00–02:15` | Familiar hook, from-scratch goal, training dataset, course map, source mystery | 260–300 |
| `02:15–03:40` | Reveal the exact stored text with `repr` | 160–200 |
| `03:40–05:00` | Similar-looking forms, prediction, and `ord` evidence | 150–190 |
| `05:00–06:25` | Unicode, code points, and the training-number boundary | 160–200 |
| `06:25–08:00` | Purpose-dependent choices, NFKC, length change, and caveat | 170–220 |
| `08:00–10:20` | One complete preparation function and causal trace | 250–330 |
| `10:20–12:10` | Predict, run, explain, and transfer to changed text | 200–260 |
| `12:10–13:00` | Compact mental model and next-lesson building block | 90–120 |

## Compression Decisions

### Preserve

- The learner-facing AI hook and larger from-scratch question.
- A compact LLM-label explanation.
- The training-dataset intuition and later need for numbers.
- The exact source string and `repr` evidence.
- All three similar-form comparisons.
- Decimal code-point evidence; `U+` notation may appear briefly on screen but
  will not receive a separate spoken tutorial.
- The code-point-versus-training-number distinction.
- The purpose-dependent normalization decision and NFKC limitation.
- One complete, independently runnable preparation file.
- Exact observed output and one changed-input transfer case.
- Prediction pauses, full causal trace, recap, and building block.

### Merge

- The original course-position and messy-source sections into the opening.
- The three separate similar-character investigations into one evidence
  sequence.
- The code-point caveat into the code-point explanation.
- The definition, length-change, and policy sections for normalization into
  one causal section.
- The five preparation-step sections into one traced walkthrough.
- The run, explanation, and changed-input sections into one lab loop.
- The two closing sections into one recap and boundary.

### Remove Or Defer

- The separate tokenizer-normalization section.
- The second standalone `inspect_characters.py` file.
- Repeated source-type lists and repeated “these forms differ” conclusions.
- A spoken tutorial on hexadecimal formatting.
- Early explanations of tokenizers, tokens, token IDs, vocabularies,
  embeddings, vectors, or neural networks.
- The detailed final pipeline beyond “prepared text becomes the next
  lesson’s starting point.”

## Terminology Contract

Spoken narration must not use these future terms:

```text
tokenizer
token
token ID
vocabulary
embedding
vector
neural network
compatibility decomposition
canonical composition
```

The lesson may say that a later stage splits prepared text into pieces and
gives those pieces numbers. The proper names for that mechanism remain
deferred.

Terms taught in this lesson must follow observable behavior:

- stored text behavior before **string**;
- hidden marks before **whitespace** and **inspection**;
- differing `ord` outputs before **character**, **Unicode**, and **code point**;
- chosen transformations before **normalization** and **NFKC**;
- intermediate operations before Python terms used by the final function.

## Runnable Lab

The lesson will use one self-contained Python file:

```text
inspect_and_prepare_text.py
```

The implementation will favor the explicit-loop version of `prepare_text`
because each intermediate behavior can be explained without first teaching
list comprehensions.

The source and required prepared output remain:

```python
source = "  Lesson ①: Ａ cat ﬀ  \r\n\r\n\tsecond line  "
```

```text
'Lesson 1: A cat ff\nsecond line'
```

The transfer source and output remain:

```python
source = "  Chapter ②: Ｂig oﬀice  \n\n  final line  "
```

```text
'Chapter 2: Big office\nfinal line'
```

The lab loop must include prediction, execution, observation, causal
explanation, one changed input, a second prediction, and comparison.

## Accuracy Boundaries

- A code point is used here as a fixed identifier for one encoded character;
  it does not represent the character’s meaning.
- `ord` accepts one Python character at a time. The `ff` comparison contains
  two characters and therefore two code points.
- Code points are not the later numerical representation used to train an
  LLM.
- NFKC applies a selected Unicode rule; it is not a universal definition of
  clean or correct text.
- `splitlines` removes the original line-boundary marks, and `join` inserts
  the selected `\n` between surviving lines.
- The example demonstrates one chosen preparation policy and does not claim
  that every dataset should remove blank lines or surrounding whitespace.

## Verification

Before the compressed artifact is accepted:

1. verify 1,550–1,700 spoken words;
2. verify an endpoint between 12:30 and 13:30;
3. verify 8 or 9 timed sections at 105–145 spoken words per minute;
4. verify no spoken sentence exceeds 40 words;
5. scan spoken narration for prohibited future terminology;
6. verify the behavior-before-terminology order;
7. execute every `ord`, normalization, preparation, and transfer result;
8. verify all code blocks form one runnable standalone file;
9. confirm the long main-checkout source retains its original hash until the
   approved merge-preservation step;
10. confirm no media or production files are added; and
11. run the repository’s full test suite before branch completion.

## Non-Goals

- Teaching tokenization or model internals.
- Surveying every Unicode normalization form.
- Covering grapheme clusters or complex emoji in detail.
- Cleaning a real web-scale corpus.
- Summarizing the repository.
- Creating media, animation, rendering, or production assets.
