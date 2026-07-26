# Audacity MCP disposable-project smoke test

Use this runbook only after `audio-mcp-doctor --json` reports four passing
Audacity checks. It is verified for Audacity 3.7.8.0 and must not be used with
Audacity 4.

## Prepare disposable media

Close valuable Audacity projects. In a terminal, create a unique temporary
directory and a one-second WAV:

```bash
smoke_dir="$(mktemp -d /tmp/audio-mcp-smoke.XXXXXX)"
python3 - "$smoke_dir/input.wav" <<'PY'
import math
import struct
import sys
import wave

path = sys.argv[1]
sample_rate = 44_100
with wave.open(path, "wb") as output:
    output.setnchannels(1)
    output.setsampwidth(2)
    output.setframerate(sample_rate)
    frames = (
        struct.pack("<h", int(8_000 * math.sin(2 * math.pi * 440 * i / sample_rate)))
        for i in range(sample_rate)
    )
    output.writeframes(b"".join(frames))
print(path)
PY
printf 'Smoke directory: %s\n' "$smoke_dir"
```

Keep the printed absolute directory path. All output in this test must stay
inside it.

## Exercise the MCP tools

In the selected MCP client, issue one operation at a time and verify Audacity
after each result:

1. Call `project_new`.
2. Call `project_import_audio` with the printed directory's `input.wav`.
3. Call `project_get_info` with `info_type="Tracks"` and confirm one audio
   track is reported.
4. Call `select_region` with `start=0.2` and `end=0.8`; confirm the visible
   selection.
5. Call `analyze_sample_data_export` with a new path named `samples.txt`
   inside the printed directory and `limit=100`.
6. Call `project_save_as` with a new path named `smoke.aup3` inside the
   printed directory. This is an explicit save to a disposable path.
7. Confirm `input.wav`, `samples.txt`, and `smoke.aup3` exist. Close the
   disposable project without saving any additional changes.

Never reuse an existing output path. If any step fails, stop; inspect the
project and any modal Audacity dialog before retrying.

## Evidence

Record:

```text
Date and time:
Audacity version:
audacity-mcp version:
MCP client:
Doctor result:
Import result:
Track-info result:
Selection result:
Analysis result:
New disposable project save result:
Observed warnings:
Temporary directory:
```

Do not include audio contents or unrelated user paths in the evidence.
