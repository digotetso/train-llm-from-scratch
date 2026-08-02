# Video 001 After Effects Motion Design

Date: 2026-07-22

Status: Approved for production

## Purpose

Translate the 48 approved Figma storyboard frames on page `02 Video 001 - AE Assets`
into a native, editable After Effects project and timed 14-minute silent lesson.

## Delivery Contract

- Master composition: `S001_MASTER_What_AI_Models_Actually_Do`
- Format: 1920x1080, square pixels, 30 fps, 840 seconds
- Shot comps: exactly 48, preserving the Figma `S001_SH##_...` names and order
- Timing source: the eight Figma handoff sections and shot map
- Project source: native AE text and shape layers; no required flattened artwork
- Review: H.264 MP4, 1920x1080, 30 fps, no audio
- Master: Apple ProRes 422 HQ MOV, 1920x1080, 30 fps, 10-bit 4:2:2

## Visual Contract

- Background `#0B1020`; panel `#11182D`; primary `#F5F7FB`; secondary `#A8B3CF`
- Fixed data `#35C7FF`; adjustable model `#8B5CF6`; warning/loss `#F59E0B`; progress `#22C55E`
- Sora for display/headings, Inter for body, and JetBrains Mono for code where available
- Preserve functional prefixes: `BG_`, `TXT_`, `CODE_`, `DATA_`, `MODEL_`, `LOSS_`,
  `PROG_`, `FX_`, `MATTE_`, `GUIDE_`, and `CTRL_`
- Keep critical text within the 120 px title-safe area and retain the Figma 12-column rhythm
- Pair semantic color with labels, geometry, or stable screen position

## Motion Language

- Base transition: 12 frames
- Stagger: 60 ms reference, clamped so dense diagrams settle quickly
- Travel: no more than 24 px
- Entry scale: 96% to 100%; focal overshoot may reach 102% before settling
- Entry/exit opacity: 0% to 100% / 100% to 0%
- Ease: restrained cubic-style temporal easing; no elastic bounce or fake 3D
- Shot changes: outgoing units clear over the final 12 frames; the persistent navy master
  background prevents flashes between non-overlapping timed shots
- Recurring pipeline positions remain stable from text through numbers, prediction, error,
  and parameter update

## Timeline

| Section | Range | Shots |
|---|---:|---:|
| Hook | 00:00-00:45 | 01-04 |
| Direct explanation | 00:45-02:00 | 05-09 |
| Technical meaning | 02:00-04:00 | 10-17 |
| Tiny example | 04:00-06:00 | 18-25 |
| Repository walkthrough | 06:00-09:00 | 26-32 |
| Live mini-lab | 09:00-12:00 | 33-39 |
| Common mistake | 12:00-13:00 | 40-43 |
| Recap and exercise | 13:00-14:00 | 44-48 |

## Editability And Project Hygiene

- Use `01_Comps`, `02_Precomps`, `03_Footage`, `04_Audio`, `05_Exports`, and
  `99_References` bins.
- Every shot comp includes a `CTRL_ShotMotion` null and disabled title-safe guide.
- The master includes section and shot markers plus `CTRL_Master`.
- Imported Figma reference renders, if used for QA, stay disabled in `99_References` and
  are not a render dependency.
- Save the project beside its build manifest and automation script so the build can be
  reproduced.

## Verification

- Validate the manifest before opening AE: unique shot names, exact Figma node IDs,
  contiguous shot starts, 840-second total, semantic layer names, and safe bounds.
- Inspect representative hook, technical, repository, lab, and recap frames in AE.
- Verify the saved project contains 48 shot comps and the 14-minute master.
- Probe both outputs for codec, profile, dimensions, frame rate, duration, and audio state.

## Residual Risk

Without final narration, shot-level reading time follows the approved Figma handoff rather
than sentence-level voice timing. A later audio conform should move shot boundaries only;
the native comp structure and motion units are designed to remain reusable.
