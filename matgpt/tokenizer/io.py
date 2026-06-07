from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tokenizers import Tokenizer


def load_tokenizer(path: str | Path) -> Tokenizer:
    base = Path(path)
    tokenizer_path = base if base.name.endswith(".json") else base / "tokenizer.json"
    return Tokenizer.from_file(str(tokenizer_path))


def load_tokenizer_metadata(path: str | Path) -> dict[str, Any]:
    base = Path(path)
    metadata_path = base / "special_tokens.json"
    return json.loads(metadata_path.read_text(encoding="utf-8"))
