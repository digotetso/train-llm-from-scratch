#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.data.telco_prepare import audit_token_quotas


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Count actual tokenizer IDs and verify Telco mixture quotas."
    )
    parser.add_argument("--input", action="append", required=True, help="Stage JSONL path.")
    parser.add_argument("--plan", action="append", required=True, help="Stage plan JSON path.")
    parser.add_argument("--tokenizer-dir", required=True)
    parser.add_argument("--tolerance", type=float, default=0.03)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    plans = [
        json.loads(Path(path).read_text(encoding="utf-8")) for path in args.plan
    ]
    report = audit_token_quotas(
        input_paths=args.input,
        tokenizer_dir=args.tokenizer_dir,
        plans=plans,
        tolerance=args.tolerance,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
