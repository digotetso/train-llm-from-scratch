#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch

from matgpt.config import config_to_yaml, load_config
from matgpt.data.prepare import effective_validation_split
from matgpt.eval.assets import (
    StoryPrompt,
    load_story_prompts,
    validate_consistency_asset,
)
from matgpt.eval.comparison import (
    CheckpointSpec,
    parse_checkpoint_specs,
    parse_seed_list,
    summarize_generations,
    summarize_validation,
)
from matgpt.eval.judge import build_judge_bundle, write_judge_bundle
from matgpt.eval.lm import evaluate_loss, generate_samples, perplexity
from matgpt.eval.repetition import measure_repetition
from matgpt.eval.tasks import evaluate_multiple_choice_file
from matgpt.model.gpt import GPT, GPTConfig
from matgpt.tokenizer.io import load_tokenizer, load_tokenizer_metadata
from matgpt.training.checkpoint import apply_checkpoint_payload, load_checkpoint
from matgpt.training.dataset import PackedTokenDataset, metadata_path_for_split
from matgpt.training.pretrain import get_device, validate_checkpoint_compatibility
from matgpt.training.run_summary import write_evaluation_result
from matgpt.utils.hashing import sha256_file, sha256_text
from matgpt.utils.seed import set_seed


DEFAULT_VALIDATION_SEEDS = "1001,1002,1003,1004,1005,1006,1007,1008,1009,1010"
DEFAULT_GENERATION_SEEDS = "2001,2002,2003,2004,2005"


@dataclass(frozen=True)
class EvaluationRequest:
    config_path: Path
    checkpoints: list[CheckpointSpec]
    validation_seeds: list[int]
    generation_seeds: list[int]
    prompts_path: Path
    prompts: list[StoryPrompt]
    task_path: Path
    task_counts: dict[str, int]
    judge_prompt_path: Path
    judge_prompt_text: str
    review_per_checkpoint: int
    review_seed: int
    judge_batch_size: int
    output_dir: Path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare preserved MatGPT checkpoints under one fixed protocol."
    )
    parser.add_argument("--config", required=True, help="MatGPT YAML config path.")
    parser.add_argument(
        "--checkpoint",
        action="append",
        required=True,
        help="Checkpoint in LABEL=PATH form. Repeat at least twice.",
    )
    parser.add_argument(
        "--validation-seeds", default=DEFAULT_VALIDATION_SEEDS
    )
    parser.add_argument(
        "--generation-seeds", default=DEFAULT_GENERATION_SEEDS
    )
    parser.add_argument("--prompts", default="evals/story_prompts.jsonl")
    parser.add_argument("--task", default="evals/story_consistency.jsonl")
    parser.add_argument("--judge-prompt", default="evals/story_judge_prompt.md")
    parser.add_argument("--review-per-checkpoint", type=int, default=50)
    parser.add_argument("--review-seed", type=int, default=3001)
    parser.add_argument("--judge-batch-size", type=int, default=20)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def _required_file(path: str | Path, name: str) -> Path:
    result = Path(path).expanduser()
    if not result.is_file():
        raise ValueError(f"{name} file does not exist: {result}")
    return result


def validate_request(args: argparse.Namespace) -> EvaluationRequest:
    validation_seeds = parse_seed_list(args.validation_seeds, "validation")
    generation_seeds = parse_seed_list(args.generation_seeds, "generation")
    checkpoints = parse_checkpoint_specs(args.checkpoint)
    if len(checkpoints) < 2:
        raise ValueError("at least two checkpoints are required")

    config_path = _required_file(args.config, "config")
    prompts_path = _required_file(args.prompts, "prompts")
    task_path = _required_file(args.task, "task")
    judge_prompt_path = _required_file(args.judge_prompt, "judge prompt")
    output_dir = Path(args.output_dir).expanduser()
    if output_dir.exists():
        raise FileExistsError(f"comparison output already exists: {output_dir}")
    if args.review_per_checkpoint <= 0:
        raise ValueError("review-per-checkpoint must be positive")
    if args.judge_batch_size <= 0:
        raise ValueError("judge-batch-size must be positive")
    review_seed = parse_seed_list(str(args.review_seed), "review")[0]

    prompts = load_story_prompts(prompts_path)
    if not prompts:
        raise ValueError("prompt asset must contain at least one prompt")
    task_counts = validate_consistency_asset(task_path)
    judge_prompt_text = judge_prompt_path.read_text(encoding="utf-8")
    if not judge_prompt_text.strip():
        raise ValueError("judge prompt must not be empty")
    return EvaluationRequest(
        config_path=config_path,
        checkpoints=checkpoints,
        validation_seeds=validation_seeds,
        generation_seeds=generation_seeds,
        prompts_path=prompts_path,
        prompts=prompts,
        task_path=task_path,
        task_counts=task_counts,
        judge_prompt_path=judge_prompt_path,
        judge_prompt_text=judge_prompt_text,
        review_per_checkpoint=args.review_per_checkpoint,
        review_seed=review_seed,
        judge_batch_size=args.judge_batch_size,
        output_dir=output_dir,
    )


def _ensure_finite_numbers(value: object, context: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{context} contains a non-finite number")
    if isinstance(value, dict):
        for nested in value.values():
            _ensure_finite_numbers(nested, context)
    elif isinstance(value, list):
        for nested in value:
            _ensure_finite_numbers(nested, context)


def _expected_fingerprints(cfg: dict[str, Any]) -> dict[str, str]:
    tokenizer_metadata = load_tokenizer_metadata(cfg["tokenizer"]["output_dir"])
    return {
        "config_sha256": sha256_text(config_to_yaml(cfg)),
        "tokenizer_sha256": tokenizer_metadata["tokenizer_sha256"],
        "dataset_manifest_hash": sha256_file(
            Path(cfg["dataset"]["normalized_dir"]) / "manifest.json"
        ),
    }


def _task_summary(task_result: dict[str, Any]) -> dict[str, object]:
    return {
        "total": task_result["total"],
        "correct": task_result["correct"],
        "accuracy": task_result["accuracy"],
        "categories": task_result.get("categories", {}),
    }


def _evaluate_checkpoint(
    spec: CheckpointSpec,
    request: EvaluationRequest,
    cfg: dict[str, Any],
    device: torch.device,
    tokenizer: object,
    validation_metadata_path: Path,
    expected_fingerprints: dict[str, str] | None,
) -> dict[str, object]:
    set_seed(int(cfg["run"]["seed"]))
    model = GPT(GPTConfig.from_dict(cfg["model"])).to(device)
    try:
        payload = load_checkpoint(spec.path, map_location=device)
        if expected_fingerprints is not None:
            validate_checkpoint_compatibility(payload, expected_fingerprints)
        apply_checkpoint_payload(payload, model=model)

        validation_rows = []
        for validation_seed in request.validation_seeds:
            dataset = PackedTokenDataset.from_metadata(
                validation_metadata_path,
                context_length=cfg["model"]["context_length"],
                seed=validation_seed,
            )
            loss = evaluate_loss(
                model,
                dataset,
                batch_size=cfg["training"]["micro_batch_size"],
                eval_batches=cfg["training"]["eval_batches"],
                device=device,
                precision=cfg["training"]["precision"],
            )
            if not math.isfinite(loss):
                raise ValueError(
                    f"checkpoint {spec.label!r}, validation seed {validation_seed} "
                    "produced a non-finite loss"
                )
            validation_rows.append(
                {"seed": validation_seed, "loss": loss, "perplexity": perplexity(loss)}
            )

        consistency = evaluate_multiple_choice_file(
            model=model,
            tokenizer=tokenizer,
            path=request.task_path,
            device=device,
            precision=cfg["training"]["precision"],
        )
        _ensure_finite_numbers(consistency, f"checkpoint {spec.label!r} task result")

        generations = []
        prompt_texts = [prompt.text for prompt in request.prompts]
        for generation_seed in request.generation_seeds:
            set_seed(generation_seed)
            samples = generate_samples(
                model=model,
                tokenizer=tokenizer,
                prompts=prompt_texts,
                max_new_tokens=cfg["evaluation"]["max_new_tokens"],
                eos_id=tokenizer.token_to_id("<|eos|>"),
                temperature=cfg["evaluation"]["temperature"],
                top_k=cfg["evaluation"]["top_k"],
                top_p=cfg["evaluation"]["top_p"],
                device=device,
            )
            if len(samples) != len(request.prompts):
                raise ValueError(
                    f"checkpoint {spec.label!r}, generation seed {generation_seed} "
                    "returned the wrong number of stories"
                )
            for prompt, sample in zip(request.prompts, samples):
                text = sample.get("text")
                if not isinstance(text, str):
                    raise ValueError("generated story text must be a string")
                generations.append(
                    {
                        "generation_id": (
                            f"{spec.label}-{prompt.id}-seed-{generation_seed}"
                        ),
                        "prompt_id": prompt.id,
                        "prompt_category": prompt.category,
                        "prompt": prompt.text,
                        "text": text,
                        "generation_seed": generation_seed,
                        "repetition": measure_repetition(text),
                    }
                )

        generation_summary = summarize_generations(generations)
        _ensure_finite_numbers(
            generation_summary, f"checkpoint {spec.label!r} generation summary"
        )
        return {
            "checkpoint_label": spec.label,
            "checkpoint_path": str(spec.path),
            "validation": validation_rows,
            "consistency_task": consistency,
            "generations": generations,
            "generation_summary": generation_summary,
        }
    finally:
        del model
        if getattr(device, "type", None) == "cuda":
            torch.cuda.empty_cache()


def run_comparison(request: EvaluationRequest) -> dict[str, object]:
    cfg = load_config(request.config_path)
    device = get_device()
    tokenizer = load_tokenizer(cfg["tokenizer"]["output_dir"])
    validation_metadata_path = metadata_path_for_split(
        cfg["sharding"]["output_dir"], effective_validation_split(cfg["dataset"])
    )
    expected_fingerprints = None
    if not cfg["training"].get("allow_artifact_mismatch", False):
        expected_fingerprints = _expected_fingerprints(cfg)

    request.output_dir.mkdir(parents=True, exist_ok=False)
    detailed: dict[str, dict[str, object]] = {}
    for spec in request.checkpoints:
        result = _evaluate_checkpoint(
            spec=spec,
            request=request,
            cfg=cfg,
            device=device,
            tokenizer=tokenizer,
            validation_metadata_path=validation_metadata_path,
            expected_fingerprints=expected_fingerprints,
        )
        detailed[spec.label] = result
        write_evaluation_result(
            request.output_dir / "checkpoints" / f"{spec.label}.json", result
        )

    validation = summarize_validation(
        {
            label: [
                {"seed": row["seed"], "loss": row["loss"]}
                for row in result["validation"]
            ]
            for label, result in detailed.items()
        }
    )
    generations_by_checkpoint = {
        label: result["generations"] for label, result in detailed.items()
    }
    judge_bundle = build_judge_bundle(
        generations_by_checkpoint,
        per_checkpoint=request.review_per_checkpoint,
        review_seed=request.review_seed,
        batch_size=request.judge_batch_size,
    )
    write_judge_bundle(
        request.output_dir, judge_bundle, prompt_text=request.judge_prompt_text
    )

    config_fingerprint = sha256_text(config_to_yaml(cfg))
    summary = {
        "protocol": {
            "validation_seeds": request.validation_seeds,
            "generation_seeds": request.generation_seeds,
            "review_seed": request.review_seed,
            "review_per_checkpoint": request.review_per_checkpoint,
            "judge_batch_size": request.judge_batch_size,
            "prompt_count": len(request.prompts),
            "task_category_counts": request.task_counts,
            "same_validation_dataset": str(validation_metadata_path),
            "generation": {
                "max_new_tokens": cfg["evaluation"]["max_new_tokens"],
                "temperature": cfg["evaluation"]["temperature"],
                "top_k": cfg["evaluation"]["top_k"],
                "top_p": cfg["evaluation"]["top_p"],
            },
        },
        "config": {
            "path": str(request.config_path),
            "sha256": config_fingerprint,
        },
        "checkpoints": {
            spec.label: {
                "path": str(spec.path),
                "evidence": f"checkpoints/{spec.label}.json",
            }
            for spec in request.checkpoints
        },
        "validation": validation,
        "consistency": {
            label: _task_summary(result["consistency_task"])
            for label, result in detailed.items()
        },
        "generations": {
            label: result["generation_summary"]
            for label, result in detailed.items()
        },
        "llm_judge": {
            "status": "awaiting_judgments",
            "batch_directory": "llm_judge/batches",
            "review_key": "llm_judge/review_key.json",
            "judge_prompt": "llm_judge/judge_prompt.md",
            "review_count": len(judge_bundle["review_key"]),
        },
    }
    _ensure_finite_numbers(summary, "comparison summary")
    write_evaluation_result(request.output_dir / "comparison_summary.json", summary)
    return summary


def main() -> None:
    request = validate_request(parse_args())
    summary = run_comparison(request)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
