# Video 1 Script 2 Book-Method Design

**Date:** 2026-07-22  
**Status:** Approved in conversation on 2026-07-22

## Goal

Create an alternate narration for Video 1 that teaches the existing objective
through the strongest transferable methods in J. Clark Scott's *But How Do It
Know?* The alternate must preserve the course's verified technical boundaries
while giving the learner the experience of constructing each idea from a tiny,
fully explained mechanism.

The result is an additional Script 2, not a replacement for either existing
Video 1 draft.

## Source And Review Method

The supplied source is the 201-page 2009 edition at:

```text
/Users/digotetsomatema/Downloads/Scott C. But How Do It Know...of Computers for Everyone 2009/Scott C. But How Do It Know...of Computers for Everyone 2009.pdf
```

The assessment covered the complete extracted text from the front matter
through the closing chapter. Representative pages were also rendered and
inspected across the book, including conceptual openings, gate and memory
traces, abstraction transitions, whole-system integrations, representation
examples, and the closing synthesis.

Page references in this document are PDF page indices, not printed page
numbers.

This design adopts general teaching principles. It does not reproduce the
author's prose, imitate distinctive phrasing, or carry dated technical claims
into the course.

## Thorough Teaching-Style Assessment

### 1. The Book Replaces Mystery With Mechanism

The introduction begins with a familiar object whose behavior is easy to
misread as intelligence, then replaces that imagined complexity with a simpler
physical explanation (PDF pp. 6-7). This establishes the central teaching move:
an impressive result does not prove that the system contains the human-like
process a viewer may imagine.

The book repeatedly returns to the difference between appearance and cause. A
computer appears to contain pictures, words, and decisions; the explanation
instead begins with physical states and shows how progressively larger systems
can be assembled from them.

For Video 1, the parallel puzzle is the coherent text produced by an AI system.
The output can look as though the system receives words together with the
learner's human understanding. The lesson must replace that impression with a
small, explicit chain: represented text becomes numeric input; a model produces
a prediction; measured error changes adjustable parameters during training.

### 2. The Teaching Contract Is Dependency Order

The book explicitly promises one idea at a time, enough detail to avoid causal
gaps, and later concepts constructed from earlier ones (PDF pp. 8-9). Its best
chapters follow that promise rather than merely stating it.

The broad construction is cumulative:

```text
two-state behavior
-> bit
-> gates
-> stored bit
-> byte
-> code
-> register and bus
-> RAM
-> operations
-> ALU
-> timing and control
-> instruction
-> program
-> input and output
```

Each step contributes one new capability. A later abstraction is not used as
the explanation for an earlier one.

### 3. Familiar Experience Is Used As An Operable Model

The strongest analogies are things the learner can mentally manipulate. Coins,
lamps, and locks establish two-state behavior before the formal definition of a
bit (pp. 14-16). A strange pair of light switches lets the learner experience a
gate's behavior before learning its name (pp. 17-24). Hotel or post-office
cubbyholes are constructed step by step before being mapped onto selectable
memory (pp. 51-54).

These analogies have a job. They expose a relationship the learner can operate,
then return to the real mechanism. The address discussion is especially strong
because it also names the limit: a computer address selects a location; it need
not be a label stored at that location (p. 65).

Script 2 should therefore avoid a decorative analogy when `Cat`, `ord`, and a
three-number trace are already more concrete. Familiar AI use supplies the
entry point; the runnable example supplies the mechanism.

### 4. Behavior Commonly Comes Before Terminology

The book often lets the learner see what a component does before giving it a
technical name. AND, NAND, and NOT behavior is derived before the naming pass
(pp. 21-24). A memory circuit is traced before it is compressed into a memory
symbol (pp. 27-28). Several byte operations exist before they are combined and
named as an arithmetic and logic unit (pp. 85-86). The instruction machinery is
assembled before recurring behavior is compressed into terms such as program,
fetch, execute, and instruction cycle (pp. 105-108).

The name functions as a handle for an understood idea. It is not treated as the
explanation.

For Script 2, the learner should first see that software follows a fixed
agreement connecting `A` with `65`. Only then should the script name Unicode
and code point. The learner should first see the contrast between a fixed
conversion and an adjustable prediction system. Only then should the script
stabilize the terms text representation and learning.

### 5. The Learner Traces State Changes

The strongest chapters require the learner to follow inputs through a
mechanism. The memory circuit changes one input at a time and traces every
affected gate until the output can be explained (pp. 27-29). The adder is built
from small input cases and carry behavior (pp. 78-80). Adding one register to
another is traced across multiple clock cycles (pp. 93 and 100-101). Fetching an
instruction is traced through the instruction address register, memory address
register, RAM, instruction register, and updated address (pp. 107-108).

This produces causal confidence: the learner does not have to accept that an
unseen step somehow works.

The book's questions are often answered immediately, however. Script 2 should
improve this by asking the learner to commit to a prediction before revealing
the result.

### 6. Careful Beginner Questions Are Answered At The Point Of Need

When the gate discussion creates the question of where output electricity
comes from, the book answers it immediately and then marks power wiring as
outside the chosen diagram boundary (p. 18). Later chapters similarly answer
why a fixed storage technology is not used for all memory (p. 178) and how the
first program can load when no loading program is initially available
(pp. 179-180).

The important pattern is not simply adding a misconception section at the end.
The answer belongs where the learner is likely to ask the question.

In Script 2, the following questions must be handled locally:

- Does `65` contain the meaning of `A`?
- Are Unicode code points and UTF-8 bytes always the same?
- If text is already represented numerically, has learning occurred?
- Does normalization preserve every source distinction?
- Can a lower error count alone prove useful learning on unseen examples?

### 7. Every Understood Mechanism Becomes A Building Block

This is the most important structural feature. After a mechanism has been
traced, the book gives it a name and a compact symbol. The internal wiring is
then closed so the learner can use the completed component without reopening
every gate. The memory circuit becomes an `M` block and is immediately reused
to construct a byte (pp. 28 and 36). Completed operations become an ALU block
(pp. 85-86). The stepper is first understood through its input/output behavior,
opened for construction, and then closed again into a stable component
(pp. 94-97).

The whole-system diagrams work because every visible block has already been
earned. The apparently complicated control system on p. 131 is reframed as a
composition of familiar parts rather than a new mystery.

Script 2 must reproduce this rhythm in spoken form:

```text
trace one fixed character mapping
-> name numeric text representation
-> close it as a building block
-> use it to ask what a learning system can change
-> trace prediction, error, and parameter adjustment
-> name learning
-> close both into the representation-learning distinction
-> use that distinction to inspect repository preparation and the lab
```

### 8. Missing Capabilities Create The Transitions

The book's best transitions are necessity-driven. Two states are not enough for
many distinctions, so several bits are grouped. Stored bytes need a route, so a
bus is introduced. The processor can move and transform bytes, but its control
wires need timing, so the clock and stepper appear. A fixed sequence can do one
job, but a useful computer needs different actions, so instructions appear
(pp. 30-54 and 87-108).

This makes the book feel like a single investigation rather than chapters
placed next to one another.

Script 2 should carry each conclusion into the next question. Examples:

- If `A` has one stable number, how do three characters become a sequence?
- If the sequence is numeric, what exactly has changed?
- If no adjustable value changed, what would have to change before this counts
  as learning?
- If that distinction is sound, which side of it does repository normalization
  belong to?

### 9. Small Numbers Function As Evidence

The book uses examples that can be checked by hand: individual gate states,
small binary values, one addition with carry, one instruction byte, one memory
address, and one font location. The arithmetic demonstrates a rule rather than
decorating it.

Video 1 already has an appropriate proof object:

```text
C -> 67
a -> 97
t -> 116
```

It also has a deliberately small learning intuition: seven mistakes becoming
five after an update. Script 2 must state the limitation of that intuition and
avoid presenting the count as the repository's actual loss calculation.

### 10. Repetition Works Best As Reuse, Not Restatement

The book repeatedly recalls earlier ideas, but its strongest repetitions add a
new consequence. The same addition task appears before and after control wiring
so the second appearance explains what the new mechanism contributes
(pp. 93 and 100-101). A mechanism is recapped exactly when it becomes an input
to the next construction.

Script 2 should use conversational callbacks such as “keep that fixed mapping”
or “use the distinction we just built.” It should not repeat the same conclusion
several times without spending it on new reasoning.

### 11. Representation Is Kept Separate From Inherent Meaning

The code chapters repeatedly distinguish physical state from the interpretation
people assign to it (pp. 30-41). A later synthesis shows that the same numeric
pattern can be treated as a character, a number, an address, an instruction, or
pixel states depending on the receiving mechanism (pp. 151-152).

This is directly relevant to Video 1. `65` does not contain every human meaning
of `A`. Unicode supplies a stable agreement; the surrounding process determines
how the value is used. Representation is necessary for calculation without
being identical to meaning or learning.

## Practices To Preserve

1. Begin each important idea with a genuine learner question.
2. Use familiar experience as an entry point, not technical proof.
3. Expose the gap in the learner's current explanation.
4. Add one mechanism or distinction at a time.
5. Ask for a prediction before revealing a result.
6. Trace input, operation, state change, and output completely.
7. Introduce the technical name after the behavior is understood.
8. Prove the explanation with a hand-checkable example.
9. Answer the likely careful objection where it occurs.
10. Compress the result into a memorable operational sentence.
11. Turn the result into a stable building block and use it immediately.

## Practices To Exclude

- Demeaning, patronizing, gendered, or culturally narrow examples.
- Long analogy setups whose incidental details delay the mechanism.
- Claims that a learner should find the concept easy.
- Rhetorical questions with no opportunity to reason.
- Dense print-style paragraphs that require rereading.
- Decorative etymology and historical detours.
- Anthropomorphic language that replaces a causal explanation.
- Absolute claims derived from a deliberately simplified machine.
- Dated ASCII-only, hardware, storage, display, security, brain, or AI claims.
- Explanations that present a procedure while deferring the cause needed to
  understand why it works.
- Close imitation of the source author's wording or mannerisms.

## Chosen Script Approach

Use the **causal ladder** approach approved by the user.

The narration follows one object, `Cat`, through two constructed mechanisms:

1. Build numeric text representation from one fixed character mapping, then a
   sequence of code points and UTF-8 bytes.
2. Use that completed representation as the input to the smallest accurate
   learning chain: prediction, measured error, parameter adjustment, and a new
   prediction.

The completed mechanisms are compressed into this durable distinction:

> Representation changes the form of the data. Learning changes the model's
> adjustable parameters using examples and measured error.

That distinction then becomes the tool used to classify repository
normalization and the mini-lab.

## Audience And Objective

The learner can run a Python file and read simple strings, lists, function
calls, and printed output. No machine-learning, Unicode, tokenization, tensor,
or Transformer knowledge is assumed.

The verified objective remains:

> Explain why text must be represented as numbers before a mathematical model
> can learn patterns from it.

## Narrative Spine

### 00:00 — Familiar Result And Apparent Mystery

Begin with the familiar act of typing `Cat` into an AI system and receiving a
coherent response such as an email revision or code. Ask what the system can
actually calculate about the letters. Reduce the large AI question to the first
small problem: how can one written character become a stable number without
that number becoming its meaning?

### 00:45 — Build One Fixed Mapping

Use `A` as the first inspectable case. Ask whether Python invents a number on
each run or follows a stable agreement. Reveal `ord("A") == 65`, explain the
fixed relationship, and only then name character, Unicode, and code point.

Immediately answer the intelligent beginner's question: `65` identifies the
encoded character under the agreement; it does not contain the possible human
meanings of `A`.

### 02:00 — Expand The Mechanism Into Numeric Text Representation

Return to `Cat`. Trace each character into `67`, `97`, and `116`. Then introduce
bytes as the stored or transmitted layer and UTF-8 as the encoding rule. Explain
why the code-point and byte lists match for these ASCII-range characters and
why that match is not universal.

Compress the completed mechanism as **numeric text representation**: a stable
way to give text a numerical form that software can store and process.

### 04:00 — Let The First Building Block Create The Learning Question

Ask what changed when `Cat` became three numbers. The form of the data changed;
no prediction improved and no adjustable model value changed. That exposes the
next missing mechanism.

Introduce a model in operational language before naming parameters. Trace
examples to a prediction, a measured error, an adjustment to internal numbers,
and a later prediction. Use seven mistakes becoming five only as a compact
intuition, immediately qualified by the need for a numeric error measure and
evaluation on separate examples.

Name the adjustable numbers **parameters** and the change process **learning**.
Compress both completed mechanisms into the representation-learning
distinction.

### 06:00 — Apply The Building Block To Repository Code

Inspect `normalize_text` and the prepared document record using one continuous
question: which values change, and are any model parameters updated?

Trace NFKC normalization, newline consistency, right-edge whitespace removal,
outer stripping, returned text, stored text, and character count. Keep the NFKC
warning local and explicit: it is a deliberate, non-lossless policy; `①` can
become `1`; some inputs can change character count.

Conclude by classifying this work as data preparation on the representation
side of the established distinction.

### 09:00 — Prove The Fixed Mechanism In The Mini-Lab

Ask the learner to predict both numeric lists before running the existing lab.
Trace the observed output line by line. Change only `Cat` to `A`, predict again,
and explain why repeated agreement is not practice or improvement. Restore the
checked input afterward.

### 12:00 — Resolve The Two Category Errors In Context

Use diagnostic questions to correct:

1. identifier versus human meaning;
2. fixed conversion versus learning.

Do not present these as an isolated warning list. Treat them as tests of the
building block the learner already constructed.

### 13:00 — Reconstruct And Transfer

Ask the learner to rebuild the complete chain in ordinary language. End with a
short transfer exercise involving `A` and a question about what would have to
change before learning could be claimed.

Use numeric text representation as the starting point for Video 2's question
about stable character numbers.

## Spoken-Flow Requirements

- Write connected paragraphs that sound like one person reasoning with the
  learner.
- Mix short conclusions with medium-length explanatory sentences.
- Use `you`, `we`, and `let's` where natural.
- Carry the answer from one paragraph into the next question.
- Give prediction prompts real breathing room before the reveal.
- Separate stage directions, code, and printed output from spoken narration.
- Avoid a sequence of slogan-like one-sentence paragraphs.
- Keep one main conceptual burden in each paragraph.
- Use technical terms consistently after introducing them.
- Target approximately 1,900-2,100 total Markdown words, including code and
  stage directions, to remain near the existing 14-minute production shape.

## Technical Constraints

- Preserve the distinction between Unicode code points and UTF-8 bytes.
- State that matching values for `Cat` arise from its ASCII-range characters
  and are not universal.
- Do not imply that a code point contains contextual meaning.
- Do not imply that numeric conversion, encoding, or normalization is learning.
- Define learning through predictions, measured error, and changes to adjustable
  model parameters.
- Qualify the tiny mistake-count example as intuition rather than the
  repository's training calculation.
- Preserve the deliberate, non-lossless NFKC warning, including `①` becoming
  `1` and possible character-count changes.
- Keep repository excerpts faithful to `matgpt/data/normalize.py` and
  `matgpt/data/prepare.py`.
- Preserve the existing lab command, input, output, and restoration step.
- Do not teach token, tensor, logit, gradient, attention, or token embedding as
  explanatory vocabulary.

## File Placement And Preservation

Create:

```text
course/video_1_script_2.md
```

Do not place the alternate inside
`course/videos/001-computer-learning-from-text/`; the course-structure test
requires an exact artifact set in that directory.

Do not modify or stage:

```text
course/videos/001-computer-learning-from-text/script.md
course/video_1_improved_script.md
```

The second path is an untracked user-owned draft and must remain untouched.

Do not create, modify, stage, or commit media, video, audio, render, or project
files.

## Verification

1. Compare every technical statement with the canonical lesson, evidence file,
   lab, and relevant repository sources.
2. Confirm the alternate contains the established eight timestamped sections
   without changing the canonical script.
3. Confirm the causal ladder contains both named building blocks and spends
   each one on the next concept.
4. Scan for deferred vocabulary used as explanation.
5. Run the existing lab and compare its output with the narration.
6. Run `uv run pytest tests/test_course_structure.py -v` to ensure the alternate
   file location does not disturb the production artifact contract.
7. Run a read-aloud review for conversational flow, isolated sentence lists,
   overloaded paragraphs, premature terminology, repeated conclusions, and
   missing transitions.
8. Run `git diff --check` and inspect the final diff and status.

## Acceptance Criteria

- The book assessment is documented with page-specific evidence and explicit
  exclusions.
- Script 2 is an alternate Markdown artifact; existing scripts are unchanged.
- The narration follows the causal ladder rather than merely adding analogies.
- Every important technical name follows an understandable behavior.
- Numeric text representation becomes a stable named building block.
- That building block creates the question that leads to learning.
- The representation-learning distinction is applied to repository preparation
  and the lab.
- Every central claim has a complete input-to-output causal trace.
- The narration is conversational and cohesive when read aloud.
- Current repository tests and lab output remain valid.
- No media or video files are included.

## Non-Goals

- Replacing or revising the canonical Video 1 script.
- Editing the user's existing improved-script draft.
- Imitating the source author's exact voice or wording.
- Teaching the complete training algorithm.
- Expanding into tokenization, embeddings, tensors, or Transformer internals.
- Updating production animation, scenes, labs, quizzes, source code, or tests.

## Risks And Mitigations

- **Risk: the book method becomes excessive narration.** Keep the causal trace
  complete but use one example, one controlled change, and short callbacks.
- **Risk: the alternate becomes a list of correct sentences.** Join every
  conclusion to the next question and run a dedicated read-aloud pass.
- **Risk: terminology arrives too early.** Require an observable behavior or
  learner prediction before each central label.
- **Risk: the representation discussion crowds out learning.** Close numeric
  representation by the 04:00 transition and use it immediately to expose what
  learning adds.
- **Risk: simplified learning language overclaims.** Keep measured error,
  adjustable parameters, unseen examples, and the illustration boundary.
- **Risk: the new artifact breaks strict course tests.** Keep it outside the
  exact-artifact production directory and run the focused contract.

