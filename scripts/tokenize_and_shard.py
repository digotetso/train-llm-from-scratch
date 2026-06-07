#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.config import load_config
from matgpt.data.shard import tokenize_splits_from_config
from matgpt.utils.seed import set_seed


def main() -> None:
    parser = argparse.ArgumentParser(description="Tokenize normalized JSONL files into packed binary shards.")
    parser.add_argument("--config", required=True, help="Path to MatGPT YAML config.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    set_seed(cfg["run"]["seed"])
    metadata = tokenize_splits_from_config(cfg)
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
