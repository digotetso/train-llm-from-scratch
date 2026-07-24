# Video 1 `final_final copy` Teaching Rewrite Design

**Date:** 2026-07-24
**Status:** Approved in conversation on 2026-07-24

## Goal

Rewrite `final_final copy` in place so it follows the course's established
beginner-teaching method:

```text
real question
-> familiar experience
-> apparent mystery
-> smallest mechanism
-> learner prediction
-> technical name
-> complete causal trace
-> tiny runnable proof
-> likely misconception
-> compact reusable explanation
-> building block for the next lesson
```

The current draft contains strong Unicode and text-preparation material, but it
spreads one lesson across 3,895 words and approximately 29 minutes. It also
introduces LLMs, tokenizers, token IDs, vectors, and training mechanics before
the learner understands the text-preparation mechanism.

The approved rewrite will target a focused 15-minute lesson.

## Source And Preservation Boundary

Modify only the learner artifact:

```text
final_final copy
```

Its approved pre-rewrite SHA-256 is:

```text
d2fe39c1250de1c679232a5bfa118966b3d05e04e0cd63c25395dbf00f6b8441
```

Preserve `final_final` unchanged. Do not modify established course scripts,
tests, media, animation, rendering, or production files as part of this
rewrite.

The design specification and subsequent implementation-plan documents are the
only additional files permitted by the workflow.

## Learner And Prerequisites

The learner can:

- recognize familiar AI uses such as improving an email or suggesting code;
- read a short Python string, function call, list, and printed output;
- run `python filename.py` from the folder containing the file; and
- compare small text and number examples.

The learner is not assumed to understand:

- LLMs as an internal mechanism;
- tokenization, token IDs, vocabularies, or embeddings;
- Unicode normalization;
- compatibility decomposition or canonical composition;
- dataset pipelines; or
- the mathematics of training.

## Central Question And Outcome

The lesson asks one central question:

> **How can we find out exactly what a piece of text contains and change it
> consistently before later AI work?**

By the end, the learner should be able to:

1. inspect hidden whitespace and line endings in a Python string;
2. explain that a code point identifies a Unicode character in the lesson's
   examples;
3. predict that similar-looking forms can have different code-point
   sequences;
4. explain why text preparation uses chosen rules rather than a universal
   definition of “clean” text;
5. trace the complete preparation function from starting text to result;
6. predict the result for one changed source; and
7. distinguish character identification from text preparation.

Before asking the lesson question, the opening must state that the course goal
is to train an LLM from scratch. At this point, `LLM` is only the name of the
system being built; its technical meaning is deferred until the relevant
mechanism has been taught. The opening must then identify itself as a
big-picture map of the complete course and describe the route in ordinary
language:

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

The opening must tell learners that these stages have proper technical names
and that each name will be introduced later, when the course reaches and
explains the behavior it describes. Video 1 then narrows to the first handoff:
turning collected writing into reliable starting material.

## Content Scope

### Keep And Integrate

- the messy source example containing surrounding whitespace, an empty line,
  `①`, `Ａ`, and `ﬀ`;
- inspection with `repr`;
- the distinction between ordinary spaces, `\t`, and `\r\n`;
- the smallest useful code-point comparison, using `ord`;
- `① -> 1`, `Ａ -> A`, and `ﬀ -> ff` as NFKC examples;
- the length-changing `ﬀ -> ff` case;
- the warning that NFKC can remove meaningful distinctions;
- one complete, self-contained `prepare_text` function;
- a predict-run-observe-explain loop; and
- one changed source string that tests transfer.

### Defer

- formal definitions of LLMs and neural networks;
- the complete training-data route;
- tokens, token IDs, vocabularies, embeddings, and numerical vectors;
- tokenizer-level normalization;
- compatibility decomposition and canonical composition;
- long catalogs of possible data sources and cleanup cases; and
- detailed code-point notation beyond what the tiny example needs.

The closing may state, in ordinary language, that prepared text becomes a
building block for the next lesson. It must not preview untaught mechanisms.

## Narrative Design

Use nine connected sections with provisional timestamps targeting 15 minutes:

1. **Hook and central question** — begin with the visibly messy source text and
   ask what software actually receives.
2. **Inspect before changing** — use `repr` to expose spaces, tabs, and line
   endings before naming cleanup rules.
3. **Similar-looking forms** — compare `①` with `1` and ask whether software
   must treat them as identical.
4. **Character identification** — explain the fixed identification mechanism,
   then name Unicode code points and `ord`.
5. **Choose what to preserve** — make the dataset goal explicit and show why
   cleanup decisions are contextual.
6. **Normalization** — reveal the selected transformations, name
   normalization and NFKC, and state the loss-of-distinction boundary.
7. **Complete causal trace** — walk through normalization, line splitting,
   surrounding-whitespace removal, empty-line removal, and joining.
8. **Mini-lab and transfer** — predict, run, observe, explain, change one input,
   predict again, and compare.
9. **Compression and building block** — state the reusable distinction:
   code points identify; preparation applies chosen transformations.

Each transition must arise from the result of the previous section. Avoid
sections that merely announce the next topic.

## Voice And Terminology

The narration must:

- sound like a patient teacher reasoning alongside the learner;
- use connected paragraphs rather than repeated lists of declarations;
- prefer concrete verbs and short or medium sentences;
- ask for a prediction only after giving enough information to reason;
- explain behavior before introducing its accepted technical name;
- keep headings, stage directions, commands, code, and output outside spoken
  paragraphs;
- introduce one new technical term at a time where practical;
- avoid patronizing reassurance and unexplained future vocabulary; and
- use examples as evidence rather than copying exercises.

Use `number`, not `integer`, in beginner-facing narration. Use `split`, not
`divide`, for text. Do not use “job,” “path,” or “compress” as editorial
metaphors in spoken narration.

## Accuracy Boundaries

- Do not claim that visual similarity proves Unicode equivalence.
- Scope one-code-point explanations to the examples being used.
- State that some visible symbols can contain several code points, but defer
  the mechanism.
- Describe NFKC as one Unicode normalization form, not a universal cleanup
  rule.
- State that NFKC may change Python string length and may remove distinctions
  that matter.
- Explain every transformation in the displayed preparation output.
- Verify all displayed Python inputs and outputs by execution.

## Length And Timing

Target:

- 1,650-1,850 spoken words;
- approximately 15 minutes including prediction and code-reading pauses;
- no spoken sentence longer than 40 words; and
- section pacing that does not require dense technical narration above roughly
  145 words per minute.

Timestamp markers remain provisional until a timed read-aloud.

## Verification

The rewrite is complete only when:

1. the target contains one central question and one coherent causal chain;
2. later AI vocabulary is deferred rather than used as explanation;
3. every major term follows an understandable mechanism;
4. the code-point and NFKC claims match current Unicode and Python
   documentation;
5. all embedded Python examples run and their output matches the script;
6. the changed-input example demonstrates transfer;
7. the recap provides a compact explanation reusable in the next lesson;
8. the spoken-word and sentence-length targets pass;
9. timestamp density is plausible for a 15-minute read;
10. `final_final` and unrelated working-tree files remain unchanged; and
11. no media or production files are added.

## Risks And Controls

- **Risk: compression removes a necessary cause.** Keep the complete
  source-to-output trace even while removing repeated explanation.
- **Risk: Unicode caveats overwhelm the opening.** Teach one-code-point
  examples first, then add one short scope boundary.
- **Risk: the rewrite becomes terminology-first again.** Check first-use order
  in headings, narration, and code for source, string, `repr`, whitespace,
  inspection, character, Unicode, code point, normalization, NFKC, text
  preparation, list, loop, `splitlines`, `strip`, `append`, `join`, function
  boundaries, `def`, indentation, parameter flow, and `return`.
- **Risk: the lab becomes a copying exercise.** Require a prediction and a
  changed source before the result is shown.
- **Risk: unrelated user work is committed.** Stage and commit only this design
  document during the design phase.
