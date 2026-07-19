import csv
import math

import pytest
import torch

from matgpt.data.shard import tokenize_jsonl_to_shards
from matgpt.model.gpt import GPT, GPTConfig
from matgpt.tokenizer.train import train_tokenizer_from_jsonl
from matgpt.training.amp import ScalerStepResult
from matgpt.training.metrics import METRIC_FIELDS
from matgpt.training.optim import build_optimizer
from matgpt.training import pretrain as pretrain_module
from matgpt.training.pretrain import run_pretraining, train_on_fixed_batch


SPECIAL_TOKENS = ["<|pad|>", "<|bos|>", "<|eos|>", "<|system|>", "<|user|>", "<|assistant|>", "<|end|>"]


def synthetic_pretraining_config(tmp_path):
    train_jsonl = tmp_path / "normalized" / "train.jsonl"
    val_jsonl = tmp_path / "normalized" / "validation.jsonl"
    train_jsonl.parent.mkdir(parents=True)
    train_jsonl.write_text('{"text": "A token is a piece of text. A model predicts tokens."}\n' * 20, encoding="utf-8")
    val_jsonl.write_text('{"text": "Validation text for a tiny language model."}\n' * 20, encoding="utf-8")

    tokenizer_dir = tmp_path / "tokenizer"
    train_tokenizer_from_jsonl([train_jsonl], tokenizer_dir, vocab_size=320, min_frequency=1, special_tokens=SPECIAL_TOKENS)
    shard_dir = tmp_path / "shards"
    tokenize_jsonl_to_shards(train_jsonl, tokenizer_dir, shard_dir, "train", shard_size_tokens=2048)
    tokenize_jsonl_to_shards(val_jsonl, tokenizer_dir, shard_dir, "validation", shard_size_tokens=2048)

    return {
        "run": {"name": "unit_pretrain", "seed": 0, "output_dir": str(tmp_path / "run")},
        "tracking": {"wandb": {"enabled": False, "project": "unit", "entity": None, "tags": []}},
        "dataset": {
            "train_split": "train",
            "validation_split": "validation",
            "normalized_dir": str(train_jsonl.parent),
        },
        "tokenizer": {"output_dir": str(tokenizer_dir), "vocab_size": 320},
        "sharding": {"output_dir": str(shard_dir)},
        "model": {
            "vocab_size": 320,
            "context_length": 8,
            "n_layers": 1,
            "n_heads": 4,
            "d_model": 32,
            "d_ff": 96,
            "dropout": 0.0,
            "norm_eps": 1.0e-5,
            "rope_base": 10000.0,
            "tie_embeddings": True,
            "use_bias": False,
            "activation": "swiglu",
        },
        "training": {
            "precision": "fp16",
            "compile": False,
            "micro_batch_size": 2,
            "gradient_accumulation_steps": 1,
            "max_tokens": 32,
            "optimizer": "adamw",
            "learning_rate": 1.0e-3,
            "min_learning_rate": 1.0e-4,
            "weight_decay": 0.0,
            "beta1": 0.9,
            "beta2": 0.95,
            "grad_clip": 1.0,
            "warmup_ratio": 0.1,
            "eval_interval_tokens": 0,
            "eval_batches": 1,
            "checkpoint_interval_tokens": 0,
            "sample_interval_tokens": 0,
            "log_interval_steps": 1,
            "max_consecutive_skipped_updates": 5,
            "save_best": True,
            "keep_milestones": False,
        },
        "evaluation": {
            "prompts": ["A token"],
            "max_new_tokens": 4,
            "temperature": 0.0,
            "top_k": None,
            "top_p": None,
        },
    }


def test_train_on_fixed_batch_reduces_loss():
    torch.manual_seed(0)
    model = GPT(
        GPTConfig(
            vocab_size=32,
            context_length=8,
            n_layers=1,
            n_heads=4,
            d_model=32,
            d_ff=96,
            dropout=0.0,
            norm_eps=1.0e-5,
            rope_base=10000.0,
            tie_embeddings=True,
            use_bias=False,
            activation="swiglu",
        )
    )
    optimizer = build_optimizer(model, "adamw", learning_rate=5e-3, weight_decay=0.0, betas=(0.9, 0.95))
    x = torch.tensor([[1, 2, 3, 4, 5, 6, 7, 8]] * 4)
    y = torch.tensor([[2, 3, 4, 5, 6, 7, 8, 9]] * 4)

    losses = train_on_fixed_batch(
        model=model,
        optimizer=optimizer,
        x=x,
        y=y,
        steps=12,
        device=torch.device("cpu"),
    )

    assert losses[-1] < losses[0]


def test_run_pretraining_one_step_with_synthetic_shards(tmp_path):
    cfg = synthetic_pretraining_config(tmp_path)

    result = run_pretraining(cfg, max_steps_override=1)

    assert result["state"]["global_step"] == 1
    assert result["schedule"]["tokens_per_step"] == 16
    assert result["schedule"]["total_steps"] == 2
    assert result["schedule"]["warmup_steps"] == 1
    assert result["schedule"]["stop_step"] == 1
    assert result["schedule"]["total_steps"] > result["schedule"]["stop_step"]
    assert (tmp_path / "run" / "checkpoints" / "latest.pt").exists()
    run_dir = tmp_path / "run"
    assert (run_dir / "config.snapshot.yaml").exists()
    assert (run_dir / "environment.json").exists()
    assert (run_dir / "fingerprints.json").exists()
    with (run_dir / "metrics.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    baseline_rows = [row for row in rows if row["event"] == "baseline"]
    assert tuple(reader.fieldnames or ()) == METRIC_FIELDS
    assert len(baseline_rows) == 1
    assert baseline_rows[0]["global_step"] == "0"
    assert math.isfinite(float(baseline_rows[0]["val_loss"]))
    assert rows[-1]["event"] == "train"
    assert rows[-1]["grad_scale"] == "1.0"
    assert rows[-1]["optimizer_step_skipped"] == "False"
    assert rows[-1]["optimizer_steps_skipped_total"] == "0"
    assert result["state"]["attempted_steps"] == 1
    assert result["state"]["global_step"] == 1
    assert result["artifacts"] == {
        "config": str(run_dir / "config.snapshot.yaml"),
        "environment": str(run_dir / "environment.json"),
        "fingerprints": str(run_dir / "fingerprints.json"),
    }


def test_fresh_run_rejects_an_initialized_metrics_file(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    metrics_path = run_dir / "metrics.csv"
    metrics_path.write_text("event\n", encoding="utf-8")
    cfg = {"run": {"name": "unit", "seed": 0, "output_dir": str(run_dir)}}

    with pytest.raises(ValueError, match="resume"):
        run_pretraining(cfg)

    assert metrics_path.read_text(encoding="utf-8") == "event\n"


def test_experiment_tracker_finishes_if_optimizer_step_tracker_construction_fails(tmp_path, monkeypatch):
    cfg = synthetic_pretraining_config(tmp_path)
    finish_calls = []

    class ExperimentTrackerProbe:
        def log(self, metrics, step=None):
            pass

        def finish(self):
            finish_calls.append("finish")

    def fail_optimizer_step_tracker(optimizer):
        raise RuntimeError("hook registration failed")

    monkeypatch.setattr(pretrain_module, "get_device", lambda: torch.device("cpu"))
    monkeypatch.setattr(
        pretrain_module,
        "create_tracker",
        lambda *args, **kwargs: ExperimentTrackerProbe(),
    )
    monkeypatch.setattr(pretrain_module, "OptimizerStepTracker", fail_optimizer_step_tracker)

    with pytest.raises(RuntimeError, match="hook registration failed"):
        run_pretraining(cfg, max_steps_override=1)

    assert finish_calls == ["finish"]


def test_five_consecutive_skips_abort_without_advancing_schedule_or_checkpoint(tmp_path, monkeypatch):
    cfg = synthetic_pretraining_config(tmp_path)
    cfg["training"].update(
        {
            "max_tokens": 96,
            "eval_interval_tokens": 96,
            "checkpoint_interval_tokens": 96,
            "sample_interval_tokens": 96,
            "log_interval_steps": 100,
        }
    )
    monkeypatch.setattr(pretrain_module, "get_device", lambda: torch.device("cpu"))
    first = run_pretraining(cfg, max_steps_override=1)
    checkpoint = tmp_path / "run" / "checkpoints" / "latest.pt"
    checkpoint_before = checkpoint.read_bytes()

    cleanup_calls = {"optimizer": 0, "tracker": 0}
    side_effect_calls = {"evaluation": 0, "sampling": 0, "checkpoint": 0}
    lr_steps = []
    real_optimizer_step_tracker = pretrain_module.OptimizerStepTracker
    real_learning_rate_at_step = pretrain_module.learning_rate_at_step

    class OptimizerStepTrackerProbe:
        def __init__(self, optimizer):
            self.inner = real_optimizer_step_tracker(optimizer)

        @property
        def count(self):
            return self.inner.count

        def close(self):
            cleanup_calls["optimizer"] += 1
            self.inner.close()

    class ExperimentTrackerProbe:
        def log(self, metrics, step=None):
            pass

        def finish(self):
            cleanup_calls["tracker"] += 1

    def force_skipped_step(scaler, optimizer, tracker):
        scale_before = float(scaler.get_scale())
        scaler.update()
        return ScalerStepResult(False, scale_before, float(scaler.get_scale()))

    def record_learning_rate(config, schedule, step):
        lr_steps.append(step)
        return real_learning_rate_at_step(config, schedule, step)

    def record_evaluation(**kwargs):
        side_effect_calls["evaluation"] += 1
        return 1.0

    def record_sampling(**kwargs):
        side_effect_calls["sampling"] += 1
        return []

    def record_checkpoint(*args, **kwargs):
        side_effect_calls["checkpoint"] += 1

    monkeypatch.setattr(pretrain_module, "OptimizerStepTracker", OptimizerStepTrackerProbe)
    monkeypatch.setattr(
        pretrain_module,
        "create_tracker",
        lambda *args, **kwargs: ExperimentTrackerProbe(),
    )
    monkeypatch.setattr(pretrain_module, "step_optimizer_with_scaler", force_skipped_step)
    monkeypatch.setattr(pretrain_module, "learning_rate_at_step", record_learning_rate)
    monkeypatch.setattr(pretrain_module, "evaluate_loss", record_evaluation)
    monkeypatch.setattr(pretrain_module, "generate_samples", record_sampling)
    monkeypatch.setattr(pretrain_module, "save_checkpoint", record_checkpoint)

    with pytest.raises(FloatingPointError, match="consecutive_skips=5"):
        run_pretraining(cfg, resume_from=checkpoint, max_steps_override=1)

    assert checkpoint.read_bytes() == checkpoint_before
    assert cleanup_calls == {"optimizer": 1, "tracker": 1}
    assert side_effect_calls == {"evaluation": 0, "sampling": 0, "checkpoint": 0}
    assert lr_steps == [1, 1, 1, 1, 1]

    with (tmp_path / "run" / "metrics.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    skipped_rows = [row for row in rows if row["optimizer_step_skipped"] == "True"]
    assert len(skipped_rows) == 5
    assert [int(row["attempted_step"]) for row in skipped_rows] == [2, 3, 4, 5, 6]
    assert [int(row["tokens_processed"]) for row in skipped_rows] == [32, 48, 64, 80, 96]
    assert all(row["global_step"] == "1" for row in skipped_rows)
    assert len({row["lr"] for row in skipped_rows}) == 1
    assert skipped_rows[-1]["optimizer_steps_skipped_total"] == "5"
    assert skipped_rows[-1]["consecutive_optimizer_steps_skipped"] == "5"
    assert first["state"]["attempted_steps"] == 1


def test_validation_metric_uses_attempted_step_after_skipped_update(tmp_path, monkeypatch):
    cfg = synthetic_pretraining_config(tmp_path)
    cfg["training"].update(
        {
            "max_tokens": 16,
            "eval_interval_tokens": 16,
            "log_interval_steps": 100,
        }
    )

    def force_skipped_step(scaler, optimizer, tracker):
        scale_before = float(scaler.get_scale())
        scaler.update()
        return ScalerStepResult(False, scale_before, float(scaler.get_scale()))

    monkeypatch.setattr(pretrain_module, "get_device", lambda: torch.device("cpu"))
    monkeypatch.setattr(pretrain_module, "evaluate_loss", lambda **kwargs: 1.0)
    monkeypatch.setattr(pretrain_module, "step_optimizer_with_scaler", force_skipped_step)

    run_pretraining(cfg, max_steps_override=1)

    with (tmp_path / "run" / "metrics.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    validation_rows = [row for row in rows if row["event"] == "validation"]
    assert len(validation_rows) == 1
    assert validation_rows[0]["attempted_step"] == "1"
    assert validation_rows[0]["global_step"] == "0"
    assert validation_rows[0]["tokens_processed"] == "16"


class StateRestoreProbe(dict):
    def __init__(self, state, calls):
        super().__init__(state)
        self.calls = calls

    def items(self):
        self.calls.append("scalar_state")
        return super().items()


def test_resume_rejects_missing_fingerprint_before_any_state_restore(tmp_path, monkeypatch):
    cfg = synthetic_pretraining_config(tmp_path)
    run_pretraining(cfg, max_steps_override=1)
    checkpoint = tmp_path / "run" / "checkpoints" / "latest.pt"
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    payload["extra"].pop("tokenizer_sha256")
    calls = []
    payload["state"] = StateRestoreProbe(payload["state"], calls)
    monkeypatch.setattr(pretrain_module, "load_checkpoint", lambda *args, **kwargs: payload)
    monkeypatch.setattr(
        pretrain_module,
        "apply_checkpoint_payload",
        lambda *args, **kwargs: calls.append("checkpoint_state"),
    )
    monkeypatch.setattr(
        pretrain_module,
        "_restore_dataset_rng_state",
        lambda *args, **kwargs: calls.append("dataset_state"),
    )

    with pytest.raises(ValueError, match="tokenizer_sha256"):
        run_pretraining(cfg, resume_from=checkpoint, max_steps_override=1)

    assert calls == []


def test_resume_rejects_artifact_conflict_before_any_state_restore(tmp_path, monkeypatch):
    cfg = synthetic_pretraining_config(tmp_path)
    run_pretraining(cfg, max_steps_override=1)
    run_dir = tmp_path / "run"
    checkpoint = run_dir / "checkpoints" / "latest.pt"
    (run_dir / "config.snapshot.yaml").write_text("conflicting: true\n", encoding="utf-8")
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    calls = []
    payload["state"] = StateRestoreProbe(payload["state"], calls)
    monkeypatch.setattr(pretrain_module, "load_checkpoint", lambda *args, **kwargs: payload)
    monkeypatch.setattr(
        pretrain_module,
        "apply_checkpoint_payload",
        lambda *args, **kwargs: calls.append("checkpoint_state"),
    )
    monkeypatch.setattr(
        pretrain_module,
        "_restore_dataset_rng_state",
        lambda *args, **kwargs: calls.append("dataset_state"),
    )

    with pytest.raises(ValueError, match="configuration snapshot"):
        run_pretraining(cfg, resume_from=checkpoint, max_steps_override=1)

    assert calls == []
