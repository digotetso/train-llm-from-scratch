#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.config import load_config
from matgpt.model.report import build_model_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Report model parameter count and size-label drift.")
    parser.add_argument("--config", required=True, help="Path to MatGPT YAML config.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    print(json.dumps(build_model_report(cfg), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
