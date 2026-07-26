# Adobe Audition MCP disposable-media smoke test

This runbook establishes compatibility only for the installed application
version. Passing on local Audition 13.0.2 does not establish compatibility
with Audition 26.3; repeat the complete runbook there before making that
claim.

Use disposable media and a disposable multitrack session. Close valuable
documents first. Every record, open, import, save, export, and favorite call
must carry literal `confirm=true` in the same tool request.

## Prerequisites

1. Run `audio-mcp-doctor --json` and retain its redacted result.
2. Confirm the CEP panel shows `Configuration: loaded`.
3. Start one configured MCP client and confirm the panel shows
   `Bridge: authenticated`.
4. Create a one-second disposable WAV and reserve unique output names with
   this command. It reads only the first configured roots and never prints the
   authentication value:

   ```bash
   python3 - <<'PY'
   import json
   import math
   import struct
   import uuid
   import wave
   from pathlib import Path

   config_path = (
       Path.home()
       / "Library"
       / "Application Support"
       / "audio-mcp"
       / "audition.json"
   )
   config = json.loads(config_path.read_text(encoding="utf-8"))
   read_root = Path(config["read_roots"][0])
   write_root = Path(config["write_roots"][0])
   identifier = uuid.uuid4().hex[:10]
   source = read_root / f"audio-mcp-smoke-{identifier}.wav"
   session = write_root / f"audio-mcp-smoke-{identifier}.sesx"
   export = write_root / f"audio-mcp-smoke-{identifier}.wav"
   sample_rate = 44_100
   with wave.open(str(source), "wb") as output:
       output.setnchannels(1)
       output.setsampwidth(2)
       output.setframerate(sample_rate)
       frames = (
           struct.pack(
               "<h",
               int(8_000 * math.sin(2 * math.pi * 440 * i / sample_rate)),
           )
           for i in range(sample_rate)
       )
       output.writeframes(b"".join(frames))
   print(f"Disposable source: {source}")
   print(f"New session path: {session}")
   print(f"New export path: {export}")
   PY
   ```

5. Keep the three printed paths for the ordered checks.

Do not use an existing destination. Do not use course audio, client media, or
another valuable project.

## Ordered functional checks

Record the structured result after every step.

1. In Codex, list MCP tools and confirm the exact 15 `audition_*` tools. End
   that MCP server before testing another client.
2. In Claude Desktop, separately list the same 15 tools. End it, then choose
   one client for the remaining test.
3. Call `audition_get_status`. Confirm the reported application version. With
   a disposable document open, call `audition_get_document`.
4. Call `audition_set_playhead`, `audition_play`, `audition_pause`, and
   `audition_stop`, visually verifying each transition.
5. Call `audition_set_selection`, then `audition_get_selection`. A documented
   `UNSUPPORTED_OPERATION` is acceptable if this installed DOM does not expose
   the fixed selection capability.
6. Call `audition_open` for the disposable WAV inside the read root with
   `confirm=true`.
7. Create an empty disposable multitrack session in Audition's UI at the new
   `.sesx` path. Call `audition_import` for the disposable WAV and a valid
   track index with `confirm=true`. Record success or the capability-backed
   `UNSUPPORTED_OPERATION`.
8. Call `audition_save` with `confirm=true` only for that disposable session.
9. Reopen the disposable WAV with `audition_open` and `confirm=true`. Call
   `audition_export` with preset `wav`, a new write-root path, and
   `confirm=true`. Confirm the output file exists and the source remains
   intact.
10. Call `audition_list_effects`. If the list is empty, record that safe
    result. If one exact favorite was independently validated, apply it only
    to the disposable WaveDocument with `audition_apply_effect` and
    `confirm=true`.
11. Quit Audition while the MCP server runs. Confirm a read-only call returns
    `BRIDGE_UNAVAILABLE`, reopen Audition and the panel, and confirm
    authenticated reconnection without replaying an earlier side effect.

Recording is intentionally excluded from unattended smoke execution. If
record must be validated, use a disposable input and explicitly approve
`audition_record` immediately before the call, then stop it manually if the
client result is delayed.

## Negative safety probes

Each probe must fail before an editor action:

- open `/etc/hosts` or another path outside the read roots:
  `PATH_NOT_ALLOWED`;
- use a wrong or uppercase extension: `PATH_NOT_ALLOWED`;
- export to an existing file: `DESTINATION_EXISTS`;
- omit confirmation or pass `"true"` as a string: schema rejection or
  `CONFIRMATION_REQUIRED`;
- request an unconfigured favorite or preset: `OPERATION_NOT_ALLOWED`;
- look for an unknown operation such as `audition_run_script`: no such MCP
  tool exists;
- inspect discovery for a raw-script, arbitrary-command, shell, overwrite, or
  generic plugin tool: none may exist.

Do not weaken a failed probe to make a version appear compatible.

## Evidence

Record:

```text
Date and time:
macOS version:
Adobe Audition version and build:
CEP runtime generation:
audio-mcp-integrations version/commit:
MCP SDK version:
websockets version:
Client (Codex or Claude Desktop):
Doctor result:
Panel configuration status:
Panel bridge status:
15-tool discovery result:
Status/document result:
Transport/playhead result:
Selection result or unsupported evidence:
Open result:
Import result or unsupported evidence:
Save result:
Export result and output-file existence:
Effect list/application result:
Negative-probe results:
Close/reconnect result:
Observed warnings:
```

Do not include the authentication token, private audio content, or unrelated
filesystem paths in the evidence.
