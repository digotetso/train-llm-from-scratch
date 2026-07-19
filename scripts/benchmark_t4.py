#!/usr/bin/env python
from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import math
import sys
from pathlib import Path
import time
from typing import TypeVar

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.config import load_config
from matgpt.model.gpt import GPT, GPTConfig, count_parameters
from matgpt.training.amp import autocast_context, make_grad_scaler
from matgpt.training.optim import build_optimizer
from matgpt.training.pretrain import get_device
from matgpt.utils.seed import set_seed


T = TypeVar("T")


def _synchronize_device(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def run_timed_steps(
    step_fn: Callable[[], T],
    *,
    device: torch.device,
    steps: int,
    warmup_steps: int = 1,
    before_timing: Callable[[], None] | None = None,
) -> tuple[T, float]:
    if steps < 1:
        raise ValueError("Benchmark steps must be at least 1")
    if warmup_steps < 0:
        raise ValueError("Benchmark warmup_steps cannot be negative")

    for _ in range(warmup_steps):
        step_fn()

    _synchronize_device(device)
    if before_timing is not None:
        before_timing()

    start = time.perf_counter()
    for _ in range(steps):
        result = step_fn()
    _synchronize_device(device)
    elapsed = max(time.perf_counter() - start, 1e-6)
    return result, elapsed


def parse_batch_sizes(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def validate_benchmark_measurements(
    measurements: dict[str, float], *, device_type: str
) -> None:
    required_fields = (
        "loss",
        "grad_norm",
        "tokens_per_second",
        "peak_memory_mb",
        "total_memory_mb",
        "memory_fraction",
    )
    for field in required_fields:
        value = float(measurements[field])
        if not math.isfinite(value):
            raise FloatingPointError(f"Benchmark {field} is not finite: {value}")

    if measurements["tokens_per_second"] <= 0:
        raise ValueError("Benchmark tokens_per_second must be positive")

    if device_type == "cuda":
        if measurements["total_memory_mb"] <= 0:
            raise ValueError("CUDA total_memory_mb must be positive")
        if measurements["peak_memory_mb"] < 0:
            raise ValueError("CUDA peak_memory_mb must be nonnegative")
        if measurements["memory_fraction"] < 0:
            raise ValueError("CUDA memory_fraction must be nonnegative")
        expected_fraction = (
            measurements["peak_memory_mb"] / measurements["total_memory_mb"]
        )
        if not math.isclose(
            measurements["memory_fraction"],
            expected_fraction,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "CUDA memory_fraction does not match "
                "peak_memory_mb / total_memory_mb"
            )
    elif device_type == "cpu":
        memory_values = (
            measurements["peak_memory_mb"],
            measurements["total_memory_mb"],
            measurements["memory_fraction"],
        )
        if memory_values != (0.0, 0.0, 0.0):
            raise ValueError("CPU benchmark memory fields must be zero")
    else:
        raise ValueError(f"Unsupported benchmark device type: {device_type}")


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

    try:
        def training_step() -> tuple[torch.Tensor, torch.Tensor]:
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
            return loss, grad_norm

        before_timing = None
        if device.type == "cuda":
            before_timing = lambda: torch.cuda.reset_peak_memory_stats(device)
        (loss, grad_norm), elapsed = run_timed_steps(
            training_step,
            device=device,
            steps=steps,
            warmup_steps=1,
            before_timing=before_timing,
        )
        loss_value = float(loss.detach().cpu())
        grad_norm_value = float(grad_norm.detach().cpu())
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
        measurements = {
            "loss": loss_value,
            "grad_norm": grad_norm_value,
            "tokens_per_second": tokens_per_step * steps / elapsed,
            "peak_memory_mb": peak_memory_mb,
            "total_memory_mb": total_memory_mb,
            "memory_fraction": peak_memory_mb / total_memory_mb if total_memory_mb else 0.0,
        }
        validate_benchmark_measurements(measurements, device_type=device.type)
        return {
            "batch_size": batch_size,
            "status": "ok",
            **measurements,
        }
    except (RuntimeError, FloatingPointError, ValueError) as exc:
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
