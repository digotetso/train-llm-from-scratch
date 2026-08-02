#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.data.mixture import build_mixture_plan, load_mixture_config
from matgpt.data.sources import load_source_registry


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an exact, role-safe Telco corpus token plan."
    )
    parser.add_argument("--sources", required=True, help="Source registry YAML.")
    parser.add_argument("--mixture", required=True, help="Mixture config YAML.")
    parser.add_argument("--stage", required=True, help="Configured mixture stage.")
    parser.add_argument(
        "--total-tokens",
        type=int,
        default=None,
        help="Optional bounded token override, intended for pilot preparation.",
    )
    parser.add_argument("--output", default=None, help="Optional plan JSON path.")
    args = parser.parse_args()

    registry = load_source_registry(args.sources)
    mixture = load_mixture_config(args.mixture)
    plan = build_mixture_plan(
        registry,
        mixture,
        args.stage,
        total_tokens=args.total_tokens,
    )
    rendered = json.dumps(plan, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
