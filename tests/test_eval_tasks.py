import json
from pathlib import Path

import torch

from matgpt.eval.tasks import (
    load_multiple_choice_examples,
    score_choice_ids,
    score_multiple_choice_examples,
)


class PreferenceModel(torch.nn.Module):
    def __init__(self, preferred_token_id: int, vocab_size: int = 8):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.zeros(1))
        self.config = type("Config", (), {"context_length": 8})()
        self.preferred_token_id = preferred_token_id
        self.vocab_size = vocab_size

    def forward(self, input_ids, targets=None):
        logits = torch.zeros(input_ids.shape[0], input_ids.shape[1], self.vocab_size, device=input_ids.device)
        logits[..., self.preferred_token_id] = 5.0
        return logits, None


def test_load_multiple_choice_examples_accepts_letters_and_indexes(tmp_path: Path):
    path = tmp_path / "mc.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"id": "one", "prompt": "A?", "choices": ["x", "y"], "answer": "B"}),
                json.dumps({"id": "two", "prompt": "B?", "choices": ["x", "y"], "answer": 0}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    examples = load_multiple_choice_examples(path)

    assert [example.answer_index for example in examples] == [1, 0]
    assert examples[0].id == "one"
    assert examples[1].choices == ["x", "y"]


def test_score_multiple_choice_examples_reports_accuracy_from_model_losses():
    model = PreferenceModel(preferred_token_id=2)
    examples = [
        {
            "id": "easy",
            "prompt_ids": [1],
            "choice_ids": [[3], [2]],
            "answer_index": 1,
        },
        {
            "id": "miss",
            "prompt_ids": [1],
            "choice_ids": [[2], [3]],
            "answer_index": 1,
        },
    ]

    result = score_multiple_choice_examples(
        model=model,
        encoded_examples=examples,
        device=torch.device("cpu"),
        precision="fp32",
    )

    assert result["accuracy"] == 0.5
    assert result["examples"][0]["prediction_index"] == 1
    assert result["examples"][1]["prediction_index"] == 0


def test_score_choice_ids_masks_prompt_tokens_and_scores_choice_only():
    model = PreferenceModel(preferred_token_id=2)

    preferred_loss = score_choice_ids(
        model=model,
        prompt_ids=[7, 7, 7],
        choice_ids=[2],
        device=torch.device("cpu"),
        precision="fp32",
    )
    rejected_loss = score_choice_ids(
        model=model,
        prompt_ids=[7, 7, 7],
        choice_ids=[3],
        device=torch.device("cpu"),
        precision="fp32",
    )

    assert preferred_loss < rejected_loss
