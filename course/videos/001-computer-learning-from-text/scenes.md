# What Does It Mean for a Computer to Learn From Text?

## Overview

- **Topic**: Why text needs numeric representation before a mathematical model can learn from it
- **Hook**: A person and a Python program can receive the same three letters without receiving the same thing
- **Target Audience**: Beginners who can read a Python string and a short list
- **Estimated Length**: 14 minutes
- **Key Insight**: Fixed text mappings supply numbers; learning changes different numbers inside the model

## Narrative Arc

The lesson begins with two perspectives on `cat`: human associations and a
program's represented input. It progressively builds a numeric view, carries
that view through a tiny prediction loop and real repository preparation code,
then resolves the common confusion between representation and learning.

---

## Scene 1: Same Word, Different Input

**Duration**: 45 seconds

**Purpose**: Establish the central contrast and learning objective.

### Visual Elements

- Large lowercase `cat` centered on an empty dark canvas
- Amber human silhouette with thought bubbles for animal, memory, and sound
- Cyan terminal window containing a Python string and small data blocks
- A thin vertical divider
- Objective card revealed at the end

### Content

Start with only `cat`. Duplicate the word and move one copy left toward the
human silhouette and one right toward the terminal. The human copy branches
into suggestive icons while the terminal copy breaks into three character
cells. Remove the icons and cells, then center the objective: explain why text
must become numbers before a model can learn patterns from it.

### Narration Notes

Hold the first word long enough for the opening question. Keep the contrast
curious rather than adversarial; the computer is receiving different input,
not failing a human test.

### Technical Notes

- Use `Text`, `RoundedRectangle`, `VGroup`, and simple vector icons
- Prefer `TransformFromCopy` to preserve the identity of `cat`
- Use no raster imagery

---

## Scene 2: Fixed Numbers and Adjustable Numbers

**Duration**: 75 seconds

**Purpose**: Create the two categories that organize the lesson.

### Visual Elements

- `A` transforming into `U+0041` and decimal `65`
- Four amber context cards: grade, note, blood type, word
- Cyan `FIXED REPRESENTATION` lane with a lock icon
- Green `ADJUSTABLE PARAMETERS` lane with three sliders
- Labels `encoding` and `learning`

### Content

Transform `A` into its code-point notation and decimal value. Fan out the four
contexts around the unchanged character and code point. Collapse the screen
into two lanes: the fixed mapping supplies numeric data, while the model's
parameters can move during learning. Finish with both lanes visible and clearly
separate.

### Narration Notes

Emphasize that Python returns the same value because the assignment is defined
by a standard. Do not imply that code-point numbers contain context.

### Technical Notes

- Use solid cyan borders for fixed mappings
- Animate green slider knobs only in the adjustable lane
- Add text labels so color is never the only distinction

---

## Scene 3: Characters, Code Points, Bytes, and a Model

**Duration**: 120 seconds

**Purpose**: Define the lesson's technical terms through one concrete example.

### Visual Elements

- Three aligned character cards: `C`, `a`, `t`
- `ord(...)` function box
- Code-point row: `67`, `97`, `116`
- Eight-cell bit strip labeled `byte`
- UTF-8 byte row matching the code-point row
- Warning ribbon: `These match here—not for every character`
- Minimal model box with numeric inputs, prediction, error meter, and parameter dials

### Content

Process each character through `ord` one at a time. Keep the characters aligned
with their numbers. Convert one number into an eight-bit byte strip, then reveal
the byte range 0-255. Duplicate the three-number row as UTF-8 bytes and attach
the non-universal warning. Move the numeric row into a model diagram. Reveal
prediction, measured error, and adjustable parameters in that order.

### Narration Notes

Pause after each new term. State that a model is mathematical operations with
adjustable parameters, not a character mapping.

### Technical Notes

- Use `TransformMatchingShapes` where character-number alignment benefits
- Build the model with shapes rather than a literal neural-network diagram
- Avoid introducing future vocabulary

---

## Scene 4: A Tiny Pattern and a Smaller Error

**Duration**: 120 seconds

**Purpose**: Show how represented examples can affect later parameter updates.

### Visual Elements

- Three lines: `cat sat`, `cat ran`, `cat slept`
- Consistent highlights on `cat`, spaces, and following action words
- Hand-check table for `C a t` and `67 97 116`
- Before/after ten-cell prediction boards
- Seven red error cells becoming five
- Circular loop: examples, prediction, error, update, later evaluation
- Caption `Illustration—not observed training output`

### Content

Write the three examples one at a time. Align them and highlight the repeated
positions without assigning animal or action categories to the input. Return to
the numeric hand-check and show permitted operations: first-value comparison,
length three, and sequence equality. Explicitly cross out a semantic
interpretation of arithmetic distance. Build the ten-prediction board, reduce
red mistakes from seven to five after a parameter adjustment, and close the
loop with later evaluation on separate examples.

### Narration Notes

Call the 7-to-5 count a simple illustration. Mention memorization as a reason to
evaluate separately without expanding into future terminology.

### Technical Notes

- Use braces and alignment rather than large paragraphs
- Keep the illustration disclaimer persistent during the error-board sequence
- Use green only for the two improved cells and update arrow

---

## Scene 5: Repository Walkthrough

**Duration**: 180 seconds

**Purpose**: Show verified preprocessing behavior without calling it learning.

### Visual Elements

- Breadcrumbs for `matgpt/data/normalize.py` and `matgpt/data/prepare.py`
- Simplified syntax-highlighted code panel from the script
- Moving line highlight and margin callouts
- Input/output text cards
- NFKC demonstration `① -> 1`
- Red warning card `Policy choice—not lossless cleanup`
- Record card containing `text` and `num_chars`
- Separation marker: `PREPARATION ≠ LEARNING`

### Content

Reveal the `normalize_text` excerpt line by line. Follow one source text card
through NFKC, newline normalization, trailing-space removal, outer stripping,
and return. Interrupt the smooth flow with the circled-one example and warning.
Then switch breadcrumbs to `prepare.py`, animate `normalized =
normalize_text(text)`, and store the result and Python string length in the
record card. End by placing this work in the preparation lane, upstream of the
model.

### Narration Notes

Read code from top to bottom and explain only the displayed lines. State that
annotations communicate expectations but do not enforce types at runtime.
Mention omitted control-character and blank-line behavior without adding it to
the simplified panel.

### Technical Notes

- Use `Code` only if its installed-version API is stable in the project; a
  custom monospace text panel is the fallback
- Dim all non-active lines to reduce scanning load
- Preserve the exact simplified excerpt from the script

---

## Scene 6: Live Mini-Lab

**Duration**: 180 seconds

**Purpose**: Let the viewer predict, run, and interpret the verified lab output.

### Visual Elements

- Editor panel for `lab.py`
- Prediction cards for the two lists
- Terminal command prompt from the repository root
- Exact five-line output
- Character-to-number connectors
- One-line edit `text = "Cat"` to `text = "A"`
- Final restoration to `Cat`

### Content

Show the lab source, then isolate `text = "Cat"`. Pause on two empty prediction
cards before filling both with `[67, 97, 116]`. Type the documented command in a
terminal and reveal the output one line at a time. Connect each list item back
to its character. Replace only `Cat` with `A`, predict `[65]`, rerun visually,
and restore the source line to `Cat`.

### Narration Notes

State that the lab displays two numeric views, not the exact later model input.
Explain that Python can process strings as text while the mathematical model
needs numeric input. Reinforce that matching lists are special to this example.

### Technical Notes

- Display verified output rather than running a subprocess during render
- Use a cursor animation sparingly and keep terminal text static after reveal
- Match punctuation and capitalization in `lab.py` exactly

---

## Scene 7: Representation Is Not Meaning

**Duration**: 60 seconds

**Purpose**: Correct the two most likely misconceptions.

### Visual Elements

- Central `A` and locked cyan `65`
- Four amber context cards orbiting the character
- False equation `65 = meaning of A` crossed out
- Fixed `ord("A")` machine
- Green parameter sliders responding to red error signals
- Two-question comparison card

### Content

Keep `A` and `65` fixed while context cards rotate through grade, note, blood
type, and word. Cross out the claim that 65 is the meaning. Ask whether another
mapping would force human meaning to change, then answer no. Repeat the fixed
`ord` mapping several times with identical output. Contrast it with parameter
sliders that change only when error signals arrive from examples.

### Narration Notes

Use the mapping-change question as the learner's reusable check. Keep
conversion and learning spatially separated.

### Technical Notes

- Use `Indicate` on the unchanged 65 during context changes
- Reserve red for the false claim and error signals
- Do not animate the fixed-mapping lane's internals

---

## Scene 8: The Complete Sequence

**Duration**: 60 seconds

**Purpose**: Consolidate the objective and leave a concrete exercise.

### Visual Elements

- Complete left-to-right pipeline
- Four numbered recap cards
- Five self-check questions revealed rapidly but legibly
- Exercise card with the fill-in-the-blank sentence
- Closing bridge to Video 2

### Content

Rebuild the pipeline as `TEXT -> NUMBERS -> PREDICTION -> ERROR -> PARAMETER
UPDATE`. Attach the four recap claims to the relevant nodes rather than showing
a detached bullet list. Reveal the self-check questions in two compact groups.
End with the command to run the lab using `A` and the sentence: `The number 65
is assigned to ___, but it does not encode ___.` Restore `Cat` on the final
editor card and point forward to assigned character numbers in Video 2.

### Narration Notes

Return explicitly to the learning objective. Give the exercise the final hold
so a viewer can pause or copy it.

### Technical Notes

- Reuse visual objects or exact theme shapes from earlier sections
- Keep the final exercise on screen for the longest pause in the section
- End on a stable frame suitable for a chapter thumbnail

---

## Transitions and Flow

- The word `cat` is the primary continuity object.
- Cyan numeric cards move left to right; they never morph into green parameters.
- A thin lower pipeline grows one node at a time across the lesson.
- Section transitions use object transforms and spatial handoffs where the
  relationship matters; full fades are reserved for major context resets.
- Every section ends with a resolved composition before the next timestamp.

## Color Palette

- **Fixed representation**: `#58C4DD`
- **Learning and improvement**: `#83C167`
- **Human context and attention**: `#F5C451`
- **Error and misconception**: `#FF6B6B`
- **Primary text**: `#F3F6FA`
- **Secondary detail**: `#8B95A7`
- **Background**: `#0B1020`

## Mathematical and Code Content

- `ord("C") = 67`
- `ord("a") = 97`
- `ord("t") = 116`
- `ord("A") = 65`
- byte range `0` through `255`
- before/after illustration: `7/10` errors to `5/10` errors
- exact simplified `normalize_text` and `prepare.py` excerpts from `script.md`
- exact `lab.py` command and output

## Implementation Order

1. Theme, timeline validation, and timing helpers
2. Shared cards, panels, pipeline, and layout helpers
3. Scene 1 and Scene 8 to validate the visual system and continuity
4. Scene 3 numeric transformations
5. Scene 5 code walkthrough
6. Scene 6 terminal mini-lab
7. Scenes 2, 4, and 7
8. Full preview render, representative-frame inspection, and timing refinement
9. Final 1080p render
