#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.data.mixture import build_mixture_plan, load_mixture_config
from matgpt.data.quality import DataQualityPolicy, load_contamination_patterns
from matgpt.data.sources import load_source_registry
from matgpt.data.telco_prepare import prepare_telco_corpora


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Stream and prepare role-safe Telco corpus stages. This command "
            "prepares data only; it never starts pretraining."
        )
    )
    parser.add_argument("--sources", required=True, help="Source registry YAML.")
    parser.add_argument("--mixture", required=True, help="Mixture config YAML.")
    parser.add_argument(
        "--stage",
        action="append",
        required=True,
        choices=("pilot", "main", "cooldown"),
        help="Stage to prepare; repeat main and cooldown for a full corpus.",
    )
    parser.add_argument("--output-dir", required=True, help="Prepared corpus directory.")
    parser.add_argument(
        "--total-tokens",
        type=int,
        default=None,
        help="Optional single-stage pilot token override.",
    )
    parser.add_argument(
        "--contamination-patterns",
        action="append",
        default=[],
        help="Text or JSONL benchmark file; repeat to add files.",
    )
    parser.add_argument("--min-chars", type=int, default=40)
    parser.add_argument("--buffer-size", type=int, default=None)
    parser.add_argument(
        "--tokenizer-dir",
        default=None,
        help=(
            "Frozen tokenizer directory used to collect exact token quotas. "
            "Omit only for the tokenizer-bootstrap corpus."
        ),
    )
    parser.add_argument(
        "--allow-full-data",
        action="store_true",
        help="Required for main+cooldown data download; does not authorize training.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Back up and replace an existing completed output directory.",
    )
    args = parser.parse_args()

    stages = args.stage
    if len(stages) != len(set(stages)):
        parser.error("--stage values must be unique.")
    full_stages = {"main", "cooldown"}
    if full_stages.intersection(stages):
        if set(stages) != full_stages:
            parser.error("Full preparation requires --stage main --stage cooldown together.")
        if not args.allow_full_data:
            parser.error("Full preparation requires --allow-full-data.")
    if args.total_tokens is not None and stages != ["pilot"]:
        parser.error("--total-tokens is supported only for a single pilot stage.")

    registry = load_source_registry(args.sources)
    mixture = load_mixture_config(args.mixture)
    plans = [
        build_mixture_plan(
            registry,
            mixture,
            stage,
            total_tokens=args.total_tokens,
        )
        for stage in stages
    ]
    patterns = load_contamination_patterns(args.contamination_patterns)
    policy = DataQualityPolicy(
        enabled=True,
        min_chars=args.min_chars,
        exact_dedup=True,
        contamination_patterns=patterns,
    )
    manifest = prepare_telco_corpora(
        registry=registry,
        plans=plans,
        output_dir=args.output_dir,
        quality_policy=policy,
        buffer_size=args.buffer_size or int(mixture["buffer_size"]),
        force=args.force,
        tokenizer_dir=args.tokenizer_dir,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
