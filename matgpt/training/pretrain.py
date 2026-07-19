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
from dataclasses import asdict
from pathlib import Path
from typing import Any

import torch

from matgpt.config import config_to_yaml
from matgpt.eval.lm import evaluate_loss, generate_samples, perplexity
from matgpt.model.gpt import GPT, GPTConfig, count_parameters
from matgpt.tokenizer.io import load_tokenizer, load_tokenizer_metadata
from matgpt.training.amp import (
    OptimizerStepTracker,
    autocast_context,
    make_grad_scaler,
    require_finite_loss,
    step_optimizer_with_scaler,
)
from matgpt.training.artifacts import validate_run_artifacts, write_run_artifacts
from matgpt.training.checkpoint import apply_checkpoint_payload, load_checkpoint, save_checkpoint
from matgpt.training.dataset import PackedTokenDataset, metadata_path_for_split
from matgpt.training.metrics import append_metric, calculate_tokens_per_second
from matgpt.training.optim import build_optimizer, set_optimizer_lr
from matgpt.training.schedule import build_training_schedule, learning_rate_at_step
from matgpt.data.prepare import effective_validation_split
from matgpt.training.tracking import create_tracker
from matgpt.utils.hashing import sha256_file, sha256_text
from matgpt.utils.logging import ensure_dir
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


def _is_due(tokens_processed: int, interval: int, tokens_per_step: int) -> bool:
    if interval <= 0:
        return False
    return tokens_processed % interval < tokens_per_step


def _write_samples(path: Path, samples: list[dict[str, Any]], state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"state": state, "samples": samples}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_checkpoint_compatibility(payload: dict[str, Any], expected_extra: dict[str, Any]) -> None:
    checkpoint_extra = payload.get("extra") or {}
    mismatches = []
    for key in ("config_sha256", "tokenizer_sha256", "dataset_manifest_hash"):
        if checkpoint_extra.get(key) is None:
            mismatches.append(f"{key}: missing from checkpoint")
        elif expected_extra.get(key) is None:
            mismatches.append(f"{key}: missing from current run")
        elif checkpoint_extra[key] != expected_extra[key]:
            checkpoint_value = checkpoint_extra[key]
            expected_value = expected_extra[key]
            mismatches.append(f"{key}: checkpoint={checkpoint_value} current={expected_value}")
    if mismatches:
        raise ValueError("Checkpoint artifact mismatch; refusing unsafe resume: " + "; ".join(mismatches))


def validate_complete_resume_checkpoint(
    payload: dict[str, Any],
    device: torch.device,
) -> None:
    """Fail before restoration when a checkpoint cannot reproduce training state."""
    missing = []
    for key in ("model", "optimizer", "scaler", "state", "config", "extra", "rng_state"):
        if key not in payload or payload[key] is None:
            missing.append(key)

    invalid = []
    for key in ("model", "optimizer", "scaler", "state", "config", "extra", "rng_state"):
        if key in payload and payload[key] is not None and not isinstance(payload[key], dict):
            invalid.append(key)

    state = payload.get("state")
    if isinstance(state, dict):
        integer_state_keys = (
            "global_step",
            "tokens_processed",
            "attempted_steps",
            "optimizer_steps_skipped_total",
            "consecutive_optimizer_steps_skipped",
        )
        for key in integer_state_keys:
            if key not in state:
                missing.append(f"state.{key}")
            elif (
                not isinstance(state[key], int)
                or isinstance(state[key], bool)
                or state[key] < 0
            ):
                invalid.append(f"state.{key}")
        for key in ("best_val_loss", "elapsed_seconds"):
            if key not in state:
                missing.append(f"state.{key}")
            elif (
                not isinstance(state[key], (int, float))
                or isinstance(state[key], bool)
                or not math.isfinite(float(state[key]))
                or float(state[key]) < 0
            ):
                invalid.append(f"state.{key}")
        dataset_rng_state = state.get("dataset_rng_state")
        if not isinstance(dataset_rng_state, dict):
            missing.append("state.dataset_rng_state")
        else:
            for split in ("train", "validation"):
                if split not in dataset_rng_state:
                    missing.append(f"state.dataset_rng_state.{split}")
                else:
                    split_state = dataset_rng_state[split]
                    if (
                        not isinstance(split_state, dict)
                        or not isinstance(split_state.get("bit_generator"), str)
                        or not isinstance(split_state.get("state"), dict)
                    ):
                        invalid.append(f"state.dataset_rng_state.{split}")

    rng_state = payload.get("rng_state")
    if isinstance(rng_state, dict):
        for key in ("python", "numpy", "torch_cpu"):
            if key not in rng_state:
                missing.append(f"rng_state.{key}")
        python_rng = rng_state.get("python")
        if python_rng is not None and (
            not isinstance(python_rng, tuple) or len(python_rng) != 3
        ):
            invalid.append("rng_state.python")
        numpy_rng = rng_state.get("numpy")
        if numpy_rng is not None and (
            not isinstance(numpy_rng, tuple) or len(numpy_rng) != 5
        ):
            invalid.append("rng_state.numpy")
        torch_cpu_rng = rng_state.get("torch_cpu")
        if torch_cpu_rng is not None and (
            not isinstance(torch_cpu_rng, torch.Tensor)
            or torch_cpu_rng.dtype != torch.uint8
            or torch_cpu_rng.ndim != 1
            or torch_cpu_rng.numel() == 0
        ):
            invalid.append("rng_state.torch_cpu")

    if missing:
        raise ValueError(
            "Checkpoint resume state incomplete; missing: " + ", ".join(missing)
        )
    if invalid:
        raise ValueError(
            "Checkpoint resume state invalid: " + ", ".join(invalid)
        )

    checkpoint_has_cuda_rng = "torch_cuda" in rng_state
    current_device_is_cuda = device.type == "cuda"
    if checkpoint_has_cuda_rng and not current_device_is_cuda:
        raise ValueError(
            "Checkpoint contains CUDA RNG state, but the current device cannot "
            "restore CUDA RNG state"
        )
    if current_device_is_cuda and not checkpoint_has_cuda_rng:
        raise ValueError("Checkpoint resume state incomplete; missing: rng_state.torch_cuda")
    if current_device_is_cuda:
        cuda_rng_states = rng_state["torch_cuda"]
        expected_cuda_devices = torch.cuda.device_count()
        valid_cuda_states = (
            isinstance(cuda_rng_states, (list, tuple))
            and expected_cuda_devices > 0
            and len(cuda_rng_states) == expected_cuda_devices
            and all(
                isinstance(cuda_rng, torch.Tensor)
                and cuda_rng.dtype == torch.uint8
                and cuda_rng.ndim == 1
                and cuda_rng.numel() > 0
                for cuda_rng in cuda_rng_states
            )
        )
        if not valid_cuda_states:
            raise ValueError(
                "Checkpoint resume state invalid: rng_state.torch_cuda must contain "
                f"one nonempty byte tensor per CUDA device (expected {expected_cuda_devices})"
            )


def _checkpoint_state(
    state: dict[str, Any],
    train_dataset: PackedTokenDataset,
    val_dataset: PackedTokenDataset,
) -> dict[str, Any]:
    checkpoint_state = dict(state)
    checkpoint_state["dataset_rng_state"] = {
        "train": train_dataset.get_rng_state(),
        "validation": val_dataset.get_rng_state(),
    }
    return checkpoint_state


def _restore_dataset_rng_state(
    checkpoint_state: dict[str, Any],
    train_dataset: PackedTokenDataset,
    val_dataset: PackedTokenDataset,
) -> None:
    dataset_rng_state = checkpoint_state.get("dataset_rng_state") or {}
    if "train" in dataset_rng_state:
        train_dataset.set_rng_state(dataset_rng_state["train"])
    if "validation" in dataset_rng_state:
        val_dataset.set_rng_state(dataset_rng_state["validation"])


def run_pretraining(
    cfg: dict[str, Any],
    resume_from: str | Path | None = None,
    max_steps_override: int | None = None,
    verify_only: bool = False,
) -> dict[str, Any]:
    """Run or resume base pretraining from the configured token shards."""

    if verify_only and resume_from is None:
        raise ValueError("verify_only requires resume_from")

    set_seed(cfg["run"]["seed"])
    if hasattr(torch, "set_float32_matmul_precision"):
        torch.set_float32_matmul_precision("high")
    device = get_device()
    run_dir = ensure_dir(cfg["run"]["output_dir"])
    metrics_path = run_dir / "metrics.csv"
    if resume_from is None and metrics_path.exists():
        raise ValueError(
            f"Run directory already contains training evidence at {metrics_path}; "
            "provide resume_from to resume the existing run"
        )
    checkpoint_dir = ensure_dir(run_dir / "checkpoints")
    sample_dir = ensure_dir(run_dir / "samples")

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

    extra = {
        "git_commit": get_git_commit(),
        "config_sha256": sha256_text(config_to_yaml(cfg)),
        "tokenizer_sha256": tokenizer_metadata["tokenizer_sha256"],
        "dataset_manifest_hash": _optional_file_hash(Path(cfg["dataset"]["normalized_dir"]) / "manifest.json"),
        "parameter_count": count_parameters(model),
    }

    state = {"global_step": 0, "tokens_processed": 0, "best_val_loss": float("inf")}
    payload = None
    if resume_from is not None:
        payload = load_checkpoint(resume_from, map_location="cpu")
        validate_complete_resume_checkpoint(payload, device)
        if not cfg["training"].get("allow_artifact_mismatch", False):
            validate_checkpoint_compatibility(payload, extra)
    validate_run_artifacts(run_dir, cfg, extra)
    if payload is not None:
        apply_checkpoint_payload(
            payload,
            model=model,
            optimizer=optimizer,
            scaler=scaler,
            restore_rng=True,
        )
        _restore_dataset_rng_state(payload["state"], train_dataset, val_dataset)
        state.update({key: value for key, value in payload["state"].items() if key != "dataset_rng_state"})

    state.setdefault("attempted_steps", state["global_step"])
    state.setdefault("optimizer_steps_skipped_total", 0)
    state.setdefault("consecutive_optimizer_steps_skipped", 0)

    schedule = build_training_schedule(
        cfg,
        global_step=state["global_step"],
        max_steps_override=max_steps_override,
    )
    if verify_only:
        return {
            "resume_verified": True,
            "state": state,
            "run_dir": str(run_dir),
            "extra": extra,
            "schedule": asdict(schedule),
        }

    train_model = torch.compile(model) if cfg["training"].get("compile") and hasattr(torch, "compile") else model

    tracker = create_tracker(cfg, config_snapshot={**cfg, "run_metadata": extra})
    optimizer_step_tracker = None
    try:
        optimizer_step_tracker = OptimizerStepTracker(optimizer)
        run_artifacts = write_run_artifacts(run_dir, cfg, extra, device)

        if resume_from is None and state["global_step"] == 0 and "initial_val_loss" not in state:
            initial_val_loss = evaluate_loss(
                model=train_model,
                dataset=val_dataset,
                batch_size=cfg["training"]["micro_batch_size"],
                eval_batches=cfg["training"]["eval_batches"],
                device=device,
                precision=cfg["training"]["precision"],
            )
            if not math.isfinite(initial_val_loss):
                raise FloatingPointError(f"Non-finite baseline validation loss: {initial_val_loss}")
            state["initial_val_loss"] = initial_val_loss
            state["best_val_loss"] = initial_val_loss
            append_metric(
                metrics_path,
                {
                    "event": "baseline",
                    "attempted_step": 0,
                    "global_step": 0,
                    "tokens_processed": 0,
                    "val_loss": initial_val_loss,
                    "val_perplexity": perplexity(initial_val_loss),
                    "peak_memory_mb": _peak_memory_mb(device),
                    "elapsed_seconds": 0.0,
                },
            )
            tracker.log(
                {"val_loss": initial_val_loss, "val_perplexity": perplexity(initial_val_loss)},
                step=0,
            )

        state.setdefault("elapsed_seconds", 0.0)
        elapsed_before_invocation = float(state["elapsed_seconds"])
        invocation_start_tokens = int(state["tokens_processed"])
        invocation_start_time = time.time()
        while (
            state["global_step"] < schedule.stop_step
            and state["tokens_processed"] < cfg["training"]["max_tokens"]
        ):
            train_model.train()
            optimizer.zero_grad(set_to_none=True)
            step_loss = 0.0
            lr = learning_rate_at_step(cfg, schedule, state["global_step"])
            set_optimizer_lr(optimizer, lr)

            for _ in range(cfg["training"]["gradient_accumulation_steps"]):
                x, y = train_dataset.sample_batch(cfg["training"]["micro_batch_size"], device)
                with autocast_context(device, cfg["training"]["precision"]):
                    _, loss = train_model(x, targets=y)
                    scaled_loss = loss / cfg["training"]["gradient_accumulation_steps"]
                require_finite_loss(
                    loss,
                    global_step=state["global_step"],
                    label="micro-batch",
                    lr=lr,
                    grad_scale=float(scaler.get_scale()),
                )
                # Gradient accumulation simulates a larger batch than fits in T4
                # memory. Dividing the loss keeps the final gradient scale correct.
                scaler.scale(scaled_loss).backward()
                step_loss += float(loss.detach().cpu()) / cfg["training"]["gradient_accumulation_steps"]

            scaler.unscale_(optimizer)
            grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), cfg["training"]["grad_clip"])
            step_result = step_optimizer_with_scaler(scaler, optimizer, optimizer_step_tracker)

            state["attempted_steps"] += 1
            if step_result.update_applied:
                state["global_step"] += 1
                state["tokens_processed"] += schedule.tokens_per_step
                state["consecutive_optimizer_steps_skipped"] = 0
            else:
                state["optimizer_steps_skipped_total"] += 1
                state["consecutive_optimizer_steps_skipped"] += 1

            invocation_elapsed = max(1e-6, time.time() - invocation_start_time)
            state["elapsed_seconds"] = elapsed_before_invocation + invocation_elapsed
            tokens_per_second = calculate_tokens_per_second(
                invocation_start_tokens,
                state["tokens_processed"],
                invocation_elapsed,
            )

            optimizer_step_skipped = not step_result.update_applied
            should_log = (
                optimizer_step_skipped
                or state["global_step"] % cfg["training"]["log_interval_steps"] == 0
            )
            if should_log:
                train_metrics = {
                    "event": "train",
                    "attempted_step": state["attempted_steps"],
                    "global_step": state["global_step"],
                    "tokens_processed": state["tokens_processed"],
                    "train_loss": step_loss,
                    "lr": lr,
                    "grad_norm": float(grad_norm.detach().cpu()),
                    "grad_scale": step_result.scale_after,
                    "optimizer_step_skipped": optimizer_step_skipped,
                    "optimizer_steps_skipped_total": state["optimizer_steps_skipped_total"],
                    "consecutive_optimizer_steps_skipped": state["consecutive_optimizer_steps_skipped"],
                    "tokens_per_second": tokens_per_second,
                    "peak_memory_mb": _peak_memory_mb(device),
                    "elapsed_seconds": state["elapsed_seconds"],
                }
                append_metric(metrics_path, train_metrics)
                tracker.log(train_metrics, step=state["global_step"])

            skip_limit = int(cfg["training"].get("max_consecutive_skipped_updates", 5))
            if state["consecutive_optimizer_steps_skipped"] >= skip_limit:
                raise FloatingPointError(
                    "Aborting after repeated skipped optimizer updates: "
                    f"global_step={state['global_step']} "
                    f"consecutive_skips={state['consecutive_optimizer_steps_skipped']} "
                    f"loss={step_loss} grad_norm={float(grad_norm.detach().cpu())} "
                    f"lr={lr} grad_scale={step_result.scale_after}"
                )

            if step_result.update_applied and _is_due(
                state["tokens_processed"],
                cfg["training"]["eval_interval_tokens"],
                schedule.tokens_per_step,
            ):
                val_loss = evaluate_loss(
                    model=train_model,
                    dataset=val_dataset,
                    batch_size=cfg["training"]["micro_batch_size"],
                    eval_batches=cfg["training"]["eval_batches"],
                    device=device,
                    precision=cfg["training"]["precision"],
                )
                val_metrics = {
                    "event": "validation",
                    "attempted_step": state["attempted_steps"],
                    "global_step": state["global_step"],
                    "tokens_processed": state["tokens_processed"],
                    "val_loss": val_loss,
                    "val_perplexity": perplexity(val_loss),
                    "lr": lr,
                    "peak_memory_mb": _peak_memory_mb(device),
                    "elapsed_seconds": state["elapsed_seconds"],
                }
                append_metric(metrics_path, val_metrics)
                tracker.log(val_metrics, step=state["global_step"])
                if val_loss < state["best_val_loss"]:
                    state["best_val_loss"] = val_loss
                    if cfg["training"]["save_best"]:
                        save_checkpoint(
                            checkpoint_dir / "best.pt",
                            model,
                            optimizer,
                            scaler,
                            _checkpoint_state(state, train_dataset, val_dataset),
                            cfg,
                            extra,
                        )

            if step_result.update_applied and _is_due(
                state["tokens_processed"],
                cfg["training"]["sample_interval_tokens"],
                schedule.tokens_per_step,
            ):
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

            if step_result.update_applied and _is_due(
                state["tokens_processed"],
                cfg["training"]["checkpoint_interval_tokens"],
                schedule.tokens_per_step,
            ):
                save_checkpoint(
                    checkpoint_dir / "latest.pt",
                    model,
                    optimizer,
                    scaler,
                    _checkpoint_state(state, train_dataset, val_dataset),
                    cfg,
                    extra,
                )
                if cfg["training"]["keep_milestones"]:
                    save_checkpoint(
                        checkpoint_dir / f"ckpt_{state['tokens_processed']:012d}.pt",
                        model,
                        optimizer,
                        scaler,
                        _checkpoint_state(state, train_dataset, val_dataset),
                        cfg,
                        extra,
                    )

        save_checkpoint(
            checkpoint_dir / "latest.pt",
            model,
            optimizer,
            scaler,
            _checkpoint_state(state, train_dataset, val_dataset),
            cfg,
            extra,
        )
        return {
            "state": state,
            "run_dir": str(run_dir),
            "extra": extra,
            "schedule": asdict(schedule),
            "artifacts": run_artifacts,
        }
    finally:
        try:
            if optimizer_step_tracker is not None:
                optimizer_step_tracker.close()
        finally:
            tracker.finish()


def _optional_file_hash(path: Path) -> str:
    return sha256_file(path) if path.exists() else "missing"


def _peak_memory_mb(device: torch.device) -> float:
    if device.type != "cuda":
        return 0.0
    return torch.cuda.max_memory_allocated(device) / (1024 * 1024)
