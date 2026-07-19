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
from matgpt.training.checkpoint import load_checkpoint
from matgpt.training.pretrain import get_device


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a checkpoint on local multiple-choice JSONL tasks.")
    parser.add_argument("--config", required=True, help="Path to MatGPT YAML config.")
    parser.add_argument("--checkpoint", required=True, help="Checkpoint path.")
    parser.add_argument("--task", action="append", required=True, help="JSONL task path. Repeat for multiple tasks.")
    parser.add_argument("--output", default=None, help="Optional JSON output path.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    device = get_device()
    model = GPT(GPTConfig.from_dict(cfg["model"])).to(device)
    load_checkpoint(args.checkpoint, model=model, map_location=device)
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
    payload = {"tasks": results}
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
