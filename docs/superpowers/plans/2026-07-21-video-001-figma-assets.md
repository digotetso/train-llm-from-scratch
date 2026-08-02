# Video 001 Figma Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and visually verify a complete 48-shot, 1920x1080 Figma storyboard and reusable After Effects-ready asset system for Video 001 in the supplied Figma file.

**Architecture:** Add one isolated page to the existing Figma design file. Build a shared token/component foundation first, then compose and verify the storyboard in section-sized batches so failures remain reversible and easy to inspect. Finish with a thumbnail board, AE handoff section, metadata audit, and representative screenshot review.

**Tech Stack:** Figma Design, Figma Plugin API through `use_figma`, Figma read-only metadata/design-context/screenshot tools, Sora, Inter, JetBrains Mono, and repository Markdown documentation.

## Global Constraints

- Target only Figma file `fFTux3sx2AzVQtoya67f95`.
- Preserve the existing `01 Brand Kit` page without mutation.
- Create exactly one additive page named `02 Video 001 - AE Assets`.
- Create exactly 48 composed 1920x1080 shot frames in the approved order.
- Use background `#0B1020`, panel `#11182D`, primary text `#F5F7FB`, secondary text `#A8B3CF`, fixed data `#35C7FF`, model `#8B5CF6`, warning/loss `#F59E0B`, and progress `#22C55E`.
- Use Sora for display/headings/captions, Inter for body copy, and JetBrains Mono for code.
- Keep text live and intended motion units as separately named editable layers.
- Use `BG_`, `TXT_`, `CODE_`, `DATA_`, `MODEL_`, `LOSS_`, `PROG_`, `FX_`, `MATTE_`, and `GUIDE_` prefixes.
- Keep all critical content inside a 120 px title-safe margin.
- Use a 12-column grid, 120 px outer margins, 24 px gutters, and 24 px card corner radii.
- Use one primary focal element per shot.
- Do not add stock imagery, external icons, raster textures, or advanced deferred vocabulary as explanation.
- Treat Figma as sRGB source artwork; do not claim AE import, animation, color pipeline, or render verification.
- Stop and report rather than silently substituting fonts or overwriting an existing page with the target name.

## File And Document Map

- Read: `course/videos/001-computer-learning-from-text/script.md` — narration and displayed copy source of truth.
- Read: `course/videos/001-computer-learning-from-text/lab.py` — mini-lab command/output source of truth.
- Read: `docs/superpowers/specs/2026-07-21-video-001-figma-assets-design.md` — approved visual and shot specification.
- Read/modify remotely: Figma file `fFTux3sx2AzVQtoya67f95`, existing page `01 Brand Kit` — theme evidence only; never mutate.
- Create remotely: Figma page `02 Video 001 - AE Assets` — all new frames and components.
- Create: `docs/superpowers/plans/2026-07-21-video-001-figma-assets.md` — this implementation plan.

---

### Task 1: Inspect And Lock The Figma Source Contract

**Files:**
- Read: `docs/superpowers/specs/2026-07-21-video-001-figma-assets-design.md`
- Read remotely: Figma nodes `0:1`, `1:5`, `1:6`, and `1:8`

**Interfaces:**
- Consumes: source file key and node IDs from the approved design.
- Produces: verified colors, font roles, 1920x1080 canvas contract, source-page screenshot, and confirmation that the additive page does not already exist.

- [ ] **Step 1: Load the mandatory Figma guidance**

Read the complete `figma-use` skill before any write and the complete
`figma-design-to-code` skill before calling `get_design_context`.

- [ ] **Step 2: Inspect the source nodes**

Call `get_design_context` for nodes `1:5`, `1:6`, and `1:8`, preserving screenshots. Confirm the returned values include the exact palette and font families in Global Constraints.

- [ ] **Step 3: Confirm page-level safety**

Call page metadata with no guessed node IDs, list top-level pages, and verify there is no existing page named `02 Video 001 - AE Assets`.

Expected: `01 Brand Kit` exists and the target page name does not exist.

- [ ] **Step 4: Capture the before state**

Capture a screenshot of node `0:1` at sufficient resolution to compare after implementation.

- [ ] **Step 5: Record the checkpoint**

Update this plan task to complete only after colors, typography, canvas size, and page-safety checks all agree with the spec.

### Task 2: Create The Additive Page, Sections, Tokens, And Direction Board

**Files:**
- Create remotely: Figma page `02 Video 001 - AE Assets`
- Create remotely: sections `00_README_AND_DIRECTION` and `01_THEME_TOKENS`

**Interfaces:**
- Consumes: verified theme contract from Task 1.
- Produces: new page ID, named page sections, color variables, typography samples, grid/safe-area reference, and direction board used by later tasks.

- [ ] **Step 1: Preflight fonts in one read-only plugin run**

Use `figma.listAvailableFontsAsync()` and require these families:

```js
const required = ["Sora", "Inter", "JetBrains Mono"];
const available = new Set((await figma.listAvailableFontsAsync()).map(f => f.fontName.family));
const missing = required.filter(name => !available.has(name));
if (missing.length) throw new Error(`Missing required fonts: ${missing.join(", ")}`);
```

Expected: no missing families.

- [ ] **Step 2: Create the page idempotently**

Before mutation, search `figma.root.children` for the exact target name. If found, throw an error. Otherwise create and rename one page:

```js
const pageName = "02 Video 001 - AE Assets";
if (figma.root.children.some(page => page.name === pageName)) {
  throw new Error(`Refusing to overwrite existing page: ${pageName}`);
}
const page = figma.createPage();
page.name = pageName;
await figma.setCurrentPageAsync(page);
```

- [ ] **Step 3: Create the direction and token sections**

Create `00_README_AND_DIRECTION` at `(0, 0)` and `01_THEME_TOKENS` at `(0, 1500)`. Add the one-message brief, three mood adjectives, motion contract, 120 px safe-area example, exact eight color swatches, and type-role samples.

- [ ] **Step 4: Create local color variables**

Create collection `Video 001 Theme` and variables named exactly:

```text
BG/Base
BG/Panel
Text/Primary
Text/Secondary
Data/Fixed
Model/Adjustable
State/Warning
State/Progress
```

Bind fills and strokes in later tasks to these variables where supported.

- [ ] **Step 5: Verify the foundation**

Call metadata on the new page and screenshot both sections.

Expected: two named sections, exact swatches, readable type hierarchy, no clipping, and no mutation on `01 Brand Kit`.

### Task 3: Build The Reusable Component Library

**Files:**
- Create remotely: section `02_COMPONENT_LIBRARY`

**Interfaces:**
- Consumes: page ID and theme variables from Task 2.
- Produces: named editable components used by all 48 shots.

- [ ] **Step 1: Create the component section**

Create `02_COMPONENT_LIBRARY` below the token section with a labeled grid for sixteen component families.

- [ ] **Step 2: Build the first eight component families**

Create live, editable components for:

```text
CMP_SectionTitle
CMP_CharacterTile
CMP_NumberTile
CMP_ContextCard
CMP_HumanInterpretationCloud
CMP_PythonInputCard
CMP_DataStreamRail
CMP_CodePanel
```

Each component must contain functional layer names, state labels, and no default Figma names.

- [ ] **Step 3: Build the remaining eight component families**

Create live, editable components for:

```text
CMP_TerminalPanel
CMP_PipelineNode
CMP_ModelBlock
CMP_PredictionRow
CMP_ErrorCounter
CMP_WarningBanner
CMP_ChecklistCard
CMP_EndCard
```

- [ ] **Step 4: Add state examples**

Show neutral, fixed-data, selected, warning, adjustable-model, error, and progress states. Pair every color state with text or a distinct shape.

- [ ] **Step 5: Verify the library**

Capture a high-resolution screenshot and inspect component metadata.

Expected: sixteen named component families, live text, independent sequential cells, no unlabeled state, and no default layer names.

### Task 4: Compose Shots 01-09 — Hook And Direct Explanation

**Files:**
- Create remotely: section `03_STORYBOARD_HOOK_AND_DIRECT`

**Interfaces:**
- Consumes: Task 3 components and Task 2 tokens.
- Produces: nine named 1920x1080 shot frames and nine motion-note cards.

- [ ] **Step 1: Create the section and frame grid**

Create a three-column grid with 160 px spacing and frames named:

```text
S001_SH01_Hook_CatWord
S001_SH02_Hook_HumanAssociations
S001_SH03_Hook_ProgramData
S001_SH04_Hook_LessonPromise
S001_SH05_Direct_DefinedStandards
S001_SH06_Direct_Ato65
S001_SH07_Direct_AContexts
S001_SH08_Direct_RepresentationNotMeaning
S001_SH09_Direct_FixedVsAdjustable
```

- [ ] **Step 2: Compose shots 01-04**

Use `cat` as the hero, then an amber human-association cloud, separated program-data cells, and finally two labeled lanes with the lesson objective. Keep semantic associations absent from the program-data lane.

- [ ] **Step 3: Compose shots 05-09**

Show defined standards, `A -> 65`, four stable contexts around `A`, rejection of `65 = meaning`, and the fixed-cyan versus adjustable-purple legend.

- [ ] **Step 4: Add motion notes**

Add one note per shot identifying purpose, hero, support, static elements, transition, and technical caution.

- [ ] **Step 5: Verify the batch**

Inspect metadata and screenshots for shots 01 and 09.

Expected: nine unique 1920x1080 frames, one hero per frame, and no meaning encoded on the program side.

### Task 5: Compose Shots 10-17 — Technical Meaning

**Files:**
- Create remotely: section `04_STORYBOARD_TECHNICAL`

**Interfaces:**
- Consumes: components and stable fixed/model color semantics.
- Produces: eight named 1920x1080 technical-explanation frames and motion notes.

- [ ] **Step 1: Create the eight-frame grid**

```text
S001_SH10_Technical_CharacterStrip
S001_SH11_Technical_UnicodeDefinition
S001_SH12_Technical_OrdFunction
S001_SH13_Technical_CatCodePoints
S001_SH14_Technical_ByteRange
S001_SH15_Technical_UTF8Cat
S001_SH16_Technical_ModelParameters
S001_SH17_Technical_TwoReasons
```

- [ ] **Step 2: Compose character, Unicode, and `ord` shots**

Use `C`, `a`, `t`, space, and `?`; show Unicode as a shared standard; and show exactly:

```python
ord("C")  # 67
ord("a")  # 97
ord("t")  # 116
```

- [ ] **Step 3: Compose code-point, byte, and UTF-8 shots**

Align `Cat` with `67 97 116`, build one byte from eight bit cells, label `0-255`, and show the matching UTF-8 row with `This match is not universal` in amber.

- [ ] **Step 4: Compose model and two-reasons shots**

Use a purple model block with separate adjustable cells. Keep storage/exchange and mathematical-input reasons separate from parameter updates.

- [ ] **Step 5: Verify the batch**

Inspect shots 13 and 15 at high resolution.

Expected: exact values, clear one-to-one alignment, visible caveat, and no claim that code points contain meaning.

### Task 6: Compose Shots 18-25 — Tiny Example

**Files:**
- Create remotely: section `05_STORYBOARD_TINY_EXAMPLE`

**Interfaces:**
- Consumes: sentence, number, prediction, error, and evaluation components.
- Produces: eight named 1920x1080 example frames and motion notes.

- [ ] **Step 1: Create the eight-frame grid**

```text
S001_SH18_Example_ThreeSentences
S001_SH19_Example_RepeatedPattern
S001_SH20_Example_CatHandCheck
S001_SH21_Example_NumericOperations
S001_SH22_Example_DistanceNotMeaning
S001_SH23_Example_BeforeTraining
S001_SH24_Example_AfterTraining
S001_SH25_Example_PatternVsMemorization
```

- [ ] **Step 2: Compose pattern and hand-check shots**

Show `cat sat`, `cat ran`, and `cat slept`; align the repeated prefix and following space; then align `C a t` with `67 97 116`.

- [ ] **Step 3: Compose numeric-operation shots**

Show equality, count-three, and sequence-comparison cards. Use a number line to show the arithmetic distance between `67` and `97`, with an explicit `not semantic distance` label.

- [ ] **Step 4: Compose before/after and evaluation shots**

Use ten markers with seven amber errors before and five amber errors after. Label the comparison `illustrative example`, show progress in green, and separate repeated pattern, memorization risk, and held-out evaluation.

- [ ] **Step 5: Verify the batch**

Inspect shots 23-25.

Expected: exactly 10 markers in each comparison, counts 7 and 5, an illustration label, and no claim of measured repository performance.

### Task 7: Compose Shots 26-32 — Repository Walkthrough

**Files:**
- Create remotely: section `06_STORYBOARD_REPOSITORY`
- Read: `matgpt/data/normalize.py`
- Read: `matgpt/data/prepare.py`

**Interfaces:**
- Consumes: exact simplified excerpts in the narration script and code-panel components.
- Produces: seven named 1920x1080 repository frames and motion notes.

- [ ] **Step 1: Create the seven-frame grid**

```text
S001_SH26_Repo_PreparationOverview
S001_SH27_Repo_NormalizeFunction
S001_SH28_Repo_NFKCStep
S001_SH29_Repo_NewlinesAndWhitespace
S001_SH30_Repo_NormalizationWarning
S001_SH31_Repo_PrepareRecord
S001_SH32_Repo_PreparationNotLearning
```

- [ ] **Step 2: Compose the normalization overview and excerpt**

Show `source text -> normalize -> stored record` and the script-approved simplified `normalize_text` code with filename, line numbers, and active-line highlight.

- [ ] **Step 3: Compose the transformation details**

Show NFKC, newline convergence, line-level trailing-space cleanup, and whole-string `strip()` as distinct operations.

- [ ] **Step 4: Compose the policy warning and prepare record**

Use `① -> 1` with `deliberate, not lossless`; then show `normalized = normalize_text(text)`, `"text": normalized`, and `"num_chars": len(normalized)`.

- [ ] **Step 5: Compose the preprocessing boundary**

End the record before a separate purple learning boundary and state `Preparation is not parameter learning`.

- [ ] **Step 6: Verify the batch**

Inspect shots 27, 30, and 32.

Expected: code matches the script excerpt, warning is prominent, and the pipeline does not imply learning occurs in normalization.

### Task 8: Compose Shots 33-39 — Live Mini-Lab

**Files:**
- Create remotely: section `07_STORYBOARD_MINI_LAB`
- Read: `course/videos/001-computer-learning-from-text/lab.py`

**Interfaces:**
- Consumes: verified lab source, command, and output.
- Produces: seven named 1920x1080 mini-lab frames and motion notes.

- [ ] **Step 1: Create the seven-frame grid**

```text
S001_SH33_Lab_FileOverview
S001_SH34_Lab_PredictCat
S001_SH35_Lab_RunCommand
S001_SH36_Lab_CompareCatLists
S001_SH37_Lab_EqualityCaveat
S001_SH38_Lab_EditToA
S001_SH39_Lab_RunAAndRestore
```

- [ ] **Step 2: Compose the file and prediction frames**

Show the five script-approved statements and two empty prediction rows for `Cat`.

- [ ] **Step 3: Compose the run and output frames**

Use this exact command:

```bash
python course/videos/001-computer-learning-from-text/lab.py
```

Show these essential values exactly:

```text
Human text: Cat
Character numbers: [67, 97, 116]
UTF-8 bytes: [67, 97, 116]
Can the mathematical model use this raw Python string as numeric input? No
Learning begins after text is represented as numbers.
```

- [ ] **Step 4: Compose the caveat and `A` rerun**

Explain the ASCII-range match, change only `text = "A"`, show `[65]` for both rows, then restore `text = "Cat"`.

- [ ] **Step 5: Verify the batch**

Inspect shots 35 and 39 and compare text to `lab.py`.

Expected: no altered command, exact numeric lists, narrow claim about model numeric input, and visible restoration to `Cat`.

### Task 9: Compose Shots 40-48 — Mistake, Recap, And Exercise

**Files:**
- Create remotely: section `08_STORYBOARD_MISTAKE_AND_RECAP`

**Interfaces:**
- Consumes: context, warning, pipeline, checklist, exercise, and end-card components.
- Produces: nine named 1920x1080 final-section frames and motion notes.

- [ ] **Step 1: Create the nine-frame grid**

```text
S001_SH40_Mistake_65IsMeaning
S001_SH41_Mistake_AContextWheel
S001_SH42_Mistake_MappingSwapTest
S001_SH43_Mistake_EncodingVsLearning
S001_SH44_Recap_Objective
S001_SH45_Recap_FourSteps
S001_SH46_Recap_SelfCheck
S001_SH47_Recap_Exercise
S001_SH48_Recap_NextLesson
```

- [ ] **Step 2: Compose the misconception sequence**

Strike through `65 is the meaning of A`; show four context cards around stable `A -> 65`; swap the assigned mapping without changing meaning; then contrast fixed `ord` with parameter updates after error.

- [ ] **Step 3: Compose the four-step recap**

Use four numbered cards for represented input, standards, representation-not-meaning, and model-parameter updates.

- [ ] **Step 4: Compose the self-check, exercise, and end card**

Show five check-yourself questions, the `A` lab exercise, and the sentence stem `The number 65 is assigned to ___, but it does not encode ___.` End on the complete pipeline and next-lesson title.

- [ ] **Step 5: Verify the batch**

Inspect shots 41 and 45-48.

Expected: no semantic meaning assigned to `65`, complete exercise wording, and a restrained end-card hold.

### Task 10: Build The Thumbnail Board And AE Handoff Section

**Files:**
- Create remotely: sections `09_THUMBNAIL_BOARD` and `10_AE_HANDOFF`

**Interfaces:**
- Consumes: all 48 verified shot frames and motion notes.
- Produces: complete narrative contact sheet and handoff reference.

- [ ] **Step 1: Build the thumbnail board**

Create scaled references to all 48 shots in eight labeled rows, preserving narrative order and section boundaries. Add shot numbers and approximate time ranges outside the artwork.

- [ ] **Step 2: Build the AE layer legend**

Document all ten layer prefixes, the three-font requirement, 1920x1080 canvas, 30 fps reference, 120 px safe area, and maximum three nesting levels.

- [ ] **Step 3: Build the motion-language board**

Document corporate calm-sharp personality, entrance curve `0.22,1,0.36,1`, exit curve `0.4,0,1,1`, 0.4-second base unit, 60 ms stagger reference, match cut/crossfade transitions, 24 px travel, `0.96 -> 1.0` scale, and maximum 2% overshoot.

- [ ] **Step 4: Add transfer cautions**

State that font installation, Figma-to-AE transfer behavior, AE color space, alpha interpretation, audio, captions, and final codecs remain unverified production decisions.

- [ ] **Step 5: Verify both sections**

Capture screenshots.

Expected: exactly 48 thumbnails in order, all handoff values match the spec, and no claim of AE-host validation.

### Task 11: Run The Final Metadata And Visual Quality Gate

**Files:**
- Verify remotely: the entire `02 Video 001 - AE Assets` page
- Verify remotely: source page `01 Brand Kit`

**Interfaces:**
- Consumes: all assets from Tasks 2-10.
- Produces: evidence that the page meets the acceptance criteria or a bounded fix list.

- [ ] **Step 1: Audit frame identity and dimensions**

Use metadata to verify all names `S001_SH01` through `S001_SH48` exist exactly once and every shot is 1920x1080.

- [ ] **Step 2: Audit layer names**

Search metadata for default names matching `Rectangle [0-9]+`, `Group [0-9]+`, `Frame [0-9]+`, `Text [0-9]+`, and `Vector [0-9]+` under the new page. Rename every match functionally.

- [ ] **Step 3: Audit exact content**

Verify `67`, `97`, `116`, `65`, `0-255`, `7`, `5`, the three example sentences, `① -> 1`, the repository command, and the exercise sentence against the source files.

- [ ] **Step 4: Perform representative visual review**

Capture high-resolution screenshots for the component library and shots 01, 09, 15, 23, 30, 35, 41, and 45. Inspect for clipping, overlaps, poor contrast, competing focal points, weak alignment, excessive copy, and inconsistent semantics.

- [ ] **Step 5: Inspect the full pacing board**

Review the 48-shot thumbnail board for rhythm, repeated-layout fatigue, inconsistent accents, and missing section transitions.

- [ ] **Step 6: Apply bounded corrections**

Fix only evidenced defects on the new page. Re-capture the affected screenshot after each coherent correction batch.

- [ ] **Step 7: Confirm source preservation**

Re-capture node `0:1` and compare page structure with Task 1. Confirm `01 Brand Kit` remains unchanged.

- [ ] **Step 8: Report completion accurately**

Report the Figma URL and new page, frame count, representative visual checks, source preservation, and residual AE/font/color/timing risks. Use `production-ready` only if all applicable source and visual gates pass, and explicitly state that AE-host validation remains outstanding.

---

## Plan Self-Review

- Spec coverage: Tasks 1-11 cover the source contract, additive safety, tokens, sixteen components, all 48 shots, motion notes, thumbnail board, AE handoff, accessibility, metadata checks, visual checks, rollback boundaries, and residual-risk reporting.
- Placeholder scan: the plan contains no deferred implementation placeholders or unspecified error-handling steps.
- Interface consistency: all tasks consume the exact page, token, component, naming, dimensions, and color contracts established in Tasks 1-3.
- Scope: the work is one Figma asset subsystem and does not include animation, rendering, audio, captions, or AE project creation.
