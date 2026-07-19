from __future__ import annotations

import math
from typing import Any

import torch

from matgpt.model.generation import generate
from matgpt.training.amp import autocast_context


# This function checks model loss on a dataset.
# Usually this dataset is the validation dataset.
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

    # model.eval() -> Put the model in evaluation mode
    # We are checking it, not training it.
    model.eval()
    losses = []
    for _ in range(eval_batches):
        # Get validation examples f
        x, y = dataset.sample_batch(batch_size, device)
        with autocast_context(device, precision):
            # Ask the model to predict & compute mistake score
            _, loss = model(x, targets=y)
        losses.append(float(loss.detach().cpu()))
    if was_training:
        model.train() # Put model back into training mode afterward.
    # Return --> Average the losses from several validation batches.
    return sum(losses) / max(1, len(losses))


def perplexity(loss: float) -> float:
    # Convert loss into perplexity.
    # min(loss, 50.0) prevents the number from becoming too huge.
    return math.exp(min(loss, 50.0))


@torch.no_grad()  # Do not train or compute gradients during evaluation.
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
