from __future__ import annotations

import torch
from torch.nn import functional as F


def _apply_top_k(logits: torch.Tensor, top_k: int | None) -> torch.Tensor:
    if top_k is None or top_k <= 0 or top_k >= logits.shape[-1]:
        return logits
    values, _ = torch.topk(logits, top_k)
    threshold = values[:, [-1]]
    return logits.masked_fill(logits < threshold, float("-inf"))


def _apply_top_p(logits: torch.Tensor, top_p: float | None) -> torch.Tensor:
    if top_p is None or top_p <= 0.0 or top_p >= 1.0:
        return logits
    sorted_logits, sorted_indices = torch.sort(logits, descending=True, dim=-1)
    probs = F.softmax(sorted_logits, dim=-1)
    cumulative = torch.cumsum(probs, dim=-1)
    remove = cumulative > top_p
    remove[..., 1:] = remove[..., :-1].clone()
    remove[..., 0] = False
    sorted_logits = sorted_logits.masked_fill(remove, float("-inf"))
    filtered = torch.full_like(logits, float("-inf"))
    return filtered.scatter(dim=-1, index=sorted_indices, src=sorted_logits)


@torch.no_grad()
def generate(
    model,
    input_ids: torch.Tensor,
    max_new_tokens: int,
    eos_id: int | None,
    temperature: float = 0.8,
    top_k: int | None = None,
    top_p: float | None = None,
) -> torch.Tensor:
    was_training = model.training
    model.eval()
    device = next(model.parameters(), torch.empty(0)).device
    input_ids = input_ids.to(device)

    for _ in range(max_new_tokens):
        context = model.crop_context(input_ids) if hasattr(model, "crop_context") else input_ids
        logits, _ = model(context)
        next_logits = logits[:, -1, :]
        if temperature <= 0.0:
            next_id = torch.argmax(next_logits, dim=-1, keepdim=True)
        else:
            next_logits = next_logits / temperature
            next_logits = _apply_top_k(next_logits, top_k)
            next_logits = _apply_top_p(next_logits, top_p)
            probs = F.softmax(next_logits, dim=-1)
            next_id = torch.multinomial(probs, num_samples=1)
        input_ids = torch.cat((input_ids, next_id), dim=1)
        if eos_id is not None and torch.all(next_id.squeeze(-1) == eos_id):
            break

    if was_training:
        model.train()
    return input_ids
