#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
import time

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.config import load_config
from matgpt.model.gpt import GPT, GPTConfig, count_parameters
from matgpt.training.amp import autocast_context, make_grad_scaler
from matgpt.training.optim import build_optimizer
from matgpt.training.pretrain import get_device
from matgpt.utils.seed import set_seed


def parse_batch_sizes(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def benchmark_batch_size(cfg: dict, batch_size: int, steps: int) -> dict:
    device = get_device()
    model = GPT(GPTConfig.from_dict(cfg["model"])).to(device)
    optimizer = build_optimizer(
        model,
        optimizer_name=cfg["training"]["optimizer"],
        learning_rate=cfg["training"]["learning_rate"],
        weight_decay=cfg["training"]["weight_decay"],
        betas=(cfg["training"]["beta1"], cfg["training"]["beta2"]),
    )
    scaler = make_grad_scaler(device, cfg["training"]["precision"])
    context_length = cfg["model"]["context_length"]
    vocab_size = cfg["model"]["vocab_size"]
    tokens_per_step = batch_size * context_length

    if device.type == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)

    start = time.time()
    try:
        for _ in range(steps):
            x = torch.randint(0, vocab_size, (batch_size, context_length), device=device)
            y = torch.randint(0, vocab_size, (batch_size, context_length), device=device)
            optimizer.zero_grad(set_to_none=True)
            with autocast_context(device, cfg["training"]["precision"]):
                _, loss = model(x, targets=y)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            grad_norm = torch.nn.utils.clip_grad_norm_(
                model.parameters(), cfg["training"]["grad_clip"]
            )
            scaler.step(optimizer)
            scaler.update()
        elapsed = max(time.time() - start, 1e-6)
        loss_value = float(loss.detach().cpu())
        grad_norm_value = float(grad_norm.detach().cpu())
        if not math.isfinite(loss_value) or not math.isfinite(grad_norm_value):
            raise FloatingPointError(
                f"Non-finite benchmark result: loss={loss_value} grad_norm={grad_norm_value}"
            )
        peak_memory_mb = (
            torch.cuda.max_memory_allocated(device) / (1024 * 1024)
            if device.type == "cuda"
            else 0.0
        )
        total_memory_mb = (
            torch.cuda.get_device_properties(device).total_memory / (1024 * 1024)
            if device.type == "cuda"
            else 0.0
        )
        return {
            "batch_size": batch_size,
            "status": "ok",
            "loss": loss_value,
            "grad_norm": grad_norm_value,
            "tokens_per_second": tokens_per_step * steps / elapsed,
            "peak_memory_mb": peak_memory_mb,
            "total_memory_mb": total_memory_mb,
            "memory_fraction": peak_memory_mb / total_memory_mb if total_memory_mb else 0.0,
        }
    except (RuntimeError, FloatingPointError) as exc:
        if device.type == "cuda":
            torch.cuda.empty_cache()
        return {"batch_size": batch_size, "status": "failed", "error": str(exc)[:500]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark safe MatGPT micro-batch sizes on the current device.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--batch-sizes", default="2,4,8,16")
    parser.add_argument("--steps", type=int, default=5)
    args = parser.parse_args()

    cfg = load_config(args.config)
    set_seed(cfg["run"]["seed"])
    if hasattr(torch, "set_float32_matmul_precision"):
        torch.set_float32_matmul_precision("high")

    results = {
        "device": str(get_device()),
        "parameter_count": count_parameters(GPT(GPTConfig.from_dict(cfg["model"]))),
        "context_length": cfg["model"]["context_length"],
        "results": [
            benchmark_batch_size(cfg, batch_size, args.steps)
            for batch_size in parse_batch_sizes(args.batch_sizes)
        ],
    }
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
