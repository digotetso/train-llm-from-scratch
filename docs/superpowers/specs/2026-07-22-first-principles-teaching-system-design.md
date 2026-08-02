# First-Principles Teaching System Design

**Date:** 2026-07-22  
**Status:** Approved in conversation on 2026-07-22

## Goal

Define a reusable teaching system for this course, package the transferable
workflow as a Codex skill, and apply it to Video 1 before the narration is
finalized.

The system must help a true beginner build a causal mental model instead of
copying terminology or code. It must remain warm and natural when spoken while
preserving every detail needed to explain why the observed behavior occurs.

## Sources And Scope

The design synthesizes pedagogical patterns from:

- Tony Alicea, *JavaScript: Understanding the Weird Parts - The First 3.5
  Hours*: https://www.youtube.com/watch?v=Bv_5Zv5c-Ts
- J. Clark Scott, *But How Do It Know? - The Basic Principles of Computers for
  Everyone*, First Edition, July 2009, supplied as a local PDF.

The video was analyzed for spoken progression, phrasing functions, transitions,
and the relationship between definitions and examples. The book was analyzed
for concept ordering, causal completeness, abstraction, anticipated questions,
and the accumulation of simple components into a complete system.

This design borrows general teaching methods. It does not reproduce either
author's wording or attempt to impersonate either author.

## Audience

The primary learner can:

- run a Python file;
- read simple strings, lists, function calls, and printed output;
- perform small arithmetic by hand;
- ask intelligent questions without already knowing technical vocabulary.

No machine-learning, tokenization, tensor, Unicode, or Transformer knowledge is
assumed unless an earlier approved lesson has taught it.

## Chosen Synthesis

Use a layered approach: conversational on the surface and first-principles
underneath.

The spoken layer should have the warmth, momentum, orientation, and low anxiety
of a patient lecture. The explanatory structure should have the completeness of
a carefully assembled machine: one understandable component at a time, no
hidden causal gaps, and every later abstraction built from earlier knowledge.

In short: make the narration easy to enter without making the reasoning shallow.

## Core Teaching Philosophy

Do not ask the learner to imitate an expert. Help the learner construct a mental
model that can explain, predict, and transfer.

A successful lesson leaves the learner able to:

1. state the lesson's one central question;
2. explain the mechanism in ordinary language;
3. use the correct technical term after understanding the mechanism;
4. predict a small example before seeing the answer;
5. trace the observed result from input through operations to output;
6. distinguish the mechanism from its analogy and representation;
7. apply the rule when one part of the example changes;
8. connect the concept to the next layer of the course.

## The Concept-Teaching Sequence

Use the following sequence for every major concept. Compress steps when the idea
is simple, but do not change their dependency order.

### 1. Begin With A Real Question

Start with something the learner may genuinely wonder, misinterpret, or find
surprising. Establish why the answer matters before naming terminology.

### 2. Activate Familiar Knowledge

Connect the question to an ordinary experience or to a mechanism already taught
in the course. The familiar case provides a starting point, not proof.

### 3. Expose The Apparent Mystery

Show the difference between appearance and mechanism. Make the learner curious
about what must happen underneath.

### 4. Isolate The Smallest Mechanism

Introduce only the components needed for the current explanation. Do not import
later vocabulary to make an early explanation sound complete.

### 5. Ask The Learner To Reason

Request a prediction, comparison, trace, or small mental simulation. Give the
learner a reason to commit to an answer before revealing the result.

### 6. Name The Technical Concept

Introduce the accepted technical term after its behavior is understandable.
Treat terminology as a useful label, not as the explanation.

### 7. Trace The Causal Chain

Walk from input to operation to output. Account for each meaningful change. Do
not use phrases such as “the model understands” or “the computer decides” unless
the concrete operation has already been explained and the shorthand is clearly
bounded.

### 8. Prove It With A Tiny Example

Use text, numbers, or code small enough to inspect completely. The example must
demonstrate the mechanism rather than merely produce the expected answer.

### 9. Anticipate The Careful Beginner's Question

Answer the likely misconception at the point where it arises. Prefer questions
that reveal category errors: identifier versus meaning, preparation versus
learning, analogy versus mechanism, or correlation versus cause.

### 10. Compress The Mental Model

End the concept with one short statement the learner can retain and use. The
statement must remain accurate within the lesson's declared scope.

### 11. Turn The Concept Into A Building Block

Once the internals are understood, give the concept a stable name or simple
representation. Reuse that abstraction in the next layer without repeatedly
opening every internal detail.

## Spoken Voice Standard

Narration should sound like a patient teacher reasoning alongside the learner.

Use:

- direct address with `you`, `we`, and `let's` where natural;
- short and medium spoken sentences;
- questions that advance reasoning rather than decorate the script;
- contractions when they improve read-aloud rhythm;
- brief orientation before a conceptual aside;
- explicit recaps of knowledge needed for the next step;
- calm reassurance when terminology sounds difficult;
- concrete verbs that name what code or data actually does.

Avoid:

- document instructions spoken aloud, such as “restatement of the objective”;
- dense strings of qualifications in one sentence;
- abstract nouns where an observable action is available;
- announcing several new terms before explaining any of them;
- exaggerated excitement, fake suspense, or patronizing reassurance;
- repeated conclusions that add no new connection;
- author-specific catchphrases used as imitation.

## Explanation Rules

### Terminology

- Explain the behavior before naming the term.
- Define one new term at a time when possible.
- Reuse the course glossary definition unless evidence requires correction.
- Do not use a future term as the explanation for a current term.

### Analogies

- Use an analogy only when it reduces a real conceptual burden.
- State the shared relationship between analogy and mechanism.
- State where the analogy stops matching.
- Return to the actual system before drawing a conclusion.
- Never require an analogy when a concrete example is already simpler.

### Examples And Labs

- Keep the first example hand-checkable.
- Ask for a prediction before execution.
- Change one variable at a time.
- Explain why the observed output follows from the mechanism.
- Include a changed case that distinguishes understanding from memorization.
- Treat code as evidence for the mental model, not as text to copy.

### Simplification And Caveats

Simplification may remove unnecessary detail, but it may not remove a necessary
cause or change a category.

Use this order:

1. state the useful beginner explanation;
2. add a short immediate qualification when omission would mislead;
3. name the deeper question being deferred;
4. identify the later lesson that will answer it when known.

Do not stack caveats before the learner understands the central idea.

### Evidence

- Tie repository claims to inspected source, tests, commands, or artifacts.
- Distinguish source facts, observed behavior, teaching analogies, and inferences.
- Preserve input, output, units, and important boundary conditions.
- Correct or reject dated claims from reference material.

## Lesson-Level Flow

The default video sequence remains:

1. Hook: a meaningful beginner question.
2. Intuition or analogy: a familiar bridge with a stated limit.
3. Technical meaning: names for ideas the learner now recognizes.
4. Tiny example: a complete hand-checkable trace.
5. Repository walkthrough: verified source connected to the mental model.
6. Mini-lab: prediction, execution, observation, and one controlled change.
7. Common mistake: a likely category error and a diagnostic question.
8. Recap and exercise: the causal model in a compact form and a transfer task.

Transitions should carry the learner's current conclusion into the next question.
Sections must not feel like independent notes joined by headings.

## Artifact Responsibilities

- `script.md`: natural spoken explanation and stage directions.
- `lesson.md`: fuller reference explanation, terminology, and caveats.
- `lab.md` and runnable files: prediction and observable behavior.
- `quiz.md`: checks explanation and transfer, not recall alone.
- `answer-key.md`: explains why each answer follows.
- `evidence.md`: sources and verification for technical claims.

The spoken script may defer detail to companion artifacts, but it may not depend
on an unseen artifact to make its central causal explanation coherent.

## Codex Skill Design

Create a reusable personal skill named `teaching-technical-concepts` in the
default Codex skills directory so it can be auto-discovered across projects.

The skill should trigger when Codex is asked to write, rewrite, structure, or
review beginner-facing technical lessons, course material, video narration,
labs, or explanatory documentation.

The skill will contain:

- `SKILL.md`: concise workflow, core sequence, output contract, and review gate;
- `references/technical-teaching-standard.md`: the detailed voice, analogy,
  example, caveat, evidence, and review rules;
- `agents/openai.yaml`: generated UI metadata.

No custom scripts or assets are required. The work depends on judgment rather
than a deterministic transformation.

The skill must be initialized with the system `init_skill.py`, validated with
`quick_validate.py`, and forward-tested on realistic lesson-writing tasks.

## Video 1 Rewrite Contract

Rewrite
`course/videos/001-computer-learning-from-text/script.md` without changing its
verified learning objective, commands, repository behavior, or deferred
vocabulary boundary.

The rewrite must:

1. restore a human experience of reading `cat` as the opening contrast;
2. state what information the computer actually receives;
3. use an analogy only as a bridge between identifier and meaning;
4. introduce `character`, `Unicode`, `code point`, `byte`, and `UTF-8` after the
   representation idea is understandable;
5. keep code points distinct from UTF-8 bytes;
6. explain why the two numeric lists match for ASCII-range `Cat` without
   implying they always match;
7. separate fixed text representation from adjustable model parameters;
8. use the tiny mistake-count example only as an intuition for improvement;
9. connect repository normalization to data preparation, not model learning;
10. preserve the NFKC policy warning without derailing the main explanation;
11. ask for predictions before the lab runs;
12. correct both “65 is the meaning of A” and “conversion is learning”;
13. end with a compact, memorable distinction between representation and
    learning;
14. sound natural when read aloud.

The script must not teach token, tensor, logit, gradient, attention, or token
embedding as part of the explanation.

## Acceptance Criteria

### Teaching System

- The specification is complete, internally consistent, and contains no
  placeholders.
- Each rule can be evaluated in a script review.
- Source-specific mannerisms and dated factual claims are excluded.

### Codex Skill

- A no-skill baseline demonstrates at least one meaningful teaching failure.
- The skill changes the same scenario toward the approved teaching contract.
- YAML frontmatter contains only `name` and `description`.
- The description begins with `Use when` and describes triggering conditions.
- `agents/openai.yaml` matches the skill and names `$teaching-technical-concepts`
  in its default prompt.
- `quick_validate.py` passes.
- Forward tests cover drafting, rewriting, and reviewing a technical lesson.

### Video 1

- Required headings and approximate section order remain valid.
- Existing commands and expected outputs remain correct.
- Repository excerpts remain faithful to implementation.
- Focused course-structure and teaching-contract tests pass.
- The complete relevant test suite passes.
- A read-aloud review finds no unexplained terminology, document-like
  instructions, or preventable caveat stacks.

## Non-Goals

- Imitating either source author's exact voice.
- Copying sentences from the video or book.
- Rewriting other course videos in this change.
- Changing production data, tokenizer, model, or training code.
- Expanding Video 1 into later tokenization or Transformer concepts.
- Treating an analogy as technical evidence.

## Risks And Mitigations

- **Risk: narration becomes too long.** Keep one objective and defer mechanisms
  owned by later lessons.
- **Risk: warmth weakens precision.** Verify every technical claim against code,
  tests, or a primary standard.
- **Risk: precision produces academic prose.** Run a read-aloud pass and replace
  document instructions with learner-directed transitions.
- **Risk: the skill becomes project-specific.** Keep the skill's core workflow
  reusable and place course-specific constraints in this specification.
- **Risk: tests overfit exact wording.** Test structural teaching contracts and
  factual boundaries, not preferred sentences.

## Planned Files

- Create:
  `docs/superpowers/plans/2026-07-22-first-principles-teaching-system.md`
- Create in the personal Codex skills directory:
  `teaching-technical-concepts/SKILL.md`
- Create in the same skill:
  `teaching-technical-concepts/references/technical-teaching-standard.md`
- Generate in the same skill:
  `teaching-technical-concepts/agents/openai.yaml`
- Modify:
  `course/videos/001-computer-learning-from-text/script.md`
- Modify or create focused tests under `tests/` for the Video 1 teaching
  contract.

