# Video 1 Spoken-English Rewrite Design

## Goal

Rewrite `final_final copy` so the narration sounds like a patient teacher speaking naturally to a learner. Keep the lesson accurate, conversational, and within a 10-to-15-minute video.

## Learner

The learner has used an AI text box and can run a small Python file. The learner is not expected to know how text is stored, what Unicode is, or how an LLM is trained.

## Lesson Objective

By the end of the lesson, the learner should be able to:

- explain why we inspect text before preparing it;
- use a tiny Python example to reveal spaces, tabs, and line endings;
- explain that similar-looking characters can still be different;
- describe, in ordinary language, how the example prepares text;
- predict how the same preparation steps will change a second example.

## Rewrite Approach

Use a full spoken-English rewrite while preserving the approved concept order, examples, code, and approximate timing.

The narration will:

- use simple, common English;
- use `you`, `we`, `let's`, and contractions where they sound natural;
- favor short and medium sentences that can be spoken in one breath;
- explain an idea in ordinary language before giving it a technical name;
- connect sections through cause and effect instead of announcing topics;
- keep code, stage directions, headings, and displayed text outside spoken paragraphs;
- avoid formal phrases that sound natural in documentation but stiff when spoken.

Examples of preferred wording:

- “choices based on what we need the text for,” not “purpose-dependent decisions”;
- “the lines we kept,” not “retained values”;
- “the result shows that they are stored as different characters,” not “the result is storage evidence”;
- “find the first step where your answer changed,” not “find where your causal trace diverged.”

## Teaching Sequence

The script will keep this dependency order:

1. Show where this lesson fits in the larger process of training an LLM.
2. Ask what the computer actually receives when we give it text.
3. Reveal details that ordinary printing can hide.
4. Show that similar-looking symbols can be stored as different characters.
5. Explain the shared numbering system, then name Unicode and code points.
6. Let the learner choose which differences should change for this example.
7. Explain the changes, then name normalization and text preparation.
8. Trace the complete Python program without skipping a step.
9. Ask the learner to predict, run, observe, explain, and change one input.
10. End with a short mental model that becomes a building block for the next lesson.

## Technical Boundaries

- A code point identifies a character; it is not a number that represents a token or its meaning.
- NFKC is a selected rule for this lesson, not a universal definition of correct or clean text.
- Inspection reveals what is present without changing the source.
- Preparation changes text according to rules chosen for the intended use.
- Later LLM-training terms will not be used before they are taught.

## Scope

### In scope

- Rewrite all spoken narration in `final_final copy`.
- Adjust transitions and paragraph boundaries for natural speech.
- Make small timing adjustments needed to keep the video near 13 minutes.
- Correct any unclear wording found during the spoken-language audit.

### Out of scope

- Changing the course topic or technical mechanism.
- Adding media, video, animation, or production assets.
- Replacing the Python example with a repository walkthrough.
- Editing the preserved long-script backup.
- Introducing later LLM-training concepts in detail.

## Acceptance Criteria

- The narration sounds natural when read aloud.
- Common words are used whenever they can express the same idea accurately.
- No technical term is needed to understand the sentence that introduces it.
- Each section grows from the conclusion of the previous section.
- The code and displayed output agree exactly.
- The second example tests the same rule with changed input.
- The estimated spoken runtime remains between 10 and 15 minutes, with a target near 13 minutes.
- The original long-script backup remains unchanged.
- No media or video files are added.

## Verification

After rewriting:

1. Separate narration from code and stage directions.
2. estimate narration word count and section pacing;
3. scan for long sentences, formal wording, and unexplained terms;
4. verify terminology appears only after its plain-language explanation;
5. run the Python examples and compare the output with the script;
6. run the relevant test suite;
7. inspect the final Git diff to confirm that unrelated files were not changed.
