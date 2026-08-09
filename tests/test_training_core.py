import json
from pathlib import Path

import numpy as np
import pytest
import torch

from matgpt.model.gpt import GPT, GPTConfig
from matgpt.training.amp import OptimizerStepTracker, require_finite_loss, step_optimizer_with_scaler
from matgpt.training.checkpoint import apply_checkpoint_payload, load_checkpoint, save_checkpoint
from matgpt.training.dataset import PackedTokenDataset
from matgpt.training.pretrain import validate_checkpoint_compatibility
from matgpt.training.optim import build_optimizer, cosine_warmup_lr
from matgpt.utils.hashing import sha256_file, sha256_json


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
        "shards": [
            {
                "path": str(shard_path),
                "num_tokens": 128,
                "sha256": sha256_file(shard_path),
            }
        ],
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


def test_packed_token_dataset_rejects_traversal_and_checksum_drift(tmp_path: Path):
    managed = tmp_path / "managed"
    managed.mkdir()
    metadata_path = write_shard_metadata(managed)
    outside = tmp_path / "outside.bin"
    np.arange(128, dtype=np.uint16).tofile(outside)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["shards"][0]["path"] = "../outside.bin"
    metadata["shards"][0]["sha256"] = sha256_file(outside)
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(ValueError, match="safe relative|escapes"):
        PackedTokenDataset.from_metadata(metadata_path, context_length=8)

    checksum = tmp_path / "checksum"
    checksum.mkdir()
    metadata_path = write_shard_metadata(checksum)
    shard = checksum / "train_00000.bin"
    shard.write_bytes(shard.read_bytes() + b"\x00\x00")
    with pytest.raises(ValueError, match="size|SHA-256"):
        PackedTokenDataset.from_metadata(metadata_path, context_length=8)


def test_packed_token_dataset_consumes_only_manifest_bound_metadata(tmp_path: Path):
    finalized_root = tmp_path / "finalized-a"
    finalized_root.mkdir()
    metadata_path = write_shard_metadata(finalized_root)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["shards"][0]["path"] = "train_00000.bin"
    metadata["metadata_sha256"] = sha256_json(metadata)
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest_artifact = {
        "path": "train_metadata.json",
        "size": metadata_path.stat().st_size,
        "sha256": sha256_file(metadata_path),
        "metadata_sha256": metadata["metadata_sha256"],
    }

    accepted = PackedTokenDataset.from_metadata(
        metadata_path,
        context_length=8,
        metadata_root=finalized_root,
        finalized_root=finalized_root,
        finalized_artifact=manifest_artifact,
    )

    alternate_root = tmp_path / "recomputed-b"
    alternate_root.mkdir()
    alternate_metadata = alternate_root / metadata_path.name
    alternate_shard = alternate_root / "train_00000.bin"
    alternate_metadata.write_bytes(metadata_path.read_bytes())
    alternate_shard.write_bytes((finalized_root / "train_00000.bin").read_bytes())
    with pytest.raises(ValueError, match="finalized manifest"):
        PackedTokenDataset.from_metadata(
            alternate_metadata,
            context_length=8,
            metadata_root=alternate_root,
            finalized_root=finalized_root,
            finalized_artifact=manifest_artifact,
        )

    wrong_internal_fingerprint = dict(manifest_artifact)
    wrong_internal_fingerprint["metadata_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="internal fingerprint"):
        PackedTokenDataset.from_metadata(
            metadata_path,
            context_length=8,
            metadata_root=finalized_root,
            finalized_root=finalized_root,
            finalized_artifact=wrong_internal_fingerprint,
        )

    assert accepted.shards[0].path == finalized_root / "train_00000.bin"


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


class FakeScaler:
    def __init__(self, apply_update: bool):
        self.apply_update = apply_update
        self.scale_value = 1024.0

    def get_scale(self):
        return self.scale_value

    def step(self, optimizer):
        if self.apply_update:
            optimizer.step()

    def update(self):
        if not self.apply_update:
            self.scale_value /= 2


def test_optimizer_step_tracker_detects_applied_and_skipped_updates():
    parameter = torch.nn.Parameter(torch.tensor(1.0))
    optimizer = torch.optim.SGD([parameter], lr=0.1)
    tracker = OptimizerStepTracker(optimizer)
    try:
        applied = step_optimizer_with_scaler(FakeScaler(True), optimizer, tracker)
        skipped = step_optimizer_with_scaler(FakeScaler(False), optimizer, tracker)
    finally:
        tracker.close()

    assert applied.update_applied is True
    assert skipped.update_applied is False
    assert skipped.scale_after == 512.0


def test_require_finite_loss_rejects_nan():
    with pytest.raises(FloatingPointError, match="micro-batch"):
        require_finite_loss(
            torch.tensor(float("nan")),
            global_step=7,
            label="micro-batch",
            lr=1e-4,
            grad_scale=1024.0,
        )


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


def test_packed_token_dataset_rng_state_round_trips(tmp_path: Path):
    dataset = PackedTokenDataset.from_metadata(write_shard_metadata(tmp_path), context_length=8, seed=0)
    _ = dataset.sample_batch(batch_size=2, device=torch.device("cpu"))
    state = dataset.get_rng_state()
    expected = dataset.sample_batch(batch_size=2, device=torch.device("cpu"))

    restored = PackedTokenDataset.from_metadata(write_shard_metadata(tmp_path), context_length=8, seed=0)
    restored.set_rng_state(state)
    actual = restored.sample_batch(batch_size=2, device=torch.device("cpu"))

    assert torch.equal(actual[0], expected[0])
    assert torch.equal(actual[1], expected[1])


def test_validate_checkpoint_compatibility_rejects_artifact_mismatch():
    payload = {
        "extra": {
            "config_sha256": "old-config",
            "tokenizer_sha256": "same-tokenizer",
            "dataset_manifest_hash": "same-dataset",
        }
    }

    try:
        validate_checkpoint_compatibility(
            payload,
            {
                "config_sha256": "new-config",
                "tokenizer_sha256": "same-tokenizer",
                "dataset_manifest_hash": "same-dataset",
            },
        )
    except ValueError as exc:
        assert "config_sha256" in str(exc)
    else:
        raise AssertionError("expected artifact mismatch to be rejected")


def test_validate_checkpoint_compatibility_rejects_missing_fingerprints():
    expected = {
        "config_sha256": "config",
        "tokenizer_sha256": "tokenizer",
        "dataset_manifest_hash": "dataset",
    }

    for missing_key in expected:
        checkpoint_extra = dict(expected)
        checkpoint_extra.pop(missing_key)
        with pytest.raises(ValueError, match=missing_key):
            validate_checkpoint_compatibility({"extra": checkpoint_extra}, expected)


def test_checkpoint_can_be_validated_before_state_is_applied(tmp_path: Path):
    torch.manual_seed(7)
    source = GPT(tiny_config())
    source_optimizer = build_optimizer(source, "adamw", 1e-3, 0.1, (0.9, 0.95))
    checkpoint = tmp_path / "latest.pt"
    save_checkpoint(
        checkpoint,
        source,
        source_optimizer,
        None,
        {"global_step": 3, "tokens_processed": 1024},
        {"run": {"name": "unit"}},
        {
            "config_sha256": "expected-config",
            "tokenizer_sha256": "expected-tokenizer",
            "dataset_manifest_hash": "expected-dataset",
        },
    )
    restored = GPT(tiny_config())
    before = {name: value.detach().clone() for name, value in restored.state_dict().items()}

    payload = load_checkpoint(checkpoint)
    assert all(torch.equal(before[name], value) for name, value in restored.state_dict().items())
    validate_checkpoint_compatibility(
        payload,
        {
            "config_sha256": "expected-config",
            "tokenizer_sha256": "expected-tokenizer",
            "dataset_manifest_hash": "expected-dataset",
        },
    )
    apply_checkpoint_payload(payload, model=restored)

    assert all(
        torch.equal(source.state_dict()[name], restored.state_dict()[name])
        for name in source.state_dict()
    )
