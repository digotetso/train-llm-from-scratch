import json
from pathlib import Path

import numpy as np
import torch

from matgpt.model.gpt import GPT, GPTConfig
from matgpt.training.checkpoint import load_checkpoint, save_checkpoint
from matgpt.training.dataset import PackedTokenDataset
from matgpt.training.optim import build_optimizer, cosine_warmup_lr


def tiny_config(vocab_size: int = 64) -> GPTConfig:
    return GPTConfig(
        vocab_size=vocab_size,
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


def write_shard_metadata(tmp_path: Path) -> Path:
    shard_path = tmp_path / "train_00000.bin"
    np.arange(128, dtype=np.uint16).tofile(shard_path)
    metadata = {
        "split": "train",
        "dtype": "uint16",
        "total_tokens": 128,
        "shards": [{"path": str(shard_path), "num_tokens": 128, "sha256": "x"}],
    }
    metadata_path = tmp_path / "train_metadata.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    return metadata_path


def test_packed_token_dataset_samples_next_token_targets(tmp_path: Path):
    dataset = PackedTokenDataset.from_metadata(write_shard_metadata(tmp_path), context_length=8, seed=0)

    x, y = dataset.sample_batch(batch_size=4, device=torch.device("cpu"))

    assert x.shape == (4, 8)
    assert y.shape == (4, 8)
    assert torch.equal(y[:, :-1], x[:, 1:])


def test_optimizer_and_lr_schedule():
    model = GPT(tiny_config())
    opt = build_optimizer(
        model,
        optimizer_name="adamw",
        learning_rate=1e-3,
        weight_decay=0.1,
        betas=(0.9, 0.95),
    )

    assert len(opt.param_groups) == 2
    assert cosine_warmup_lr(step=0, warmup_steps=10, total_steps=100, max_lr=1e-3, min_lr=1e-4) == 0.0
    assert cosine_warmup_lr(step=10, warmup_steps=10, total_steps=100, max_lr=1e-3, min_lr=1e-4) == 1e-3


def test_checkpoint_save_load_restores_model_equivalence(tmp_path: Path):
    torch.manual_seed(7)
    model = GPT(tiny_config())
    optimizer = build_optimizer(model, "adamw", 1e-3, 0.1, (0.9, 0.95))
    x = torch.randint(0, 64, (2, 8))
    logits_before, _ = model(x)

    checkpoint_path = tmp_path / "latest.pt"
    save_checkpoint(
        path=checkpoint_path,
        model=model,
        optimizer=optimizer,
        scaler=None,
        state={"global_step": 3, "tokens_processed": 1024, "best_val_loss": 2.5},
        config={"run": {"name": "unit"}},
        extra={"dataset_manifest_hash": "abc"},
    )

    restored = GPT(tiny_config())
    restored_optimizer = build_optimizer(restored, "adamw", 1e-3, 0.1, (0.9, 0.95))
    payload = load_checkpoint(checkpoint_path, model=restored, optimizer=restored_optimizer)
    logits_after, _ = restored(x)

    assert payload["state"]["tokens_processed"] == 1024
    assert payload["extra"]["dataset_manifest_hash"] == "abc"
    assert torch.allclose(logits_before, logits_after)
