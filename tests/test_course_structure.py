import ast
import re
import subprocess
import sys
from pathlib import Path


EXPECTED_OUTLINE = [
    "1. From a Sentence to a Training Example",
    "2. Turning Token IDs Into Embeddings",
    "3. What You Will Build: The Model, Budget, and Training Roadmap",
    "4. Run the Whole Pipeline Once Before Understanding It",
    "5. How Computers Store Characters as Agreed Numbers",
    "6. Unicode Code Points and UTF-8 Bytes",
    "7. Why Visually Similar Text Needs Normalization",
    "8. Inspecting Real Text: Invisible Characters and Cleaning Decisions",
    "9. Tokens and Token IDs",
    "10. Why Byte-Level Tokenization Works",
    "11. How BPE Learns Frequent Merges",
    "12. Vocabulary Size and Special Tokens",
    "13. Training the Repository Tokenizer",
    "14. Unicode Round Trips and the Complete Byte Alphabet",
    "15. Tokenizer Reports, Compression, and Failure Tests",
    "16. EOS Tokens and Packed Document Streams",
    "17. Context Windows, Shifted Targets, and Batches",
    "18. Tensors and Shapes Without Fear",
    "19. What a Parameter Is: Fitting a Line by Hand",
    "20. Linear Layers, Matrix Multiplication, and Nonlinearity",
    "21. One Training Step: Forward, Loss, Backward, Update",
    "22. Logits and Next-Token Probabilities",
    "23. Cross-Entropy Loss With Small Numbers",
    "24. Training a Model Without Attention, and Where It Fails",
    "25. Training Loss, Validation Loss, and Overfitting",
    "26. Why Tokens Need to Look at Other Tokens",
    "27. Queries, Keys, and Values",
    "28. Dot Products, Scaling, and Attention Softmax",
    "29. Causal Masks and Weighted Value Mixing",
    "30. Heads, Reshaping, Transposing, and the Output Projection",
    "31. Why Tokens Need Position Information",
    "32. RoPE Rotations and Relative Position Math",
    "33. Residual Connections and RMSNorm",
    "34. MLPs, Activations, and SwiGLU Gates",
    "35. One Complete Block and a Stack of Blocks",
    "36. Weight Initialization and Tied Embeddings",
    "37. Tracing Shapes and Counting Parameters Through the Whole Model",
    "38. Computation Graphs, Gradients, and the Chain Rule",
    "39. SGD and Learning Rate",
    "40. Momentum, Adam, and AdamW",
    "41. Weight Decay and Optimizer Parameter Groups",
    "42. Warmup, Cosine Decay, and Gradient Accumulation",
    "43. FP32, FP16, and BF16: Choosing Precision for a T4",
    "44. Autocast and Gradient Scaling",
    "45. Clipping, Inf, NaN, and Skipped Updates",
    "46. Documents, Corpora, JSON, and JSONL",
    "47. Choosing a Dataset: License, Provenance, and a Pinned Revision",
    "48. Data-Quality Filters and Rejection Reasons",
    "49. Exact Deduplication and Benchmark Contamination",
    "50. Stable Dataset Splits, Manifests, and Fingerprints",
    "51. Binary Shards, Dtypes, Memory Mapping, and Shard Sampling",
    "52. What a Complete Checkpoint Saves",
    "53. Seeds, RNG State, and Reproducibility",
    "54. Safe Resume and Artifact Compatibility",
    "55. Setting Up Colab, CUDA, and Persistent Drive Storage",
    "56. Estimating Memory and Benchmarking the Batch",
    "57. Running the Preflight and Reading Its Report",
    "58. Tracking a Run: Logs, Metrics, and Experiment Records",
    "59. The Twenty-Step Smoke Test",
    "60. The Ten-Million-Token Pilot and Go/No-Go Review",
    "61. Training to the Configured Token Budget and Surviving Disconnects",
    "62. Greedy Decoding and Why It Repeats",
    "63. Temperature, Top-k, and Top-p Sampling",
    "64. Running the Chat Script and Why Generation Is Slow",
    "65. Evaluating Loss, Perplexity, and Fixed Prompts",
    "66. Multiple-Choice Tasks and Accuracy",
    "67. Reading Samples Without Fooling Yourself",
    "68. Debugging Loss, NaNs, OOM, Repetition, and Resume Failures",
    "69. What a 59M-Parameter Model Can and Cannot Do",
    "70. Token Budgets, Scaling Laws, and Being Under-Trained",
    "71. Scaling Width, Depth, Data, Context, and Compute",
    "72. What Post-Training Would Add: SFT and Chat Templates",
    "73. Designing Your Own Experiment",
    "74. Writing a Model Card and Publishing Your Run",
    "75. Explaining Technical Ideas Without Hidden Jargon",
]

VIDEO_DIR = Path("course/videos/001-computer-learning-from-text")
REQUIRED_VIDEO_FILES = {
    "animation.py",
    "answer-key.md",
    "evidence.md",
    "lab.md",
    "lab.py",
    "lesson.md",
    "manim.cfg",
    "quiz.md",
    "scenes.md",
    "script.md",
}
TITLE = "From a Sentence to a Training Example"
SUPERSEDED_LESSON_FILES = {
    Path("course/video_1_script_2.md"),
    Path("course/video_1_script_3.md"),
    Path("course/video_1_script_4.md"),
    Path("course/templates/video/final_script_v1.md"),
    Path("course/templates/video/character_representation.py"),
    Path("course/templates/video/text_preparation.py"),
}

TEMPLATE_HEADINGS = {
    "script.md": [
        "# Video N: Title",
        "## 00:00 Hook",
        "## 01:10 Intuition",
        "## 02:20 Technical Meaning",
        "## 03:30 Tiny Example",
        "## 05:10 Repository Walkthrough",
        "## 07:20 Live Mini-Lab",
        "## 09:40 Common Mistakes",
        "## 10:50 Recap And Exercise",
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
        "## Primary Sources",
        "## Commands Run",
        "## Observed Output",
        "## Simplifications And Boundaries",
    ],
}

VIDEO_HEADINGS = {
    "script.md": [f"# Video 1: {TITLE}", *TEMPLATE_HEADINGS["script.md"][1:]],
    "lesson.md": [f"# Video 1: {TITLE}", *TEMPLATE_HEADINGS["lesson.md"][1:]],
    "lab.md": [f"# Video 1 Mini-Lab: {TITLE}", *TEMPLATE_HEADINGS["lab.md"][1:]],
    "quiz.md": [f"# Video 1 Quiz: {TITLE}", "## Questions"],
    "answer-key.md": [f"# Video 1 Answer Key: {TITLE}", "## Answers", "## Gap Explanations"],
    "evidence.md": [f"# Video 1 Evidence: {TITLE}", *TEMPLATE_HEADINGS["evidence.md"][1:]],
}

APPROVED_QUIZ_ITEMS = [
    (
        "In the phrase The opposite of hot is cold, what is the input and what is the target at the final cut?",
        "The input is The opposite of hot is, and the target is cold.",
        "If the two parts are reversed, revisit Simple Explanation. The model receives the text before the cut and is evaluated against the recorded word after it.",
    ),
    (
        "Why does this six-word sentence contain five next-token prediction positions in our simplified example?",
        "The first word has no earlier word before it, while each of the other five words can be the recorded next target.",
        "If the answer is six, revisit Tiny Math Or Text Example and ask what input would exist before the first word.",
    ),
    (
        "Does target mean the only sensible or factually correct continuation?",
        "No. The target is the continuation recorded in this training text; other continuations may also be sensible.",
        "If the answer says the target is uniquely correct, revisit Misconception. Training supplies an observed continuation, not proof that every alternative is wrong.",
    ),
    (
        "Why does the lesson use words first even though the repository trains on token IDs?",
        "Words make the shift easy to inspect by hand. The same positional relationship is later applied to token IDs produced by the tokenizer.",
        "If the answer says words are the real model input, revisit Technical Meaning. Words are the visible example; the repository shifts token IDs.",
    ),
    (
        "For window = [7, 20, 4, 2, 6], what are x and y?",
        "x is [7, 20, 4, 2], and y is [20, 4, 2, 6].",
        "If either row is unchanged, revisit Commented Repository Code. x drops the final ID; y drops the first ID.",
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


def lesson_section_headings(markdown: str) -> list[str]:
    return [line for line in headings(markdown) if line.startswith(("# ", "## "))]


def section(markdown: str, heading: str) -> str:
    content = markdown.split(f"{heading}\n", maxsplit=1)[1]
    return content.split("\n## ", maxsplit=1)[0]


def numbered_items(markdown: str) -> list[str]:
    return [line for line in markdown.splitlines() if re.match(r"^\d+\. ", line)]


def test_course_outline_matches_the_new_approved_sequence_without_duplicates():
    numbered = numbered_items(read(Path("course/outline.md")))

    assert numbered == EXPECTED_OUTLINE
    titles = [line.split(". ", maxsplit=1)[1] for line in numbered]
    assert len(titles) == len(set(titles)) == 75


def test_embedding_transition_and_shifted_lesson_references_stay_aligned():
    outline = read(Path("course/outline.md"))
    glossary = read(Path("course/glossary.md"))
    lesson = read(VIDEO_DIR / "lesson.md")

    assert numbered_items(outline)[1] == "2. Turning Token IDs Into Embeddings"
    assert "before embeddings" not in outline.lower()
    assert "**First video:** Video 2" in section(glossary, "## Embedding")
    assert "Lesson 2" in section(lesson, "## Recap")
    technical = section(lesson, "## Technical Meaning")
    assert "Lesson 9" in technical
    assert "Lesson 17" in technical


def test_only_video_one_is_the_canonical_completed_lesson():
    produced = sorted(path.name for path in Path("course/videos").iterdir() if path.is_dir())
    assert produced == ["001-computer-learning-from-text"]


def test_superseded_lesson_drafts_are_not_competing_course_sources():
    assert not {path for path in SUPERSEDED_LESSON_FILES if path.exists()}


def test_video_one_has_the_complete_lesson_artifact_set():
    artifacts = {path.name for path in VIDEO_DIR.iterdir() if path.is_file()}
    assert artifacts == REQUIRED_VIDEO_FILES


def test_video_templates_have_required_headings():
    template_dir = Path("course/templates/video")
    for name, expected in TEMPLATE_HEADINGS.items():
        assert lesson_section_headings(read(template_dir / name)) == expected, name


def test_video_one_artifacts_have_required_headings():
    for name, expected in VIDEO_HEADINGS.items():
        actual = lesson_section_headings(read(VIDEO_DIR / name))
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
        "Sentence: The opposite of hot is cold\n"
        "Words: ['The', 'opposite', 'of', 'hot', 'is', 'cold']\n"
        "Prediction positions: 5\n"
        "\n"
        "Prefix questions:\n"
        "['The'] -> opposite\n"
        "['The', 'opposite'] -> of\n"
        "['The', 'opposite', 'of'] -> hot\n"
        "['The', 'opposite', 'of', 'hot'] -> is\n"
        "['The', 'opposite', 'of', 'hot', 'is'] -> cold\n"
        "\n"
        "Shifted toy ID window:\n"
        "window: [7, 20, 4, 2, 6]\n"
        "x     : [7, 20, 4, 2]\n"
        "y     : [20, 4, 2, 6]\n"
    )


def test_video_one_evidence_covers_sources_repository_behavior_and_boundaries():
    evidence = read(VIDEO_DIR / "evidence.md")
    anchors = section(evidence, "## Repository Anchors")
    sources = section(evidence, "## Primary Sources")
    commands = section(evidence, "## Commands Run")
    boundaries = section(evidence, "## Simplifications And Boundaries")

    assert "matgpt/training/dataset.py" in anchors
    assert "window[:-1]" in anchors and "window[1:]" in anchors
    assert "is_causal=True" in anchors
    assert "Attention Is All You Need" in sources
    assert "Causal language modeling" in sources
    assert "python course/videos/001-computer-learning-from-text/lab.py" in commands
    assert "uv run --extra test pytest tests/test_course_structure.py tests/test_video_001_teaching_style.py -v" in commands
    assert "words" in boundaries.lower() and "tokens" in boundaries.lower()
    assert "prediction positions" in boundaries.lower()
