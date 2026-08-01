import json
from pathlib import Path

import pytest

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


@pytest.mark.parametrize(
    ("prompt", "choices", "expected_error"),
    [
        ("", [" yes", " no"], "non-empty prompt"),
        ("The answer is", [" yes", "   "], "non-empty choices"),
    ],
)
def test_consistency_asset_rejects_blank_prompt_or_choice(
    tmp_path: Path,
    prompt: str,
    choices: list[str],
    expected_error: str,
):
    path = tmp_path / "invalid.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "character-001",
                "category": "character",
                "prompt": prompt,
                "choices": choices,
                "answer": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=expected_error):
        validate_consistency_asset(path)
