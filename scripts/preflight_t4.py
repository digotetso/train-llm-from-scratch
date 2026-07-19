#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.config import load_config
from matgpt.preflight import run_preflight


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate MatGPT artifacts and T4 readiness.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--require-t4", action="store_true")
    parser.add_argument("--min-free-disk-gb", type=float, default=0.0)
    args = parser.parse_args()

    cfg = load_config(args.config)
    output = (
        Path(args.output)
        if args.output
        else Path(cfg["run"]["output_dir"]) / "preflight.json"
    )
    report = run_preflight(
        cfg,
        output,
        require_t4=args.require_t4,
        min_free_disk_gb=args.min_free_disk_gb,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
