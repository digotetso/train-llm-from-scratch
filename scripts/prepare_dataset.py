#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.config import load_config
from matgpt.data.prepare import prepare_hf_dataset
from matgpt.utils.seed import set_seed


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare normalized JSONL corpus files.")
    parser.add_argument("--config", required=True, help="Path to MatGPT YAML config.")
    args = parser.parse_args()

    cfg = load_config(args.config) # Read settings.
    set_seed(cfg["run"]["seed"])  # Make preparation repeatable.
    manifest = prepare_hf_dataset(cfg)  # Prepare the corpus.
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
