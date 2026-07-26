# Local audio-editor MCP integrations

This isolated project connects MCP clients to Audacity and Adobe Audition
without changing the repository's model-training environment. The Audacity
integration uses the reviewed upstream `audacity-mcp==0.1.8` release. The
Audition integration is documented separately while its bounded local bridge
is being implemented.

## Audacity prerequisites

- macOS
- Python 3.11 and `uv`
- Audacity 3.x (verified locally with 3.7.8.0)
- one controlling MCP client at a time

Audacity 4 is not supported by the pinned server. Read
[docs/security.md](docs/security.md) before enabling `mod-script-pipe`.

## Install and diagnose

Run these commands from the repository root:

```bash
cd integrations/audio-mcp
scripts/install-audacity-mcp.sh --dry-run
scripts/install-audacity-mcp.sh
uv run audio-mcp-doctor --json
```

The dry run prints the only two installation commands. The real installation
creates or updates only `.venv-audacity` and verifies the installed package
version. It does not edit Codex, Claude Desktop, Audacity, or Adobe settings.

In Audacity, open **Audacity → Settings/Preferences → Modules**, set
**mod-script-pipe** to **Enabled**, quit Audacity completely, and reopen it.
Run the doctor again; all four Audacity checks should pass.

## Configure one MCP client

Choose one of these templates:

- Codex: `configs/codex.example.toml`
- Claude Desktop: `configs/claude-desktop.example.json`

Replace the one `__ABSOLUTE_REPOSITORY_ROOT__` sentinel with the output of
`git rev-parse --show-toplevel`. Merge only the `audacity` entry into the
selected client's existing configuration; do not replace the entire config.
Restart that client after saving.

Do not run the Audacity server from Codex and Claude Desktop simultaneously.
The local script pipe supports one controlling process reliably.

Complete [docs/audacity-smoke-test.md](docs/audacity-smoke-test.md) with a
disposable project before using valuable media.

## Troubleshooting

- `audacity.script_pipe` fails: confirm the module is enabled, then fully
  restart Audacity.
- Tool calls report a missing pipe: open Audacity and keep it running.
- The version check rejects Audacity 4: use a supported Audacity 3.x
  installation for this pinned integration.
- The MCP client cannot start the command: confirm the template contains an
  absolute path and rerun the installer.
- A command appears stuck: inspect Audacity for an open modal dialog before
  retrying. Do not automatically replay save, export, or edit operations.

## Rollback

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

Rollback does not remove projects, exported media, Audacity preferences,
`/tmp`, a home directory, or a workspace root.
