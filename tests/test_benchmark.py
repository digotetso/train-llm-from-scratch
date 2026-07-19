import math

from matgpt.config import clone_config, load_config
from scripts.benchmark_t4 import benchmark_batch_size


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

    result = benchmark_batch_size(cfg, batch_size=2, steps=1)

    assert result["status"] == "ok"
    assert math.isfinite(result["loss"])
    assert math.isfinite(result["grad_norm"])
    assert result["tokens_per_second"] > 0
    assert result["memory_fraction"] == 0.0
