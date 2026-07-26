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
unreviewed future release is not installed implicitly. The upstream package,
its transitive dependencies, Audacity, and the MCP client remain separate
trust boundaries.

## Sensitive data

Audio contents, project paths, transcripts, and metadata may be sensitive.
Do not paste them into prompts or logs unnecessarily. Keep MCP client logging
at the minimum needed for diagnosis, and review the client's data-handling
policy before opening private recordings.

## Incident response

If Audacity performs an unexpected action:

1. Stop the controlling MCP client.
2. Preserve the open project state without blindly saving over the original.
3. Use Audacity's undo history or a known-good project copy.
4. Disable `mod-script-pipe` and restart Audacity.
5. Record the tool name, arguments, client, package version, and observed
   result without including private audio or credentials.

The Audition bridge has a separate loopback authentication and path-policy
model; its controls and residual risks are documented in the Audition runbook.
