#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.config import load_config
from matgpt.training.pretrain import run_pretraining


def main() -> None:
    parser = argparse.ArgumentParser(description="Pretrain MatGPT from random weights or resume checkpoint.")
    parser.add_argument("--config", required=True, help="Path to MatGPT YAML config.")
    parser.add_argument("--resume-from", default=None, help="Full checkpoint path to resume from.")
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Maximum additional successful optimizer updates in this invocation; the full LR schedule is unchanged.",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    result = run_pretraining(cfg, resume_from=args.resume_from, max_steps_override=args.max_steps)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
