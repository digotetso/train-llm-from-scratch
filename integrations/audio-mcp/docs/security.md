# Audio MCP security boundaries

## Audacity

Enabling `mod-script-pipe` allows another process running as the same local
user to issue Audacity commands. Audacity itself warns that the module can
make the application vulnerable, and the upstream MCP exposes broad editor
control. Treat every connected MCP client as capable of changing the open
project.

Required operating constraints:

- Do not expose either Audacity pipe through a web server, socket relay, SSH
  forward, container port, or network share.
- Run the pinned MCP process only as the same-user local process that launched
  the MCP client.
- Connect only one MCP client at a time.
- Keep valuable projects closed during initial validation.
- Require explicit user intent before save, save-as, export, close, delete,
  destructive effects, or batch operations.
- Choose new output paths. The upstream server rejects an export path that
  already exists, but that does not replace operator review.
- Stop the MCP server and disable the module when remote control is not needed.

The repository pins `audacity-mcp==0.1.8` in a dedicated environment so an
unreviewed future release is not installed implicitly. On macOS and Linux,
the local `audio-mcp-audacity` launcher patches only response framing and
process-exit pipe cleanup: it ignores empty frames before a real response,
drains buffered lines through the terminating blank line, and replaces the
upstream unawaited async `atexit` callback with synchronous pipe closure. It
does not reduce the upstream package's broad 131-tool permissions. The
upstream package, its transitive dependencies, Audacity, and the MCP client
remain separate trust boundaries.

## Adobe Audition

The Audition integration has four trust boundaries:

```text
MCP client -> Python policy server -> authenticated 127.0.0.1 WebSocket
           -> CEP fixed dispatcher -> ExtendScript fixed host functions
```

The Python process is the policy boundary. It requires an owner-only config
file, a 64-character random token, exact `127.0.0.1` binding, one MCP host,
one authenticated CEP connection, a 64 KiB message limit, finite deadlines,
fixed request identifiers, and at most eight concurrent pending calls. The
token is sent only as the first local WebSocket frame and is never rendered
in the panel or written to operational logs.

The server validates the complete request before emitting a bridge message:

- literal JSON `confirm=true` is required for record, open, import, save,
  export, and favorite application;
- read paths must resolve to existing regular files inside configured read
  roots;
- export parents must resolve inside configured write roots;
- symlink escapes, traversal, device files, missing parents, wrong
  extensions, and existing destinations are rejected;
- effect favorite names and export preset names are exact allowlists;
- side-effecting requests are not retried automatically.

The CEP layer does not expose raw ExtendScript, a generic evaluation tool,
arbitrary command IDs, shell execution, Node.js, remote content, or
caller-selected functions. It maps 14 bridge operations to fixed
`AudioMcpHost` calls. The fifteenth MCP tool, effect-list discovery, is
answered locally from the configuration.

Residual risks:

- A malicious process already running as the same user can read user-owned
  files and may obtain the token. Loopback authentication is not a sandbox.
- CEP is a legacy extension runtime. Enabling `PlayerDebugMode` permits
  unsigned CEP extensions for that CSXS generation, not only this extension.
  Enable it only for testing and reverse it afterward when possible.
- Save intentionally modifies the active document after confirmation. Export
  never overwrites, but save-in-place cannot provide that guarantee.
- An allowlisted Audition favorite can still make destructive audio changes.
  Validate on disposable media and keep the initial allowlist empty if unsure.
- Installed Audition DOM behavior varies by release. Missing or unproven APIs
  return `UNSUPPORTED_OPERATION`; bypassing that response is outside the
  security model.
- Audition opens and exports by pathname, not by a file descriptor supplied
  by the policy process. The policy resolves paths and the host rechecks
  export nonexistence immediately before `saveAs`, but a malicious same-user
  process can still race a filesystem path between validation and the
  application call. Do not run the bridge alongside untrusted local
  processes.

## Sensitive data

Audio contents, project paths, transcripts, and metadata may be sensitive.
Do not paste them into prompts or logs unnecessarily. Keep MCP client logging
at the minimum needed for diagnosis, and review the client's data-handling
policy before opening private recordings.

## Incident response

If either editor performs an unexpected action:

1. Stop the controlling MCP client.
2. Preserve the open project state without blindly saving over the original.
3. Use the editor's undo history or a known-good project/session copy.
4. Disable `mod-script-pipe` for Audacity or close the Audition CEP panel.
5. Record the tool name, arguments, client, package version, and observed
   result without including private audio or credentials.
