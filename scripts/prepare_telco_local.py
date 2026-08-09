#!/usr/bin/env python
"""Run only the local Telco data and tokenizer preparation stages."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.config import load_config
from matgpt.data.contamination import pattern_fingerprint
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
from matgpt.utils.paths import open_exclusive_nofollow, require_managed_path


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
    parser.add_argument("--sample-manifest", help="Complete v3 sample manifest.")
    parser.add_argument("--baseline-tokenizer", help="Baseline tokenizer directory.")
    parser.add_argument(
        "--baseline-provenance",
        help="Canonical preserved-pilot tokenizer provenance JSON.",
    )
    parser.add_argument("--candidate-tokenizer", help="Candidate tokenizer directory.")
    parser.add_argument("--holdout-manifest", help="Shared complete v3 sample manifest.")
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


def _required_managed_path(
    root: Path,
    value: str | Path | None,
    option: str,
    *,
    directory: bool = False,
) -> Path:
    if value is None or not str(value):
        raise ValueError(f"Stage requires {option}.")
    path = Path(value).expanduser()
    require_managed_path(
        root,
        path,
        kind="directory" if directory else "file",
        allow_missing=False,
    )
    valid = path.is_dir() if directory else path.is_file()
    if not valid:
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


def _write_json_exclusive(
    path: Path, payload: dict[str, Any], *, managed_root: Path
) -> None:
    require_managed_path(managed_root, path.parent, kind="directory")
    require_managed_path(managed_root, path, kind="file")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open_exclusive_nofollow(path, "w", encoding="utf-8") as handle:
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
    supplied: str | None,
    work_dir: Path,
    option: str,
    *,
    expected_provenance: Mapping[str, Any],
) -> tuple[Path, str, dict[str, Any]]:
    manifest = _required_managed_path(work_dir, supplied, option)
    canonical = work_dir / "tokenizer_sample" / "manifest.json"
    if manifest != canonical.resolve():
        raise ValueError(f"{option} must be the canonical work-root sample manifest.")
    payload = _load_json_object(manifest, "Tokenizer sample manifest")
    if payload.get("version") != 3 or payload.get("complete") is not True:
        raise ValueError("Tokenizer sample manifest must be complete version 3 evidence.")
    expected_manifest_sha256 = _manifest_sha256(payload, "Tokenizer sample")
    unsigned = dict(payload)
    unsigned.pop("manifest_sha256", None)
    if sha256_json(unsigned) != expected_manifest_sha256:
        raise ValueError("Tokenizer sample manifest checksum mismatch.")
    provenance = payload.get("build_provenance")
    provenance_sha256 = payload.get("build_provenance_sha256")
    if (
        not isinstance(provenance, Mapping)
        or provenance.get("workflow") != "telco_200m_tokenizer_candidate"
        or not isinstance(provenance_sha256, str)
        or SHA256_PATTERN.fullmatch(provenance_sha256) is None
        or sha256_json(provenance) != provenance_sha256
    ):
        raise ValueError("Tokenizer sample manifest build provenance is missing or foreign.")
    if dict(provenance) != dict(expected_provenance):
        raise ValueError(
            "Tokenizer sample manifest build provenance does not match current "
            "canonical configs and contamination evidence."
        )
    return manifest, _manifest_sha256(payload, "Tokenizer sample"), payload


def _quality_policy(
    model_config: dict[str, Any], contamination_paths: Sequence[str]
) -> DataQualityPolicy:
    policy = DataQualityPolicy.from_dataset_config(model_config["dataset"])
    additional = load_contamination_patterns(contamination_paths)
    return replace(
        policy,
        contamination_patterns=[*policy.contamination_patterns, *additional],
    )


def _provenance_component(payload: Mapping[str, Any]) -> dict[str, Any]:
    component = dict(payload)
    component["sha256"] = sha256_json(payload)
    return component


def _contamination_evidence_provenance(paths: Sequence[Path]) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    for source_id in OPEN_TELCO_SOURCES:
        source_paths = [
            path
            for path in paths
            if _load_json_object(path.parent / "manifest.json", "Open Telco manifest").get(
                "source_id"
            )
            == source_id
        ]
        if len(source_paths) != len(OPEN_TELCO_CONFIGS):
            raise ValueError(f"{source_id} contamination provenance is incomplete.")
        manifest_path = source_paths[0].parent / "manifest.json"
        manifest = _load_json_object(manifest_path, f"{source_id} manifest")
        sources.append(
            {
                "source_id": source_id,
                "manifest_sha256": _manifest_sha256(manifest, source_id),
                "manifest_file_sha256": sha256_file(manifest_path),
                "configs": {
                    name: {
                        "sha256": str(manifest["configs"][name]["sha256"]),
                        "raw_bytes": int(manifest["configs"][name]["raw_bytes"]),
                        "examples": int(manifest["configs"][name]["examples"]),
                    }
                    for name in OPEN_TELCO_CONFIGS
                },
            }
        )
    return _provenance_component({"version": 1, "sources": sources})


def _sample_build_provenance(
    *,
    registry: Any,
    plan: Mapping[str, Any],
    candidate_config: TokenizerCandidateConfig,
    model_config: Mapping[str, Any],
    quality_policy: DataQualityPolicy,
    contamination_paths: Sequence[Path],
    chunk_bytes: int,
) -> dict[str, Any]:
    plan_payload = dict(plan)
    recipe_payload = {
        "candidate_config": asdict(candidate_config),
        "candidate_config_file_sha256": sha256_file(
            CANONICAL_CONFIGS["--candidate-config"]
        ),
        "mixture_config_file_sha256": sha256_file(CANONICAL_CONFIGS["--mixture"]),
        "model_config_file_sha256": sha256_file(CANONICAL_CONFIGS["--model-config"]),
        "tokenizer": dict(model_config["tokenizer"]),
    }
    source_payload = {
        "registry_file_sha256": sha256_file(CANONICAL_CONFIGS["--sources"]),
        "registry_sha256": sha256_json(asdict(registry)),
    }
    quality_payload = {
        "enabled": quality_policy.enabled,
        "min_chars": quality_policy.min_chars,
        "max_chars": quality_policy.max_chars,
        "exact_dedup": quality_policy.exact_dedup,
        "contamination_patterns": len(quality_policy.contamination_patterns),
        "contamination_patterns_sha256": pattern_fingerprint(
            quality_policy.contamination_patterns
        ),
        "policy_sha256": sha256_json(asdict(quality_policy)),
    }
    return {
        "version": 1,
        "workflow": "telco_200m_tokenizer_candidate",
        "target_estimated_tokens": int(plan["total_tokens"]),
        "role_quotas": dict(plan["role_quotas"]),
        "plan": _provenance_component(plan_payload),
        "recipe": _provenance_component(recipe_payload),
        "sources": _provenance_component(source_payload),
        "quality_policy": _provenance_component(quality_payload),
        "contamination_evidence": _contamination_evidence_provenance(
            contamination_paths
        ),
        "format": {
            "version": 3,
            "encoding": "utf-8",
            "json": {"ensure_ascii": False, "sort_keys": True},
            "chunk_bytes": chunk_bytes,
        },
    }


def _canonical_contamination_paths(work_dir: Path, registry: Any) -> list[Path]:
    supplied = [
        str(work_dir / "evaluation" / source_id / f"{config}.jsonl")
        for source_id in OPEN_TELCO_SOURCES
        for config in OPEN_TELCO_CONFIGS
    ]
    for source_id in OPEN_TELCO_SOURCES:
        require_managed_path(
            work_dir,
            work_dir / "evaluation" / source_id,
            kind="directory",
            allow_missing=False,
        )
    return _verified_contamination_paths(supplied, registry)


def _current_sample_provenance(
    *,
    work_dir: Path,
    registry: Any,
    mixture: Mapping[str, Any],
    candidate_config: TokenizerCandidateConfig,
    model_config: Mapping[str, Any],
) -> dict[str, Any]:
    contamination_paths = _canonical_contamination_paths(work_dir, registry)
    plan = build_tokenizer_sample_plan(registry, mixture, candidate_config)
    quality_policy = _quality_policy(
        dict(model_config), [str(path) for path in contamination_paths]
    )
    return _sample_build_provenance(
        registry=registry,
        plan=plan,
        candidate_config=candidate_config,
        model_config=model_config,
        quality_policy=quality_policy,
        contamination_paths=contamination_paths,
        chunk_bytes=268_435_456,
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
    canonical_contamination_paths = _canonical_contamination_paths(work_dir, registry)
    if contamination_paths != canonical_contamination_paths:
        raise ValueError(
            "Contamination evidence must use the canonical work-root evaluation paths."
        )
    work_dir.mkdir(parents=True, exist_ok=True)
    sample_dir = work_dir / "tokenizer_sample"
    state_dir = work_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    plan = build_tokenizer_sample_plan(registry, mixture, candidate_config)
    quality_policy = _quality_policy(
        model_config, [str(path) for path in contamination_paths]
    )
    chunk_bytes = 268_435_456
    request = LocalSampleRequest(
        registry=registry,
        plan=plan,
        output_dir=sample_dir,
        state_path=state_dir / "tokenizer_sample.sqlite3",
        quality_policy=quality_policy,
        chunk_bytes=chunk_bytes,
        build_provenance=_sample_build_provenance(
            registry=registry,
            plan=plan,
            candidate_config=candidate_config,
            model_config=model_config,
            quality_policy=quality_policy,
            contamination_paths=contamination_paths,
            chunk_bytes=chunk_bytes,
        ),
        managed_root=work_dir,
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
    registry: Any,
    mixture: Mapping[str, Any],
) -> dict[str, Any]:
    destination = drive_dir / "tokenizers" / candidate_config.candidate_label
    expected_provenance = _current_sample_provenance(
        work_dir=work_dir,
        registry=registry,
        mixture=mixture,
        candidate_config=candidate_config,
        model_config=model_config,
    )
    sample_manifest, sample_manifest_sha256, _ = _canonical_sample_manifest(
        args.sample_manifest,
        work_dir,
        "--sample-manifest",
        expected_provenance=expected_provenance,
    )
    require_managed_path(drive_dir, destination.parent, kind="directory")
    require_managed_path(drive_dir, destination, kind="directory")
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
    for filename in ("tokenizer.json", "special_tokens.json", "tokenizer_report.json"):
        require_managed_path(
            drive_dir, destination / filename, kind="file", allow_missing=False
        )
    tokenizer_sha256 = sha256_file(destination / "tokenizer.json")
    for candidate_report in (report, persisted):
        if candidate_report.get("fitting_manifest_sha256") != sample_manifest_sha256:
            raise ValueError("Candidate tokenizer fitting manifest fingerprint mismatch.")
        if candidate_report.get("tokenizer_sha256") != tokenizer_sha256:
            raise ValueError("Candidate tokenizer report fingerprint mismatch.")
    if persisted != report:
        raise ValueError("Persisted candidate tokenizer report mismatch.")
    return report


def _pilot_recipe_sha256() -> str:
    digest = hashlib.sha256()
    digest.update(b"telco-data-recipe-v1\0")
    digest.update(CANONICAL_CONFIGS["--model-config"].read_bytes())
    digest.update(b"\0")
    digest.update(CANONICAL_CONFIGS["--sources"].read_bytes())
    digest.update(b"\0")
    digest.update(CANONICAL_CONFIGS["--mixture"].read_bytes())
    return digest.hexdigest()


def _canonical_pilot_provenance(
    drive_dir: Path,
    supplied: str | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    recipe_sha256 = _pilot_recipe_sha256()
    recipe_id = recipe_sha256[:12]
    recipe_root = drive_dir / "recipes" / recipe_id
    baseline = recipe_root / "prepared" / "pilot" / "tokenizer"
    provenance_path = (
        recipe_root / "evidence" / "pilot" / "tokenizer_provenance.json"
    )
    for path, kind in (
        (drive_dir / "recipes", "directory"),
        (recipe_root, "directory"),
        (recipe_root / "prepared", "directory"),
        (recipe_root / "prepared" / "pilot", "directory"),
        (baseline, "directory"),
        (baseline / "tokenizer.json", "file"),
        (baseline / "special_tokens.json", "file"),
        (recipe_root / "evidence", "directory"),
        (recipe_root / "evidence" / "pilot", "directory"),
        (provenance_path, "file"),
    ):
        require_managed_path(drive_dir, path, kind=kind, allow_missing=False)
    if supplied is not None:
        supplied_path = _required_managed_path(
            drive_dir, supplied, "--baseline-provenance"
        )
        if supplied_path != provenance_path.resolve():
            raise ValueError(
                "--baseline-provenance must be the canonical pilot evidence file."
            )
    provenance = _load_json_object(provenance_path, "Pilot tokenizer provenance")
    expected_relative_sample = "corpora/pilot/manifest.json"
    expected_relative_tokenizer = "prepared/pilot/tokenizer"
    sample_manifest = recipe_root / expected_relative_sample
    require_managed_path(
        drive_dir, sample_manifest, kind="file", allow_missing=False
    )
    sample_payload = _load_json_object(sample_manifest, "Pilot sample manifest")
    sample_manifest_sha256 = _manifest_sha256(sample_payload, "Pilot sample")
    unsigned_sample = dict(sample_payload)
    unsigned_sample.pop("manifest_sha256", None)
    if sha256_json(unsigned_sample) != sample_manifest_sha256:
        raise ValueError("Pilot sample manifest checksum mismatch.")
    expected = {
        "version": 1,
        "stage": "pilot",
        "recipe_sha256": recipe_sha256,
        "recipe_id": recipe_id,
        "sample_manifest_relative_path": expected_relative_sample,
        "sample_manifest_file_sha256": sha256_file(sample_manifest),
        "sample_manifest_sha256": sample_manifest_sha256,
        "tokenizer_relative_path": expected_relative_tokenizer,
        "tokenizer_sha256": sha256_file(baseline / "tokenizer.json"),
    }
    expected["provenance_sha256"] = sha256_json(expected)
    if provenance != expected:
        raise ValueError(
            "Pilot tokenizer provenance does not match the canonical pilot recipe, "
            "sample, and tokenizer."
        )
    return baseline.resolve(), provenance_path.resolve(), provenance


def _comparison_workflow_evidence(
    *,
    sample_manifest_sha256: str,
    sample_payload: Mapping[str, Any],
    expected_sample_provenance: Mapping[str, Any],
    pilot_provenance: Mapping[str, Any],
    candidate_report: Mapping[str, Any],
    baseline_tokenizer_sha256: str,
    candidate_tokenizer_sha256: str,
) -> dict[str, Any]:
    recipe = expected_sample_provenance.get("recipe")
    if not isinstance(recipe, Mapping):
        raise ValueError("Current candidate recipe provenance is invalid.")
    evidence = {
        "version": 1,
        "sample_manifest_sha256": sample_manifest_sha256,
        "sample_build_provenance_sha256": sample_payload.get(
            "build_provenance_sha256"
        ),
        "candidate_recipe_sha256": recipe.get("sha256"),
        "candidate_report_sha256": sha256_json(candidate_report),
        "baseline_provenance_sha256": pilot_provenance.get("provenance_sha256"),
        "baseline_recipe_sha256": pilot_provenance.get("recipe_sha256"),
        "baseline_sample_manifest_sha256": pilot_provenance.get(
            "sample_manifest_sha256"
        ),
        "baseline_tokenizer_sha256": baseline_tokenizer_sha256,
        "candidate_tokenizer_sha256": candidate_tokenizer_sha256,
    }
    if any(not isinstance(value, (int, str)) for value in evidence.values()):
        raise ValueError("Tokenizer comparison workflow evidence is incomplete.")
    return evidence


def _comparison_stage(
    args: argparse.Namespace,
    *,
    work_dir: Path,
    drive_dir: Path,
    candidate_config: TokenizerCandidateConfig,
    model_config: dict[str, Any],
    registry: Any,
    mixture: Mapping[str, Any],
) -> dict[str, Any]:
    destination = drive_dir / "comparison.json"
    require_managed_path(drive_dir, destination, kind="file")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Comparison already exists: {destination}")
    if not args.baseline_provenance:
        raise ValueError("tokenizer_compare requires --baseline-provenance.")
    baseline, _, pilot_provenance = _canonical_pilot_provenance(
        drive_dir, args.baseline_provenance
    )
    supplied_baseline = _required_managed_path(
        drive_dir,
        args.baseline_tokenizer,
        "--baseline-tokenizer",
        directory=True,
    )
    if supplied_baseline != baseline:
        raise ValueError(
            "--baseline-tokenizer must be the canonical preserved pilot tokenizer."
        )
    canonical_candidate = drive_dir / "tokenizers" / candidate_config.candidate_label
    for path, kind in (
        (drive_dir / "tokenizers", "directory"),
        (canonical_candidate, "directory"),
        (canonical_candidate / "tokenizer.json", "file"),
        (canonical_candidate / "special_tokens.json", "file"),
        (canonical_candidate / "tokenizer_report.json", "file"),
    ):
        require_managed_path(drive_dir, path, kind=kind, allow_missing=False)
    candidate = _required_managed_path(
        drive_dir,
        args.candidate_tokenizer,
        "--candidate-tokenizer",
        directory=True,
    )
    if candidate != canonical_candidate.resolve():
        raise ValueError(
            "--candidate-tokenizer must be the canonical candidate destination."
        )
    if baseline == candidate:
        raise ValueError("Baseline and candidate tokenizer directories must differ.")
    expected_provenance = _current_sample_provenance(
        work_dir=work_dir,
        registry=registry,
        mixture=mixture,
        candidate_config=candidate_config,
        model_config=model_config,
    )
    holdout, sample_manifest_sha256, sample_payload = _canonical_sample_manifest(
        args.holdout_manifest,
        work_dir,
        "--holdout-manifest",
        expected_provenance=expected_provenance,
    )
    candidate_report = _load_json_object(
        candidate / "tokenizer_report.json", "Candidate tokenizer report"
    )
    if candidate_report.get("fitting_manifest_sha256") != sample_manifest_sha256:
        raise ValueError("Candidate tokenizer fitting manifest fingerprint mismatch.")
    candidate_report_sha256 = candidate_report.get("tokenizer_sha256")
    baseline_report_sha256 = pilot_provenance["tokenizer_sha256"]
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
    if baseline_evaluation.get("tokenizer_sha256") != baseline_report_sha256:
        raise ValueError("Baseline evaluation tokenizer provenance mismatch.")
    comparison = compare_tokenizers(
        baseline_evaluation, candidate_evaluation, candidate_config
    )
    if comparison.get("labels") != {
        "baseline": candidate_config.baseline_label,
        "candidate": candidate_config.candidate_label,
    }:
        raise ValueError("Tokenizer comparison side labels mismatch.")
    comparison.pop("comparison_sha256", None)
    comparison["workflow_evidence"] = _comparison_workflow_evidence(
        sample_manifest_sha256=sample_manifest_sha256,
        sample_payload=sample_payload,
        expected_sample_provenance=expected_provenance,
        pilot_provenance=pilot_provenance,
        candidate_report=candidate_report,
        baseline_tokenizer_sha256=baseline_report_sha256,
        candidate_tokenizer_sha256=candidate_report_sha256,
    )
    comparison["comparison_sha256"] = sha256_json(comparison)
    _write_json_exclusive(destination, comparison, managed_root=drive_dir)
    return comparison


def _selection_stage(
    args: argparse.Namespace,
    *,
    work_dir: Path,
    drive_dir: Path,
    registry: Any,
    mixture: Mapping[str, Any],
    candidate_config: TokenizerCandidateConfig,
    model_config: Mapping[str, Any],
) -> dict[str, Any]:
    if not args.approve:
        raise ValueError(
            "tokenizer_select requires --approve after the comparison is reviewed."
        )
    if not args.winner:
        raise ValueError("tokenizer_select requires --winner.")
    canonical_comparison = drive_dir / "comparison.json"
    comparison_path = _required_managed_path(
        drive_dir, args.comparison, "--comparison"
    )
    if comparison_path != canonical_comparison.resolve():
        raise ValueError("--comparison must be the canonical Drive comparison.json.")
    comparison = _load_json_object(comparison_path, "Tokenizer comparison")
    expected_labels = {
        "baseline": candidate_config.baseline_label,
        "candidate": candidate_config.candidate_label,
    }
    if comparison.get("labels") != expected_labels:
        raise ValueError("Tokenizer comparison labels do not match the current recipe.")
    expected_provenance = _current_sample_provenance(
        work_dir=work_dir,
        registry=registry,
        mixture=mixture,
        candidate_config=candidate_config,
        model_config=model_config,
    )
    sample_manifest = work_dir / "tokenizer_sample" / "manifest.json"
    _, sample_manifest_sha256, sample_payload = _canonical_sample_manifest(
        str(sample_manifest),
        work_dir,
        "canonical sample manifest",
        expected_provenance=expected_provenance,
    )
    baseline, _, pilot_provenance = _canonical_pilot_provenance(drive_dir)
    candidate = drive_dir / "tokenizers" / candidate_config.candidate_label
    for path, kind in (
        (candidate, "directory"),
        (candidate / "tokenizer.json", "file"),
        (candidate / "special_tokens.json", "file"),
        (candidate / "tokenizer_report.json", "file"),
        (baseline, "directory"),
        (baseline / "tokenizer.json", "file"),
        (baseline / "special_tokens.json", "file"),
    ):
        require_managed_path(drive_dir, path, kind=kind, allow_missing=False)
    candidate_report = _load_json_object(
        candidate / "tokenizer_report.json", "Candidate tokenizer report"
    )
    baseline_sha256 = sha256_file(baseline / "tokenizer.json")
    candidate_sha256 = sha256_file(candidate / "tokenizer.json")
    if (
        candidate_report.get("fitting_manifest_sha256")
        != sample_manifest_sha256
        or candidate_report.get("tokenizer_sha256") != candidate_sha256
    ):
        raise ValueError(
            "Candidate tokenizer report is not bound to the current sample and "
            "tokenizer."
        )
    expected_workflow_evidence = _comparison_workflow_evidence(
        sample_manifest_sha256=sample_manifest_sha256,
        sample_payload=sample_payload,
        expected_sample_provenance=expected_provenance,
        pilot_provenance=pilot_provenance,
        candidate_report=candidate_report,
        baseline_tokenizer_sha256=baseline_sha256,
        candidate_tokenizer_sha256=candidate_sha256,
    )
    if comparison.get("workflow_evidence") != expected_workflow_evidence:
        raise ValueError(
            "Tokenizer comparison does not match current recipe and provenance evidence."
        )
    fingerprints = comparison.get("fingerprints")
    if not isinstance(fingerprints, Mapping) or (
        fingerprints.get("baseline_tokenizer_sha256") != baseline_sha256
        or fingerprints.get("candidate_tokenizer_sha256") != candidate_sha256
        or fingerprints.get("baseline_sample_manifest_sha256")
        != sample_manifest_sha256
        or fingerprints.get("candidate_sample_manifest_sha256")
        != sample_manifest_sha256
    ):
        raise ValueError("Tokenizer comparison fingerprints are stale or foreign.")
    selection_path = drive_dir / "tokenizer_selection.json"
    require_managed_path(drive_dir, selection_path, kind="file")
    return write_tokenizer_selection(
        comparison,
        args.winner,
        selection_path,
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
    print(
        json.dumps(
            {
                "event": "storage_advisory",
                "enforced": False,
                "max_working_gib": candidate_config.max_working_gib,
                "min_free_gib": candidate_config.min_free_gib,
                "mode": candidate_config.storage_enforcement,
            },
            sort_keys=True,
        ),
        flush=True,
    )

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
            registry=registry,
            mixture=mixture,
        )
    if args.stage == "tokenizer_compare":
        return _comparison_stage(
            args,
            work_dir=work_dir,
            drive_dir=drive_dir,
            candidate_config=candidate_config,
            model_config=model_config,
            registry=registry,
            mixture=mixture,
        )
    if args.stage == "tokenizer_select":
        return _selection_stage(
            args,
            work_dir=work_dir,
            drive_dir=drive_dir,
            registry=registry,
            mixture=mixture,
            candidate_config=candidate_config,
            model_config=model_config,
        )
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
