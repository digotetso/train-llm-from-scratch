#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch

from matgpt.config import config_to_yaml, load_config
from matgpt.eval.lm import evaluate_loss, generate_samples, perplexity
from matgpt.model.gpt import GPT, GPTConfig
from matgpt.tokenizer.io import load_tokenizer, load_tokenizer_metadata
from matgpt.training.checkpoint import apply_checkpoint_payload, load_checkpoint
from matgpt.training.dataset import PackedTokenDataset, metadata_path_for_split
from matgpt.training.pretrain import get_device, validate_checkpoint_compatibility
from matgpt.training.run_summary import write_evaluation_result
from matgpt.data.prepare import effective_validation_split
from matgpt.utils.hashing import sha256_file, sha256_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a MatGPT base checkpoint.")
    parser.add_argument("--config", required=True, help="Path to MatGPT YAML config.")
    parser.add_argument("--checkpoint", required=True, help="Checkpoint path.")
    parser.add_argument("--output", help="Path for the evaluation JSON artifact.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    default_output = Path(cfg["run"]["output_dir"]) / "evaluation" / f"{Path(args.checkpoint).stem}.json"
    output_path = Path(args.output) if args.output else default_output
    device = get_device()
    model = GPT(GPTConfig.from_dict(cfg["model"])).to(device)
    payload = load_checkpoint(args.checkpoint, map_location=device)
    if not cfg["training"].get("allow_artifact_mismatch", False):
        tokenizer_metadata = load_tokenizer_metadata(cfg["tokenizer"]["output_dir"])
        expected_fingerprints = {
            "config_sha256": sha256_text(config_to_yaml(cfg)),
            "tokenizer_sha256": tokenizer_metadata["tokenizer_sha256"],
            "dataset_manifest_hash": sha256_file(
                Path(cfg["dataset"]["normalized_dir"]) / "manifest.json"
            ),
        }
        validate_checkpoint_compatibility(payload, expected_fingerprints)
    apply_checkpoint_payload(payload, model=model)
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
    result = {
        "checkpoint": str(Path(args.checkpoint)),
        "val_loss": val_loss,
        "perplexity": perplexity(val_loss),
        "samples": samples,
    }
    write_evaluation_result(output_path, result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
