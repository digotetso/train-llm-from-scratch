# From a Sentence to a Training Example

## Production Status

- **Canonical source:** `script.md`
- **Target runtime:** 11:45
- **Format:** 1920×1080, 16:9
- **Current state:** Scripted and ready for a new storyboard/render pass
- **Legacy warning:** Existing Manim and After Effects assets implement the superseded Lesson 1. Preserve them for recovery, but do not use them as the visual source for this script.

## Visual System

- Input: consistent cool color with an explicit `input` label.
- Target: consistent warm color with an explicit `target` label.
- Recorded source text: neutral light text.
- Deferred mechanism: muted panel with a lock icon.
- Keep one visual hero per shot.
- Use short crossfades, match cuts, and position-preserving transforms.
- Do not use bounce, spins, or decorative data motion.
- Keep code and terminal text static long enough to read.

## Scene 1 — Hook

**Time:** 00:00–01:10

**Purpose:** Start from familiar AI tools, name the LLM, and ask how text becomes training data.

**Key shots:**

1. Familiar AI text outcomes.
2. `Large Language Model (LLM)`.
3. `The opposite of hot is ___`.
4. Two-second learner prediction.
5. Reveal `cold`.
6. Question card: `How do we train an LLM from text?`

## Scene 2 — Intuition

**Time:** 01:10–02:20

**Purpose:** Let the learner discover the useful cut positions before naming them.

**Key shots:**

1. Six separate word tiles.
2. One movable vertical cut.
3. Left side remains visible; next recorded word is covered.
4. Five cuts accumulate as rows.
5. Prompt: `Six words. How many useful cuts?`

## Scene 3 — Technical Meaning

**Time:** 02:20–03:30

**Purpose:** Name input, target, training example, tokenization, token, token ID, sequence, and the word-level simplification.

**Key shots:**

1. `input` and `target` labels attach to the already-understood sides.
2. Both sides receive the bracket `training example`.
3. Flow: `text → tokenization → tokens → token IDs`.
4. Five expanded rows compress into one shifted window.
5. Boundary card: `Visible words are stand-ins; the real pipeline shifts token IDs.`

## Scene 4 — Tiny Example

**Time:** 03:30–05:10

**Purpose:** Prove the count and shift by hand.

**Key shots:**

1. Build all five prefix questions.
2. Show `prediction positions = 6 - 1 = 5`.
3. Transform the full sentence into aligned input and target rows.
4. Draw five position guides.
5. Keep the growing-prefix view as a small reference while showing the compact rows.

## Scene 5 — Repository Walkthrough

**Time:** 05:10–07:20

**Purpose:** Connect the hand-worked rule to the repository's exact numeric data path.

**Key shots:**

1. Breadcrumb: `matgpt/training/dataset.py`.
2. Highlight `window`, then `window[:-1]`, then `window[1:]`.
3. Apply the slices to `[7, 20, 4, 2, 6]`.
4. Align `x` and `y`.
5. Show one model box receiving the whole `x` row.
6. Place a lock over future positions: `cannot look ahead`.

## Scene 6 — Live Mini-Lab

**Time:** 07:20–09:40

**Purpose:** Predict, run, observe, explain, and transfer.

**Key shots:**

1. Readable `lab.py` panel.
2. Empty prediction cards for position count, `x`, and `y`.
3. Terminal command:

   ```bash
   uv run python course/videos/001-computer-learning-from-text/lab.py
   ```

4. Reveal output in the same order as the learner's predictions.
5. Change only the sentence to `Birds fly over the calm lake`.
6. Hold before revealing the unchanged count of five positions.

## Scene 7 — Common Mistakes

**Time:** 09:40–10:50

**Purpose:** Separate the core mechanism from four likely category errors.

**Correction cards:**

1. `recorded target ≠ only correct continuation`
2. `aligned word ≠ whole available context`
3. `word demonstration ≠ real tokenization`
4. `base pretraining objective ≠ every post-training objective`

End with a footer: `Text supplies targets; people still choose and audit the data pipeline.`

## Scene 8 — Recap And Exercise

**Time:** 10:50–11:45

**Purpose:** Compress the causal chain and build the question that Lesson 2 answers.

**Key shots:**

1. `recorded text → tokens → token IDs`
2. `shift by one position`
3. `input row x + target row y`
4. `next-token prediction at every usable position`
5. Transfer case: `Birds fly over the calm lake`
6. Closing line: `Show the sequence so far. Predict the recorded next token.`
7. Transform one token ID into an `embedding` vector.
8. Next question: `How does a token ID become an embedding?`
