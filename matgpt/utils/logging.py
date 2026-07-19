from __future__ import annotations

import csv
from pathlib import Path
from typing import Mapping


def ensure_dir(path: str | Path) -> Path:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def append_csv_row(
    path: str | Path,
    row: Mapping[str, object],
    fieldnames: tuple[str, ...] | list[str] | None = None,
) -> None:
    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists()
    fields = list(fieldnames) if fieldnames is not None else list(row.keys())
    if not write_header and fieldnames is not None:
        with csv_path.open(newline="", encoding="utf-8") as f:
            existing_fields = next(csv.reader(f), [])
        if existing_fields != fields:
            raise ValueError(
                f"Existing CSV header does not match the required schema: {csv_path}"
            )
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="raise")
        if write_header:
            writer.writeheader()
        writer.writerow(row)
