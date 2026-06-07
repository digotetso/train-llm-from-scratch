"""Base-pretraining loop for MatGPT.

The loop is token-count driven rather than epoch-driven because language-model
training quality is usually compared by how many tokens the model has seen.
It supports interrupted Colab sessions by saving model, optimizer, scheduler
state, gradient scaler state, RNG state, and run metadata.
"""

from __future__ import annotations

import json
import math
import subprocess
import time
from pathlib import Path
from typing import Any

import torch

from matgpt.config import config_to_yaml
from matgpt.eval.lm import evaluate_loss, generate_samples, perplexity
from matgpt.model.gpt import GPT, GPTConfig, count_parameters
from matgpt.tokenizer.io import load_tokenizer, load_tokenizer_metadata
from matgpt.training.amp import autocast_context, make_grad_scaler
from matgpt.training.checkpoint import load_checkpoint, save_checkpoint
from matgpt.training.dataset import PackedTokenDataset, metadata_path_for_split
from matgpt.training.optim import build_optimizer, cosine_warmup_lr, set_optimizer_lr
from matgpt.data.prepare import effective_validation_split
from matgpt.training.tracking import create_tracker
from matgpt.utils.hashing import sha256_file, sha256_text
from matgpt.utils.logging import append_csv_row, ensure_dir
from matgpt.utils.seed import set_seed


def get_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def get_git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "not-a-git-repository"


def train_on_fixed_batch(
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    x: torch.Tensor,
    y: torch.Tensor,
    steps: int,
    device: torch.device,
) -> list[float]:
    model.to(device)
    x = x.to(device)
    y = y.to(device)
    losses = []
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        _, loss = model(x, targets=y)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu()))
    return losses


def _steps_from_tokens(cfg: dict[str, Any]) -> int:
    training = cfg["training"]
    model = cfg["model"]
    tokens_per_step = (
        training["micro_batch_size"]
        * model["context_length"]
        * training["gradient_accumulation_steps"]
    )
    return max(1, math.ceil(training["max_tokens"] / tokens_per_step))


def _is_due(tokens_processed: int, interval: int, tokens_per_step: int) -> bool:
    if interval <= 0:
        return False
    return tokens_processed % interval < tokens_per_step


def _write_samples(path: Path, samples: list[dict[str, Any]], state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"state": state, "samples": samples}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_pretraining(
    cfg: dict[str, Any],
    resume_from: str | Path | None = None,
    max_steps_override: int | None = None,
) -> dict[str, Any]:
    """Run or resume base pretraining from the configured token shards."""

    set_seed(cfg["run"]["seed"])
    if hasattr(torch, "set_float32_matmul_precision"):
        torch.set_float32_matmul_precision("high")
    device = get_device()
    run_dir = ensure_dir(cfg["run"]["output_dir"])
    checkpoint_dir = ensure_dir(run_dir / "checkpoints")
    sample_dir = ensure_dir(run_dir / "samples")
    metrics_path = run_dir / "metrics.csv"

    model = GPT(GPTConfig.from_dict(cfg["model"])).to(device)
    optimizer = build_optimizer(
        model,
        optimizer_name=cfg["training"]["optimizer"],
        learning_rate=cfg["training"]["learning_rate"],
        weight_decay=cfg["training"]["weight_decay"],
        betas=(cfg["training"]["beta1"], cfg["training"]["beta2"]),
    )
    scaler = make_grad_scaler(device, cfg["training"]["precision"])
    tokenizer = load_tokenizer(cfg["tokenizer"]["output_dir"])
    tokenizer_metadata = load_tokenizer_metadata(cfg["tokenizer"]["output_dir"])
    eos_id = tokenizer.token_to_id("<|eos|>")

    train_dataset = PackedTokenDataset.from_metadata(
        metadata_path_for_split(cfg["sharding"]["output_dir"], cfg["dataset"]["train_split"]),
        context_length=cfg["model"]["context_length"],
        seed=cfg["run"]["seed"],
    )
    val_dataset = PackedTokenDataset.from_metadata(
        metadata_path_for_split(cfg["sharding"]["output_dir"], effective_validation_split(cfg["dataset"])),
        context_length=cfg["model"]["context_length"],
        seed=cfg["run"]["seed"] + 1,
    )

    state = {"global_step": 0, "tokens_processed": 0, "best_val_loss": float("inf")}
    if resume_from is not None:
        payload = load_checkpoint(resume_from, model=model, optimizer=optimizer, scaler=scaler, map_location=device, restore_rng=True)
        state.update(payload["state"])

    train_model = torch.compile(model) if cfg["training"].get("compile") and hasattr(torch, "compile") else model

    total_steps = _steps_from_tokens(cfg)
    if max_steps_override is not None:
        total_steps = min(total_steps, state["global_step"] + max_steps_override)
    warmup_steps = max(1, int(total_steps * cfg["training"]["warmup_ratio"]))
    tokens_per_step = (
        cfg["training"]["micro_batch_size"]
        * cfg["model"]["context_length"]
        * cfg["training"]["gradient_accumulation_steps"]
    )
    extra = {
        "git_commit": get_git_commit(),
        "config_sha256": sha256_text(config_to_yaml(cfg)),
        "tokenizer_sha256": tokenizer_metadata["tokenizer_sha256"],
        "dataset_manifest_hash": _optional_file_hash(Path(cfg["dataset"]["normalized_dir"]) / "manifest.json"),
        "parameter_count": count_parameters(model),
    }
    tracker = create_tracker(cfg, config_snapshot={**cfg, "run_metadata": extra})

    start_time = time.time()
    while state["global_step"] < total_steps and state["tokens_processed"] < cfg["training"]["max_tokens"]:
        train_model.train()
        optimizer.zero_grad(set_to_none=True)
        step_loss = 0.0
        lr = cosine_warmup_lr(
            step=state["global_step"],
            warmup_steps=warmup_steps,
            total_steps=total_steps,
            max_lr=cfg["training"]["learning_rate"],
            min_lr=cfg["training"]["min_learning_rate"],
        )
        set_optimizer_lr(optimizer, lr)

        for _ in range(cfg["training"]["gradient_accumulation_steps"]):
            x, y = train_dataset.sample_batch(cfg["training"]["micro_batch_size"], device)
            with autocast_context(device, cfg["training"]["precision"]):
                _, loss = train_model(x, targets=y)
                scaled_loss = loss / cfg["training"]["gradient_accumulation_steps"]
            # Gradient accumulation simulates a larger batch than fits in T4
            # memory. Dividing the loss keeps the final gradient scale correct.
            scaler.scale(scaled_loss).backward()
            step_loss += float(loss.detach().cpu()) / cfg["training"]["gradient_accumulation_steps"]

        scaler.unscale_(optimizer)
        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), cfg["training"]["grad_clip"])
        scaler.step(optimizer)
        scaler.update()

        state["global_step"] += 1
        state["tokens_processed"] += tokens_per_step
        elapsed = max(1e-6, time.time() - start_time)
        tokens_per_second = state["tokens_processed"] / elapsed

        if state["global_step"] % cfg["training"]["log_interval_steps"] == 0:
            train_metrics = {
                "global_step": state["global_step"],
                "tokens_processed": state["tokens_processed"],
                "train_loss": step_loss,
                "lr": lr,
                "grad_norm": float(grad_norm.detach().cpu()),
                "tokens_per_second": tokens_per_second,
                "peak_memory_mb": _peak_memory_mb(device),
            }
            append_csv_row(metrics_path, train_metrics)
            tracker.log(train_metrics, step=state["global_step"])

        if _is_due(state["tokens_processed"], cfg["training"]["eval_interval_tokens"], tokens_per_step):
            val_loss = evaluate_loss(
                model=train_model,
                dataset=val_dataset,
                batch_size=cfg["training"]["micro_batch_size"],
                eval_batches=cfg["training"]["eval_batches"],
                device=device,
                precision=cfg["training"]["precision"],
            )
            val_metrics = {
                "global_step": state["global_step"],
                "tokens_processed": state["tokens_processed"],
                "val_loss": val_loss,
                "val_perplexity": perplexity(val_loss),
                "lr": lr,
                "peak_memory_mb": _peak_memory_mb(device),
            }
            append_csv_row(metrics_path, val_metrics)
            tracker.log(val_metrics, step=state["global_step"])
            if val_loss < state["best_val_loss"]:
                state["best_val_loss"] = val_loss
                if cfg["training"]["save_best"]:
                    save_checkpoint(checkpoint_dir / "best.pt", model, optimizer, scaler, state, cfg, extra)

        if _is_due(state["tokens_processed"], cfg["training"]["sample_interval_tokens"], tokens_per_step):
            samples = generate_samples(
                model=train_model,
                tokenizer=tokenizer,
                prompts=cfg["evaluation"]["prompts"],
                max_new_tokens=cfg["evaluation"]["max_new_tokens"],
                eos_id=eos_id,
                temperature=cfg["evaluation"]["temperature"],
                top_k=cfg["evaluation"]["top_k"],
                top_p=cfg["evaluation"]["top_p"],
                device=device,
            )
            _write_samples(sample_dir / f"samples_{state['tokens_processed']:012d}.json", samples, dict(state))
            tracker.log({"sample_text": samples[0]["text"] if samples else ""}, step=state["global_step"])

        if _is_due(state["tokens_processed"], cfg["training"]["checkpoint_interval_tokens"], tokens_per_step):
            save_checkpoint(checkpoint_dir / "latest.pt", model, optimizer, scaler, state, cfg, extra)
            if cfg["training"]["keep_milestones"]:
                save_checkpoint(
                    checkpoint_dir / f"ckpt_{state['tokens_processed']:012d}.pt",
                    model,
                    optimizer,
                    scaler,
                    state,
                    cfg,
                    extra,
                )

    save_checkpoint(checkpoint_dir / "latest.pt", model, optimizer, scaler, state, cfg, extra)
    tracker.finish()
    return {"state": state, "run_dir": str(run_dir), "extra": extra}


def _optional_file_hash(path: Path) -> str:
    return sha256_file(path) if path.exists() else "missing"


def _peak_memory_mb(device: torch.device) -> float:
    if device.type != "cuda":
        return 0.0
    return torch.cuda.max_memory_allocated(device) / (1024 * 1024)
