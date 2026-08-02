import json
import os
import re
import subprocess
from pathlib import Path


VIDEO_DIR = Path("course/videos/001-computer-learning-from-text")
AE_DIR = VIDEO_DIR / "after-effects"
MANIFEST_PATH = AE_DIR / "figma-scenes.json"
BUILDER_PATH = AE_DIR / "build-video-001.jsx"
RENDER_SCRIPT_PATH = AE_DIR / "render-sections.sh"

EXPECTED_SHOT_DURATIONS = [
    8, 10, 12, 15,
    13, 14, 16, 15, 17,
    14, 14, 15, 15, 14, 15, 16, 17,
    14, 14, 15, 15, 14, 16, 16, 16,
    22, 26, 24, 26, 27, 27, 28,
    24, 24, 30, 26, 21, 27, 28,
    14, 16, 14, 16,
    12, 16, 14, 12, 6,
]


def load_manifest():
    assert MANIFEST_PATH.exists(), "The AE scene manifest must be generated from Figma"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_preserves_the_forty_eight_figma_shots_and_timing():
    manifest = load_manifest()
    shots = manifest["shots"]
    assert len(shots) == 48
    assert [shot["duration"] for shot in shots] == EXPECTED_SHOT_DURATIONS
    assert sum(shot["duration"] for shot in shots) == 840
    assert shots[0]["name"] == "S001_SH01_Hook_CatWord"
    assert shots[-1]["name"] == "S001_SH48_Recap_NextLesson"
    assert len({shot["name"] for shot in shots}) == 48
    assert len({shot["figmaNodeId"] for shot in shots}) == 48


def test_manifest_uses_the_approved_canvas_palette_and_motion_contract():
    manifest = load_manifest()
    assert manifest["canvas"] == {"width": 1920, "height": 1080, "fps": 30, "duration": 840}
    assert manifest["palette"] == {
        "background": "#0B1020",
        "panel": "#11182D",
        "primary": "#F5F7FB",
        "secondary": "#A8B3CF",
        "fixed": "#35C7FF",
        "model": "#8B5CF6",
        "warning": "#F59E0B",
        "progress": "#22C55E",
    }


def test_builder_embeds_the_current_external_manifest():
    manifest = load_manifest()
    source = BUILDER_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"var EMBEDDED_MANIFEST = (\{.*\});\n\s*var scriptFile =",
        source,
        flags=re.DOTALL,
    )
    assert match, "The AE builder must contain a parseable embedded manifest fallback"
    assert json.loads(match.group(1)) == manifest
    assert manifest["motion"] == {
        "transitionFrames": 12,
        "staggerSeconds": 0.06,
        "maxTravelPx": 24,
        "entryScalePercent": 96,
        "maxOvershootPercent": 102,
    }


def test_scene_primitives_are_native_semantic_and_within_canvas():
    manifest = load_manifest()
    semantic = re.compile(r"^(BG|TXT|CODE|DATA|MODEL|LOSS|PROG|FX|MATTE|GUIDE|CTRL)_")
    primitive_count = 0
    for shot in manifest["shots"]:
        assert shot["elements"], shot["name"]
        for element in shot["elements"]:
            primitive_count += 1
            assert element["kind"] in {"text", "rect", "ellipse", "line"}
            assert semantic.match(element["name"]), element["name"]
            assert -2 <= element["x"] <= 1922
            assert -2 <= element["y"] <= 1082
            assert element["width"] >= 0
            assert element["height"] >= 0
            assert element["x"] + element["width"] <= 1922
            assert element["y"] + element["height"] <= 1082
    assert primitive_count >= 800


def test_manifest_applies_figma_full_width_translation_to_right_aligned_text():
    manifest = load_manifest()
    actual_x = {
        element["name"]: element["x"]
        for shot in manifest["shots"]
        for element in shot["elements"]
        if element["kind"] == "text" and element.get("align") == "right"
    }
    assert actual_x == {
        "TXT_Text_100_47": 1319,
        "DATA_Text_102_98": 1069,
        "MODEL_Text_I102_166_97_64": 1509.44,
        "DATA_Text_104_98": 1517,
        "DATA_Text_104_102": 1517,
        "DATA_Text_104_106": 1517,
        "LOSS_Text_I104_188_97_67": 1259,
        "PROG_Text_104_219": 1257,
        "TXT_Text_105_186": 367,
        "DATA_Text_105_190": 1367,
        "TXT_Text_105_193": 367,
        "DATA_Text_105_197": 1367,
        "TXT_Text_105_200": 367,
        "DATA_Text_105_204": 1367,
    }


def test_manifest_uses_an_arrow_capable_font_for_arrow_bearing_text():
    manifest = load_manifest()
    arrow_elements = [
        element
        for shot in manifest["shots"]
        for element in shot["elements"]
        if element["kind"] == "text" and "→" in element["text"]
    ]
    assert arrow_elements
    assert all(not element["font"].startswith("Sora:") for element in arrow_elements)


def test_builder_declares_project_hygiene_native_layers_and_render_queue():
    source = BUILDER_PATH.read_text(encoding="utf-8")
    for required in [
        "01_Comps",
        "02_Precomps",
        "03_Footage",
        "04_Audio",
        "05_Exports",
        "99_References",
        "CTRL_Master",
        "CTRL_ShotMotion",
        "S001_MASTER_What_AI_Models_Actually_Do",
        "Apple ProRes 422 HQ",
        "app.project.save",
    ]:
        assert required in source
    assert "addText" in source
    assert "addShape" in source
    assert "setValueAtTime" in source


def test_builder_keeps_ae_paragraph_box_anchor_at_its_center_origin():
    source = BUILDER_PATH.read_text(encoding="utf-8")
    add_text = source[source.index("function addText"):source.index("function addSafeGuide")]
    assert 'property("ADBE Anchor Point").setValue([0, 0])' in add_text
    assert "setValue([width / 2, height / 2])" not in add_text


def test_builder_only_closes_its_own_generated_project_before_rebuild():
    source = BUILDER_PATH.read_text(encoding="utf-8")
    assert "app.project.file.fsName === projectFile.fsName" in source
    assert "app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES)" in source
    assert "Open a blank After Effects project before running this builder" in source


def test_section_renderer_fails_preflight_before_aerender_when_disk_is_low(tmp_path):
    env = os.environ.copy()
    env.update(
        {
            "VIDEO001_AERENDER": "/usr/bin/false",
            "VIDEO001_TEMP_ROOT": str(tmp_path),
            "VIDEO001_MIN_FREE_KB": "999999999999",
        }
    )

    result = subprocess.run(
        ["bash", str(RENDER_SCRIPT_PATH)],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "insufficient temporary storage" in result.stderr.lower()
    assert not list(tmp_path.iterdir())


def test_section_renderer_covers_the_complete_fourteen_minute_timeline():
    source = RENDER_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "readonly -a SECTION_IDS=(00 01 02 03 04 05 06 07)" in source
    assert "readonly -a START_FRAMES=(0 1350 3600 7200 10800 16200 21600 23400)" in source
    assert "readonly -a END_FRAMES=(1349 3599 7199 10799 16199 21599 23399 25199)" in source
