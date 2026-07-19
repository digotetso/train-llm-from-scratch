import json
from pathlib import Path

from matgpt.tokenizer.io import load_tokenizer, load_tokenizer_metadata
from matgpt.tokenizer.train import train_tokenizer_from_jsonl

SPECIAL_TOKENS = [
    "<|pad|>",
    "<|bos|>",
    "<|eos|>",
    "<|system|>",
    "<|user|>",
    "<|assistant|>",
    "<|end|>",
]

def write_corpus(path: Path) -> None:
    records = [
        {"text": "A token is a small piece of text."},
        {"text": "A model predicts the next token."},
        {"text": "Python lists can store numbers and strings."},
    ]
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def test_train_tokenizer_round_trip_and_special_tokens(tmp_path: Path):
    corpus = tmp_path / "train.jsonl"
    output_dir = tmp_path / "tokenizer"
    write_corpus(corpus)

    report = train_tokenizer_from_jsonl(
        input_paths=[corpus],
        output_dir=output_dir,
        vocab_size=320,
        min_frequency=1,
        special_tokens=SPECIAL_TOKENS,
    )
    tokenizer = load_tokenizer(output_dir)
    metadata = load_tokenizer_metadata(output_dir)

    for token in SPECIAL_TOKENS:
        assert tokenizer.token_to_id(token) is not None
        assert token in metadata["special_token_ids"]

    text = "A token is text."
    ids = tokenizer.encode(text).ids
    assert tokenizer.decode(ids) == text
    assert report["num_training_documents"] == 3
    assert report["vocab_size_actual"] <= 320
    assert (output_dir / "tokenizer.json").exists()
    assert (output_dir / "tokenizer_report.json").exists()


def test_byte_level_tokenizer_round_trips_unseen_unicode(tmp_path: Path):
    corpus = tmp_path / "train.jsonl"
    output_dir = tmp_path / "tokenizer"
    write_corpus(corpus)
    train_tokenizer_from_jsonl(
        [corpus],
        output_dir,
        vocab_size=320,
        min_frequency=1,
        special_tokens=SPECIAL_TOKENS,
    )
    tokenizer = load_tokenizer(output_dir)

    for text in ["🙂", "café", "你好", "A space, then punctuation!"]:
        ids = tokenizer.encode(text).ids
        assert ids, f"non-empty text encoded to no IDs: {text!r}"
        assert tokenizer.decode(ids) == text
