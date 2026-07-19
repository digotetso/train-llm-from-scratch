import subprocess
import sys
from pathlib import Path


def test_course_outline_contains_all_64_numbered_videos():
    outline = Path("course/outline.md").read_text(encoding="utf-8")
    numbered = [line for line in outline.splitlines() if line.startswith(tuple(f"{n}. " for n in range(1, 65)))]
    assert len(numbered) == 64
    assert numbered[0].startswith("1. What Does It Mean")
    assert numbered[-1].startswith("64. Building and Teaching")


def test_video_one_has_required_artifacts_and_runnable_lab():
    video_dir = Path("course/videos/001-computer-learning-from-text")
    for name in ["script.md", "lesson.md", "lab.md", "quiz.md", "answer-key.md", "evidence.md", "lab.py"]:
        assert (video_dir / name).is_file(), name
    result = subprocess.run([sys.executable, str(video_dir / "lab.py")], text=True, capture_output=True, check=True)
    assert "Character numbers: [67, 97, 116]" in result.stdout
    assert "UTF-8 bytes: [67, 97, 116]" in result.stdout
