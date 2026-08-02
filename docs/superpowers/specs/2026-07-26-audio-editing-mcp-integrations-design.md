# Audio Editing MCP Integrations Design

**Date:** 2026-07-26  
**Status:** Approved for implementation planning  
**Owners:** Repository maintainer and Codex

## Problem

The repository needs local Model Context Protocol integrations for two desktop
audio editors:

1. Audacity, where a maintained community MCP server already exposes broad
   editing capabilities through Audacity 3.x `mod-script-pipe`.
2. Adobe Audition, where no maintained public Audition-specific MCP server was
   verified and a narrow local bridge must be built on Adobe CEP and
   ExtendScript.

Both integrations must be usable from Codex and Claude Desktop. Desktop audio
applications are privileged automation boundaries: they can modify projects,
read or write media, and trigger application commands. The design therefore
prioritizes local-only communication, explicit allowlists, path confinement,
structured schemas, and confirmation before destructive actions.

## Goals

- Provide reproducible, pinned setup for the maintained upstream Audacity MCP.
- Provide Codex and Claude Desktop configuration examples for both editors.
- Build a local Adobe Audition MCP server and companion CEP extension.
- Support and verify the first release on the repository host's macOS
  environment.
- Support Audition status and document inspection, transport, playhead and
  selection control, import/open, save/export, and explicitly allowlisted
  effects.
- Reject arbitrary scripts, arbitrary application command identifiers, remote
  connections, and paths outside configured media roots.
- Require explicit confirmation for operations that overwrite, record, save,
  export, or apply an effect.
- Make the security and protocol logic fully testable without either desktop
  application installed.
- Provide diagnostic commands and manual smoke-test runbooks for the real
  application boundaries.

## Non-Goals

- Reimplementing the upstream Audacity tool surface.
- Supporting Audacity 4 beta before its scripting interface is stable and the
  selected upstream MCP declares compatibility.
- Remote MCP or browser access to either audio editor.
- Exposing raw ExtendScript, `eval`, shell execution, arbitrary command IDs, or
  arbitrary plugin loading.
- Installing third-party audio plugins.
- Adding denoising, source separation, transcription, or other ML audio
  processing to the custom Audition bridge.
- Claiming compatibility with Adobe Audition versions not covered by a
  completed manual smoke test.
- Claiming Windows or Linux support before platform-specific installation and
  smoke tests exist.
- Adding audio dependencies to the `matgpt-training` Python distribution.

## Decision

Use a hybrid integration:

- Audacity uses the upstream `audacity-mcp==0.1.8` package in an isolated
  integration environment. A version change requires a new review and smoke
  test before the pin moves.
- Adobe Audition uses a repository-owned Python MCP server over stdio and a
  repository-owned CEP extension that communicates with the server over an
  authenticated loopback protocol.

This avoids duplicating the mature Audacity surface while keeping the
unproven Audition automation layer small enough to review and test.

## Repository Boundaries

All integration code and documentation lives under:

```text
integrations/audio-mcp/
├── README.md
├── pyproject.toml
├── configs/
│   ├── codex.example.toml
│   └── claude-desktop.example.json
├── src/audio_mcp/
│   ├── __init__.py
│   ├── audition/
│   │   ├── __init__.py
│   │   ├── bridge.py
│   │   ├── config.py
│   │   ├── policy.py
│   │   ├── protocol.py
│   │   └── server.py
│   └── doctor.py
├── audition-cep/
│   ├── CSXS/manifest.xml
│   ├── index.html
│   ├── js/
│   │   ├── CSInterface.js
│   │   └── main.js
│   └── jsx/
│       ├── host.jsx
│       └── json2.js
├── scripts/
│   ├── install-audacity-mcp.sh
│   └── install-audition-cep.sh
├── tests/
│   ├── test_bridge.py
│   ├── test_doctor.py
│   ├── test_mcp_server.py
│   ├── test_policy.py
│   └── test_protocol.py
└── docs/
    ├── audition-smoke-test.md
    ├── audacity-smoke-test.md
    └── security.md
```

The integration has its own Python project so its MCP and test dependencies do
not affect the model-training package or root lockfile.

## Architecture

### Audacity

```text
Codex or Claude Desktop
        │ MCP stdio
        ▼
Pinned upstream audacity-mcp process
        │ local named pipe
        ▼
Audacity 3.x mod-script-pipe
```

The repository supplies:

- an installation script that creates or updates a dedicated virtual
  environment under `integrations/audio-mcp/.venv-audacity`;
- the exact `audacity-mcp==0.1.8` release pin;
- client configuration templates using an absolute executable path;
- a diagnostic command that checks the executable, Audacity version where
  discoverable, expected pipe endpoints, and whether the server can start;
- a smoke-test runbook that avoids modifying valuable projects.

The setup does not expose `mod-script-pipe` over a network and does not modify
the root Python environment.

### Adobe Audition

```text
Codex or Claude Desktop
        │ MCP stdio
        ▼
Python Audition MCP server
        │ authenticated WebSocket on 127.0.0.1
        ▼
Audition CEP extension
        │ CSInterface.evalScript with fixed function names
        ▼
Allowlisted ExtendScript host functions
        │
        ▼
Adobe Audition
```

The Python process is the policy enforcement point. It validates the MCP tool
input before creating a bridge request. The CEP extension accepts only the
fixed protocol operations defined in this specification and maps them to
fixed ExtendScript host functions. Neither side accepts script text or
application command IDs from MCP callers.

The WebSocket listener:

- binds only to `127.0.0.1`;
- accepts one active CEP connection;
- requires an installation-generated, high-entropy bearer secret;
- rejects missing, malformed, or incorrect tokens before processing requests;
- applies bounded request and response sizes;
- uses a request identifier, operation name, arguments object, and deadline;
- times out requests and discards late responses;
- never writes protocol data to MCP stdout.

The secret is supplied to both processes through a user-owned configuration
file with owner-only permissions. It is never committed, printed, or included
in error details. Client configuration templates reference the configuration
file rather than containing the secret.

Only one MCP host controls Audition at a time. Codex and Claude Desktop are
both supported and tested independently, but running both Audition MCP
processes concurrently is rejected because the bridge port and CEP connection
have a single owner.

## Audition Tool Surface

The initial MCP server exposes these tools:

| Tool | Purpose | Side effect | Confirmation |
| `audition_get_status` | Report bridge, application, document, and transport status | No | No |
| `audition_get_document` | Report active document/session metadata | No | No |
| `audition_get_selection` | Report playhead and active time selection | No | No |
| `audition_set_playhead` | Move the playhead to a validated time | Yes | No |
| `audition_set_selection` | Set a validated start/end time range | Yes | No |
| `audition_play` | Start playback | Yes | No |
| `audition_pause` | Pause playback | Yes | No |
| `audition_stop` | Stop playback or recording | Yes | No |
| `audition_record` | Begin recording | Yes | Yes |
| `audition_open` | Open an existing supported media or session file | Yes | Yes |
| `audition_import` | Import supported media into the active context | Yes | Yes |
| `audition_save` | Save the active document or session | Yes | Yes |
| `audition_export` | Export through a named export preset to a new path | Yes | Yes |
| `audition_list_effects` | Return the bridge's fixed effect allowlist | No | No |
| `audition_apply_effect` | Apply an allowlisted effect preset to the current selection | Yes | Yes |

`audition_open` and `audition_import` are confined to configured readable
media roots. `audition_export` is confined to configured writable media roots
and refuses an existing destination. Overwriting is outside the initial tool
surface. `audition_save` may update the already-open active document only
after confirmation; save-as behavior uses the same new-path protections as
export.

The initial effect allowlist contains only effect presets proven during the
manual Audition 26.3 validation. If no effect can be safely identified through
the installed Audition API, `audition_list_effects` returns an empty list and
`audition_apply_effect` returns a structured unsupported-operation error. The
bridge must not guess command identifiers or expose a bypass.

## Protocol

Messages use a versioned JSON envelope:

```json
{
  "protocol": "audio-mcp-audition/1",
  "request_id": "01J...",
  "operation": "get_status",
  "arguments": {},
  "deadline_ms": 5000
}
```

Success responses contain the same protocol and request identifier plus
`"ok": true` and a structured `"result"`. Failure responses contain
`"ok": false` and:

```json
{
  "error": {
    "code": "DOCUMENT_NOT_OPEN",
    "message": "No active Audition document is open.",
    "retryable": false
  }
}
```

Supported error families are:

- `INVALID_ARGUMENT`
- `UNAUTHORIZED`
- `BRIDGE_UNAVAILABLE`
- `BRIDGE_TIMEOUT`
- `APPLICATION_UNAVAILABLE`
- `DOCUMENT_NOT_OPEN`
- `PATH_NOT_ALLOWED`
- `DESTINATION_EXISTS`
- `CONFIRMATION_REQUIRED`
- `OPERATION_NOT_ALLOWED`
- `UNSUPPORTED_OPERATION`
- `APPLICATION_ERROR`
- `PROTOCOL_ERROR`

Errors must not disclose authentication tokens, full environment contents, or
paths outside configured media roots.

## Policy and Validation

### Path policy

- Resolve paths without requiring the destination to exist.
- Reject empty paths, NUL bytes, traversal outside a configured root, device
  files, and symlink escapes.
- Read operations require an existing regular file under a readable root.
- Write operations require an existing parent directory under a writable
  root.
- Initial exports and save-as operations reject an existing destination.
- Supported extensions are explicit and operation-specific.

### Confirmation policy

Confirmation is a literal boolean `confirm: true` in the same MCP tool call.
Strings, numbers, environment variables, or remembered approval are not
accepted. Confirmation is required for record, open, import, save, export, and
effect application. A confirmation covers only that single request.

### Command policy

- MCP arguments select a fixed operation, never an ExtendScript function.
- The CEP dispatcher maps each operation to one hard-coded host function.
- Effect selection uses a symbolic preset name from a fixed allowlist.
- Export selection uses a symbolic preset name from a fixed allowlist.
- Raw JSX, command IDs, menu names, shell commands, and plugin paths are not
  accepted anywhere in the protocol.

## Configuration

Both the Python server and CEP extension load one owner-only JSON
configuration file from the macOS user configuration directory:

- `~/Library/Application Support/audio-mcp/audition.json`

The file contains the high-entropy `secret`, `read_roots`, `write_roots`,
loopback `host`, and `port`. The default host is fixed to `127.0.0.1` and the
default port is `18765`. The server accepts `AUDIO_MCP_AUDITION_CONFIG` only as
an explicit alternative path; the CEP extension settings panel must be pointed
to the same file before that override can be used.

Empty root arrays disable the corresponding file operation. The server
refuses wildcard roots and filesystem roots such as `/`, a drive root, or a
user home directory.

The Codex and Claude Desktop examples launch the same project-local executable.
They contain placeholders only for absolute repository and media-root paths;
the README provides a validation command that fails if placeholders remain.

## Diagnostics

The `audio-mcp-doctor` command produces human-readable text by default and
machine-readable JSON with `--json`. It checks:

- supported Python version;
- integration environment and installed package versions;
- Codex and Claude configuration syntax;
- configuration-file existence, required fields, secret strength, and
  owner-only permissions;
- read/write root validity;
- loopback host enforcement and port availability;
- CEP extension installation path and manifest presence;
- Audacity executable/version when discoverable;
- Audacity script-pipe endpoint presence;
- Audition executable/version when discoverable;
- optional live bridge handshake without invoking an editing command.

Checks are classified as `pass`, `warning`, `fail`, or `skipped`. Diagnostics
must not print the authentication token.

## Failure Modes and Recovery

| Failure | Behavior | Recovery |
|---|---|---|
| Audacity is closed | Upstream tool reports pipe connection failure | Start Audacity and retry |
| `mod-script-pipe` disabled | Doctor reports missing pipe after Audacity startup | Enable module and restart Audacity |
| Audition is closed | CEP unavailable; MCP returns `BRIDGE_UNAVAILABLE` | Start Audition and open the CEP panel |
| CEP is installed but disconnected | MCP request times out without application action | Reopen panel and run doctor |
| Incorrect secret | Connection rejected and security warning logged without the secret value | Regenerate the local configuration secret |
| Path rejected | No bridge request is emitted | Correct configured roots or choose an allowed path |
| Operation times out | Request is marked failed; late response is discarded | Inspect application state before retrying |
| Export destination exists | Export is refused before reaching Audition | Choose a new destination |
| Effect unsupported | No application command is emitted | Use a validated allowlisted effect |
| Application closes mid-command | Structured retryability reflects whether replay is safe | Inspect state; do not automatically replay side effects |

The server does not automatically retry side-effecting operations. Read-only
status operations may be retried once after reconnect.

## Logging and Observability

- MCP stdout is reserved for protocol messages.
- Operational logs go to stderr as structured JSON.
- Each request has a request identifier and operation name.
- Logs include duration, outcome, error code, application version when known,
  and whether confirmation was required and present.
- Logs exclude tokens, audio contents, user prompts, and paths outside allowed
  roots.
- Allowed paths are logged relative to their configured root.

## Installation and Rollback

Installation scripts are idempotent and scoped:

- the Audacity script creates only the integration's dedicated environment;
- the Audition script copies the CEP extension only to the current user's Adobe
  CEP extension directory;
- the Audition script creates the user configuration file with an
  installation-generated secret and owner-only permissions when it is absent;
- neither script edits Codex or Claude configuration automatically;
- both scripts support a dry-run mode;
- existing destinations are backed up before an extension update.

Rollback consists of:

- removing the two client configuration entries;
- moving the installed Audition CEP extension to a timestamped backup or the
  operating system trash;
- deleting only the dedicated Audacity virtual environment after resolving its
  exact repository-local path.

No rollback step removes projects, media, Adobe preferences, or Audacity
preferences.

## Testing Strategy

### Automated tests

The narrowest tests run from the integration project and cover:

- protocol envelope validation and response correlation;
- rejection of incorrect, missing, and leaked authentication values;
- single-client connection enforcement;
- operation and effect allowlists;
- confirmation gates for every destructive tool;
- read/write root containment, traversal, NUL, symlink, device, extension, and
  existing-destination cases;
- timeout and late-response handling;
- MCP initialization and exact tool discovery;
- translation of MCP arguments into fixed bridge operations;
- structured error mapping with secret redaction;
- doctor classification and JSON output;
- Codex TOML and Claude Desktop JSON example syntax.

Tests use an in-process fake CEP peer. They do not mock policy decisions or
assert implementation-private calls.

### Manual smoke tests

Audacity smoke testing uses a disposable generated audio clip and verifies:

1. doctor detects Audacity 3.x and its script pipe;
2. both clients discover the upstream server;
3. status, import, selection, and a non-destructive analysis command work;
4. the disposable project can be saved to a new path;
5. Audacity 4 beta is rejected as unsupported.

Audition 26.3 smoke testing uses a disposable generated audio clip and verifies:

1. doctor detects the application and authenticated CEP handshake;
2. both clients discover the custom tools;
3. application/document status returns structured metadata;
4. play, pause, stop, playhead, and selection work;
5. import succeeds only from the configured read root;
6. export to a new file under the write root succeeds with confirmation;
7. one verified allowlisted effect succeeds with confirmation, or effect tools
   explicitly report unsupported if the installed API exposes no safe mapping;
8. traversal, overwrite, missing confirmation, and arbitrary operation probes
   fail without reaching the application.

## Acceptance Criteria

The work is accepted when:

- the isolated integration project installs without changing the root package;
- the pinned Audacity MCP starts from both configuration examples;
- the Audition MCP completes MCP initialization and exposes exactly the
  documented tool surface;
- all automated integration tests pass;
- security tests prove raw script and arbitrary command execution are absent;
- doctor emits valid text and JSON reports without exposing secrets;
- installation and rollback instructions are complete and non-destructive;
- the Audacity manual smoke test passes against Audacity 3.7.8;
- the Audition manual smoke test records the tested Audition version and
  passes all applicable steps against Audition 26.3;
- any unavailable safe effect mapping is reported as a documented limitation,
  not bypassed.

## Residual Risks

- Audition's public automation documentation and community type definitions
  lag the current desktop release. Manual API validation may reduce the initial
  effect or export preset allowlist.
- CEP lifecycle and compatibility can change between Audition releases.
- Audacity `mod-script-pipe` is an experimental, privileged local interface;
  using the upstream MCP inherits its application-level behavior and risks.
- Automated tests can validate the security boundary and bridge protocol but
  cannot prove the behavior of proprietary desktop application APIs.

These risks are contained by version recording, manual smoke tests, fixed
allowlists, local-only communication, and refusing unsupported operations.
