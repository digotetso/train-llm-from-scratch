import math
from types import SimpleNamespace

import pytest

from matgpt.config import clone_config, load_config
from scripts import benchmark_t4


def test_timed_steps_warm_up_and_synchronize_cuda(monkeypatch):
    events: list[str] = []
    clock_values = iter([10.0, 12.5])
    step_number = 0

    def training_step() -> int:
        nonlocal step_number
        events.append(f"step-{step_number}")
        result = step_number
        step_number += 1
        return result

    monkeypatch.setattr(
        benchmark_t4.torch.cuda,
        "synchronize",
        lambda device: events.append("sync"),
    )
    monkeypatch.setattr(
        benchmark_t4.time,
        "perf_counter",
        lambda: events.append("clock") or next(clock_values),
    )

    result, elapsed = benchmark_t4.run_timed_steps(
        training_step,
        device=SimpleNamespace(type="cuda"),
        steps=2,
        warmup_steps=1,
        before_timing=lambda: events.append("reset"),
    )

    assert result == 2
    assert elapsed == 2.5
    assert events == [
        "step-0",
        "sync",
        "reset",
        "clock",
        "step-1",
        "step-2",
        "sync",
        "clock",
    ]


def valid_cpu_measurements() -> dict[str, float]:
    return {
        "loss": 4.0,
        "grad_norm": 1.25,
        "tokens_per_second": 100.0,
        "peak_memory_mb": 0.0,
        "total_memory_mb": 0.0,
        "memory_fraction": 0.0,
    }


def valid_cuda_measurements() -> dict[str, float]:
    measurements = valid_cpu_measurements()
    measurements.update({
        "peak_memory_mb": 4096.0,
        "total_memory_mb": 16384.0,
        "memory_fraction": 0.25,
    })
    return measurements


def test_benchmark_reports_finite_loss_gradient_and_memory():
    cfg = clone_config(load_config("configs/matgpt_mini_8m.yaml"))
    cfg["model"].update({
        "vocab_size": 64,
        "context_length": 8,
        "n_layers": 1,
        "n_heads": 4,
        "d_model": 32,
        "d_ff": 96,
    })
    cfg["training"].update({"precision": "fp32", "grad_clip": 1.0})

    result = benchmark_t4.benchmark_batch_size(cfg, batch_size=2, steps=1)

    assert result["status"] == "ok"
    assert math.isfinite(result["loss"])
    assert math.isfinite(result["grad_norm"])
    assert result["tokens_per_second"] > 0
    assert result["memory_fraction"] == 0.0


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("loss", float("nan")),
        ("grad_norm", float("inf")),
        ("tokens_per_second", float("-inf")),
        ("peak_memory_mb", float("nan")),
        ("total_memory_mb", float("inf")),
        ("memory_fraction", float("nan")),
    ],
)
def test_benchmark_validation_rejects_every_non_finite_field(field, invalid_value):
    measurements = valid_cpu_measurements()
    measurements[field] = invalid_value

    with pytest.raises(FloatingPointError, match=field):
        benchmark_t4.validate_benchmark_measurements(measurements, device_type="cpu")


@pytest.mark.parametrize("throughput", [0.0, -1.0])
def test_benchmark_validation_requires_positive_throughput(throughput):
    measurements = valid_cpu_measurements()
    measurements["tokens_per_second"] = throughput

    with pytest.raises(ValueError, match="tokens_per_second must be positive"):
        benchmark_t4.validate_benchmark_measurements(measurements, device_type="cpu")


@pytest.mark.parametrize(
    ("field", "invalid_value", "message"),
    [
        ("total_memory_mb", 0.0, "total_memory_mb must be positive"),
        ("total_memory_mb", -1.0, "total_memory_mb must be positive"),
        ("peak_memory_mb", -1.0, "peak_memory_mb must be nonnegative"),
        ("memory_fraction", -0.25, "memory_fraction must be nonnegative"),
    ],
)
def test_cuda_benchmark_validation_rejects_invalid_memory_bounds(
    field, invalid_value, message
):
    measurements = valid_cuda_measurements()
    measurements[field] = invalid_value

    with pytest.raises(ValueError, match=message):
        benchmark_t4.validate_benchmark_measurements(measurements, device_type="cuda")


def test_cuda_benchmark_validation_rejects_inconsistent_memory_fraction():
    measurements = valid_cuda_measurements()
    measurements["memory_fraction"] = 0.250001

    with pytest.raises(ValueError, match="does not match peak_memory_mb / total_memory_mb"):
        benchmark_t4.validate_benchmark_measurements(measurements, device_type="cuda")


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("peak_memory_mb", 1.0),
        ("total_memory_mb", 1.0),
        ("memory_fraction", 0.1),
    ],
)
def test_cpu_benchmark_validation_requires_zero_memory_fields(field, invalid_value):
    measurements = valid_cpu_measurements()
    measurements[field] = invalid_value

    with pytest.raises(ValueError, match="CPU benchmark memory fields must be zero"):
        benchmark_t4.validate_benchmark_measurements(measurements, device_type="cpu")


def test_benchmark_validation_accepts_consistent_cpu_and_cuda_measurements():
    benchmark_t4.validate_benchmark_measurements(
        valid_cpu_measurements(), device_type="cpu"
    )
    benchmark_t4.validate_benchmark_measurements(
        valid_cuda_measurements(), device_type="cuda"
    )
