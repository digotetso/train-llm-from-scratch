#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.config import load_config
from matgpt.eval.tasks import evaluate_multiple_choice_file
from matgpt.model.gpt import GPT, GPTConfig
from matgpt.tokenizer.io import load_tokenizer
from matgpt.training.checkpoint import apply_checkpoint_payload, load_checkpoint
from matgpt.training.checkpoint_provenance import (
    checkpoint_binding,
    training_artifact_identity,
)
from matgpt.training.pretrain import get_device, validate_checkpoint_compatibility


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a checkpoint on local multiple-choice JSONL tasks.")
    parser.add_argument("--config", required=True, help="Path to MatGPT YAML config.")
    parser.add_argument("--checkpoint", required=True, help="Checkpoint path.")
    parser.add_argument("--task", action="append", required=True, help="JSONL task path. Repeat for multiple tasks.")
    parser.add_argument("--output", default=None, help="Optional JSON output path.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    binding = checkpoint_binding(args.checkpoint)
    artifact_identity = training_artifact_identity(cfg)
    device = get_device()
    model = GPT(GPTConfig.from_dict(cfg["model"])).to(device)
    checkpoint_payload = load_checkpoint(binding["path"], map_location=device)
    if not cfg["training"].get("allow_artifact_mismatch", False):
        validate_checkpoint_compatibility(checkpoint_payload, {
            "config_sha256": artifact_identity["config_sha256"],
            "tokenizer_sha256": artifact_identity["tokenizer_sha256"],
            "dataset_manifest_hash": artifact_identity["dataset_manifest_sha256"],
        })
    apply_checkpoint_payload(checkpoint_payload, model=model)
    tokenizer = load_tokenizer(cfg["tokenizer"]["output_dir"])

    results = [
        evaluate_multiple_choice_file(
            model=model,
            tokenizer=tokenizer,
            path=task_path,
            device=device,
            precision=cfg["training"]["precision"],
        )
        for task_path in args.task
    ]
    payload = {
        "checkpoint": binding["path"],
        "checkpoint_binding": binding,
        "artifact_identity": artifact_identity,
        "tasks": results,
    }
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
