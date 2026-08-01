import pytest

from matgpt.eval.comparison import (
    parse_checkpoint_specs,
    parse_seed_list,
    summarize_generations,
    summarize_validation,
)
from matgpt.eval.repetition import measure_repetition


def test_parse_seed_list_preserves_predeclared_order_and_rejects_duplicates():
    assert parse_seed_list("1001,1002,1003", "validation") == [1001, 1002, 1003]
    with pytest.raises(ValueError, match="duplicate validation seed"):
        parse_seed_list("1001,1001", "validation")


def test_parse_checkpoint_specs_rejects_unsafe_or_duplicate_labels(tmp_path):
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    with pytest.raises(ValueError, match="unsafe checkpoint label"):
        parse_checkpoint_specs([f"../bad={checkpoint}"])
    with pytest.raises(ValueError, match="duplicate checkpoint label"):
        parse_checkpoint_specs([f"mini={checkpoint}", f"mini={checkpoint}"])


def test_summarize_validation_uses_matched_seed_pairs():
    result = summarize_validation(
        {
            "170m": [{"seed": 1, "loss": 1.7}, {"seed": 2, "loss": 1.8}],
            "200m": [{"seed": 1, "loss": 1.8}, {"seed": 2, "loss": 1.7}],
        }
    )

    assert result["checkpoints"]["170m"]["mean_loss"] == 1.75
    assert result["pairs"][0]["left_wins"] == 1
    assert result["pairs"][0]["right_wins"] == 1
    assert result["pairs"][0]["mean_loss_difference"] == 0.0


def test_summarize_validation_rejects_unmatched_seeds_and_nonfinite_losses():
    with pytest.raises(ValueError, match="same validation seeds"):
        summarize_validation(
            {
                "170m": [{"seed": 1, "loss": 1.7}],
                "200m": [{"seed": 2, "loss": 1.8}],
            }
        )
    with pytest.raises(ValueError, match="finite"):
        summarize_validation({"170m": [{"seed": 1, "loss": float("nan")}]})


def test_summarize_generations_reports_length_and_repetition_metrics():
    rows = [
        {"text": "A cat ran.", "repetition": measure_repetition("A cat ran.")},
        {
            "text": "A cat. A cat.",
            "repetition": measure_repetition("A cat. A cat."),
        },
    ]

    result = summarize_generations(rows)

    assert result["generation_count"] == 2
    assert result["minimum_word_count"] == 3
    assert result["mean_word_count"] == 3.5
    assert result["maximum_word_count"] == 4
    assert result["repetition"]["mean_duplicate_sentence_rate"] == 0.25
