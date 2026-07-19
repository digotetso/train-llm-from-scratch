# Figma Knowledge System Blueprint

This guide tells you exactly how to build a Figma knowledge map for this repository and for your wider learning system. It is written for a beginner in Figma, so it includes what to draw, the size of each object, where to place it, what text to use, and how to format it.

The reference style is the dark "business blueprint" system from the attached screenshots: a huge dark canvas, thin technical borders, title bars, tiny labels, modular panels, horizontal master lines, curved relationship lines, dashed dependency lines, artifact libraries, and dense but organized information. Use that structure, but use your own fonts and colors from `MY FONTS AND COLORS.png` and `MY COLORS.png`.

## 0. Final Outcome

When finished, your Figma file should have these pages:

1. `00 Components`
2. `01 Master Knowledge System`
3. `02 Training an LLM from Scratch`
4. `03 LLM Concept Library`
5. `04 Learning Log`

The most important page is `02 Training an LLM from Scratch`. It should look like a technical command center for the course:

- Top row: objective, models, environment, and course status.
- Middle row: a 10-step pipeline from dataset to iteration.
- Main body: five large blueprint panels for data, tokenizer/shards, model architecture, training, and evaluation/operations.
- Bottom row: artifact library, concept map, and KPI/tracking strip.
- Styling: dark navy background, thin blue-gray borders, Sora headings, Inter body text, JetBrains Mono code labels, cyan guide lines, purple model blocks, amber warnings, and green success states.

## 1. Figma Basics For This Build

Use these Figma tools:

| Need | Figma tool | Shortcut | How to use it |
| --- | --- | --- | --- |
| Big page/canvas | Frame | `F` | Click the canvas, then set exact `W` and `H` in the right sidebar. |
| Boxes/cards/panels | Rectangle | `R` | Draw a rectangle, then set `X`, `Y`, `W`, `H`, fill, stroke, and radius. |
| Text labels | Text | `T` | Click once for auto-size text, or drag for fixed-width paragraphs. |
| Straight lines | Line | `L` | Hold `Shift` to keep the line straight. Add arrowheads in the stroke panel. |
| Curved lines | Pen | `P` | Click to place points, drag slightly for curves, then set stroke and arrowhead. |
| Duplicate | Duplicate | `Cmd+D` | Duplicate selected object. Move it by typing exact `X` and `Y`. |
| Group | Group | `Cmd+G` | Use for temporary organization. |
| Component | Create component | `Cmd+Option+K` | Use on the reusable elements on `00 Components`. |
| Auto Layout | Auto Layout | `Shift+A` | Use inside cards/lists so text and rows stay aligned. |

In Figma, each object has position and size fields in the right sidebar:

- `X` means distance from the left edge of the parent frame.
- `Y` means distance from the top edge of the parent frame.
- `W` means width.
- `H` means height.

All coordinates in this guide assume the page frame starts at `X=0`, `Y=0`.

## 2. Create The Figma File

Create a new Figma design file called:

```text
Knowledge OS - Technical Master Map
```

Create these pages in the left sidebar:

```text
00 Components
01 Master Knowledge System
02 Training an LLM from Scratch
03 LLM Concept Library
04 Learning Log
```

On every page, create one main frame. Do not build directly on the empty Figma canvas. The frame is your blueprint board.

## 3. Visual System

Use your own colors exactly. Do not use the older gray palette from the first draft.

### 3.1 Color Styles

Create these color styles in Figma:

| Style name | Hex | Use |
| --- | --- | --- |
| `KS/BG` | `#0B1020` | Page/frame background. |
| `KS/Panel` | `#11182D` | Main panels, cards, title bars, nodes. |
| `KS/Text Primary` | `#F5F7FB` | Main headings and important labels. |
| `KS/Text Secondary` | `#A8B3CF` | Body text, muted labels, strokes. |
| `KS/Cyan Highlight` | `#35C7FF` | Active routes, guide lines, selected course, key dependencies. |
| `KS/Purple Model` | `#8B5CF6` | Model architecture blocks and transformer layers. |
| `KS/Amber Warning` | `#F59E0B` | Risk, cost, warning, unresolved items. |
| `KS/Green Progress` | `#22C55E` | Done, verified, working, passing tests. |

Use opacity to create border and background variation:

| Derived use | Color | Opacity |
| --- | --- | --- |
| Thin panel stroke | `#A8B3CF` | `55%` |
| Muted divider line | `#A8B3CF` | `28%` |
| Ghost label | `#A8B3CF` | `35%` |
| Cyan guide line | `#35C7FF` | `80%` |
| Panel fill variant | `#11182D` | `70%` |
| Alert fill | `#F59E0B` | `14%` |
| Success fill | `#22C55E` | `14%` |
| Model fill | `#8B5CF6` | `16%` |

### 3.2 Text Styles

Create these text styles. Keep letter spacing at `0%`.

| Style name | Font | Weight | Size | Line height | Color | Use |
| --- | --- | --- | --- | --- | --- | --- |
| `KS/Display Large` | Sora | ExtraBold or Bold | `96` | `112` | `#F5F7FB` | Huge page title or section number. |
| `KS/Heading Large` | Sora | Bold | `56` | `68` | `#F5F7FB` | Page title. |
| `KS/Heading Medium` | Sora | Bold | `34` | `44` | `#F5F7FB` | Blueprint title. |
| `KS/Heading Small` | Sora | SemiBold | `22` | `30` | `#F5F7FB` | Panel title bars. |
| `KS/Body Large` | Inter | Regular | `20` | `30` | `#A8B3CF` | Objective paragraphs. |
| `KS/Body Regular` | Inter | Regular | `16` | `24` | `#A8B3CF` | Panel body text. |
| `KS/Caption Primary` | Sora | SemiBold | `13` | `18` | `#F5F7FB` | Small headings, tags. |
| `KS/Caption Secondary` | Sora | Regular | `12` | `17` | `#A8B3CF` | Small notes. |
| `KS/Code Label` | JetBrains Mono | Medium | `13` | `19` | `#F5F7FB` | File names, shapes, pipeline labels. |
| `KS/Code Muted` | JetBrains Mono | Regular | `12` | `18` | `#A8B3CF` | Code notes and metadata. |

If Sora, Inter, or JetBrains Mono are not visible in Figma, open the font dropdown and search for them. They are Google fonts and usually available in Figma. If a font is missing, use:

- Sora fallback: `Space Grotesk`
- Inter fallback: `Arial`
- JetBrains Mono fallback: `Roboto Mono`

## 4. Global Drawing Rules

Follow these rules on every page.

### 4.1 Spacing

Use an 8 px spacing system:

| Spacing | Use |
| --- | --- |
| `8` | Space between tiny icon and label. |
| `12` | Space between rows inside small cards. |
| `16` | Card inner padding. |
| `24` | Panel inner padding. |
| `40` | Space between panels in a column. |
| `80` | Space between major sections. |
| `180` | Outer margin on the large blueprint page. |

### 4.2 Strokes

Use thin strokes like the reference screenshots.

| Element | Stroke |
| --- | --- |
| Large panel border | `1.5 px`, `#A8B3CF` at `55%` |
| Small card border | `1 px`, `#A8B3CF` at `45%` |
| Main system line | `3 px`, `#A8B3CF` at `55%` |
| Active guide line | `3 px`, `#35C7FF` at `80%` |
| Dashed dependency | `1.5 px`, `#A8B3CF` at `45%`, dash `10`, gap `10` |
| Curved relationship | `2 px`, `#A8B3CF` at `50%` |

For line endings:

- Use `Round` cap.
- Use `Round` join.
- Use a small arrowhead only when direction matters.

### 4.3 Corner Radius

Keep the blueprint technical, not soft.

| Element | Radius |
| --- | --- |
| Main panels | `6` |
| Cards/nodes | `4` |
| Pills | `4` |
| Status dots | Circle, no radius setting needed |

### 4.4 Text Alignment

Use this alignment:

- Page titles: left aligned.
- Panel title bars: centered.
- Body text: left aligned.
- Pipeline step titles: centered in the title bar.
- Code/file names: left aligned.
- Large numbers such as `001`: left aligned, low opacity.

### 4.5 Do Not Draw

Do not copy the big white video subtitles from the screenshots. Those are video captions over the design, not part of the blueprint.

Do not add gradients, decorative blobs, or heavy shadows. The reference is a structured dark blueprint, not a marketing page.

## 5. Reusable Components On `00 Components`

Create a main frame on `00 Components`:

```text
Frame name: 00 Components Board
X: 0
Y: 0
W: 5200
H: 3200
Fill: #0B1020
```

Add a page title:

```text
Text: COMPONENT LIBRARY
X: 180
Y: 120
W: 1600
H: 80
Style: KS/Heading Large
```

Add a small note:

```text
Text: Reusable parts for the Knowledge OS blueprint system.
X: 184
Y: 208
W: 1300
H: 32
Style: KS/Body Regular
```

Build the components below. After each component is complete, select the whole component and press `Cmd+Option+K`.

### 5.1 Component: `C/Blueprint Panel`

Place it here on the components board:

```text
X: 180
Y: 360
W: 900
H: 560
```

Draw:

1. Main rectangle:
   - `X: 180`, `Y: 360`, `W: 900`, `H: 560`
   - Fill: `#11182D` at `70%`
   - Stroke: `#A8B3CF` at `55%`, `1.5 px`
   - Radius: `6`
2. Title bar rectangle inside it:
   - `X: 180`, `Y: 360`, `W: 900`, `H: 44`
   - Fill: `#11182D`
   - Stroke bottom only if possible. If not, draw a line from `X=180`, `Y=404` to `X=1080`, `Y=404`.
3. Title text:
   - Text: `PANEL TITLE`
   - `X: 204`, `Y: 371`, `W: 852`, `H: 22`
   - Style: `KS/Heading Small`
   - Align: center
4. Body placeholder text:
   - Text: `Add diagram, list, table, metrics, or notes here.`
   - `X: 212`, `Y: 440`, `W: 820`, `H: 48`
   - Style: `KS/Body Regular`

Use this for large sections.

### 5.2 Component: `C/Pipeline Step`

Place it here:

```text
X: 1220
Y: 360
W: 620
H: 220
```

Draw:

1. Main rectangle:
   - Fill: `#11182D` at `70%`
   - Stroke: `#A8B3CF` at `55%`, `1.5 px`
   - Radius: `6`
2. Title bar:
   - `W: 620`, `H: 40`
   - Fill: `#11182D`
   - Bottom divider line: `#A8B3CF` at `35%`, `1 px`
3. Step number circle:
   - Circle size: `28 x 28`
   - Place at `X: 1236`, `Y: 370`
   - Fill: `#35C7FF` at `18%`
   - Stroke: `#35C7FF` at `80%`, `1 px`
   - Text: `01`, JetBrains Mono, `11`, centered
4. Title text:
   - Text: `DATASET SELECTION`
   - Place at `X: 1276`, `Y: 371`, `W: 540`, `H: 22`
   - Style: `KS/Code Label`
   - Align: center
5. Body text:
   - Place at `X: 1244`, `Y: 424`, `W: 572`, `H: 130`
   - Style: `KS/Code Muted`
   - Text:

```text
TinyStories / BabyLM
license + split
text field
manifest + hash
```

Use this for every pipeline stage.

### 5.3 Component: `C/Domain Node`

Place it here:

```text
X: 1980
Y: 360
W: 560
H: 92
```

Draw:

1. Rectangle:
   - Fill: `#11182D`
   - Stroke: `#A8B3CF` at `55%`, `1.5 px`
   - Radius: `4`
2. Text:
   - Text: `DOMAIN NAME`
   - Style: `KS/Heading Small`
   - Align: center
   - Center vertically and horizontally
3. Optional status dot:
   - Circle `14 x 14`
   - Place inside the right edge: `X: 2508`, `Y: 399`
   - Fill depends on status

Use this for big knowledge areas.

### 5.4 Component: `C/Sub Node`

Place it here:

```text
X: 1980
Y: 500
W: 320
H: 64
```

Draw:

1. Rectangle:
   - Fill: `#11182D` at `70%`
   - Stroke: `#A8B3CF` at `45%`, `1 px`
   - Radius: `4`
2. Text:
   - Style: `KS/Code Label`
   - Align: center

Use this for subdomains such as `Tokenizer`, `Attention`, and `Evaluation`.

### 5.5 Component: `C/Concept Card`

Place it here:

```text
X: 2760
Y: 360
W: 540
H: 300
```

Draw:

1. Main rectangle:
   - Fill: `#11182D` at `70%`
   - Stroke: `#A8B3CF` at `45%`, `1 px`
   - Radius: `6`
2. Title row:
   - Height: `46`
   - Divider line at `Y: 406`
3. Title text:
   - Text: `CONCEPT NAME`
   - `X: 2784`, `Y: 373`, `W: 420`, `H: 22`
   - Style: `KS/Heading Small`
4. Status dot:
   - Circle `14 x 14`
   - `X: 3258`, `Y: 378`
   - Fill: status color
5. Field labels and body:
   - Starting `X: 2784`, `Y: 430`
   - Use `KS/Caption Primary` for labels
   - Use `KS/Code Muted` for body
   - Add these labels:

```text
Definition
Why it matters
Used in
Related to
Open question
```

Use this for each learning concept.

### 5.6 Component: `C/Artifact Row`

Place it here:

```text
X: 3520
Y: 360
W: 640
H: 56
```

Draw:

1. Rectangle:
   - Fill: `#11182D` at `70%`
   - Stroke: `#A8B3CF` at `40%`, `1 px`
   - Radius: `4`
2. Small icon square:
   - `X: 3536`, `Y: 372`, `W: 32`, `H: 32`
   - Fill: `#35C7FF` at `14%`
   - Stroke: `#35C7FF` at `70%`
   - Text inside: `F`, `C`, `M`, or `R`
3. File text:
   - `X: 3584`, `Y: 371`, `W: 420`, `H: 20`
   - Style: `KS/Code Label`
4. Metadata text:
   - `X: 3584`, `Y: 392`, `W: 520`, `H: 16`
   - Style: `KS/Code Muted`

Use this for generated files and scripts.

### 5.7 Component: `C/Status Dot`

Create five circles, each `18 x 18`:

| Status | Fill | Stroke | Meaning |
| --- | --- | --- | --- |
| Planned | `#A8B3CF` at `35%` | `#A8B3CF` at `55%` | Not started. |
| Learning | `#35C7FF` | none | In progress. |
| Understood | `#22C55E` | none | Clear and verified. |
| Unclear | `#F59E0B` | none | Needs more study. |
| Blocked | `#F59E0B` at `22%` | `#F59E0B` | Cannot progress without a decision or fix. |

Place them at:

```text
X: 180
Y: 1040
Gap: 48
```

Add small labels under them using `KS/Caption Secondary`.

### 5.8 Component: `C/System Line`

Draw a line:

```text
X1: 180
Y1: 1240
X2: 1180
Y2: 1240
Stroke: #A8B3CF at 55%
Width: 3
Cap: round
```

Create two variants:

- `Solid`: no dash.
- `Active`: stroke `#35C7FF`, width `3`.

### 5.9 Component: `C/Curved Connector`

Use the Pen tool:

1. Press `P`.
2. Click start point.
3. Click the middle point and drag slightly to create a curve.
4. Click endpoint.
5. Set stroke:
   - Color: `#A8B3CF` at `50%`
   - Width: `2`
   - Cap: round
   - End arrow: triangle arrowhead if direction matters

Create two variants:

- Relationship curve: solid.
- Dependency curve: dashed with dash `10`, gap `10`.

### 5.10 Component: `C/Section Number Header`

Place it here:

```text
X: 1220
Y: 720
W: 1200
H: 160
```

Draw:

1. Number text:
   - Text: `001`
   - Style: `KS/Display Large`
   - Fill: `#A8B3CF` at `20%`
2. Title text:
   - Text: `Section Title v0.1`
   - Style: `KS/Heading Large`
   - Place to the right of the number

Use this to create the screenshot-style large numbered section labels.

## 6. Page `01 Master Knowledge System`

This page is the high-level map. Keep it simple. It shows your major life/work knowledge domains, not every detail.

### 6.1 Create The Frame

```text
Frame name: 01 Master Knowledge System Board
X: 0
Y: 0
W: 5200
H: 3200
Fill: #0B1020
```

### 6.2 Draw The Header

Add the large section header:

```text
Number text: 000
X: 180
Y: 120
W: 280
H: 120
Style: KS/Display Large
Fill: #A8B3CF at 20%

Title text: KNOWLEDGE OS v0.1
X: 420
Y: 145
W: 1600
H: 70
Style: KS/Heading Large
```

Add the subtitle:

```text
Text: Domains -> Responsibilities -> Projects -> Concepts -> Artifacts
X: 426
Y: 224
W: 1600
H: 30
Style: KS/Code Muted
```

### 6.3 Draw The Central Node

Create a `C/Domain Node` instance:

```text
Text: ME / KNOWLEDGE OPERATING SYSTEM
X: 1840
Y: 420
W: 1520
H: 104
```

Add a small caption below:

```text
Text: One map for learning, work, research, projects, and reusable artifacts.
X: 1880
Y: 548
W: 1440
H: 28
Style: KS/Body Regular
Align: center
```

### 6.4 Draw The Three Domain Branches

Place three large domain nodes:

| Node text | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| `DATA NETWORKS` | `420` | `800` | `1120` | `92` |
| `PHD COMPUTER SCIENCE` | `2040` | `800` | `1120` | `92` |
| `COURSES & LEARNING PROJECTS` | `3660` | `800` | `1120` | `92` |

Draw curved connectors from the central node to each domain node:

- Central bottom point: around `X=2600`, `Y=524`.
- Domain top points: `X=980`, `Y=800`; `X=2600`, `Y=800`; `X=4220`, `Y=800`.
- Stroke: `#A8B3CF` at `50%`, `2 px`.

### 6.5 Draw The Domain Panels

Create three large blueprint panels:

| Panel title | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| `DATA NETWORKS` | `260` | `1060` | `1480` | `1120` |
| `PHD COMPUTER SCIENCE` | `1860` | `1060` | `1480` | `1120` |
| `COURSES & LEARNING PROJECTS` | `3460` | `1060` | `1480` | `1120` |

Inside each panel, create sub nodes.

Data Networks sub nodes:

| Text | X | Y |
| --- | ---: | ---: |
| `PS Core` | `340` | `1160` |
| `IP Core` | `740` | `1160` |
| `ISP` | `1140` | `1160` |
| `Transport` | `340` | `1260` |
| `RAN` | `740` | `1260` |
| `OSS / BSS` | `1140` | `1260` |
| `Telecom Systems` | `540` | `1400` |

PhD Computer Science sub nodes:

| Text | X | Y |
| --- | ---: | ---: |
| `Research Area` | `1940` | `1160` |
| `Theory` | `2340` | `1160` |
| `Methods` | `2740` | `1160` |
| `Papers` | `1940` | `1260` |
| `Experiments` | `2340` | `1260` |
| `Writing` | `2740` | `1260` |
| `Supervision` | `2140` | `1400` |

Courses & Learning Projects sub nodes:

| Text | X | Y |
| --- | ---: | ---: |
| `Training an LLM from Scratch` | `3540` | `1160` |
| `Networking` | `3940` | `1160` |
| `Artificial Intelligence` | `4340` | `1160` |
| `Software Development` | `3540` | `1260` |
| `Future Courses` | `3940` | `1260` |

For `Training an LLM from Scratch`, add a `Learning` status dot:

```text
Dot X: 3828
Dot Y: 1179
Fill: #35C7FF
```

Draw thin curved lines from each domain node to its sub nodes.

### 6.6 Draw The Master System Line

This is the long horizontal line like the reference screenshots.

```text
Line start: X=260, Y=2380
Line end: X=4940, Y=2380
Stroke: #A8B3CF at 55%
Width: 3
Cap: round
```

Add five labels above the line:

| Label | X | Y |
| --- | ---: | ---: |
| `Domains` | `460` | `2316` |
| `Responsibilities` | `1380` | `2316` |
| `Projects` | `2480` | `2316` |
| `Concepts` | `3380` | `2316` |
| `Artifacts` | `4300` | `2316` |

Style: `KS/Code Label`.

Add small downward ticks from the line to each label position:

- Tick height: `64`
- Stroke: `#A8B3CF` at `45%`, `2 px`

### 6.7 Add The Rule Box

Create a small panel:

```text
Title: SYSTEM RULES
X: 260
Y: 2560
W: 4680
H: 360
```

Inside it, add three columns:

```text
1. Keep this page high level.
2. Put deep notes on project pages.
3. Every artifact should connect back to the concept or project that created it.
```

Use `KS/Body Regular` for the body. Highlight `high level`, `project pages`, and `artifact` in `#35C7FF`.

## 7. Page `02 Training an LLM from Scratch`

This is the main course blueprint. It should feel like a technical operating map for the repository.

### 7.1 Create The Frame

```text
Frame name: 02 Training an LLM from Scratch Board
X: 0
Y: 0
W: 7600
H: 4400
Fill: #0B1020
```

### 7.2 Page Header

Create the large numbered title:

```text
Number text: 001
X: 180
Y: 120
W: 290
H: 120
Style: KS/Display Large
Fill: #A8B3CF at 20%

Title text: TRAINING AN LLM FROM SCRATCH v0.1
X: 430
Y: 154
W: 2200
H: 70
Style: KS/Heading Large
```

Add source text:

```text
Text: Source repo: train-llm-from-scratch | Framework: MatGPT T4 Base Training Framework
X: 436
Y: 234
W: 2100
H: 28
Style: KS/Code Muted
```

### 7.3 Top Objective Panel

Draw a panel:

```text
Title: NORTH STAR
X: 180
Y: 340
W: 1800
H: 300
```

Inside it:

```text
Goal: Understand and build a small decoder-only GPT training system from dataset preparation to generation.

Success signal: deterministic data prep, training-only tokenizer fitting, packed token shards, FP16 T4 training, checkpoint resume, validation loss, perplexity, and fixed prompt samples.
```

Formatting:

- `Goal:` and `Success signal:` use `KS/Caption Primary`.
- Body uses `KS/Body Regular`.
- Highlight `decoder-only GPT`, `FP16 T4`, and `checkpoint resume` in cyan.

### 7.4 Top Model Cards

Create three model cards beside the objective panel:

| Card title | X | Y | W | H | Accent |
| --- | ---: | ---: | ---: | ---: | --- |
| `MatGPT-Mini 8M` | `2100` | `340` | `720` | `300` | Green |
| `MatGPT-Tiny 59M` | `2860` | `340` | `720` | `300` | Purple |
| `Target Environment` | `3620` | `340` | `720` | `300` | Cyan |

Each card:

- Fill: `#11182D` at `70%`
- Stroke: accent color at `70%`, `1.5 px`
- Radius: `6`
- Title: `KS/Heading Small`, top left `24 px` padding.
- Body: `KS/Code Muted`, `24 px` left padding, `74 px` from top.

Card body text:

```text
MatGPT-Mini 8M
Dataset: roneneldan/TinyStories
Context: 256
Vocab: 8192
Layers: 6
Heads: 8
Max tokens: 50M
```

```text
MatGPT-Tiny 59M
Dataset: BabyLM-community/BabyLM-2026-Strict
Context: 512
Vocab: 16384
Layers: 12
Heads: 8
Max tokens: 100M
```

```text
Target Environment
Google Colab T4
FP16
Gradient accumulation
Checkpoint resume
W&B optional
```

### 7.5 Top Status Card

Create a small repo status card:

```text
Title: REPO SURFACE
X: 4580
Y: 340
W: 2840
H: 300
```

Inside it, create four columns:

| Column | X inside panel | Text |
| --- | ---: | --- |
| `Scripts` | `24` | `prepare_dataset.py`, `train_tokenizer.py`, `tokenize_and_shard.py`, `benchmark_t4.py`, `pretrain.py`, `evaluate.py`, `chat.py` |
| `Core modules` | `720` | `matgpt/data`, `matgpt/tokenizer`, `matgpt/model`, `matgpt/training`, `matgpt/eval` |
| `Configs` | `1420` | `configs/matgpt_mini_8m.yaml`, `configs/matgpt_tiny_59m.yaml` |
| `Tests` | `2120` | `test_data`, `test_tokenizer`, `test_model`, `test_training_core`, `test_pretrain_smoke` |

Column headings: `KS/Caption Primary`. Items: `KS/Code Muted`.

### 7.6 Master System Line

Draw the long line that creates the visual structure:

```text
Line start: X=180, Y=860
Line end: X=7420, Y=860
Stroke: #A8B3CF at 55%
Width: 3
Cap: round
```

Add five labels above it:

| Label | X | Y |
| --- | ---: | ---: |
| `Data` | `520` | `790` |
| `Tokenizer & Shards` | `1870` | `790` |
| `Model` | `3370` | `790` |
| `Training` | `4800` | `790` |
| `Evaluation & Ops` | `6150` | `790` |

For each label, draw a down arrow from the line to the first pipeline card:

- Start Y: `860`
- End Y: `1010`
- Stroke: `#A8B3CF` at `45%`, `2 px`
- End arrow: small triangle

### 7.7 Config Folder And Dashed Dependencies

Draw a folder tile above the pipeline:

```text
X: 3440
Y: 690
W: 720
H: 92
Fill: #11182D
Stroke: #35C7FF at 80%, 1.5 px
Radius: 6
```

Text:

```text
CONFIGS
configs/matgpt_mini_8m.yaml
configs/matgpt_tiny_59m.yaml
```

Use `KS/Code Label` for `CONFIGS`; use `KS/Code Muted` for file names.

Draw dashed cyan connectors from this folder to pipeline steps `01`, `03`, `04`, `05`, `06`, `07`, `08`, and `09`.

Dash settings:

```text
Stroke: #35C7FF at 55%
Width: 1.5
Dash: 8
Gap: 8
No arrowhead
```

### 7.8 Main Pipeline Row

Create 10 `C/Pipeline Step` cards. Use these exact positions:

| Step | Title | X | Y | W | H |
| ---: | --- | ---: | ---: | ---: | ---: |
| `01` | `DATASET SELECTION` | `180` | `1040` | `620` | `220` |
| `02` | `NORMALIZE CORPUS` | `880` | `1040` | `620` | `220` |
| `03` | `TRAIN TOKENIZER` | `1580` | `1040` | `620` | `220` |
| `04` | `TOKENIZE + SHARD` | `2280` | `1040` | `620` | `220` |
| `05` | `MODEL ARCHITECTURE` | `2980` | `1040` | `620` | `220` |
| `06` | `BENCHMARK T4` | `3680` | `1040` | `620` | `220` |
| `07` | `PRETRAIN` | `4380` | `1040` | `620` | `220` |
| `08` | `EVALUATE` | `5080` | `1040` | `620` | `220` |
| `09` | `GENERATE / CHAT` | `5780` | `1040` | `620` | `220` |
| `10` | `ITERATE` | `6480` | `1040` | `620` | `220` |

Card body text:

```text
01 DATASET SELECTION
TinyStories / BabyLM
license + split
text_field
raw_dir
```

```text
02 NORMALIZE CORPUS
JSONL output
deterministic split
manifest
SHA hashes
```

```text
03 TRAIN TOKENIZER
byte-level BPE
train split only
special tokens
tokenizer report
```

```text
04 TOKENIZE + SHARD
append EOS
packed stream
uint16 .bin shards
metadata + split metadata
```

```text
05 MODEL ARCHITECTURE
decoder-only GPT
RoPE
RMSNorm
SwiGLU
```

```text
06 BENCHMARK T4
batch sizes
tokens/sec
peak memory
safe microbatch
```

```text
07 PRETRAIN
FP16
AdamW
grad accumulation
warmup/cosine LR
```

```text
08 EVALUATE
validation loss
perplexity
fixed prompts
best checkpoint
```

```text
09 GENERATE / CHAT
prompt
temperature
top_k / top_p
decode samples
```

```text
10 ITERATE
compare runs
adjust config
resume
document result
```

Draw solid arrows between the cards:

```text
Start: right center of previous card
End: left center of next card
Y: 1150
Stroke: #A8B3CF at 55%
Width: 2
End arrow: triangle
```

### 7.9 Main Blueprint Panels

Create five large panels under the pipeline. Each panel is `1320 x 1120`.

| Panel | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| `DATA BLUEPRINT` | `180` | `1420` | `1320` | `1120` |
| `TOKENIZER + SHARDS BLUEPRINT` | `1580` | `1420` | `1320` | `1120` |
| `MODEL ARCHITECTURE BLUEPRINT` | `2980` | `1420` | `1320` | `1120` |
| `TRAINING CONTROL BLUEPRINT` | `4380` | `1420` | `1320` | `1120` |
| `EVALUATION + OPS BLUEPRINT` | `5780` | `1420` | `1320` | `1120` |

Each panel:

- Fill: `#11182D` at `70%`
- Stroke: `#A8B3CF` at `55%`, `1.5 px`
- Radius: `6`
- Title bar height: `44`
- Title style: `KS/Heading Small`, centered

#### 7.9.1 Data Blueprint Panel

Inside `DATA BLUEPRINT`, draw three mini sections:

| Mini section | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| `DATASET SOURCES` | `220` | `1500` | `560` | `300` |
| `NORMALIZATION RULES` | `900` | `1500` | `560` | `300` |
| `OUTPUTS` | `220` | `1860` | `1240` | `560` |

`DATASET SOURCES` body:

```text
8M: roneneldan/TinyStories
59M: BabyLM-community/BabyLM-2026-Strict
Language: en
Stage: base_pretraining
```

`NORMALIZATION RULES` body:

```text
Use configured text field
Write normalized JSONL
Keep deterministic manifests
Use hash-based validation when needed
```

`OUTPUTS` body:

```text
matgpt/data/normalized/tinystories/train.jsonl
matgpt/data/normalized/tinystories/validation.jsonl
matgpt/data/normalized/tinystories/manifest.json
matgpt/data/normalized/babylm_2026_strict/train.jsonl
matgpt/data/normalized/babylm_2026_strict/validation.jsonl
matgpt/data/normalized/babylm_2026_strict/manifest.json
```

Add a small amber callout:

```text
X: 900
Y: 1860
W: 560
H: 160
Title: RISK
Body: BabyLM config creates validation from the training split because validation_split is null.
Fill: #F59E0B at 14%
Stroke: #F59E0B at 70%
```

#### 7.9.2 Tokenizer + Shards Blueprint Panel

Draw a left-to-right mini flow:

| Block | X | Y | W | H | Accent |
| --- | ---: | ---: | ---: | ---: | --- |
| `TRAIN TEXT ONLY` | `1620` | `1530` | `360` | `180` | Cyan |
| `BYTE-LEVEL BPE` | `2040` | `1530` | `360` | `180` | Cyan |
| `TOKENIZER FILES` | `2460` | `1530` | `360` | `180` | Green |
| `PACKED SHARDS` | `1830` | `1870` | `840` | `420` | Purple |

Add arrows between the first three blocks. Add a downward arrow from `TOKENIZER FILES` to `PACKED SHARDS`.

Text details:

```text
TRAIN TEXT ONLY
Fit tokenizer on train split
Do not fit on validation
min_frequency: 2
```

```text
BYTE-LEVEL BPE
8M vocab: 8192
59M vocab: 16384
Special tokens included
```

```text
TOKENIZER FILES
tokenizer.json
special_tokens.json
tokenizer_report.json
```

```text
PACKED SHARDS
append_eos: true
dtype: uint16
8M shard size: 5,000,000 tokens
59M shard size: 10,000,000 tokens
Writes train_metadata.json,
validation_metadata.json,
and combined metadata.json
```

#### 7.9.3 Model Architecture Blueprint Panel

Use purple for model internals. Draw this flow from left to right:

| Block | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| `input_ids [B,T]` | `3020` | `1530` | `260` | `100` |
| `Token Embedding` | `3340` | `1530` | `300` | `100` |
| `Dropout` | `3700` | `1530` | `220` | `100` |
| `Transformer Block x N` | `3020` | `1710` | `840` | `500` |
| `RMSNorm Final` | `3920` | `1780` | `320` | `100` |
| `LM Head` | `3920` | `1930` | `320` | `100` |
| `Logits [B,T,V]` | `3920` | `2080` | `320` | `100` |

All model blocks:

- Fill: `#8B5CF6` at `16%`
- Stroke: `#8B5CF6` at `75%`, `1.5 px`
- Text: `KS/Code Label`

Inside `Transformer Block x N`, draw a vertical stack:

```text
RMSNorm
QKV Projection
Causal Self-Attention + RoPE
Output Projection
Residual Add
RMSNorm
SwiGLU MLP
Residual Add
```

Each internal row:

- `X: 3060`
- `W: 760`
- `H: 42`
- Gap: `14`
- Fill: `#11182D`
- Stroke: `#8B5CF6` at `55%`, `1 px`

Add a small triangular mask icon beside `Causal Self-Attention + RoPE`:

```text
Shape: triangle
X: 3828
Y: 1834
W: 24
H: 24
Fill: #F59E0B
Label: No future tokens visible
```

Add model config note at bottom:

```text
8M: d_model 256, layers 6, heads 8, d_ff 1024
59M: d_model 512, layers 12, heads 8, d_ff 2048
```

#### 7.9.4 Training Control Blueprint Panel

Draw a circular training loop in the center:

```text
Outer circle: X=4710, Y=1610, W=620, H=620
Stroke: #35C7FF at 65%, 2 px
Fill: none

Inner circle: X=4890, Y=1790, W=260, H=260
Fill: #11182D
Stroke: #35C7FF at 70%, 1.5 px
Text: LOSS
```

Place loop labels around the circle:

| Label | X | Y |
| --- | ---: | ---: |
| `Sample packed batch` | `4630` | `1540` |
| `x = tokens[:-1]` | `4480` | `1760` |
| `Forward pass` | `4520` | `2070` |
| `Backward` | `4900` | `2310` |
| `Grad accumulation` | `5260` | `2070` |
| `AdamW step` | `5320` | `1760` |
| `LR scheduler` | `5080` | `1540` |

Use `KS/Code Label`.

Add arrowheads around the outer circle by drawing short curved arrow segments.

Add three formula cards:

| Card | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| `TOKENS PER STEP` | `4420` | `2260` | `380` | `190` |
| `8M RUN` | `4860` | `2260` | `340` | `190` |
| `59M RUN` | `5260` | `2260` | `340` | `190` |

Card text:

```text
tokens_per_step =
micro_batch_size
* context_length
* grad_accum_steps
```

```text
8M:
16 * 256 * 8
= 32,768 tokens
```

```text
59M:
4 * 512 * 16
= 32,768 tokens
```

Add a cyan note:

```text
Training is token-count driven, not epoch-driven.
```

#### 7.9.5 Evaluation + Ops Blueprint Panel

Draw four mini panels:

| Mini panel | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| `EVALUATION` | `5820` | `1510` | `580` | `360` |
| `GENERATION` | `6460` | `1510` | `580` | `360` |
| `CHECKPOINTS` | `5820` | `1930` | `580` | `360` |
| `OBSERVABILITY` | `6460` | `1930` | `580` | `360` |

Text:

```text
EVALUATION
validation loss
perplexity
eval_batches: 64
fixed prompts
```

```text
GENERATION
temperature: 0.8
top_k: 50
top_p: 0.95
max_new_tokens: 120
```

```text
CHECKPOINTS
latest.pt
best.pt
resume-from
keep milestones
```

```text
OBSERVABILITY
metrics.csv
samples/*.json
W&B optional
test suite
```

Add a green verification strip along the bottom:

```text
X: 5820
Y: 2350
W: 1220
H: 80
Fill: #22C55E at 14%
Stroke: #22C55E at 70%
Text: Verified by tests: config, data, tokenizer, shards, model, training core, smoke pretrain.
```

### 7.10 Artifact Library

Create a lower-left large panel:

```text
Title: THE ARTIFACT LIBRARY
X: 180
Y: 2740
W: 3420
H: 1060
```

Add a subtitle:

```text
Text: Every generated file should connect back to the step that creates it.
X: 220
Y: 2820
W: 1600
H: 28
Style: KS/Body Regular
```

Create four columns of artifact rows:

| Column | X | Y | W |
| --- | ---: | ---: | ---: |
| `Data` | `220` | `2900` | `760` |
| `Tokenizer` | `1040` | `2900` | `760` |
| `Shards` | `1860` | `2900` | `760` |
| `Runs` | `2680` | `2900` | `760` |

Artifact rows are `740 x 56`, gap `14`.

Data artifacts:

```text
matgpt/data/normalized/tinystories/train.jsonl
matgpt/data/normalized/tinystories/validation.jsonl
matgpt/data/normalized/tinystories/manifest.json
matgpt/data/normalized/babylm_2026_strict/train.jsonl
matgpt/data/normalized/babylm_2026_strict/validation.jsonl
matgpt/data/normalized/babylm_2026_strict/manifest.json
```

Tokenizer artifacts:

```text
matgpt/tokenizer/matgpt_mini_8m/tokenizer.json
matgpt/tokenizer/matgpt_mini_8m/special_tokens.json
matgpt/tokenizer/matgpt_mini_8m/tokenizer_report.json
matgpt/tokenizer/matgpt_tiny_59m/tokenizer.json
matgpt/tokenizer/matgpt_tiny_59m/special_tokens.json
matgpt/tokenizer/matgpt_tiny_59m/tokenizer_report.json
```

Shard artifacts:

```text
matgpt/data/shards/matgpt_mini_8m/train_00000.bin
matgpt/data/shards/matgpt_mini_8m/validation_00000.bin
matgpt/data/shards/matgpt_mini_8m/train_metadata.json
matgpt/data/shards/matgpt_mini_8m/validation_metadata.json
matgpt/data/shards/matgpt_mini_8m/metadata.json
matgpt/data/shards/matgpt_tiny_59m/train_00000.bin
matgpt/data/shards/matgpt_tiny_59m/validation_00000.bin
matgpt/data/shards/matgpt_tiny_59m/train_metadata.json
matgpt/data/shards/matgpt_tiny_59m/validation_metadata.json
matgpt/data/shards/matgpt_tiny_59m/metadata.json
```

Run artifacts:

```text
runs/<name>/metrics.csv
runs/<name>/checkpoints/latest.pt
runs/<name>/checkpoints/best.pt
runs/<name>/samples/samples_*.json
notebooks/train_matgpt_t4_base_colab.ipynb
```

Draw dashed connectors:

- Data artifacts -> Steps `01` and `02`
- Tokenizer artifacts -> Step `03`
- Shard artifacts -> Step `04`
- Run artifacts -> Steps `07`, `08`, and `09`

### 7.11 Concept Map Panel

Create a lower-right panel:

```text
Title: CONCEPT MAP
X: 3780
Y: 2740
W: 3320
H: 1060
```

In the center, draw a circular hub:

```text
Outer circle: X=5140, Y=3050, W=460, H=460
Stroke: #A8B3CF at 55%, 2 px
Fill: none

Inner circle: X=5260, Y=3170, W=220, H=220
Fill: #11182D
Stroke: #35C7FF at 70%, 2 px
Text: LEARN
```

Around it, add six concept clusters:

| Cluster | X | Y | Accent |
| --- | ---: | ---: | --- |
| `Data` | `3940` | `2880` | Cyan |
| `Tokenizer` | `3940` | `3340` | Cyan |
| `Transformer` | `6200` | `2880` | Purple |
| `Training` | `6200` | `3340` | Purple |
| `Open Questions` | `4930` | `2830` | Amber |
| `Evaluation` | `4930` | `3580` | Green |

Each cluster:

- Side cluster rectangle: `720 x 210`
- Top/bottom cluster rectangle: `880 x 180`
- Fill: `#11182D` at `70%`
- Stroke: accent color at `70%`
- Radius: `6`
- Title: `KS/Heading Small`
- Items: `KS/Code Muted`

Cluster items:

```text
Data
JSONL
manifest
hash split
license
```

```text
Tokenizer
byte-level BPE
EOS token
vocab size
special tokens
```

```text
Transformer
causal attention
RoPE
RMSNorm
SwiGLU
```

```text
Training
FP16
AdamW
grad accumulation
warmup/cosine
```

```text
Evaluation
validation loss
perplexity
fixed prompts
sample quality
```

```text
Open Questions
What changed?
What is unclear?
What needs testing?
What affects quality?
```

Draw curved connectors from each cluster to the hub.

### 7.12 KPI And Review Strip

Create a bottom strip:

```text
Title: KPI METRICS + REVIEW CHECKS
X: 180
Y: 3920
W: 6920
H: 320
```

Make six equal columns inside the strip:

| Column | Title | Body |
| --- | --- | --- |
| 1 | `Data` | `docs processed`, `validation split`, `manifest hash` |
| 2 | `Tokenizer` | `vocab size`, `fertility`, `round-trip test` |
| 3 | `Model` | `params`, `context length`, `causality test` |
| 4 | `Training` | `tokens/sec`, `peak memory`, `loss curve` |
| 5 | `Evaluation` | `val loss`, `perplexity`, `sample prompts` |
| 6 | `Release` | `checkpoint exists`, `resume works`, `README updated` |

Column size:

```text
W: 1080
H: 220
Gap: 40
Start X: 220
Start Y: 4000
```

Use `KS/Caption Primary` for column titles and `KS/Code Muted` for body.

## 8. Page `03 LLM Concept Library`

This page stores reusable learning cards. It is not a pipeline. It is a library.

### 8.1 Create The Frame

```text
Frame name: 03 LLM Concept Library Board
X: 0
Y: 0
W: 5600
H: 3600
Fill: #0B1020
```

### 8.2 Header

```text
Number text: 003
X: 180
Y: 120
W: 280
H: 120
Style: KS/Display Large
Fill: #A8B3CF at 20%

Title text: LLM CONCEPT LIBRARY v0.1
X: 430
Y: 154
W: 1900
H: 70
Style: KS/Heading Large
```

Subtitle:

```text
Text: Each concept gets one card. Connect cards back to pipeline steps on Page 02.
X: 436
Y: 234
W: 2000
H: 28
Style: KS/Body Regular
```

### 8.3 Section Columns

Create seven section panels:

| Section | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| `DATA CONCEPTS` | `180` | `420` | `720` | `1320` |
| `TOKENIZER CONCEPTS` | `960` | `420` | `720` | `1320` |
| `TRANSFORMER CONCEPTS` | `1740` | `420` | `720` | `1320` |
| `TRAINING CONCEPTS` | `2520` | `420` | `720` | `1320` |
| `EVALUATION CONCEPTS` | `3300` | `420` | `720` | `1320` |
| `INFRA CONCEPTS` | `4080` | `420` | `720` | `1320` |
| `OPEN QUESTIONS` | `4860` | `420` | `560` | `1320` |

Inside each section, place compact concept cards:

```text
Card W: 640
Card H: 180
Card X: section X + 40
First card Y: 520
Gap: 28
```

Compact card fields:

```text
Concept:
Definition:
Used in:
Question:
```

### 8.4 Starter Concept Cards

Add these starter cards.

Data:

- `TinyStories`
- `BabyLM Strict`
- `JSONL`
- `Manifest`
- `Hash Validation Split`

Tokenizer:

- `Byte-Level BPE`
- `EOS Token`
- `Special Tokens`
- `Vocab Size`
- `Packed Token Stream`

Transformer:

- `Decoder-Only Transformer`
- `Causal Self-Attention`
- `RoPE`
- `RMSNorm`
- `SwiGLU`

Training:

- `FP16`
- `Gradient Accumulation`
- `AdamW`
- `Warmup + Cosine LR`
- `Gradient Clipping`

Evaluation:

- `Validation Loss`
- `Perplexity`
- `Fixed Prompt Samples`
- `Best Checkpoint`
- `Generation Settings`

Infrastructure:

- `Colab T4`
- `Checkpoint Resume`
- `W&B Tracking`
- `Pytest Smoke Test`
- `Notebook Workflow`

Open Questions:

- `Which examples prove learning?`
- `What does a bad sample look like?`
- `When should vocab size change?`
- `What is the first quality bottleneck?`

### 8.5 Concept Card Fill Rules

Use status dots:

- Cyan dot: currently learning.
- Green dot: understood and tested.
- Amber dot: unclear or needs review.

Do not make a card green because you watched a video. Make it green only when you can explain it and point to where it appears in the repo.

## 9. Page `04 Learning Log`

This page tracks what you learned and what changed.

### 9.1 Create The Frame

```text
Frame name: 04 Learning Log Board
X: 0
Y: 0
W: 4200
H: 2800
Fill: #0B1020
```

### 9.2 Header

```text
Number text: 004
X: 180
Y: 120
W: 280
H: 120
Style: KS/Display Large
Fill: #A8B3CF at 20%

Title text: LEARNING LOG v0.1
X: 430
Y: 154
W: 1600
H: 70
Style: KS/Heading Large
```

### 9.3 Weekly Review Table

Create a large panel:

```text
Title: WEEKLY REVIEW
X: 180
Y: 380
W: 3840
H: 880
```

Inside, draw a table with six columns:

| Column | Width |
| --- | ---: |
| `Date` | `320` |
| `Topic` | `620` |
| `What I understood` | `900` |
| `What is unclear` | `760` |
| `Artifact updated` | `760` |
| `Next action` | `420` |

Header row:

- Height: `56`
- Fill: `#11182D`
- Stroke: `#A8B3CF` at `45%`
- Text style: `KS/Caption Primary`

Data rows:

- Height: `96`
- Text style: `KS/Code Muted`
- Add 6 starter rows.

### 9.4 Decision Log

Create a panel:

```text
Title: DECISION LOG
X: 180
Y: 1380
W: 1840
H: 880
```

Use this format:

```text
Decision:
Why:
Evidence:
Files affected:
Review date:
```

Starter decisions:

- `Use byte-level BPE`
- `Use FP16 on T4`
- `Use checkpoint resume`
- `Use token-count driven training`

### 9.5 Question Queue

Create a panel:

```text
Title: QUESTION QUEUE
X: 2180
Y: 1380
W: 1840
H: 880
```

Use this format:

```text
Question:
Why it matters:
Where to check:
Status:
```

Starter questions:

- `How do tokenizer errors show up in samples?`
- `What loss value is good enough for this course?`
- `Which prompt set best shows progress?`
- `When does T4 memory become the limit?`

## 10. Beginner Build Order

Build in this order. Do not try to draw the whole system at once.

1. Create all pages.
2. Create color styles.
3. Create text styles.
4. Build `00 Components`.
5. Build `01 Master Knowledge System`.
6. Build the header, objective, model cards, and system line on `02 Training an LLM from Scratch`.
7. Add the 10 pipeline cards.
8. Add the five main blueprint panels.
9. Add the artifact library.
10. Add the concept map.
11. Add the KPI strip.
12. Build `03 LLM Concept Library`.
13. Build `04 Learning Log`.
14. Go back and add curved/dashed connectors.
15. Zoom out to 10% and check whether the structure is readable.
16. Zoom in to 100% and check whether the text is readable.

## 11. Formatting Checklist

Use this before calling the Figma version finished.

- Background is `#0B1020`.
- Main panels are `#11182D`.
- Main text is `#F5F7FB`.
- Secondary text is `#A8B3CF`.
- Cyan is used only for active routes, dependencies, and selected course items.
- Purple is used for model/transformer internals.
- Amber is used only for risks, warnings, and unclear items.
- Green is used only for verified/progress/done items.
- Borders are thin, not thick.
- Corners are `4` or `6`, not heavily rounded.
- Page 02 has a clear top-to-bottom hierarchy: title, context, master line, pipeline, panels, library/KPIs.
- Every generated artifact points to the pipeline step that creates it.
- Every concept card has a status dot.
- The map still works when zoomed out.

## 12. What To Update As The Course Grows

Update the Figma file when one of these changes:

- A new script is added under `scripts/`.
- A config changes under `configs/`.
- A new generated artifact appears under `matgpt/data`, `matgpt/tokenizer`, or `runs`.
- A new concept becomes important enough to explain in the course.
- A test is added that verifies a new behavior.
- A training run gives a result worth comparing.

When updating:

1. Add or change the artifact row first.
2. Connect it to the pipeline step.
3. Add or update the concept card.
4. Add a learning log entry.
5. Change the page version label from `v0.1` to `v0.2`, `v0.3`, and so on.

## 13. Source Of Truth

Use these repository files as the truth for the content of the blueprint:

- `README.md`: course objective, workflow, commands, and outputs.
- `configs/matgpt_mini_8m.yaml`: 8M TinyStories model/data/training settings.
- `configs/matgpt_tiny_59m.yaml`: 59M BabyLM model/data/training settings.
- `scripts/prepare_dataset.py`: dataset preparation entry point.
- `scripts/train_tokenizer.py`: tokenizer training entry point.
- `scripts/tokenize_and_shard.py`: tokenization and shard creation entry point.
- `scripts/benchmark_t4.py`: T4 benchmark entry point.
- `scripts/pretrain.py`: training entry point.
- `scripts/evaluate.py`: evaluation entry point.
- `scripts/chat.py`: generation/chat entry point.
- `tests/`: evidence that important behavior is verified.

Use the attached reference screenshots only for visual style. Use the repository files for technical truth.
