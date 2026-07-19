from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import torch
from torch.nn import functional as F

from matgpt.training.amp import autocast_context


@dataclass(frozen=True)
class MultipleChoiceExample:
    id: str
    prompt: str
    choices: list[str]
    answer_index: int


def _answer_to_index(answer: str | int, choices: list[str]) -> int:
    if isinstance(answer, int):
        index = answer
    elif isinstance(answer, str):
        stripped = answer.strip()
        if len(stripped) == 1 and stripped.upper().isalpha():
            index = ord(stripped.upper()) - ord("A")
        elif stripped.isdigit():
            index = int(stripped)
        elif stripped in choices:
            index = choices.index(stripped)
        else:
            raise ValueError(f"Unsupported answer value: {answer!r}")
    else:
        raise ValueError(f"Unsupported answer value: {answer!r}")

    if index < 0 or index >= len(choices):
        raise ValueError(f"Answer index {index} outside choices length {len(choices)}")
    return index


def load_multiple_choice_examples(path: str | Path) -> list[MultipleChoiceExample]:
    examples: list[MultipleChoiceExample] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            choices = list(row["choices"])
            if len(choices) < 2:
                raise ValueError(f"Line {line_number} must contain at least two choices.")
            examples.append(
                MultipleChoiceExample(
                    id=str(row.get("id", line_number)),
                    prompt=str(row["prompt"]),
                    choices=[str(choice) for choice in choices],
                    answer_index=_answer_to_index(row["answer"], choices),
                )
            )
    return examples


def encode_multiple_choice_examples(examples: Iterable[MultipleChoiceExample], tokenizer) -> list[dict[str, Any]]:
    encoded = []
    for example in examples:
        encoded.append(
            {
                "id": example.id,
                "prompt": example.prompt,
                "choices": example.choices,
                "answer_index": example.answer_index,
                "prompt_ids": tokenizer.encode(example.prompt).ids,
                "choice_ids": [tokenizer.encode(choice).ids for choice in example.choices],
            }
        )
    return encoded


@torch.no_grad()
def score_choice_ids(
    model,
    prompt_ids: list[int],
    choice_ids: list[int],
    device: torch.device,
    precision: str,
) -> float:
    if not choice_ids:
        return math.inf

    full_ids = list(prompt_ids) + list(choice_ids)
    if len(full_ids) < 2:
        return math.inf

    context_length = getattr(getattr(model, "config", None), "context_length", len(full_ids) - 1)
    max_full_len = context_length + 1
    prompt_len = len(prompt_ids)
    if len(full_ids) > max_full_len:
        overflow = len(full_ids) - max_full_len
        full_ids = full_ids[overflow:]
        prompt_len = max(0, prompt_len - overflow)

    input_ids = torch.tensor([full_ids[:-1]], dtype=torch.long, device=device)
    targets = torch.tensor([full_ids[1:]], dtype=torch.long, device=device)
    mask_until = max(0, prompt_len - 1)
    if mask_until:
        targets[:, :mask_until] = -100
    if torch.all(targets == -100):
        return math.inf

    model.eval()
    with autocast_context(device, precision):
        logits, _ = model(input_ids)
        loss = F.cross_entropy(
            logits.reshape(-1, logits.size(-1)),
            targets.reshape(-1),
            ignore_index=-100,
        )
    return float(loss.detach().cpu())


def score_multiple_choice_examples(
    model,
    encoded_examples: Iterable[dict[str, Any]],
    device: torch.device,
    precision: str,
) -> dict[str, Any]:
    rows = []
    correct = 0
    total = 0
    for example in encoded_examples:
        losses = [
            score_choice_ids(
                model=model,
                prompt_ids=example["prompt_ids"],
                choice_ids=choice_ids,
                device=device,
                precision=precision,
            )
            for choice_ids in example["choice_ids"]
        ]
        prediction_index = min(range(len(losses)), key=lambda index: losses[index])
        is_correct = prediction_index == example["answer_index"]
        correct += int(is_correct)
        total += 1
        rows.append(
            {
                "id": example["id"],
                "answer_index": example["answer_index"],
                "prediction_index": prediction_index,
                "correct": is_correct,
                "choice_losses": losses,
            }
        )

    return {
        "task_type": "multiple_choice",
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else 0.0,
        "examples": rows,
    }


def evaluate_multiple_choice_file(
    model,
    tokenizer,
    path: str | Path,
    device: torch.device,
    precision: str,
) -> dict[str, Any]:
    examples = load_multiple_choice_examples(path)
    encoded = encode_multiple_choice_examples(examples, tokenizer)
    result = score_multiple_choice_examples(model, encoded, device=device, precision=precision)
    result["path"] = str(Path(path))
    return result
