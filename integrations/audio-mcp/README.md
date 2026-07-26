# Local audio-editor MCP integrations

This isolated project connects MCP clients to Audacity and Adobe Audition
without changing the repository's model-training environment. The Audacity
integration uses the reviewed upstream `audacity-mcp==0.1.8` release through
a local POSIX response-framing and shutdown wrapper. The Audition integration
is a safety-bounded Python MCP server plus a local CEP extension. Both support
Codex and Claude Desktop, one controlling client at a time.

Documentation and compatibility research baseline: 2026-07-26.

Read [docs/security.md](docs/security.md) before enabling either editor
integration.

## Audacity

### Prerequisites

- macOS
- Python 3.11 and `uv`
- Audacity 3.x (verified locally with 3.7.8.0)
- one controlling MCP client at a time

Audacity 4 is not supported by the pinned server.

### Install and diagnose

Run these commands from the repository root:

```bash
cd integrations/audio-mcp
scripts/install-audacity-mcp.sh --dry-run
scripts/install-audacity-mcp.sh
uv run audio-mcp-doctor --json
```

The dry run prints the scoped installation commands. The real installation
creates or updates only `.venv-audacity`, verifies the pinned upstream
package, and installs the local `audio-mcp-audacity` wrapper. The wrapper
prevents macOS/Linux pipe replies from shifting between MCP calls and closes
the pipes synchronously at process exit. It does not alter the upstream
131-tool surface. The installer does not edit Codex, Claude Desktop, Audacity,
or Adobe settings.

In Audacity, open **Audacity → Settings/Preferences → Modules**, set
**mod-script-pipe** to **Enabled**, quit Audacity completely, and reopen it.
Run the doctor again; all four Audacity checks should pass.

### Configure one MCP client

Choose one of these templates:

- Codex: `configs/codex.example.toml`
- Claude Desktop: `configs/claude-desktop.example.json`

For Audacity, replace the command's `__ABSOLUTE_REPOSITORY_ROOT__` sentinel
with the output of `git rev-parse --show-toplevel`. Merge only the `audacity`
entry into the selected client's existing configuration; do not replace the
entire config. Restart that client after saving.

Do not run the Audacity server from Codex and Claude Desktop simultaneously.
The local script pipe supports one controlling process reliably.

Complete [docs/audacity-smoke-test.md](docs/audacity-smoke-test.md) with a
disposable project before using valuable media.

### Audacity troubleshooting

- `audacity.script_pipe` fails: confirm the module is enabled, then fully
  restart Audacity.
- Tool calls report a missing pipe: open Audacity and keep it running.
- On Audacity 3.7.8, do not call `project_new` from the initial empty project;
  `New:` creates another project while scripting supports one project at a
  time and may not return a completion reply.
- A sample-data export can show an Audacity completion dialog. Dismiss it
  promptly; if the MCP call has already timed out but the new output exists,
  do not replay the export.
- The version check rejects Audacity 4: use a supported Audacity 3.x
  installation for this pinned integration.
- The MCP client cannot start the command: confirm the template contains an
  absolute path and rerun the installer.
- A command appears stuck: inspect Audacity for an open modal dialog before
  retrying. Do not automatically replay save, export, or edit operations.

### Audacity rollback

1. Remove only the `audacity` MCP server entry that you added to the selected
   client, then restart that client.
2. Resolve and inspect the integration directory:

   ```bash
   cd integrations/audio-mcp
   pwd -P
   ```

3. After confirming the printed directory ends in
   `integrations/audio-mcp`, move only its `.venv-audacity` directory to the
   Trash.
4. Optionally return `mod-script-pipe` to **Disabled** in Audacity and restart
   Audacity.

## Adobe Audition

### Compatibility and prerequisites

- macOS, Python 3.11+, `uv`, and Adobe CEP 9-compatible Audition
- local automated target: Adobe Audition 2020 version 13.0.2
- external acceptance target: Audition 26.3, still requiring the full smoke
  runbook on a machine with that release
- one Audition MCP server and one authenticated CEP panel at a time

The server binds only to `127.0.0.1`, uses an installation-generated token,
requires owner-only configuration, and exposes exactly 15 fixed tools. It
does not expose raw ExtendScript or arbitrary application command IDs.

### Preview and install user-scoped files

From the repository root:

```bash
integrations/audio-mcp/scripts/install-audition-cep.sh --dry-run
integrations/audio-mcp/scripts/install-audition-cep.sh
chmod 600 "$HOME/Library/Application Support/audio-mcp/audition.json"
uv run --project integrations/audio-mcp audio-mcp-doctor --json
```

The installer creates default read/write roots under `~/Music/AudioMCP`,
creates the config only when absent, and installs the extension under the
current user's Adobe CEP directory. An existing extension is moved to a
timestamped backup under
`~/Library/Application Support/audio-mcp/backups`, outside Adobe's scanned
extension directory. Existing config is preserved. The installer does not
enable CEP development mode or edit an MCP client.

### Explicit unsigned-extension setting

The development extension is unsigned. After reviewing the security
implications, the operator must explicitly run:

```bash
defaults write com.adobe.CSXS.9 PlayerDebugMode 1
```

Quit and reopen Audition, then open **Window → Extensions → Audio MCP**. The
panel must show `Configuration: loaded` and, while the MCP server is running,
`Bridge: authenticated`.

After testing, reverse the unsigned-extension setting with:

```bash
defaults delete com.adobe.CSXS.9 PlayerDebugMode
```

Neither command is executed by the installer.

### Configure one MCP client

Use the same templates listed in the Audacity section. For the `audition`
entry:

1. replace `__ABSOLUTE_REPOSITORY_ROOT__` with the absolute repository root;
2. replace `__USER_APPLICATION_SUPPORT__` with the absolute current-user
   `Library/Application Support` path;
3. merge only the `audition` entry and restart that client.

Run Codex and Claude Desktop discovery in separate sessions. A second
Audition MCP process cannot bind the same local port and cannot replace the
authenticated CEP connection.

The generated configuration starts with no effect favorites and one `wav`
export preset. Add a favorite only after verifying its exact Audition
favorite name; never add script text or a plugin path.

Complete [docs/audition-smoke-test.md](docs/audition-smoke-test.md) before
using valuable sessions or media.

### Audition troubleshooting

- Panel absent: confirm the extension path, CEP 9 development setting, and a
  full Audition restart.
- `Configuration: error`: run the doctor and correct the owner-only config;
  do not copy the token into logs or prompts.
- `Bridge: disconnected`: start only one configured Audition MCP server.
- `BRIDGE_TIMEOUT`: inspect Audition for a modal dialog and inspect document
  state before retrying; side effects are not automatically replayed.
- `UNSUPPORTED_OPERATION`: the installed Audition DOM did not expose the safe
  fixed capability. Do not bypass this with an arbitrary command or script.

### Audition rollback

1. Remove only the `audition` entry from each MCP client where it was added.
2. Quit Audition.
3. Move
   `~/Library/Application Support/Adobe/CEP/extensions/com.zx.audio-mcp-audition`
   to a timestamped backup under
   `~/Library/Application Support/audio-mcp/backups` or to the
   operating-system Trash.
4. Retain the owner-only configuration unless you explicitly choose to
   archive it.
5. To restore, move the newest known-good timestamped extension backup from
   `~/Library/Application Support/audio-mcp/backups` back to the exact
   extension path.
6. Reverse `PlayerDebugMode` with the command above if no other unsigned CEP
   development extensions require it.

Rollback never removes projects, exported media, editor preferences, `/tmp`,
a home directory, or a workspace root.
