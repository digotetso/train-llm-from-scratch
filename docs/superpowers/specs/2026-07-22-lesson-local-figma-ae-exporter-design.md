# Lesson-Local Figma to After Effects Exporter Design

**Status:** Approved in conversation on 2026-07-22

**License foundation:** Apache License 2.0 code from AEUX, with required notices retained

**Initial scope:** Video 001, “What AI Models Actually Do”

## Problem

The lesson has 48 prepared Figma shots and a working native After Effects build, but it does not have a reliable direct-export workflow for future Figma revisions. DISKO Beam completed a transfer in After Effects 25.2.2 but corrupted UTF-8 characters, changed paragraph wrapping, shipped an invalid Figma plugin ID, and exposed an unauthenticated local bridge. AEUX is legally reusable under Apache 2.0, but its archived Vue 2/CEP interface renders blank in the same After Effects environment.

The first release must provide a private, project-local exporter for this lesson. It must move a selected Figma shot into After Effects as editable, semantically named layers without overwriting existing animation work.

## Users and Job to Be Done

The primary user is the lesson’s motion designer. They select a prepared 16:9 lesson frame in Figma and send it to After Effects, where a new versioned comp is ready for animation. They must be able to trust text fidelity, layer structure, and safe re-export behavior without rebuilding the frame manually.

## Goals

1. Export selected lesson frames directly from current Figma Desktop to After Effects 2025.
2. Preserve UTF-8 text, paragraph geometry, semantic names, native shapes, transforms, and supported hierarchy.
3. Create a new versioned comp for every distinct re-export and never modify existing comps.
4. Use a secured, local-only bridge with a manual file fallback.
5. Reuse the repository’s tested native AE layer-building behavior where it matches the exporter schema.
6. Prove fidelity on Shot 32 before validating representative shots and then all 48 lesson shots.

## Non-Goals

- Publishing a general-purpose Figma Community plugin in the first release.
- Supporting arbitrary Figma documents outside the Video 001 handoff.
- Updating an existing AE layer while preserving its keyframes.
- Replacing the existing animated Video 001 project or delivered renders.
- Recreating unsupported Figma effects natively when a lossless raster fallback is safer.
- Reusing or redistributing DISKO Beam source code.
- Supporting Windows or After Effects versions earlier than 25.2 in the first release.

## Architectural Decision

Build a lean exporter using AEUX’s Apache-licensed concepts and the repository’s proven AE construction patterns. Do not restore AEUX’s obsolete Vue/CEP UI. The runtime path is:

```text
Selected Figma lesson frame
        |
        v
Current Figma development plugin
        |
        v
Versioned UTF-8 manifest + hashed raster assets
        |
        +---- manual download fallback
        |
        v
Authenticated 127.0.0.1 Node bridge
        |
        v
Atomic local queue
        |
        v
After Effects ScriptUI/ExtendScript importer
        |
        v
S001_SH##_Name_v001, then _v002, _v003, ...
```

The exporter lives at `course/videos/001-computer-learning-from-text/after-effects/exporter/`. Runtime code has no third-party Node dependencies. Development uses TypeScript and a pinned bundler, while the bridge uses only Node standard-library modules on Node 20 or newer. The AE importer remains ES3-compatible ExtendScript. The verified host targets are Figma Desktop 126.6.14 and After Effects 25.2.2 on macOS.

### Alternatives Considered

1. **Repair AEUX in place.** Rejected because its Vue 2, old WebSocket dependencies, CEP packaging, and blank AE 2025 panel create unnecessary compatibility and supply-chain risk.
2. **File-only export.** Retained as a fallback but rejected as the primary flow because it is not a clean direct exporter.
3. **DISKO Beam fork.** Rejected because its current EULA does not grant the modification and redistribution rights required for a maintained fork.

## Component Boundaries

### Figma Plugin

The plugin accepts one or more selected lesson frames. It traverses supported nodes, normalizes values into the shared schema, exports unsupported visuals as lossless PNG assets, and either sends the package to the paired bridge or downloads it as a file. It uses a valid Figma-assigned development plugin ID and the current manifest fields required by Figma.

### Shared Manifest Schema

The JSON schema is the stable boundary between Figma and AE. Every package contains:

- schema version;
- exporter version;
- Figma file key, page ID, frame node ID, and frame name;
- export timestamp and content hash;
- source width and height;
- target width, height, frame rate, and duration;
- ordered nodes with semantic names, hierarchy, geometry, transforms, opacity, and type-specific properties;
- hashed asset descriptors for raster fallbacks;
- structured warnings for unsupported or substituted properties.

Unknown required fields, unknown schema major versions, invalid numbers, unsafe names, and out-of-bounds asset references are rejected before import.

### Local Bridge

The bridge binds only to `127.0.0.1`. Pairing begins in the AE panel, which shows a short-lived one-time code. Figma exchanges that code for a random bearer token and stores the token in Figma client storage. Every subsequent request requires the token.

The bridge validates content type, schema version, frame count, payload size, asset count, and asset size. One request may contain at most 48 frames, 2,048 assets, 32 MiB of manifest JSON excluding encoded assets, 32 MiB per decoded asset, 512 MiB of decoded assets in aggregate, and 768 MiB in the complete HTTP body. Requests time out after 120 seconds. It generates filenames from SHA-256 content hashes, never from Figma-controlled paths. It writes packages to a temporary queue path and atomically renames them only after validation completes. Logs exclude credentials and embedded asset data.

### AE Importer

The ScriptUI panel starts and stops the bridge, manages pairing, watches the queue, offers manual import, and displays results. The importer creates all new items under `01_Exporter_Imports/<frame-name>/v###`. It determines the next available three-digit version by inspecting project items and creates a new comp without modifying earlier versions.

If import fails, it removes only the incomplete new items created by that transaction. It never closes, replaces, or saves over an unrelated project.

## Fidelity Rules

1. Geometry remains in Figma frame coordinates. AE applies one explicit source-to-target scale factor.
2. The default target is 1920×1080 at 30 fps. Duration comes from the matching Video 001 shot manifest.
3. Text is UTF-8 and includes its exact box width, height, alignment, line height, letter spacing, font family/style, opacity, and mixed-style runs.
4. Paragraph text boxes are not widened. Wrapping is checked against the Figma reference render.
5. Rectangles, ellipses, solid fills, and supported strokes become editable AE shape layers.
6. Supported groups and components become nested precomps and retain semantic Figma names.
7. Images, gradients, complex vectors, masks, and unsupported effects use lossless PNG fallback at the configured target scale.
8. Missing fonts and unsupported properties are reported visibly and never silently discarded.
9. A repeated manifest with the same content hash is idempotent and does not create another comp unless the user explicitly chooses “Import duplicate.”
10. A changed export creates the next available version, such as `_v002`, and leaves `_v001` unchanged.

## Security and Privacy

- The bridge is loopback-only and has no remote service dependency.
- Pairing codes expire after five minutes and can be used once.
- Bearer tokens contain at least 128 bits of randomness and are never logged.
- Bearer tokens expire after 30 days without a successful request and can be revoked immediately with “Reset pairing.”
- Requests use an explicit JSON media type and a bounded body size.
- Frame count, asset count, individual asset size, and aggregate asset size have configured limits.
- Asset paths are content-addressed and constrained to the exporter queue directory.
- Queue writes are atomic.
- Invalid packages are moved to quarantine with a redacted error report.
- The panel provides a visible “Stop bridge” control and stops its child bridge process when AE exits normally.
- Successfully imported queue packages are deleted after the import report is written. Quarantined packages and redacted logs are retained for seven days, with logs rotating at 10 MiB.

## Error Handling and Recovery

- If the bridge is unavailable or pairing fails, the plugin offers the same package as a manual download.
- Invalid manifests fail before AE project mutation.
- Missing fonts create a warning and use an explicit configured fallback; the report names every affected layer.
- Unsupported Figma properties use raster fallback when available; otherwise the import fails with the exact node ID and property.
- A failed AE transaction removes only items created during that transaction.
- Existing lesson comps and the existing animated AEP remain untouched in every failure mode.
- Import reports include created comp names, layer counts, native/raster counts, missing fonts, fallbacks, warnings, content hash, and elapsed time.

## Acceptance Criteria

### Milestone 1: Shot 32 Proof

Given Figma node `95:44`, `S001_SH32_Repo_PreparationNotLearning`, when it is sent to a fresh AE 25.2.2 project:

1. The exporter creates `S001_SH32_Repo_PreparationNotLearning_v001` at 1920×1080, 30 fps, using the shot duration from `figma-scenes.json`.
2. `θ`, `·`, arrows, and all other source characters match the Figma strings exactly.
3. The title wraps to the same line count as the Figma reference.
4. Supported text and simple shapes remain editable.
5. Layer names and nested precomp names remain semantic and deterministic.
6. No prior project item is modified or deleted.
7. Sending an unchanged package again reports a duplicate and creates no new comp.
8. Sending changed content creates `_v002` while `_v001` remains byte-for-byte unchanged at the property-audit level.

The exporter does not proceed to the full lesson if Shot 32 fails Unicode, wrapping, geometry, or non-destructive versioning.

### Milestone 2: Representative Fixtures

Representative simple, nested, rotated, mixed-style, image-heavy, and raster-fallback frames pass structural audits and visual comparison. Authentication, expired pairing codes, oversized payloads, path traversal attempts, invalid schemas, partial queue writes, missing fonts, and interrupted imports produce the documented safe failures.

### Milestone 3: Full Lesson

All 48 prepared lesson shots export to a fresh AE project as versioned comps. Each comp has the expected dimensions, frame rate, duration, semantic layer names, supported native layer types, and a complete import report. The existing animated project is not opened or mutated during this validation.

## Testing Strategy

### Unit Tests

Use deterministic fixtures to test schema parsing, UTF-8 preservation, coordinate scaling, version naming, path safety, pairing, token validation, payload limits, content hashing, duplicate detection, and report generation.

### Integration Tests

Run real packages through the Node bridge and verify authenticated transfer, atomic queue output, quarantine behavior, hashed assets, redacted logs, and manual-file equivalence.

### After Effects Audits

Run ExtendScript audit scripts against generated comps and record dimensions, frame rate, duration, layer types, names, fonts, source text, text box sizes, transforms, hierarchy, and project mutation boundaries.

### Visual Regression

Render representative AE frames and compare them with Figma reference screenshots using image metrics plus manual inspection. Metrics are diagnostic; text wrapping, missing content, clipping, and semantic correctness remain explicit pass/fail checks.

## Release and Rollback

The project-local release contains the Figma development plugin, shared schema, bridge, AE ScriptUI panel, Apache 2.0 license and AEUX attribution, installation guide, test fixtures, audit scripts, and troubleshooting instructions.

The exporter is installed alongside the existing lesson assets and does not replace the current AEP or renders. Rollback consists of stopping the bridge, removing the development plugin registration and ScriptUI panel, and deleting only the exporter’s local queue/config directory. Generated versioned comps remain ordinary AE project items and are never deleted automatically.

## Risks and Mitigations

- **AE text metrics differ from Figma.** Preserve exact paragraph boxes, use installed PostScript font names, audit line count, and rasterize only when fidelity cannot be achieved natively.
- **ExtendScript has an older JavaScript runtime.** Keep the importer ES3-compatible and move schema/security work into the tested Node bridge.
- **Figma API changes.** Isolate traversal behind adapter functions and version fixtures by source node type.
- **Local bridge abuse.** Require pairing and bearer authentication, enforce strict limits, bind to loopback, and never trust client paths.
- **Large raster payloads.** Enforce aggregate limits, stream assets to temporary files, hash incrementally, and fail before AE mutation.
- **License contamination.** Reuse only Apache-licensed AEUX material with notices; do not copy DISKO Beam implementation code.
