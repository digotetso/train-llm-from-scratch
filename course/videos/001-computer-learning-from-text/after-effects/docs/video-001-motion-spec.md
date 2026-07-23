# Video 001 After Effects Motion Specification

## Delivery contract

- One editable source-import project and one editable animated project.
- One 14-minute, 1920×1080, 30 fps animated master.
- 48 shot compositions in the approved Figma order and section timing.
- No voice-over is present; picture timing follows the approved Figma handoff.
- The original 48 imported shot comps and `VIDEO001_MASTER_v001` remain unchanged.

## Motion language

The lesson uses restrained, premium technical motion. The constant dark
background creates match cuts between shots; foreground information reveals in
reading order, then holds still.

- Base entry: 12 frames.
- Stagger: 60 ms per foreground layer.
- Maximum position travel: 24 px.
- Standard entry scale: 96% to 100%.
- Maximum scale overshoot: 102%; the implementation uses 101.5%.
- Easing: strong ease-out with Bézier temporal interpolation.
- Background layers do not animate.
- One dominant non-text graphic per shot may use the scale entry. Other
  foreground layers use opacity plus vertical travel.
- Reveal order follows the original Figma child order within each semantic
  tier. The first `DATA_`, `MODEL_`, `LOSS_`, `PROG_`, `CODE_`, or `FX_`
  non-text layer in that order is the deterministic hero; later candidates do
  not displace it based on precomp canvas size.
- No spins, wipes, elastic bounce, continuous floating, or decorative camera
  movement.

## Layer treatment

`BG_` and `ROOT_SOLID_BACKGROUND` layers remain fully visible from the first
frame. Eyebrows, titles, and decks enter first. The dominant diagram, code
panel, data rail, model, loss, progress, or focus graphic follows. Supporting
labels and details complete the reveal.

Every animation is applied only to a duplicated root shot comp named
`<source>_ANIM_v001`. Recursive precomps remain reusable and editable. The
animated master is `VIDEO001_ANIMATED_MASTER_v001`; it uses the exact canonical
start, in, and out points with no gaps or overlaps.

## Quality gates

- 48 animated shot comps and exactly one animated master.
- Master duration: 840 seconds / 25,200 frames.
- Source master and source shot keyframe fingerprints unchanged.
- Entry duration no longer than 12 frames.
- Per-layer stagger equals 60 ms.
- Position travel no greater than 24 px.
- Scale never below 96% of the base or above 102% of the base.
- No expressions, missing sources, timing gaps, timing overlaps, or `_v002`
  animation items.
- A read-only audit must pass before review or master rendering.
- Close and reopen the saved animated AEP before running the read-only audit,
  so the audit examines the persisted project rather than builder memory.
- The audit rejects a dirty project and requires the exact saved animated AEP
  to exist as a non-alias file.
- Every source shot must match the immutable SHA-256-pinned full-lesson audit:
  exporter content hash, canonical identity, native-node order, and raster
  node/hash inventory. The build report records that provenance per shot.
- Every source layer must also match the SHA-256-pinned raw Figma package:
  Source Text and text-box styling, vector geometry/fill/stroke, static
  transforms, recursive precomp identity, and raster file bytes.
- Each source shot receives a canonical visual SHA-256. Its animated duplicate
  must match the complete source property tree and source-item identities after
  normalizing only the approved opacity, position, and scale keyframes.
