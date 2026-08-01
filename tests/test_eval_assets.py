from pathlib import Path

from matgpt.eval.assets import load_story_prompts, validate_consistency_asset


ROOT = Path(__file__).resolve().parents[1]


def test_story_prompt_asset_has_50_unique_base_model_continuations():
    prompts = load_story_prompts(ROOT / "evals" / "story_prompts.jsonl")

    assert len(prompts) == 50
    assert len({prompt.id for prompt in prompts}) == 50
    assert len({prompt.text for prompt in prompts}) == 50
    assert all(prompt.text.strip() and not prompt.text.endswith("?") for prompt in prompts)


def test_consistency_asset_has_25_examples_in_each_category():
    counts = validate_consistency_asset(ROOT / "evals" / "story_consistency.jsonl")

    assert counts == {
        "cause_effect": 25,
        "character": 25,
        "location_state": 25,
        "object_attribute": 25,
    }


def test_judge_prompt_defines_blinding_scores_flags_and_jsonl_contract():
    text = (ROOT / "evals" / "story_judge_prompt.md").read_text(encoding="utf-8")

    for required in (
        "character_consistency",
        "object_location_consistency",
        "causal_coherence",
        "overall_consistency",
        "character_swap",
        "Return exactly one JSON object per input line",
    ):
        assert required in text
