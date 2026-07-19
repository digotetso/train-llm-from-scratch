import pytest

from matgpt.config import load_config
from matgpt.training.schedule import build_training_schedule, learning_rate_at_step


def test_mini_schedule_math_is_unchanged_by_smoke_cap():
    cfg = load_config("configs/matgpt_mini_8m.yaml")
    schedule = build_training_schedule(cfg, global_step=0, max_steps_override=20)

    assert schedule.tokens_per_step == 32_768
    assert schedule.total_steps == 6_104
    assert schedule.warmup_steps == 122
    assert schedule.stop_step == 20


def test_resumed_learning_rates_equal_uninterrupted_learning_rates():
    cfg = load_config("configs/matgpt_mini_8m.yaml")
    uninterrupted = build_training_schedule(cfg)
    first = build_training_schedule(cfg, global_step=0, max_steps_override=20)
    resumed = build_training_schedule(cfg, global_step=20, max_steps_override=5)

    expected = [learning_rate_at_step(cfg, uninterrupted, step) for step in range(25)]
    actual = [learning_rate_at_step(cfg, first, step) for step in range(20)]
    actual += [learning_rate_at_step(cfg, resumed, step) for step in range(20, 25)]
    assert actual == expected


def test_step_override_must_be_positive():
    cfg = load_config("configs/matgpt_mini_8m.yaml")
    with pytest.raises(ValueError, match="positive"):
        build_training_schedule(cfg, max_steps_override=0)
