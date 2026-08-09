#!/usr/bin/env python
"""Run only the local Telco data and tokenizer preparation stages."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.config import load_config
from matgpt.data.local_sample import LocalSampleRequest, build_tokenizer_sample
from matgpt.data.mixture import load_mixture_config
from matgpt.data.quality import DataQualityPolicy, load_contamination_patterns
from matgpt.data.sources import load_source_registry
from matgpt.tokenizer.candidate import (
    TokenizerCandidateConfig,
    build_tokenizer_sample_plan,
    compare_tokenizers,
    load_tokenizer_candidate_config,
    write_tokenizer_selection,
)
from matgpt.tokenizer.train import (
    evaluate_tokenizer_on_jsonl,
    train_tokenizer_from_manifest,
)


STAGES = (
    "tokenizer_sample",
    "tokenizer_candidate",
    "tokenizer_compare",
    "tokenizer_select",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare and compare Telco tokenizers locally. This command has no "
            "model-pretraining stage."
        )
    )
    parser.add_argument("--stage", required=True, choices=STAGES)
    parser.add_argument("--sources", required=True, help="Pinned source registry YAML.")
    parser.add_argument("--mixture", required=True, help="Telco mixture YAML.")
    parser.add_argument(
        "--candidate-config", required=True, help="Tokenizer candidate recipe YAML."
    )
    parser.add_argument("--model-config", required=True, help="MatGPT model YAML.")
    parser.add_argument(
        "--work-dir", required=True, help="Local non-Drive working directory."
    )
    parser.add_argument(
        "--drive-dir", required=True, help="Existing streamed Drive publish directory."
    )

    parser.add_argument(
        "--contamination-patterns",
        action="append",
        default=[],
        metavar="JSONL",
        help="Evaluation text to exclude; repeat for every contamination file.",
    )
    parser.add_argument("--sample-manifest", help="Complete v2 sample manifest.")
    parser.add_argument("--baseline-tokenizer", help="Baseline tokenizer directory.")
    parser.add_argument("--candidate-tokenizer", help="Candidate tokenizer directory.")
    parser.add_argument("--holdout-manifest", help="Shared complete v2 sample manifest.")
    parser.add_argument("--comparison", help="Reviewed tokenizer comparison JSON.")
    parser.add_argument("--winner", help="Explicit tokenizer label to select.")
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Confirm that the comparison was reviewed and selection is intentional.",
    )
    return parser


def _resolved_roots(work_dir: str, drive_dir: str) -> tuple[Path, Path]:
    work = Path(work_dir).expanduser()
    drive = Path(drive_dir).expanduser()
    if work.is_symlink():
        raise ValueError("Local work root must not be a symbolic link.")
    if work.exists() and not work.is_dir():
        raise ValueError("Local work root must be a directory.")
    if drive.is_symlink() or not drive.is_dir():
        raise ValueError("Drive publish root must be an existing real directory.")

    resolved_work = work.resolve()
    resolved_drive = drive.resolve()
    if (
        resolved_work == resolved_drive
        or resolved_work.is_relative_to(resolved_drive)
        or resolved_drive.is_relative_to(resolved_work)
    ):
        raise ValueError(
            "Local work root and Drive publish root must be distinct, non-overlapping "
            "directories."
        )
    return resolved_work, resolved_drive


def _required_path(value: str | None, option: str, *, directory: bool = False) -> Path:
    if not value:
        raise ValueError(f"Stage requires {option}.")
    path = Path(value).expanduser()
    valid = path.is_dir() if directory else path.is_file()
    if path.is_symlink() or not valid:
        kind = "directory" if directory else "file"
        raise ValueError(f"{option} must name an existing real {kind}: {path}")
    return path.resolve()


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"{label} contains invalid JSON constant {value}.")

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"), parse_constant=reject_constant
        )
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} is invalid JSON: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object.")
    return payload


def _write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _quality_policy(
    model_config: dict[str, Any], contamination_paths: Sequence[str]
) -> DataQualityPolicy:
    policy = DataQualityPolicy.from_dataset_config(model_config["dataset"])
    additional = load_contamination_patterns(contamination_paths)
    return replace(
        policy,
        contamination_patterns=[*policy.contamination_patterns, *additional],
    )


def _sample_stage(
    args: argparse.Namespace,
    *,
    work_dir: Path,
    registry: Any,
    mixture: dict[str, Any],
    candidate_config: TokenizerCandidateConfig,
    model_config: dict[str, Any],
) -> dict[str, Any]:
    if not args.contamination_patterns:
        raise ValueError(
            "tokenizer_sample requires at least one --contamination-patterns file."
        )
    contamination_paths = [
        _required_path(path, "--contamination-patterns")
        for path in args.contamination_patterns
    ]
    work_dir.mkdir(parents=True, exist_ok=True)
    sample_dir = work_dir / "tokenizer_sample"
    state_dir = work_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    plan = build_tokenizer_sample_plan(registry, mixture, candidate_config)
    request = LocalSampleRequest(
        registry=registry,
        plan=plan,
        output_dir=sample_dir,
        state_path=state_dir / "tokenizer_sample.sqlite3",
        quality_policy=_quality_policy(
            model_config, [str(path) for path in contamination_paths]
        ),
    )

    def report_progress(event: Any) -> None:
        print(
            json.dumps({"event": "progress", **asdict(event)}, sort_keys=True),
            flush=True,
        )

    return dict(build_tokenizer_sample(request, progress_sink=report_progress))


def _candidate_stage(
    args: argparse.Namespace,
    *,
    drive_dir: Path,
    candidate_config: TokenizerCandidateConfig,
    model_config: dict[str, Any],
) -> dict[str, Any]:
    destination = drive_dir / "tokenizers" / candidate_config.candidate_label
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Candidate destination already exists: {destination}")
    sample_manifest = _required_path(args.sample_manifest, "--sample-manifest")
    tokenizer_config = model_config["tokenizer"]
    return dict(
        train_tokenizer_from_manifest(
            sample_manifest,
            destination,
            int(tokenizer_config["vocab_size"]),
            int(tokenizer_config["min_frequency"]),
            list(tokenizer_config["special_tokens"]),
            tokenizer_config.get("probe_sets_path"),
        )
    )


def _comparison_stage(
    args: argparse.Namespace,
    *,
    drive_dir: Path,
    candidate_config: TokenizerCandidateConfig,
    model_config: dict[str, Any],
) -> dict[str, Any]:
    destination = drive_dir / "comparison.json"
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Comparison already exists: {destination}")
    baseline = _required_path(
        args.baseline_tokenizer, "--baseline-tokenizer", directory=True
    )
    candidate = _required_path(
        args.candidate_tokenizer, "--candidate-tokenizer", directory=True
    )
    holdout = _required_path(args.holdout_manifest, "--holdout-manifest")
    probes = _required_path(
        model_config["tokenizer"].get("probe_sets_path"),
        "model tokenizer.probe_sets_path",
    )
    baseline_evaluation = evaluate_tokenizer_on_jsonl(baseline, [holdout], probes)
    candidate_evaluation = evaluate_tokenizer_on_jsonl(candidate, [holdout], probes)
    comparison = compare_tokenizers(
        baseline_evaluation, candidate_evaluation, candidate_config
    )
    _write_json_exclusive(destination, comparison)
    return comparison


def _selection_stage(
    args: argparse.Namespace,
    *,
    drive_dir: Path,
) -> dict[str, Any]:
    if not args.approve:
        raise ValueError(
            "tokenizer_select requires --approve after the comparison is reviewed."
        )
    if not args.winner:
        raise ValueError("tokenizer_select requires --winner.")
    comparison_path = _required_path(args.comparison, "--comparison")
    comparison = _load_json_object(comparison_path, "Tokenizer comparison")
    return write_tokenizer_selection(
        comparison,
        args.winner,
        drive_dir / "tokenizer_selection.json",
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    work_dir, drive_dir = _resolved_roots(args.work_dir, args.drive_dir)
    registry = load_source_registry(args.sources)
    mixture = load_mixture_config(args.mixture)
    candidate_config = load_tokenizer_candidate_config(args.candidate_config)
    model_config = load_config(args.model_config)

    if args.stage == "tokenizer_sample":
        return _sample_stage(
            args,
            work_dir=work_dir,
            registry=registry,
            mixture=mixture,
            candidate_config=candidate_config,
            model_config=model_config,
        )
    if args.stage == "tokenizer_candidate":
        return _candidate_stage(
            args,
            drive_dir=drive_dir,
            candidate_config=candidate_config,
            model_config=model_config,
        )
    if args.stage == "tokenizer_compare":
        return _comparison_stage(
            args,
            drive_dir=drive_dir,
            candidate_config=candidate_config,
            model_config=model_config,
        )
    if args.stage == "tokenizer_select":
        return _selection_stage(args, drive_dir=drive_dir)
    raise ValueError(f"Unsupported stage: {args.stage}")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run(args)
    except (FileExistsError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr, flush=True)
        return 2
    print(
        json.dumps(
            {"event": "complete", "stage": args.stage, "result": result},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
