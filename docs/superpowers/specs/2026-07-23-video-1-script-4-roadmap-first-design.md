# Video 1 Script 4 Roadmap-First Design

**Date:** 2026-07-23
**Status:** Approved in conversation on 2026-07-23

## Goal

Turn the user's rough Video 1 draft into a complete alternate narration that
begins with the whole language-model training journey and then zooms into the
first mechanism the learner can understand completely: representing text with
numbers.

The script must preserve the draft's distinctive promise—show the destination
and the route before examining the first step—while correcting the technical
pipeline, controlling cognitive load, and meeting the course's established
beginner-teaching standard.

The result is an additional Script 4. It does not replace the canonical Video 1
script or Scripts 2 and 3.

## Source Draft And Preservation

The user supplied this rough draft:

```text
/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/script_video1_draft.md
```

Its essential idea is:

```text
familiar AI capabilities
-> AI learns from a large body of text
-> show the full text-to-training journey at a high level
-> explain that the course will revisit and open each step
-> focus Video 1 on why text must become numbers
```

Preserve the rough draft unchanged as the source artifact. Create the polished
alternate at:

```text
course/video_1_script_4.md
```

The canonical Video 1 script, the other alternate scripts, the user's improved
draft, source code, tests, and media remain outside this change.

## Chosen Narrative Approach

Use the approved **roadmap, then zoom in** approach.

The other considered approaches were:

- following `Cat` through every later pipeline stage, which would be concrete
  but would make future concepts look understood before their prerequisites;
- beginning with the text-to-numbers mystery and revealing the roadmap later,
  which would work but would be too similar to the existing Video 1 scripts.

Script 4 should feel like the opening of a long, carefully guided journey. It
shows the learner where the course is going, labels the major stops, explicitly
closes the boxes whose mechanisms have not been taught, and then earns one
small part of the map through a complete causal explanation.

## Learner And Learning Contract

The learner can:

- recognize familiar AI uses such as rewriting an email, improving an essay,
  or suggesting code;
- run a Python file;
- read a short string, list, function call, and printed output;
- compare a few small integers.

The learner is not assumed to understand machine learning, tokens, token IDs,
embeddings, tensors, prediction, loss, gradients, optimizers, or model
parameters.

The central question is:

> How does an AI system get from written examples to improved output, and what
> first step makes that numerical learning process possible?

By the end of Video 1, the learner should be able to do two different things:

1. point to each major stage on the course roadmap and state its job in one
   plain-language clause, without claiming to understand its internal
   mechanism;
2. fully explain, predict, and trace the first prerequisite: text must receive a
   numerical representation before a mathematical model can use it.

The roadmap supplies orientation. Text representation supplies the lesson's
earned causal mental model.

## Corrected High-Level Roadmap

Use this high-level sequence:

```text
training text
-> reusable text pieces [token: roadmap signpost]
-> one identifier per piece [token ID: roadmap signpost]
-> ID selects a learned number list [embedding: roadmap signpost]
-> model calculations
-> prediction
-> comparison with the known training target
-> measured error
-> parameter adjustment through a later-taught update method
-> repeat across examples
```

This map is deliberately compressed. The narration must say that an arrow can
hide an entire later lesson and that a label is not yet an explanation.

### Roadmap Signpost Policy

The user approved naming later technical concepts as brief signposts. Apply
this exact policy:

- describe the stage's job in ordinary language first;
- give the technical label once;
- spend no more than one or two spoken sentences on the stage;
- explicitly keep its internal mechanism closed;
- identify the later course lesson that will open it when useful;
- never use a signpost term as the explanation for today's text-representation
  mechanism.

The roadmap may name:

- **token:** one reusable text piece produced by a later-taught dividing rule;
- **token ID:** an integer identifier assigned to one defined token;
- **embedding:** a learned list of numbers selected using a token ID;
- **model:** a mathematical prediction system with adjustable internal numbers;
- **prediction:** the model's numerical answer for the current training task;
- **measured error:** a number describing how far that answer is from the known
  training target;
- **parameter adjustment:** a later-taught process that changes adjustable
  model numbers in response to measured error.

The script may mention that these mechanisms are taught later in Videos 11,
23, 37-40, and related lessons. It must not attempt to teach tokenization,
embedding lookup, probability calculation, loss, gradient calculation, or an
optimizer in Video 1.

## Technical Corrections To The Rough Draft

The polished script must correct these points without criticizing the learner:

### 1. Training Data Is Not Automatically “Massive”

Say that useful language models learn from many text examples. The scale can be
large, but “massive” is not part of the definition of learning.

### 2. Text Is Divided According To A Defined Rule

Do not imply that text naturally arrives as tokens. A later mechanism divides
or encodes text into reusable pieces. `Token` is the name for a resulting
piece, not an explanation of how the piece was chosen.

### 3. A Token ID Does Not Turn Into An Embedding

Use this precise relationship:

```text
token -> token ID -> use the ID to select an embedding
```

A token ID is an integer identifier. An embedding is a learned list of numbers
associated with a vocabulary entry and selected by its ID. Do not say that an
ID “is represented by” an embedding, because that phrasing merges two different
jobs.

### 4. A Model Is Not Merely A Collection Of Formulas

For this lesson's scope, define a model as a mathematical prediction system
with adjustable internal numbers called parameters. Later lessons will open the
specific calculations.

### 5. Training Uses A Known Target From The Example

At roadmap level, say that the model's answer is compared with the target
already supplied by the training example. Do not teach the exact shifted-target
or next-token mechanism yet.

### 6. Measured Error Does Not Adjust Parameters By Itself

The roadmap should show measured error leading into a closed **update method**
box, which then changes parameters. This avoids a magical causal jump while
deferring gradients and optimizers to their scheduled lessons.

### 7. A Repeated Update Can Support Improvement, Not Guarantee It

Say that parameter changes can make later predictions less wrong. A tiny
mistake-count example illustrates the idea but cannot prove generalization to
unseen examples.

## Today's Fully Opened Mechanism

After showing the roadmap, close every future box and focus on this question:

> Why must written text receive numbers before the rest of the mathematical
> pipeline can begin?

Teach this mechanism completely:

```text
one character A
-> Python follows a stable standard
-> ord("A") returns code point 65
-> the number identifies the character without containing its human meaning
-> Cat maps to code points 67, 97, 116
-> UTF-8 stores these ASCII-range characters as matching single-byte values
-> the match is not universal
-> name the completed mechanism text representation
```

Use **text representation** as the stable building-block name:

> Text representation changes text into a numerical form that software can
> store and process.

Immediately contrast it with the roadmap's learning stage:

> Representation changes the form of the data. Learning changes adjustable
> model parameters using examples and measured error.

The learner must understand that Unicode code points, UTF-8 bytes, token IDs,
and embeddings are different numerical objects with different jobs. Video 1
fully teaches only the character/code-point/byte boundary. The other two remain
roadmap signposts.

## Narrative Structure

Create a complete approximately fourteen-to-fifteen-minute narration of
1,900-2,200 words with exactly eight timestamped sections.

### 00:00 — The Result And The Question

- Begin with AI rewriting an email, improving an essay, and suggesting code.
- Ask how a system can improve at those tasks from text examples.
- Explain that using the system does not reveal its internal mechanism.
- Promise both a high-level journey map and one fully understood first step.

### 00:50 — The Whole Journey In One Map

- Walk through the corrected roadmap from training text to repeated parameter
  adjustment.
- Give each future signpost one plain-language job and one technical label.
- Use `Cat` only as a label moving across the map, not as a fully tokenized or
  embedded numerical example.
- State that the map shows dependency order, not detailed mechanisms.

### 03:00 — Close The Boxes We Have Not Opened

- Explain the difference between recognizing a label and understanding a
  mechanism.
- Close tokenization, token IDs, embeddings, prediction math, measured error,
  and parameter updates as future boxes.
- Correct the token-ID/embedding relationship locally.
- Identify today's first openable question: why numbers are needed at all.

### 04:00 — Why Text Needs A Numerical Form

- Start with `A` and ask whether `ord` invents a number or follows a stable
  standard.
- Reveal `65`, then name character, Unicode, and code point.
- Correct identifier versus human meaning immediately.
- Expand to `Cat -> 67, 97, 116`.
- Introduce byte and UTF-8 after the code-point sequence is understood.
- Explain the ASCII-range match and its non-universal boundary.
- Name and compress text representation.

### 06:30 — Representation Is Not Learning

- Ask what changed during conversion and what stayed fixed.
- Use the roadmap to identify the missing actions: model answer, known target,
  measured error, closed update method, changed parameters, later answer.
- Use seven mistakes becoming five only as qualified intuition.
- State that it is not the repository's training calculation and does not prove
  performance on unseen examples.
- Stabilize the representation-learning distinction.

### 08:00 — Apply The Distinction To The Repository

- Ask whether `normalize_text` changes data, model parameters, or both.
- Trace the actual order in `matgpt/data/normalize.py`: `str(text)` -> NFKC ->
  newline standardization -> selected control-character removal -> per-line
  trailing-whitespace removal -> outer stripping -> blank-line-run limiting ->
  return.
- Explain that type annotations communicate intended types without runtime
  enforcement.
- Preserve the non-lossless NFKC policy warning: `①` can become `1`, a source
  distinction can collapse, and character count can change.
- Show that `prepare.py` stores normalized text and `len(normalized)`.
- Classify the result as preparation on the text-representation side.

### 10:30 — Predict, Run, And Explain

- Embed the existing `lab.py` source exactly.
- Ask for the `Cat` code-point and UTF-8 list predictions before execution.
- Preserve the exact repository-root command and five-line output.
- Explain `ord`, `encode("utf-8")`, and `list` line by line.
- Change only `Cat` to `A`, apply the rule to predict `[65]`, rerun, explain,
  and restore `Cat`.
- State explicitly that these character numbers are not token IDs or
  embeddings; those belong to later roadmap boxes.

### 13:00 — Return To The Whole Map

- Rebuild the full roadmap once in ordinary language.
- Highlight the exact portion earned today: written character -> stable number
  -> stored bytes -> prepared numerical data.
- Keep all later boxes closed while explaining why they now have a valid input
  dependency.
- Give a transfer exercise: classify a fixed representation step versus a
  parameter-changing learning step.
- Use text representation as the building block for Video 2's question about
  stable character numbers.

## Voice And Flow Contract

The narration must:

- sound like a patient teacher giving the learner a map before starting a long
  journey;
- use `you`, `we`, and `let's` naturally;
- use connected paragraphs with varied sentence lengths rather than a list of
  declarations;
- translate each intimidating roadmap term into one ordinary-language job;
- distinguish “we can locate this box” from “we understand how this box works”;
- use callbacks from the roadmap to create later questions;
- ask for predictions before revealing observable outputs;
- keep stage directions and code outside spoken paragraphs;
- return to the whole map at the end so the opening earns a payoff.

The narration must not:

- recite a glossary before the learner understands the purpose of the map;
- teach later mechanisms through compressed jargon;
- imply that code points, bytes, token IDs, or embeddings are interchangeable;
- imply that text conversion itself is learning;
- say measured error directly changes parameters without acknowledging the
  closed update mechanism;
- promise that fewer training mistakes guarantees useful unseen performance;
- repeat the full roadmap so often that it becomes cognitive noise;
- sound like independent short sentences joined by timestamp headings.

## Repository And Lab Preservation Contract

Script 4 must preserve these verified facts:

1. `ord("A") == 65`; `Cat` maps to code points `67`, `97`, and `116`.
2. Unicode code points and UTF-8 bytes are different layers.
3. Their lists match for ASCII-range `Cat`, but the match is not universal.
4. `normalize_text` calls `str(text)` before NFKC and follows the exact current
   cleanup order described above.
5. Python type annotations in the function communicate intended types but are
   not automatically enforced at runtime.
6. NFKC is deliberate and non-lossless.
7. `prepare.py` stores normalized text and records `len(normalized)`.
8. Repository preparation changes data without changing model parameters.
9. The existing `lab.py` source, invocation command, and five-line output are
   reproduced exactly.
10. The changed `A` case yields `[65]` for both displayed lists and is restored
    afterward.

## Artifact And Change Boundary

Create only this narration deliverable:

```text
course/video_1_script_4.md
```

Planning and review documentation may be added under `docs/superpowers/`.

Do not modify, stage, or commit:

- `script_video1_draft.md`;
- `course/videos/001-computer-learning-from-text/script.md`;
- `course/video_1_improved_script.md`;
- `course/video_1_script_2.md`;
- `course/video_1_script_3.md`;
- repository source code or tests;
- media, video, audio, animation, render, font, or Adobe project files.

## Acceptance Criteria

Script 4 is complete when:

1. it is a standalone Markdown narration of 1,900-2,200 words;
2. it contains exactly the eight approved timestamped sections;
3. its first minute establishes a familiar outcome, central question, roadmap
   promise, and one-step lesson scope;
4. the high-level roadmap uses the corrected dependency order;
5. token, token ID, embedding, prediction, measured error, and parameter update
   remain short signposts rather than prerequisite explanations;
6. the script explicitly says that a token ID selects an embedding rather than
   becoming or being represented by one;
7. every closed roadmap box is visibly deferred;
8. the `A` and `Cat` representation traces are complete and hand-checkable;
9. code points, UTF-8 bytes, token IDs, and embeddings are kept distinct;
10. text representation receives a stable operational definition and is used
    to construct the representation-learning distinction;
11. repository claims match current source order and policy;
12. the lab source, command, output, explanation, and changed case are exact;
13. the ending returns to the roadmap and marks the portion actually earned;
14. a read-aloud review finds connected conversational narration rather than a
    list of sentences;
15. the source draft, existing scripts, source, tests, and media remain
    untouched;
16. focused and full repository tests pass.

## Risks And Controls

- **Risk: the roadmap overloads the learner.** Give each future stage one job,
  name it once, and close it immediately.
- **Risk: signposts become premature teaching.** Enforce the one-to-two-sentence
  limit and prohibit later mechanism details.
- **Risk: the roadmap contains a hidden causal jump.** Show the update method as
  an explicitly closed box between measured error and parameter change.
- **Risk: identifiers and learned vectors are merged.** State the token -> ID ->
  select embedding relationship and contrast their jobs.
- **Risk: the roadmap competes with today's objective.** Spend most narration
  time on the fully opened text-representation mechanism, repository trace, and
  lab.
- **Risk: Script 4 becomes Script 3 with a longer introduction.** Use the whole
  map as a recurring orientation device and return to it at the end, while
  keeping the middle causal explanation concise.
- **Risk: the original draft or unrelated user work is overwritten.** Create a
  new Script 4 file, stage explicit paths only, and verify protected hashes
  before and after implementation.
