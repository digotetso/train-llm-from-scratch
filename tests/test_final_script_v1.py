import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "course/templates/video/final_script_v1.md"
CHARACTER_PATH = ROOT / "course/templates/video/character_representation.py"
PREPARATION_PATH = ROOT / "course/templates/video/text_preparation.py"
OLD_LAB_PATH = ROOT / "course/templates/video/final_script_v1_lab.py"

EXPECTED_CHARACTER_SOURCE = '''text = "Cat"
print("Text:", text)
print("Code-point numbers:", [ord(character) for character in text])
print("UTF-8 byte numbers:", list(text.encode("utf-8")))

print()

text = "🐱"
print("Text:", text)
print("Code-point numbers:", [ord(character) for character in text])
print("UTF-8 byte numbers:", list(text.encode("utf-8")))'''

EXPECTED_CHARACTER_OUTPUT = """Text: Cat
Code-point numbers: [67, 97, 116]
UTF-8 byte numbers: [67, 97, 116]

Text: 🐱
Code-point numbers: [128049]
UTF-8 byte numbers: [240, 159, 144, 177]"""

EXPECTED_PREPARATION_SOURCE = r'''import unicodedata


def prepare_text(text):
    text = unicodedata.normalize("NFKC", text)
    lines = [line.strip() for line in text.splitlines()]
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines)


source = "  ① cat ﬀ  \r\n\r\n  second line  "

print("Source text:", repr(source))
print("Prepared text:", repr(prepare_text(source)))'''

EXPECTED_PREPARATION_OUTPUT = r"""Source text: '  ① cat ﬀ  \r\n\r\n  second line  '
Prepared text: '1 cat ff\nsecond line'"""


def run_example(path: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=path.parent,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stderr == ""
    return result.stdout


def test_character_example_is_exact_and_runnable():
    assert (
        CHARACTER_PATH.read_text(encoding="utf-8")
        == EXPECTED_CHARACTER_SOURCE + "\n"
    )
    assert run_example(CHARACTER_PATH) == EXPECTED_CHARACTER_OUTPUT + "\n"


def test_character_example_is_embedded_with_local_command_and_output():
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    assert f"```python\n{EXPECTED_CHARACTER_SOURCE}\n```" in script
    assert f"```text\n{EXPECTED_CHARACTER_OUTPUT}\n```" in script
    assert (
        script.count("```bash\npython character_representation.py\n```")
        == 1
    )
    assert "python course/" not in script


def test_preparation_example_is_exact_and_runnable():
    assert (
        PREPARATION_PATH.read_text(encoding="utf-8")
        == EXPECTED_PREPARATION_SOURCE + "\n"
    )
    assert run_example(PREPARATION_PATH) == EXPECTED_PREPARATION_OUTPUT + "\n"


def test_preparation_example_is_embedded_and_old_lab_is_removed():
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    assert f"```python\n{EXPECTED_PREPARATION_SOURCE}\n```" in script
    assert f"```text\n{EXPECTED_PREPARATION_OUTPUT}\n```" in script
    assert script.count("```bash\npython text_preparation.py\n```") == 1
    assert not OLD_LAB_PATH.exists()
