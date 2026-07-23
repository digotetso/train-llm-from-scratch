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
HOST_RUNTIME_TEST_PATH = EXPORTER_DIR / "tests/ae-host-runtime.test.ts"
SHOT_32_AUDIT_PATH = EXPORTER_DIR / "evidence/shot-32-audit.json"
SHOT_32_COMPARISON_PATH = EXPORTER_DIR / "evidence/shot-32-comparison.json"
SHOT_32_REFERENCE_PATH = EXPORTER_DIR / "tests/fixtures/shot-32-reference.json"
SHOT_32_RAW_DIR = EXPORTER_DIR / "evidence/raw"
SHOT_32_ASSEMBLER_PATH = EXPORTER_DIR / "scripts/assemble-shot-32-evidence.mjs"


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


def test_shot_32_live_plugin_bridge_ae_evidence_is_raw_and_redacted(tmp_path: Path):
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
    plugin_id_file = tmp_path / ".figma-plugin-id"
    plugin_id_file.write_text("987654321012345678\n", encoding="utf-8")
    build = subprocess.run(
        [
            "node",
            str(EXPORTER_DIR / "scripts/build.mjs"),
            "--plugin-id-file",
            str(plugin_id_file),
        ],
        cwd=EXPORTER_DIR,
        text=True,
        capture_output=True,
        check=False,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    assert session["buildArtifacts"] == {
        "panelSha256": sha256_path(
            EXPORTER_DIR / "dist/ae/Video001-Figma-AE-Exporter.jsx"
        ),
        "timingSha256": sha256_path(EXPORTER_DIR / "dist/ae/figma-scenes.json"),
        "bridgeSha256": sha256_path(
            EXPORTER_DIR / "dist/bridge/video001-bridge.mjs"
        ),
        "figmaCodeSha256": sha256_path(EXPORTER_DIR / "dist/figma/code.js"),
        "figmaUiSha256": sha256_path(EXPORTER_DIR / "dist/figma/ui.html"),
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
