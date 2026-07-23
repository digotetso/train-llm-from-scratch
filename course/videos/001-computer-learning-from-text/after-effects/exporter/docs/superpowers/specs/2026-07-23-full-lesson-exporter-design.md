# Full-Lesson Figma-to-After-Effects Exporter Design

## Goal

Turn the approved Video 001 exporter into a production-ready, direct full-lesson workflow: one Figma action builds the 48 prepared lesson frames in canonical order, the local bridge transfers the package, and After Effects creates editable shot compositions plus one 14-minute master timeline.

## Approved Product Direction

The exporter remains a native layered workflow. Supported Figma text, shapes, groups, frames, components, and instances become editable After Effects layers and precompositions. Unsupported appearance is rasterized only at the smallest faithful subtree and remains explicitly reported.

The workflow does not require Creative Cloud, Adobe Media Encoder, a hosted service, or a third-party exporter. It uses the installed Figma desktop application, the installed After Effects application, and the loopback-only local bridge already implemented in this repository.

## Scope

### Figma

- Keep the current selected-frame export path.
- Add a separate `Build full lesson` action.
- Resolve the 48 approved frame IDs from the embedded canonical timing configuration without changing the user's Figma selection or document.
- Validate file key, page ID, section ancestry, node identity, node name, frame dimensions, and exact config order before serialization.
- Produce schema `2.0.0` with `target.timeUnit: "seconds"`, 48 frames, a total duration of 840 seconds, and content-addressed raster assets.
- Preserve current generation cancellation, SHA-256 hashing, download, pairing, and authenticated send behavior.

### After Effects

- Preserve existing immutable per-shot versioning and transaction rollback.
- When and only when a package contains all 48 canonical lesson shots exactly once, create one immutable master composition:
  - 1920×1080
  - 30 fps
  - 840 seconds / 25,200 frames
  - one layer per imported shot comp
  - chronological in/out points from canonical shot starts and durations
- Keep single-shot and partial-selection imports unchanged; they do not create a master.
- Treat an unchanged full-package resend as `DUPLICATE_CONTENT` with no new project items.
- Reject missing, duplicated, reordered, mistimed, or noncanonical full-lesson inputs before mutating the project.

### Evidence and Release

- Add a read-only audit for all 48 shot comps and the master timeline.
- Validate root and recursive precomp duration fidelity, master-layer timing, native/raster counts, missing fonts, fallbacks, content hashes, and item-count stability.
- Capture only redacted evidence. Never retain pairing codes, authentication secrets, authorization headers, or mutable user paths.
- Build a reproducible source release archive with checksums and exact installation/use instructions for Figma desktop and After Effects.
- Validate the full workflow in a new `/private/tmp` AEP. The production lesson AEP must retain SHA-256 `ffbb3daa7b1cc225cdacc1ed4e490da083c85c9e3877162293993cd6306a3881`.

## Architecture

### Full-Lesson Node Resolution

`ControllerHost` gains an asynchronous node lookup boundary. The Figma adapter delegates to `figma.getNodeByIdAsync`. Tests provide an in-memory node map. The controller resolves configured shot IDs sequentially, validates each node through the same approved-frame rules as selection export, and sends progress-safe output through the existing package generation.

The selected-frame and full-lesson paths converge before serialization. This prevents two serializers, two package formats, or two security policies.

### Full-Lesson Master Assembly

The After Effects timing loader retains canonical `start` and `duration` values for each shot. After all 48 shot roots import successfully, the importer creates the master comp inside the same undo transaction. Each layer sources its imported root comp, starts at the approved timeline start, and ends at `start + duration`.

Master creation is conditional on an exact full-lesson set. Partial packages continue to produce only shot comps. Any failure rolls back every item created by the package, including the master.

### Release Boundary

Source remains authoritative. `npm run build` produces Figma, bridge, and AE runtime artifacts. A release script stages only documented files into a temporary owned directory, writes SHA-256 checksums, and creates a deterministic archive. No credential, live user-data directory, or `.aep` is included.

## Failure Modes

- Missing Figma node: fail with shot index and node ID before serialization.
- Wrong page/section/name/dimensions: fail with the exact source path; do not silently skip.
- Cancellation during 48-frame serialization: discard the stale generation and do not expose a package.
- Package/asset limit exceeded: preserve the current bounded validation error and manual recovery guidance.
- AE full-package mismatch: reject before the first project item is created.
- AE failure after creation begins: roll back only items created by that import, in reverse identity order.
- Audit detects mutation: fail and retain the temporary proof project for diagnosis.
- Release archive mismatch: fail before publishing the archive.

## Security and Privacy

- Bridge remains IPv4 loopback-only and authenticated.
- Pairing code remains one-time and short-lived; authentication material is never embedded in Figma packages or release artifacts.
- All filesystem targets remain fixed, validated, owner-controlled descendants.
- Full-lesson lookup can access only the 48 IDs embedded at build time.
- Evidence and logs are deny-listed for credentials and mutable user paths.

## Test Strategy

- Unit: full-lesson protocol validation, node resolution, exact order, cancellation, and failures.
- Contract: schema `2.0.0`, seconds, 48-frame and asset ceilings, canonical hashing.
- AE host: exact full-set detection, master comp geometry/timing, rollback, duplicate no-op, and partial-package behavior.
- Integration: bridge accepts a 48-frame package within production limits and publishes exactly one queue file.
- Live host: Figma desktop → bridge → isolated AE project → read-only 48-shot audit.
- Release: clean standalone clone, `npm ci`, 204+ tests, both typechecks, build, Python guards, evidence verifier, archive checksum verification, and `npm audit`.

## Acceptance Criteria

- A user can build and send all 48 approved frames without manually multi-selecting them.
- AE creates 48 editable root shot comps and one 840-second master timeline in a fresh temporary project.
- Every shot and recursive precomp has its approved duration in seconds and frames.
- Master layers cover the exact continuous range `[0, 840]` with no gaps or overlaps.
- Unchanged resend creates no project items.
- No unsupported Figma appearance is silently changed; fallbacks are explicit.
- All automated checks and clean-clone checks pass.
- The release archive is reproducible and contains source, built runtimes, docs, licenses/provenance, and checksums only.
- The user's production AEP and Figma source remain unchanged.

## Non-Goals

- Voice-over synchronization.
- Motion keyframing or final renders.
- Publishing to the Figma Community or an external marketplace.
- Installing Creative Cloud or Adobe Media Encoder.
- Mutating the user's production AEP during exporter validation.

Motion design, the editable final lesson AEP, H.264 review file, and ProRes 422 HQ master remain the immediately following production increment after this exporter release gate.
