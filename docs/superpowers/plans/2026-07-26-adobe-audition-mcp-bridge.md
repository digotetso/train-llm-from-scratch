# Adobe Audition MCP Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, authenticated Adobe Audition MCP server and CEP extension with allowlisted inspection, transport, open/import, save/export, selection, and favorite-application tools for Codex and Claude Desktop.

**Architecture:** A Python FastMCP 1.x stdio server enforces configuration, confirmation, path, operation, and timeout policy before sending versioned JSON requests over a loopback-only WebSocket. A CEP panel authenticates as its first message, maps fixed operation names to fixed ExtendScript host functions, and never accepts raw script or command identifiers. The host layer uses documented Audition DOM calls and returns structured unsupported-operation errors when the installed application lacks a safe API.

**Tech Stack:** Python 3.11+, MCP Python SDK `>=1.28.1,<2`, `websockets==16.1.1`, pytest 8, Adobe CEP 9-compatible HTML/JavaScript, ExtendScript, Audition 2020 `13.0.2` for local validation, Audition `26.3` as an external compatibility gate.

## Global Constraints

- All implementation files live under `integrations/audio-mcp/`; do not modify the root MatGPT package or root lockfile.
- Use stable MCP Python SDK 1.x with `mcp>=1.28.1,<2`; MCP 2 is prerelease and is excluded.
- Pin `websockets==16.1.1`.
- Bind only to `127.0.0.1`; reject any configured host other than that exact address.
- Permit one authenticated CEP connection and one controlling MCP host at a time.
- Never expose raw JSX, `eval`, shell execution, arbitrary application command IDs, arbitrary plugin paths, or arbitrary favorite names.
- Confirmation must be the literal boolean `True` on the same request for record, open, import, save, export, and favorite application.
- Constrain reads and writes to configured roots; reject roots equal to `/`, a volume root, or the user's home directory.
- Reject write destinations that already exist.
- MCP stdout is protocol-only; operational logs go to stderr and redact the shared secret.
- Side-effecting requests are never retried automatically.
- Installation is macOS-scoped, idempotent, supports `--dry-run`, backs up an existing CEP extension, and does not edit Codex or Claude configuration.
- Local smoke evidence may establish compatibility only for installed Audition `13.0.2`. Audition `26.3` remains unverified until the same runbook passes there.
- Existing unrelated working-tree changes must remain untouched.

---

## File Map

| File | Responsibility |
|---|---|
| `integrations/audio-mcp/pyproject.toml` | Add stable MCP/WebSocket dependencies and Audition entry point |
| `integrations/audio-mcp/src/audio_mcp/audition/config.py` | Owner-only JSON configuration loading and validation |
| `integrations/audio-mcp/src/audio_mcp/audition/errors.py` | Stable error codes and secret-safe public failures |
| `integrations/audio-mcp/src/audio_mcp/audition/protocol.py` | Versioned request/response envelopes and size limits |
| `integrations/audio-mcp/src/audio_mcp/audition/policy.py` | Confirmation, operation, extension, and path policies |
| `integrations/audio-mcp/src/audio_mcp/audition/bridge.py` | Authenticated single-client WebSocket request correlation |
| `integrations/audio-mcp/src/audio_mcp/audition/service.py` | Tool-level validation and fixed bridge-operation translation |
| `integrations/audio-mcp/src/audio_mcp/audition/server.py` | FastMCP lifespan, exact tool registration, and stdio entry point |
| `integrations/audio-mcp/audition-cep/CSXS/manifest.xml` | Audition CEP 9+ panel declaration |
| `integrations/audio-mcp/audition-cep/index.html` | Minimal local status panel |
| `integrations/audio-mcp/audition-cep/js/main.js` | Config load, WebSocket auth, fixed dispatch, reconnect |
| `integrations/audio-mcp/audition-cep/js/cep.js` | Minimal audited wrapper around `window.__adobe_cep__` and `window.cep.fs` |
| `integrations/audio-mcp/audition-cep/js/dispatcher.js` | Operation-to-host-function allowlist |
| `integrations/audio-mcp/audition-cep/jsx/host.jsx` | Fixed Audition ExtendScript functions and JSON result encoder |
| `integrations/audio-mcp/scripts/install-audition-cep.sh` | Scoped extension/config installer with backup and dry-run |
| `integrations/audio-mcp/configs/codex.example.toml` | Add Audition MCP entry |
| `integrations/audio-mcp/configs/claude-desktop.example.json` | Add Audition MCP entry |
| `integrations/audio-mcp/src/audio_mcp/doctor.py` | Add config, Audition, port, CEP, and live-handshake checks |
| `integrations/audio-mcp/tests/conftest.py` | Free-port and secure temporary Audition configuration fixtures |
| `integrations/audio-mcp/tests/` | Unit, security, protocol, MCP, installer, config, and docs tests |
| `integrations/audio-mcp/docs/audition-smoke-test.md` | Real-application verification and evidence |

### Task 1: Add stable dependencies and secure configuration

**Files:**
- Modify: `integrations/audio-mcp/pyproject.toml`
- Create: `integrations/audio-mcp/src/audio_mcp/audition/__init__.py`
- Create: `integrations/audio-mcp/src/audio_mcp/audition/config.py`
- Create: `integrations/audio-mcp/tests/conftest.py`
- Create: `integrations/audio-mcp/tests/test_audition_config.py`

**Interfaces:**
- Consumes: `AUDIO_MCP_AUDITION_CONFIG` or macOS default `~/Library/Application Support/audio-mcp/audition.json`.
- Produces:
  - `AuditionConfig(secret, read_roots, write_roots, host, port, favorites, export_presets)`
  - `default_config_path() -> Path`
  - `load_config(path: Path | None = None) -> AuditionConfig`
  - `ConfigError`

- [ ] **Step 1: Write failing configuration tests**

```python
# integrations/audio-mcp/tests/test_audition_config.py
import json
import os
from pathlib import Path

import pytest

from audio_mcp.audition.config import ConfigError, load_config


def _write_config(path: Path, read_root: Path, write_root: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "secret": "a" * 64,
                "read_roots": [str(read_root)],
                "write_roots": [str(write_root)],
                "host": "127.0.0.1",
                "port": 18765,
                "favorites": ["Normalize -3 dB"],
                "export_presets": {"wav": ".wav"},
            }
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)


def test_load_config_accepts_owner_only_local_configuration(tmp_path: Path) -> None:
    read_root = tmp_path / "read"
    write_root = tmp_path / "write"
    read_root.mkdir()
    write_root.mkdir()
    config_path = tmp_path / "audition.json"
    _write_config(config_path, read_root, write_root)

    config = load_config(config_path)

    assert config.host == "127.0.0.1"
    assert config.port == 18765
    assert config.favorites == ("Normalize -3 dB",)
    assert config.export_presets == {"wav": ".wav"}


@pytest.mark.parametrize("host", ["localhost", "0.0.0.0", "::1", "192.168.1.2"])
def test_load_config_rejects_non_exact_loopback(tmp_path: Path, host: str) -> None:
    config_path = tmp_path / "audition.json"
    config_path.write_text(
        json.dumps(
            {
                "secret": "a" * 64,
                "read_roots": [],
                "write_roots": [],
                "host": host,
                "port": 18765,
                "favorites": [],
                "export_presets": {},
            }
        ),
        encoding="utf-8",
    )
    config_path.chmod(0o600)
    with pytest.raises(ConfigError, match="127.0.0.1"):
        load_config(config_path)


def test_load_config_rejects_group_permissions(tmp_path: Path) -> None:
    config_path = tmp_path / "audition.json"
    config_path.write_text(
        '{"secret":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","read_roots":[],"write_roots":[],"host":"127.0.0.1","port":18765,"favorites":[],"export_presets":{}}',
        encoding="utf-8",
    )
    config_path.chmod(0o640)
    with pytest.raises(ConfigError):
        load_config(config_path)


def test_load_config_rejects_non_hex_secret(tmp_path: Path) -> None:
    config_path = tmp_path / "audition.json"
    config_path.write_text(
        '{"secret":"zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz","read_roots":[],"write_roots":[],"host":"127.0.0.1","port":18765,"favorites":[],"export_presets":{}}',
        encoding="utf-8",
    )
    config_path.chmod(0o600)
    with pytest.raises(ConfigError, match="lowercase hex"):
        load_config(config_path)
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_audition_config.py -q
```

Expected: collection fails because `audio_mcp.audition.config` is absent.

- [ ] **Step 3: Add exact dependency bounds and entry point**

Modify the project sections to contain:

```toml
[project]
name = "audio-mcp-integrations"
version = "0.1.0"
description = "Local Audacity and Adobe Audition MCP integrations."
requires-python = ">=3.11"
dependencies = [
  "mcp>=1.28.1,<2",
  "websockets==16.1.1",
]

[project.scripts]
audio-mcp-doctor = "audio_mcp.doctor:main"
audio-mcp-audition = "audio_mcp.audition.server:main"
```

- [ ] **Step 4: Implement configuration validation**

```python
# integrations/audio-mcp/src/audio_mcp/audition/config.py
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AuditionConfig:
    secret: str
    read_roots: tuple[Path, ...]
    write_roots: tuple[Path, ...]
    host: str
    port: int
    favorites: tuple[str, ...]
    export_presets: dict[str, str]


def default_config_path() -> Path:
    return Path.home() / "Library" / "Application Support" / "audio-mcp" / "audition.json"


def _validate_root(value: str) -> Path:
    root = Path(value).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ConfigError("Configured media roots must be directories.")
    if root == Path(root.anchor) or root == Path.home().resolve():
        raise ConfigError("Filesystem and user-home roots are forbidden.")
    return root


def load_config(path: Path | None = None) -> AuditionConfig:
    selected = path or Path(
        os.environ.get("AUDIO_MCP_AUDITION_CONFIG", default_config_path())
    )
    mode = selected.stat().st_mode & 0o777
    if mode & 0o077:
        raise ConfigError("Audition configuration must have mode 0600.")
    raw = json.loads(selected.read_text(encoding="utf-8"))
    secret = raw.get("secret")
    if not isinstance(secret, str) or re.fullmatch(r"[0-9a-f]{64}", secret) is None:
        raise ConfigError("Audition configuration secret must be 64 lowercase hex characters.")
    if raw.get("host") != "127.0.0.1":
        raise ConfigError("Audition bridge host must be exactly 127.0.0.1.")
    port = raw.get("port")
    if not isinstance(port, int) or not 1024 <= port <= 65535:
        raise ConfigError("Audition bridge port must be between 1024 and 65535.")
    favorites = raw.get("favorites", [])
    export_presets = raw.get("export_presets", {})
    if not all(isinstance(value, str) and value for value in favorites):
        raise ConfigError("Favorite names must be non-empty strings.")
    if not all(
        isinstance(name, str)
        and name
        and isinstance(extension, str)
        and extension.startswith(".")
        for name, extension in export_presets.items()
    ):
        raise ConfigError("Export presets must map names to file extensions.")
    return AuditionConfig(
        secret=secret,
        read_roots=tuple(_validate_root(value) for value in raw.get("read_roots", [])),
        write_roots=tuple(_validate_root(value) for value in raw.get("write_roots", [])),
        host="127.0.0.1",
        port=port,
        favorites=tuple(favorites),
        export_presets=dict(export_presets),
    )
```

Also create:

```python
# integrations/audio-mcp/src/audio_mcp/audition/__init__.py
"""Safety-bounded Adobe Audition MCP bridge."""
```

- [ ] **Step 5: Add shared secure test fixtures**

```python
# integrations/audio-mcp/tests/conftest.py
import json
import socket
from pathlib import Path

import pytest

from audio_mcp.audition.config import AuditionConfig


@pytest.fixture
def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@pytest.fixture
def config(tmp_path: Path, free_port: int) -> AuditionConfig:
    read_root = tmp_path / "read"
    write_root = tmp_path / "write"
    read_root.mkdir()
    write_root.mkdir()
    return AuditionConfig(
        secret="a" * 64,
        read_roots=(read_root,),
        write_roots=(write_root,),
        host="127.0.0.1",
        port=free_port,
        favorites=("Normalize -3 dB",),
        export_presets={"wav": ".wav"},
    )


@pytest.fixture
def config_path(config: AuditionConfig, tmp_path: Path) -> Path:
    path = tmp_path / "audition.json"
    path.write_text(
        json.dumps(
            {
                "secret": config.secret,
                "read_roots": [str(value) for value in config.read_roots],
                "write_roots": [str(value) for value in config.write_roots],
                "host": config.host,
                "port": config.port,
                "favorites": list(config.favorites),
                "export_presets": config.export_presets,
            }
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path
```

- [ ] **Step 6: Run configuration tests and verify GREEN**

Run:

```bash
uv lock --project integrations/audio-mcp
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_audition_config.py -q
```

Expected: config tests pass and only `integrations/audio-mcp/uv.lock` is created.

- [ ] **Step 7: Commit the configuration slice**

```bash
git add integrations/audio-mcp/pyproject.toml integrations/audio-mcp/uv.lock integrations/audio-mcp/src/audio_mcp/audition integrations/audio-mcp/tests/conftest.py integrations/audio-mcp/tests/test_audition_config.py
git commit -m "feat: add secure Audition MCP configuration"
```

### Task 2: Define the versioned protocol and public errors

**Files:**
- Create: `integrations/audio-mcp/src/audio_mcp/audition/errors.py`
- Create: `integrations/audio-mcp/src/audio_mcp/audition/protocol.py`
- Create: `integrations/audio-mcp/tests/test_audition_protocol.py`

**Interfaces:**
- Produces:
  - `ErrorCode` string enum with the specification's 13 codes
  - `AuditionError(code, message, retryable=False)`
  - `Request.create(operation, arguments, timeout_ms) -> Request`
  - `Request.to_json() -> str`
  - `Response.from_json(payload, expected_request_id) -> Response`
  - constants `PROTOCOL = "audio-mcp-audition/1"` and `MAX_MESSAGE_BYTES = 65536`

- [ ] **Step 1: Write failing protocol tests**

```python
# integrations/audio-mcp/tests/test_audition_protocol.py
import json

import pytest

from audio_mcp.audition.errors import AuditionError, ErrorCode
from audio_mcp.audition.protocol import MAX_MESSAGE_BYTES, PROTOCOL, Request, Response


def test_request_has_version_id_operation_arguments_and_deadline() -> None:
    request = Request.create("get_status", {}, timeout_ms=5000)
    payload = json.loads(request.to_json())
    assert payload["protocol"] == PROTOCOL
    assert payload["request_id"] == request.request_id
    assert payload["operation"] == "get_status"
    assert payload["arguments"] == {}
    assert payload["deadline_ms"] == 5000


def test_response_rejects_wrong_request_id() -> None:
    payload = json.dumps(
        {"protocol": PROTOCOL, "request_id": "wrong", "ok": True, "result": {}}
    )
    with pytest.raises(AuditionError) as caught:
        Response.from_json(payload, expected_request_id="expected")
    assert caught.value.code is ErrorCode.PROTOCOL_ERROR


def test_response_rejects_oversized_payload() -> None:
    with pytest.raises(AuditionError) as caught:
        Response.from_json("x" * (MAX_MESSAGE_BYTES + 1), expected_request_id="id")
    assert caught.value.code is ErrorCode.PROTOCOL_ERROR
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_audition_protocol.py -q
```

Expected: imports fail because the protocol modules do not exist.

- [ ] **Step 3: Implement exact enums and envelopes**

```python
# integrations/audio-mcp/src/audio_mcp/audition/errors.py
from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    UNAUTHORIZED = "UNAUTHORIZED"
    BRIDGE_UNAVAILABLE = "BRIDGE_UNAVAILABLE"
    BRIDGE_TIMEOUT = "BRIDGE_TIMEOUT"
    APPLICATION_UNAVAILABLE = "APPLICATION_UNAVAILABLE"
    DOCUMENT_NOT_OPEN = "DOCUMENT_NOT_OPEN"
    PATH_NOT_ALLOWED = "PATH_NOT_ALLOWED"
    DESTINATION_EXISTS = "DESTINATION_EXISTS"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    OPERATION_NOT_ALLOWED = "OPERATION_NOT_ALLOWED"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    APPLICATION_ERROR = "APPLICATION_ERROR"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"


class AuditionError(RuntimeError):
    def __init__(self, code: ErrorCode, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
```

`protocol.py` must use `uuid.uuid4().hex`, compact `json.dumps`, explicit type
checks, the 64 KiB limit, exact protocol equality, exact request-ID equality,
and convert a remote error only through `ErrorCode(remote_code)`. Unknown
codes become `PROTOCOL_ERROR`. The bridge layer redacts the configured secret
before any remote error message reaches MCP or stderr.

- [ ] **Step 4: Run protocol tests and verify GREEN**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_audition_protocol.py -q
```

Expected: all protocol tests pass.

- [ ] **Step 5: Commit the protocol slice**

```bash
git add integrations/audio-mcp/src/audio_mcp/audition/errors.py integrations/audio-mcp/src/audio_mcp/audition/protocol.py integrations/audio-mcp/tests/test_audition_protocol.py
git commit -m "feat: define Audition bridge protocol"
```

### Task 3: Enforce confirmation, allowlists, and filesystem containment

**Files:**
- Create: `integrations/audio-mcp/src/audio_mcp/audition/policy.py`
- Create: `integrations/audio-mcp/tests/test_audition_policy.py`

**Interfaces:**
- Produces:
  - `READ_EXTENSIONS = {".wav", ".wave", ".aif", ".aiff", ".mp3", ".flac", ".sesx"}`
  - `require_confirmation(confirm: object) -> None`
  - `validate_read_path(path: str, roots: tuple[Path, ...]) -> Path`
  - `validate_write_path(path: str, roots: tuple[Path, ...], extension: str) -> Path`
  - `validate_favorite(name: str, allowed: tuple[str, ...]) -> str`
  - `validate_time(value: float, name: str) -> float`

- [ ] **Step 1: Write failing adversarial policy tests**

```python
# integrations/audio-mcp/tests/test_audition_policy.py
from pathlib import Path

import pytest

from audio_mcp.audition.errors import AuditionError, ErrorCode
from audio_mcp.audition.policy import (
    require_confirmation,
    validate_favorite,
    validate_read_path,
    validate_write_path,
)


@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_confirmation_accepts_only_literal_true(value: object) -> None:
    with pytest.raises(AuditionError) as caught:
        require_confirmation(value)
    assert caught.value.code is ErrorCode.CONFIRMATION_REQUIRED


def test_read_path_rejects_traversal_and_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    secret = outside / "secret.wav"
    secret.write_bytes(b"RIFF")
    (root / "link.wav").symlink_to(secret)

    with pytest.raises(AuditionError) as caught:
        validate_read_path(str(root / "link.wav"), (root,))
    assert caught.value.code is ErrorCode.PATH_NOT_ALLOWED


def test_write_rejects_existing_destination(tmp_path: Path) -> None:
    root = tmp_path / "exports"
    root.mkdir()
    destination = root / "mix.wav"
    destination.write_bytes(b"existing")
    with pytest.raises(AuditionError) as caught:
        validate_write_path(str(destination), (root,), ".wav")
    assert caught.value.code is ErrorCode.DESTINATION_EXISTS


def test_favorite_is_exactly_allowlisted() -> None:
    assert validate_favorite("Normalize -3 dB", ("Normalize -3 dB",)) == "Normalize -3 dB"
    with pytest.raises(AuditionError):
        validate_favorite("Normalize -3 dB; app.quit()", ("Normalize -3 dB",))
```

- [ ] **Step 2: Run policy tests and verify RED**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_audition_policy.py -q
```

Expected: module import fails.

- [ ] **Step 3: Implement policy using canonical parents**

Implementation requirements:

```python
def require_confirmation(confirm: object) -> None:
    if confirm is not True:
        raise AuditionError(
            ErrorCode.CONFIRMATION_REQUIRED,
            "This operation requires confirm=true on the same request.",
        )
```

For reads, resolve the existing candidate with `strict=True`, require
`candidate.is_file()`, reject NUL before constructing `Path`, require a
supported lowercase suffix, and accept only when
`candidate.is_relative_to(root.resolve(strict=True))`.

For writes, resolve the existing parent with `strict=True`, append only
`Path(path).name`, ensure the resolved parent is within an allowed root,
require the exact preset extension, and reject `candidate.exists()`. Do not
call `touch`, create directories, or modify files during validation.

- [ ] **Step 4: Add device, empty-root, wrong-extension, and time tests**

```python
def test_empty_roots_disable_file_operations(tmp_path: Path) -> None:
    source = tmp_path / "voice.wav"
    source.write_bytes(b"RIFF")
    with pytest.raises(AuditionError):
        validate_read_path(str(source), ())


def test_write_requires_preset_extension(tmp_path: Path) -> None:
    root = tmp_path / "exports"
    root.mkdir()
    with pytest.raises(AuditionError):
        validate_write_path(str(root / "mix.mp3"), (root,), ".wav")
```

- [ ] **Step 5: Run policy tests and verify GREEN**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_audition_policy.py -q
```

Expected: all policy tests pass.

- [ ] **Step 6: Commit the policy slice**

```bash
git add integrations/audio-mcp/src/audio_mcp/audition/policy.py integrations/audio-mcp/tests/test_audition_policy.py
git commit -m "feat: enforce Audition MCP safety policy"
```

### Task 4: Build the authenticated, single-client WebSocket bridge

**Files:**
- Create: `integrations/audio-mcp/src/audio_mcp/audition/bridge.py`
- Create: `integrations/audio-mcp/tests/test_audition_bridge.py`

**Interfaces:**
- Consumes: `AuditionConfig`, `Request`, `Response`, and a first-message
  authentication object containing exactly the keys `type` and `secret`.
- Produces:
  - `AuditionBridge(config)`
  - `await bridge.start()`
  - `await bridge.close()`
  - `bridge.connected: bool`
  - `await bridge.request(operation, arguments, timeout_ms=5000) -> dict`

- [ ] **Step 1: Write failing auth and correlation tests**

```python
# integrations/audio-mcp/tests/test_audition_bridge.py
import asyncio
import json
from dataclasses import replace

from websockets.asyncio.client import connect

from audio_mcp.audition.bridge import AuditionBridge


def test_bridge_authenticates_and_correlates_response(config) -> None:
    async def scenario() -> None:
        bridge = AuditionBridge(config)
        await bridge.start()
        try:
            async with connect(f"ws://127.0.0.1:{config.port}") as socket:
                await socket.send(json.dumps({"type": "authenticate", "secret": config.secret}))
                assert json.loads(await socket.recv()) == {"type": "authenticated"}

                request_task = asyncio.create_task(bridge.request("get_status", {}))
                request = json.loads(await socket.recv())
                await socket.send(
                    json.dumps(
                        {
                            "protocol": request["protocol"],
                            "request_id": request["request_id"],
                            "ok": True,
                            "result": {"application": "Audition"},
                        }
                    )
                )
                assert await request_task == {"application": "Audition"}
        finally:
            await bridge.close()

    asyncio.run(scenario())


def test_bridge_rejects_wrong_secret(config) -> None:
    async def scenario() -> None:
        bridge = AuditionBridge(config)
        await bridge.start()
        try:
            async with connect(f"ws://127.0.0.1:{config.port}") as socket:
                await socket.send(json.dumps({"type": "authenticate", "secret": "wrong"}))
                await socket.wait_closed()
                assert socket.close_code == 1008
                assert not bridge.connected
        finally:
            await bridge.close()

    asyncio.run(scenario())
```

The `config` fixture must reserve a free local port, use a 64-character test
secret, and create temporary read/write roots.

- [ ] **Step 2: Run bridge tests and verify RED**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_audition_bridge.py -q
```

Expected: bridge import fails.

- [ ] **Step 3: Implement bridge lifecycle and auth**

Use:

```python
from websockets.asyncio.server import ServerConnection, serve
```

Start with:

```python
self._server = await serve(
    self._handle_connection,
    self._config.host,
    self._config.port,
    compression=None,
    max_size=65536,
    max_queue=8,
    ping_interval=20,
    ping_timeout=20,
    close_timeout=5,
    origins=None,
)
```

The connection handler must:

1. await the first frame with a two-second timeout;
2. parse a JSON object containing only `type` and `secret`;
3. compare secrets with `hmac.compare_digest`;
4. close unauthorized peers with code `1008`;
5. close a second authenticated peer with code `1013`;
6. set the active connection only after successful authentication;
7. send `{"type":"authenticated"}`;
8. route later messages by `request_id`;
9. fail all pending requests with `BRIDGE_UNAVAILABLE` on disconnect.

`request()` must reject while disconnected, use `asyncio.wait_for`, remove its
pending future in `finally`, map timeouts to `BRIDGE_TIMEOUT`, and discard a
late or unknown request ID without raising in the receive loop.

- [ ] **Step 4: Add timeout, second-client, oversize, and shutdown tests**

Tests must prove:

- unauthenticated frames never become responses;
- a second connection cannot replace the first;
- a 64 KiB+ frame closes without entering response correlation;
- timeout removes the pending request;
- `close()` is idempotent;
- no exception text contains the configured secret.

- [ ] **Step 5: Run bridge tests and verify GREEN**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_audition_bridge.py -q
```

Expected: all bridge tests pass with no warnings.

- [ ] **Step 6: Commit the bridge slice**

```bash
git add integrations/audio-mcp/src/audio_mcp/audition/bridge.py integrations/audio-mcp/tests/test_audition_bridge.py
git commit -m "feat: add authenticated Audition CEP bridge"
```

### Task 5: Implement the safe service and exact MCP tool surface

**Files:**
- Create: `integrations/audio-mcp/src/audio_mcp/audition/service.py`
- Create: `integrations/audio-mcp/src/audio_mcp/audition/server.py`
- Create: `integrations/audio-mcp/tests/test_audition_service.py`
- Create: `integrations/audio-mcp/tests/test_audition_mcp.py`

**Interfaces:**
- Consumes: `AuditionBridge`, `AuditionConfig`, policy functions.
- Produces exactly 15 MCP tools listed in the approved design.

- [ ] **Step 1: Write failing service translation tests**

```python
# integrations/audio-mcp/tests/test_audition_service.py
import asyncio
from pathlib import Path

import pytest

from audio_mcp.audition.errors import AuditionError, ErrorCode
from audio_mcp.audition.service import AuditionService


class FakeBridge:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.connected = True

    async def request(self, operation: str, arguments: dict, timeout_ms: int = 5000) -> dict:
        self.calls.append((operation, arguments))
        return {"ok": True}


def test_open_validates_path_and_confirmation_before_bridge(config, tmp_path: Path) -> None:
    source = config.read_roots[0] / "voice.wav"
    source.write_bytes(b"RIFF")
    bridge = FakeBridge()
    service = AuditionService(config, bridge)

    result = asyncio.run(service.open(str(source), confirm=True))

    assert result == {"ok": True}
    assert bridge.calls == [("open", {"path": str(source.resolve())})]


def test_export_rejects_unknown_preset_without_bridge(config) -> None:
    bridge = FakeBridge()
    service = AuditionService(config, bridge)
    destination = config.write_roots[0] / "mix.wav"
    with pytest.raises(AuditionError) as caught:
        asyncio.run(service.export(str(destination), "unknown", confirm=True))
    assert caught.value.code is ErrorCode.OPERATION_NOT_ALLOWED
    assert bridge.calls == []
```

- [ ] **Step 2: Run service tests and verify RED**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_audition_service.py -q
```

Expected: service import fails.

- [ ] **Step 3: Implement all service methods**

`AuditionService` must expose these exact coroutine signatures:

- `get_status() -> dict[str, object]`
- `get_document() -> dict[str, object]`
- `get_selection() -> dict[str, object]`
- `set_playhead(seconds: float) -> dict[str, object]`
- `set_selection(start_seconds: float, end_seconds: float) -> dict[str, object]`
- `play() -> dict[str, object]`
- `pause() -> dict[str, object]`
- `stop() -> dict[str, object]`
- `record(confirm: bool) -> dict[str, object]`
- `open(path: str, confirm: bool) -> dict[str, object]`
- `import_media(path: str, track_index: int, confirm: bool) -> dict[str, object]`
- `save(confirm: bool) -> dict[str, object]`
- `export(path: str, preset: str, confirm: bool) -> dict[str, object]`
- `list_effects() -> dict[str, object]`
- `apply_effect(favorite: str, confirm: bool) -> dict[str, object]`

Validate all arguments before calling `bridge.request`. Map tool names to only
these fixed operation strings:

```python
{
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
```

`list_effects()` returns the configured favorite allowlist locally and emits no
bridge request.

- [ ] **Step 4: Write the exact MCP discovery test**

```python
# integrations/audio-mcp/tests/test_audition_mcp.py
import asyncio
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {
    "audition_get_status",
    "audition_get_document",
    "audition_get_selection",
    "audition_set_playhead",
    "audition_set_selection",
    "audition_play",
    "audition_pause",
    "audition_stop",
    "audition_record",
    "audition_open",
    "audition_import",
    "audition_save",
    "audition_export",
    "audition_list_effects",
    "audition_apply_effect",
}


def test_server_exposes_exact_tool_surface(config_path: Path) -> None:
    async def scenario() -> None:
        root = Path(__file__).parents[1]
        parameters = StdioServerParameters(
            command="uv",
            args=["run", "--project", str(root), "audio-mcp-audition"],
            env={
                **os.environ,
                "AUDIO_MCP_AUDITION_CONFIG": str(config_path),
            },
        )
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {tool.name for tool in tools.tools} == EXPECTED_TOOLS

    asyncio.run(scenario())
```

- [ ] **Step 5: Implement FastMCP lifecycle and registrations**

Use `FastMCP("Adobe Audition")`, typed function signatures, and a lifespan that
starts and closes `AuditionBridge`. `create_server(config, bridge=None)` must
support injected fakes in tests. `main()` must call `mcp.run()` with stdio and
must configure structured logging to stderr.

Catch only `AuditionError` at the MCP boundary. Return a structured failure
dictionary with `code`, `message`, and `retryable`; do not expose tracebacks or
the secret. Unexpected exceptions log a request ID to stderr and return
`APPLICATION_ERROR`. Each structured stderr record includes request ID,
operation, duration in milliseconds, outcome, error code, application version
when known, and confirmation-required/present booleans. Allowed paths are
logged relative to their configured root.

- [ ] **Step 6: Run service and MCP tests**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest \
  integrations/audio-mcp/tests/test_audition_service.py \
  integrations/audio-mcp/tests/test_audition_mcp.py -q
```

Expected: all service and discovery tests pass.

- [ ] **Step 7: Commit the MCP server**

```bash
git add integrations/audio-mcp/src/audio_mcp/audition/service.py integrations/audio-mcp/src/audio_mcp/audition/server.py integrations/audio-mcp/tests/test_audition_service.py integrations/audio-mcp/tests/test_audition_mcp.py
git commit -m "feat: expose safe Adobe Audition MCP tools"
```

### Task 6: Build the fixed CEP and ExtendScript dispatcher

**Files:**
- Create: `integrations/audio-mcp/audition-cep/CSXS/manifest.xml`
- Create: `integrations/audio-mcp/audition-cep/index.html`
- Create: `integrations/audio-mcp/audition-cep/js/cep.js`
- Create: `integrations/audio-mcp/audition-cep/js/dispatcher.js`
- Create: `integrations/audio-mcp/audition-cep/js/main.js`
- Create: `integrations/audio-mcp/audition-cep/jsx/host.jsx`
- Create: `integrations/audio-mcp/tests/test_audition_cep_static.py`

**Interfaces:**
- Consumes: shared macOS config file, fixed bridge protocol, Audition DOM.
- Produces: authenticated CEP peer that calls only `AudioMcpHost` fixed functions.

- [ ] **Step 1: Write failing static security tests**

```python
# integrations/audio-mcp/tests/test_audition_cep_static.py
from pathlib import Path

ROOT = Path(__file__).parents[1] / "audition-cep"


def test_manifest_targets_only_audition_and_local_panel() -> None:
    text = (ROOT / "CSXS" / "manifest.xml").read_text(encoding="utf-8")
    assert 'Name="AUDT"' in text
    assert 'Version="[13.0,99.9]"' in text
    assert "<MainPath>./index.html</MainPath>" in text
    assert "--enable-nodejs" not in text


def test_cep_never_uses_dynamic_eval_or_caller_command_ids() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in ROOT.rglob("*")
        if path.suffix in {".js", ".jsx", ".html"}
    )
    assert "eval(" not in text
    assert "new Function" not in text
    assert "command_id" not in text
    assert "script_text" not in text


def test_dispatcher_contains_only_fixed_operations() -> None:
    text = (ROOT / "js" / "dispatcher.js").read_text(encoding="utf-8")
    for operation in [
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
    ]:
        assert f'"{operation}"' in text
```

- [ ] **Step 2: Run static tests and verify RED**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_audition_cep_static.py -q
```

Expected: files are absent.

- [ ] **Step 3: Add the CEP 9-compatible manifest and local panel**

The manifest must use extension ID `com.zx.audio-mcp-audition`, host `AUDT`
range `[13.0,99.9]`, runtime `CSXS` version `9.0`, panel type, local
`index.html`, and no Node or remote-content flags.

The panel displays only:

```text
Audio MCP for Adobe Audition
Configuration: loaded | error
Bridge: connecting | authenticated | disconnected
Last operation: <fixed operation name or none>
```

No secret, media path, or MCP arguments may be rendered.

- [ ] **Step 4: Implement the minimal CEP wrapper**

`cep.js` must wrap only:

```javascript
window.AudioMcpCep = {
  userDataPath: function () {
    return window.__adobe_cep__.getSystemPath("userData");
  },
  readFile: function (path) {
    return window.cep.fs.readFile(path);
  }
};
```

It does not expose a general script-execution function. `dispatcher.js` owns a
private `runFixedHostCall` closure that calls
`window.__adobe_cep__.evalScript` only with a string generated by its fixed
operation map.

- [ ] **Step 5: Implement fixed operation dispatch**

`dispatcher.js` maps every operation to a hard-coded host call. Caller strings
are encoded with `JSON.stringify(value)` only as JavaScript string literals;
caller data is never used as a function or property name.

Examples:

```javascript
handlers.get_status = function () {
  return "AudioMcpHost.getStatus()";
};
handlers.set_playhead = function (args) {
  return "AudioMcpHost.setPlayhead(" + Number(args.seconds) + ")";
};
handlers.open = function (args) {
  return "AudioMcpHost.openDocument(" + JSON.stringify(String(args.path)) + ")";
};
handlers.apply_favorite = function (args) {
  return "AudioMcpHost.applyFavorite(" + JSON.stringify(String(args.favorite)) + ")";
};
```

Unknown operations return `OPERATION_NOT_ALLOWED` without calling
`evalScript`.

- [ ] **Step 6: Implement fixed ExtendScript host functions**

`host.jsx` defines one namespace:

```javascript
var AudioMcpHost = AudioMcpHost || {};
```

It must implement:

- status from `app.version`, `app.buildNumber`, `app.activeDocument`, and
  `app.transport`;
- document metadata from `displayName`, `id`, `path`, `sampleRate`,
  `duration`, and `playheadPosition`;
- playhead seconds converted to samples;
- selection inspection from a fixed `timeSelection` property only when
  runtime reflection confirms it exists, otherwise a structured
  `UNSUPPORTED_OPERATION`;
- selection through only
  `Application.COMMAND_EDIT_SETINPOINTTOCTI` and
  `Application.COMMAND_EDIT_SETOUTPOINTTOCTI`;
- transport through `app.transport.play/pause/stop/record`;
- open through `new DocumentOpenParameter(path)` and `app.openDocument`;
- import by capturing the active `MultitrackDocument`, opening a source
  `WaveDocument`, reactivating the target, validating `trackIndex`, and using
  the target track's `audioClips.add` only when runtime reflection confirms the
  method; otherwise return `UNSUPPORTED_OPERATION`;
- save through the fixed `Application.COMMAND_FILE_SAVE` constant only when
  `app.isCommandEnabled` returns true;
- export only for a `WaveDocument` through `saveAs(path, true)`;
- favorite application only for a `WaveDocument` through
  `applyFavorite(name)`.

The host returns JSON built by a small serializer that supports only null,
boolean, finite number, string, array, and plain object values created inside
the host. It must not use `eval`, `toSource`, caller-selected properties, or
caller-selected command identifiers.

- [ ] **Step 7: Implement authenticated WebSocket lifecycle**

`main.js` loads:

```text
<userDataPath>/audio-mcp/audition.json
```

It validates exact host `127.0.0.1`, integer port, and a 64-character secret,
opens `ws://127.0.0.1:<port>`, sends the authentication object as the first
frame, waits for `{"type":"authenticated"}`, then processes versioned request
envelopes. It reconnects with bounded delays `[1000, 2000, 5000, 10000]` ms,
stops increasing at 10 seconds, and never retries an application request.

- [ ] **Step 8: Run static CEP tests and verify GREEN**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_audition_cep_static.py -q
```

Expected: static safety and manifest tests pass.

- [ ] **Step 9: Commit the CEP extension**

```bash
git add integrations/audio-mcp/audition-cep integrations/audio-mcp/tests/test_audition_cep_static.py
git commit -m "feat: add allowlisted Audition CEP extension"
```

### Task 7: Add installer, client entries, and expanded diagnostics

**Files:**
- Create: `integrations/audio-mcp/scripts/install-audition-cep.sh`
- Modify: `integrations/audio-mcp/configs/codex.example.toml`
- Modify: `integrations/audio-mcp/configs/claude-desktop.example.json`
- Modify: `integrations/audio-mcp/src/audio_mcp/doctor.py`
- Create: `integrations/audio-mcp/tests/test_audition_installer.py`
- Modify: `integrations/audio-mcp/tests/test_client_configs.py`
- Create: `integrations/audio-mcp/tests/test_audition_doctor.py`

**Interfaces:**
- Produces:
  - user config at `~/Library/Application Support/audio-mcp/audition.json`;
  - extension at `~/Library/Application Support/Adobe/CEP/extensions/com.zx.audio-mcp-audition`;
  - client launch command `uv run --project <absolute integration root> audio-mcp-audition`;
  - doctor checks for app version, CEP files, config mode/strength, port, and handshake.

- [ ] **Step 1: Write failing installer and client-config tests**

```python
def test_audition_installer_dry_run_is_user_scoped() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--dry-run"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "com.zx.audio-mcp-audition" in result.stdout
    assert "Application Support/audio-mcp/audition.json" in result.stdout
    assert "/Applications/" not in result.stdout
    assert "defaults write" not in result.stdout
```

Extend `test_client_configs.py` to assert both examples contain an `audition`
entry with:

```text
command = "uv"
args = ["run", "--project", "__ABSOLUTE_REPOSITORY_ROOT__/integrations/audio-mcp", "audio-mcp-audition"]
AUDIO_MCP_AUDITION_CONFIG = "__USER_APPLICATION_SUPPORT__/audio-mcp/audition.json"
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest \
  integrations/audio-mcp/tests/test_audition_installer.py \
  integrations/audio-mcp/tests/test_client_configs.py \
  integrations/audio-mcp/tests/test_audition_doctor.py -q
```

Expected: installer and Audition diagnostic tests fail.

- [ ] **Step 3: Implement scoped install and backup**

The shell script must:

1. resolve its repository-local source directory;
2. set explicit user destinations under `~/Library/Application Support`;
3. print actions only for `--dry-run`;
4. create parent directories with mode `0700`;
5. create config only when absent, with `secrets.token_hex(32)` and mode
   `0600`;
6. leave an existing config unchanged;
7. move an existing extension to
   `com.zx.audio-mcp-audition.backup-YYYYMMDD-HHMMSS`;
8. copy the repository extension;
9. never run `defaults write`, edit client configs, or remove a backup.

- [ ] **Step 4: Add Audition client entries**

Codex TOML:

```toml
[mcp_servers.audition]
command = "uv"
args = [
  "run",
  "--project",
  "__ABSOLUTE_REPOSITORY_ROOT__/integrations/audio-mcp",
  "audio-mcp-audition",
]

[mcp_servers.audition.env]
AUDIO_MCP_AUDITION_CONFIG = "__USER_APPLICATION_SUPPORT__/audio-mcp/audition.json"
```

Claude JSON adds:

```json
"audition": {
  "command": "uv",
  "args": [
    "run",
    "--project",
    "__ABSOLUTE_REPOSITORY_ROOT__/integrations/audio-mcp",
    "audio-mcp-audition"
  ],
  "env": {
    "AUDIO_MCP_AUDITION_CONFIG": "__USER_APPLICATION_SUPPORT__/audio-mcp/audition.json"
  }
}
```

- [ ] **Step 5: Expand doctor without weakening Audacity checks**

Add injectable signature
`audition_checks(app_path: Path, extension_path: Path, config_path: Path,
port_probe: Callable[[str, int], bool]) -> list[Check]` and implement it with
the existing `Check` result model.

Detect installed local version from:

```text
/Applications/Adobe Audition 2020/Adobe Audition 2020.app/Contents/Info.plist
```

Report `13.0.2` as a warning because it is locally testable but not the latest
supported acceptance target. Report `26.3` as pass only after the runbook
records a completed smoke test. Port-in-use without an authenticated live
handshake is a warning, not proof of the bridge.

- [ ] **Step 6: Run installer, client, and doctor tests**

Run:

```bash
bash -n integrations/audio-mcp/scripts/install-audition-cep.sh
uv run --project integrations/audio-mcp --extra test pytest \
  integrations/audio-mcp/tests/test_audition_installer.py \
  integrations/audio-mcp/tests/test_client_configs.py \
  integrations/audio-mcp/tests/test_audition_doctor.py -q
```

Expected: all focused tests pass.

- [ ] **Step 7: Commit setup and diagnostics**

```bash
git add integrations/audio-mcp/scripts/install-audition-cep.sh integrations/audio-mcp/configs integrations/audio-mcp/src/audio_mcp/doctor.py integrations/audio-mcp/tests
git commit -m "feat: add Audition MCP setup and diagnostics"
```

### Task 8: Complete runbooks, security review, and automated preflight

**Files:**
- Modify: `integrations/audio-mcp/README.md`
- Modify: `integrations/audio-mcp/docs/security.md`
- Create: `integrations/audio-mcp/docs/audition-smoke-test.md`
- Create: `integrations/audio-mcp/tests/test_audition_docs.py`

**Interfaces:**
- Consumes: complete server, extension, installer, diagnostics, both client examples.
- Produces: installation, debug-mode, smoke, rollback, limitation, and evidence procedures.

- [ ] **Step 1: Write failing runbook-contract tests**

```python
# integrations/audio-mcp/tests/test_audition_docs.py
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_audition_runbook_records_version_and_safety_probes() -> None:
    text = (ROOT / "docs" / "audition-smoke-test.md").read_text(encoding="utf-8")
    for phrase in [
        "13.0.2",
        "26.3",
        "disposable",
        "confirm=true",
        "PATH_NOT_ALLOWED",
        "DESTINATION_EXISTS",
        "UNSUPPORTED_OPERATION",
        "Evidence",
    ]:
        assert phrase in text


def test_security_doc_states_single_owner_and_no_raw_script() -> None:
    text = (ROOT / "docs" / "security.md").read_text(encoding="utf-8")
    assert "127.0.0.1" in text
    assert "one MCP host" in text
    assert "raw ExtendScript" in text
    assert "arbitrary command" in text
    assert "owner-only" in text
```

- [ ] **Step 2: Run docs tests and verify RED**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests/test_audition_docs.py -q
```

Expected: missing Audition runbook or required content.

- [ ] **Step 3: Write exact install and debug-mode procedure**

Document:

```bash
integrations/audio-mcp/scripts/install-audition-cep.sh --dry-run
integrations/audio-mcp/scripts/install-audition-cep.sh
chmod 600 "$HOME/Library/Application Support/audio-mcp/audition.json"
uv run --project integrations/audio-mcp audio-mcp-doctor --json
```

For the unsigned development extension, document the CEP 9 setting separately
and require explicit operator execution:

```bash
defaults write com.adobe.CSXS.9 PlayerDebugMode 1
```

Do not run that command from the installer. Document reversal:

```bash
defaults delete com.adobe.CSXS.9 PlayerDebugMode
```

The rollback section must instruct the operator to:

1. remove only the `audition` entry from each selected MCP client;
2. quit Audition;
3. move
   `~/Library/Application Support/Adobe/CEP/extensions/com.zx.audio-mcp-audition`
   to a timestamped backup or the operating-system trash;
4. retain the owner-only configuration unless the operator explicitly chooses
   to archive it;
5. restore the most recent timestamped extension backup by moving it back to
   the exact extension path.

- [ ] **Step 4: Write the disposable Audition smoke sequence**

The runbook must test, in order:

1. authenticated panel status;
2. MCP discovery in Codex;
3. MCP discovery in Claude Desktop in a separate run;
4. status and active-document metadata;
5. play, pause, stop, and playhead;
6. selection or explicit unsupported response;
7. open from the read root with confirmation;
8. import into a disposable session with confirmation or explicit unsupported
   response backed by capability evidence;
9. save with confirmation;
10. WAV export to a new write-root path with confirmation;
11. one configured favorite with confirmation or empty allowlist;
12. traversal, wrong extension, existing destination, missing confirmation,
    unknown operation, and arbitrary-script probes;
13. application close and reconnect behavior.

Record installed app version, CEP runtime, MCP SDK version, websockets version,
client, tool result, output-file existence, and warnings.

- [ ] **Step 5: Run complete automated verification**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests -q
bash -n integrations/audio-mcp/scripts/install-audacity-mcp.sh
bash -n integrations/audio-mcp/scripts/install-audition-cep.sh
uv run --project integrations/audio-mcp python -m compileall -q integrations/audio-mcp/src
git diff --check
```

Expected: all tests and syntax checks pass with no warnings or whitespace
errors.

- [ ] **Step 6: Run focused security inspection**

Run:

```bash
rg -n "eval\\(|new Function|subprocess|os\\.system|shell=True|0\\.0\\.0\\.0|command_id|script_text" integrations/audio-mcp
```

Expected:

- no dynamic evaluation or shell execution in production code;
- `0.0.0.0`, `command_id`, and `script_text` appear only in rejection tests or
  security documentation;
- the installer contains fixed `uv`, `mv`, `cp`, `mkdir`, and `chmod`
  operations only.

- [ ] **Step 7: Commit runbooks and preflight coverage**

```bash
git add integrations/audio-mcp/README.md integrations/audio-mcp/docs integrations/audio-mcp/tests/test_audition_docs.py
git commit -m "docs: add Adobe Audition MCP operations runbook"
```

### Task 9: Install locally and record real-application evidence

**Files:**
- Modify only if evidence requires correction:
  - `integrations/audio-mcp/docs/audition-smoke-test.md`
  - implementation files responsible for a reproduced failure

**Interfaces:**
- Consumes: local Audition 2020 `13.0.2`, disposable audio/session files, explicit operator approval for CEP debug mode.
- Produces: honest compatibility evidence for `13.0.2`; no claim for `26.3`.

- [ ] **Step 1: Preview and install user-scoped files**

Run:

```bash
integrations/audio-mcp/scripts/install-audition-cep.sh --dry-run
integrations/audio-mcp/scripts/install-audition-cep.sh
```

Expected: user-scoped config and extension only; any previous extension is
moved to a timestamped backup.

- [ ] **Step 2: Ask before enabling unsigned CEP development mode**

Request explicit user approval, then run:

```bash
defaults write com.adobe.CSXS.9 PlayerDebugMode 1
```

Restart Audition after approval. If approval is declined, stop the live CEP
smoke test and report automated verification separately.

- [ ] **Step 3: Run doctor before tool calls**

Run:

```bash
uv run --project integrations/audio-mcp audio-mcp-doctor --json
```

Expected: config, permissions, extension, installed Audition `13.0.2`, and
loopback checks are explicit. A missing open CEP panel is a clear failure or
warning, not a false pass.

- [ ] **Step 4: Execute the disposable smoke runbook**

Follow `integrations/audio-mcp/docs/audition-smoke-test.md`. Never use existing
course audio as an overwrite destination. Use a new temporary read root and
write root, and confirm each side effect individually.

- [ ] **Step 5: Fix only reproduced failures with TDD**

For each failure:

1. add the cheapest automated regression test;
2. run it and verify the expected failure;
3. make the smallest implementation correction;
4. rerun focused and full integration tests;
5. repeat the specific manual smoke step.

Do not weaken a security assertion to match undocumented Audition behavior.
Return `UNSUPPORTED_OPERATION` when no safe API is demonstrated.

- [ ] **Step 6: Run final verification and report residual gate**

Run:

```bash
uv run --project integrations/audio-mcp --extra test pytest integrations/audio-mcp/tests -q
uv run --project integrations/audio-mcp audio-mcp-doctor --json
git diff --check
git status --short
```

Expected: automated checks pass; doctor records local `13.0.2`; the final
report explicitly states that Audition `26.3` compatibility remains unverified
until the same smoke runbook passes on that version.
