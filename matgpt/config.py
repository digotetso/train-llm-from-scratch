from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


REQUIRED_TOP_LEVEL_KEYS = {
    "run",
    "dataset",
    "tracking",
    "tokenizer",
    "sharding",
    "model",
    "training",
    "evaluation",
}

BYTE_LEVEL_ALPHABET_SIZE = 256


def minimum_byte_bpe_vocab_size(special_tokens: list[str]) -> int:
    return BYTE_LEVEL_ALPHABET_SIZE + len(set(special_tokens))


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"Config must be a mapping: {config_path}")
    validate_config(cfg)
    return cfg


def validate_config(cfg: dict[str, Any]) -> None:
    missing = REQUIRED_TOP_LEVEL_KEYS.difference(cfg)
    if missing:
        raise ValueError(f"Config missing top-level keys: {sorted(missing)}")

    model = cfg["model"]
    tokenizer = cfg["tokenizer"]
    sharding = cfg["sharding"]
    training = cfg["training"]
    dataset = cfg["dataset"]

    # Technical rule: d_model must be divisible by n_heads
    if model["d_model"] % model["n_heads"] != 0:
        raise ValueError("d_model must be divisible by n_heads")
    if model["vocab_size"] != tokenizer["vocab_size"]:
        raise ValueError("model.vocab_size must match tokenizer.vocab_size")
    if sharding.get("dtype") == "uint16" and tokenizer["vocab_size"] > 65535:
        raise ValueError("uint16 shards require tokenizer.vocab_size <= 65535")
    if model["context_length"] < 2:
        raise ValueError("model.context_length must be at least 2")
    if training["micro_batch_size"] < 1:
        raise ValueError("training.micro_batch_size must be positive")
    if training["gradient_accumulation_steps"] < 1:
        raise ValueError("training.gradient_accumulation_steps must be positive")
    if training.get("max_consecutive_skipped_updates", 5) < 1:
        raise ValueError("training.max_consecutive_skipped_updates must be positive")
    if training["max_tokens"] < model["context_length"]:
        raise ValueError("training.max_tokens must cover at least one sequence")

    training_splits = dataset.get("training_splits")
    data_phases = training.get("data_phases")
    if training_splits is not None:
        if not isinstance(training_splits, dict) or not training_splits:
            raise ValueError("dataset.training_splits must be a non-empty mapping")
        for name, split in training_splits.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("dataset.training_splits names must be non-empty")
            if not isinstance(split, str) or not split.strip():
                raise ValueError("dataset.training_splits values must be non-empty")
        if len(set(training_splits.values())) != len(training_splits):
            raise ValueError("dataset.training_splits values must be unique")
        if not isinstance(data_phases, list) or not data_phases:
            raise ValueError(
                "training.data_phases is required with dataset.training_splits"
            )
    elif data_phases is not None:
        raise ValueError(
            "dataset.training_splits is required with training.data_phases"
        )

    if data_phases is not None:
        allowed_phase_keys = {"name", "split", "until_tokens"}
        phase_names: set[str] = set()
        previous_boundary = 0
        configured_splits = set(training_splits.values())
        for index, phase in enumerate(data_phases):
            if not isinstance(phase, dict):
                raise ValueError(f"training.data_phases[{index}] must be a mapping")
            unknown_phase_keys = set(phase) - allowed_phase_keys
            if unknown_phase_keys:
                raise ValueError(
                    f"training.data_phases[{index}] contains unknown keys: "
                    f"{sorted(unknown_phase_keys)}"
                )
            name = phase.get("name")
            split = phase.get("split")
            boundary = phase.get("until_tokens")
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"training.data_phases[{index}].name must be non-empty")
            if name in phase_names:
                raise ValueError(f"Duplicate training data phase name: {name!r}")
            phase_names.add(name)
            if split not in configured_splits:
                raise ValueError(
                    f"training.data_phases[{index}] uses unknown training split "
                    f"{split!r}"
                )
            if (
                not isinstance(boundary, int)
                or isinstance(boundary, bool)
                or boundary <= previous_boundary
            ):
                raise ValueError(
                    "training.data_phases until_tokens must be strictly increasing"
                )
            previous_boundary = boundary
        if previous_boundary != training["max_tokens"]:
            raise ValueError(
                "The final training.data_phases until_tokens must equal "
                "training.max_tokens"
            )

    special_tokens = tokenizer.get("special_tokens", [])
    if tokenizer.get("algorithm") == "byte_level_bpe":
        minimum_vocab = minimum_byte_bpe_vocab_size(special_tokens)
        if tokenizer["vocab_size"] < minimum_vocab:
            raise ValueError(
                "byte_level_bpe tokenizer.vocab_size must be at least "
                f"{minimum_vocab} for 256 byte symbols and "
                f"{len(set(special_tokens))} unique special tokens"
            )
    for required in ("<|pad|>", "<|eos|>"):
        if required not in special_tokens:
            raise ValueError(f"tokenizer.special_tokens must include {required}")


def clone_config(cfg: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(cfg)


def config_to_yaml(cfg: dict[str, Any]) -> str:
    return yaml.safe_dump(cfg, sort_keys=False)
