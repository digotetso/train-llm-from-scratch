from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers

from matgpt.utils.hashing import sha256_file


def _iter_texts(input_paths: Iterable[str | Path]):
    for path in input_paths:
        with Path(path).open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                text = record.get("text", "")
                if text:
                    yield text


def _count_texts(input_paths: Iterable[str | Path]) -> tuple[int, int]:
    count = 0
    total_chars = 0
    for text in _iter_texts(input_paths):
        count += 1
        total_chars += len(text)
    return count, total_chars


def train_tokenizer_from_jsonl(
    input_paths: list[str | Path],
    output_dir: str | Path,
    vocab_size: int,
    min_frequency: int,
    special_tokens: list[str],
) -> dict[str, object]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    tokenizer = Tokenizer(models.BPE(unk_token=None))
    tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tokenizer.decoder = decoders.ByteLevel()

    trainer = trainers.BpeTrainer(
        vocab_size=vocab_size,
        min_frequency=min_frequency,
        special_tokens=special_tokens,
        show_progress=True,
    )

    num_documents, total_chars = _count_texts(input_paths)
    if num_documents == 0:
        raise ValueError("No training text found for tokenizer.")

    tokenizer.train_from_iterator(_iter_texts(input_paths), trainer=trainer, length=num_documents)
    tokenizer_path = out / "tokenizer.json"
    tokenizer.save(str(tokenizer_path))

    total_tokens = 0
    for text in _iter_texts(input_paths):
        total_tokens += len(tokenizer.encode(text).ids)
    special_token_ids = {token: tokenizer.token_to_id(token) for token in special_tokens}
    metadata = {
        "algorithm": "byte_level_bpe",
        "vocab_size_requested": vocab_size,
        "vocab_size_actual": tokenizer.get_vocab_size(),
        "special_token_ids": special_token_ids,
        "tokenizer_sha256": sha256_file(tokenizer_path),
    }
    (out / "special_tokens.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = {
        **metadata,
        "num_training_documents": num_documents,
        "total_training_chars": total_chars,
        "total_training_tokens": total_tokens,
        "chars_per_token": (total_chars / total_tokens) if total_tokens else 0.0,
        "avg_tokens_per_document": total_tokens / num_documents,
        "input_paths": [str(Path(path)) for path in input_paths],
    }
    (out / "tokenizer_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def train_tokenizer_from_config(cfg: dict) -> dict[str, object]:
    train_split = cfg["dataset"]["train_split"]
    input_path = Path(cfg["dataset"]["normalized_dir"]) / f"{train_split}.jsonl"
    tokenizer_cfg = cfg["tokenizer"]
    return train_tokenizer_from_jsonl(
        input_paths=[input_path],
        output_dir=tokenizer_cfg["output_dir"],
        vocab_size=tokenizer_cfg["vocab_size"],
        min_frequency=tokenizer_cfg["min_frequency"],
        special_tokens=tokenizer_cfg["special_tokens"],
    )
