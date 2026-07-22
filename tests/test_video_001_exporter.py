import re
from pathlib import Path


EXPORTER_DIR = (
    Path(__file__).resolve().parents[1]
    / "course/videos/001-computer-learning-from-text/after-effects/exporter"
)
AE_SOURCE_DIR = EXPORTER_DIR / "src/ae"
CORE_PATH = AE_SOURCE_DIR / "import-core.jsxinc"


def ae_sources() -> dict[Path, str]:
    paths = sorted(
        path
        for path in AE_SOURCE_DIR.rglob("*")
        if path.is_file() and path.suffix in {".jsx", ".jsxinc"}
    )
    assert paths, "the exporter must contain After Effects source files"
    return {path: path.read_text(encoding="utf-8") for path in paths}


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
