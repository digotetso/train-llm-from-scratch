# Reusable Figma to After Effects Exporter Design

**Status:** Approved in conversation on 2026-07-23

**Initial release:** `figma-ae-exporter` 1.0.0

**Initial platform:** macOS, Figma Desktop, After Effects 25.2 or newer, and
Node.js 20 or newer

## Problem

The existing exporter safely transfers the prepared Video 001 Figma lesson into
After Effects, but project identity, Figma source, timing, naming, queue paths,
build outputs, and release names are hard-coded to that lesson. Reusing it for a
new lesson would require code edits, another development-plugin installation,
and another separately maintained release.

The motion designer needs one installed, private Figma plugin and one After
Effects palette that can switch between validated lesson profiles without
rebuilding or reinstalling runtime code. Adding a lesson must be a data and
validation task, not an exporter fork.

## Users and Job to Be Done

The primary user is a motion designer working in prepared Figma lesson files and
After Effects projects on the same Mac.

Their job is to install a project profile once, select that profile in Figma,
send prepared frames to After Effects, and receive immutable, versioned,
editable compositions without risking existing project items or animation.

A secondary user is the engineer or course producer who creates, reviews, and
packages project profiles and exporter releases.

## Success

The release is successful when:

1. One installed Figma plugin switches between at least two installed project
   profiles without rebuilding or reinstalling.
2. Video 001 remains compatible and produces the same 48 shot compositions and
   master-composition naming.
3. A second fixture profile proves that frame count, dimensions, frame rate,
   timing, source identity, and naming are profile-driven.
4. Invalid profiles and mismatched packages fail before After Effects project
   mutation.
5. The portable private release can be rebuilt, installed with a recipient's
   Figma development-plugin ID, and independently verified from a clean
   extraction.

## Goals

1. Replace Video 001 runtime constants with a strict project-profile contract.
2. Keep one generic Figma plugin, local bridge, and After Effects palette.
3. Install project profiles once through the After Effects palette.
4. Expose installed profiles to Figma only after authenticated local pairing.
5. Preserve immutable versioning, duplicate detection, transactional rollback,
   Unicode fidelity, paragraph geometry, native layers, and declared raster
   fallbacks.
6. Provide a CLI wizard and validator for `.figma-ae-project.json` files.
7. Package a deterministic, machine-independent private release with a
   checksum, verifier, documentation, licenses, and Video 001 compatibility.

## Non-Goals

- Publishing a Figma Community plugin or organization-wide hosted plugin.
- Supporting Windows in the 1.0.0 release.
- Loading executable code, filesystem paths, URLs, or bridge permissions from a
  project profile.
- Updating an existing After Effects layer while preserving its keyframes.
- Automatically migrating animation from `_v001` to `_v002`.
- Automatically importing mutable state from the legacy Video 001 queue.
- Recreating every Figma effect natively when a declared lossless raster
  fallback is safer.
- Building a graphical profile-authoring wizard in Figma.
- Hosting profiles, packages, authentication, or telemetry in a cloud service.

## Architectural Decision

Use one runtime plugin backed by a local immutable project-profile registry.
The After Effects palette is the profile-installation authority. The paired
Figma plugin lists installed profiles from the bridge and never owns a separate
profile copy.

```text
figma-ae profile init
          |
          v
<project>.figma-ae-project.json
          |
          v
After Effects: Install project profile...
          |
          v
Validated immutable local profile registry
          |
          +----------------------+
          |                      |
          v                      v
Authenticated profile list   AE package validation
          |
          v
One installed Figma plugin
          |
          v
Hashed .figma-ae.json package
          |
          v
Authenticated loopback bridge and project queue
          |
          v
Transactional AE import into immutable _v### comps
```

### Alternatives Considered

1. **Runtime project-profile registry — selected.** This is the only approach
   that provides one installed plugin, one profile authority, safe switching,
   and no per-project rebuild.
2. **Self-contained export packages.** Rejected because Figma and After Effects
   would own separate profile copies and After Effects would have to trust any
   structurally valid profile embedded by a package.
3. **Build-time project profiles.** Rejected because every project would require
   another branded build and plugin installation.

## Components and Ownership

### Generic Figma Plugin

The plugin:

- pairs with the loopback bridge;
- requests installed profile summaries after authentication;
- lets the user select one profile;
- requests that profile's validated public export projection;
- verifies the open Figma file and page against that profile;
- resolves selected frames or the complete ordered timeline;
- serializes supported nodes and declared raster fallbacks;
- computes the canonical package hash;
- sends the package to the bridge or downloads the same package manually.

The summary contains project ID, display name, revision, hash, source page name,
and target dimensions/frame rate. The selected profile projection contains the
remaining source, naming, timeline, font-policy, and limit data needed for
export. Neither response contains registry paths or mutable bridge state.

The plugin does not install profiles, persist profile bodies independently, or
accept profile-supplied executable behavior. The selected projection exists
only in plugin memory and is refreshed when the bridge reports a registry
change.

Figma client storage may remember only the selected project ID, profile
revision, profile hash, and bridge token. A missing or changed profile forces a
new selection.

### Local Bridge

The bridge remains bound to `127.0.0.1` and owns:

- pairing and bearer-token validation;
- authenticated profile discovery;
- profile-registry reads;
- generic package-schema validation;
- exact installed-profile reference validation;
- project-namespaced queue, quarantine, asset, and log paths;
- request and asset limits;
- atomic package publication and redacted reporting.

The bridge must not accept a profile body from a Figma export request. It accepts
only an exact installed profile reference and validates the package against the
registry copy.

### After Effects Palette and Importer

The palette:

- starts and stops the bridge;
- resets pairing;
- installs a profile through **Install project profile...**;
- lists installed profiles and their immutable revisions;
- shows project-scoped queue counts and reports;
- imports the next package or a manually downloaded package.

Profile parsing, hashing, and registry mutation are implemented by the bundled
Node CLI so that the Figma plugin, bridge, CLI, and release tests share one
TypeScript validation contract. The ExtendScript palette invokes only bounded,
quoted CLI operations and displays their redacted result.

The importer:

- resolves the exact installed profile reference;
- validates the package and assets before `app.beginUndoGroup`;
- creates new items under the profile's configured import folder;
- creates the next safe `_v###` comp names;
- creates a versioned master composition when the package represents the
  profile's complete timeline;
- removes only items created by a failed attempt;
- never closes, replaces, or saves the user's After Effects project.

### Profile CLI

The portable release provides:

```text
figma-ae profile init
figma-ae profile validate <file>
figma-ae profile inspect <file>
figma-ae profile install <file>
figma-ae profile list
```

`profile init` is an interactive terminal wizard that creates a safe starter
profile. It accepts explicit project identity, Figma source, target canvas,
frame rate, naming, and timeline input. It does not query Figma or invent frame
IDs and timings.

`validate` and `inspect` never mutate registry state. `install` writes only
after complete validation and collision checks.

### Deterministic Release Builder and Verifier

The release builder captures an explicit source and built-runtime allowlist,
rejects secrets and mutable user paths, normalizes POSIX archive metadata, and
produces:

```text
figma-ae-exporter-1.0.0.tar.gz
figma-ae-exporter-1.0.0.sha256
```

The independent verifier checks the checksum, gzip header, archive structure,
file allowlist, modes, timestamps, ownership, padding, version agreement,
secret exclusions, and a clean deterministic rebuild.

## Project-Profile Contract

The file suffix is `.figma-ae-project.json`. The 1.0.0 contract contains these
top-level keys and rejects unknown keys:

```json
{
  "schemaVersion": "1.0.0",
  "project": {
    "id": "video-001",
    "displayName": "Video 001 - What AI Models Actually Do",
    "revision": 1
  },
  "source": {
    "fileKey": "fFTux3sx2AzVQtoya67f95",
    "pageId": "90:2",
    "pageName": "02 Video 001 - AE Assets"
  },
  "target": {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "timeUnit": "seconds"
  },
  "naming": {
    "shotPrefix": "S001",
    "masterCompBase": "VIDEO001_MASTER",
    "importFolder": "Video 001"
  },
  "timeline": {
    "sections": [],
    "shots": []
  },
  "fontPolicy": {
    "required": [],
    "fallbacks": []
  },
  "limits": {
    "maxFrames": 48,
    "maxAssets": 2048
  }
}
```

Each section declares a stable section ID, name, first shot, and last shot.
Each shot declares:

- one-based contiguous index;
- unique Figma node ID;
- safe deterministic composition base name;
- start time;
- positive duration;
- optional required section ID and section-parent node ID.

The complete timeline must be contiguous, ordered, and aligned to whole frames
at the configured frame rate. Profile schema 1.0.0 accepts only `seconds` as the
time unit.

### Global Ceilings

Profiles may choose lower project-specific limits but cannot exceed:

- profile file size: 1 MiB;
- installed immutable profile files: 256;
- project ID: 3-64 lowercase slug characters;
- display, folder, section, and composition names: 1-120 UTF-8 characters;
- target width and height: integer 16-16384 pixels;
- target frame rate: integer 1-120 fps;
- timeline: 1-256 frames and at most six hours;
- each shot: at least one frame;
- required font entries: 256;
- font fallback entries: 512;
- assets per package: 2,048;
- decoded bytes per asset: 32 MiB;
- aggregate decoded asset bytes: 512 MiB;
- manifest JSON: 32 MiB;
- complete bridge request: 768 MiB;
- JSON container depth: 64;
- bridge request time: 120 seconds.

All numeric products and total frame counts must be finite safe integers where
the contract requires integral values.

`fontPolicy.required` contains family/style pairs that act as visual review
gates. `fontPolicy.fallbacks` contains explicit source family/style to approved
fallback family/style mappings. Per-glyph fallback remains a runtime capability
and is always reported.

Profiles may not contain:

- filesystem paths;
- URLs or network origins;
- shell commands or script source;
- bridge ports or authentication settings;
- output filenames outside naming fields;
- encoded binary assets;
- control characters or unsafe path segments.

### Profile Identity and Immutability

The installer canonicalizes the validated profile and computes SHA-256 over the
entire canonical value. The profile does not contain its own hash.

Registry identity is the tuple:

```text
project.id + project.revision + profileSha256
```

The same project ID and revision may be installed repeatedly only when the hash
matches. A different hash at the same revision is rejected. Profile changes
require the next positive revision.

## Registry and Filesystem Layout

Mutable runtime state lives only under:

```text
~/Library/Application Support/FigmaAEExporter/
```

The logical layout is:

```text
profiles/<project-id>/<revision>/<profile-sha256>.figma-ae-project.json
projects/<project-id>/incoming/
projects/<project-id>/quarantine/
projects/<project-id>/assets/
projects/<project-id>/logs/
tmp/
auth/
```

Project IDs use lowercase ASCII letters, digits, and single internal hyphens,
with a bounded length. They are validated before path construction. Every path
is derived by trusted code, resolved under the fixed root, checked for symlinks,
and created with restrictive permissions.

Profile installation writes a private temporary file, fsyncs it, verifies its
identity and bytes, and atomically renames it into a previously absent final
path. Registry indexes are derived from immutable files rather than treated as
an independent source of truth.

## Generic Export-Package Contract

New packages use `.figma-ae.json` and schema major version 3. The package
contains:

- schema and exporter versions;
- export timestamp and canonical content hash;
- exact `projectId`, `profileRevision`, and `profileSha256`;
- Figma file and page identity;
- target dimensions, frame rate, and time unit;
- ordered frames and nodes;
- content-addressed asset descriptors;
- structured warnings.

The package does not embed a project profile. The bridge and AE importer resolve
the installed immutable profile and validate:

- source file and page;
- frame node IDs, names, order, timing, and section ancestry;
- target canvas and frame rate;
- profile-specific count limits;
- generic global request and asset limits;
- canonical package fingerprint and every asset hash.

Queue filenames are `<contentHash>.figma-ae.json` and are stored only in the
referenced project's queue.

## Runtime Data Flow

### Profile Creation and Installation

1. The producer runs `figma-ae profile init`.
2. The producer edits the generated JSON when timeline details require explicit
   review.
3. `figma-ae profile validate` reports all validation errors without mutation.
4. In AE, the user selects **Install project profile...** and chooses the file.
5. The palette invokes the bundled CLI installer.
6. The installer validates, hashes, collision-checks, and atomically stores the
   immutable profile.
7. The palette refreshes its profile list.

### Pair, Select, Build, and Send

1. The AE palette starts the bridge and displays a short-lived pairing code.
2. The Figma plugin pairs and requests installed profile metadata.
3. The user selects a profile.
4. The plugin verifies the current Figma file and page.
5. The user builds selected prepared frames or the complete profile timeline.
6. The plugin serializes and hashes a package referencing the exact profile.
7. The bridge authenticates the request, resolves the profile, validates all
   data and assets, and atomically publishes the package to the project queue.

### Import

1. AE displays a queue count scoped to the selected project.
2. The user selects **Import next**.
3. The importer resolves and revalidates the exact installed profile.
4. Duplicate content returns `DUPLICATE_CONTENT` without mutation.
5. A new import creates versioned shot comps and, for a full timeline, a
   versioned master comp.
6. The queue package is consumed only after the import report is complete.
7. A failure rolls back only the new items and quarantines the package with a
   redacted report.

### Manual Fallback

Figma may download the same `.figma-ae.json` package. **Import package...** in
AE accepts it only when the exact profile is installed. Manual packages include
inline content-addressed assets and receive the same canonical fingerprint and
profile validation as queued packages.

## Versioning and Duplicate Behavior

Composition versioning remains immutable:

```text
<shot-comp-base>_v001
<shot-comp-base>_v002
...
<master-comp-base>_v001
<master-comp-base>_v002
```

Version detection matches only the exact configured base plus `_v###`, stops at
`_v999`, and never renames existing items.

New project comments use a generic machine-readable marker containing project
ID, profile hash, and content hash. The importer recognizes the legacy
`Video001Export sha256:<hash>` marker for Video 001 duplicate detection.

## Security and Privacy

- The bridge remains loopback-only and unauthenticated requests receive no
  profile metadata.
- Pairing codes are one-time and short-lived; bearer tokens remain random,
  expiring, revocable, and excluded from logs.
- Profile data is untrusted until exact schema and semantic validation pass.
- Profile responses expose only the data needed to validate the open Figma
  document and build configured frames.
- Profiles cannot expand global payload, asset, timeout, or permission ceilings.
- Package and registry writes are atomic and constrained to fixed application
  data roots.
- Filenames derive only from validated project IDs, revisions, and hashes.
- Logs and errors exclude bearer tokens, pairing codes, source payloads, asset
  data, stack traces, and direct user paths.
- Release scanning rejects credentials, private keys, mutable user paths, live
  registry state, logs, evidence captures, and AEP files.
- No remote telemetry or cloud service is added.

## Error Handling and Recovery

### Profile Errors

- Invalid profile: reject with field path and stable error code; no registry
  mutation.
- Revision collision: retain the installed profile and require the next
  revision.
- Missing or corrupt installed profile: hide it from Figma, report it in AE, and
  leave the file untouched for forensic recovery.
- Source mismatch: disable export and identify the expected file and page.

### Transfer Errors

- Unauthorized or expired pairing: clear Figma auth state and require pairing.
- Missing profile reference: reject before queue publication.
- Profile hash mismatch: reject and require profile refresh or installation.
- Duplicate queued content: return a stable conflict without replacing bytes.
- Oversized, invalid, or partial request: destroy temporary data and publish
  nothing.

### Import Errors

- Invalid package or asset: fail before the undo group.
- Mutation failure: remove only newly created items.
- Duplicate content: create nothing.
- Missing font or declared raster fallback: complete with an explicit visual
  review warning when policy allows it.
- Queue failure after a valid import: retain a redacted report and do not repeat
  project mutation automatically.

## Migration and Compatibility

Video 001 becomes a bundled ordinary profile with its existing Figma source,
48-shot timeline, dimensions, frame rate, naming, font policy, and limits.

A compatibility adapter accepts legacy `.video001-ae.json` packages after the
Video 001 profile is installed. It maps the legacy source and timing contract to
the exact bundled profile and rejects any mismatch. It does not make legacy
schema rules available to other profiles.

The migration preserves:

- Video 001 shot and master comp names;
- immutable `_v###` behavior;
- legacy duplicate markers;
- Unicode and mixed-style text behavior;
- glyph-level font fallback;
- raster-fallback and warning reports;
- transactional rollback.

The new installer does not automatically read or delete the legacy
`Video001FigmaAEExporter` application-data root. A documented manual drain path
handles any package that must be retained. Existing AEPs and generated comps
remain ordinary project items and require no conversion.

## Portable Private Packaging

The 1.0.0 archive is machine-independent. It includes:

- generic source code;
- built generic Figma controller and UI;
- built bridge and profile CLI;
- built AE palette and audits;
- profile JSON schema;
- Video 001 profile;
- a second fixture profile;
- package lockfile and pinned build tools;
- README, installation, operation, migration, and troubleshooting docs;
- tests;
- Apache license, notice, and provenance;
- deterministic release builder and independent verifier.

It excludes:

- `.figma-plugin-id`;
- recipient-specific Figma manifests;
- bearer tokens and pairing state;
- installed profile registry files;
- queues, logs, quarantine data, and temporary files;
- AEP files and rendered media;
- live evidence captures;
- user-specific paths and credentials.

After extraction, the recipient runs the documented setup command with their own
Figma development-plugin ID. Setup generates the local Figma manifest and
verifies the installed Node, generated files, and generic runtime versions. A
recipient-specific manifest is not part of the deterministic archive.

## Observability

Project-scoped redacted reports include:

- project ID, profile revision, and profile hash;
- package content hash;
- queue and import status;
- created comp names and layer counts;
- native and raster layer counts;
- missing fonts and applied fallbacks;
- warnings and stable error codes;
- elapsed time.

Logs rotate at the existing bounded size and retain the existing bounded
retention period. Profile install/list events record only project identity,
revision, hash, result, and elapsed time.

## Testing Strategy

### Unit Tests

- profile schema exact-key validation;
- canonical profile hashing;
- safe project IDs and path derivation;
- revision collision and idempotent reinstall;
- source, target, timeline, section, naming, font-policy, and limit validation;
- generic package profile references;
- generic version names and duplicate markers;
- legacy Video 001 adaptation;
- CLI parsing and non-mutating `validate` and `inspect`;
- release allowlists and secret scanning.

### Integration Tests

- atomic profile installation and derived registry listing;
- authenticated profile discovery;
- no profile data before authentication;
- two installed profiles visible after pairing;
- project-namespaced queues, assets, quarantine, and logs;
- package rejection for missing, stale, or mismatched profiles;
- queue idempotency and conflict handling;
- manual and bridge package equivalence;
- recipient-specific manifest generation;
- deterministic archive build and independent verification.

### After Effects Host Runtime Tests

- import a full Video 001 package through the bundled profile;
- import a second profile with different dimensions, frame rate, duration,
  frame count, and naming;
- switch profiles without restarting or rebuilding the exporter;
- create `_v001` and `_v002` without modifying `_v001`;
- detect unchanged and explicitly duplicated content;
- roll back a deliberately failed import;
- preserve Unicode, mixed-style runs, paragraph boxes, and per-glyph fallback;
- recognize a legacy Video 001 package and duplicate marker;
- prove the importer never closes or saves the user's project.

### Real-Host Smoke Tests

Run Figma Desktop and After Effects smoke tests for both Video 001 and the second
fixture profile. Record:

- selected profile;
- source file/page match;
- package hash;
- queue acceptance;
- imported comp names;
- dimensions, frame rate, and duration;
- font and raster warnings;
- project mutation boundaries.

### Release Tests

From a clean extraction:

1. verify archive checksum and structure;
2. install pinned dependencies;
3. supply a fresh local Figma development-plugin ID;
4. generate the recipient manifest;
5. build generic runtime outputs;
6. run unit, integration, type, AE-host, and release tests;
7. rebuild the deterministic archive and compare bytes.

## Acceptance Criteria

1. Given two valid installed profiles, when the paired Figma plugin requests
   profiles, it lists both without a rebuild or reinstall.
2. Given an open Figma document matching Profile A, when Profile B is selected,
   export remains disabled with a source-mismatch error.
3. Given a valid new profile, when AE installs it, the registry contains one
   immutable canonical file and Figma can discover it after pairing.
4. Given different bytes for an installed project ID and revision, when
   installation is attempted, the installer rejects the collision and preserves
   the original file.
5. Given a package with a missing or mismatched profile reference, when the
   bridge or AE importer validates it, no queue or project mutation occurs.
6. Given a changed export, when it is imported, the next `_v###` comps are
   created and all previous versions remain unchanged.
7. Given unchanged content, when **Import next** is selected, the importer
   returns `DUPLICATE_CONTENT` and creates nothing.
8. Given a complete Video 001 export, when it is imported through the generic
   runtime, it creates the same 48 shot comps and `VIDEO001_MASTER_v###`
   structure.
9. Given the second fixture profile, when it is exported and imported, its own
   dimensions, frame rate, timing, frame count, names, and queue namespace are
   used without Video 001 constants.
10. Given a legacy Video 001 package and installed Video 001 profile, when it is
    manually imported, the compatibility adapter validates and imports it
    without weakening generic package validation.
11. Given a clean release extraction and recipient plugin ID, when setup and
    verification run, they complete without access to the original machine's
    paths, credentials, registry, or plugin ID.
12. Generic runtime source contains no Video 001 identity, dimensions, timing,
    naming, queue root, or package suffix outside the explicit compatibility
    adapter and bundled profile.

## Delivery Slices

1. **Profile contract and CLI:** shared schema, hashing, safe registry paths,
   `init`, `validate`, `inspect`, `install`, and tests.
2. **Generic bridge and registry API:** authenticated discovery and
   project-namespaced state.
3. **Generic Figma plugin:** profile selection, source enforcement, profile
   reference, and generic package suffix.
4. **Generic AE palette/importer:** profile installation, selection, validation,
   naming, timeline, and reports.
5. **Video 001 migration:** bundled profile, legacy adapter, and structural
   equivalence tests.
6. **Second profile proof:** automated fixtures and real-host smoke evidence.
7. **Portable release:** setup, docs, deterministic archive, checksum, and
   independent clean-extraction verification.

Each slice is independently testable and retains the existing Video 001
exporter until the migration slice passes.

## Rollout and Rollback

The generic exporter is installed alongside the legacy exporter during
validation. Video 001 first runs through both paths against fresh disposable AE
projects, and their structural audits are compared. The generic exporter
becomes the documented path only after Video 001 equivalence and second-profile
smoke tests pass.

Rollback consists of stopping the generic bridge, removing its Figma
development-plugin registration and AE palette, and returning to the legacy
Video 001 exporter. The generic profile registry and generated comps are not
deleted automatically. No production AEP or render is replaced during rollout
or rollback.

## Risks and Mitigations

- **Profile flexibility weakens safety.** Mitigation: exact keys, semantic
  validation, immutable hashes, global ceilings, no executable fields, and
  installed-profile matching at every boundary.
- **Figma and AE use different profile versions.** Mitigation: the bridge owns
  discovery and every package references an exact immutable hash.
- **Project IDs become filesystem input.** Mitigation: strict slug syntax,
  trusted path construction, containment checks, no symlinks, and atomic writes.
- **Genericization regresses Video 001 fidelity.** Mitigation: bundled profile,
  legacy adapter, existing runtime fixtures, structural equivalence, and
  real-host comparison.
- **Recipient-specific plugin IDs break deterministic packaging.** Mitigation:
  exclude the generated manifest and local ID from the archive; generate and
  verify them during recipient setup.
- **Profile authoring is error-prone.** Mitigation: CLI wizard, full field-path
  validation, non-mutating inspection, and a documented Video 001 example.
- **Old and new mutable roots create confusion.** Mitigation: distinct generic
  root, no automatic deletion, explicit migration documentation, and
  project-scoped status in the AE palette.
