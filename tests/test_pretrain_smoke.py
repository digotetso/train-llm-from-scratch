import torch

from matgpt.data.shard import tokenize_jsonl_to_shards
from matgpt.model.gpt import GPT, GPTConfig
from matgpt.tokenizer.train import train_tokenizer_from_jsonl
from matgpt.training.optim import build_optimizer
from matgpt.training.pretrain import run_pretraining, train_on_fixed_batch


SPECIAL_TOKENS = ["<|pad|>", "<|bos|>", "<|eos|>", "<|system|>", "<|user|>", "<|assistant|>", "<|end|>"]


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

    cfg = {
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

    result = run_pretraining(cfg, max_steps_override=1)

    assert result["state"]["global_step"] == 1
    assert result["schedule"]["tokens_per_step"] == 16
    assert result["schedule"]["total_steps"] == 2
    assert result["schedule"]["warmup_steps"] == 1
    assert result["schedule"]["stop_step"] == 1
    assert result["schedule"]["total_steps"] > result["schedule"]["stop_step"]
    assert (tmp_path / "run" / "checkpoints" / "latest.pt").exists()
