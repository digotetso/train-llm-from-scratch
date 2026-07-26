# Training Examples Narration Audio Edit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a source-complete, coherent, professionally edited,
production-ready 11:50 narration master in Adobe Audition while preserving the
immutable source recording and using the production script's visual timing as
a reference.

**Architecture:** Use local Whisper and FFmpeg only for read-only analysis,
alignment, and independent verification. Use a non-destructive Adobe Audition
multitrack session for take selection, assembly, timing, corrective processing,
and rendering. Record every source-to-output decision and measurement in a
human-readable audit log beside the session and master.

**Tech Stack:** Adobe Audition 13.0.2 build 35, Audio MCP Audition bridge,
Computer Use for Audition UI operations not exposed by MCP, OpenAI Whisper CLI,
FFmpeg/FFprobe, SHA-256, Markdown.

## Global Constraints

- Treat the recorded narration as the wording authority. Use
  `course/video-1-training-example/script.md` as the structural, teaching-flow,
  and timing reference. Retain intentional coherent changes such as two key
  points instead of three.
- Speak only prose under `### Narration`; never include headings, code blocks,
  terminal output, or visual directions.
- Never overwrite, rename, move, or delete
  `/Users/digotetsomatema/Desktop/audio/training_examples.wav` or
  `/Users/digotetsomatema/Desktop/audio/training_examples.pkf`.
- Preserve 48 kHz sample rate, 24-bit PCM depth, and mono output.
- Use an Adobe Audition multitrack session for assembly and final rendering.
- Preserve intentional visual, prediction, and demonstration holds.
- Target approximately -16 LUFS integrated and no more than -1.5 dBTP without
  audible processing artifacts.
- Do not synthesize, rewrite, omit, or phoneme-assemble missing narration.
- Mark any intended source-led teaching idea without a complete intelligible
  take as a pickup.
- Keep production work under
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/`.
- Do not commit WAV, PKF, SESX, transcripts, measurements, or edit logs to the
  repository.

---

## File and Artifact Map

**Repository files**

- Read:
  `course/video-1-training-example/script.md` — authoritative content and timing.
- Read:
  `docs/superpowers/specs/2026-07-26-training-examples-audio-edit-design.md` —
  approved design and acceptance criteria.
- Read:
  `docs/superpowers/plans/2026-07-26-training-examples-audio-edit.md` — this
  execution checklist.

**Immutable source files**

- Read only:
  `/Users/digotetsomatema/Desktop/audio/training_examples.wav`
- Read only:
  `/Users/digotetsomatema/Desktop/audio/training_examples.pkf`

**Production files**

- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/source_checksums.sha256`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/source_ffprobe.json`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/source_loudness.txt`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/source_silence.txt`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/source_astats.txt`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/source_processing_decisions.txt`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_working.wav`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples.json`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_transcript.txt`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_source_words.tsv`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_edl.md`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_edit_v1.sesx`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_master_v1.wav`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/master_ffprobe.json`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/master_loudness.txt`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/master_silence.txt`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/master_astats.txt`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/master_transcription.json`
- Create:
  `/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_edit_log.md`

---

### Task 1: Establish the Immutable Source Baseline

**Interfaces:**

- Consumes: the two immutable source paths from Global Constraints.
- Produces: source checksum, metadata, and a byte-identical working WAV copy.

- [ ] **Step 1: Refuse to overwrite an earlier production run**

Run:

```bash
test ! -e "/Users/digotetsomatema/Desktop/audio/training_examples_production"
```

Expected: exit status 0. If the directory already exists, stop and inspect it;
do not overwrite or delete it.

- [ ] **Step 2: Create the production directory**

Run:

```bash
mkdir -p "/Users/digotetsomatema/Desktop/audio/training_examples_production"
```

Expected: the directory exists and neither source file changes.

- [ ] **Step 3: Record immutable source checksums**

Run:

```bash
shasum -a 256 \
  "/Users/digotetsomatema/Desktop/audio/training_examples.wav" \
  "/Users/digotetsomatema/Desktop/audio/training_examples.pkf" \
  > "/Users/digotetsomatema/Desktop/audio/training_examples_production/source_checksums.sha256"
```

Expected: exactly two SHA-256 records.

- [ ] **Step 4: Record source metadata**

Run:

```bash
ffprobe -v error -show_format -show_streams -of json \
  "/Users/digotetsomatema/Desktop/audio/training_examples.wav" \
  > "/Users/digotetsomatema/Desktop/audio/training_examples_production/source_ffprobe.json"
```

Expected fields:

```text
codec_name=pcm_s24le
sample_rate=48000
channels=1
bits_per_sample=24
duration=988.863896
```

- [ ] **Step 5: Create and verify the working copy**

Run:

```bash
cp -p \
  "/Users/digotetsomatema/Desktop/audio/training_examples.wav" \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_working.wav"
```

Run:

```bash
shasum -a 256 \
  "/Users/digotetsomatema/Desktop/audio/training_examples.wav" \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_working.wav"
```

Expected: the two hashes are identical.

- [ ] **Step 6: Recheck source immutability**

Run:

```bash
shasum -a 256 -c \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/source_checksums.sha256"
```

Expected:

```text
/Users/digotetsomatema/Desktop/audio/training_examples.wav: OK
/Users/digotetsomatema/Desktop/audio/training_examples.pkf: OK
```

---

### Task 2: Transcribe and Measure the Source

**Interfaces:**

- Consumes:
  `training_examples_working.wav` and the authoritative production script.
- Produces: word-timestamped transcript and objective source measurements used
  by the edit decision list.

- [ ] **Step 1: Transcribe locally with word timestamps**

Run:

```bash
whisper \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_working.wav" \
  --model turbo \
  --device cpu \
  --language en \
  --task transcribe \
  --word_timestamps True \
  --fp16 False \
  --condition_on_previous_text True \
  --hallucination_silence_threshold 2 \
  --initial_prompt "large language model, LLM, training_examples.py, shifted_targets.py, input, target, Python, The opposite of hot is cold" \
  --output_format all \
  --output_dir "/Users/digotetsomatema/Desktop/audio/training_examples_production"
```

Expected: files named `training_examples_working.json`, `.txt`, `.tsv`, `.srt`,
and `.vtt` exist. No network transmission of the audio is permitted; the CLI
must run locally.

- [ ] **Step 2: Preserve analysis outputs under stable deliverable names**

Run:

```bash
mv \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_working.json" \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples.json"
```

Run:

```bash
cp \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_working.txt" \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_transcript.txt"
```

Expected: `training_examples.json` and `training_examples_transcript.txt` are
non-empty.

- [ ] **Step 3: Extract word-level source timing**

Run:

```bash
jq -r \
  '.segments[] | .words[]? | [.start, .end, (.word | gsub("^ +| +$"; "")), .probability] | @tsv' \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples.json" \
  > "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_source_words.tsv"
```

Expected: each row contains start seconds, end seconds, word, and probability.

- [ ] **Step 4: Measure integrated loudness and true peak**

Run:

```bash
ffmpeg -hide_banner -nostats \
  -i "/Users/digotetsomatema/Desktop/audio/training_examples.wav" \
  -filter_complex ebur128=peak=true \
  -f null - \
  2> "/Users/digotetsomatema/Desktop/audio/training_examples_production/source_loudness.txt"
```

Expected: the final EBU R128 summary includes integrated LUFS, LRA, and true
peak.

- [ ] **Step 5: Detect candidate silence without editing**

Run:

```bash
ffmpeg -hide_banner -nostats \
  -i "/Users/digotetsomatema/Desktop/audio/training_examples.wav" \
  -af silencedetect=noise=-45dB:d=0.35 \
  -f null - \
  2> "/Users/digotetsomatema/Desktop/audio/training_examples_production/source_silence.txt"
```

Expected: candidate `silence_start`, `silence_end`, and `silence_duration`
records. These are analysis hints, not automatic cut instructions.

- [ ] **Step 6: Measure source peaks, RMS, DC offset, and noise indicators**

Run:

```bash
ffmpeg -hide_banner -nostats \
  -i "/Users/digotetsomatema/Desktop/audio/training_examples.wav" \
  -af astats=metadata=1:reset=0 \
  -f null - \
  2> "/Users/digotetsomatema/Desktop/audio/training_examples_production/source_astats.txt"
```

Expected: peak level, RMS level, dynamic range, DC offset, and noise-floor
statistics are present.

- [ ] **Step 7: Gate processing decisions from measurements**

Create `source_processing_decisions.txt` with these exact decision gates and
record whether each process is enabled or disabled after listening:

```text
High-pass: enable at 70 Hz, 12 dB/oct only if audible rumble or material
sub-70 Hz energy is present; otherwise disabled.
Noise reduction: enable only if broadband room noise is audibly distracting;
maximum reduction 6 dB and no audible metallic modulation; otherwise disabled.
De-esser: enable only for recurring harsh 5-9 kHz sibilance; maximum gain
reduction 4 dB; otherwise disabled.
Compression: 2.5:1, 10 ms attack, 100 ms release, soft knee, with threshold
set for 3-6 dB maximum gain reduction; disable if level consistency is already
within that range.
Limiter/loudness: final integrated target -16 LUFS, true-peak ceiling
-1.5 dBTP.
```

---

### Task 3: Build the Script-Locked Edit Decision List

**Interfaces:**

- Consumes: `script.md`, `training_examples_transcript.txt`,
  `training_examples_source_words.tsv`, `source_processing_decisions.txt`,
  silence analysis, and source measurements.
- Produces: `training_examples_edl.md`, the exact source-to-timeline contract
  used in Audition.

- [ ] **Step 1: Create the EDL header and schema**

Create `training_examples_edl.md` with this exact table:

```markdown
# Training Examples Narration Edit Decision List

| ID | Script section | Script text | Source in | Source out | Output in | Output out | Decision | Confidence | Notes |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | --- |
```

Use one row per sentence or independently editable phrase. Time values are
seconds with three decimal places. Confidence is Whisper's mean word
probability for the retained phrase, supplemented by listening.

- [ ] **Step 2: Mark all mandatory section boundaries**

Add marker rows with these exact output times:

```text
00:00.000 The AI We Are Going to Build
01:00.000 A Sentence You Can Finish
01:50.000 The Answer Is Already in the Sentence
02:40.000 Make One Example by Hand
03:50.000 One Sentence, Five Examples
05:10.000 Build the Examples in Python
06:50.000 The Same Sequence, Shifted One Place
08:20.000 Run, Observe, and Explain
10:10.000 Three Easy Mistakes
11:00.000 The Mental Model
11:50.000 Program End
```

- [ ] **Step 3: Align the intended recorded narration to clean source takes**

Use the recorded teaching sequence as the wording authority and the prose under
`### Narration` as the structural and timing reference:

1. Normalize case, curly quotes, Markdown emphasis, and punctuation for
   comparison only.
2. Locate every matching or near-matching span in the word-timestamp TSV.
3. Listen to each candidate in Audition.
4. Select the clearest complete take with natural delivery.
5. Enter its exact source in/out with 100-250 ms handles.
6. Record discarded repeats or false starts as `REMOVE` rows.
7. Record unclear but unavoidable content as `PICKUP-RISK`.

Expected: every intended source-led narration idea has exactly one `KEEP` row.

- [ ] **Step 4: Place explicit visual and learner holds**

Add `ROOM-TONE` rows so speech does not occupy these protected beats:

```text
01:00-01:12 missing-word prompt, including two-second learner prediction
03:32-03:50 six-word example-count prediction
06:42-06:50 example-line prediction
08:05-08:20 shifted-list prediction
10:05-10:10 changed-sentence prediction
11:37-11:44 closing mental-model hold
11:44-11:50 course-path end hold
```

Where a visual range also carries narration, preserve the explicit learner
prediction at the end of the range and place narration earlier in that section.

- [ ] **Step 5: Validate EDL content and timing**

Check all of the following manually:

```text
Every intended source-led narration idea: exactly one KEEP row
Every source range: within 0.000-988.864
Every output range: monotonic and non-overlapping
Every section marker: exact to 0.001 seconds
Every protected hold: present
Program end: 710.000 seconds
Every REMOVE row: reason recorded
Every confidence below 0.80: listening verification recorded
```

Stop before Audition assembly if an intended source-led teaching idea has no
complete, intelligible candidate. Record the source range and pickup need
instead of inventing or omitting words.

---

### Task 4: Create the Non-Destructive Audition Session

**Interfaces:**

- Consumes: the working WAV and validated EDL.
- Produces: `training_examples_edit_v1.sesx` with one dialogue track, one room
  tone track, a stereo master bus during editing, and exact timeline markers.

- [ ] **Step 1: Confirm the Audition bridge and application**

Call `audition_get_status`.

Expected:

```text
application.version=13.0.2
application.build_number=35
transport_available=true
```

Visually confirm the Audio MCP panel shows:

```text
Configuration: loaded
Bridge: authenticated
```

- [ ] **Step 2: Create the multitrack session through Audition**

Using Computer Use:

1. Choose **File → New → Multitrack Session**.
2. Set session name to `training_examples_edit_v1`.
3. Set folder to
   `/Users/digotetsomatema/Desktop/audio/training_examples_production/`.
4. Set template to `None`.
5. Set sample rate to `48000`.
6. Set bit depth to `24`.
7. Create the session.

Expected:
`training_examples_edit_v1.sesx` exists in the production directory.

- [ ] **Step 3: Import only the working copy**

Using **File → Import → File**, import:

```text
/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_working.wav
```

Place it on a mono dialogue track named `VO EDIT`. Do not import or open the
immutable source WAV in Waveform Editor.

- [ ] **Step 4: Create the room-tone and reference structure**

Create:

```text
Track 1: VO EDIT, mono
Track 2: ROOM TONE, mono
Track 3: SOURCE REFERENCE, mono, muted and locked
```

Place a full-length copy of the working WAV on `SOURCE REFERENCE`, mute it, and
lock it. Keep it at session time `00:00.000` as the visual reference for source
timecodes.

- [ ] **Step 5: Add exact section and hold markers**

Add section markers at the eleven times from Task 3 Step 2. Add range markers
for each protected hold from Task 3 Step 4.

Expected: marker timestamps match the EDL within one sample.

- [ ] **Step 6: Save and reopen the session**

Save, close only the session, reopen `training_examples_edit_v1.sesx`, and call
`audition_get_document`.

Expected: the document type is multitrack/session, the session reopens without
missing-media or sample-rate warnings, and the immutable source is unchanged.

---

### Task 5: Assemble the Script-Locked Dialogue Edit

**Interfaces:**

- Consumes: validated EDL and the Audition session.
- Produces: a complete VO assembly aligned to the fixed production timeline.

- [ ] **Step 1: Create one clip for each `KEEP` EDL row**

For every `KEEP` row:

1. Duplicate from `SOURCE REFERENCE` or the Files panel onto `VO EDIT`.
2. Set the clip's source in/out to the EDL source range.
3. Set its destination start to the EDL output-in time.
4. Trim handles so no abandoned syllable or adjacent take remains.
5. Retain natural inhalations when they support the sentence.

Expected: clip source and destination properties match the EDL within one
sample.

- [ ] **Step 2: Make every edit click-free**

At adjacent speech edits:

```text
Crossfade duration: 10-25 ms
Curve: equal power
Edit point: zero crossing where practical
Maximum overlap: 50 ms unless a longer room-tone transition is required
```

Listen across each edit at normal speed and headphones. Extend the fade only
when the room tone changes audibly; do not smear consonants.

- [ ] **Step 3: Fill intentional holds with source room tone**

Choose a clean 1-3 second source region with no speech, breath, click, or
handling noise. Place repeated, alternated copies on `ROOM TONE` under protected
holds with 50-100 ms equal-power crossfades.

Expected: holds sound continuous with surrounding narration and contain no
looping cadence. Extend room tone through exactly `11:50.000` so the session
mixdown has the required 710.000-second duration.

- [ ] **Step 4: Match clip gain before dynamics**

Adjust clip gain so sentence-level short-term loudness remains within 3 LU
between retained takes. Do not use track compression to conceal a single
mis-matched clip.

- [ ] **Step 5: Perform the first complete script listen**

Listen from `00:00.000` to `11:50.000` while following `script.md` and the EDL.
For each sentence, mark:

```text
present
in order
intelligible
not duplicated
not clipped
correctly timed
```

Resolve every failed mark before processing.

- [ ] **Step 6: Preserve the assembly checkpoint**

Save the session, then use **File → Save Copy As** to create:

```text
/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_edit_v1_preprocess.sesx
```

Expected: the checkpoint reopens independently and references the working WAV,
not the immutable source.

---

### Task 6: Apply Measured Corrective Processing and Render

**Interfaces:**

- Consumes: assembled session, Task 2 measurements, and
  `source_processing_decisions.txt`.
- Produces: processed session and `training_examples_master_v1.wav`.

- [ ] **Step 1: Apply only enabled corrective processes**

On the `VO EDIT` track, apply the exact enabled gates from Task 2 Step 7:

```text
High-pass: 70 Hz, 12 dB/oct
Noise reduction: no more than 6 dB
De-esser: no more than 4 dB gain reduction in 5-9 kHz
Compression: 2.5:1, 10 ms attack, 100 ms release, soft knee, 3-6 dB maximum
gain reduction
```

Leave each untriggered process disabled. Record every enabled effect, setting,
and reason in the edit log.

- [ ] **Step 2: Loudness-match without audible limiting**

Set output gain and limiter so the narration reaches:

```text
Integrated loudness: -16.0 LUFS, tolerance ±0.5 LU
Maximum true peak: -1.5 dBTP
Maximum limiter gain reduction: 3 dB
```

If meeting the loudness target requires more than 3 dB limiter reduction,
reduce upstream compression/output gain and remeasure rather than applying
hard limiting.

- [ ] **Step 3: Listen for processing artifacts**

Audition-check these regions:

```text
quietest retained sentence
loudest retained sentence
strongest sibilant phrase
every noise-profile transition
first edit in each section
last edit before each protected hold
```

Reject processing that introduces pumping, metallic tails, lisping, clipped
breaths, or audible room-tone gates.

- [ ] **Step 4: Mix down the complete session in Audition**

Using **Multitrack → Mixdown Session to New File → Entire Session**, create a
new waveform. Convert the mixdown to:

```text
Sample rate: 48000 Hz
Channels: Mono
Bit depth: 24-bit
Dither: disabled because source and output are both 24-bit
```

- [ ] **Step 5: Save the master to a new path**

Using **File → Save As**, save:

```text
/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_master_v1.wav
```

Select uncompressed PCM WAV, 24-bit integer, 48 kHz, mono. Do not overwrite an
existing destination; increment the version instead if the path exists.

- [ ] **Step 6: Confirm Audition can reopen the master**

Close only the rendered waveform, reopen `training_examples_master_v1.wav`, and
call `audition_get_document`.

Expected:

```text
type=WaveDocument
sample_rate=48000
duration_samples=34080000
```

The target sample count is 710 seconds × 48,000 samples/second.

---

### Task 7: Independently Verify the Master

**Interfaces:**

- Consumes: rendered master, session, EDL, script, and immutable checksum file.
- Produces: final metadata, loudness, silence, transcript, and acceptance
  evidence.

- [ ] **Step 1: Verify immutable sources again**

Run:

```bash
shasum -a 256 -c \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/source_checksums.sha256"
```

Expected: both immutable source files report `OK`.

- [ ] **Step 2: Verify master format and duration**

Run:

```bash
ffprobe -v error -show_format -show_streams -of json \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_master_v1.wav" \
  > "/Users/digotetsomatema/Desktop/audio/training_examples_production/master_ffprobe.json"
```

Expected:

```text
codec_name=pcm_s24le
sample_rate=48000
channels=1
bits_per_sample=24
duration=710.000000 ± 0.001
```

- [ ] **Step 3: Verify final loudness and true peak**

Run:

```bash
ffmpeg -hide_banner -nostats \
  -i "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_master_v1.wav" \
  -filter_complex ebur128=peak=true \
  -f null - \
  2> "/Users/digotetsomatema/Desktop/audio/training_examples_production/master_loudness.txt"
```

Expected:

```text
Integrated loudness: -16.0 LUFS ±0.5 LU
True peak: <= -1.5 dBTP
```

- [ ] **Step 4: Verify silence and waveform statistics**

Run:

```bash
ffmpeg -hide_banner -nostats \
  -i "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_master_v1.wav" \
  -af silencedetect=noise=-45dB:d=0.35 \
  -f null - \
  2> "/Users/digotetsomatema/Desktop/audio/training_examples_production/master_silence.txt"
```

Run:

```bash
ffmpeg -hide_banner -nostats \
  -i "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_master_v1.wav" \
  -af astats=metadata=1:reset=0 \
  -f null - \
  2> "/Users/digotetsomatema/Desktop/audio/training_examples_production/master_astats.txt"
```

Expected: detected long holds correspond to protected ranges or section
spacing; there are no unexplained long silences inside narration.

- [ ] **Step 5: Retranscribe the final master locally**

Run:

```bash
whisper \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_master_v1.wav" \
  --model turbo \
  --device cpu \
  --language en \
  --task transcribe \
  --word_timestamps True \
  --fp16 False \
  --condition_on_previous_text True \
  --hallucination_silence_threshold 2 \
  --initial_prompt "large language model, LLM, training_examples.py, shifted_targets.py, input, target, Python, The opposite of hot is cold" \
  --output_format json \
  --output_dir "/Users/digotetsomatema/Desktop/audio/training_examples_production"
```

Rename the generated JSON:

```bash
mv \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_master_v1.json" \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/master_transcription.json"
```

Expected: the transcript contains the complete intended source-led narration in
order. Treat
Whisper mismatches as listening-review prompts, not automatic proof of an audio
error.

- [ ] **Step 6: Perform the final full-duration listening pass**

Listen in Audition from `00:00.000` through `11:50.000` with the script and EDL
open. Verify:

```text
all intended source-led narration present exactly once
no false starts or repeated takes
no unclear discarded speech
section starts aligned to markers
prediction and code-demonstration time preserved
no clicks, abrupt ambience changes, or cut consonants
no pumping, metallic denoising, or harsh limiting
clean start and natural final tail
```

Do not declare completion if any item fails.

---

### Task 8: Complete the Audit Log and Delivery Gate

**Interfaces:**

- Consumes: every artifact and verification result from Tasks 1-7.
- Produces: `training_examples_edit_log.md` and the final delivery summary.

- [ ] **Step 1: Create the audit log**

Use this exact structure:

```markdown
# Training Examples Narration Edit Log

## Source Identity
## Script Identity
## Audition Environment
## Deliverables
## Section Timing
## Retained Takes
## Removed Material
## Protected Holds and Room Tone
## Processing and Settings
## Source Measurements
## Master Measurements
## Completeness Verification
## Audition Reopen Verification
## Pickup Risks
## Residual Risks
```

Populate every section with concrete paths, hashes, timecodes, values, and
results. Write `None` only when a category was explicitly checked and no item
was found.

- [ ] **Step 2: Verify the deliverable set**

Run:

```bash
ls -lh \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_edit_v1.sesx" \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_master_v1.wav" \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_edit_log.md" \
  "/Users/digotetsomatema/Desktop/audio/training_examples_production/training_examples_transcript.txt"
```

Expected: all four required deliverables exist and are non-empty.

- [ ] **Step 3: Run the final acceptance checklist**

Confirm all eleven acceptance criteria from
`docs/superpowers/specs/2026-07-26-training-examples-audio-edit-design.md`
against fresh evidence. Report any failed criterion as a blocker or residual
risk; do not weaken the criterion.

- [ ] **Step 4: Report the delivery**

The handoff must state:

```text
what changed
where the session, master, transcript, and audit log are located
source immutability result
master format, duration, loudness, and true peak
how completeness and timing were verified
pickup or residual risks
recommended next production step
```

Do not claim that the full soundtrack is mixed; this deliverable is the
production narration master only.
