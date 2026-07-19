from __future__ import annotations

import re
from typing import Any

from matgpt.model.gpt import GPT, GPTConfig, count_parameters


SIZE_LABEL_RE = re.compile(r"(?:^|_)(\d+)([mb])(?:_|$)", re.IGNORECASE)


def parse_size_label(name: str) -> int | None:
    match = SIZE_LABEL_RE.search(name)
    if not match:
        return None
    value = int(match.group(1))
    suffix = match.group(2).lower()
    multiplier = 1_000_000 if suffix == "m" else 1_000_000_000
    return value * multiplier


def build_model_report(cfg: dict[str, Any], drift_tolerance: float = 0.10) -> dict[str, Any]:
    parameter_count = count_parameters(GPT(GPTConfig.from_dict(cfg["model"])))
    label_parameters = parse_size_label(cfg["run"]["name"])
    drift_fraction = None
    matches = None
    if label_parameters:
        drift_fraction = abs(parameter_count - label_parameters) / label_parameters
        matches = drift_fraction <= drift_tolerance

    return {
        "run_name": cfg["run"]["name"],
        "parameter_count": parameter_count,
        "size_label_parameters": label_parameters,
        "size_label_drift_fraction": drift_fraction,
        "size_label_matches": matches,
        "model": {
            "vocab_size": cfg["model"]["vocab_size"],
            "context_length": cfg["model"]["context_length"],
            "n_layers": cfg["model"]["n_layers"],
            "n_heads": cfg["model"]["n_heads"],
            "d_model": cfg["model"]["d_model"],
            "d_ff": cfg["model"]["d_ff"],
        },
    }
