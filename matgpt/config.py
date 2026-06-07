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
    if training["max_tokens"] < model["context_length"]:
        raise ValueError("training.max_tokens must cover at least one sequence")

    special_tokens = tokenizer.get("special_tokens", [])
    for required in ("<|pad|>", "<|eos|>"):
        if required not in special_tokens:
            raise ValueError(f"tokenizer.special_tokens must include {required}")


def clone_config(cfg: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(cfg)


def config_to_yaml(cfg: dict[str, Any]) -> str:
    return yaml.safe_dump(cfg, sort_keys=False)
