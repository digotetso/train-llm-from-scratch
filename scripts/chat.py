#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch

from matgpt.config import load_config
from matgpt.model.generation import generate
from matgpt.model.gpt import GPT, GPTConfig
from matgpt.tokenizer.io import load_tokenizer
from matgpt.training.checkpoint import load_checkpoint
from matgpt.training.pretrain import get_device


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate text from a MatGPT base checkpoint.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--max-new-tokens", type=int, default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    device = get_device()
    tokenizer = load_tokenizer(cfg["tokenizer"]["output_dir"])
    model = GPT(GPTConfig.from_dict(cfg["model"])).to(device)
    load_checkpoint(args.checkpoint, model=model, map_location=device)
    input_ids = torch.tensor([tokenizer.encode(args.prompt).ids], dtype=torch.long, device=device)
    output = generate(
        model=model,
        input_ids=input_ids,
        max_new_tokens=args.max_new_tokens or cfg["evaluation"]["max_new_tokens"],
        eos_id=tokenizer.token_to_id("<|eos|>"),
        temperature=cfg["evaluation"]["temperature"],
        top_k=cfg["evaluation"]["top_k"],
        top_p=cfg["evaluation"]["top_p"],
    )
    print(tokenizer.decode(output[0].detach().cpu().tolist()))


if __name__ == "__main__":
    main()
