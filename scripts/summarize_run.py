#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.training.run_summary import write_run_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize a MatGPT training run.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--known-limitation", action="append", default=[])
    args = parser.parse_args()
    limitations = args.known_limitation or [
        "Single T4 run; exact CUDA determinism is not claimed."
    ]
    output = write_run_summary(args.run_dir, limitations)
    print(output)


if __name__ == "__main__":
    main()
