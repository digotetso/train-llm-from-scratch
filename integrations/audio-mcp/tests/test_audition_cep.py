import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).parents[1] / "audition-cep"
JS_FILES = (
    ROOT / "js" / "cep.js",
    ROOT / "js" / "dispatcher.js",
    ROOT / "js" / "main.js",
)
OPERATIONS = {
    "get_status",
    "get_document",
    "get_selection",
    "set_playhead",
    "set_selection",
    "play",
    "pause",
    "stop",
    "record",
    "open",
    "import_media",
    "save",
    "export",
    "apply_favorite",
}


def test_manifest_targets_only_audition_and_local_panel() -> None:
    manifest = ROOT / "CSXS" / "manifest.xml"
    tree = ET.parse(manifest)
    namespace = {"c": "http://www.adobe.com/ExtensionManifest/7.0"}

    host = tree.find(".//c:Host", namespace)
    runtime = tree.find(".//c:RequiredRuntime", namespace)
    main_path = tree.find(".//c:MainPath", namespace)
    script_path = tree.find(".//c:ScriptPath", namespace)
    assert host is not None and host.attrib == {
        "Name": "AUDT",
        "Version": "[13.0,99.9]",
    }
    assert runtime is not None and runtime.attrib == {
        "Name": "CSXS",
        "Version": "9.0",
    }
    assert main_path is not None and main_path.text == "./index.html"
    assert script_path is not None and script_path.text == "./jsx/host.jsx"

    text = manifest.read_text(encoding="utf-8")
    assert "--enable-nodejs" not in text
    assert "http://" not in text.replace(
        "http://www.adobe.com/ExtensionManifest/7.0",
        "",
    )
    assert "https://" not in text


def test_javascript_has_valid_syntax() -> None:
    for path in JS_FILES:
        result = subprocess.run(
            ["node", "--check", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"{path}: {result.stderr}"


def test_cep_never_uses_dynamic_evaluation_or_caller_selected_commands() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in ROOT.rglob("*")
        if path.suffix in {".js", ".jsx", ".html"}
    )

    assert re.search(r"\beval\s*\(", text) is None
    assert "new Function" not in text
    assert "toSource" not in text
    assert "command_id" not in text
    assert "script_text" not in text
    assert "os.system" not in text


def _run_dispatcher(calls: list[dict[str, object]]) -> dict[str, object]:
    dispatcher = ROOT / "js" / "dispatcher.js"
    node_program = f"""
const fs = require("fs");
const vm = require("vm");
const scripts = [];
global.window = {{
  __adobe_cep__: {{
    evalScript: function (script, callback) {{
      scripts.push(script);
      callback(JSON.stringify({{ok: true, result: {{accepted: true}}}}));
    }}
  }}
}};
vm.runInThisContext(fs.readFileSync({json.dumps(str(dispatcher))}, "utf8"));
const calls = {json.dumps(calls)};
const results = [];
for (const call of calls) {{
  window.AudioMcpDispatcher.dispatch(
    call.operation,
    call.arguments,
    function (error, result) {{
      results.push({{error: error, result: result}});
    }}
  );
}}
process.stdout.write(JSON.stringify({{scripts: scripts, results: results}}));
"""
    result = subprocess.run(
        ["node", "-e", node_program],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_dispatcher_maps_only_fixed_operations() -> None:
    calls = [
        {"operation": "get_status", "arguments": {}},
        {"operation": "get_document", "arguments": {}},
        {"operation": "get_selection", "arguments": {}},
        {"operation": "set_playhead", "arguments": {"seconds": 1.25}},
        {
            "operation": "set_selection",
            "arguments": {"start_seconds": 0.25, "end_seconds": 1.5},
        },
        {"operation": "play", "arguments": {}},
        {"operation": "pause", "arguments": {}},
        {"operation": "stop", "arguments": {}},
        {"operation": "record", "arguments": {}},
        {"operation": "open", "arguments": {"path": "/tmp/voice.wav"}},
        {
            "operation": "import_media",
            "arguments": {"path": "/tmp/voice.wav", "track_index": 2},
        },
        {"operation": "save", "arguments": {}},
        {"operation": "export", "arguments": {"path": "/tmp/mix.wav"}},
        {
            "operation": "apply_favorite",
            "arguments": {"favorite": "Normalize -3 dB"},
        },
    ]

    output = _run_dispatcher(calls)

    assert len(output["scripts"]) == len(OPERATIONS)
    assert output["scripts"] == [
        "AudioMcpHost.getStatus()",
        "AudioMcpHost.getDocument()",
        "AudioMcpHost.getSelection()",
        "AudioMcpHost.setPlayhead(1.25)",
        "AudioMcpHost.setSelection(0.25,1.5)",
        "AudioMcpHost.play()",
        "AudioMcpHost.pause()",
        "AudioMcpHost.stop()",
        "AudioMcpHost.record()",
        'AudioMcpHost.openDocument("/tmp/voice.wav")',
        'AudioMcpHost.importMedia("/tmp/voice.wav",2)',
        "AudioMcpHost.save()",
        'AudioMcpHost.exportDocument("/tmp/mix.wav")',
        'AudioMcpHost.applyFavorite("Normalize -3 dB")',
    ]
    assert all(item["error"] is None for item in output["results"])


def test_dispatcher_quotes_caller_strings_and_rejects_unknown_operation() -> None:
    injected_path = '/tmp/x");app.quit();//.wav'
    output = _run_dispatcher(
        [
            {"operation": "open", "arguments": {"path": injected_path}},
            {"operation": "run_script", "arguments": {"code": "app.quit()"}},
            {"operation": "set_playhead", "arguments": {"seconds": "1"}},
        ]
    )

    assert output["scripts"] == [
        f"AudioMcpHost.openDocument({json.dumps(injected_path, separators=(',', ':'))})"
    ]
    unknown, invalid_number = output["results"][1:]
    assert unknown["error"]["code"] == "OPERATION_NOT_ALLOWED"
    assert invalid_number["error"]["code"] == "INVALID_ARGUMENT"


def test_host_uses_only_fixed_audition_commands_and_apis() -> None:
    text = (ROOT / "jsx" / "host.jsx").read_text(encoding="utf-8")

    required = [
        "Application.COMMAND_EDIT_SETINPOINTTOCTI",
        "Application.COMMAND_EDIT_SETOUTPOINTTOCTI",
        "Application.COMMAND_FILE_SAVE",
        "app.transport.play()",
        "app.transport.pause()",
        "app.transport.stop()",
        "app.transport.record()",
        "new DocumentOpenParameter(path)",
        "app.openDocument",
        "new File(path).exists",
        "saveAs(path, true)",
        "applyFavorite(name)",
    ]
    for expression in required:
        assert expression in text

    assert "app.invokeCommand(command" not in text
    assert "eval(" not in text
    assert "toSource" not in text
    assert 'case "DESTINATION_EXISTS":' in (
        ROOT / "js" / "main.js"
    ).read_text(encoding="utf-8")


def test_host_response_encoder_round_trips_control_characters() -> None:
    host = ROOT / "jsx" / "host.jsx"
    display_name = 'Voice "one"\nline\x08\x01'
    node_program = f"""
const fs = require("fs");
const vm = require("vm");
global.app = {{
  version: "13.0.2",
  buildNumber: "42",
  activeDocument: {{
    displayName: {json.dumps(display_name)},
    id: "doc-1",
    path: "/tmp/voice.wav",
    sampleRate: 48000,
    duration: 96000,
    playheadPosition: 24000,
    reflect: {{name: "WaveDocument", properties: [], methods: []}}
  }},
  transport: {{}}
}};
vm.runInThisContext(fs.readFileSync({json.dumps(str(host))}, "utf8"));
const status = JSON.parse(AudioMcpHost.getStatus());
const documentResult = JSON.parse(AudioMcpHost.getDocument());
process.stdout.write(JSON.stringify({{status: status, document: documentResult}}));
"""
    result = subprocess.run(
        ["node", "-e", node_program],
        capture_output=True,
        text=True,
        check=True,
    )
    output = json.loads(result.stdout)

    assert output["status"]["ok"] is True
    assert output["status"]["result"]["application"]["version"] == "13.0.2"
    assert output["document"]["ok"] is True
    assert output["document"]["result"]["display_name"] == display_name


def test_panel_renders_status_only_and_main_has_bounded_reconnects() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    main = (ROOT / "js" / "main.js").read_text(encoding="utf-8")

    assert "Audio MCP for Adobe Audition" in html
    assert "Configuration:" in html
    assert "Bridge:" in html
    assert "Last operation:" in html
    assert "secret" not in html.lower()
    assert "[1000, 2000, 5000, 10000]" in main
    assert "127.0.0.1" in main
    assert "audio-mcp/audition.json" in main
