from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path
from typing import Any


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def write_evaluation_result(path: str | Path, result: dict[str, Any]) -> Path:
    output = Path(path)
    _atomic_write_text(output, json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return output


def _finite_values(rows: list[dict[str, str]], key: str) -> list[float]:
    values = []
    for row in rows:
        raw = row.get(key, "")
        if raw in (None, ""):
            continue
        value = float(raw)
        if math.isfinite(value):
            values.append(value)
    return values


def _load_json_if_present(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def build_run_summary(run_dir: str | Path, known_limitations: list[str]) -> str:
    root = Path(run_dir)
    metrics_path = root / "metrics.csv"
    if not metrics_path.is_file():
        raise FileNotFoundError(f"Run metrics are missing: {metrics_path}")
    with metrics_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    validation_losses = _finite_values(rows, "val_loss")
    training_losses = _finite_values(rows, "train_loss")
    throughput = _finite_values(rows, "tokens_per_second")
    peak_memory = _finite_values(rows, "peak_memory_mb")
    elapsed = _finite_values(rows, "elapsed_seconds")
    skipped = _finite_values(rows, "optimizer_steps_skipped_total")
    if not validation_losses:
        raise ValueError("No finite validation loss is present in metrics.csv")

    environment = _load_json_if_present(root / "environment.json")
    fingerprints = _load_json_if_present(root / "fingerprints.json")
    evaluation_dir = root / "evaluation"
    evaluation_files = sorted(evaluation_dir.glob("*.json")) if evaluation_dir.is_dir() else []
    for path in evaluation_files:
        _load_json_if_present(path)

    latest_exists = (root / "checkpoints" / "latest.pt").is_file()
    best_exists = (root / "checkpoints" / "best.pt").is_file()
    config_snapshot_exists = (root / "config.snapshot.yaml").is_file()
    lines = [
        "# Run Summary",
        "",
        "## Identity",
        f"- Run directory: {root}",
        f"- Config snapshot: {'available' if config_snapshot_exists else 'unavailable'}",
        f"- Device: {environment.get('device_name', 'unavailable')}",
        f"- Config SHA-256: {fingerprints.get('config_sha256', 'unavailable')}",
        "",
        "## Quality",
        f"- Initial validation loss: {validation_losses[0]}",
        f"- Best validation loss: {min(validation_losses)}",
        f"- Final validation loss: {validation_losses[-1]}",
        f"- Final training loss: {training_losses[-1] if training_losses else 'unavailable'}",
        "",
        "## Performance",
        f"- Maximum tokens/second: {max(throughput) if throughput else 'unavailable'}",
        f"- Peak memory MB: {max(peak_memory) if peak_memory else 'unavailable'}",
        f"- Elapsed seconds: {max(elapsed) if elapsed else 'unavailable'}",
        f"- Skipped optimizer updates: {int(max(skipped)) if skipped else 'unavailable'}",
        "",
        "## Checkpoints",
        f"- latest.pt load candidate exists: {latest_exists}",
        f"- best.pt load candidate exists: {best_exists}",
        "",
        "## Evaluation Artifacts",
    ]
    lines.extend(f"- {path.name}" for path in evaluation_files)
    if not evaluation_files:
        lines.append("- none")
    lines.extend(["", "## Known Limitations"])
    lines.extend(f"- {limitation}" for limitation in known_limitations)
    return "\n".join(lines) + "\n"


def write_run_summary(run_dir: str | Path, known_limitations: list[str]) -> Path:
    root = Path(run_dir)
    output = root / "run_summary.md"
    _atomic_write_text(output, build_run_summary(root, known_limitations))
    return output
