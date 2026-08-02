# Video 001 Figma Assets Design

Date: 2026-07-21

Status: Approved direction, awaiting written-spec review

## 1. Purpose

Create a complete, editable Figma storyboard and asset system for
`course/videos/001-computer-learning-from-text/script.md`. The deliverable will
contain 48 composed 1920x1080 shot frames, a reusable component library, and an
After Effects handoff section. It will be added to the existing Figma file
`Lesson 01 - What AI Models Actually Do` without changing the existing brand
kit page.

The visuals must help a beginner retain one distinction:

1. text receives fixed numeric representations; and
2. learning later updates separate model parameters in response to measured
   error.

## 2. Source Facts

- The narration assumes no machine-learning knowledge.
- The script has eight timestamped sections from `00:00` through `13:00`; the
  existing approved animation design allocates the recap through `14:00`.
- The existing approved animation contract targets 1920x1080, 16:9, and 30 fps.
- The source Figma brand kit uses 1920x1080 frames.
- The source Figma palette is:
  - background `#0B1020`;
  - card/panel `#11182D`;
  - main text `#F5F7FB`;
  - secondary text `#A8B3CF`;
  - cyan highlight `#35C7FF`;
  - purple model blocks `#8B5CF6`;
  - amber warning/loss `#F59E0B`; and
  - green correct/progress `#22C55E`.
- The source Figma typography uses Sora for display, headings, and captions;
  Inter for body copy; and JetBrains Mono for code.
- The script's repository walkthrough refers to
  `matgpt/data/normalize.py` and `matgpt/data/prepare.py`.
- The working copy of `script.md` contains user changes and must not be edited
  as part of this work.
- The file already contains the brand-kit page. The video work must be additive
  and isolated on a new page.

## 3. Requirements

### 3.1 Deliverables

- One new Figma page named `02 Video 001 - AE Assets`.
- Forty-eight shot frames named and ordered according to the shot map in this
  document.
- One theme-token section that documents the exact brand colors and type roles.
- One reusable component section for recurring video grammar.
- One thumbnail storyboard showing all shots in narrative order.
- One After Effects handoff section containing the motion-language contract,
  layer-prefix legend, font requirements, section timing, and shot notes.
- Live text, editable vectors, separated effects, and stable layer names.

### 3.2 Acceptance behavior

- Every narration beat has a corresponding composed shot, not merely an empty
  placeholder or title card.
- Every shot has exactly one primary focal element.
- Fixed representations and learned parameters remain visually distinct in
  every applicable shot.
- The displayed code, numbers, examples, and warnings match the lesson script.
- No visual suggests that code points encode meaning, that encoding is
  learning, or that the illustrative 7-to-5 error count is measured repository
  evidence.

## 4. Non-Goals

- Do not rewrite the narration script.
- Do not animate the frames in Figma or produce the final rendered video.
- Do not create an After Effects project or claim AE-host verification.
- Do not teach tokens, tensors, logits, gradients, attention, or token
  embeddings.
- Do not add stock photography, generated character art, external icons, or
  textures that introduce licensing dependencies.
- Do not modify, delete, or reorganize the existing `01 Brand Kit` page.
- Do not create assets for later course videos.

## 5. Delivery Contract

| Property | Contract |
|---|---|
| Canvas | 1920x1080, 16:9 |
| Timeline reference | 14:00 total, using the eight script sections |
| AE frame-rate reference | 30 fps |
| Figma color encoding | sRGB hex values from the source brand kit |
| AE output color space | Set during AE production; not established by this asset task |
| Audio, loudness, captions | Outside this asset task |
| Alpha | Editable vector assets; alpha export settings are deferred to AE production |
| Final codec/container | Outside this asset task |
| Typography | Sora, Inter, JetBrains Mono; live text retained |
| File destination | Existing file `fFTux3sx2AzVQtoya67f95`, new page only |

The Figma result can be source-validated and visually validated. It is not
After Effects-host-validated until it has been imported into AE and inspected
there.

## 6. Creative Direction

### 6.1 Intended response

The viewer should feel that text representation and model learning are simple,
separate steps that can be inspected rather than mysterious acts of machine
understanding.

### 6.2 Tone

Confident, precise, approachable.

The piece sits in the calm-sharp quadrant: premium educational technology with
controlled motion and generous reading time. The visual system uses clean
geometry, large type, dark academic surfaces, sparse glow, and diagrammatic
continuity. It avoids playful bounce, visual noise, fake 3D, and decorative
motion.

### 6.3 Color semantics

| Token | Hex | Meaning |
|---|---:|---|
| `BG/Base` | `#0B1020` | Canvas and negative space |
| `BG/Panel` | `#11182D` | Cards, code panels, model surfaces |
| `Text/Primary` | `#F5F7FB` | Main statements and labels |
| `Text/Secondary` | `#A8B3CF` | Supporting explanation |
| `Data/Fixed` | `#35C7FF` | Characters, code points, bytes, fixed mappings |
| `Model/Adjustable` | `#8B5CF6` | Model blocks and parameters |
| `State/Warning` | `#F59E0B` | Error, loss, caveats, normalization warning |
| `State/Progress` | `#22C55E` | Improvement, correct outcomes, completion |

Color is always paired with a label, icon shape, line style, or position. Color
alone must not carry the distinction.

### 6.4 Typography

| Role | Family | Default treatment |
|---|---|---|
| Display | Sora | 104 px, bold, tight line height |
| Section heading | Sora | 64 px, semibold |
| Shot heading | Sora | 48 px, semibold |
| Body large | Inter | 36 px, regular |
| Body | Inter | 30 px, regular |
| Caption | Sora | 22 px, medium, tracked |
| Code | JetBrains Mono | 28 px, regular |

Text sizes may reduce only where a code excerpt requires it, and never below
24 px in a 1080p shot frame. Critical text must stay inside a 120 px title-safe
margin.

### 6.5 Layout grammar

- Use a 12-column grid with 120 px outer margins and 24 px gutters.
- Default composition is a left-to-right causal flow.
- Cards use a 24 px corner radius and restrained shadow or glow.
- One hero, one supporting system, and optional low-contrast texture per shot.
- Use empty space to separate concepts; do not fill the frame with explanatory
  copy.
- Maintain stable screen positions for recurring ideas:
  `TEXT -> NUMBERS -> PREDICTION -> ERROR -> PARAMETER UPDATE`.

## 7. Reusable Component System

The component library will include the following editable assets:

1. Section title and timestamp lockup.
2. Character tile in neutral, fixed-data, selected, and warning states.
3. Numeric value tile for code points and bytes.
4. Context card for alternate meanings of one character.
5. Human interpretation cloud with labeled concept chips.
6. Python input card and data-stream rail.
7. Code panel with filename bar, line numbers, line highlight, and callout pin.
8. Terminal panel with command, output, prompt, and cursor layers.
9. Pipeline node and connector in fixed, model, loss, and success roles.
10. Model block with individually separated parameter cells.
11. Prediction row with correct and incorrect states.
12. Error counter and before/after comparison.
13. Warning banner and misconception strike-through.
14. Checklist card and exercise card.
15. Progress indicator for the eight lesson sections.
16. End-card lockup for the next lesson.

Component instances may be used while composing. Keep the library masters, but
detach final shot instances when the selected Figma-to-AE transfer path would
otherwise flatten or lock the intended motion units.

## 8. Figma Page Architecture

The new page will contain these sections in canvas order:

```text
00_README_AND_DIRECTION
01_THEME_TOKENS
02_COMPONENT_LIBRARY
03_STORYBOARD_HOOK_AND_DIRECT
04_STORYBOARD_TECHNICAL
05_STORYBOARD_TINY_EXAMPLE
06_STORYBOARD_REPOSITORY
07_STORYBOARD_MINI_LAB
08_STORYBOARD_MISTAKE_AND_RECAP
09_THUMBNAIL_BOARD
10_AE_HANDOFF
```

Shot frames will use the name pattern:

```text
S001_SH##_Section_Descriptor
```

Within each frame, layers will use functional prefixes:

```text
BG_       background and panels
TXT_      narrative text and labels
CODE_     code-panel elements
DATA_     characters, code points, bytes, and fixed mappings
MODEL_    parameter and model elements
LOSS_     error or warning elements
PROG_     progress and correct-state elements
FX_       glow, shadow, blur, and ambient texture
MATTE_    masks intended for reveals
GUIDE_    non-rendering notes or safe-area guides
```

No generated layer may retain names such as `Rectangle 1`, `Group 5`, or
`Frame 27`.

## 9. Forty-Eight-Shot Storyboard

### 9.1 Hook, 00:00-00:45

| Shot | Approx. time | Frame name | Hero and visual intent |
|---:|---:|---|---|
| 01 | 00:00-00:08 | `S001_SH01_Hook_CatWord` | The word `cat` alone, large and quiet, establishes the object of study. |
| 02 | 00:08-00:18 | `S001_SH02_Hook_HumanAssociations` | Amber interpretation cloud expands around `cat`: animal, memory, sound, image. |
| 03 | 00:18-00:30 | `S001_SH03_Hook_ProgramData` | The same word becomes separated character cells and abstract data on the program side. |
| 04 | 00:30-00:45 | `S001_SH04_Hook_LessonPromise` | Human interpretation and program input settle into two labeled lanes with the lesson objective. |

### 9.2 Direct explanation, 00:45-02:00

| Shot | Approx. time | Frame name | Hero and visual intent |
|---:|---:|---|---|
| 05 | 00:45-00:58 | `S001_SH05_Direct_DefinedStandards` | A standard/ruler motif establishes that character mappings are defined, not learned. |
| 06 | 00:58-01:12 | `S001_SH06_Direct_Ato65` | `A` aligns to `65` with a fixed cyan connector and `ord("A")` evidence. |
| 07 | 01:12-01:28 | `S001_SH07_Direct_AContexts` | One central `A` connects to grade, musical note, blood type, and word contexts while `65` remains fixed. |
| 08 | 01:28-01:43 | `S001_SH08_Direct_RepresentationNotMeaning` | A split equation rejects `65 = meaning` and confirms `65 = assigned code point`. |
| 09 | 01:43-02:00 | `S001_SH09_Direct_FixedVsAdjustable` | Fixed cyan mapping and adjustable purple parameter bank become the recurring two-category legend. |

### 9.3 Technical meaning, 02:00-04:00

| Shot | Approx. time | Frame name | Hero and visual intent |
|---:|---:|---|---|
| 10 | 02:00-02:14 | `S001_SH10_Technical_CharacterStrip` | `C`, `a`, `t`, space, and `?` appear as separate character units. |
| 11 | 02:14-02:28 | `S001_SH11_Technical_UnicodeDefinition` | A shared-standard card assigns stable integer identifiers to characters. |
| 12 | 02:28-02:43 | `S001_SH12_Technical_OrdFunction` | A focused Python code panel reveals `ord` results one line at a time. |
| 13 | 02:43-02:58 | `S001_SH13_Technical_CatCodePoints` | `Cat` maps one-to-one to `67 97 116` with persistent alignment. |
| 14 | 02:58-03:12 | `S001_SH14_Technical_ByteRange` | Eight bit cells group into one byte, with the `0-255` range labeled. |
| 15 | 03:12-03:27 | `S001_SH15_Technical_UTF8Cat` | Code-point and UTF-8 byte rows match for `Cat`; amber caveat says this is not universal. |
| 16 | 03:27-03:43 | `S001_SH16_Technical_ModelParameters` | Numeric input enters a purple model block containing visibly adjustable parameter cells. |
| 17 | 03:43-04:00 | `S001_SH17_Technical_TwoReasons` | Storage/exchange and mathematical-input reasons converge without merging encoding and learning. |

### 9.4 Tiny example, 04:00-06:00

| Shot | Approx. time | Frame name | Hero and visual intent |
|---:|---:|---|---|
| 18 | 04:00-04:14 | `S001_SH18_Example_ThreeSentences` | `cat sat`, `cat ran`, and `cat slept` appear as three clean example rows. |
| 19 | 04:14-04:28 | `S001_SH19_Example_RepeatedPattern` | Repeated `cat` and following spaces align vertically; action words remain unclassified. |
| 20 | 04:28-04:43 | `S001_SH20_Example_CatHandCheck` | Human-readable `C a t` and agreed `67 97 116` rows form the hand-check. |
| 21 | 04:43-04:58 | `S001_SH21_Example_NumericOperations` | Three cards show equality check, count of values, and sequence comparison. |
| 22 | 04:58-05:12 | `S001_SH22_Example_DistanceNotMeaning` | A number line shows distance between `67` and `97`, explicitly disconnected from semantic relationship. |
| 23 | 05:12-05:28 | `S001_SH23_Example_BeforeTraining` | Ten prediction markers show seven illustrative errors, clearly labeled `before`. |
| 24 | 05:28-05:44 | `S001_SH24_Example_AfterTraining` | Comparable markers show five illustrative errors with a green improvement delta. |
| 25 | 05:44-06:00 | `S001_SH25_Example_PatternVsMemorization` | Repeated pattern, memorization risk, and separate evaluation examples form three distinct cards; token embeddings are marked deferred. |

### 9.5 Repository walkthrough, 06:00-09:00

| Shot | Approx. time | Frame name | Hero and visual intent |
|---:|---:|---|---|
| 26 | 06:00-06:22 | `S001_SH26_Repo_PreparationOverview` | `source text -> normalize -> stored record` establishes the preprocessing boundary. |
| 27 | 06:22-06:48 | `S001_SH27_Repo_NormalizeFunction` | A large code panel shows the simplified `normalize_text` excerpt with filename and line numbers. |
| 28 | 06:48-07:12 | `S001_SH28_Repo_NFKCStep` | The NFKC line is isolated; input and normalized output retain explicit labels. |
| 29 | 07:12-07:38 | `S001_SH29_Repo_NewlinesAndWhitespace` | CRLF/CR and trailing whitespace visibly converge to the normalized form. |
| 30 | 07:38-08:05 | `S001_SH30_Repo_NormalizationWarning` | `① -> 1` demonstrates the deliberate, non-lossless policy with an amber warning. |
| 31 | 08:05-08:32 | `S001_SH31_Repo_PrepareRecord` | The simplified `prepare.py` excerpt highlights `normalize_text`, `text`, and `num_chars`. |
| 32 | 08:32-09:00 | `S001_SH32_Repo_PreparationNotLearning` | The stored record stops before a separate learning boundary; visible-symbol and Python-length caveat appears. |

### 9.6 Live mini-lab, 09:00-12:00

| Shot | Approx. time | Frame name | Hero and visual intent |
|---:|---:|---|---|
| 33 | 09:00-09:24 | `S001_SH33_Lab_FileOverview` | `lab.py` appears in an editor panel with the five relevant statements grouped. |
| 34 | 09:24-09:48 | `S001_SH34_Lab_PredictCat` | A prediction board pauses on two empty numeric lists for the viewer to fill mentally. |
| 35 | 09:48-10:18 | `S001_SH35_Lab_RunCommand` | Terminal runs the exact repository-relative command and reveals output line by line. |
| 36 | 10:18-10:44 | `S001_SH36_Lab_CompareCatLists` | Code-point and byte rows align for `Cat`, with identical values highlighted. |
| 37 | 10:44-11:05 | `S001_SH37_Lab_EqualityCaveat` | The ASCII-range reason is shown beside an explicit `not always equal` warning. |
| 38 | 11:05-11:32 | `S001_SH38_Lab_EditToA` | Only the source-string line changes from `Cat` to `A`; everything else remains stable. |
| 39 | 11:32-12:00 | `S001_SH39_Lab_RunAAndRestore` | Terminal reveals `[65]` for both lists, explains fixed assignment, and restores `Cat`. |

### 9.7 Common mistake, 12:00-13:00

| Shot | Approx. time | Frame name | Hero and visual intent |
|---:|---:|---|---|
| 40 | 12:00-12:14 | `S001_SH40_Mistake_65IsMeaning` | The incorrect statement `65 is the meaning of A` is presented and struck through. |
| 41 | 12:14-12:30 | `S001_SH41_Mistake_AContextWheel` | Grade, note, blood type, and word contexts orbit a stable `A -> 65` center. |
| 42 | 12:30-12:44 | `S001_SH42_Mistake_MappingSwapTest` | An alternate mapping changes the assigned number while the contextual meanings remain. |
| 43 | 12:44-13:00 | `S001_SH43_Mistake_EncodingVsLearning` | A fixed `ord` mapping contrasts with parameters changing after measured error. |

### 9.8 Recap and exercise, 13:00-14:00

| Shot | Approx. time | Frame name | Hero and visual intent |
|---:|---:|---|---|
| 44 | 13:00-13:12 | `S001_SH44_Recap_Objective` | The lesson objective returns as a single concise statement. |
| 45 | 13:12-13:28 | `S001_SH45_Recap_FourSteps` | Four numbered cards summarize input, representation, meaning distinction, and parameter updates. |
| 46 | 13:28-13:42 | `S001_SH46_Recap_SelfCheck` | Five check-yourself prompts appear as a paced checklist, not a dense paragraph. |
| 47 | 13:42-13:54 | `S001_SH47_Recap_Exercise` | The `A` mini-lab task and sentence-completion exercise become the final action card. |
| 48 | 13:54-14:00 | `S001_SH48_Recap_NextLesson` | The complete pipeline settles into a restrained next-lesson end card. |

## 10. Motion-Language Contract

The Figma file documents motion intent but does not contain final animation.

| Property | Choice |
|---|---|
| Personality | Corporate, calm-sharp |
| Entrance easing | `cubic-bezier(0.22, 1, 0.36, 1)` |
| Exit easing | `cubic-bezier(0.4, 0, 1, 1)` |
| Base timing unit | 0.4 seconds / 12 frames at 30 fps |
| Group stagger | 60 ms reference; round to frame-appropriate timing in AE |
| Transition family | Match cut and crossfade only |
| Motion intensity | Travel at most 24 px; scale `0.96 -> 1.0`; overshoot at most 2% |
| Hold discipline | At least 0.3 seconds after a completed explanatory beat |
| Ambient motion | Low-contrast drift only; never animate reading text continuously |

Every shot note must identify:

- the purpose;
- the hero layer or group;
- supporting layers;
- layers that intentionally remain static;
- transition in and out; and
- any caution needed to preserve the lesson's technical meaning.

## 11. After Effects Handoff Contract

- Keep text live in Figma. The AE operator must have Sora, Inter, and JetBrains
  Mono installed before import.
- Preserve one top-level Figma frame per shot and one named group per motion
  unit.
- Separate glows, shadows, and mattes from their source shapes so effects can be
  rebuilt rather than baked.
- Keep character, number, prediction, and parameter cells as independent
  vectors where sequential animation is intended.
- Avoid deep nesting. Target no more than three group levels under a shot
  frame.
- Keep safe-area guides in `GUIDE_` groups and exclude them from export/import.
- Use 1x scale at 1920x1080. Do not rely on raster upscaling.
- The recommended AE organization after import is:

```text
01_Comps/
02_Precomps/
04_Images/
08_Reference/
99_Old/
```

- AE comp names should preserve the Figma shot names and add a version suffix,
  for example `S001_SH13_Technical_CatCodePoints_v01`.
- Final color space, codec, alpha interpretation, audio, and caption settings
  remain production decisions outside this Figma task.

## 12. Accessibility And Legibility

- Pair every color distinction with a label, position, shape, or line style.
- Use high-contrast primary text on navy or panel backgrounds.
- Keep explanatory copy short and progressively disclosed.
- Preserve at least 120 px of title-safe margin.
- Avoid flashing, rapid alternating contrast, constant camera movement, and
  more than one competing focal point.
- Hold diagrams long enough for a beginner to trace their causality.
- Do not animate text while it must be read.

## 13. Failure Handling And Rollback

- If a requested font is unavailable to the Figma plugin, stop and report the
  missing family rather than silently substituting a visually incompatible
  font.
- If the existing file cannot be edited, use `whoami` to verify the authenticated
  Figma account and report the access issue.
- Build in page sections and verify after each coherent batch. Do not stack
  corrective mutations after an unexpected result.
- Never mutate or delete the existing brand-kit page.
- Rollback consists of deleting the additive `02 Video 001 - AE Assets` page;
  no repository or existing Figma content must be restored.

## 14. Verification Strategy

1. Confirm the target file and inspect the source brand-kit node using Figma's
   design context before mutation.
2. Create the new page and theme/component sections first.
3. Build shots in eight section-sized batches.
4. After each batch, inspect metadata for frame count, dimensions, ordering, and
   layer names.
5. Capture screenshots of at least the component library and representative
   shots 01, 09, 15, 23, 30, 35, 41, and 45.
6. Inspect the thumbnail board for pacing, repetition, contrast, and one-hero
   hierarchy across the full sequence.
7. Search generated metadata for default layer names and for advanced
   vocabulary being used as explanatory labels rather than explicit deferred
   terms.
8. Verify all 48 expected frame names exist exactly once.
9. Verify code snippets, terminal text, numeric values, and warning language
   against `script.md` and `lab.py`.
10. Confirm the existing `01 Brand Kit` page remains unchanged.

## 15. Acceptance Criteria

The Figma asset task is complete when:

- the additive page exists in the supplied Figma file;
- all 48 named, composed 1920x1080 shots exist exactly once and in order;
- all eight narration sections are represented;
- the reusable component and theme-token sections are complete;
- every shot has one hero and a written motion note;
- live text and intended motion units remain independently editable;
- the exact source brand colors and font families are used consistently;
- code, terminal output, examples, and numeric values match the lesson sources;
- the representation-versus-learning distinction remains technically correct;
- no generated layer retains a default name;
- representative screenshots pass visual inspection for clipping, overlap,
  hierarchy, legibility, and contrast;
- the existing brand-kit page is unchanged; and
- residual AE import, font, color-management, and animation risks are reported
  without claiming host validation.

## 16. Residual Risks

- There is no recorded narration waveform, so sentence-level shot timing may
  need adjustment when voiceover becomes available.
- Figma-to-AE import behavior depends on the chosen transfer workflow and can
  affect text, gradients, blur, and component instances. That behavior requires
  a later AE-host test.
- Font availability must be confirmed on the AE workstation even if Figma loads
  the families successfully.
- The source brand kit defines sRGB hex colors but not the final AE working or
  output color space.
