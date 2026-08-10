#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
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
    parser.add_argument("--corpus-manifest", required=True)
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
        corpus_manifest_path=args.corpus_manifest,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output.parent, prefix=f".{output.name}.", suffix=".partial"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
        directory = os.open(output.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)
    print(rendered)


if __name__ == "__main__":
    main()
