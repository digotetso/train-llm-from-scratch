#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch

from matgpt.config import load_config
from matgpt.eval.lm import evaluate_loss, generate_samples, perplexity
from matgpt.model.gpt import GPT, GPTConfig
from matgpt.tokenizer.io import load_tokenizer
from matgpt.training.checkpoint import load_checkpoint
from matgpt.training.dataset import PackedTokenDataset, metadata_path_for_split
from matgpt.training.pretrain import get_device
from matgpt.data.prepare import effective_validation_split


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a MatGPT base checkpoint.")
    parser.add_argument("--config", required=True, help="Path to MatGPT YAML config.")
    parser.add_argument("--checkpoint", required=True, help="Checkpoint path.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    device = get_device()
    model = GPT(GPTConfig.from_dict(cfg["model"])).to(device)
    load_checkpoint(args.checkpoint, model=model, map_location=device)
    tokenizer = load_tokenizer(cfg["tokenizer"]["output_dir"])
    val_dataset = PackedTokenDataset.from_metadata(
        metadata_path_for_split(cfg["sharding"]["output_dir"], effective_validation_split(cfg["dataset"])),
        context_length=cfg["model"]["context_length"],
        seed=cfg["run"]["seed"] + 1,
    )
    val_loss = evaluate_loss(
        model,
        val_dataset,
        batch_size=cfg["training"]["micro_batch_size"],
        eval_batches=cfg["training"]["eval_batches"],
        device=device,
        precision=cfg["training"]["precision"],
    )
    samples = generate_samples(
        model=model,
        tokenizer=tokenizer,
        prompts=cfg["evaluation"]["prompts"],
        max_new_tokens=cfg["evaluation"]["max_new_tokens"],
        eos_id=tokenizer.token_to_id("<|eos|>"),
        temperature=cfg["evaluation"]["temperature"],
        top_k=cfg["evaluation"]["top_k"],
        top_p=cfg["evaluation"]["top_p"],
        device=device,
    )
    print(json.dumps({"val_loss": val_loss, "perplexity": perplexity(val_loss), "samples": samples}, indent=2))


if __name__ == "__main__":
    main()
