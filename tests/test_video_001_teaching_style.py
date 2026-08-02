from pathlib import Path


SCRIPT_PATH = Path("course/videos/001-computer-learning-from-text/script.md")


def read_script() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def section(markdown: str, heading: str) -> str:
    content = markdown.split(f"{heading}\n", maxsplit=1)[1]
    return content.split("\n## ", maxsplit=1)[0]


def spoken_paragraphs(markdown: str) -> list[str]:
    return [
        block.strip()
        for block in markdown.strip().split("\n\n")
        if block.strip() and not block.strip().startswith("[")
    ]


def test_video_one_builds_intuition_before_technical_vocabulary():
    script = read_script()
    hook = section(script, "## 00:00 Hook")
    analogy = section(script, "## 00:45 Analogy")
    technical = section(script, "## 02:00 Technical Meaning")

    assert "When you read" in hook
    assert "computer" in hook.lower() and "meaning" in hook.lower()
    assert "**Teaching analogy:**" in analogy
    assert "analogy" in analogy.lower() and "limit" in analogy.lower()
    for term in ["**character**", "**Unicode**", "**code point**", "**byte**", "**UTF-8**"]:
        assert term in technical


def test_video_one_hook_uses_familiar_ai_outcomes_without_assuming_prediction_knowledge():
    hook = section(read_script(), "## 00:00 Hook")
    lowered = hook.lower()

    for familiar_outcome in ["rewrite an essay", "improve an email", "write code"]:
        assert familiar_outcome in lowered
    for untaught_mechanism in ["predictions", "better guesses", "parameters", "measured error"]:
        assert untaught_mechanism not in lowered
    assert "text you type" in lowered
    assert "numbers" in lowered
    assert "?" in hook


def test_video_one_hook_and_analogy_fit_spoken_pacing_and_invite_a_prediction():
    script = read_script()
    hook = section(script, "## 00:00 Hook")
    analogy = section(script, "## 00:45 Analogy")
    lowered_analogy = analogy.lower()

    assert len(hook.split()) <= 120
    assert "mathematical operations" not in hook.lower()
    assert len(analogy.split()) <= 120
    assert lowered_analogy.count("identifier") <= 3
    assert "predict" in lowered_analogy
    assert "new number" in lowered_analogy
    assert "fixed agreement" in lowered_analogy


def test_video_one_hook_and_analogy_flow_as_connected_conversation():
    script = read_script()
    hook = section(script, "## 00:00 Hook")
    analogy = section(script, "## 00:45 Analogy")

    assert len(spoken_paragraphs(hook)) <= 3
    assert len(spoken_paragraphs(analogy)) <= 3
    assert "here's the puzzle" in hook.lower()
    assert "let's" in hook.lower()
    assert "only takes us so far" in analogy.lower()
    assert "\n\nFirst:" not in hook


def test_video_one_uses_prediction_and_changed_case_as_evidence():
    script = read_script()
    lab = section(script, "## 09:00 Live Mini-Lab")

    prediction_index = lab.lower().index("predict")
    run_index = lab.index("python course/videos/001-computer-learning-from-text/lab.py")
    assert prediction_index < run_index
    assert 'text = "A"' in lab
    assert "Predict" in lab or "predict" in lab


def test_video_one_keeps_future_vocabulary_out_of_the_explanation():
    teaching_body = read_script().split("### Vocabulary Deferred to Later Videos", maxsplit=1)[0].lower()

    for term in ["token embedding", "tensor", "logit", "gradient", "attention"]:
        assert term not in teaching_body


def test_video_one_ends_with_a_spoken_transferable_distinction():
    script = read_script()
    recap = section(script, "## 13:00 Recap And Exercise")

    assert "Restate our objective" not in recap
    assert "representation" in recap.lower()
    assert "learning" in recap.lower()
    assert "parameters" in recap.lower()
    assert "prediction" in recap.lower() or "guesses" in recap.lower()


def test_video_one_names_the_understood_mechanism_and_uses_it_as_a_building_block():
    script = read_script()
    technical = section(script, "## 02:00 Technical Meaning")
    recap = section(script, "## 13:00 Recap And Exercise")

    assert "stable name" in technical.lower()
    assert "**text representation**" in technical.lower()
    assert "**learning**" in technical.lower()
    assert "building block" in recap.lower()
    assert "representation side" in recap.lower()
    assert "next lesson" in recap.lower()


def test_video_one_preserves_source_and_observation_labels():
    script = read_script()

    assert "**Source fact:**" in script
    assert "**Observed code behavior:**" in script
    assert "**Teaching analogy:**" in script
