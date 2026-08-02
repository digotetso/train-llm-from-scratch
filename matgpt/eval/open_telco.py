"""Pinned Open Telco benchmark materialization for local MatGPT evaluation."""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from matgpt.data.sources import SourceRegistry
from matgpt.eval.tasks import load_multiple_choice_examples
from matgpt.utils.hashing import sha256_file, sha256_json


SUPPORTED_MULTIPLE_CHOICE_CONFIGS = frozenset(
    {"teleqna", "oranbench", "srsranbench", "sixg_bench"}
)
DatasetLoader = Callable[..., Iterable[Mapping[str, Any]]]


def _answer_index(answer: Any, choices: list[str]) -> int:
    if isinstance(answer, int) and not isinstance(answer, bool):
        index = answer
    elif isinstance(answer, str):
        stripped = answer.strip()
        if len(stripped) == 1 and stripped.upper().isalpha():
            index = ord(stripped.upper()) - ord("A")
        elif stripped.isdigit():
            index = int(stripped)
        elif stripped in choices:
            index = choices.index(stripped)
        else:
            raise ValueError(f"Unsupported answer value: {answer!r}")
    else:
        raise ValueError(f"Unsupported answer value: {answer!r}")
    if index < 0 or index >= len(choices):
        raise ValueError(f"Answer index {index} is outside choices length {len(choices)}.")
    return index


def convert_open_telco_row(
    dataset_id: str,
    config: str,
    index: int,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    """Convert one supported benchmark row to MatGPT multiple-choice JSONL."""

    if config not in SUPPORTED_MULTIPLE_CHOICE_CONFIGS:
        raise ValueError(
            f"Open Telco config {config!r} is not supported by the "
            "multiple-choice evaluator."
        )
    question = row.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError(f"Open Telco {config!r} row {index} has no question.")
    raw_choices = row.get("choices")
    if not isinstance(raw_choices, (list, tuple)) or len(raw_choices) < 2:
        raise ValueError(
            f"Open Telco {config!r} row {index} requires at least two choices."
        )
    choices = [str(choice).strip() for choice in raw_choices]
    if any(not choice for choice in choices):
        raise ValueError(f"Open Telco {config!r} row {index} has an empty choice.")
    answer = _answer_index(row.get("answer"), choices)
    category = next(
        (
            str(row[field]).strip()
            for field in ("category", "subject", "task_name", "difficulty")
            if row.get(field) is not None and str(row[field]).strip()
        ),
        config,
    )
    content = {
        "prompt": question.strip(),
        "choices": choices,
        "answer": answer,
        "category": category,
    }
    return {
        "id": f"{dataset_id}/{config}/{index}",
        **content,
        "dataset_id": dataset_id,
        "config": config,
        "source_index": index,
        "content_sha256": sha256_json(content),
    }


def _load_dataset_function(dataset_loader: DatasetLoader | None) -> DatasetLoader:
    if dataset_loader is not None:
        return dataset_loader
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError(
            "Install the 'datasets' package to materialize Open Telco tasks."
        ) from exc
    return load_dataset


def prepare_open_telco_evals(
    registry: SourceRegistry,
    source_id: str,
    configs: Sequence[str],
    output_dir: str | Path,
    *,
    dataset_loader: DatasetLoader | None = None,
) -> dict[str, Any]:
    """Stream pinned evaluation configs and atomically publish local JSONL files."""

    source = registry.by_id.get(source_id)
    if source is None:
        raise ValueError(f"Unknown source id: {source_id!r}")
    if source.role != "evaluation_only":
        raise ValueError(
            f"Source {source_id!r} must have role 'evaluation_only'; "
            f"observed {source.role!r}."
        )
    if not configs:
        raise ValueError("At least one Open Telco config is required.")
    if len(configs) != len(set(configs)):
        raise ValueError("Open Telco configs must be unique.")
    unsupported = set(configs) - SUPPORTED_MULTIPLE_CHOICE_CONFIGS
    if unsupported:
        raise ValueError(
            "Configs not supported by the multiple-choice evaluator: "
            f"{sorted(unsupported)}"
        )

    output = Path(output_dir)
    if output.exists():
        raise FileExistsError(f"Evaluation output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
    )
    loader = _load_dataset_function(dataset_loader)
    config_stats: dict[str, Any] = {}

    try:
        for config in configs:
            dataset = loader(
                source.hf_name,
                name=config,
                split=source.split,
                revision=source.revision,
                streaming=True,
            )
            path = staging / f"{config}.jsonl"
            count = 0
            with path.open("w", encoding="utf-8") as handle:
                for index, row in enumerate(dataset):
                    if not isinstance(row, Mapping):
                        raise ValueError(
                            f"Open Telco {config!r} row {index} must be a mapping."
                        )
                    converted = convert_open_telco_row(
                        source.hf_name,
                        config,
                        index,
                        row,
                    )
                    handle.write(
                        json.dumps(converted, ensure_ascii=False, sort_keys=True)
                        + "\n"
                    )
                    count += 1
            if count == 0:
                raise ValueError(f"Open Telco config {config!r} returned no rows.")
            examples = load_multiple_choice_examples(path)
            if len(examples) != count:
                raise ValueError(
                    f"Open Telco config {config!r} failed local schema validation."
                )
            config_stats[config] = {
                "path": path.name,
                "examples": count,
                "raw_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }

        manifest: dict[str, Any] = {
            "version": 1,
            "complete": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dataset_id": source.hf_name,
            "source_id": source.id,
            "revision": source.revision,
            "role": source.role,
            "license": source.license,
            "configs": {
                config: config_stats[config] for config in sorted(config_stats)
            },
        }
        manifest["manifest_sha256"] = sha256_json(manifest)
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        staging.replace(output)
        return manifest
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
