from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass

import torch


def autocast_context(device: torch.device, precision: str):

    #  If training is not using a CUDA GPU,
    # do not enable CUDA's automatic precision selection.
    if device.type != "cuda":
        return nullcontext()

    # If the configuration requests fp16,
    # let PyTorch use FP16 for suitable CUDA calculations.
    if precision == "fp16":
        return torch.autocast(device_type="cuda", dtype=torch.float16)

    # Use BF16 autocasting when requested.
    if precision == "bf16":
        return torch.autocast(device_type="cuda", dtype=torch.bfloat16)
    return nullcontext()


def make_grad_scaler(device: torch.device, precision: str):
    # The repo enables GradScaler only for FP16
    # It does not enable it for BF16.
    # BF16’s much wider numerical range makes gradient overflow and underflow less likely, so BF16 training commonly does not require gradient scaling.
    enabled = device.type == "cuda" and precision == "fp16"
    try:
        return torch.amp.GradScaler("cuda", enabled=enabled)
    except TypeError:
        return torch.cuda.amp.GradScaler(enabled=enabled)


@dataclass(frozen=True)
class ScalerStepResult:
    update_applied: bool
    scale_before: float
    scale_after: float


class OptimizerStepTracker:
    def __init__(self, optimizer: torch.optim.Optimizer) -> None:
        self.count = 0
        self._handle = optimizer.register_step_pre_hook(self._before_step)

    def _before_step(self, optimizer, args, kwargs):
        self.count += 1

    def close(self) -> None:
        self._handle.remove()


def step_optimizer_with_scaler(scaler, optimizer, tracker) -> ScalerStepResult:
    count_before = tracker.count
    scale_before = float(scaler.get_scale())
    scaler.step(optimizer)
    scaler.update()
    return ScalerStepResult(
        update_applied=tracker.count > count_before,
        scale_before=scale_before,
        scale_after=float(scaler.get_scale()),
    )


def require_finite_loss(
    loss: torch.Tensor,
    *,
    global_step: int,
    label: str,
    lr: float,
    grad_scale: float,
) -> None:
    if bool(torch.isfinite(loss).all()):
        return
    value = float(loss.detach().cpu())
    raise FloatingPointError(
        f"Non-finite {label} loss at global_step={global_step}: "
        f"loss={value} lr={lr} grad_scale={grad_scale}"
    )
