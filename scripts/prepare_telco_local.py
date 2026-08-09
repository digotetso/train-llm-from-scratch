#!/usr/bin/env python
"""Run only the local Telco data and tokenizer preparation stages."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

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
from matgpt.utils.hashing import sha256_file, sha256_json


STAGES = (
    "tokenizer_sample",
    "tokenizer_candidate",
    "tokenizer_compare",
    "tokenizer_select",
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_CONFIGS = {
    "--sources": REPOSITORY_ROOT / "configs/data/telco_300m_sources.yaml",
    "--mixture": REPOSITORY_ROOT / "configs/data/telco_300m_mixture.yaml",
    "--candidate-config": (
        REPOSITORY_ROOT / "configs/data/telco_300m_tokenizer_candidate.yaml"
    ),
    "--model-config": REPOSITORY_ROOT / "configs/matgpt_telco_300m.yaml",
}
OPEN_TELCO_SOURCES = ("open_telco_lite", "open_telco_full")
OPEN_TELCO_CONFIGS = ("oranbench", "sixg_bench", "srsranbench", "teleqna")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


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


def _approved_config(value: str, option: str) -> Path:
    supplied = _required_path(value, option)
    canonical = CANONICAL_CONFIGS[option]
    if sha256_file(supplied) != sha256_file(canonical):
        raise ValueError(
            f"{option} does not match the approved repository config: {canonical}"
        )
    return supplied


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


def _manifest_sha256(payload: Mapping[str, Any], label: str) -> str:
    digest = payload.get("manifest_sha256")
    if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
        raise ValueError(f"{label} manifest_sha256 must be a lowercase SHA-256.")
    return digest


def _verify_open_telco_manifest(
    manifest_path: Path,
    *,
    source_id: str,
    evidence_by_config: Mapping[str, Path],
    registry: Any,
) -> None:
    manifest = _load_json_object(manifest_path, f"{source_id} manifest")
    if manifest.get("version") != 1 or manifest.get("complete") is not True:
        raise ValueError(f"{source_id} manifest must be complete version 1 evidence.")
    expected_digest = _manifest_sha256(manifest, source_id)
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256", None)
    if sha256_json(unsigned) != expected_digest:
        raise ValueError(f"{source_id} manifest checksum mismatch.")

    source = registry.by_id[source_id]
    expected_identity = {
        "dataset_id": source.hf_name,
        "source_id": source.id,
        "revision": source.revision,
        "role": source.role,
        "license": source.license,
    }
    for field, expected in expected_identity.items():
        if manifest.get(field) != expected:
            raise ValueError(f"{source_id} manifest {field} mismatch.")

    configs = manifest.get("configs")
    if not isinstance(configs, Mapping) or set(configs) != set(OPEN_TELCO_CONFIGS):
        raise ValueError(f"{source_id} manifest must contain all four configs.")
    for config in OPEN_TELCO_CONFIGS:
        entry = configs.get(config)
        if not isinstance(entry, Mapping):
            raise ValueError(f"{source_id} manifest config {config} is invalid.")
        path = evidence_by_config[config]
        examples = entry.get("examples")
        if (
            entry.get("path") != path.name
            or not isinstance(examples, int)
            or isinstance(examples, bool)
            or examples < 1
            or entry.get("raw_bytes") != path.stat().st_size
            or entry.get("sha256") != sha256_file(path)
        ):
            raise ValueError(f"{source_id} manifest config {config} mismatch.")


def _verified_contamination_paths(
    supplied_paths: Sequence[str], registry: Any
) -> list[Path]:
    if len(supplied_paths) != len(OPEN_TELCO_SOURCES) * len(OPEN_TELCO_CONFIGS):
        raise ValueError(
            "tokenizer_sample requires all eight Open Telco Lite/Full "
            "--contamination-patterns files."
        )
    paths = [
        _required_path(path, "--contamination-patterns") for path in supplied_paths
    ]
    if len(set(paths)) != len(paths):
        raise ValueError("Contamination evidence paths must be unique.")

    grouped: dict[str, dict[str, Path]] = {
        source_id: {} for source_id in OPEN_TELCO_SOURCES
    }
    roots: dict[str, Path] = {}
    for path in paths:
        if path.suffix != ".jsonl" or path.stem not in OPEN_TELCO_CONFIGS:
            raise ValueError(f"Unexpected Open Telco contamination file: {path}")
        manifest_path = path.parent / "manifest.json"
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise ValueError(
                f"Contamination evidence requires a real manifest: {manifest_path}"
            )
        manifest = _load_json_object(manifest_path, "Open Telco manifest")
        source_id = manifest.get("source_id")
        if source_id not in grouped:
            raise ValueError(f"Cannot identify Lite/Full contamination evidence: {path}")
        previous_root = roots.setdefault(source_id, path.parent)
        if previous_root != path.parent:
            raise ValueError(f"{source_id} contamination files must share one directory.")
        if path.stem in grouped[source_id]:
            raise ValueError(f"Duplicate {source_id} config evidence: {path.stem}")
        if path.stat().st_size < 1 or not load_contamination_patterns([path]):
            raise ValueError(f"Contamination evidence must be non-empty: {path}")
        grouped[source_id][path.stem] = path

    for source_id in OPEN_TELCO_SOURCES:
        evidence = grouped[source_id]
        if set(evidence) != set(OPEN_TELCO_CONFIGS):
            raise ValueError(f"{source_id} requires all four config JSONL files.")
        manifest_path = roots[source_id] / "manifest.json"
        _verify_open_telco_manifest(
            manifest_path,
            source_id=source_id,
            evidence_by_config=evidence,
            registry=registry,
        )
    return [
        grouped[source_id][config]
        for source_id in OPEN_TELCO_SOURCES
        for config in OPEN_TELCO_CONFIGS
    ]


def _canonical_sample_manifest(
    supplied: str | None, work_dir: Path, option: str
) -> tuple[Path, str]:
    manifest = _required_path(supplied, option)
    canonical = work_dir / "tokenizer_sample" / "manifest.json"
    if manifest != canonical.resolve():
        raise ValueError(f"{option} must be the canonical work-root sample manifest.")
    payload = _load_json_object(manifest, "Tokenizer sample manifest")
    return manifest, _manifest_sha256(payload, "Tokenizer sample")


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
    contamination_paths = _verified_contamination_paths(
        args.contamination_patterns, registry
    )
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
    work_dir: Path,
    drive_dir: Path,
    candidate_config: TokenizerCandidateConfig,
    model_config: dict[str, Any],
) -> dict[str, Any]:
    destination = drive_dir / "tokenizers" / candidate_config.candidate_label
    sample_manifest, sample_manifest_sha256 = _canonical_sample_manifest(
        args.sample_manifest, work_dir, "--sample-manifest"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(exist_ok=False)
    tokenizer_config = model_config["tokenizer"]
    report = dict(
        train_tokenizer_from_manifest(
            sample_manifest,
            destination,
            int(tokenizer_config["vocab_size"]),
            int(tokenizer_config["min_frequency"]),
            list(tokenizer_config["special_tokens"]),
            tokenizer_config.get("probe_sets_path"),
        )
    )
    persisted = _load_json_object(
        destination / "tokenizer_report.json", "Candidate tokenizer report"
    )
    for candidate_report in (report, persisted):
        if candidate_report.get("fitting_manifest_sha256") != sample_manifest_sha256:
            raise ValueError("Candidate tokenizer fitting manifest fingerprint mismatch.")
    if persisted != report:
        raise ValueError("Persisted candidate tokenizer report mismatch.")
    return report


def _comparison_stage(
    args: argparse.Namespace,
    *,
    work_dir: Path,
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
    canonical_candidate = drive_dir / "tokenizers" / candidate_config.candidate_label
    candidate = _required_path(
        args.candidate_tokenizer, "--candidate-tokenizer", directory=True
    )
    if candidate != canonical_candidate.resolve():
        raise ValueError(
            "--candidate-tokenizer must be the canonical candidate destination."
        )
    if baseline == candidate:
        raise ValueError("Baseline and candidate tokenizer directories must differ.")
    holdout, sample_manifest_sha256 = _canonical_sample_manifest(
        args.holdout_manifest, work_dir, "--holdout-manifest"
    )
    candidate_report = _load_json_object(
        candidate / "tokenizer_report.json", "Candidate tokenizer report"
    )
    if candidate_report.get("fitting_manifest_sha256") != sample_manifest_sha256:
        raise ValueError("Candidate tokenizer fitting manifest fingerprint mismatch.")
    candidate_report_sha256 = candidate_report.get("tokenizer_sha256")
    if (
        not isinstance(candidate_report_sha256, str)
        or SHA256_PATTERN.fullmatch(candidate_report_sha256) is None
        or candidate_report_sha256 != sha256_file(candidate / "tokenizer.json")
    ):
        raise ValueError("Candidate tokenizer report fingerprint mismatch.")
    probes = _required_path(
        model_config["tokenizer"].get("probe_sets_path"),
        "model tokenizer.probe_sets_path",
    )
    baseline_evaluation = evaluate_tokenizer_on_jsonl(baseline, [holdout], probes)
    candidate_evaluation = evaluate_tokenizer_on_jsonl(candidate, [holdout], probes)
    if baseline_evaluation.get("tokenizer_sha256") == candidate_evaluation.get(
        "tokenizer_sha256"
    ):
        raise ValueError("Baseline and candidate tokenizer fingerprints must differ.")
    for side, evaluation in (
        ("baseline", baseline_evaluation),
        ("candidate", candidate_evaluation),
    ):
        if evaluation.get("sample_manifest_sha256") != sample_manifest_sha256:
            raise ValueError(f"{side} evaluation sample manifest fingerprint mismatch.")
    if candidate_evaluation.get("tokenizer_sha256") != candidate_report_sha256:
        raise ValueError("Candidate evaluation tokenizer fingerprint mismatch.")
    comparison = compare_tokenizers(
        baseline_evaluation, candidate_evaluation, candidate_config
    )
    if comparison.get("labels") != {
        "baseline": candidate_config.baseline_label,
        "candidate": candidate_config.candidate_label,
    }:
        raise ValueError("Tokenizer comparison side labels mismatch.")
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
    sources_path = _approved_config(args.sources, "--sources")
    mixture_path = _approved_config(args.mixture, "--mixture")
    candidate_path = _approved_config(args.candidate_config, "--candidate-config")
    model_path = _approved_config(args.model_config, "--model-config")
    registry = load_source_registry(sources_path)
    mixture = load_mixture_config(mixture_path)
    candidate_config = load_tokenizer_candidate_config(candidate_path)
    model_config = load_config(model_path)

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
            work_dir=work_dir,
            drive_dir=drive_dir,
            candidate_config=candidate_config,
            model_config=model_config,
        )
    if args.stage == "tokenizer_compare":
        return _comparison_stage(
            args,
            work_dir=work_dir,
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
