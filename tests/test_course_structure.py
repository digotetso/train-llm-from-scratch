import ast
import re
import subprocess
import sys
from pathlib import Path


EXPECTED_OUTLINE = [
    "1. What Does It Mean for a Computer to Learn From Text?",
    "2. How Computers Store Characters as Agreed Numbers",
    "3. From a Sentence to a Learning Example",
    "4. Unicode Code Points and UTF-8 Bytes",
    "5. Why Visually Similar Text Needs Normalization",
    "6. Spaces, Control Characters, and Practical Cleaning",
    "7. Documents, Corpora, JSON, and JSONL",
    "8. Data-Quality Filters and Rejection Reasons",
    "9. Exact Deduplication and Benchmark Contamination",
    "10. Stable Dataset Splits, Manifests, and Fingerprints",
    "11. Tokens and Token IDs",
    "12. Why Byte-Level Tokenization Works",
    "13. How BPE Learns Frequent Merges",
    "14. Vocabulary Size and Special Tokens",
    "15. Training the Repository Tokenizer",
    "16. Unicode Round Trips and the Complete Byte Alphabet",
    "17. Tokenizer Reports, Compression, and Failure Tests",
    "18. EOS Tokens and Packed Document Streams",
    "19. Binary Shards, Dtypes, and Metadata",
    "20. Memory Mapping and Weighted Shard Sampling",
    "21. Context Windows, Shifted Targets, and Batches",
    "22. Tensors and Shapes Without Fear",
    "23. Turning Token IDs Into Embeddings",
    "24. Why Tokens Need Position Information",
    "25. Tracing Shapes Through the Model",
    "26. Why Tokens Need to Look at Other Tokens",
    "27. Queries, Keys, and Values",
    "28. Dot Products, Scaling, and Attention Softmax",
    "29. Causal Masks and Weighted Value Mixing",
    "30. Heads, Reshaping, Transposing, and Joining",
    "31. RoPE Rotations and Relative Position Math",
    "32. Attention Output Projection",
    "33. Residual Connections",
    "34. RMSNorm",
    "35. MLPs, Activations, and SwiGLU Gates",
    "36. One Complete Block and a Stack of Blocks",
    "37. Logits and Next-Token Probabilities",
    "38. Cross-Entropy Loss With Small Numbers",
    "39. Validation Loss and Perplexity",
    "40. Computation Graphs, Gradients, and the Chain Rule",
    "41. SGD and Learning Rate",
    "42. Momentum, Adam, and AdamW",
    "43. Weight Decay and Optimizer Parameter Groups",
    "44. Warmup, Cosine Decay, and Gradient Accumulation",
    "45. FP32, FP16, and BF16",
    "46. Autocast and Gradient Scaling",
    "47. Gradient Clipping, Underflow, Overflow, Inf, and NaN",
    "48. Skipped Updates and Stability Metrics",
    "49. What a Complete Checkpoint Saves",
    "50. Seeds, RNG State, and Reproducibility",
    "51. Safe Resume and Artifact Compatibility",
    "52. Setting Up Colab, CUDA, and Persistent Drive Storage",
    "53. Estimating Memory and Benchmarking the Batch",
    "54. Running the Preflight and Reading Its Report",
    "55. The Twenty-Step Smoke Test",
    "56. The Ten-Million-Token Pilot and Go/No-Go Review",
    "57. Continuing to 200M Tokens and Surviving Disconnects",
    "58. Evaluating Loss, Perplexity, and Fixed Prompts",
    "59. Reading Samples Without Fooling Yourself",
    "60. Debugging Loss, NaNs, OOM, Repetition, and Resume Failures",
    "61. Scaling Width, Depth, Data, Context, and Compute",
    "62. Designing the 59M-Parameter Experiment",
    "63. Explaining Technical Ideas Without Hidden Jargon",
    "64. Building and Teaching Your Own LLM Pretraining Course",
]

VIDEO_DIR = Path("course/videos/001-computer-learning-from-text")
REQUIRED_VIDEO_FILES = {
    "answer-key.md",
    "evidence.md",
    "lab.md",
    "lab.py",
    "lesson.md",
    "quiz.md",
    "script.md",
}
MODEL_INPUT_PROMPT = "Can the mathematical model use this raw Python string as numeric input? No"

TEMPLATE_HEADINGS = {
    "script.md": [
        "# Video N: Title",
        "## 00:00 Hook",
        "## 00:45 Analogy",
        "## 02:00 Technical Meaning",
        "## 04:00 Tiny Example",
        "## 06:00 Repository Walkthrough",
        "## 09:00 Live Mini-Lab",
        "## 12:00 Common Mistake",
        "## 13:00 Recap And Exercise",
    ],
    "lesson.md": [
        "# Video N: Title",
        "## Prerequisites",
        "## Learning Objective",
        "## Simple Explanation",
        "## Analogy And Its Limitation",
        "## Technical Meaning",
        "## Tiny Math Or Text Example",
        "## Commented Repository Code",
        "## Misconception",
        "## Recap",
    ],
    "lab.md": [
        "# Video N Mini-Lab: Title",
        "## Setup",
        "## Command",
        "## Prediction",
        "## Steps",
        "## Expected Output",
        "## Explanation",
        "## Extension",
    ],
    "quiz.md": ["# Video N Quiz: Title", "## Questions"],
    "answer-key.md": ["# Video N Answer Key: Title", "## Answers", "## Gap Explanations"],
    "evidence.md": [
        "# Video N Evidence: Title",
        "## Repository Anchors",
        "## Commands Run",
        "## Observed Output",
        "## Unverified Claims",
    ],
}

VIDEO_HEADINGS = {
    "script.md": [
        "# Video 1: What Does It Mean for a Computer to Learn From Text?",
        *TEMPLATE_HEADINGS["script.md"][1:],
    ],
    "lesson.md": [
        "# Video 1: What Does It Mean for a Computer to Learn From Text?",
        *TEMPLATE_HEADINGS["lesson.md"][1:],
    ],
    "lab.md": [
        "# Video 1 Mini-Lab: Turn `Cat` Into Agreed Numbers",
        *TEMPLATE_HEADINGS["lab.md"][1:],
    ],
    "quiz.md": [
        "# Video 1 Quiz: What Does It Mean for a Computer to Learn From Text?",
        "## Questions",
    ],
    "answer-key.md": [
        "# Video 1 Answer Key: What Does It Mean for a Computer to Learn From Text?",
        "## Answers",
        "## Gap Explanations",
    ],
    "evidence.md": [
        "# Video 1 Evidence: What Does It Mean for a Computer to Learn From Text?",
        *TEMPLATE_HEADINGS["evidence.md"][1:],
    ],
}

APPROVED_QUIZ_ITEMS = [
    (
        "Does a computer naturally understand `cat` like a human?",
        "No. A program receives represented data, not the experiences and meaning a person brings to the word `cat`.",
        "If the answer says yes, revisit `Simple Explanation`. The missing distinction is between human experience and data received by a program.",
    ),
    (
        'What does `ord("A")` return, and what does that number represent?',
        '`ord("A")` returns `65`. The number is the agreed Unicode number for the character `A`.',
        "If the answer gives a different number or says `65` means a school grade, rerun the mini-lab and revisit `Technical Meaning`. The question asks about an agreed character number, not one possible use of the character.",
    ),
    (
        "Is character number `65` the human meaning of `A`?",
        "No. `65` identifies the character under an agreed representation; it does not contain human meaning.",
        "If the answer says yes, revisit `Analogy And Its Limitation` and `Misconception`. A library identifier helps locate a book without containing its story; character number `65` behaves similarly as an identifier.",
    ),
    (
        "Why must text become numbers before a mathematical model can use it?",
        "A mathematical model works with numbers, so text needs a numeric representation before the model can perform calculations and learn patterns from examples.",
        "If the answer mentions only storage, revisit the final paragraph of `Simple Explanation`. Storage is one reason; the model also needs numbers because its operations are mathematical.",
    ),
    (
        "In one sentence, what does learning mean at this stage?",
        "Learning means adjusting a model's internal numbers so its guesses become less wrong across many examples.",
        "If the answer describes fixed conversion with `ord`, revisit `Technical Meaning`. Representation follows an agreement. Learning requires adjustable internal values that change in response to mistakes across examples.",
    ),
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def headings(markdown: str) -> list[str]:
    found: list[str] = []
    inside_fence = False
    for line in markdown.splitlines():
        if line.startswith("```"):
            inside_fence = not inside_fence
        elif not inside_fence and re.match(r"^#{1,6} ", line):
            found.append(line)
    return found


def section(markdown: str, heading: str) -> str:
    content = markdown.split(f"{heading}\n", maxsplit=1)[1]
    return content.split("\n## ", maxsplit=1)[0]


def numbered_items(markdown: str) -> list[str]:
    return [line for line in markdown.splitlines() if re.match(r"^\d+\. ", line)]


def test_course_outline_matches_exact_approved_sequence_without_duplicates():
    outline = read(Path("course/outline.md"))
    numbered = numbered_items(outline)

    assert numbered == EXPECTED_OUTLINE
    titles = [line.split(". ", maxsplit=1)[1] for line in numbered]
    assert len(titles) == len(set(titles)) == 64


def test_only_video_one_is_fully_produced():
    produced = sorted(path.name for path in Path("course/videos").iterdir() if path.is_dir())
    assert produced == ["001-computer-learning-from-text"]


def test_video_one_has_exact_required_artifacts():
    artifacts = {path.name for path in VIDEO_DIR.iterdir() if path.is_file()}
    assert artifacts == REQUIRED_VIDEO_FILES


def test_video_templates_have_required_headings():
    template_dir = Path("course/templates/video")
    for name, expected in TEMPLATE_HEADINGS.items():
        assert headings(read(template_dir / name)) == expected, name


def test_video_one_artifacts_have_required_headings():
    for name, expected in VIDEO_HEADINGS.items():
        actual = headings(read(VIDEO_DIR / name))
        assert actual[: len(expected)] == expected, name


def test_video_one_uses_approved_quiz_and_aligned_answer_key():
    quiz = read(VIDEO_DIR / "quiz.md")
    answer_key = read(VIDEO_DIR / "answer-key.md")

    expected_questions = [f"{number}. {question}" for number, (question, _, _) in enumerate(APPROVED_QUIZ_ITEMS, 1)]
    expected_answers = [f"{number}. {answer}" for number, (_, answer, _) in enumerate(APPROVED_QUIZ_ITEMS, 1)]
    expected_gaps = [f"{number}. {gap}" for number, (_, _, gap) in enumerate(APPROVED_QUIZ_ITEMS, 1)]

    assert numbered_items(section(quiz, "## Questions")) == expected_questions
    assert numbered_items(section(answer_key, "## Answers")) == expected_answers
    assert numbered_items(section(answer_key, "## Gap Explanations")) == expected_gaps


def test_video_one_lab_is_standard_library_only_and_has_exact_stdout():
    lab_path = VIDEO_DIR / "lab.py"
    tree = ast.parse(read(lab_path))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", maxsplit=1)[0])
    assert imported_roots <= sys.stdlib_module_names

    result = subprocess.run([sys.executable, str(lab_path)], text=True, capture_output=True, check=True)
    assert result.stderr == ""
    assert result.stdout == (
        "Human text: Cat\n"
        "Character numbers: [67, 97, 116]\n"
        "UTF-8 bytes: [67, 97, 116]\n"
        f"{MODEL_INPUT_PROMPT}\n"
        "Learning begins after text is represented as numbers.\n"
    )


def test_video_one_warns_that_nfkc_is_a_non_lossless_cleaning_policy():
    for name in ["script.md", "lesson.md"]:
        content = read(VIDEO_DIR / name)
        lowered = content.lower()
        assert "deliberate cleaning policy" in lowered, name
        assert "not lossless" in lowered, name
        assert "①" in content and "`1`" in content, name
        assert "change character count" in lowered, name
        assert "Video 5" in content, name


def test_video_one_uses_one_precise_raw_string_prompt_everywhere():
    for name in ["script.md", "lesson.md", "lab.md", "lab.py"]:
        assert MODEL_INPUT_PROMPT in read(VIDEO_DIR / name), name


def test_video_one_evidence_matches_the_shown_work():
    evidence = read(VIDEO_DIR / "evidence.md")
    anchors = section(evidence, "## Repository Anchors")
    commands = section(evidence, "## Commands Run")

    assert "uv run pytest tests/test_course_structure.py -v" in commands
    assert "uv run pytest -v" in commands
    assert "**Source fact:**" in anchors
    assert "**Observed code behavior:**" in anchors
    assert "**Teaching analogy:**" in anchors
    assert "exact text of all five approved questions, answers, and gap explanations" in anchors
    assert "control-character removal" not in anchors
    assert "blank-line limiting" not in anchors
