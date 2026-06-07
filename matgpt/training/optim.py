from __future__ import annotations

import math
from typing import Iterable

import torch
from torch import nn


def _parameter_groups(model: nn.Module, weight_decay: float) -> list[dict]:
    decay = []
    no_decay = []
    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        if param.dim() >= 2 and "norm" not in name.lower():
            decay.append(param)
        else:
            no_decay.append(param)
    return [
        {"params": decay, "weight_decay": weight_decay},
        {"params": no_decay, "weight_decay": 0.0},
    ]


def build_optimizer(
    model: nn.Module,
    optimizer_name: str,
    learning_rate: float,
    weight_decay: float,
    betas: tuple[float, float],
) -> torch.optim.Optimizer:
    groups = _parameter_groups(model, weight_decay)
    if optimizer_name == "adamw":
        if torch.cuda.is_available():
            try:
                return torch.optim.AdamW(groups, lr=learning_rate, betas=betas, fused=True)
            except TypeError:
                pass
        return torch.optim.AdamW(groups, lr=learning_rate, betas=betas)
    if optimizer_name == "adamw8bit":
        try:
            import bitsandbytes as bnb
        except ImportError as exc:
            raise RuntimeError("bitsandbytes is required for optimizer=adamw8bit") from exc
        return bnb.optim.AdamW8bit(groups, lr=learning_rate, betas=betas)
    raise ValueError(f"Unsupported optimizer: {optimizer_name}")


def cosine_warmup_lr(
    step: int,
    warmup_steps: int,
    total_steps: int,
    max_lr: float,
    min_lr: float,
) -> float:
    if step < warmup_steps:
        return max_lr * step / max(1, warmup_steps)
    if step >= total_steps:
        return min_lr
    progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
    cosine = 0.5 * (1.0 + math.cos(math.pi * progress))
    return min_lr + cosine * (max_lr - min_lr)


def set_optimizer_lr(optimizer: torch.optim.Optimizer, lr: float) -> None:
    for group in optimizer.param_groups:
        group["lr"] = lr
