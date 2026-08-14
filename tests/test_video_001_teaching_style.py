from pathlib import Path


SCRIPT_PATH = Path("course/videos/001-computer-learning-from-text/script.md")


def read_script() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def section(markdown: str, heading: str) -> str:
    content = markdown.split(f"{heading}\n", maxsplit=1)[1]
    return content.split("\n## ", maxsplit=1)[0]


def test_video_one_starts_with_an_observable_next_piece_question():
    hook = section(read_script(), "## 00:00 Hook")
    narration = hook.split("### Narration", maxsplit=1)[1]

    assert "The opposite of hot is" in narration
    assert "cold" in narration
    assert "what comes next" in narration.lower()
    assert "token" not in narration.lower()
    assert len(narration.split()) <= 180


def test_video_one_names_concepts_after_the_learner_has_used_them():
    script = read_script()
    intuition = section(script, "## 01:10 Intuition")
    technical = section(script, "## 02:20 Technical Meaning")

    assert "words before the cut" in intuition.lower()
    assert "recorded word after the cut" in intuition.lower()
    assert "**input**" in technical
    assert "**target**" in technical
    assert "**training example**" in technical
    lowered_technical = technical.lower()
    assert "**teaching simplification:**" in lowered_technical
    assert lowered_technical.index("**input**") < lowered_technical.index("**teaching simplification:**")


def test_video_one_distinguishes_prediction_positions_from_independent_examples():
    script = read_script().lower()

    assert "five prediction positions" in script
    assert "not five independently stored sentences" in script
    assert "one shifted training window" in script


def test_video_one_explains_the_shift_without_turning_each_input_word_into_its_whole_context():
    walkthrough = section(read_script(), "## 05:10 Repository Walkthrough").lower()

    assert "whole input row" in walkthrough
    assert "each position" in walkthrough
    assert "text up to that position" in walkthrough
    assert "does not mean that each isolated input word is the whole context" in walkthrough


def test_video_one_uses_prediction_then_observation_then_transfer():
    lab = section(read_script(), "## 07:20 Live Mini-Lab").split("### Narration", maxsplit=1)[1]

    prediction_index = lab.lower().index("predict")
    run_index = lab.index("python course/videos/001-computer-learning-from-text/lab.py")
    changed_case_index = lab.index("Birds fly over the calm lake")
    assert prediction_index < run_index < changed_case_index


def test_video_one_corrects_likely_target_and_scale_misconceptions():
    mistakes = section(read_script(), "## 09:40 Common Mistakes").lower()

    assert "only correct continuation" in mistakes
    assert "recorded continuation" in mistakes
    assert "base pretraining" in mistakes
    assert "post-training" in mistakes
    assert "tokens" in mistakes
    assert "words" in mistakes


def test_video_one_separates_production_directions_from_spoken_narration():
    script = read_script()
    for heading in [
        "## 00:00 Hook",
        "## 01:10 Intuition",
        "## 02:20 Technical Meaning",
        "## 03:30 Tiny Example",
        "## 05:10 Repository Walkthrough",
        "## 07:20 Live Mini-Lab",
        "## 09:40 Common Mistakes",
        "## 10:50 Recap And Exercise",
    ]:
        content = section(script, heading)
        assert "### Visual / Animation" in content
        assert "### Narration" in content
        assert content.index("### Visual / Animation") < content.index("### Narration")


def test_video_one_ends_with_a_transferable_causal_chain():
    recap = section(read_script(), "## 10:50 Recap And Exercise").lower()

    for phrase in [
        "recorded sequence",
        "shift it by one position",
        "input row",
        "target row",
        "next-piece prediction",
    ]:
        assert phrase in recap
    assert "birds fly over the calm lake" in recap


def test_video_one_labels_sources_observations_and_simplifications():
    script = read_script()

    assert "**Source fact:**" in script
    assert "**Observed repository behavior:**" in script
    assert "**Teaching simplification:**" in script
