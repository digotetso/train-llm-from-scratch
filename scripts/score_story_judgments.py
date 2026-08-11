#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matgpt.eval.judge import summarize_judgments, validate_judgments
from matgpt.training.checkpoint_provenance import checkpoint_binding
from matgpt.training.run_summary import write_evaluation_result
from matgpt.utils.hashing import sha256_file


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value: {value}")


def _load_review_key(path: Path) -> dict[str, dict[str, object]]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant
        )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"invalid review key JSON: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError("review key must contain a JSON object")

    result: dict[str, dict[str, object]] = {}
    for review_id, row in payload.items():
        if not isinstance(review_id, str) or not review_id:
            raise ValueError("review key ids must be non-empty strings")
        if not isinstance(row, dict):
            raise ValueError(f"review key entry {review_id!r} must be an object")
        checkpoint_label = row.get("checkpoint_label")
        generation_id = row.get("generation_id")
        if not isinstance(checkpoint_label, str) or not checkpoint_label:
            raise ValueError(f"review key entry {review_id!r} has no checkpoint label")
        if not isinstance(generation_id, str) or not generation_id:
            raise ValueError(f"review key entry {review_id!r} has no generation id")
        result[review_id] = dict(row)
    return result


def _load_jsonl_objects(paths: list[Path]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in paths:
        try:
            handle = path.open("r", encoding="utf-8")
        except OSError as error:
            raise ValueError(f"cannot read judgments: {path}") from error
        with handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line, parse_constant=_reject_json_constant)
                except (json.JSONDecodeError, ValueError) as error:
                    raise ValueError(
                        f"invalid judgment JSON at {path}:{line_number}"
                    ) from error
                if not isinstance(row, dict):
                    raise ValueError(
                        f"judgment at {path}:{line_number} must be an object"
                    )
                rows.append(row)
    return rows


def _join_judgments(
    judgments: list[dict[str, object]],
    review_key: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    joined = []
    for judgment in judgments:
        review_id = str(judgment["review_id"])
        joined.append({**review_key[review_id], **judgment})
    return joined


def _checkpoint_path_for_validation(
    stored_path: object, checkpoint_root: Path | None
) -> Path:
    if not isinstance(stored_path, str) or not stored_path:
        raise ValueError("checkpoint binding path is invalid")
    if checkpoint_root is None:
        return Path(stored_path)
    reference = Path(stored_path)
    if not reference.is_absolute() or reference.parent.name != "checkpoints":
        raise ValueError("relocated checkpoint path is outside a checkpoints directory")
    resolved_root = checkpoint_root.expanduser().resolve(strict=True)
    if not resolved_root.is_dir():
        raise ValueError("checkpoint root is not a directory")
    candidate = (resolved_root / reference.name).resolve(strict=True)
    if candidate.parent != resolved_root:
        raise ValueError("relocated checkpoint path is outside checkpoint root")
    return candidate


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and score blinded story-consistency judgments."
    )
    parser.add_argument("--key", required=True, help="Private review_key.json path.")
    parser.add_argument(
        "--judgments",
        action="append",
        required=True,
        help="Judgment JSONL path. Repeat for multiple batches.",
    )
    parser.add_argument(
        "--reviewer", required=True, choices=("llm", "human"), help="Reviewer type."
    )
    parser.add_argument(
        "--comparison-summary", required=True,
        help="comparison_summary.json whose checkpoints were judged.",
    )
    parser.add_argument(
        "--checkpoint-root",
        help=(
            "Optional local checkpoints directory used to validate bindings "
            "recorded on another machine."
        ),
    )
    parser.add_argument("--output", required=True, help="New scored JSON path.")
    args = parser.parse_args()

    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"scored output already exists: {output}")
    review_key = _load_review_key(Path(args.key))
    raw_rows = _load_jsonl_objects([Path(path) for path in args.judgments])
    judgments = validate_judgments(raw_rows, set(review_key))
    summary = summarize_judgments(judgments, review_key)
    comparison_path = Path(args.comparison_summary)
    try:
        comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as error:
        raise ValueError("invalid comparison summary JSON") from error
    comparison_checkpoints = comparison_payload.get("checkpoints") \
        if isinstance(comparison_payload, dict) else None
    artifact_identity = comparison_payload.get("artifact_identity") \
        if isinstance(comparison_payload, dict) else None
    if (
        not isinstance(comparison_checkpoints, dict)
        or set(comparison_checkpoints) != set(summary["checkpoints"])
        or not isinstance(artifact_identity, dict)
        or not artifact_identity
        or any(
            not isinstance(key, str) or not isinstance(value, str) or not value
            for key, value in artifact_identity.items()
        )
    ):
        raise ValueError("comparison identity or checkpoint labels do not match scored judgments")
    checkpoint_bindings = {}
    checkpoint_root = Path(args.checkpoint_root) if args.checkpoint_root else None
    for label, record in comparison_checkpoints.items():
        stored_binding = record.get("binding") if isinstance(record, dict) else None
        if (
            not isinstance(stored_binding, dict)
            or set(stored_binding) != {"path", "size", "sha256"}
            or record.get("path") != stored_binding.get("path")
        ):
            raise ValueError(
                f"comparison checkpoint {label!r} has no immutable binding"
            )
        try:
            validation_path = _checkpoint_path_for_validation(
                stored_binding.get("path"), checkpoint_root
            )
            current_binding = checkpoint_binding(validation_path)
        except (OSError, ValueError) as error:
            raise ValueError(f"comparison checkpoint is invalid: {label}") from error
        if (
            current_binding["size"] != stored_binding["size"]
            or current_binding["sha256"] != stored_binding["sha256"]
        ):
            raise ValueError(f"comparison checkpoint changed after evaluation: {label}")
        checkpoint_bindings[label] = dict(stored_binding)
    result = {
        "reviewer": args.reviewer,
        "review_count": len(judgments),
        "judgments": _join_judgments(judgments, review_key),
        "summary": summary,
        "artifact_identity": dict(artifact_identity),
        "comparison": {
            "path": Path(os.path.relpath(comparison_path, output.parent)).as_posix(),
            "sha256": sha256_file(comparison_path),
        },
        "checkpoints": checkpoint_bindings,
    }
    write_evaluation_result(output, result)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
