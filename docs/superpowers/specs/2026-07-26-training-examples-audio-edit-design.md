# Training Examples Narration Audio Edit Design

## Objective

Produce a professional, production-ready narration master for:

`course/video-1-training-example/script.md`

The edit must remove repeated takes, false starts, accidental dead air, and
unclear discarded material while retaining the recording's complete intended
teaching sequence. Intentional pauses required by the visual and animation
plan must remain synchronized to the script's reference production timeline.

## Source and Safety

The immutable source assets are:

- `/Users/digotetsomatema/Desktop/audio/training_examples.wav`
- `/Users/digotetsomatema/Desktop/audio/training_examples.pkf`

The WAV is a 48 kHz, 24-bit, mono PCM recording with a measured source duration
of 988.863896 seconds. The PKF is Audition peak-cache data, not an audio source.

Editing will be non-destructive. Neither source asset may be overwritten,
renamed, moved, or deleted. Work products will use new names under:

`/Users/digotetsomatema/Desktop/audio/training_examples_production/`

## Editorial Authority

`course/video-1-training-example/script.md` is the structural, teaching-flow,
and timing reference. Only recorded narration is spoken. Code blocks, terminal
output, headings, and visual directions remain silent.

### Source-led amendment approved 2026-07-26

The recorded narration is now the editorial wording authority. The production
script remains a structural, teaching-flow, and timing reference rather than
an exact transcript contract. Intentional recorded changes—including the
closing's two key points instead of three—must be retained when they are
complete, coherent, and consistent. False starts, repeated takes, unclear
abandoned material, and the incomplete restart after the finished sign-off
remain removable.

The completed narration must:

1. contain the recording's intended teaching sequence once, using the script
   as a structural and timing reference;
2. use the clearest complete recorded take available for each sentence;
3. remove false starts, repeated takes, abandoned words, coughs, handling
   noise, and accidental long gaps when removal does not damage speech;
4. preserve natural breaths and phrasing unless they distract or impair timing;
5. preserve the visual holds, prediction pauses, and demonstration time
   specified by the production script;
6. identify any source-led teaching idea without a usable complete take as a
   pickup rather than concealing the omission.

## Timing Contract

The edit will conform narration and intentional room-tone holds to these
section boundaries:

| Section | Start |
| --- | ---: |
| The AI We Are Going to Build | 00:00 |
| A Sentence You Can Finish | 01:00 |
| The Answer Is Already in the Sentence | 01:50 |
| Make One Example by Hand | 02:40 |
| One Sentence, Five Examples | 03:50 |
| Build the Examples in Python | 05:10 |
| The Same Sequence, Shifted One Place | 06:50 |
| Run, Observe, and Explain | 08:20 |
| Three Easy Mistakes | 10:10 |
| The Mental Model | 11:00 |

The target program end is approximately 11:50. Speech may move within a
section to sound natural, but it must not collide with explicitly timed learner
predictions, code demonstrations, or the following section.

## Editing Approach

Use a script-locked dialogue conform in Adobe Audition:

1. Analyze and transcribe the source locally with word-level timestamps.
2. Align recorded phrases to the authoritative narration.
3. Build a timecoded edit decision list that identifies the chosen take and
   removals for each script beat.
4. Create a non-destructive Audition multitrack session.
5. Assemble the selected takes in script order and place section boundaries on
   the production timeline.
6. Use clean room tone from the source for required visual holds; use short,
   natural crossfades at edits to avoid clicks.
7. Apply only processing justified by measured defects.
8. Render a new production master and verify it independently.

Automated silence deletion is not permitted as the primary edit method because
it can clip consonants, breaths, or intentional timing. Automation may identify
candidate regions, but every cut must be validated against the script and
adjacent audio.

## Audio Processing

Processing must remain conservative and speech-focused:

- preserve the source 48 kHz sample rate and 24-bit depth;
- remove DC offset or subsonic rumble only when measured;
- use corrective equalization, de-essing, compression, click repair, or noise
  reduction only when the source demonstrates the corresponding problem;
- avoid aggressive denoising, gating, or limiting that creates pumping,
  metallic artifacts, clipped breaths, or an unnaturally flat performance;
- use short equal-power crossfades and source room tone at assembly points;
- target a production-ready narration level near -16 LUFS integrated with
  maximum true peak at or below -1.5 dBTP, unless measurement shows that
  achieving it would require audibly damaging processing.

The audit log must record each applied process and its settings.

## Deliverables

The production directory will contain:

- `training_examples_edit_v1.sesx` — non-destructive Audition session;
- `training_examples_master_v1.wav` — 48 kHz, 24-bit, mono master;
- `training_examples_edit_log.md` — source identity, script identity,
  section timing, edit decisions, processing, measurements, verification, and
  pickup notes;
- `training_examples_transcript.txt` — timecoded local analysis transcript used
  for alignment.

Temporary analysis artifacts may be created outside the production directory
but are not deliverables.

## Verification and Acceptance Criteria

The edit is accepted only if:

1. source WAV and PKF checksums and metadata remain unchanged;
2. the master opens successfully and reports PCM 24-bit mono at 48 kHz;
3. every retained narration idea can be traced from source transcript to EDL
   and master;
4. no narration idea is unintentionally duplicated or out of order;
5. section starts match the timing contract within 100 milliseconds;
6. prediction and demonstration holds remain present where specified;
7. edit boundaries contain no audible clicks, clipped words, or abrupt
   room-tone changes;
8. no unintended leading or trailing material remains;
9. integrated loudness, true peak, duration, and silence analysis are recorded;
10. Audition can reopen the session and master;
11. any unresolved unclear line is explicitly recorded as a pickup risk.

## Failure Handling

If the source lacks a complete intelligible take for an intended source-led
teaching idea, the editor will preserve the best available take, mark its exact
output time, and recommend a pickup. Content will not be synthesized, silently
omitted, or assembled from phonemes without explicit approval.

If Audition cannot perform a required safe operation through the installed
integration, the work will stop before destructive action. A local analysis
tool may assist with transcription or measurement, but the editorial session,
assembly, and final render remain Audition work.

## Non-Goals

- Rewriting the approved narration.
- Reading code or visual directions aloud.
- Adding music, sound effects, ambience, or generated speech.
- Overwriting the original recording.
- Mixing the complete video soundtrack.
- Claiming compatibility with an untested Audition release.
