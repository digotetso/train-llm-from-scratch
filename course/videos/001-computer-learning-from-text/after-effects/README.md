# Video 001 After Effects Delivery

This directory contains the editable 14-minute After Effects version of
“What AI Models Actually Do,” rebuilt as native text and shape layers from the 48-shot
Figma handoff.

## Deliverables

- `video-001-what-ai-models-actually-do.aep` — editable 48-shot AE project
- `exports/video-001-what-ai-models-actually-do-review.mp4` — H.264 review file
- `exports/video-001-what-ai-models-actually-do-prores-422-hq.mov` — ProRes 422 HQ master
- `delivery-verification.json` — hashes, codec facts, test evidence, and visual-QA samples

All media is 1920×1080, 30 fps, 840 seconds, silent, and tagged BT.709. Both media
files include a QuickTime timecode (`tmcd`) data track.

## Prerequisites

- Adobe After Effects 2025 (verified with 25.2.2)
- `ffmpeg` and `ffprobe`
- At least 4 GiB free on the temporary-media filesystem
- The bundled fonts installed for the current user:
  - Sora Bold and SemiBold
  - Inter Regular and Medium
  - JetBrains Mono Medium

Font files and their OFL licenses are under `fonts/`.

## Rebuild the AEP

1. Open After Effects with either a blank project or this generated AEP.
2. Run `build-video-001.jsx` through **File → Scripts → Run Script File**.
3. Run `fix-video-001-fonts.jsx` the same way.
4. Confirm `build-report.json` and `font-fix-report.json` both report `complete`.

The builder refuses to close an unrelated open project. It may close only its own generated
AEP before rebuilding it.

## Render Sections

From the repository root:

```bash
bash course/videos/001-computer-learning-from-text/after-effects/render-sections.sh
```

The script renders all eight Figma timing sections to `/private/tmp`, validates exact frame
counts, creates ProRes 422 HQ and H.264 derivatives, and removes each large AE source only
after both derivatives pass. It stops before rendering if less than 4 GiB is available.

The installed AE output-module templates did not include ProRes 422 HQ. The pipeline uses
AE’s 10-bit ProRes 422 “High Quality” output as a bounded intermediate, then encodes the
master derivatives with `prores_ks` profile 3 (`yuv422p10le`).

## Timing and Audio

Shot timings follow the eight Figma handoff sections, not sentence-level narration. No final
voice-over was supplied, so both delivered media files intentionally contain no audio stream.
A later narration conform should adjust shot boundaries without flattening the native shot comps.

## Troubleshooting

- **AE error 9988 during export:** check free space and clear AE’s recoverable disk cache if it
  has grown unexpectedly. Do not delete project or source files.
- **Missing or substituted fonts:** install the bundled static fonts, restart AE, and rerun
  `fix-video-001-fonts.jsx`. The expected result is 565 changed layers, 0 skipped, and an empty
  `missing` object.
- **Stale embedded manifest:** run `repair-figma-coordinate-conversion.mjs`, then rerun the AE
  test suite before rebuilding.

