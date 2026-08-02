# Video 001 Manim Animation Design

Date: 2026-07-21

Status: Approved design, awaiting written-spec review

## 1. Purpose

Create a production-ready Manim Community animation for
`course/videos/001-computer-learning-from-text/script.md`. The result will be a
single 16:9 educational video whose visuals follow the script's timestamps. No
narration audio is available, so timing will come from the script rather than an
audio waveform.

The animation must help a beginner distinguish two ideas:

1. text receives fixed numeric representations; and
2. learning later updates separate model parameters in response to error.

## 2. Source Facts

- The script targets a beginner with no assumed machine-learning knowledge.
- The repository's course contract expects one 10-15 minute video.
- The script contains eight anchors from `00:00` through `13:00`.
- `lab.py` prints the Unicode code points and UTF-8 bytes for `Cat`.
- `matgpt/data/normalize.py` applies NFKC normalization and other cleanup.
- `matgpt/data/prepare.py` stores normalized text and `num_chars`.
- The repository currently has no Manim source, configuration, or voiceover
  pipeline.
- The working copy of `script.md` contains user changes and must remain
  untouched by animation implementation.

## 3. Decisions

- Use Manim Community Edition, not ManimGL.
- Record Manim as an optional, reproducibly pinned project dependency so model
  training and course-document workflows do not require video tooling.
- Produce one master scene with eight named sections.
- Implement each section as a focused method so it can be reasoned about and
  revised independently.
- Use script timestamps as section boundaries and target a 14-minute normal
  render.
- Add a preview timing mode that preserves animation order while shortening
  waits and run times for development renders.
- Use only generated vector shapes and rendered text/code. No external stock
  assets are required.
- Target 1920x1080, 30 fps, and a 16:9 frame for the final render.
- Keep the animation silent. Audio synchronization and text-to-speech are
  outside this version.

## 4. Non-Goals

- Do not rewrite or simplify the approved narration script.
- Do not teach tokens, tensors, logits, gradients, or attention.
- Do not depict code points as learned meanings or model inputs beyond the
  narrow claims in the script.
- Do not imply that the 7-to-5 error example is observed repository training
  evidence.
- Do not add a voiceover service, music, sound effects, or external media.
- Do not animate later course videos.

## 5. Delivery Architecture

The implementation will live beside the lesson artifacts:

```text
course/videos/001-computer-learning-from-text/
  animation.py
  manim.cfg
  scenes.md
  script.md
  lab.py
```

`animation.py` will contain:

- immutable visual theme and timeline data;
- small helpers for titles, labels, code panels, terminal panels, number cards,
  and timed pauses;
- one method per timestamped section; and
- one public master `Scene` class that calls the eight methods in order.

The master scene will mark boundaries with Manim's section API. A normal render
produces one continuous movie, while `--save_sections` can also emit the eight
timestamped clips for focused review and replacement.

The section methods will communicate through explicit recurring visual motifs,
not hidden mutable state. Objects that visually carry across a boundary will be
returned by one helper or reconstructed from shared theme constants.

`manim.cfg` will define the final frame size, frame rate, background, output
directory, and media behavior. Command-line quality flags may override quality
during development.

## 6. Timeline And Narrative Arc

The narrative combines two patterns: two perspectives becoming one pipeline,
and a common misconception becoming a precise distinction.

| Section | Start | End | Duration | Visual objective |
|---|---:|---:|---:|---|
| Hook | 00:00 | 00:45 | 45 s | Contrast human associations with program data. |
| Fixed versus adjustable | 00:45 | 02:00 | 75 s | Establish the two categories used throughout. |
| Technical meaning | 02:00 | 04:00 | 120 s | Build character, code-point, byte, model, and learning concepts progressively. |
| Tiny example | 04:00 | 06:00 | 120 s | Connect repeated text patterns to measured prediction improvement. |
| Repository walkthrough | 06:00 | 09:00 | 180 s | Trace source text through normalization and storage without calling it learning. |
| Live mini-lab | 09:00 | 12:00 | 180 s | Predict and reveal the `Cat` and `A` numeric views. |
| Common mistake | 12:00 | 13:00 | 60 s | Show one fixed code point across changing human contexts. |
| Recap and exercise | 13:00 | 14:00 | 60 s | Resolve the full text-to-learning pipeline and leave the exercise on screen. |

The detailed shot and animation specification is in
`course/videos/001-computer-learning-from-text/scenes.md`.

## 7. Visual Language

Use a dark academic canvas with generous empty space and high-contrast text.
Color must carry the same meaning in every section:

- background: near-black navy `#0B1020`;
- fixed text representations: cyan `#58C4DD`;
- learning and improvement: green `#83C167`;
- human context and attention: amber `#F5C451`;
- errors and misconceptions: coral red `#FF6B6B`;
- neutral labels and code: soft white `#F3F6FA`;
- secondary detail: slate `#8B95A7`.

The recurring pipeline is spatially consistent from left to right:

```text
TEXT -> NUMBERS -> PREDICTION -> ERROR -> PARAMETER UPDATE
```

Early sections reveal only the relevant portion. The complete sequence appears
only in the recap. Fixed-mapping objects use solid cyan borders. Adjustable
parameter objects use green controls or sliders. Human interpretations use
amber thought bubbles. Red is reserved for mistakes, warnings, and the word
`ERROR`.

## 8. Content And Data Flow

The visual information flow follows the lesson claims:

1. Display `cat` as human-readable text.
2. Split the view into human associations and a Python data path.
3. Transform `C`, `a`, and `t` into `67`, `97`, and `116` while retaining
   one-to-one visual alignment.
4. Show the same values as UTF-8 bytes only for this ASCII-range example, with a
   visible warning that this equality is not universal.
5. Move represented examples into a small abstract model, then visualize
   prediction, measured error, and adjustable parameters.
6. Inspect actual repository preparation code as a separate preprocessing path.
7. Reproduce the mini-lab output exactly.
8. Recombine the ideas into the complete pipeline.

Transforms are preferred over replacement fades where they clarify continuity.
Long code blocks use a moving highlight and dimmed surrounding lines so the
viewer never has to scan the entire listing at once.

## 9. Timing Model

Normal mode must allocate exactly 840 seconds across the eight sections. Each
section owns a declared duration budget. Its animations and pauses must sum to
that budget.

Preview mode will apply a single small scale factor to animation run times and
pauses. The content, order, section names, and final states must remain the same.
Preview mode is a development aid and must not affect the default render.

Timing calculations will be pure functions so they can be unit tested without
invoking the renderer.

## 10. Failure Handling

- Timeline validation fails before rendering if section names are duplicated,
  boundaries are not contiguous, or total normal duration is not 840 seconds.
- Layout helpers constrain text and code to safe frame bounds. Tests cover the
  mathematical bounds; representative frames receive visual inspection.
- Unsupported fonts fall back to Manim's available default rather than making
  the lesson depend on a machine-specific font.
- The animation uses the repository excerpts as displayed in the script. It
  will not dynamically import or execute training code while rendering.
- The lab output is stored as explicit verified display text so a render does
  not mutate `lab.py` or depend on a subprocess.
- Manim or system dependency failures must report the missing dependency rather
  than silently omitting a scene.

## 11. Accessibility And Legibility

- Do not encode a distinction by color alone; pair color with labels, shape,
  position, or line style.
- Keep body text large enough for a 1080p classroom or laptop display.
- Limit simultaneous text and progressively disclose lists.
- Keep critical labels on screen long enough to match the narration budget.
- Avoid rapid flashing, excessive camera motion, and unnecessary 3D effects.
- Use persistent headings and predictable left-to-right causality.

## 12. Verification Strategy

Implementation follows test-driven development.

1. Add timeline tests that initially fail because animation structures do not
   exist.
2. Verify exact section names, contiguous boundaries, individual durations, and
   the 840-second total.
3. Test preview scaling and helper layout bounds with deterministic values.
4. Test that the displayed lab output matches the verified `lab.py` output.
5. Import the animation module and instantiate the public scene class.
6. Render the full master scene in accelerated preview mode at low quality.
7. Render representative still frames or short ranges for the hook, code
   walkthrough, mini-lab, and recap, then inspect them visually.
8. Run the repository's existing course-structure tests to ensure animation
   additions did not alter the approved lesson contract.
9. Render the final 1080p video when the preview and representative frames pass.

## 13. Acceptance Criteria

The work is complete when:

- a single public Manim scene renders all eight sections in script order;
- normal timing totals 14 minutes and aligns with every script timestamp;
- preview mode renders the complete sequence on a practical development
  timescale;
- displayed code and terminal output match the approved lesson artifacts;
- the fixed representation versus adjustable parameter distinction remains
  visually consistent;
- the NFKC warning is visible and does not imply lossless normalization;
- the 7-to-5 example is explicitly labeled as an illustration;
- advanced deferred vocabulary is not used as an explanation;
- automated tests pass;
- representative rendered frames have no clipping, overlap, or illegible text;
  and
- the final MP4 is produced at 1920x1080 and 30 fps.

## 14. Rollback And Residual Risk

All animation files are additive. Rollback consists of removing the new Manim
source, configuration, tests, and generated media; existing course content does
not need to change.

The largest residual risk is pacing without recorded narration. Script
timestamps provide section-level timing, but sentence-level emphasis may need
minor adjustment after a human reads the script against the first full preview.
