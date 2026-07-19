#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.config import load_config
from matgpt.preflight import (
    build_config_failure_report,
    run_preflight,
    write_preflight_report,
)


def _default_report_path(cfg: dict) -> Path:
    run_cfg = cfg.get("run")
    if not isinstance(run_cfg, dict):
        raise ValueError("run must be a mapping with a usable run.output_dir")
    output_dir = run_cfg.get("output_dir")
    if not isinstance(output_dir, str) or not output_dir.strip():
        raise ValueError("run.output_dir must be a non-empty path string")
    if "\x00" in output_dir:
        raise ValueError("run.output_dir must not contain null bytes")
    output_path = Path(output_dir)
    if output_path.exists() and not output_path.is_dir():
        raise ValueError(f"run.output_dir is not a directory: {output_path}")
    return output_path / "preflight.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate MatGPT artifacts and T4 readiness.")
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--report-path",
        "--output",
        dest="report_path",
        default=None,
        help=(
            "JSON report destination. If omitted, valid configs use "
            "<run.output_dir>/preflight.json and invalid configs use ./preflight.json."
        ),
    )
    parser.add_argument("--require-t4", action="store_true")
    parser.add_argument("--min-free-disk-gb", type=float, default=0.0)
    args = parser.parse_args(argv)

    requested_report_path = Path(args.report_path) if args.report_path else None
    config_failure_path = requested_report_path or Path.cwd() / "preflight.json"
    try:
        cfg = load_config(args.config)
        default_report_path = _default_report_path(cfg)
    except Exception as exc:
        report = build_config_failure_report(exc)
        write_preflight_report(report, config_failure_path)
        print(f"Preflight failed: config: {exc}", file=sys.stderr)
        return 1

    report_path = requested_report_path or default_report_path
    try:
        report = run_preflight(
            cfg,
            report_path,
            require_t4=args.require_t4,
            min_free_disk_gb=args.min_free_disk_gb,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        if requested_report_path is not None:
            raise
        report = build_config_failure_report(
            ValueError(f"run.output_dir could not persist preflight evidence: {exc}")
        )
        write_preflight_report(report, config_failure_path)
        print(f"Preflight failed: config: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
