#!/usr/bin/env python
"""Run only the local Telco data and tokenizer preparation stages."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import sys
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.config import config_to_yaml, load_config
from matgpt.data.contamination import pattern_fingerprint
from matgpt.data.local_corpus import (
    LocalCorpusRequest,
    _identity as _local_corpus_identity,
    _load_dataset_function,
    _selected_tokenizer_sha as _local_selected_tokenizer_sha,
    build_local_corpus,
)
from matgpt.data.local_publish import DrivePublisher, StoragePolicy, StoragePressure
from matgpt.data.local_sample import LocalSampleRequest, build_tokenizer_sample
from matgpt.data.mixture import build_mixture_plan, load_mixture_config
from matgpt.data.quality import DataQualityPolicy, load_contamination_patterns
from matgpt.data.sources import load_source_registry
from matgpt.data.token_dtype import DTYPES
from matgpt.data.telco_prepare import QUOTA_AUDIT_METHOD, QUOTA_AUDIT_VERSION
from matgpt.preflight_schema import CHECK_IDS
from matgpt.tokenizer.candidate import (
    TokenizerCandidateConfig,
    build_tokenizer_sample_plan,
    compare_tokenizers,
    load_tokenizer_candidate_config,
    validate_tokenizer_selection,
    write_tokenizer_selection,
)
from matgpt.tokenizer.io import load_tokenizer_metadata
from matgpt.tokenizer.train import (
    REQUIRED_VOCAB_SIZE,
    evaluate_tokenizer_on_jsonl,
    train_tokenizer_from_manifest,
)
from matgpt.utils.hashing import sha256_file, sha256_json, sha256_text
from matgpt.utils.paths import open_exclusive_nofollow, require_managed_path


STAGES = (
    "tokenizer_sample",
    "tokenizer_candidate",
    "tokenizer_compare",
    "tokenizer_select",
    "pilot_refresh",
    "full_calibration",
    "full_resume",
    "status",
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
CALIBRATION_TARGET_TOKENS = 100_000_000
PILOT_TOKENS = 20_000_000
PILOT_SHARD_DTYPE = "uint16"
FULL_TARGET_TOKENS = 12_000_000_000
CALIBRATION_MAX_WALL_SECONDS = 48 * 60 * 60
MAX_EVIDENCE_JSON_BYTES = 4 * 1024 * 1024
MAX_EVALUATION_JSON_FILES = 256
MAX_JSON_DEPTH = 64


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
    parser.add_argument(
        "--stop-after-quota-tokens",
        type=int,
        default=CALIBRATION_TARGET_TOKENS,
        help="Calibration stop. The canonical full calibration requires exactly 100M.",
    )
    parser.add_argument(
        "--accept-calibration",
        action="store_true",
        help="Explicitly accept the canonical same-identity 100M calibration.",
    )
    parser.add_argument(
        "--override-calibration-guard",
        action="store_true",
        help="Override only the 48-hour or storage-pressure calibration guard.",
    )
    parser.add_argument(
        "--override-reason",
        default="",
        help="Required operator reason when overriding a calibration guard.",
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
        size = path.stat().st_size
        if size > MAX_EVIDENCE_JSON_BYTES:
            raise ValueError(f"{label} exceeds the bounded JSON size limit.")
        with path.open("rb") as handle:
            raw = handle.read(MAX_EVIDENCE_JSON_BYTES + 1)
        if len(raw) > MAX_EVIDENCE_JSON_BYTES:
            raise ValueError(f"{label} exceeds the bounded JSON size limit.")
        payload = json.loads(raw.decode("utf-8"), parse_constant=reject_constant)
    except (json.JSONDecodeError, UnicodeError, RecursionError) as error:
        raise ValueError(f"{label} is invalid JSON: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object.")
    pending = [(payload, 1)]
    while pending:
        value, depth = pending.pop()
        if depth > MAX_JSON_DEPTH:
            raise ValueError(f"{label} exceeds the maximum JSON nesting depth.")
        if isinstance(value, Mapping):
            pending.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            pending.extend((item, depth + 1) for item in value)
    return payload


def _bounded_json_files(root: Path, *, managed_root: Path, label: str) -> list[Path]:
    root = require_managed_path(managed_root, root, kind="directory", allow_missing=False)
    found: list[Path] = []
    for directory, names, files in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        for name in names:
            if (directory_path / name).is_symlink():
                raise ValueError(f"{label} contains a symbolic-link directory.")
        for name in files:
            if not name.endswith(".json"):
                continue
            path = directory_path / name
            require_managed_path(managed_root, path, kind="file", allow_missing=False)
            found.append(path)
            if len(found) > MAX_EVALUATION_JSON_FILES:
                raise ValueError(f"{label} exceeds the maximum JSON file count.")
    return sorted(found)


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


def _operator_evidence_root(drive_dir: Path, tokenizer_sha256: str) -> Path:
    if SHA256_PATTERN.fullmatch(tokenizer_sha256) is None:
        raise ValueError("Selected tokenizer fingerprint must be a lowercase SHA-256.")
    return drive_dir / "evidence" / "tokenizers" / tokenizer_sha256


def _pilot_refresh_path(drive_dir: Path, tokenizer_sha256: str) -> Path:
    return _operator_evidence_root(drive_dir, tokenizer_sha256) / "pilot/pilot_refresh.json"


def _calibration_operator_path(drive_dir: Path, tokenizer_sha256: str) -> Path:
    return (
        _operator_evidence_root(drive_dir, tokenizer_sha256)
        / "full/calibration_operator_report.json"
    )


def _resume_operator_path(drive_dir: Path, tokenizer_sha256: str) -> Path:
    return (
        _operator_evidence_root(drive_dir, tokenizer_sha256)
        / "full/resume_operator_evidence.json"
    )


def _hashed_payload(
    payload: Mapping[str, Any], hash_field: str
) -> dict[str, Any]:
    result = dict(payload)
    result.pop(hash_field, None)
    result[hash_field] = sha256_json(result)
    return result


def _write_hashed_evidence(
    path: Path,
    payload: Mapping[str, Any],
    *,
    hash_field: str,
    managed_root: Path,
) -> dict[str, Any]:
    evidence = _hashed_payload(payload, hash_field)
    _write_json_exclusive(path, evidence, managed_root=managed_root)
    persisted = _load_json_object(path, path.name)
    expected_bytes = (
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    if persisted != evidence or path.read_bytes() != expected_bytes:
        raise ValueError(f"Evidence publication verification failed: {path}")
    return evidence


def _read_hashed_evidence(
    path: Path,
    *,
    hash_field: str,
    managed_root: Path,
    label: str,
) -> dict[str, Any]:
    path = require_managed_path(
        managed_root, path, kind="file", allow_missing=False
    )
    payload = _load_json_object(path, label)
    stored = payload.get(hash_field)
    unsigned = dict(payload)
    unsigned.pop(hash_field, None)
    if (
        not isinstance(stored, str)
        or SHA256_PATTERN.fullmatch(stored) is None
        or sha256_json(unsigned) != stored
    ):
        raise ValueError(f"{label} checksum mismatch.")
    return payload


def _selected_tokenizer_evidence(
    *,
    drive_dir: Path,
    work_dir: Path,
    registry: Any,
    mixture: Mapping[str, Any],
    candidate_config: TokenizerCandidateConfig,
    model_config: Mapping[str, Any],
) -> tuple[str, Path, str, dict[str, Any], dict[str, Any]]:
    comparison_path = require_managed_path(
        drive_dir,
        drive_dir / "comparison.json",
        kind="file",
        allow_missing=False,
    )
    selection_path = require_managed_path(
        drive_dir,
        drive_dir / "tokenizer_selection.json",
        kind="file",
        allow_missing=False,
    )
    comparison = _load_json_object(comparison_path, "Tokenizer comparison")
    selection = _load_json_object(selection_path, "Tokenizer selection")
    selected_sha256 = validate_tokenizer_selection(selection, comparison)
    expected_labels = {
        "baseline": candidate_config.baseline_label,
        "candidate": candidate_config.candidate_label,
    }
    if comparison.get("labels") != expected_labels:
        raise ValueError("Tokenizer selection comparison labels are stale or foreign.")
    winner = str(selection["winner"])
    if winner == candidate_config.baseline_label:
        tokenizer_dir, _, provenance = _canonical_pilot_provenance(drive_dir)
        if provenance.get("tokenizer_sha256") != selected_sha256:
            raise ValueError("Selected pilot tokenizer provenance fingerprint mismatch.")
    elif winner == candidate_config.candidate_label:
        tokenizer_dir = drive_dir / "tokenizers" / candidate_config.candidate_label
        for relative, kind in (
            (tokenizer_dir, "directory"),
            (tokenizer_dir / "tokenizer.json", "file"),
            (tokenizer_dir / "special_tokens.json", "file"),
            (tokenizer_dir / "tokenizer_report.json", "file"),
        ):
            require_managed_path(
                drive_dir, relative, kind=kind, allow_missing=False
            )
        report = _load_json_object(
            tokenizer_dir / "tokenizer_report.json", "Candidate tokenizer report"
        )
        if report.get("tokenizer_sha256") != selected_sha256:
            raise ValueError("Selected candidate tokenizer report fingerprint mismatch.")
    else:
        raise ValueError("Tokenizer selection winner is not a canonical label.")
    tokenizer_dir = tokenizer_dir.resolve()
    if sha256_file(tokenizer_dir / "tokenizer.json") != selected_sha256:
        raise ValueError("Selected tokenizer bytes changed after approval.")
    metadata = load_tokenizer_metadata(tokenizer_dir)
    if metadata.get("tokenizer_sha256") != selected_sha256:
        raise ValueError("Selected tokenizer metadata fingerprint mismatch.")
    expected_provenance = _current_sample_provenance(
        work_dir=work_dir,
        registry=registry,
        mixture=mixture,
        candidate_config=candidate_config,
        model_config=model_config,
    )
    sample_manifest, sample_manifest_sha256, sample_payload = (
        _canonical_sample_manifest(
            str(work_dir / "tokenizer_sample/manifest.json"),
            work_dir,
            "canonical sample manifest",
            expected_provenance=expected_provenance,
        )
    )
    del sample_manifest
    baseline, _, pilot_provenance = _canonical_pilot_provenance(drive_dir)
    candidate = drive_dir / "tokenizers" / candidate_config.candidate_label
    for path, kind in (
        (baseline / "tokenizer.json", "file"),
        (candidate, "directory"),
        (candidate / "tokenizer.json", "file"),
        (candidate / "special_tokens.json", "file"),
        (candidate / "tokenizer_report.json", "file"),
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
        raise ValueError("Candidate tokenizer report is stale or foreign.")
    expected_workflow = _comparison_workflow_evidence(
        sample_manifest_sha256=sample_manifest_sha256,
        sample_payload=sample_payload,
        expected_sample_provenance=expected_provenance,
        pilot_provenance=pilot_provenance,
        candidate_report=candidate_report,
        baseline_tokenizer_sha256=baseline_sha256,
        candidate_tokenizer_sha256=candidate_sha256,
    )
    if comparison.get("workflow_evidence") != expected_workflow:
        raise ValueError("Tokenizer selection workflow evidence is stale or foreign.")
    fingerprints = comparison.get("fingerprints")
    if not isinstance(fingerprints, Mapping) or (
        fingerprints.get("baseline_tokenizer_sha256") != baseline_sha256
        or fingerprints.get("candidate_tokenizer_sha256") != candidate_sha256
        or fingerprints.get("baseline_sample_manifest_sha256")
        != sample_manifest_sha256
        or fingerprints.get("candidate_sample_manifest_sha256")
        != sample_manifest_sha256
    ):
        raise ValueError("Tokenizer selection comparison fingerprints are stale.")
    return winner, tokenizer_dir, selected_sha256, selection, comparison


def _corpus_request(
    *,
    kind: str,
    work_dir: Path,
    drive_dir: Path,
    registry: Any,
    mixture: Mapping[str, Any],
    candidate_config: TokenizerCandidateConfig,
    model_config: Mapping[str, Any],
    tokenizer_dir: Path,
    tokenizer_sha256: str,
) -> LocalCorpusRequest:
    if kind not in {"pilot", "full"}:
        raise ValueError(f"Unsupported corpus request kind: {kind}")
    stages = ("pilot",) if kind == "pilot" else ("main", "cooldown")
    plans = tuple(build_mixture_plan(registry, mixture, stage) for stage in stages)
    contamination_paths = _canonical_contamination_paths(work_dir, registry)
    quality = _quality_policy(
        dict(model_config), [str(path) for path in contamination_paths]
    )
    local_root = work_dir / "corpus" / kind / tokenizer_sha256
    destination_root = drive_dir / "corpora" / kind / tokenizer_sha256
    return LocalCorpusRequest(
        registry=registry,
        plans=plans,
        tokenizer_dir=tokenizer_dir,
        tokenizer_selection_path=drive_dir / "tokenizer_selection.json",
        local_root=local_root,
        destination_root=destination_root,
        quality_policy=quality,
        evidence_root=drive_dir,
        batch_documents=128,
        shard_size_tokens=int(model_config["sharding"]["shard_size_tokens"]),
        raw_unit_bytes=268_435_456,
        max_working_bytes=candidate_config.max_working_gib * 1024**3,
        min_free_bytes=candidate_config.min_free_gib * 1024**3,
        progress_interval_seconds=30.0,
    )


def _provider_preflight(request: LocalCorpusRequest) -> dict[str, bool]:
    Path(request.local_root).mkdir(parents=True, exist_ok=True)
    publisher = DrivePublisher(
        local_root=request.local_root,
        destination_root=request.destination_root,
        policy=StoragePolicy(request.max_working_bytes, request.min_free_bytes),
    )
    result = publisher.preflight_destination_provider()
    if result != {"fsynced_partial_rename": True, "hard_links_required": False}:
        raise ValueError("Destination provider preflight did not prove safe publication.")
    return result


def _safe_tree_bytes(root: Path) -> int:
    if not root.exists():
        return 0
    require_managed_path(root, root, kind="directory", allow_missing=False)
    total = 0
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Managed tree contains a symbolic link: {path}")
        if path.is_file():
            require_managed_path(root, path, kind="file", allow_missing=False)
            total += path.stat().st_size
    return total


def _fingerprint_tree(root: Path, *, managed_root: Path, label: str) -> dict[str, Any]:
    root = require_managed_path(
        managed_root, root, kind="directory", allow_missing=False
    )
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"{label} contains a symbolic link: {path}")
        if not path.is_file():
            continue
        path = require_managed_path(root, path, kind="file", allow_missing=False)
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    if not files:
        raise ValueError(f"{label} contains no files.")
    return {"files": files, "fingerprint_sha256": sha256_json(files)}


def _file_fingerprint(path: Path, *, managed_root: Path) -> dict[str, Any]:
    path = require_managed_path(
        managed_root, path, kind="file", allow_missing=False
    )
    return {
        "path": path.relative_to(managed_root).as_posix(),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _validated_pilot_manifest(
    path: Path,
    *,
    managed_root: Path,
    tokenizer_sha256: str,
    expected_build_identity: str | None = None,
) -> tuple[dict[str, Any], str]:
    path = require_managed_path(
        managed_root, path, kind="file", allow_missing=False
    )
    manifest = _load_json_object(path, "Pilot corpus manifest")
    stored = manifest.get("manifest_sha256")
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256", None)
    quota_counting = manifest.get("quota_counting", {})
    manifest_tokenizer = (
        quota_counting.get("tokenizer_sha256")
        if isinstance(quota_counting, Mapping)
        else None
    ) or manifest.get("tokenizer_sha256")
    build_identity = manifest.get("build_identity_sha256")
    version = manifest.get("version")
    if (
        version not in (1, 2)
        or (version == 2 and manifest.get("status") != "complete")
        or manifest.get("complete") is not True
        or stored != sha256_json(unsigned)
        or manifest_tokenizer != tokenizer_sha256
        or (version == 2 and (
            not isinstance(build_identity, str)
            or SHA256_PATTERN.fullmatch(build_identity) is None
        ))
    ):
        raise ValueError("Pilot corpus manifest schema or identity is invalid.")
    if version == 1:
        stages = manifest.get("stages")
        pilot = stages.get("pilot") if isinstance(stages, Mapping) else None
        validation = manifest.get("validation")
        split_stats = manifest.get("split_stats")
        if (
            not isinstance(pilot, Mapping)
            or type(pilot.get("requested_tokens")) is not int
            or pilot["requested_tokens"] != PILOT_TOKENS
            or type(pilot.get("quota_tokens")) is not int
            or not PILOT_TOKENS <= pilot["quota_tokens"] <= 2**63 - 1
            or type(pilot.get("documents")) is not int
            or not 0 < pilot["documents"] <= 2**63 - 1
            or pilot.get("document_count") != pilot["documents"]
            or not isinstance(validation, Mapping)
            or type(validation.get("quota_tokens")) is not int
            or not 0 < validation["quota_tokens"] <= 2**63 - 1
            or type(validation.get("documents")) is not int
            or not 0 < validation["documents"] <= 2**63 - 1
            or validation.get("document_count") != validation["documents"]
            or not isinstance(split_stats, Mapping)
            or split_stats.get("pilot") != pilot
            or split_stats.get("validation") != validation
            or not isinstance(quota_counting, Mapping)
            or quota_counting.get("method") != "tokenizer_exact"
        ):
            raise ValueError("Legacy pilot manifest does not prove the canonical 20M target and validation split.")
        items = pilot.get("items")
        if not isinstance(items, Mapping) or not items:
            raise ValueError("Legacy pilot manifest item accounting is missing.")
        item_requested = item_quota = item_documents = item_estimated = 0
        for item_id, item in items.items():
            if (
                not isinstance(item_id, str)
                or not item_id
                or not isinstance(item, Mapping)
                or type(item.get("requested_tokens")) is not int
                or not 0 < item["requested_tokens"] <= 2**63 - 1
                or type(item.get("quota_tokens")) is not int
                or not item["requested_tokens"] <= item["quota_tokens"] <= 2**63 - 1
                or type(item.get("documents")) is not int
                or not 0 < item["documents"] <= 2**63 - 1
                or type(item.get("estimated_tokens")) is not int
                or not 0 <= item["estimated_tokens"] <= 2**63 - 1
                or type(item.get("raw_bytes")) is not int
                or not 0 <= item["raw_bytes"] <= 2**63 - 1
            ):
                raise ValueError("Legacy pilot manifest item accounting is invalid.")
            values = (
                item["requested_tokens"], item["quota_tokens"],
                item["documents"], item["estimated_tokens"],
            )
            totals = (item_requested, item_quota, item_documents, item_estimated)
            if any(total > (2**63 - 1) - value for total, value in zip(totals, values)):
                raise ValueError("Legacy pilot manifest item accounting overflows.")
            item_requested += item["requested_tokens"]
            item_quota += item["quota_tokens"]
            item_documents += item["documents"]
            item_estimated += item["estimated_tokens"]
        if (
            item_requested != pilot["requested_tokens"]
            or item_quota != pilot["quota_tokens"]
            or item_documents != pilot["documents"]
            or pilot.get("estimated_tokens") != item_estimated
        ):
            raise ValueError("Legacy pilot manifest item totals do not reconcile.")
        validation_items = validation.get("items")
        if (
            not isinstance(validation_items, Mapping)
            or not validation_items
            or any(
                not isinstance(item_id, str)
                or not item_id
                or type(document_count) is not int
                or not 0 < document_count <= 2**63 - 1
                for item_id, document_count in validation_items.items()
            )
            or sum(validation_items.values()) != validation["documents"]
        ):
            raise ValueError("Legacy validation item accounting does not reconcile.")
        build_identity = sha256_json(
            {"format": "legacy_telco_prepare_v1", "manifest_sha256": stored,
             "tokenizer_sha256": tokenizer_sha256}
        )
    if expected_build_identity is not None and build_identity != expected_build_identity:
        raise ValueError("Pilot corpus manifest build identity mismatch.")
    return manifest, build_identity


def _validated_pilot_quota_audit(
    path: Path,
    *,
    managed_root: Path,
    manifest: Mapping[str, Any],
    tokenizer_sha256: str,
    build_identity_sha256: str,
    manifest_file_sha256: str,
) -> dict[str, Any]:
    path = require_managed_path(
        managed_root, path, kind="file", allow_missing=False
    )
    audit = _load_json_object(path, "Pilot quota audit")
    stored = audit.get("audit_sha256")
    unsigned = dict(audit)
    unsigned.pop("audit_sha256", None)
    version = manifest.get("version")
    fingerprints = manifest.get("fingerprints")
    if (
        audit.get("version") != QUOTA_AUDIT_VERSION
        or audit.get("passed") is not True
        or audit.get("method") != QUOTA_AUDIT_METHOD
        or audit.get("tokenizer_sha256") != tokenizer_sha256
        or audit.get("corpus_manifest_sha256") != manifest.get("manifest_sha256")
        or audit.get("corpus_build_identity_sha256") != build_identity_sha256
        or audit.get("corpus_manifest_file_sha256")
        != manifest_file_sha256
        or not isinstance(stored, str)
        or stored != sha256_json(unsigned)
    ):
        raise ValueError("Pilot quota audit schema or identity is invalid.")
    manifest_stages = manifest.get("stages")
    audit_stages = audit.get("stages")
    stage_plan_sha256s = audit.get("stage_plan_sha256s")
    if (
        not isinstance(manifest_stages, Mapping)
        or not isinstance(audit_stages, Mapping)
        or set(audit_stages) != set(manifest_stages)
        or not isinstance(stage_plan_sha256s, Mapping)
        or set(stage_plan_sha256s) != set(manifest_stages)
    ):
        raise ValueError("Pilot quota audit stage coverage is incomplete.")
    if version == 1:
        expected_stage_plans = {
            stage: details.get("plan_sha256")
            for stage, details in manifest_stages.items()
            if isinstance(details, Mapping)
        }
        expected_plan_sha256 = sha256_json(dict(sorted(expected_stage_plans.items())))
        if (
            dict(stage_plan_sha256s) != expected_stage_plans
            or audit.get("plan_sha256") != expected_plan_sha256
        ):
            raise ValueError("Pilot quota audit plan identity is invalid.")
    elif (
        not isinstance(fingerprints, Mapping)
        or audit.get("plan_sha256") != fingerprints.get("plan_sha256")
    ):
        raise ValueError("Pilot quota audit plan identity is invalid.")
    for stage_id, manifest_stage in manifest_stages.items():
        audited_stage = audit_stages.get(stage_id)
        if not isinstance(manifest_stage, Mapping) or not isinstance(
            audited_stage, Mapping
        ):
            raise ValueError("Pilot quota audit stage accounting is invalid.")
        requested = manifest_stage.get("requested_tokens")
        actual = manifest_stage.get(
            "quota_tokens", manifest_stage.get("actual_tokens")
        )
        manifest_items = manifest_stage.get("items")
        audited_items = audited_stage.get("items")
        if (
            type(requested) is not int
            or type(actual) is not int
            or audited_stage.get("requested_tokens") != requested
            or audited_stage.get("planned_tokens") != requested
            or audited_stage.get("actual_tokens") != actual
            or audited_stage.get("overshoot_tokens") != actual - requested
            or audited_stage.get("document_boundary_limited") is not True
            or not isinstance(manifest_items, Mapping)
            or not isinstance(audited_items, Mapping)
            or set(audited_items) != set(manifest_items)
        ):
            raise ValueError("Pilot quota audit stage totals do not reconcile.")
        requested_sum = actual_sum = 0
        for item_id, manifest_item in manifest_items.items():
            audited_item = audited_items.get(item_id)
            if not isinstance(manifest_item, Mapping) or not isinstance(
                audited_item, Mapping
            ):
                raise ValueError("Pilot quota audit item accounting is invalid.")
            item_requested = manifest_item.get("requested_tokens")
            item_actual = manifest_item.get(
                "quota_tokens", manifest_item.get("actual_tokens")
            )
            last_document = audited_item.get("last_document_tokens")
            overshoot = audited_item.get("overshoot_tokens")
            if (
                type(item_requested) is not int
                or type(item_actual) is not int
                or type(last_document) is not int
                or type(overshoot) is not int
                or item_requested <= 0
                or item_actual < item_requested
                or last_document <= 0
                or audited_item.get("requested_tokens") != item_requested
                or audited_item.get("planned_tokens") != item_requested
                or audited_item.get("actual_tokens") != item_actual
                or overshoot != item_actual - item_requested
                or overshoot > last_document
                or item_actual - last_document >= item_requested
                or audited_item.get("document_boundary_limited")
                is not (overshoot > 0)
                or audited_item.get("passed") is not True
            ):
                raise ValueError(
                    "Pilot quota audit does not prove a minimal whole-document boundary."
                )
            requested_sum += item_requested
            actual_sum += item_actual
        if requested_sum != requested or actual_sum != actual:
            raise ValueError("Pilot quota audit item totals do not reconcile.")
    return audit


def _validated_pilot_gate(
    payload: Mapping[str, Any],
    *,
    gate: str,
    tokenizer_sha256: str,
    build_identity_sha256: str,
) -> None:
    if "gate" not in payload:
        if gate == "evaluation":
            if payload.get("status") in {"fail", "failed", "error"}:
                raise ValueError("Pilot evaluation evidence records failure.")
            checkpoint = payload.get("checkpoint")
            if not isinstance(checkpoint, str) or not checkpoint:
                raise ValueError("Pilot evaluation evidence has no checkpoint provenance.")
            if not any(key in payload for key in ("val_loss", "perplexity", "results", "tasks")):
                raise ValueError("Pilot evaluation evidence has no successful result payload.")
            return
        if payload.get("status") != "pass":
            raise ValueError(f"Pilot {gate} evidence status failed.")
        if gate == "preflight":
            checks = payload.get("checks")
            if not isinstance(checks, list) or any(
                not isinstance(check, Mapping) or check.get("status") != "pass"
                for check in checks
            ):
                raise ValueError("Pilot preflight checks did not all pass.")
            names = [check.get("name") for check in checks]
            if names != list(CHECK_IDS):
                raise ValueError(
                    "Pilot preflight must contain exactly the authoritative required checks."
                )
            return
        checkpoint = payload.get("checkpoint")
        if not isinstance(checkpoint, str) or not checkpoint:
            raise ValueError(f"Pilot {gate} evidence has no checkpoint provenance.")
        if gate == "smoke" and payload.get("resume_verified") is not True:
            raise ValueError("Pilot smoke evidence does not prove resume verification.")
        if gate == "pilot" and (
            payload.get("complete") is not True
            or not isinstance(payload.get("tokens_processed"), int)
            or isinstance(payload.get("tokens_processed"), bool)
            or payload["tokens_processed"] < 20_000_000
        ):
            raise ValueError("Pilot completion evidence did not reach 20M tokens.")
        return
    if (
        payload.get("version") != 1
        or payload.get("status") != "pass"
        or payload.get("gate") != gate
        or payload.get("gate_passed") is not True
        or payload.get("tokenizer_sha256") != tokenizer_sha256
        or payload.get("build_identity_sha256") != build_identity_sha256
    ):
        raise ValueError(f"Pilot {gate} evidence schema, status, or identity failed.")
    if gate == "preflight":
        checks = payload.get("checks")
        if not isinstance(checks, list) or [
            check.get("name") if isinstance(check, Mapping) else None
            for check in checks
        ] != list(CHECK_IDS) or any(
            not isinstance(check, Mapping) or check.get("status") != "pass"
            for check in checks
        ):
            raise ValueError(
                "Pilot preflight must contain exactly the authoritative required checks."
            )
    if gate == "smoke" and payload.get("resume_verified") is not True:
        raise ValueError("Pilot smoke evidence does not prove resume verification.")
    if gate == "pilot" and (
        payload.get("complete") is not True
        or not isinstance(payload.get("tokens_processed"), int)
        or isinstance(payload.get("tokens_processed"), bool)
        or int(payload["tokens_processed"]) < 20_000_000
    ):
        raise ValueError("Pilot completion evidence did not reach 20M tokens.")
    if gate == "evaluation" and payload.get("evaluation_passed") is not True:
        raise ValueError("Pilot evaluation evidence did not pass.")


def _finite_metric(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _checkpoint_from_canonical_reference(
    value: object, *, drive_dir: Path, checkpoint_root: Path
) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("Pilot checkpoint reference is invalid.")
    reference = PurePosixPath(value)
    if ".." in reference.parts:
        raise ValueError("Pilot checkpoint reference is unsafe.")
    drive_dir = require_managed_path(
        drive_dir, drive_dir, kind="directory", allow_missing=False
    )
    checkpoint_root = require_managed_path(
        drive_dir, checkpoint_root, kind="directory", allow_missing=False
    )
    local_candidate = Path(value)
    if local_candidate.is_absolute():
        try:
            resolved = local_candidate.resolve(strict=True)
            if resolved.is_relative_to(drive_dir.resolve()):
                candidate = resolved
            else:
                raise ValueError
        except (OSError, ValueError):
            selected_root_parts = PurePosixPath(
                checkpoint_root.relative_to(drive_dir).as_posix()
            ).parts
            selected_root_indexes = [
                index
                for index in range(len(reference.parts) - len(selected_root_parts))
                if reference.parts[index : index + len(selected_root_parts)]
                == selected_root_parts
                and len(reference.parts) == index + len(selected_root_parts) + 1
            ]
            recipe_indexes = [
                index for index, part in enumerate(reference.parts) if part == "recipes"
            ]
            if len(selected_root_indexes) == 1:
                candidate = checkpoint_root / reference.parts[-1]
            elif len(recipe_indexes) == 1:
                candidate = drive_dir / Path(*reference.parts[recipe_indexes[0] :])
            else:
                raise ValueError("Pilot checkpoint reference is outside the canonical namespace.")
    else:
        candidate = drive_dir / Path(*reference.parts)
    candidate = require_managed_path(
        drive_dir, candidate, kind="file", allow_missing=False
    )
    if candidate.parent != checkpoint_root:
        raise ValueError("Pilot checkpoint reference is outside the selected pilot namespace.")
    return candidate


def _validated_checkpoint_binding(
    payload: Mapping[str, Any],
    *,
    reference_key: str,
    binding_key: str,
    drive_dir: Path,
    checkpoint_root: Path,
    expected_stage: str,
) -> tuple[Path, dict[str, object]]:
    reference = payload.get(reference_key)
    binding = payload.get(binding_key)
    if (
        not isinstance(binding, Mapping)
        or set(binding) != {"path", "size", "sha256"}
        or binding.get("path") != reference
        or type(binding.get("size")) is not int
        or not 0 < binding["size"] <= 2**63 - 1
        or not isinstance(binding.get("sha256"), str)
        or SHA256_PATTERN.fullmatch(binding["sha256"]) is None
    ):
        raise ValueError(
            "Pilot checkpoint evidence lacks an immutable path/size/SHA binding; "
            "rerun the pilot gates."
        )
    checkpoint = _checkpoint_from_canonical_reference(
        reference, drive_dir=drive_dir, checkpoint_root=checkpoint_root
    )
    actual_size = checkpoint.stat().st_size
    actual_sha256 = sha256_file(checkpoint)
    expected_prefix = f"{expected_stage}-"
    if (
        actual_size < 1
        or binding["size"] != actual_size
        or binding["sha256"] != actual_sha256
        or not checkpoint.name.startswith(expected_prefix)
        or not checkpoint.name.endswith(f"-{actual_sha256}.pt")
    ):
        raise ValueError("Pilot immutable checkpoint binding mismatch.")
    return checkpoint, dict(binding)


def _validate_artifact_identity(
    payload: Mapping[str, Any], expected: Mapping[str, str]
) -> None:
    identity = payload.get("artifact_identity")
    if not isinstance(identity, Mapping) or dict(identity) != dict(expected):
        raise ValueError("Pilot evidence config/tokenizer/build identity mismatch.")


def _validate_task_result(row: object) -> None:
    if not isinstance(row, Mapping):
        raise ValueError("Pilot task evaluation row must be an object.")
    total, correct, accuracy = row.get("total"), row.get("correct"), row.get("accuracy")
    examples, categories = row.get("examples"), row.get("categories")
    if (
        row.get("task_type") != "multiple_choice"
        or not isinstance(row.get("path"), str)
        or not row["path"]
        or type(total) is not int
        or total < 1
        or type(correct) is not int
        or not 0 <= correct <= total
        or not _finite_metric(accuracy)
        or not 0.0 <= float(accuracy) <= 1.0
        or not isinstance(categories, Mapping)
        or not isinstance(examples, list)
        or len(examples) != total
        or abs(float(accuracy) - correct / total) > 1e-12
    ):
        raise ValueError("Pilot task evaluation summary is invalid.")
    category_total = 0
    category_correct = 0
    for category, category_row in categories.items():
        if not isinstance(category, str) or not category or not isinstance(category_row, Mapping):
            raise ValueError("Pilot task evaluation category is invalid.")
        row_total = category_row.get("total")
        row_correct = category_row.get("correct")
        row_accuracy = category_row.get("accuracy")
        if (
            type(row_total) is not int
            or row_total < 1
            or type(row_correct) is not int
            or not 0 <= row_correct <= row_total
            or not _finite_metric(row_accuracy)
            or abs(float(row_accuracy) - row_correct / row_total) > 1e-12
        ):
            raise ValueError("Pilot task evaluation category metric is invalid.")
        category_total += row_total
        category_correct += row_correct
    if category_total != total or category_correct != correct:
        raise ValueError("Pilot task evaluation categories do not reconcile.")
    for example in examples:
        losses = example.get("choice_losses") if isinstance(example, Mapping) else None
        if (
            not isinstance(example, Mapping)
            or not isinstance(example.get("id"), str)
            or not isinstance(example.get("category"), str)
            or type(example.get("answer_index")) is not int
            or type(example.get("prediction_index")) is not int
            or type(example.get("correct")) is not bool
            or not isinstance(losses, list)
            or not losses
            or any(not _finite_metric(loss) for loss in losses)
            or not 0 <= example["answer_index"] < len(losses)
            or not 0 <= example["prediction_index"] < len(losses)
            or example["correct"]
            != (example["answer_index"] == example["prediction_index"])
        ):
            raise ValueError("Pilot task evaluation outcome is invalid.")


def _validate_finite_tree(value: object) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Pilot evaluation contains a non-finite metric.")
    if isinstance(value, Mapping):
        for nested in value.values():
            _validate_finite_tree(nested)
    elif isinstance(value, list):
        for nested in value:
            _validate_finite_tree(nested)


def _validated_comparison_evidence(
    path: Path,
    payload: Mapping[str, Any],
    *,
    drive_dir: Path,
    checkpoint_root: Path,
    expected_config_sha256: str,
    expected_artifact_identity: Mapping[str, str],
) -> dict[str, dict[str, object]]:
    checkpoints = payload.get("checkpoints")
    if not isinstance(checkpoints, Mapping) or len(checkpoints) < 2:
        raise ValueError("Pilot comparison requires at least two checkpoints.")
    config = payload.get("config")
    if not isinstance(config, Mapping) or config.get("sha256") != expected_config_sha256:
        raise ValueError("Pilot comparison config fingerprint mismatch.")
    _validate_artifact_identity(payload, expected_artifact_identity)
    if not all(isinstance(payload.get(key), Mapping) for key in (
        "protocol", "validation", "consistency", "generations", "llm_judge"
    )):
        raise ValueError("Pilot checkpoint comparison evidence is incomplete.")
    labels = set(checkpoints)
    if set(payload["consistency"]) != labels or set(payload["generations"]) != labels:
        raise ValueError("Pilot comparison checkpoint metrics are incomplete.")
    result: dict[str, dict[str, object]] = {}
    for label, record in checkpoints.items():
        if not isinstance(label, str) or not isinstance(record, Mapping):
            raise ValueError("Pilot comparison checkpoint record is invalid.")
        checkpoint, binding = _validated_checkpoint_binding(
            record, reference_key="path", binding_key="binding",
            drive_dir=drive_dir, checkpoint_root=checkpoint_root,
            expected_stage="pilot",
        )
        evidence_value = record.get("evidence")
        if evidence_value != f"checkpoints/{label}.json":
            raise ValueError("Pilot comparison detailed-evidence path is not canonical.")
        detailed_path = require_managed_path(
            path.parent, path.parent / f"checkpoints/{label}.json",
            kind="file", allow_missing=False,
        )
        detailed = _load_json_object(detailed_path, "Pilot comparison checkpoint detail")
        _validate_artifact_identity(detailed, expected_artifact_identity)
        detailed_checkpoint, detailed_binding = _validated_checkpoint_binding(
            detailed, reference_key="checkpoint_path",
            binding_key="checkpoint_binding", drive_dir=drive_dir,
            checkpoint_root=checkpoint_root, expected_stage="pilot",
        )
        if (
            detailed.get("checkpoint_label") != label
            or detailed_checkpoint != checkpoint
            or detailed_binding != binding
            or not isinstance(detailed.get("validation"), list)
            or not detailed["validation"]
            or not isinstance(detailed.get("consistency_task"), Mapping)
            or not isinstance(detailed.get("generations"), list)
            or not detailed["generations"]
            or not isinstance(detailed.get("generation_summary"), Mapping)
        ):
            raise ValueError("Pilot comparison checkpoint detail is incomplete.")
        for validation_row in detailed["validation"]:
            if (
                not isinstance(validation_row, Mapping)
                or type(validation_row.get("seed")) is not int
                or not _finite_metric(validation_row.get("loss"))
                or not _finite_metric(validation_row.get("perplexity"))
            ):
                raise ValueError("Pilot comparison validation metric is invalid.")
        _validate_task_result(detailed["consistency_task"])
        _validate_finite_tree(detailed)
        result[label] = binding
    for label, summary in payload["consistency"].items():
        if (
            not isinstance(summary, Mapping)
            or type(summary.get("total")) is not int
            or summary["total"] < 1
            or type(summary.get("correct")) is not int
            or not 0 <= summary["correct"] <= summary["total"]
            or not _finite_metric(summary.get("accuracy"))
            or abs(float(summary["accuracy"]) - summary["correct"] / summary["total"])
            > 1e-12
            or not isinstance(payload["generations"].get(label), Mapping)
            or not payload["generations"][label]
        ):
            raise ValueError("Pilot comparison consistency or repetition metrics are invalid.")
    _validate_finite_tree(payload)
    return result


def _validated_scored_review(
    path: Path,
    payload: Mapping[str, Any],
    *,
    comparison_path: Path,
    checkpoints: Mapping[str, Mapping[str, object]],
    expected_artifact_identity: Mapping[str, str],
    drive_dir: Path,
    checkpoint_root: Path,
) -> None:
    _validate_artifact_identity(payload, expected_artifact_identity)
    judgments = payload.get("judgments")
    summary = payload.get("summary")
    bindings = payload.get("checkpoints")
    comparison = payload.get("comparison")
    if (
        payload.get("reviewer") not in {"llm", "human"}
        or type(payload.get("review_count")) is not int
        or payload["review_count"] < 1
        or not isinstance(judgments, list)
        or len(judgments) != payload["review_count"]
        or not isinstance(summary, Mapping)
        or not isinstance(summary.get("checkpoints"), Mapping)
        or set(summary["checkpoints"]) != set(checkpoints)
        or not isinstance(comparison, Mapping)
        or comparison.get("path") != "../../comparison_summary.json"
        or comparison.get("sha256") != sha256_file(comparison_path)
        or not isinstance(bindings, Mapping)
        or set(bindings) != set(checkpoints)
    ):
        raise ValueError("Pilot scored review is incomplete or unbound.")
    for label, expected_binding in checkpoints.items():
        binding = bindings[label]
        if not isinstance(binding, Mapping):
            raise ValueError("Pilot scored review checkpoint binding mismatch.")
        _, validated_binding = _validated_checkpoint_binding(
            {"path": binding.get("path"), "binding": binding},
            reference_key="path", binding_key="binding", drive_dir=drive_dir,
            checkpoint_root=checkpoint_root, expected_stage="pilot",
        )
        if validated_binding != dict(expected_binding):
            raise ValueError("Pilot scored review checkpoint binding mismatch.")
    seen_review_ids: set[str] = set()
    for judgment in judgments:
        review_id = judgment.get("review_id") if isinstance(judgment, Mapping) else None
        scores = (
            judgment.get("character_consistency"),
            judgment.get("object_location_consistency"),
            judgment.get("causal_coherence"),
            judgment.get("overall_consistency"),
        ) if isinstance(judgment, Mapping) else ()
        if (
            not isinstance(judgment, Mapping)
            or not isinstance(review_id, str)
            or not review_id
            or review_id in seen_review_ids
            or judgment.get("checkpoint_label") not in checkpoints
            or any(type(score) is not int or score not in {0, 1, 2} for score in scores)
            or not isinstance(judgment.get("flags"), list)
            or not isinstance(judgment.get("evidence"), str)
            or not judgment["evidence"]
            or not isinstance(judgment.get("reason"), str)
            or not judgment["reason"]
        ):
            raise ValueError("Pilot scored review judgment is invalid.")
        seen_review_ids.add(review_id)
    _validate_finite_tree(payload)


def _pilot_colab_evidence(
    *,
    drive_dir: Path,
    gate_root: Path,
    evaluation_root: Path,
    tokenizer_sha256: str,
    build_identity_sha256: str,
) -> dict[str, Any]:
    required = {
        "preflight": gate_root / "preflight.json",
        "smoke": gate_root / "smoke_resume_verified.json",
        "pilot": gate_root / "pilot_complete.json",
    }
    artifacts: dict[str, Any] = {}
    expected_config_sha256: str | None = None
    expected_artifact_identity: dict[str, str] | None = None
    stage_bindings: dict[str, dict[str, object]] = {}
    declared_pilot_bindings: list[dict[str, object]] = []
    checkpoint_root = evaluation_root.parent / "checkpoints"
    for gate, path in required.items():
        path = require_managed_path(
            drive_dir, path, kind="file", allow_missing=False
        )
        payload = _load_json_object(path, f"Pilot {gate} evidence")
        _validated_pilot_gate(
            payload,
            gate=gate,
            tokenizer_sha256=tokenizer_sha256,
            build_identity_sha256=build_identity_sha256,
        )
        artifacts[gate] = _file_fingerprint(path, managed_root=drive_dir)
        if gate == "preflight" and "gate" not in payload:
            checks = {str(check["name"]): check for check in payload["checks"]}
            operator_gate_root = (
                _operator_evidence_root(drive_dir, tokenizer_sha256)
                / "pilot/colab"
            )
            prebuilt_producer = gate_root == operator_gate_root
            config_path = (
                gate_root / "config.yaml"
                if prebuilt_producer
                else gate_root.parents[1] / "prepared/pilot/config.yaml"
            )
            expected_config_sha256 = sha256_text(
                config_to_yaml(load_config(config_path))
            )
            details = checks["config"].get("details")
            if (
                not isinstance(details, Mapping)
                or details.get("config_sha256") != expected_config_sha256
            ):
                raise ValueError("Pilot preflight config fingerprint mismatch.")
            tokenizer_details = checks["tokenizer"].get("details")
            if (
                not isinstance(tokenizer_details, Mapping)
                or tokenizer_details.get("tokenizer_sha256") != tokenizer_sha256
                or tokenizer_details.get("vocab_size") != REQUIRED_VOCAB_SIZE
            ):
                raise ValueError("Pilot preflight tokenizer fingerprint mismatch.")
            manifest_path = (
                drive_dir
                / "corpora"
                / "pilot"
                / tokenizer_sha256
                / "manifest.json"
                if prebuilt_producer
                else gate_root.parents[1] / "corpora/pilot/manifest.json"
            )
            manifest_payload = _load_json_object(
                manifest_path, "Pilot preflight corpus manifest"
            )
            manifest_details = checks["dataset_manifest"].get("details")
            if (
                not isinstance(manifest_details, Mapping)
                or manifest_details.get("manifest_sha256")
                != manifest_payload.get("manifest_sha256")
            ):
                raise ValueError("Pilot preflight manifest fingerprint mismatch.")
            manifest_identity = manifest_payload.get("manifest_sha256")
            if not isinstance(manifest_identity, str):
                raise ValueError("Pilot preflight manifest identity is missing.")
            expected_artifact_identity = {
                "config_sha256": expected_config_sha256,
                "tokenizer_sha256": tokenizer_sha256,
                "dataset_manifest_sha256": sha256_file(manifest_path),
                "dataset_manifest_identity_sha256": manifest_identity,
                "build_identity_sha256": build_identity_sha256,
            }
            shard_details = checks["shards"].get("details")
            if not isinstance(shard_details, Mapping):
                raise ValueError("Pilot preflight shard fingerprints are missing.")
            shard_root = (
                manifest_path.parent
                if prebuilt_producer
                else gate_root.parents[1] / "prepared/pilot/shards"
            )
            for split in ("pilot", "validation"):
                metadata = _load_json_object(
                    shard_root / f"{split}_metadata.json",
                    f"Pilot preflight {split} shard metadata",
                )
                rows = [
                    {
                        "path": shard["path"],
                        "byte_size": shard["byte_size"],
                        "num_tokens": shard["num_tokens"],
                        "sha256": shard["sha256"],
                    }
                    for shard in metadata["shards"]
                ]
                observed = shard_details.get(split)
                if (
                    not isinstance(observed, Mapping)
                    or observed.get("total_tokens") != metadata["total_tokens"]
                    or observed.get("metadata_sha256") != metadata["metadata_sha256"]
                    or observed.get("shard_files_sha256") != sha256_json(rows)
                ):
                    raise ValueError("Pilot preflight shard fingerprint mismatch.")
            artifacts["config"] = _file_fingerprint(
                config_path, managed_root=drive_dir
            )
        if gate in {"smoke", "pilot"}:
            if "gate" not in payload:
                if expected_artifact_identity is None:
                    raise ValueError("Pilot checkpoint evidence has no artifact identity.")
                _validate_artifact_identity(payload, expected_artifact_identity)
            checkpoint, binding = _validated_checkpoint_binding(
                payload, reference_key="checkpoint",
                binding_key="checkpoint_binding", drive_dir=drive_dir,
                checkpoint_root=checkpoint_root, expected_stage=gate,
            )
            stage_bindings[gate] = binding
            if gate == "pilot":
                raw_bindings = payload.get("checkpoint_bindings")
                if not isinstance(raw_bindings, list) or not raw_bindings:
                    raise ValueError("Pilot checkpoint snapshot set is missing.")
                for raw_binding in raw_bindings:
                    if not isinstance(raw_binding, Mapping):
                        raise ValueError("Pilot checkpoint snapshot set is invalid.")
                    _, validated = _validated_checkpoint_binding(
                        {"path": raw_binding.get("path"), "binding": raw_binding},
                        reference_key="path", binding_key="binding",
                        drive_dir=drive_dir, checkpoint_root=checkpoint_root,
                        expected_stage="pilot",
                    )
                    declared_pilot_bindings.append(validated)
                if (
                    len({sha256_json(row) for row in declared_pilot_bindings})
                    != len(declared_pilot_bindings)
                    or binding not in declared_pilot_bindings
                ):
                    raise ValueError("Pilot checkpoint snapshot set does not reconcile.")
            artifacts[f"{gate}_checkpoint"] = _file_fingerprint(
                checkpoint, managed_root=drive_dir
            )
    if (
        stage_bindings.get("smoke", {}).get("sha256")
        == stage_bindings.get("pilot", {}).get("sha256")
    ):
        raise ValueError("Smoke and pilot must use distinct immutable checkpoint snapshots.")
    evaluation_files = _bounded_json_files(
        evaluation_root, managed_root=drive_dir, label="Pilot evaluation evidence"
    )
    if not evaluation_files:
        raise ValueError("Pilot evaluation evidence is missing.")
    payloads = {
        path: _load_json_object(path, "Pilot evaluation evidence")
        for path in evaluation_files
    }
    explicit_path = evaluation_root / "review.json"
    if set(payloads) == {explicit_path} and "gate" in payloads[explicit_path]:
        _validated_pilot_gate(
            payloads[explicit_path], gate="evaluation",
            tokenizer_sha256=tokenizer_sha256,
            build_identity_sha256=build_identity_sha256,
        )
        _, evaluation_binding = _validated_checkpoint_binding(
            payloads[explicit_path], reference_key="checkpoint",
            binding_key="checkpoint_binding", drive_dir=drive_dir,
            checkpoint_root=checkpoint_root, expected_stage="pilot",
        )
        if evaluation_binding != stage_bindings.get("pilot"):
            raise ValueError("Pilot evaluation is not bound to the pilot snapshot.")
        evaluations = [_file_fingerprint(explicit_path, managed_root=drive_dir)]
    else:
        if expected_config_sha256 is None:
            raise ValueError("Pilot producer evaluation has no bound config fingerprint.")
        if expected_artifact_identity is None:
            raise ValueError("Pilot producer evaluation has no artifact identity.")
        base_paths = sorted(
            path for path in payloads
            if path.parent.parent == evaluation_root and path.name.endswith("_base.json")
        )
        if not base_paths:
            raise ValueError("Pilot loss evaluation evidence is missing.")
        allowed: set[Path] = set()
        checkpoints_by_prefix: dict[str, dict[str, object]] = {}
        evaluations = []
        session_root = base_paths[0].parent
        if any(path.parent != session_root for path in base_paths):
            raise ValueError("Pilot evaluation evidence spans multiple sessions.")
        for path in base_paths:
            payload = payloads[path]
            _validate_artifact_identity(payload, expected_artifact_identity)
            checkpoint, binding = _validated_checkpoint_binding(
                payload, reference_key="checkpoint",
                binding_key="checkpoint_binding", drive_dir=drive_dir,
                checkpoint_root=checkpoint_root, expected_stage="pilot",
            )
            if (
                payload.get("status") in {"fail", "failed", "error"}
                or
                not _finite_metric(payload.get("val_loss"))
                or not _finite_metric(payload.get("perplexity"))
                or float(payload["val_loss"]) <= 0
                or float(payload["perplexity"]) <= 0
                or not isinstance(payload.get("samples"), list)
                or not payload["samples"]
                or any(
                    not isinstance(sample, Mapping)
                    or not isinstance(sample.get("prompt"), str)
                    or not isinstance(sample.get("text"), str)
                    for sample in payload["samples"]
                )
            ):
                raise ValueError("Pilot loss evaluation metrics are invalid.")
            prefix = path.name.removesuffix("_base.json")
            task_path = path.with_name(f"{prefix}_open_telco.json")
            tasks_payload = payloads.get(task_path)
            tasks = tasks_payload.get("tasks") if isinstance(tasks_payload, Mapping) else None
            if not isinstance(tasks, list) or not tasks:
                raise ValueError("Pilot task evaluation lacks its checkpoint companion.")
            _validate_artifact_identity(tasks_payload, expected_artifact_identity)
            task_checkpoint, task_binding = _validated_checkpoint_binding(
                tasks_payload, reference_key="checkpoint",
                binding_key="checkpoint_binding", drive_dir=drive_dir,
                checkpoint_root=checkpoint_root, expected_stage="pilot",
            )
            if task_checkpoint != checkpoint or task_binding != binding:
                raise ValueError("Pilot task and loss checkpoint bindings differ.")
            for task in tasks:
                _validate_task_result(task)
            fingerprint = _file_fingerprint(checkpoint, managed_root=drive_dir)
            checkpoints_by_prefix[prefix] = binding
            for evidence_path in (path, task_path):
                evidence_fingerprint = _file_fingerprint(
                    evidence_path, managed_root=drive_dir
                )
                evidence_fingerprint["checkpoint"] = fingerprint
                evaluations.append(evidence_fingerprint)
                allowed.add(evidence_path)
        comparison_path = session_root / "checkpoint_comparison/comparison_summary.json"
        comparison_payload = payloads.get(comparison_path)
        if not isinstance(comparison_payload, Mapping):
            raise ValueError("Pilot checkpoint comparison evidence is missing.")
        comparison_checkpoints = _validated_comparison_evidence(
            comparison_path, comparison_payload, drive_dir=drive_dir,
            checkpoint_root=checkpoint_root,
            expected_config_sha256=expected_config_sha256,
            expected_artifact_identity=expected_artifact_identity,
        )
        if {
            sha256_json(binding) for binding in comparison_checkpoints.values()
        } != {
            sha256_json(binding) for binding in checkpoints_by_prefix.values()
        }:
            raise ValueError("Pilot comparison checkpoint set does not match evaluations.")
        if sha256_json(stage_bindings["pilot"]) not in {
            sha256_json(binding) for binding in checkpoints_by_prefix.values()
        }:
            raise ValueError("Pilot evaluation does not include the selected pilot snapshot.")
        if {
            sha256_json(binding) for binding in declared_pilot_bindings
        } != {
            sha256_json(binding) for binding in checkpoints_by_prefix.values()
        }:
            raise ValueError("Pilot evaluation checkpoint set differs from pilot completion evidence.")
        allowed.add(comparison_path)
        for label in comparison_checkpoints:
            allowed.add(comparison_path.parent / f"checkpoints/{label}.json")
        review_key_path = comparison_path.parent / "llm_judge/review_key.json"
        review_key = payloads.get(review_key_path)
        if not isinstance(review_key, Mapping) or not review_key or any(
            not isinstance(row, Mapping)
            or row.get("checkpoint_label") not in comparison_checkpoints
            for row in review_key.values()
        ):
            raise ValueError("Pilot comparison review key is invalid.")
        allowed.add(review_key_path)
        scored_paths = [
            path for path in payloads
            if path.parent == comparison_path.parent / "llm_judge/results"
            and re.fullmatch(r"scored_(llm|human)\.json", path.name)
        ]
        if not scored_paths:
            raise ValueError("Pilot scored review evidence is missing.")
        for scored_path in scored_paths:
            _validated_scored_review(
                scored_path, payloads[scored_path],
                comparison_path=comparison_path,
                checkpoints=comparison_checkpoints,
                expected_artifact_identity=expected_artifact_identity,
                drive_dir=drive_dir,
                checkpoint_root=checkpoint_root,
            )
            allowed.add(scored_path)
        if set(payloads) != allowed:
            raise ValueError("Pilot evaluation contains an unknown JSON artifact role.")
        evaluations.extend(
            _file_fingerprint(path, managed_root=drive_dir)
            for path in sorted(allowed - set(base_paths) - {
                path.with_name(
                    f"{path.name.removesuffix('_base.json')}_open_telco.json"
                ) for path in base_paths
            })
        )
    artifacts["evaluation"] = {
        "files": evaluations,
        "fingerprint_sha256": sha256_json(evaluations),
    }
    return artifacts


def _pilot_reuse_evidence(
    drive_dir: Path, tokenizer_sha256: str
) -> dict[str, Any]:
    tokenizer_dir, provenance_path, provenance = _canonical_pilot_provenance(drive_dir)
    recipe_root = provenance_path.parents[2]
    corpus_path = recipe_root / "corpora/pilot/manifest.json"
    shards_root = recipe_root / "prepared/pilot/shards"
    evidence_root = recipe_root / "evidence/pilot"
    runs_root = recipe_root / "runs/pilot"
    manifest, build_identity_sha256 = _validated_pilot_manifest(
        corpus_path,
        managed_root=drive_dir,
        tokenizer_sha256=tokenizer_sha256,
    )
    quota_audit_path = evidence_root / "quota_audit.json"
    _validated_pilot_quota_audit(
        quota_audit_path,
        managed_root=drive_dir,
        manifest=manifest,
        tokenizer_sha256=tokenizer_sha256,
        build_identity_sha256=build_identity_sha256,
        manifest_file_sha256=sha256_file(corpus_path),
    )
    if provenance.get("tokenizer_sha256") != tokenizer_sha256:
        raise ValueError("Preserved pilot tokenizer fingerprint mismatch.")
    tokenizer_metadata = load_tokenizer_metadata(tokenizer_dir)
    special_token_ids = tokenizer_metadata.get("special_token_ids")
    eos_id = (
        special_token_ids.get("<|eos|>")
        if isinstance(special_token_ids, Mapping)
        else None
    )
    if (
        type(eos_id) is not int
        or not 0 <= eos_id < REQUIRED_VOCAB_SIZE
    ):
        raise ValueError("Preserved pilot tokenizer has no valid frozen EOS ID.")
    shard_fingerprint = _fingerprint_tree(
        shards_root, managed_root=drive_dir, label="Pilot shards"
    )
    metadata_files = sorted(shards_root.glob("*_metadata.json"))
    if {path.name for path in metadata_files} != {
        "pilot_metadata.json", "validation_metadata.json"
    }:
        raise ValueError("Pilot shards require complete train and validation metadata.")
    referenced_shards: set[Path] = set()
    split_totals: dict[str, int] = {}
    split_documents: dict[str, int] = {}
    for metadata_path in metadata_files:
        metadata = _load_json_object(metadata_path, "Pilot shard metadata")
        stored_metadata = metadata.get("metadata_sha256")
        unsigned_metadata = dict(metadata)
        unsigned_metadata.pop("metadata_sha256", None)
        if (
            metadata.get("tokenizer_sha256") != tokenizer_sha256
            or stored_metadata != sha256_json(unsigned_metadata)
            or (
                "build_identity_sha256" in metadata
                and metadata.get("build_identity_sha256") != build_identity_sha256
            )
        ):
            raise ValueError("Pilot shard metadata identity mismatch.")
        expected_split = metadata_path.name.removesuffix("_metadata.json")
        shards = metadata.get("shards")
        if (
            metadata.get("split") != expected_split
            or metadata.get("dtype") != PILOT_SHARD_DTYPE
            or metadata.get("append_eos") is not True
            or not isinstance(shards, list)
            or not shards
        ):
            raise ValueError("Pilot shard metadata split or shard list is incomplete.")
        dtype = np.dtype(DTYPES[PILOT_SHARD_DTYPE])
        seen_names: set[str] = set()
        token_sum = 0
        eos_sum = 0
        for shard_index, shard in enumerate(shards):
            if not isinstance(shard, Mapping):
                raise ValueError("Pilot shard metadata entry is invalid.")
            relative_value = shard.get("path")
            if not isinstance(relative_value, str):
                raise ValueError("Pilot shard metadata entry is invalid.")
            relative = PurePosixPath(relative_value)
            if (
                not relative_value
                or "\\" in relative_value
                or relative.is_absolute()
                or ".." in relative.parts
                or str(relative) != relative_value
                or len(relative.parts) != 1
                or relative.suffix != ".bin"
                or relative_value in seen_names
            ):
                raise ValueError("Pilot shard metadata paths must be unique safe filenames.")
            seen_names.add(relative_value)
            num_tokens = shard.get("num_tokens")
            byte_size = shard.get("byte_size")
            if (
                type(num_tokens) is not int
                or not 0 < num_tokens <= 2**63 - 1
                or type(byte_size) is not int
                or not 0 < byte_size <= 2**63 - 1
                or shard.get("index") != shard_index
                or num_tokens > (2**63 - 1) // dtype.itemsize
                or byte_size != num_tokens * dtype.itemsize
            ):
                raise ValueError("Pilot shard token and byte counts are invalid.")
            if token_sum > (2**63 - 1) - num_tokens:
                raise ValueError("Pilot shard token total exceeds the supported range.")
            token_sum += num_tokens
            shard_path = metadata_path.parent / Path(*relative.parts)
            fingerprint = _file_fingerprint(shard_path, managed_root=drive_dir)
            referenced_shards.add(shard_path.resolve())
            if (
                byte_size != fingerprint["size"]
                or shard.get("sha256") != fingerprint["sha256"]
            ):
                raise ValueError("Pilot shard metadata file fingerprint mismatch.")
            values = np.memmap(shard_path, mode="r", dtype=dtype)
            if values.size != num_tokens:
                raise ValueError("Pilot shard token count differs from its bytes.")
            for offset in range(0, int(values.size), 1_048_576):
                block = values[offset : offset + 1_048_576]
                if block.size and int(block.max()) >= REQUIRED_VOCAB_SIZE:
                    raise ValueError(
                        "Pilot shard token IDs exceed the expected vocabulary."
                    )
                eos_sum += int(np.count_nonzero(block == eos_id))
        total_tokens = metadata.get("total_tokens")
        total_documents = metadata.get("total_documents")
        if (
            type(total_tokens) is not int
            or total_tokens != token_sum
            or type(total_documents) is not int
            or total_documents < 1
            or total_documents != eos_sum
        ):
            raise ValueError("Pilot shard metadata totals do not reconcile.")
        if expected_split == "validation" and total_tokens < 1:
            raise ValueError("Pilot validation shard metadata is empty.")
        split_totals[expected_split] = total_tokens
        split_documents[expected_split] = total_documents
    actual_shards = {
        path.resolve() for path in shards_root.glob("*.bin")
        if path.is_file() and not path.is_symlink()
    }
    if actual_shards != referenced_shards:
        raise ValueError("Pilot split metadata does not enumerate every shard exactly.")
    stages = manifest.get("stages")
    pilot_stage = stages.get("pilot") if isinstance(stages, Mapping) else None
    validation = manifest.get("validation")
    if (
        not isinstance(pilot_stage, Mapping)
        or pilot_stage.get("requested_tokens") != PILOT_TOKENS
        or type(pilot_stage.get("quota_tokens")) is not int
        or pilot_stage["quota_tokens"] < PILOT_TOKENS
        or type(pilot_stage.get("documents")) is not int
        or pilot_stage["documents"] != split_documents["pilot"]
        or pilot_stage["quota_tokens"] > (2**63 - 1) - pilot_stage["documents"]
        or split_totals["pilot"]
        != pilot_stage["quota_tokens"] + pilot_stage["documents"]
        or not isinstance(validation, Mapping)
        or type(validation.get("quota_tokens")) is not int
        or type(validation.get("documents")) is not int
        or validation["documents"] != split_documents["validation"]
        or validation["quota_tokens"] > (2**63 - 1) - validation["documents"]
        or split_totals["validation"]
        != validation["quota_tokens"] + validation["documents"]
    ):
        raise ValueError("Pilot manifest quotas and split metadata do not reconcile.")
    gates = _pilot_colab_evidence(
        drive_dir=drive_dir,
        gate_root=evidence_root,
        evaluation_root=runs_root / "evaluation",
        tokenizer_sha256=tokenizer_sha256,
        build_identity_sha256=build_identity_sha256,
    )
    artifacts = {
        label: {
            "path": path.relative_to(drive_dir).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for label, path in {
            "tokenizer": tokenizer_dir / "tokenizer.json",
            "tokenizer_provenance": provenance_path,
            "corpus": corpus_path,
            "quota_audit": quota_audit_path,
        }.items()
    }
    artifacts["shards"] = shard_fingerprint
    artifacts.update(gates)
    artifacts["build_identity_sha256"] = build_identity_sha256
    return artifacts


def _current_pilot_refresh(
    report: Mapping[str, Any],
    *,
    drive_dir: Path,
    tokenizer_sha256: str,
    winner: str,
    selection: Mapping[str, Any],
    comparison: Mapping[str, Any],
    candidate_config: TokenizerCandidateConfig,
) -> dict[str, Any]:
    expected_common = {
        "version": 1,
        "winner": winner,
        "selected_tokenizer_sha256": tokenizer_sha256,
        "selection_file_sha256": sha256_file(drive_dir / "tokenizer_selection.json"),
        "comparison_file_sha256": sha256_file(drive_dir / "comparison.json"),
        "selection_comparison_sha256": selection["comparison_sha256"],
        "comparison_sha256": comparison["comparison_sha256"],
    }
    if any(report.get(key) != value for key, value in expected_common.items()):
        raise ValueError("Pilot refresh is not bound to the current selected workflow.")
    current = dict(report)
    if winner == candidate_config.baseline_label:
        if report.get("action") != "reuse":
            raise ValueError("Pilot refresh action conflicts with the selected tokenizer.")
        artifacts = _pilot_reuse_evidence(drive_dir, tokenizer_sha256)
        if report.get("artifacts") != artifacts:
            raise ValueError("Pilot refresh recorded artifact fingerprints changed.")
        current["refreshed_pilot_gates_passed"] = True
        current["pending_colab_gates"] = []
        return current
    if report.get("action") != "rebuild":
        raise ValueError("Pilot refresh action conflicts with the selected tokenizer.")
    build_identity = report.get("build_identity_sha256")
    if not isinstance(build_identity, str) or SHA256_PATTERN.fullmatch(build_identity) is None:
        raise ValueError("Pilot refresh build identity is invalid.")
    destination = drive_dir / "corpora" / "pilot" / tokenizer_sha256
    _validated_pilot_manifest(
        destination / "manifest.json",
        managed_root=drive_dir,
        tokenizer_sha256=tokenizer_sha256,
        expected_build_identity=build_identity,
    )
    corpus_tree = _fingerprint_tree(
        destination, managed_root=drive_dir, label="Refreshed pilot corpus"
    )
    if report.get("artifacts") != {"corpus_tree": corpus_tree}:
        raise ValueError("Pilot refresh recorded artifact fingerprints changed.")
    try:
        current_gates = _pilot_colab_evidence(
            drive_dir=drive_dir,
            gate_root=_operator_evidence_root(drive_dir, tokenizer_sha256)
            / "pilot/colab",
            evaluation_root=_operator_evidence_root(drive_dir, tokenizer_sha256)
            / "pilot/colab/evaluation",
            tokenizer_sha256=tokenizer_sha256,
            build_identity_sha256=build_identity,
        )
    except (FileNotFoundError, OSError, ValueError) as error:
        current["refreshed_pilot_gates_passed"] = False
        current["pending_colab_gates"] = ["smoke", "pilot", "evaluation"]
        current["current_gate_reason"] = str(error)
        return current
    current["refreshed_pilot_gates_passed"] = True
    current["pending_colab_gates"] = []
    current["current_colab_artifacts"] = current_gates
    return current


def _pilot_refresh_stage(
    *,
    work_dir: Path,
    drive_dir: Path,
    registry: Any,
    mixture: Mapping[str, Any],
    candidate_config: TokenizerCandidateConfig,
    model_config: Mapping[str, Any],
) -> dict[str, Any]:
    winner, tokenizer_dir, tokenizer_sha256, selection, comparison = (
        _selected_tokenizer_evidence(
            drive_dir=drive_dir,
            work_dir=work_dir,
            registry=registry,
            mixture=mixture,
            candidate_config=candidate_config,
            model_config=model_config,
        )
    )
    report_path = _pilot_refresh_path(drive_dir, tokenizer_sha256)
    require_managed_path(drive_dir, report_path, kind="file")
    if report_path.exists() or report_path.is_symlink():
        report = _read_hashed_evidence(
            report_path,
            hash_field="pilot_refresh_sha256",
            managed_root=drive_dir,
            label="Pilot refresh",
        )
        return _current_pilot_refresh(
            report,
            drive_dir=drive_dir,
            tokenizer_sha256=tokenizer_sha256,
            winner=winner,
            selection=selection,
            comparison=comparison,
            candidate_config=candidate_config,
        )
    common = {
        "version": 1,
        "winner": winner,
        "selected_tokenizer_sha256": tokenizer_sha256,
        "selection_file_sha256": sha256_file(drive_dir / "tokenizer_selection.json"),
        "comparison_file_sha256": sha256_file(drive_dir / "comparison.json"),
        "selection_comparison_sha256": selection["comparison_sha256"],
        "comparison_sha256": comparison["comparison_sha256"],
    }
    if winner == candidate_config.baseline_label:
        evidence = _pilot_reuse_evidence(drive_dir, tokenizer_sha256)
        payload = {
            **common,
            "action": "reuse",
            "status": "ready_for_colab",
            "refreshed_pilot_gates_passed": True,
            "pending_colab_gates": [],
            "artifacts": evidence,
        }
    else:
        request = _corpus_request(
            kind="pilot",
            work_dir=work_dir,
            drive_dir=drive_dir,
            registry=registry,
            mixture=mixture,
            candidate_config=candidate_config,
            model_config=model_config,
            tokenizer_dir=tokenizer_dir,
            tokenizer_sha256=tokenizer_sha256,
        )
        provider = _provider_preflight(request)
        expected_identity = _expected_build_identity(request)
        result = build_local_corpus(request)
        if (
            result.status != "complete"
            or result.accepted_quota_tokens < 20_000_000
            or not isinstance(result.manifest, Mapping)
            or result.manifest.get("complete") is not True
        ):
            raise ValueError("Refreshed pilot corpus did not complete its 20M quota.")
        if result.build_identity_sha256 != expected_identity.content_sha256:
            raise ValueError("Refreshed pilot returned a changed corpus build identity.")
        destination = Path(request.destination_root)
        _validated_pilot_manifest(
            destination / "manifest.json",
            managed_root=drive_dir,
            tokenizer_sha256=tokenizer_sha256,
            expected_build_identity=result.build_identity_sha256,
        )
        corpus_tree = _fingerprint_tree(
            destination, managed_root=drive_dir, label="Refreshed pilot corpus"
        )
        payload = {
            **common,
            "action": "rebuild",
            "status": "ready_for_colab",
            "refreshed_pilot_gates_passed": False,
            "pending_colab_gates": ["smoke", "pilot", "evaluation"],
            "provider_preflight": provider,
            "build_identity_sha256": result.build_identity_sha256,
            "actual_committed_quota_tokens": result.accepted_quota_tokens,
            "artifacts": {"corpus_tree": corpus_tree},
            "destination_namespace": Path(request.destination_root)
            .relative_to(drive_dir)
            .as_posix(),
        }
    return _write_hashed_evidence(
        report_path,
        payload,
        hash_field="pilot_refresh_sha256",
        managed_root=drive_dir,
    )


def _progress_payload(local_root: Path) -> dict[str, Any]:
    path = local_root / "progress.json"
    if not path.is_file() or path.is_symlink():
        return {}
    require_managed_path(local_root, path, kind="file", allow_missing=False)
    return _load_json_object(path, "Corpus progress")


def _full_calibration_stage(
    args: argparse.Namespace,
    *,
    work_dir: Path,
    drive_dir: Path,
    registry: Any,
    mixture: Mapping[str, Any],
    candidate_config: TokenizerCandidateConfig,
    model_config: Mapping[str, Any],
) -> dict[str, Any]:
    if args.stop_after_quota_tokens != CALIBRATION_TARGET_TOKENS:
        raise ValueError("full_calibration requires the canonical 100M stop target.")
    _, tokenizer_dir, tokenizer_sha256, _, _ = _selected_tokenizer_evidence(
        drive_dir=drive_dir,
        work_dir=work_dir,
        registry=registry,
        mixture=mixture,
        candidate_config=candidate_config,
        model_config=model_config,
    )
    request = _corpus_request(
        kind="full",
        work_dir=work_dir,
        drive_dir=drive_dir,
        registry=registry,
        mixture=mixture,
        candidate_config=candidate_config,
        model_config=model_config,
        tokenizer_dir=tokenizer_dir,
        tokenizer_sha256=tokenizer_sha256,
    )
    expected_identity = _expected_build_identity(request)
    provider = _provider_preflight(request)
    result = build_local_corpus(
        request, stop_after_quota_tokens=CALIBRATION_TARGET_TOKENS
    )
    if (
        result.status != "calibration_complete"
        or result.accepted_quota_tokens < CALIBRATION_TARGET_TOKENS
    ):
        raise ValueError("Calibration stopped before 100M committed quota tokens.")
    if result.build_identity_sha256 != expected_identity.content_sha256:
        raise ValueError("Calibration returned a changed corpus build identity.")
    destination_root = Path(request.destination_root)
    core_report, core_binding = _validated_core_calibration_report(
        destination_root / "calibration_report.json",
        managed_root=destination_root,
        expected_build_identity=result.build_identity_sha256,
    )
    if core_report["accepted_quota_tokens"] != result.accepted_quota_tokens:
        raise ValueError(
            "Committed calibration report token count does not match the builder result."
        )
    report_path = _calibration_operator_path(drive_dir, tokenizer_sha256)
    if report_path.exists() or report_path.is_symlink():
        existing = _read_hashed_evidence(
            report_path,
            hash_field="operator_report_sha256",
            managed_root=drive_dir,
            label="Calibration operator report",
        )
        if existing.get("build_identity_sha256") != result.build_identity_sha256:
            raise ValueError("Calibration operator report build identity mismatch.")
        _validated_calibration_report(
            existing,
            expected_build_identity=result.build_identity_sha256,
            core_report_path=destination_root / "calibration_report.json",
            core_managed_root=destination_root,
        )
        return existing
    metrics = core_report["metrics"]
    throughput = core_report["throughput"]
    source_network = metrics["source_network"]
    encode = metrics["encode"]
    contamination = metrics["contamination"]
    publication = metrics["publication"]
    rolling_rate = throughput["rolling_overall_tokens_per_second"]
    payload = {
        "version": 2,
        "status": "calibration_complete",
        "build_identity_sha256": result.build_identity_sha256,
        "selected_tokenizer_sha256": tokenizer_sha256,
        "actual_committed_quota_tokens": result.accepted_quota_tokens,
        "wall_time_seconds": metrics["wall_time_seconds"],
        "process_cpu_time_seconds": metrics["process_cpu_time_seconds"],
        "peak_rss_bytes": metrics["peak_rss_bytes"],
        "source_network_wait_seconds": source_network["wall_time_seconds"],
        "encode_tokens_per_second": throughput["encode_tokens_per_second"],
        "contamination_documents_per_second": throughput[
            "contamination_documents_per_second"
        ],
        "publication_bytes_per_second": throughput[
            "publication_bytes_per_second"
        ],
        "mean_overall_tokens_per_second": throughput[
            "mean_overall_tokens_per_second"
        ],
        "rolling_overall_tokens_per_second": rolling_rate,
        "projected_12b_wall_time_seconds": FULL_TARGET_TOKENS / rolling_rate,
        "measurement_methods": {
            "source_network_wait": source_network["method"],
            "encode": encode["method"],
            "contamination": contamination["method"],
            "publication": publication["method"],
        },
        "core_calibration_report": core_binding,
        "drive_verification_state": "verified",
        "unrecovered_storage_pressure": False,
        "provider_preflight": provider,
        "destination_namespace": Path(request.destination_root)
        .relative_to(drive_dir)
        .as_posix(),
    }
    return _write_hashed_evidence(
        report_path,
        payload,
        hash_field="operator_report_sha256",
        managed_root=drive_dir,
    )


def _strict_integer(value: Any, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} is invalid.")
    return value


def _strict_nonnegative_number(value: Any, *, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} is invalid.")
    try:
        number = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{label} is invalid.") from error
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} is invalid.")
    return number


def _strict_positive_number(value: Any, *, label: str) -> float:
    number = _strict_nonnegative_number(value, label=label)
    if number <= 0:
        raise ValueError(f"{label} must be positive.")
    return number


def _strict_nonnegative_integer(value: Any, *, label: str) -> int:
    number = _strict_integer(value, label=label)
    if number < 0 or number > 2**63 - 1:
        raise ValueError(f"{label} is invalid.")
    return number


def _strict_positive_integer(value: Any, *, label: str) -> int:
    number = _strict_nonnegative_integer(value, label=label)
    if number < 1:
        raise ValueError(f"{label} must be positive.")
    return number


def _same_number(actual: Any, expected: float, *, label: str) -> None:
    number = _strict_nonnegative_number(actual, label=label)
    if not math.isclose(number, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"{label} does not match committed calibration metrics.")


def _validated_core_calibration_report(
    path: Path,
    *,
    managed_root: Path,
    expected_build_identity: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        report = _read_hashed_evidence(
            path,
            hash_field="calibration_report_sha256",
            managed_root=managed_root,
            label="Committed core calibration report",
        )
    except (FileNotFoundError, OSError, ValueError) as error:
        raise ValueError(
            f"Committed core calibration report is missing or invalid: {error}"
        ) from error
    committed = _strict_nonnegative_integer(
        report.get("accepted_quota_tokens"),
        label="Committed core calibration report accepted tokens",
    )
    committed_units = _strict_nonnegative_integer(
        report.get("committed_units"),
        label="Committed core calibration report units",
    )
    if (
        report.get("version") != 2
        or report.get("status") != "calibration_complete"
        or committed < CALIBRATION_TARGET_TOKENS
        or committed_units < 1
    ):
        raise ValueError(
            "Committed core calibration report must be complete version 2 evidence "
            "for at least 100M tokens."
        )
    if report.get("build_identity_sha256") != expected_build_identity:
        raise ValueError("Committed core calibration report build identity mismatch.")

    metrics = report.get("metrics")
    throughput = report.get("throughput")
    if (
        not isinstance(metrics, Mapping)
        or metrics.get("version") != 1
        or not isinstance(throughput, Mapping)
    ):
        raise ValueError("Committed core calibration report metrics schema is invalid.")
    wall = _strict_positive_number(
        metrics.get("wall_time_seconds"), label="Calibration wall time"
    )
    _strict_nonnegative_number(
        metrics.get("process_cpu_time_seconds"), label="Calibration process CPU time"
    )
    _strict_nonnegative_integer(
        metrics.get("peak_rss_bytes"), label="Calibration peak RSS"
    )
    _same_number(report.get("elapsed_seconds"), wall, label="Calibration elapsed time")
    if report.get("peak_rss_bytes") != metrics.get("peak_rss_bytes"):
        raise ValueError("Calibration peak RSS does not match committed metrics.")

    phase_schemas = {
        "source_network": (
            "provider_load_and_next_wall_time",
            ("operations", "rows"),
        ),
        "encode": (
            "tokenizer_encode_batch_wall_time",
            ("batches", "documents", "tokens"),
        ),
        "contamination": (
            "quality_filter_accept_wall_time",
            ("documents",),
        ),
        "publication": (
            "publisher_publish_wall_time",
            ("artifacts", "bytes"),
        ),
    }
    phases: dict[str, Mapping[str, Any]] = {}
    for phase, (method, counters) in phase_schemas.items():
        evidence = metrics.get(phase)
        if not isinstance(evidence, Mapping) or evidence.get("method") != method:
            raise ValueError(f"Calibration {phase} measurement schema is invalid.")
        _strict_positive_number(
            evidence.get("wall_time_seconds"), label=f"Calibration {phase} wall time"
        )
        for counter in counters:
            _strict_nonnegative_integer(
                evidence.get(counter), label=f"Calibration {phase} {counter}"
            )
        phases[phase] = evidence

    source_network = phases["source_network"]
    encode = phases["encode"]
    contamination = phases["contamination"]
    publication = phases["publication"]
    for phase, evidence, counters in (
        ("source_network", source_network, ("operations", "rows")),
        ("encode", encode, ("batches", "documents", "tokens")),
        ("contamination", contamination, ("documents",)),
        ("publication", publication, ("artifacts", "bytes")),
    ):
        for counter in counters:
            _strict_positive_integer(
                evidence[counter], label=f"Calibration {phase} {counter}"
            )
    if encode["tokens"] < committed:
        raise ValueError("Calibration encode token count is below committed tokens.")
    expected_rates = {
        "encode_tokens_per_second": float(encode["tokens"])
        / float(encode["wall_time_seconds"]),
        "contamination_documents_per_second": float(contamination["documents"])
        / float(contamination["wall_time_seconds"]),
        "publication_bytes_per_second": float(publication["bytes"])
        / float(publication["wall_time_seconds"]),
        "mean_overall_tokens_per_second": committed / wall,
    }
    for field, expected in expected_rates.items():
        _same_number(throughput.get(field), expected, label=f"Calibration {field}")
    _strict_positive_number(
        throughput.get("rolling_overall_tokens_per_second"),
        label="Calibration rolling throughput",
    )
    resolved = require_managed_path(
        managed_root, path, kind="file", allow_missing=False
    )
    binding = {
        "path": "calibration_report.json",
        "size": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
        "calibration_report_sha256": report["calibration_report_sha256"],
    }
    return report, binding


def _validated_calibration_report(
    report: Mapping[str, Any],
    *,
    expected_build_identity: str,
    core_report_path: Path,
    core_managed_root: Path,
) -> tuple[int, float, bool]:
    stored = report.get("operator_report_sha256")
    unsigned = dict(report)
    unsigned.pop("operator_report_sha256", None)
    if stored != sha256_json(unsigned):
        raise ValueError("Calibration operator report checksum mismatch.")
    committed = _strict_integer(
        report.get("actual_committed_quota_tokens"),
        label="Calibration report committed tokens",
    )
    if (
        report.get("version") != 2
        or report.get("status") != "calibration_complete"
        or committed < CALIBRATION_TARGET_TOKENS
    ):
        raise ValueError("Calibration report does not prove 100M committed tokens.")
    if report.get("build_identity_sha256") != expected_build_identity:
        raise ValueError("Calibration report build identity does not match the full build.")
    if report.get("drive_verification_state") != "verified":
        raise ValueError("Calibration report does not prove Drive verification.")
    core_report, current_binding = _validated_core_calibration_report(
        core_report_path,
        managed_root=core_managed_root,
        expected_build_identity=expected_build_identity,
    )
    if report.get("core_calibration_report") != current_binding:
        raise ValueError("Calibration operator report core binding mismatch.")
    if core_report["accepted_quota_tokens"] != committed:
        raise ValueError("Calibration operator and core committed tokens mismatch.")
    metrics = core_report["metrics"]
    throughput = core_report["throughput"]
    expected_methods = {
        "source_network_wait": metrics["source_network"]["method"],
        "encode": metrics["encode"]["method"],
        "contamination": metrics["contamination"]["method"],
        "publication": metrics["publication"]["method"],
    }
    if report.get("measurement_methods") != expected_methods:
        raise ValueError("Calibration operator measurement methods are invalid.")
    copied_metrics = {
        "wall_time_seconds": metrics["wall_time_seconds"],
        "process_cpu_time_seconds": metrics["process_cpu_time_seconds"],
        "peak_rss_bytes": metrics["peak_rss_bytes"],
        "source_network_wait_seconds": metrics["source_network"][
            "wall_time_seconds"
        ],
        "encode_tokens_per_second": throughput["encode_tokens_per_second"],
        "contamination_documents_per_second": throughput[
            "contamination_documents_per_second"
        ],
        "publication_bytes_per_second": throughput[
            "publication_bytes_per_second"
        ],
        "mean_overall_tokens_per_second": throughput[
            "mean_overall_tokens_per_second"
        ],
        "rolling_overall_tokens_per_second": throughput[
            "rolling_overall_tokens_per_second"
        ],
    }
    for field, expected in copied_metrics.items():
        _same_number(report.get(field), float(expected), label=f"Operator {field}")
    projected = _strict_positive_number(
        report.get("projected_12b_wall_time_seconds"),
        label="Calibration report projection",
    )
    expected_projection = FULL_TARGET_TOKENS / float(
        throughput["rolling_overall_tokens_per_second"]
    )
    if not math.isclose(
        projected, expected_projection, rel_tol=1e-12, abs_tol=1e-12
    ):
        raise ValueError("Calibration report projection does not match core metrics.")
    storage_pressure = report.get("unrecovered_storage_pressure")
    if not isinstance(storage_pressure, bool):
        raise ValueError("Calibration report storage-pressure state is invalid.")
    return committed, projected, storage_pressure


def _require_accepted_calibration(
    report: Mapping[str, Any],
    *,
    expected_build_identity: str,
    core_report_path: Path,
    core_managed_root: Path,
    accept_calibration: bool,
    override_guard: bool,
    override_reason: str,
) -> dict[str, Any]:
    _, projected, storage_pressure = _validated_calibration_report(
        report,
        expected_build_identity=expected_build_identity,
        core_report_path=core_report_path,
        core_managed_root=core_managed_root,
    )
    stored = report["operator_report_sha256"]
    if not accept_calibration:
        raise ValueError("full_resume requires --accept-calibration.")
    over_time = projected > CALIBRATION_MAX_WALL_SECONDS
    guarded = over_time or storage_pressure
    reason = override_reason.strip()
    if override_guard and not reason:
        raise ValueError("--override-calibration-guard requires --override-reason.")
    if guarded and not override_guard:
        if storage_pressure:
            raise ValueError(
                "Calibration records unrecovered storage pressure; use an explicit "
                "reasoned override only after review."
            )
        raise ValueError(
            "Projected full preparation exceeds 48 hours; use an explicit reasoned "
            "override only after review."
        )
    return {
        "version": 1,
        "build_identity_sha256": expected_build_identity,
        "calibration_operator_report_sha256": stored,
        "accepted_calibration": True,
        "guard_overridden": bool(guarded and override_guard),
        "override_reason": reason if override_guard else "",
    }


def _expected_build_identity(request: LocalCorpusRequest):
    tokenizer_sha, selection_sha, comparison_sha, operational = (
        _local_selected_tokenizer_sha(request)
    )
    return _local_corpus_identity(
        request,
        tokenizer_sha,
        selection_sha,
        comparison_sha,
        operational,
    )


def _full_resume_stage(
    args: argparse.Namespace,
    *,
    work_dir: Path,
    drive_dir: Path,
    registry: Any,
    mixture: Mapping[str, Any],
    candidate_config: TokenizerCandidateConfig,
    model_config: Mapping[str, Any],
) -> dict[str, Any]:
    _, tokenizer_dir, tokenizer_sha256, _, _ = _selected_tokenizer_evidence(
        drive_dir=drive_dir,
        work_dir=work_dir,
        registry=registry,
        mixture=mixture,
        candidate_config=candidate_config,
        model_config=model_config,
    )
    request = _corpus_request(
        kind="full",
        work_dir=work_dir,
        drive_dir=drive_dir,
        registry=registry,
        mixture=mixture,
        candidate_config=candidate_config,
        model_config=model_config,
        tokenizer_dir=tokenizer_dir,
        tokenizer_sha256=tokenizer_sha256,
    )
    identity = _expected_build_identity(request)
    report = _read_hashed_evidence(
        _calibration_operator_path(drive_dir, tokenizer_sha256),
        hash_field="operator_report_sha256",
        managed_root=drive_dir,
        label="Calibration operator report",
    )
    authorization = _require_accepted_calibration(
        report,
        expected_build_identity=identity.content_sha256,
        core_report_path=Path(request.destination_root) / "calibration_report.json",
        core_managed_root=Path(request.destination_root),
        accept_calibration=args.accept_calibration,
        override_guard=args.override_calibration_guard,
        override_reason=args.override_reason,
    )
    provider = _provider_preflight(request)
    operator_path = _resume_operator_path(drive_dir, tokenizer_sha256)
    operator_payload = {
        **authorization,
        "operator_timestamp": datetime.now(UTC).isoformat(),
        "provider_preflight": provider,
    }
    if operator_path.exists() or operator_path.is_symlink():
        persisted_authorization = _read_hashed_evidence(
            operator_path,
            hash_field="resume_operator_evidence_sha256",
            managed_root=drive_dir,
            label="Resume operator evidence",
        )
        for field in (
            "build_identity_sha256",
            "calibration_operator_report_sha256",
            "accepted_calibration",
            "guard_overridden",
            "override_reason",
        ):
            if persisted_authorization.get(field) != operator_payload.get(field):
                raise ValueError("Resume operator evidence conflicts with this authorization.")
    else:
        persisted_authorization = _write_hashed_evidence(
            operator_path,
            operator_payload,
            hash_field="resume_operator_evidence_sha256",
            managed_root=drive_dir,
        )
    result = build_local_corpus(request)
    if result.build_identity_sha256 != identity.content_sha256:
        raise ValueError("Resumed corpus returned a changed build identity.")
    return {
        "status": result.status,
        "build_identity_sha256": result.build_identity_sha256,
        "actual_committed_quota_tokens": result.accepted_quota_tokens,
        "manifest_complete": bool(
            isinstance(result.manifest, Mapping)
            and result.manifest.get("complete") is True
        ),
        "operator_evidence_sha256": persisted_authorization[
            "resume_operator_evidence_sha256"
        ],
    }


def _nearest_existing_directory(path: Path) -> Path:
    candidate = path
    while not candidate.exists():
        if candidate.parent == candidate:
            raise ValueError(f"No existing ancestor for storage status: {path}")
        candidate = candidate.parent
    if not candidate.is_dir():
        candidate = candidate.parent
    return candidate


def _status_stage(
    *,
    work_dir: Path,
    drive_dir: Path,
    registry: Any,
    mixture: Mapping[str, Any],
    candidate_config: TokenizerCandidateConfig,
    model_config: Mapping[str, Any],
) -> dict[str, Any]:
    winner, tokenizer_dir, tokenizer_sha256, selection, comparison = (
        _selected_tokenizer_evidence(
            drive_dir=drive_dir,
            work_dir=work_dir,
            registry=registry,
            mixture=mixture,
            candidate_config=candidate_config,
            model_config=model_config,
        )
    )
    request = _corpus_request(
        kind="full",
        work_dir=work_dir,
        drive_dir=drive_dir,
        registry=registry,
        mixture=mixture,
        candidate_config=candidate_config,
        model_config=model_config,
        tokenizer_dir=tokenizer_dir,
        tokenizer_sha256=tokenizer_sha256,
    )
    identity = _expected_build_identity(request)
    requested = {
        f"{plan['stage']}:{item['id']}": int(item["token_quota"])
        for plan in request.plans
        for item in plan["items"]
    }
    actual = {key: 0 for key in requested}
    last_commit: dict[str, Any] | None = None
    unpublished_count = 0
    unpublished_bytes = 0
    journal_path = Path(request.local_root) / "corpus.sqlite3"
    journal_state = "not_started"
    if journal_path.exists():
        require_managed_path(
            request.local_root, journal_path, kind="file", allow_missing=False
        )
        connection = sqlite3.connect(f"file:{journal_path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            metadata = dict(connection.execute("SELECT key, value FROM metadata"))
            saved_identity = json.loads(metadata.get("identity_json", "null"))
            if (
                not isinstance(saved_identity, Mapping)
                or metadata.get("identity_sha256") != sha256_json(saved_identity)
                or metadata.get("identity_sha256") != identity.sha256
            ):
                raise ValueError("Corpus journal identity does not match selected workflow.")
            row = connection.execute(
                "SELECT unit_id, stage, source_id, row_cursor, quota_tokens, "
                "state_json, published FROM units ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            if row is not None:
                state = json.loads(str(row["state_json"]))
                cumulative = state.get("cumulative", {})
                saved_quotas = (
                    cumulative.get("item_quotas", {})
                    if isinstance(cumulative, Mapping)
                    else {}
                )
                if isinstance(saved_quotas, Mapping):
                    for key in actual:
                        actual[key] = int(saved_quotas.get(key, 0))
                last_commit = {
                    "unit_id": str(row["unit_id"]),
                    "stage": str(row["stage"]),
                    "source_id": str(row["source_id"]),
                    "row_cursor": int(row["row_cursor"]),
                    "quota_tokens": int(row["quota_tokens"]),
                    "published": bool(row["published"]),
                }
                journal_state = "active"
            pending = connection.execute(
                "SELECT COUNT(*) AS count, COALESCE(SUM(size), 0) AS bytes "
                "FROM artifacts WHERE published = 0"
            ).fetchone()
            unpublished_count = int(pending["count"])
            unpublished_bytes = int(pending["bytes"])
        finally:
            connection.close()
    progress = _progress_payload(Path(request.local_root))
    throughput = progress.get("throughput", {})
    rolling_rate = (
        float(throughput.get("rolling_tokens_per_second", 0.0))
        if isinstance(throughput, Mapping)
        else 0.0
    )
    total = sum(actual.values())
    eta = (
        max(0, FULL_TARGET_TOKENS - total) / rolling_rate
        if rolling_rate > 0
        else None
    )
    calibration_gate = False
    calibration_gate_reason = "Calibration operator or core evidence is missing."
    calibration_path = _calibration_operator_path(drive_dir, tokenizer_sha256)
    if calibration_path.is_file() and not calibration_path.is_symlink():
        try:
            calibration = _read_hashed_evidence(
                calibration_path,
                hash_field="operator_report_sha256",
                managed_root=drive_dir,
                label="Calibration operator report",
            )
            _validated_calibration_report(
                calibration,
                expected_build_identity=identity.content_sha256,
                core_report_path=(
                    Path(request.destination_root) / "calibration_report.json"
                ),
                core_managed_root=Path(request.destination_root),
            )
            calibration_gate = True
            calibration_gate_reason = "passed"
        except (FileNotFoundError, OSError, ValueError) as error:
            calibration_gate_reason = str(error)
    manifest_complete = False
    manifest_path = Path(request.destination_root) / "manifest.json"
    if manifest_path.is_file() and not manifest_path.is_symlink():
        manifest = _load_json_object(manifest_path, "Full corpus manifest")
        stored = manifest.get("manifest_sha256")
        unsigned = dict(manifest)
        unsigned.pop("manifest_sha256", None)
        manifest_complete = bool(
            stored == sha256_json(unsigned)
            and manifest.get("complete") is True
            and manifest.get("build_identity_sha256") == identity.content_sha256
        )
    pilot_gate = False
    pilot_gate_reason = "Pilot refresh evidence is missing."
    pilot_path = _pilot_refresh_path(drive_dir, tokenizer_sha256)
    if pilot_path.is_file() and not pilot_path.is_symlink():
        try:
            pilot = _read_hashed_evidence(
                pilot_path,
                hash_field="pilot_refresh_sha256",
                managed_root=drive_dir,
                label="Pilot refresh",
            )
            current_pilot = _current_pilot_refresh(
                pilot,
                drive_dir=drive_dir,
                tokenizer_sha256=tokenizer_sha256,
                winner=winner,
                selection=selection,
                comparison=comparison,
                candidate_config=candidate_config,
            )
            pilot_gate = bool(
                current_pilot.get("refreshed_pilot_gates_passed") is True
                and current_pilot.get("pending_colab_gates") == []
            )
            pilot_gate_reason = (
                "passed"
                if pilot_gate
                else str(current_pilot.get("current_gate_reason", "Pilot gates pending."))
            )
        except (FileNotFoundError, OSError, ValueError) as error:
            pilot_gate_reason = str(error)
    return {
        "status": "complete" if manifest_complete else journal_state,
        "build_identity_sha256": identity.content_sha256,
        "selected_tokenizer_sha256": tokenizer_sha256,
        "journal_state": journal_state,
        "exact_quotas": {
            key: {"requested_tokens": requested[key], "actual_tokens": actual[key]}
            for key in sorted(requested)
        },
        "accepted_quota_tokens": total,
        "last_commit": last_commit,
        "local_bytes": _safe_tree_bytes(Path(request.local_root)),
        "destination_bytes": _safe_tree_bytes(Path(request.destination_root)),
        "unpublished_artifacts": unpublished_count,
        "unpublished_bytes": unpublished_bytes,
        "free_disk_bytes": shutil.disk_usage(
            _nearest_existing_directory(Path(request.local_root))
        ).free,
        "throughput": dict(throughput) if isinstance(throughput, Mapping) else {},
        "eta_seconds": eta,
        "calibration_gate_satisfied": calibration_gate,
        "calibration_gate_reason": calibration_gate_reason,
        "pilot_refresh_gate_satisfied": pilot_gate,
        "pilot_refresh_gate_reason": pilot_gate_reason,
        "full_completion_gate_satisfied": bool(
            manifest_complete and calibration_gate and pilot_gate
        ),
    }


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
    if args.stage == "pilot_refresh":
        return _pilot_refresh_stage(
            work_dir=work_dir,
            drive_dir=drive_dir,
            registry=registry,
            mixture=mixture,
            candidate_config=candidate_config,
            model_config=model_config,
        )
    if args.stage == "full_calibration":
        return _full_calibration_stage(
            args,
            work_dir=work_dir,
            drive_dir=drive_dir,
            registry=registry,
            mixture=mixture,
            candidate_config=candidate_config,
            model_config=model_config,
        )
    if args.stage == "full_resume":
        return _full_resume_stage(
            args,
            work_dir=work_dir,
            drive_dir=drive_dir,
            registry=registry,
            mixture=mixture,
            candidate_config=candidate_config,
            model_config=model_config,
        )
    if args.stage == "status":
        return _status_stage(
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
    except (FileExistsError, OSError, StoragePressure, ValueError) as error:
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
