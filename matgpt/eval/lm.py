from __future__ import annotations

import math
from typing import Any

import torch

from matgpt.model.generation import generate
from matgpt.training.amp import autocast_context


@torch.no_grad()
def evaluate_loss(
    model,
    dataset,
    batch_size: int,
    eval_batches: int,
    device: torch.device,
    precision: str,
) -> float:
    was_training = model.training
    model.eval()
    losses = []
    for _ in range(eval_batches):
        x, y = dataset.sample_batch(batch_size, device)
        with autocast_context(device, precision):
            _, loss = model(x, targets=y)
        losses.append(float(loss.detach().cpu()))
    if was_training:
        model.train()
    return sum(losses) / max(1, len(losses))


def perplexity(loss: float) -> float:
    return math.exp(min(loss, 50.0))


@torch.no_grad()
def generate_samples(
    model,
    tokenizer,
    prompts: list[str],
    max_new_tokens: int,
    eos_id: int | None,
    temperature: float,
    top_k: int | None,
    top_p: float | None,
    device: torch.device,
) -> list[dict[str, Any]]:
    samples = []
    for prompt in prompts:
        input_ids = torch.tensor([tokenizer.encode(prompt).ids], dtype=torch.long, device=device)
        output = generate(
            model=model,
            input_ids=input_ids,
            max_new_tokens=max_new_tokens,
            eos_id=eos_id,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
        )
        samples.append(
            {
                "prompt": prompt,
                "text": tokenizer.decode(output[0].detach().cpu().tolist()),
            }
        )
    return samples
