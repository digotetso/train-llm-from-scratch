#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.data.sources import load_source_registry
from matgpt.eval.open_telco import (
    SUPPORTED_MULTIPLE_CHOICE_CONFIGS,
    prepare_open_telco_evals,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize pinned Open Telco multiple-choice evaluation JSONL."
    )
    parser.add_argument("--sources", required=True, help="Source registry YAML.")
    parser.add_argument(
        "--dataset",
        choices=("lite", "full"),
        default="lite",
        help="Use ot-lite for iteration or ot-full for final reporting.",
    )
    parser.add_argument(
        "--config",
        action="append",
        choices=tuple(sorted(SUPPORTED_MULTIPLE_CHOICE_CONFIGS)),
        default=None,
        help="Config to materialize; repeat or omit for all supported configs.",
    )
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    source_id = "open_telco_lite" if args.dataset == "lite" else "open_telco_full"
    configs = tuple(args.config or sorted(SUPPORTED_MULTIPLE_CHOICE_CONFIGS))
    manifest = prepare_open_telco_evals(
        registry=load_source_registry(args.sources),
        source_id=source_id,
        configs=configs,
        output_dir=args.output_dir,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
