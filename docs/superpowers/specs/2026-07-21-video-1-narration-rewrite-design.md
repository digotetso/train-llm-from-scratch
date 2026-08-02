# Video 1 Narration Rewrite Design

**Date:** 2026-07-21

## Goal

Rewrite `course/videos/001-computer-learning-from-text/script.md` so it sounds
like a warm, confident teacher speaking to a true beginner. Improve flow,
clarity, rhythm, and transitions without weakening technical accuracy or
changing the lesson's verified behavior.

## Audience And Voice

The audience can read simple Python but is assumed to know nothing about
machine learning, Unicode, tokenization, or Transformers.

The narration should be:

- conversational rather than document-like;
- confident without overstating what the program or model understands;
- patient, with one new technical term introduced at a time;
- concise enough to read aloud naturally;
- precise whenever representation, meaning, preparation, and learning are
  distinguished.

## Rewrite Structure

Preserve the existing lesson sequence and approximate timestamps:

1. Hook: contrast a person's experience of `cat` with the text data received
   by a computer.
2. Analogy: restore the library-identifier analogy from the companion lesson.
3. Technical meaning: introduce character, Unicode, code point, byte, UTF-8,
   model, parameter, learning, and pattern only after the intuition is clear.
4. Tiny example: use `Cat`, the three short training examples, and the simple
   before-and-after mistake count.
5. Repository walkthrough: explain normalization and preparation using the
   existing verified code excerpts.
6. Mini-lab: preserve the current commands, predictions, and expected output.
7. Common mistakes: distinguish assigned character numbers from meaning and
   distinguish representation from learning.
8. Recap and exercise: finish with a short, memorable explanation and retain
   the learner check.

The `00:45` section heading will be `Analogy`, matching the companion lesson
and course structure contract.

## Content Constraints

- Preserve the learning objective: explain why text needs a numeric
  representation before a mathematical model can learn patterns from it.
- Preserve the factual distinction between Unicode code points and UTF-8
  bytes.
- State that the matching values for `Cat` are a property of these ASCII-range
  characters, not a universal rule.
- Preserve the warning that NFKC normalization is a deliberate, potentially
  lossy policy.
- Keep the repository code excerpts behaviorally faithful to
  `matgpt/data/normalize.py` and `matgpt/data/prepare.py`.
- Do not teach token, tensor, logit, gradient, or attention in this video.
- Mention token embeddings only as explicitly deferred vocabulary if needed;
  do not use them to explain the lesson.
- Do not imply that character identifiers contain meaning or that encoding is
  itself learning.
- Do not modify the lab, lesson, quiz, answer key, evidence, or production code
  as part of this rewrite.

## Flow And Read-Aloud Rules

- Prefer short sentences and familiar words before technical labels.
- Use a question or conclusion from one section to lead into the next.
- Avoid stacking several qualifications in one spoken sentence.
- Keep essential caveats, but present them immediately after the simplified
  statement they qualify.
- Separate stage directions and on-screen code from spoken narration.
- Use contractions where they make the teacher sound natural.
- End major sections with one sentence that states what the learner should
  remember.

## Verification

After rewriting:

1. Compare every technical claim with the companion lesson and repository
   source files.
2. Confirm the script retains all required headings and expected order.
3. Run the focused Video 1 course-structure tests.
4. Run the complete repository test suite in a clean tree so unrelated local
   work cannot distort the result.
5. Perform a read-aloud review for sentence length, transitions, repeated
   wording, and unexplained jargon.

## Non-Goals

- Changing the lesson's technical scope.
- Adding later Transformer or training mathematics.
- Rewriting other Video 1 artifacts.
- Producing animation, slides, or recorded audio.
- Changing repository implementation code.
