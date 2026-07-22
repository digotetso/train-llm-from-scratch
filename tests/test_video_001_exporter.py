import json
import re
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


def ae_sources() -> dict[Path, str]:
    paths = sorted(
        path
        for path in AE_SOURCE_DIR.rglob("*")
        if path.is_file() and path.suffix in {".jsx", ".jsxinc"}
    )
    assert paths, "the exporter must contain After Effects source files"
    return {path: path.read_text(encoding="utf-8") for path in paths}


def test_shot_32_evidence_preserves_unicode_wrapping_and_versioning():
    audit = json.loads(SHOT_32_AUDIT_PATH.read_text(encoding="utf-8"))

    assert audit["comp"]["name"] == "S001_SH32_Repo_PreparationNotLearning_v001"
    assert audit["comp"]["width"] == 1920
    assert audit["comp"]["height"] == 1080
    assert audit["comp"]["fps"] == 30
    assert audit["comp"]["duration"] == 28
    texts = {layer["name"]: layer["text"] for layer in audit["layers"] if layer["type"] == "text"}
    assert texts["MODEL_Parameters"] == "θ"
    assert "·" in texts["TXT_Caveat"]
    assert audit["textChecks"]["TXT_Title"]["lineCount"] == audit["reference"]["TXT_Title"]["lineCount"]
    assert audit["hardChecks"]["thetaResolvedFont"] == "Inter-Regular"
    assert audit["textChecks"]["MODEL_Parameters"]["fauxBold"] is True
    assert audit["textChecks"]["TXT_Deck"]["fauxBold"] is False
    assert audit["hardChecks"]["nativeCount"] == 30
    assert audit["hardChecks"]["rasterCount"] == 0
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
