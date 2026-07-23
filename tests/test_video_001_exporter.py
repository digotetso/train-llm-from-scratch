import json
import hashlib
import re
import shutil
import struct
import subprocess
from pathlib import Path


EXPORTER_DIR = (
    Path(__file__).resolve().parents[1]
    / "course/videos/001-computer-learning-from-text/after-effects/exporter"
)
AE_SOURCE_DIR = EXPORTER_DIR / "src/ae"
CORE_PATH = AE_SOURCE_DIR / "import-core.jsxinc"
IMPORTER_PATH = AE_SOURCE_DIR / "importer.jsxinc"
PANEL_PATH = AE_SOURCE_DIR / "panel.jsx"
AUDIT_PATH = AE_SOURCE_DIR / "audit-export.jsx"
FULL_LESSON_AUDIT_SOURCE_PATH = AE_SOURCE_DIR / "audit-full-lesson.jsx"
DUPLICATE_EVIDENCE_CAPTURE_PATH = (
    AE_SOURCE_DIR / "capture-full-lesson-duplicate-evidence.jsx"
)
HOST_RUNTIME_TEST_PATH = EXPORTER_DIR / "tests/ae-host-runtime.test.ts"
SHOT_32_AUDIT_PATH = EXPORTER_DIR / "evidence/shot-32-audit.json"
SHOT_32_COMPARISON_PATH = EXPORTER_DIR / "evidence/shot-32-comparison.json"
SHOT_32_REFERENCE_PATH = EXPORTER_DIR / "tests/fixtures/shot-32-reference.json"
SHOT_32_RAW_DIR = EXPORTER_DIR / "evidence/raw"
SHOT_32_ASSEMBLER_PATH = EXPORTER_DIR / "scripts/assemble-shot-32-evidence.mjs"
FULL_LESSON_ASSEMBLER_PATH = (
    EXPORTER_DIR / "scripts/assemble-full-lesson-evidence.mjs"
)
FIGMA_UI_PROTOCOL_TEST_PATH = EXPORTER_DIR / "tests/ui-protocol.test.ts"
RELEASE_TEST_PATH = EXPORTER_DIR / "tests/release.test.ts"
RELEASE_BUILD_PATH = EXPORTER_DIR / "scripts/build-release.mjs"
RELEASE_VERIFY_PATH = EXPORTER_DIR / "scripts/verify-release.mjs"
README_PATH = EXPORTER_DIR / "README.md"
ANIMATION_ROOT = EXPORTER_DIR.parent
ANIMATE_FULL_LESSON_PATH = ANIMATION_ROOT / "scripts/animate-full-lesson.jsx"
AUDIT_ANIMATED_LESSON_PATH = ANIMATION_ROOT / "scripts/audit-animated-full-lesson.jsx"
MOTION_PROVENANCE_PATH = (
    ANIMATION_ROOT / "scripts/lib/video001-motion-provenance.jsxinc"
)
MOTION_SPEC_PATH = ANIMATION_ROOT / "docs/video-001-motion-spec.md"


def ae_sources() -> dict[Path, str]:
    paths = sorted(
        path
        for path in AE_SOURCE_DIR.rglob("*")
        if path.is_file() and path.suffix in {".jsx", ".jsxinc"}
    )
    assert paths, "the exporter must contain After Effects source files"
    return {path: path.read_text(encoding="utf-8") for path in paths}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    payload = path.read_bytes()
    assert payload[:8] == b"\x89PNG\r\n\x1a\n"
    assert payload[12:16] == b"IHDR"
    return struct.unpack(">II", payload[16:24])


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def flatten_package_nodes(nodes, path=()):
    flattened = []
    fields = [
        "id",
        "name",
        "kind",
        "x",
        "y",
        "width",
        "height",
        "rotation",
        "opacity",
        "text",
        "textBox",
        "paragraph",
        "runs",
        "fill",
        "stroke",
        "strokeWidth",
        "radius",
        "assetHash",
    ]
    for index, node in enumerate(nodes):
        entry = {"path": [*path, index], "zIndex": index}
        entry.update({field: node[field] for field in fields if node.get(field) is not None})
        flattened.append(entry)
        flattened.extend(flatten_package_nodes(node.get("children", []), (*path, index)))
    return flattened


def stable_v001_audit(audit):
    return {
        key: audit[key]
        for key in [
            "comp",
            "layers",
            "precompHierarchy",
            "contentHash",
            "missingFonts",
            "rasterFallbacks",
            "warnings",
        ]
    }


def write_synthetic_full_lesson_evidence_tree(root: Path):
    timing = load_json(EXPORTER_DIR / "config/video001-figma-scenes.json")
    raster_data_base64 = "iVBORw0KGgo="
    raster_hash = hashlib.sha256(b"\x89PNG\r\n\x1a\n").hexdigest()
    session_id = "full-lesson-session-synthetic-001"
    request_id = "11111111-1111-4111-8111-111111111111"
    duplicate_request_id = "22222222-2222-4222-8222-222222222222"
    raw_dir = root / "evidence/full-lesson/raw"
    raw_dir.mkdir(parents=True)
    config_dir = root / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "video001-figma-scenes.json").write_text(
        json.dumps(timing, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    package = {
        "schemaVersion": "2.0.0",
        "exporterVersion": "0.2.0",
        "exportedAt": "2026-07-23T00:00:00.000Z",
        "contentHash": "",
        "source": {
            "fileKey": timing["source"]["figmaFileKey"],
            "pageId": timing["source"]["figmaPageNodeId"],
        },
        "target": {
            "width": timing["canvas"]["width"],
            "height": timing["canvas"]["height"],
            "fps": timing["canvas"]["fps"],
            "timeUnit": timing["canvas"]["timeUnit"],
        },
        "frames": [
            {
                "nodeId": shot["figmaNodeId"],
                "name": shot["name"],
                "width": 1920,
                "height": 1080,
                "duration": shot["duration"],
                "children": [
                    {
                        "id": f'{shot["figmaNodeId"]}::shape',
                        "name": "Synthetic native shape",
                        "kind": "rect",
                        "x": 0,
                        "y": 0,
                        "width": 100,
                        "height": 100,
                        "rotation": 0,
                        "opacity": 1,
                        "fill": "#000000",
                        "stroke": None,
                        "strokeWidth": 0,
                        "radius": 0,
                    },
                    *(
                        [
                            {
                                "id": f'{shot["figmaNodeId"]}::raster',
                                "name": "Synthetic declared raster",
                                "kind": "raster",
                                "x": 100,
                                "y": 100,
                                "width": 100,
                                "height": 100,
                                "rotation": 0,
                                "opacity": 1,
                                "assetHash": raster_hash,
                            }
                        ]
                        if shot["index"] == 31
                        else []
                    ),
                ],
                "warnings": (
                    [
                        {
                            "nodeId": f'{shot["figmaNodeId"]}::raster',
                            "nodeName": "Synthetic declared raster",
                            "property": "gradient",
                            "fallback": "png",
                        }
                    ]
                    if shot["index"] == 31
                    else []
                ),
            }
            for shot in timing["shots"]
        ],
        "assets": [
            {
                "hash": raster_hash,
                "mimeType": "image/png",
                "byteLength": 8,
                "dataBase64": raster_data_base64,
            }
        ],
    }
    fingerprint = {**package, "exportedAt": "", "contentHash": ""}
    package["contentHash"] = hashlib.sha256(
        canonical_json(fingerprint).encode("utf-8")
    ).hexdigest()
    content_hash = package["contentHash"]
    root_names = [f'{shot["name"]}_v001' for shot in timing["shots"]]
    audit = {
        "auditSchemaVersion": 1,
        "contentHash": content_hash,
        "itemCountBefore": 97,
        "itemCountAfter": 97,
        "projectStateUnchanged": True,
        "master": {
            "name": "VIDEO001_MASTER_v001",
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "durationSeconds": 840,
            "durationFrames": 25_200,
            "layers": [
                {
                    "index": shot["index"],
                    "nodeId": shot["figmaNodeId"],
                    "name": f'{shot["name"]}_v001',
                    "sourceComp": f'{shot["name"]}_v001',
                    "startTime": shot["start"],
                    "inPoint": shot["start"],
                    "outPoint": shot["start"] + shot["duration"],
                }
                for shot in timing["shots"]
            ],
        },
        "shots": [
            {
                "index": shot["index"],
                "nodeId": shot["figmaNodeId"],
                "configuredName": shot["name"],
                "name": f'{shot["name"]}_v001',
                "contentHash": content_hash,
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "durationSeconds": shot["duration"],
                "durationFrames": shot["duration"] * 30,
                "nativeCount": 1,
                "nativeNodeIds": [f'{shot["figmaNodeId"]}::shape'],
                "rasterCount": 1 if shot["index"] == 31 else 0,
                "rasterFallbacks": (
                    [
                        {
                            "nodeId": f'{shot["figmaNodeId"]}::raster',
                            "assetHash": raster_hash,
                        }
                    ]
                    if shot["index"] == 31
                    else []
                ),
                "hierarchy": {
                    "name": f'{shot["name"]}_v001',
                    "durationSeconds": shot["duration"],
                    "durationFrames": shot["duration"] * 30,
                    "children": [],
                },
            }
            for shot in timing["shots"]
        ],
        "missingFonts": [],
        "fallbacks": [
            {
                "type": "raster-fallback",
                "nodeId": f'{timing["shots"][30]["figmaNodeId"]}::raster',
                "nodeName": "Synthetic declared raster",
                "property": "gradient",
                "replacement": "png",
            }
        ],
        "warnings": [
            "Raster fallback on Synthetic declared raster: gradient"
        ],
    }
    import_report = {
        "contentHash": content_hash,
        "createdCompNames": root_names,
        "createdMasterCompName": "VIDEO001_MASTER_v001",
        "layerCount": 49,
        "nativeCount": 48,
        "rasterCount": 1,
        "missingFonts": [],
        "fallbacks": audit["fallbacks"],
        "warnings": audit["warnings"],
        "elapsedMs": 1,
    }
    project_items = [
        {
            "index": 1,
            "name": "VIDEO001_MASTER_v001",
            "kind": "comp",
            "parentName": "01_Exporter_Imports",
            "width": 1920,
            "height": 1080,
            "duration": 840,
            "frameRate": 30,
            "layerCount": 48,
            "contentFingerprint": {
                "layers": [{"comment": "master source", "propertyTree": "master-v1"}],
            },
        },
        *[
            {
                "index": index + 2,
                "name": f'{shot["name"]}_v001',
                "kind": "comp",
                "parentName": "01_Exporter_Imports",
                "width": 1920,
                "height": 1080,
                "duration": shot["duration"],
                "frameRate": 30,
                "layerCount": 1,
                "contentFingerprint": {
                    "layers": [
                        {"comment": "shot source", "propertyTree": shot["figmaNodeId"]}
                    ],
                },
            }
            for index, shot in enumerate(timing["shots"])
        ],
        *[
            {
                "index": index + 50,
                "name": f"Synthetic supporting item {index + 1}",
                "kind": "folder",
                "parentName": "",
                "width": None,
                "height": None,
                "duration": None,
                "frameRate": None,
                "layerCount": None,
                "contentFingerprint": None,
            }
            for index in range(226)
        ],
    ]
    duplicate_result = {
        "evidenceSchemaVersion": 1,
        "generator": "After Effects synthetic test fixture",
        "capturedAt": "2026-07-23T00:01:01.000Z",
        "sessionId": session_id,
        "requestId": duplicate_request_id,
        "contentHash": content_hash,
        "projectPath": "/private/tmp/Video001-Exporter-Full-Lesson.aep",
        "importResult": {
            "status": "DUPLICATE_CONTENT",
            "report": None,
        },
        "before": {
            "itemCount": 275,
            "queueCount": 1,
            "v002Count": 0,
            "masterV001Count": 1,
            "shotV001Count": 48,
            "items": project_items,
        },
        "after": {
            "itemCount": 275,
            "queueCount": 0,
            "v002Count": 0,
            "masterV001Count": 1,
            "shotV001Count": 48,
            "items": project_items,
        },
    }
    post_resend_audit = {
        "evidenceSchemaVersion": 1,
        "generator": "After Effects synthetic test fixture",
        "capturedAt": "2026-07-23T00:01:02.000Z",
        "sessionId": session_id,
        "requestId": duplicate_request_id,
        "contentHash": content_hash,
        "projectPath": "/private/tmp/Video001-Exporter-Full-Lesson.aep",
        "snapshot": duplicate_result["after"],
    }
    files = {
        "full-lesson-package.video001-ae.json": package,
        "full-lesson-import-report.json": import_report,
        "full-lesson-ae-audit.json": audit,
        "full-lesson-duplicate-result.json": duplicate_result,
        "full-lesson-post-resend-audit.json": post_resend_audit,
        "full-lesson-live-session.json": {
            "fixture": "synthetic-test-only",
            "status": "COMPLETE",
            "sessionId": session_id,
            "requestId": request_id,
            "contentHash": content_hash,
            "figma": {
                "build": {
                    "status": "PACKAGE_READY",
                    "shotCount": 48,
                    "durationSeconds": 840,
                    "contentHash": content_hash,
                },
                "export": {
                    "sessionId": session_id,
                    "requestId": request_id,
                    "method": "POST",
                    "route": "export",
                    "status": 202,
                    "code": "EXPORT_ACCEPTED",
                    "contentHash": content_hash,
                },
                "unchangedResend": {
                    "sessionId": session_id,
                    "requestId": duplicate_request_id,
                    "method": "POST",
                    "route": "export",
                    "status": 202,
                    "code": "EXPORT_ACCEPTED",
                    "contentHash": content_hash,
                },
            },
            "bridge": {
                "requestId": request_id,
                "contentHash": content_hash,
            },
            "afterEffects": {
                "import": {
                    "status": "IMPORTED",
                    "sessionId": session_id,
                    "requestId": request_id,
                    "contentHash": content_hash,
                    "createdCompCount": 48,
                    "createdMasterCompName": "VIDEO001_MASTER_v001",
                },
                "duplicate": {
                    "status": "DUPLICATE_CONTENT",
                    "sessionId": session_id,
                    "requestId": duplicate_request_id,
                    "contentHash": content_hash,
                    "itemCountBefore": 275,
                    "itemCountAfter": 275,
                    "queueCountBefore": 1,
                    "queueCountAfter": 0,
                    "v002Before": 0,
                    "v002After": 0,
                    "masterV001Count": 1,
                    "shotV001Count": 48,
                },
                "queueCountAfterImport": 0,
                "projectPath": "/private/tmp/Video001-Exporter-Full-Lesson.aep",
            },
        },
    }
    for name, value in files.items():
        (raw_dir / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    accepted_event = {
        "timestamp": "2026-07-23T00:00:00.000Z",
        "event": "export_accepted",
        "requestId": request_id,
        "method": "POST",
        "route": "export",
        "status": 202,
        "remoteAddress": "127.0.0.1",
        "remoteFamily": "IPv4",
        "authenticated": True,
        "contentHash": content_hash,
    }
    duplicate_event = {
        **accepted_event,
        "timestamp": "2026-07-23T00:01:00.000Z",
        "requestId": duplicate_request_id,
    }
    (raw_dir / "full-lesson-bridge-log.jsonl").write_text(
        "\n".join(
            json.dumps(event, ensure_ascii=False)
            for event in (accepted_event, duplicate_event)
        )
        + "\n",
        encoding="utf-8",
    )


def test_full_lesson_figma_exporter_protocol_integration():
    result = subprocess.run(
        [
            "npx",
            "tsx",
            "--test",
            "--test-concurrency=1",
            "--test-name-pattern=full lesson|full-lesson",
            str(FIGMA_UI_PROTOCOL_TEST_PATH),
        ],
        cwd=EXPORTER_DIR,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_full_lesson_evidence_verifier_rejects_falsified_master_out_point(tmp_path):
    synthetic_root = tmp_path / "synthetic-source"
    write_synthetic_full_lesson_evidence_tree(synthetic_root)
    assembled = subprocess.run(
        [
            "node",
            str(FULL_LESSON_ASSEMBLER_PATH),
            "--write",
            "--root",
            str(synthetic_root),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert assembled.returncode == 0, assembled.stdout + assembled.stderr

    isolated_root = tmp_path / "isolated-exporter"
    shutil.copytree(
        synthetic_root / "evidence/full-lesson",
        isolated_root / "evidence/full-lesson",
    )

    def verify():
        return subprocess.run(
            [
                "node",
                str(FULL_LESSON_ASSEMBLER_PATH),
                "--verify",
                "--root",
                str(isolated_root),
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    first = verify()
    assert first.returncode == 0, first.stdout + first.stderr

    audit_path = isolated_root / "evidence/full-lesson/audit.json"
    audit = load_json(audit_path)
    audit["master"]["layers"][31]["outPoint"] += 1
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    falsified = verify()
    assert falsified.returncode != 0
    assert "deterministic assembler output" in (
        falsified.stdout + falsified.stderr
    )


def test_full_lesson_evidence_requires_ae_authored_duplicate_proof(tmp_path):
    synthetic_root = tmp_path / "synthetic-source"
    write_synthetic_full_lesson_evidence_tree(synthetic_root)
    duplicate_result = (
        synthetic_root
        / "evidence/full-lesson/raw/full-lesson-duplicate-result.json"
    )
    duplicate_result.unlink()

    rejected = subprocess.run(
        [
            "node",
            str(FULL_LESSON_ASSEMBLER_PATH),
            "--write",
            "--root",
            str(synthetic_root),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert rejected.returncode != 0
    assert "duplicate" in (rejected.stdout + rejected.stderr).lower()


def test_full_lesson_evidence_rejects_raw_symlink_escape(tmp_path):
    root = tmp_path / "synthetic-source"
    write_synthetic_full_lesson_evidence_tree(root)
    package_path = (
        root
        / "evidence/full-lesson/raw/full-lesson-package.video001-ae.json"
    )
    outside_path = tmp_path / "outside-package.json"
    package_path.rename(outside_path)
    package_path.symlink_to(outside_path)

    result = subprocess.run(
        [
            "node",
            str(FULL_LESSON_ASSEMBLER_PATH),
            "--write",
            "--root",
            str(root),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert re.search(
        r"symlink|containment|regular file|evidence root",
        result.stdout + result.stderr,
        re.IGNORECASE,
    )


def test_full_lesson_evidence_rejects_normalized_credential_key_families(
    tmp_path,
):
    for credential_key in ["apiKey", "credential", "bridgeToken", "pairing_code"]:
        root = tmp_path / credential_key
        write_synthetic_full_lesson_evidence_tree(root)
        session_path = (
            root / "evidence/full-lesson/raw/full-lesson-live-session.json"
        )
        session = load_json(session_path)
        secret_value = "DO_NOT_ECHO_THIS_SECRET_VALUE"
        session["metadata"] = {credential_key: secret_value}
        session_path.write_text(
            json.dumps(session, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                "node",
                str(FULL_LESSON_ASSEMBLER_PATH),
                "--write",
                "--root",
                str(root),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        output = result.stdout + result.stderr
        assert result.returncode != 0
        assert re.search(r"credential|secret|prohibited", output, re.IGNORECASE)
        assert secret_value not in output


def test_full_lesson_evidence_rejects_decoded_json_and_jsonl_secrets(tmp_path):
    cases = [
        ("json", r"\u002fUsers\u002falice\u002fproject.aep", "/Users/alice/project.aep"),
        ("json", r"B\u0065arer opaque-secret", "Bearer opaque-secret"),
        ("jsonl", r"\u002fUsers\u002falice\u002fproject.aep", "/Users/alice/project.aep"),
        ("jsonl", r"B\u0065arer opaque-secret", "Bearer opaque-secret"),
    ]
    for index, (format_name, escaped_value, decoded_value) in enumerate(cases):
        root = tmp_path / f"semantic-{index}"
        write_synthetic_full_lesson_evidence_tree(root)
        raw_dir = root / "evidence/full-lesson/raw"
        if format_name == "json":
            evidence_path = raw_dir / "full-lesson-live-session.json"
            value = load_json(evidence_path)
            value["metadata"] = {"note": "SEMANTIC_REDACTION_PLACEHOLDER"}
            source = (
                json.dumps(value, ensure_ascii=False, indent=2) + "\n"
            ).replace("SEMANTIC_REDACTION_PLACEHOLDER", escaped_value)
        else:
            evidence_path = raw_dir / "full-lesson-bridge-log.jsonl"
            generic_event = {
                "timestamp": "2026-07-23T00:00:01.000Z",
                "event": "http_request",
                "route": "health",
                "status": 200,
                "note": "SEMANTIC_REDACTION_PLACEHOLDER",
            }
            source = evidence_path.read_text(encoding="utf-8") + json.dumps(
                generic_event,
                ensure_ascii=False,
            ).replace("SEMANTIC_REDACTION_PLACEHOLDER", escaped_value) + "\n"
        assert decoded_value not in source
        evidence_path.write_text(source, encoding="utf-8")

        result = subprocess.run(
            [
                "node",
                str(FULL_LESSON_ASSEMBLER_PATH),
                "--write",
                "--root",
                str(root),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        output = result.stdout + result.stderr
        assert result.returncode != 0
        assert re.search(
            r"mutable user path|bearer|credential|prohibited",
            output,
            re.IGNORECASE,
        )
        assert decoded_value not in output


def test_full_lesson_evidence_rejects_cross_shot_raster_rebinding(tmp_path):
    root = tmp_path / "cross-shot-raster"
    write_synthetic_full_lesson_evidence_tree(root)
    audit_path = root / "evidence/full-lesson/raw/full-lesson-ae-audit.json"
    audit = load_json(audit_path)
    audit["shots"][29]["rasterCount"] = 1
    audit["shots"][29]["rasterFallbacks"] = audit["shots"][30][
        "rasterFallbacks"
    ]
    audit["shots"][30]["rasterCount"] = 0
    audit["shots"][30]["rasterFallbacks"] = []
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "node",
            str(FULL_LESSON_ASSEMBLER_PATH),
            "--write",
            "--root",
            str(root),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert re.search(
        r"shot|raster|node",
        result.stdout + result.stderr,
        re.IGNORECASE,
    )


def test_synthetic_full_lesson_evidence_is_explicitly_test_only_and_redacted(
    tmp_path,
):
    root = tmp_path / "synthetic-evidence"
    write_synthetic_full_lesson_evidence_tree(root)
    assembled = subprocess.run(
        [
            "node",
            str(FULL_LESSON_ASSEMBLER_PATH),
            "--write",
            "--root",
            str(root),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert assembled.returncode == 0, assembled.stdout + assembled.stderr

    evidence_files = sorted(
        path
        for path in (root / "evidence/full-lesson").rglob("*")
        if path.is_file()
    )
    combined_text = "\n".join(
        path.read_text(encoding="utf-8") for path in evidence_files
    )
    assert "synthetic-test-only" in combined_text
    assert "/Users/" not in combined_text
    assert "pairingCode" not in combined_text
    assert "authorization" not in combined_text.lower()
    assert not re.search(r'"token"\s*:', combined_text, re.IGNORECASE)
    assert not re.search(
        r"Bearer\s+[A-Za-z0-9._~-]+", combined_text, re.IGNORECASE
    )


def test_shot_32_evidence_preserves_unicode_wrapping_and_versioning():
    audit = load_json(SHOT_32_AUDIT_PATH)

    assert audit["comp"]["name"] == "S001_SH32_Repo_PreparationNotLearning_v001"
    assert audit["comp"]["width"] == 1920
    assert audit["comp"]["height"] == 1080
    assert audit["comp"]["fps"] == 30
    assert audit["comp"]["durationSeconds"] == 28
    assert audit["comp"]["durationFrames"] == 840
    assert "duration" not in audit["comp"]
    texts = {layer["name"]: layer["text"] for layer in audit["layers"] if layer["type"] == "text"}
    assert texts["MODEL_Parameters"] == "θ"
    assert "·" in texts["TXT_Caveat"]
    assert audit["textChecks"]["TXT_Title"]["lineCount"] == audit["reference"]["TXT_Title"]["lineCount"]
    assert audit["hardChecks"]["thetaResolvedFont"] == "Inter-Regular"
    assert audit["textChecks"]["MODEL_Parameters"]["fauxBold"] is True
    assert audit["textChecks"]["TXT_Deck"]["fauxBold"] is False
    assert audit["hardChecks"]["nativeCount"] == 30
    assert audit["hardChecks"]["rasterCount"] == 0
    assert audit["hardChecks"]["compDurationSeconds"] is True
    assert audit["hardChecks"]["compDurationFrames"] is True
    assert audit["hardChecks"]["recursiveDurationsExact"] is True
    assert audit["duplicate"] == {
        "status": "DUPLICATE_CONTENT",
        "itemCountBefore": 10,
        "itemCountAfter": 10,
    }
    assert audit["changed"]["createdCompNames"] == [
        "S001_SH32_Repo_PreparationNotLearning_v002"
    ]
    assert audit["v001Immutable"] is True
    assert audit["mutatedPreexistingItems"] == []


def test_shot_32_summaries_are_deterministically_derived_from_raw_evidence():
    assert SHOT_32_ASSEMBLER_PATH.is_file(), "the deterministic evidence assembler is missing"
    verification = subprocess.run(
        ["node", str(SHOT_32_ASSEMBLER_PATH), "--verify"],
        cwd=EXPORTER_DIR,
        text=True,
        capture_output=True,
        check=False,
    )
    assert verification.returncode == 0, verification.stdout + verification.stderr

    package_path = SHOT_32_RAW_DIR / "shot-32-package.video001-ae.json"
    changed_package_path = SHOT_32_RAW_DIR / "shot-32-changed-package.video001-ae.json"
    result_path = SHOT_32_RAW_DIR / "shot-32-final-result.json"
    before_path = SHOT_32_RAW_DIR / "shot-32-v001-before.json"
    after_path = SHOT_32_RAW_DIR / "shot-32-v001-after.json"
    v002_path = SHOT_32_RAW_DIR / "shot-32-v002.json"
    timing_path = SHOT_32_RAW_DIR / "shot-32-timing.json"
    metrics_path = SHOT_32_RAW_DIR / "shot-32-image-metrics.json"
    manifest_path = SHOT_32_RAW_DIR / "shot-32-evidence-manifest.json"
    for path in [
        package_path,
        changed_package_path,
        result_path,
        before_path,
        after_path,
        v002_path,
        timing_path,
        metrics_path,
        manifest_path,
    ]:
        assert path.is_file(), f"missing raw evidence: {path.name}"

    package = load_json(package_path)
    changed_package = load_json(changed_package_path)
    result = load_json(result_path)
    before = load_json(before_path)
    after = load_json(after_path)
    v002 = load_json(v002_path)
    timing = load_json(timing_path)
    metrics = load_json(metrics_path)
    manifest = load_json(manifest_path)
    reference = load_json(SHOT_32_REFERENCE_PATH)
    audit = load_json(SHOT_32_AUDIT_PATH)
    comparison = load_json(SHOT_32_COMPARISON_PATH)

    for relative_path, expected_hash in manifest["sha256"].items():
        assert sha256_path(EXPORTER_DIR / relative_path) == expected_hash

    fingerprint_value = {**package, "exportedAt": "", "contentHash": ""}
    computed_content_hash = hashlib.sha256(
        canonical_json(fingerprint_value).encode("utf-8")
    ).hexdigest()
    assert package["contentHash"] == computed_content_hash
    assert package["schemaVersion"] == "2.0.0"
    assert reference["contentHash"] == computed_content_hash
    assert reference["packageSha256"] == sha256_path(package_path)
    assert reference["timingSha256"] == sha256_path(timing_path)

    expected_changed_package = json.loads(json.dumps(package))
    changed_background = next(
        node
        for node in expected_changed_package["frames"][0]["children"]
        if node["id"] == "95:45"
    )
    assert changed_background["name"] == "BG_Base"
    assert changed_background["opacity"] == 1
    changed_background["opacity"] = 0.999999
    changed_fingerprint = {
        **expected_changed_package,
        "exportedAt": "",
        "contentHash": "",
    }
    changed_content_hash = hashlib.sha256(
        canonical_json(changed_fingerprint).encode("utf-8")
    ).hexdigest()
    expected_changed_package["contentHash"] = changed_content_hash
    assert changed_package == expected_changed_package
    assert v002["contentHash"] == changed_content_hash
    assert v002["comp"] == {
        "name": "S001_SH32_Repo_PreparationNotLearning_v002",
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "durationSeconds": 28,
        "durationFrames": 840,
    }
    assert audit["changedPackage"] == {
        "contentHash": changed_content_hash,
        "sha256": sha256_path(changed_package_path),
        "delta": {
            "nodeId": "95:45",
            "nodeName": "BG_Base",
            "property": "opacity",
            "before": 1,
            "after": 0.999999,
        },
    }
    assert audit["v002"]["contentHash"] == changed_content_hash
    assert audit["hardChecks"]["changedPackageCanonical"] is True
    assert audit["hardChecks"]["changedPackageExactDelta"] is True
    assert audit["hardChecks"]["v002ContentHashExact"] is True
    assert audit["hardChecks"]["v002DurationSeconds"] is True
    assert audit["hardChecks"]["v002DurationFrames"] is True
    assert audit["hardChecks"]["v002RecursiveDurationsExact"] is True

    frame = package["frames"][0]
    flattened_nodes = flatten_package_nodes(frame["children"])
    assert reference["frame"]["nodes"] == flattened_nodes
    assert reference["frame"]["nodeId"] == frame["nodeId"] == "95:44"
    assert reference["frame"]["name"] == frame["name"]
    assert package["target"]["timeUnit"] == "seconds"
    assert timing["canvas"]["timeUnit"] == "seconds"
    assert reference["frame"]["durationSeconds"] == frame["duration"] == 28
    timing_shot = next(shot for shot in timing["shots"] if shot["figmaNodeId"] == frame["nodeId"])
    assert timing["source"]["figmaFileKey"] == package["source"]["fileKey"]
    assert timing["source"]["figmaPageNodeId"] == package["source"]["pageId"]
    assert timing_shot["name"] == frame["name"]
    assert timing_shot["duration"] == frame["duration"]
    assert reference["frame"]["nativeNodeCount"] == len(flattened_nodes) == 30
    assert reference["frame"]["rasterNodeCount"] == sum(
        node["kind"] == "raster" for node in flattened_nodes
    ) == 0

    assert stable_v001_audit(before) == stable_v001_audit(after)
    for key in [
        "comp",
        "layers",
        "precompHierarchy",
        "contentHash",
        "missingFonts",
        "rasterFallbacks",
        "warnings",
    ]:
        assert audit[key] == after[key]

    payload = result["payload"]
    assert result["status"] == "COMPLETE"
    assert audit["original"] == payload["original"]
    assert audit["duplicate"] == {
        "status": payload["duplicate"]["status"],
        "itemCountBefore": payload["duplicate"]["itemCountBefore"],
        "itemCountAfter": payload["duplicate"]["itemCountAfter"],
    }
    assert audit["duplicateDetails"] == {
        "v001Count": payload["duplicate"]["v001Count"],
        "v002CountBeforeChangedImport": payload["duplicate"]["v002Count"],
        "queueCountAfter": payload["duplicate"]["queueCountAfter"],
    }
    assert audit["changed"] == payload["changed"]
    assert audit["textChecks"] == payload["textChecks"]
    assert audit["duplicate"]["status"] == "DUPLICATE_CONTENT"
    assert audit["duplicate"]["itemCountBefore"] == audit["duplicate"]["itemCountAfter"]
    assert audit["changed"]["createdCompNames"] == [
        "S001_SH32_Repo_PreparationNotLearning_v002"
    ]
    assert audit["v001Immutable"] is True
    assert audit["hardChecks"]["v001Immutable"] is True
    assert audit["mutatedPreexistingItems"] == payload["mutatedPreexistingItems"] == []

    texts = {layer["name"]: layer["text"] for layer in after["layers"] if layer["type"] == "text"}
    assert texts["MODEL_Parameters"] == "θ"
    assert "·" in texts["TXT_Caveat"]
    assert payload["textChecks"]["TXT_Title"]["lineCount"] == reference["expected"]["TXT_Title"]["lineCount"]
    assert payload["textChecks"]["MODEL_Parameters"]["fauxBold"] is True
    assert payload["textChecks"]["TXT_Deck"]["fauxBold"] is False
    assert payload["original"]["nativeCount"] == len(flattened_nodes)
    assert payload["original"]["rasterCount"] == 0

    figma_path = EXPORTER_DIR / "evidence/shot-32-figma.png"
    ae_path = EXPORTER_DIR / "evidence/shot-32-ae.png"
    assert png_dimensions(figma_path) == png_dimensions(ae_path) == (1920, 1080)
    assert comparison["figma"]["sha256"] == sha256_path(figma_path)
    assert comparison["afterEffects"]["sha256"] == sha256_path(ae_path)
    assert comparison["pixelDiagnostics"] == metrics["pixelDiagnostics"]


def test_shot_32_verifier_rejects_summary_falsification_and_raw_byte_drift(tmp_path):
    isolated_exporter = tmp_path / "exporter"
    shutil.copytree(EXPORTER_DIR / "evidence", isolated_exporter / "evidence")
    (isolated_exporter / "tests/fixtures").mkdir(parents=True)
    shutil.copy2(
        SHOT_32_REFERENCE_PATH,
        isolated_exporter / "tests/fixtures/shot-32-reference.json",
    )

    def verify():
        return subprocess.run(
            [
                "node",
                str(SHOT_32_ASSEMBLER_PATH),
                "--verify",
                "--root",
                str(isolated_exporter),
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    assert verify().returncode == 0

    isolated_audit_path = isolated_exporter / "evidence/shot-32-audit.json"
    falsified_audit = load_json(isolated_audit_path)
    falsified_audit["hardChecks"]["nativeCount"] = 999
    isolated_audit_path.write_text(
        json.dumps(falsified_audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    assert verify().returncode != 0

    shutil.copy2(SHOT_32_AUDIT_PATH, isolated_audit_path)
    isolated_package_path = (
        isolated_exporter / "evidence/raw/shot-32-package.video001-ae.json"
    )
    isolated_package_path.write_bytes(isolated_package_path.read_bytes() + b"\n")
    assert verify().returncode != 0


def test_shot_32_live_plugin_bridge_ae_evidence_is_raw_and_redacted():
    live_session_path = SHOT_32_RAW_DIR / "shot-32-live-session.json"
    live_package_path = SHOT_32_RAW_DIR / "shot-32-live-package.video001-ae.json"
    live_bridge_log_path = SHOT_32_RAW_DIR / "shot-32-live-bridge-log.jsonl"
    live_import_report_path = SHOT_32_RAW_DIR / "shot-32-live-import-report.json"
    live_v002_import_report_path = (
        SHOT_32_RAW_DIR / "shot-32-live-v002-import-report.json"
    )
    changed_package_path = (
        SHOT_32_RAW_DIR / "shot-32-changed-package.video001-ae.json"
    )
    v002_audit_path = SHOT_32_RAW_DIR / "shot-32-v002.json"
    live_ae_result_path = SHOT_32_RAW_DIR / "shot-32-live-ae-result.json"
    for path in [
        live_session_path,
        live_package_path,
        live_bridge_log_path,
        live_import_report_path,
        live_v002_import_report_path,
        changed_package_path,
        v002_audit_path,
        live_ae_result_path,
    ]:
        assert path.is_file(), f"missing live-path evidence: {path.name}"

    combined_raw_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            live_session_path,
            live_package_path,
            live_bridge_log_path,
            live_import_report_path,
            live_v002_import_report_path,
            changed_package_path,
            v002_audit_path,
            live_ae_result_path,
        ]
    )
    assert "/Users/" not in combined_raw_text
    assert "pairingCode" not in combined_raw_text
    assert "authorization" not in combined_raw_text.lower()
    assert not re.search(r'"token"\s*:', combined_raw_text, re.IGNORECASE)
    assert not re.search(r'Bearer\s+[A-Za-z0-9._~-]+', combined_raw_text, re.IGNORECASE)

    package = load_json(live_package_path)
    session = load_json(live_session_path)
    import_report = load_json(live_import_report_path)
    v002_import_report = load_json(live_v002_import_report_path)
    changed_package = load_json(changed_package_path)
    v002_audit = load_json(v002_audit_path)
    ae_result = load_json(live_ae_result_path)
    bridge_events = [
        json.loads(line)
        for line in live_bridge_log_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    fingerprint_value = {**package, "exportedAt": "", "contentHash": ""}
    computed_content_hash = hashlib.sha256(
        canonical_json(fingerprint_value).encode("utf-8")
    ).hexdigest()
    assert session["buildArtifacts"] == {
        "panelSha256": "798153d8137803e0b20a1dace0613598ffa4e0bdac7f817916d542d32999265b",
        "timingSha256": "4f649953f632585e531fba318caba75dd5232414f61e25b37cec76a2c1a1eb87",
        "bridgeSha256": "0f27fb5406607fa69d925e7184c150a5843b6b1f30e664f53e4222cd3dc78c10",
        "figmaCodeSha256": "b40165d475cf70206b8a3c8f8f8a4a1e6875f8be3207ffa9b52d3b96eb77f4f2",
        "figmaUiSha256": "3dcc621d8e5f400801ef782f5d1bfa71565cbd1f3286cff95bbdb48d5b871c51",
    }

    assert package["contentHash"] == computed_content_hash
    assert package["schemaVersion"] == "2.0.0"
    assert package["source"] == {"fileKey": "fFTux3sx2AzVQtoya67f95", "pageId": "90:2"}
    assert package["target"]["timeUnit"] == "seconds"
    assert package["frames"][0]["nodeId"] == "95:44"
    assert package["frames"][0]["name"] == "S001_SH32_Repo_PreparationNotLearning"
    assert package["frames"][0]["duration"] == 28
    assert session["figma"]["selection"] == {
        "count": 1,
        "nodeId": "95:44",
        "name": "S001_SH32_Repo_PreparationNotLearning",
    }
    assert session["figma"]["build"] == {
        "status": "PACKAGE_READY",
        "schemaVersion": "2.0.0",
        "timeUnit": "seconds",
        "durationSeconds": 28,
        "contentHash": computed_content_hash,
        "nativeCount": 30,
        "rasterCount": 0,
    }
    assert session["figma"]["pair"] == {"httpStatus": 200, "code": "PAIRED"}
    assert session["figma"]["sends"] == [
        {
            "httpStatus": 202,
            "code": "EXPORT_ACCEPTED",
            "contentHash": computed_content_hash,
        },
        {
            "httpStatus": 202,
            "code": "EXPORT_ACCEPTED",
            "contentHash": computed_content_hash,
        },
    ]
    assert any(event["route"] == "pair" and event["status"] == 200 for event in bridge_events)
    assert sum(
        event["route"] == "export" and event["status"] == 202
        for event in bridge_events
    ) >= 2
    assert import_report["contentHash"] == computed_content_hash
    assert import_report["createdCompNames"] == [
        "S001_SH32_Repo_PreparationNotLearning_v001"
    ]
    changed_fingerprint = {
        **changed_package,
        "exportedAt": "",
        "contentHash": "",
    }
    changed_content_hash = hashlib.sha256(
        canonical_json(changed_fingerprint).encode("utf-8")
    ).hexdigest()
    assert changed_package["contentHash"] == changed_content_hash
    assert v002_import_report["contentHash"] == changed_content_hash
    assert v002_import_report["createdCompNames"] == [
        "S001_SH32_Repo_PreparationNotLearning_v002"
    ]
    assert v002_audit["contentHash"] == changed_content_hash
    assert v002_audit["comp"]["durationSeconds"] == 28
    assert v002_audit["comp"]["durationFrames"] == 840
    assert ae_result["status"] == "COMPLETE"
    assert ae_result["payload"]["schemaVersion"] == "2.0.0"
    assert ae_result["payload"]["timeUnit"] == "seconds"
    assert ae_result["payload"]["originalContentHash"] == computed_content_hash
    assert ae_result["payload"]["changedContentHash"] == changed_content_hash
    assert ae_result["payload"]["duplicateStatus"] == "DUPLICATE_CONTENT"
    assert ae_result["payload"]["itemCountAfterFirst"] == ae_result["payload"]["itemCountAfterDuplicate"]
    assert ae_result["payload"]["compNames"] == [
        "S001_SH32_Repo_PreparationNotLearning_v001",
        "S001_SH32_Repo_PreparationNotLearning_v002",
    ]
    assert ae_result["payload"]["durations"] == {
        "v001": {"seconds": 28, "frames": 840},
        "v002": {"seconds": 28, "frames": 840},
    }


def test_after_effects_sources_forbid_destructive_project_and_process_calls():
    prohibited_literals = [
        "WRAP_SLACK",
        "CloseOptions.DO_NOT_SAVE_CHANGES",
        "app.project.close",
        "app.project.save",
        "app.quit",
        "killall",
        "pkill",
        "taskkill",
    ]

    for path, source in ae_sources().items():
        for prohibited in prohibited_literals:
            assert prohibited not in source, f"{path.name} contains prohibited {prohibited!r}"
        assert re.search(r"width\s*\*\s*1\.5", source) is None


def test_import_core_remains_es3_compatible():
    source = CORE_PATH.read_text(encoding="utf-8")
    prohibited_patterns = {
        "let declarations": r"\blet\s+[$A-Za-z_]",
        "const declarations": r"\bconst\s+[$A-Za-z_]",
        "arrow functions": r"=>",
        "classes": r"\bclass\s+[$A-Za-z_]",
        "template literals": r"`",
        "optional chaining": r"\?\.",
        "nullish coalescing": r"\?\?",
        "Node globals": r"\b(?:require|module|exports|process|Buffer|global)\b",
        "Array prototype additions": r"Array\.prototype\.",
    }

    for description, pattern in prohibited_patterns.items():
        assert re.search(pattern, source) is None, f"import core contains {description}"


def test_import_core_avoids_the_ae_regex_literal_parser_failure_for_path_separators():
    source = CORE_PATH.read_text(encoding="utf-8")

    assert 'split(/[\\\\/]+/)' not in source
    assert 'replace(new RegExp("\\\\\\\\", "g"), "/").split("/")' in source


def test_importer_avoids_the_ae_regex_literal_parser_failure_for_base64_slashes():
    source = IMPORTER_PATH.read_text(encoding="utf-8")

    assert '!/^(?:[A-Za-z0-9+/]{4})*' not in source
    assert 'new RegExp("^(?:[A-Za-z0-9+/]{4})*' in source


def test_import_core_uses_exact_three_digit_versions_with_a_v999_ceiling():
    source = CORE_PATH.read_text(encoding="utf-8")

    assert "_v([0-9]{3})$" in source
    assert re.search(r"(?:>=|===?)\s*999", source)
    assert "_v999" in source


def test_after_effects_sources_retain_clean_apache_provenance():
    for path, source in ae_sources().items():
        assert "AEUX" in source, f"{path.name} is missing AEUX attribution"
        assert "Apache License, Version 2.0" in source
        assert re.search(r"\bmodified\b", source, re.IGNORECASE)
        assert "DISKO" not in source.upper()


def test_bundled_panel_contains_native_import_and_utf8_report_primitives():
    bundled_panel = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [CORE_PATH, IMPORTER_PATH, PANEL_PATH]
    )

    for required in [
        'app.beginUndoGroup("Import Video 001 Figma Frame")',
        'app.project.items.addFolder("01_Exporter_Imports")',
        "comp.layers.addBoxText([textBox.width, textBox.height]",
        'property("ADBE Text Document")',
        'contents.addProperty("ADBE Vector Shape - Rect")',
        'contents.addProperty("ADBE Vector Shape - Ellipse")',
        'File.encoding = "UTF-8"',
        "Video001Export sha256:",
    ]:
        assert required in bundled_panel


def test_import_rollback_removes_only_current_transaction_items_in_reverse_order():
    importer = IMPORTER_PATH.read_text(encoding="utf-8")

    assert "transactionItems[transactionItems.length] =" in importer
    assert re.search(
        r"for\s*\(\s*transactionIndex\s*=\s*transactionItems\.length\s*-\s*1\s*;"
        r"\s*transactionIndex\s*>=\s*0\s*;\s*transactionIndex\s*-=\s*1\s*\)",
        importer,
    )
    assert "transactionItems[transactionIndex].remove()" in importer
    assert re.search(r"app\.project\.items\s*\[[^\]]+\]\s*\.remove\s*\(", importer) is None


def test_full_lesson_master_is_canonical_transactional_and_auditable():
    core = CORE_PATH.read_text(encoding="utf-8")
    importer = IMPORTER_PATH.read_text(encoding="utf-8")
    audit = AUDIT_PATH.read_text(encoding="utf-8")
    full_audit = FULL_LESSON_AUDIT_SOURCE_PATH.read_text(encoding="utf-8")
    harness = HOST_RUNTIME_TEST_PATH.read_text(encoding="utf-8")

    assert "createdMasterCompName" in core
    for required in [
        "packageObject.isFullLesson",
        "timing.shots[index].nodeId",
        "Full-lesson package frames must preserve canonical shot order",
        "function createFullLessonMaster",
        '"VIDEO001_MASTER"',
        "layer.startTime = shot.start",
        "layer.inPoint = shot.start",
        "layer.outPoint = shot.start + shot.duration",
        "state.createdMasterCompName = masterName",
    ]:
        assert required in importer
    create_master = importer[
        importer.index("function createFullLessonMaster"):
        importer.index("function reportFileFor")
    ]
    assert "rememberItem(" in create_master
    assert re.search(
        r"for\s*\(\s*index\s*=\s*importedFrames\.length\s*-\s*1\s*;"
        r"\s*index\s*>=\s*0\s*;\s*index\s*-=\s*1\s*\)",
        create_master,
    )
    for timing_field in ["result.startTime", "result.inPoint", "result.outPoint"]:
        assert timing_field in audit
    for required in [
        "full-lesson-audit.json",
        "VIDEO001_MASTER_v",
        "Video001Export sha256:",
        "Figma recursive precomp ",
        'property("ADBE Transform Group")',
        "projectStateUnchanged",
        "cyclic precomp reference",
    ]:
        assert required in full_audit
    for prohibited in [
        ".setValue(",
        ".remove(",
        "app.project.save",
        "app.project.close",
        "app.endUndoGroup",
        "app.beginUndoGroup",
    ]:
        assert prohibited not in full_audit
    for behavior in [
        "exact canonical 48-frame lesson",
        "reordered 48-frame lesson",
        "duplicated node ID in a 48-frame lesson",
        "missing configured shot",
        "master layer creation fails",
        "unchanged full-lesson resend",
        "partial selected-frame import",
        "records timing only for precomp layers",
    ]:
        assert behavior in harness


def test_live_duplicate_evidence_capture_is_guarded_and_ae_authored():
    source = DUPLICATE_EVIDENCE_CAPTURE_PATH.read_text(encoding="utf-8")

    for required in [
        "/private/tmp/Video001-Exporter-Full-Lesson.aep",
        "/private/tmp/video001-full-lesson-duplicate-witness.json",
        "Video001ExporterImporter.importPackageFile",
        'result.status !== "DUPLICATE_CONTENT"',
        "before.itemCount !== after.itemCount",
        "!sameJson(before.items, after.items)",
        "full-lesson-duplicate-result.json",
        "full-lesson-post-resend-audit.json",
        'generator: "After Effects " + String(app.version)',
        "file.alias === true",
        "file.parent.fsName !== rawDirectory.fsName",
        "Raw evidence ancestor chain",
        "cursor.fsName !== exporterRoot.fsName",
        "temporaryEvidenceFile",
        "fileSha256",
        "/usr/bin/shasum -a 256 ",
        ".rename(",
    ]:
        assert required in source
    for prohibited in [
        "app.project.items.add",
        "app.project.save",
        "app.project.close",
        "allowDuplicate: true",
    ]:
        assert prohibited not in source


def test_animated_lesson_delivery_is_guarded_layered_and_auditable():
    assert MOTION_SPEC_PATH.is_file()
    assert ANIMATE_FULL_LESSON_PATH.is_file()
    assert AUDIT_ANIMATED_LESSON_PATH.is_file()
    assert MOTION_PROVENANCE_PATH.is_file()

    animation = ANIMATE_FULL_LESSON_PATH.read_text(encoding="utf-8")
    audit = AUDIT_ANIMATED_LESSON_PATH.read_text(encoding="utf-8")
    provenance = MOTION_PROVENANCE_PATH.read_text(encoding="utf-8")
    motion_spec = MOTION_SPEC_PATH.read_text(encoding="utf-8")

    for required in [
        "/private/tmp/Video001-Exporter-Full-Lesson.aep",
        "VIDEO001_MASTER_v001",
        "VIDEO001_ANIMATED_MASTER_v001",
        "_ANIM_v001",
        "transitionFrames: 12",
        "staggerSeconds: 0.06",
        "maxTravelPx: 24",
        "entryScalePercent: 96",
        "maxOvershootPercent: 102",
        "duplicate()",
        "setValueAtTime",
        "KeyframeEase",
        "app.beginUndoGroup",
        "app.endUndoGroup",
        "video-001-figma-exported-source-import.aep",
        "video-001-figma-exported-animated.aep",
        "property.propertyValueType === PropertyValueType.TwoD",
        "property.propertyValueType === PropertyValueType.ThreeD",
        "rollbackBuild",
        "projectRestored",
        "restoreRelinkedAssets",
        "writeJsonAtomically",
        "expectedOutputRoot",
        "assertSafeOutputAncestors",
        "trustedPackageSha256",
        "sourceVisualSha256",
        "assertCompMatchesFrame",
    ]:
        assert required in animation
    assert animation.index("app.project.save(animatedAep)") < animation.index(
        "writeJsonAtomically(reportFile"
    )
    source_save = animation.index("app.project.save(sourceAep)")
    source_track = animation.index("] = sourceAep;")
    source_failure = animation.index(
        'throw new Error("Source-import AEP was not saved completely")'
    )
    assert source_track < source_save < source_failure
    animated_save = animation.index("app.project.save(animatedAep)")
    animated_track = animation.index("] = animatedAep;")
    animated_failure = animation.index(
        'throw new Error("Animated AEP was not saved completely")'
    )
    assert animated_track < animated_save < animated_failure
    assert "finally" in animation[animation.index("function animateShot"):animation.index(
        "function buildAnimatedMaster"
    )]
    for prohibited in [
        "VIDEO001_MASTER_v001.remove",
        "app.project.close",
        "CloseOptions.DO_NOT_SAVE_CHANGES",
        "writeUtf8(reportFile",
    ]:
        assert prohibited not in animation
    for required in [
        "48",
        "840",
        "25200",
        "VIDEO001_ANIMATED_MASTER_v001",
        "projectStateUnchanged",
        "maxTravelPx",
        "maxOvershootPercent",
        "sourceMasterUnchanged",
        "canonicalJson(property.keyValue(1))",
        "canonicalJson(entry.scale.start)",
        "canonicalJson(property.keyValue(2))",
        "canonicalJson(entry.scale.overshoot)",
        "entry.scale.overshootTime",
        "discoverExpectedRevealLayers",
        "selectExpectedHero",
        "assertExactAnimatedLayerCoverage",
        "assertNoUnexpectedAnimation",
        "keyInInterpolationType",
        "keyOutInterpolationType",
        "keyInTemporalEase",
        "keyOutTemporalEase",
        "contentHashFromMaster",
        "assertSafeOutputAncestors",
        "trustedPackageSha256",
        "sourceVisualSha256",
        "assertCompMatchesFrame",
    ]:
        assert required in audit
    for prohibited in [
        ".setValue(",
        ".setValueAtTime(",
        ".remove(",
        "app.project.save",
        "app.beginUndoGroup",
    ]:
        assert prohibited not in audit
    for required in [
        "Source Text",
        "ADBE Vector Fill Color",
        "ADBE Vector Rect Size",
        "static position",
        "Animated-layer source differs",
        "propertyTreeFingerprint",
        "sha256Utf8",
    ]:
        assert required in provenance
    for phrase in [
        "12 frames",
        "60 ms",
        "24 px",
        "96%",
        "102%",
        "48 shot",
        "14-minute",
        "No voice-over",
    ]:
        assert phrase in motion_spec


def test_manual_raster_assets_are_verified_before_content_addressed_import():
    importer = IMPORTER_PATH.read_text(encoding="utf-8")

    assert "asset.dataBase64" in importer
    assert 'system.callSystem("/usr/bin/shasum -a 256 "' in importer
    assert 'asset.hash + ".png"' in importer


def test_importer_uses_concrete_ae_item_classes_and_host_valid_range_selector_paths():
    importer = IMPORTER_PATH.read_text(encoding="utf-8")

    assert "instanceof Item" not in importer
    for concrete_item in ["FolderItem", "CompItem", "FootageItem"]:
        assert f"item instanceof {concrete_item}" in importer
    assert 'selector.property("ADBE Text Range Advanced")' in importer
    assert 'property("ADBE Text Range Units")' in importer
    assert 'selector.property("ADBE Text Index Start")' in importer
    assert 'selector.property("ADBE Text Index End")' in importer


def test_paragraph_text_geometry_uses_the_actual_box_origin_and_size():
    importer = IMPORTER_PATH.read_text(encoding="utf-8")

    assert "documentValue.boxTextPos" in importer
    assert re.search(r"anchorX\s*=\s*boxTextPos\[0\]\s*\+\s*rect\.width\s*/\s*2", importer)
    assert re.search(r"anchorY\s*=\s*boxTextPos\[1\]\s*\+\s*rect\.height\s*/\s*2", importer)
    assert 'setValue([anchorX, anchorY])' in importer


def test_text_resets_inherited_ae_style_state_before_applying_figma_runs():
    importer = IMPORTER_PATH.read_text(encoding="utf-8")
    add_text = importer[
        importer.index("function addText"):
        importer.index("function addFillAndStroke")
    ]

    reset_character = add_text.index("documentValue.resetCharStyle();")
    reset_paragraph = add_text.index("documentValue.resetParagraphStyle();")
    set_text = add_text.index("documentValue.text = node.text;")
    set_font = add_text.index("applyResolvedFont(documentValue, dominantResolved);")
    assert reset_character < set_text
    assert reset_paragraph < set_text
    assert set_text < set_font


def test_package_identity_and_every_asset_are_preflighted_before_project_mutation():
    importer = IMPORTER_PATH.read_text(encoding="utf-8")
    import_file_body = importer[importer.index("function importPackageFile"):]

    identity_check = import_file_body.index("verifyPackageFileIdentity")
    import_call = import_file_body.index("importValidatedPackage(")
    assert identity_check < import_call
    assert "referencedAssets[asset.hash]" not in importer[importer.index("for (index = 0; index < assets.length; index += 1) {", importer.index("function validatePackage"),):importer.index("packageObject.assetByHash")]
    assert "verifyManualContentFingerprint" in importer


def test_public_file_import_derives_queue_identity_from_the_exporter_user_data_root():
    importer = IMPORTER_PATH.read_text(encoding="utf-8")
    identity_body = importer[
        importer.index("function isQueuedPackageFile"):
        importer.index("function importPackageFile")
    ]

    assert 'Folder.userData.fsName + "/Video001FigmaAEExporter"' in importer
    assert "isQueuedPackageFile(packageFile, options.queueRoot" not in importer
    assert "var queueRoot = trustedQueueRoot()" in identity_body


def test_panel_recovers_stale_bridge_state_without_process_wide_signals():
    panel = PANEL_PATH.read_text(encoding="utf-8")

    assert "readLiveBridgeState" in panel
    assert "stateFile.remove()" in panel
    assert panel.count("commandPathContainsBridge") >= 3
    assert "/bin/kill -TERM " in panel
    for prohibited in ["killall", "pkill", "taskkill"]:
        assert prohibited not in panel


def test_ae_host_runtime_harness_and_read_only_audit_guards_are_present():
    assert HOST_RUNTIME_TEST_PATH.is_file()
    harness = HOST_RUNTIME_TEST_PATH.read_text(encoding="utf-8")
    audit = AUDIT_PATH.read_text(encoding="utf-8")

    for behavior in [
        "rolls back only new identities in reverse",
        "public file importer automatically rolls back only its new items in reverse",
        "Advanced index units",
        "box origin for unrotated text",
        "box origin through rotation",
        "queue filename and direct-parent identity",
        "declared asset is verified",
        "stale state for a nonexistent PID",
        "unrelated reused PID",
        "replacement state file that appears during stale-state revalidation",
        "PID is reused by the bridge during stale-state revalidation",
        "cancels its task when closed",
        "read-only audit deeply preserves project, comp, layer, and property state",
        "custom queue roots cannot bypass public package fingerprint verification",
    ]:
        assert behavior in harness
    for prohibited in [
        "app.project.items.add",
        "app.project.importFile",
        "app.project.close",
        "app.project.save",
    ]:
        assert prohibited not in audit
    assert 'fallback.type === "raster-fallback"' in audit


def test_reproducible_source_release_and_operator_runbook_are_required():
    for path in [
        RELEASE_TEST_PATH,
        RELEASE_BUILD_PATH,
        RELEASE_VERIFY_PATH,
        README_PATH,
    ]:
        assert path.is_file(), f"missing release deliverable: {path.name}"

    package = load_json(EXPORTER_DIR / "package.json")
    lock = load_json(EXPORTER_DIR / "package-lock.json")
    controller = (EXPORTER_DIR / "src/figma/controller.ts").read_text(encoding="utf-8")
    assert package["version"] == "0.2.0"
    assert lock["version"] == "0.2.0"
    assert lock["packages"][""]["version"] == "0.2.0"
    assert 'const EXPORTER_VERSION = "0.2.0";' in controller
    assert package["scripts"]["release:build"] == "node scripts/build-release.mjs"
    assert package["scripts"]["release:verify"] == "node scripts/verify-release.mjs"

    release_test = RELEASE_TEST_PATH.read_text(encoding="utf-8")
    for required in [
        "byte-identical deterministic releases",
        "fixed safe ustar metadata",
        "allowlisted source symlinks",
        "independent verifier",
        "versions cannot drift",
        "historical Shot 32 evidence",
    ]:
        assert required in release_test

    readme = README_PATH.read_text(encoding="utf-8")
    prerequisites = readme.index("## Prerequisites")
    workflow = readme.index("## Build and operate")
    assert prerequisites < workflow
    for required in [
        "macOS",
        "Figma desktop",
        "After Effects 25+",
        "Node.js 20+",
        "No Adobe Creative Cloud",
        "npm ci",
        ".figma-plugin-id",
        "npm run build",
        "dist/figma/manifest.json",
        "dist/ae/Video001-Figma-AE-Exporter.jsx",
        "Build full lesson (48 shots)",
        "Import next",
        "DUPLICATE_CONTENT",
        "missing font",
        "raster fallback",
        "npm run release:verify",
    ]:
        assert required in readme
