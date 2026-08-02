import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from matgpt.tokenizer.io import load_tokenizer, load_tokenizer_metadata
from matgpt.tokenizer.fertility import load_probe_sets, measure_tokenizer_fertility
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


def test_checked_probe_sets_cover_general_and_telecom_language():
    probes = load_probe_sets("configs/data/telco_tokenizer_probes.yaml")

    assert len(probes["general"]) >= 20
    assert len(probes["telecom"]) >= 40
    assert any("gNodeB" in text for text in probes["telecom"])
    assert any("MPLS" in text for text in probes["telecom"])
    assert any("O-RAN" in text for text in probes["telecom"])


def test_fertility_report_has_general_and_telco_groups(tmp_path: Path):
    corpus = tmp_path / "train.jsonl"
    tokenizer_dir = tmp_path / "tokenizer"
    write_corpus(corpus)
    train_tokenizer_from_jsonl(
        [corpus],
        tokenizer_dir,
        vocab_size=320,
        min_frequency=1,
        special_tokens=SPECIAL_TOKENS,
    )
    tokenizer = load_tokenizer(tokenizer_dir)

    report = measure_tokenizer_fertility(
        tokenizer,
        {
            "general": ["A router forwards packets."],
            "telecom": ["The gNodeB establishes an RRC connection."],
        },
    )

    assert set(report["groups"]) == {"general", "telecom"}
    assert report["groups"]["telecom"]["tokens_per_word"] > 0
    assert report["groups"]["general"]["characters_per_token"] > 0
    assert report["round_trip_failures"] == []
    assert report["invalid_token_ids"] == []


def test_training_report_includes_configured_fertility_probes(tmp_path: Path):
    corpus = tmp_path / "train.jsonl"
    tokenizer_dir = tmp_path / "tokenizer"
    probes = tmp_path / "probes.yaml"
    write_corpus(corpus)
    probes.write_text(
        "version: 1\ngroups:\n  general:\n    - General prose.\n  telecom:\n    - RRC connection.\n",
        encoding="utf-8",
    )

    report = train_tokenizer_from_jsonl(
        [corpus],
        tokenizer_dir,
        vocab_size=320,
        min_frequency=1,
        special_tokens=SPECIAL_TOKENS,
        probe_sets_path=probes,
    )

    persisted = json.loads(
        (tokenizer_dir / "tokenizer_report.json").read_text(encoding="utf-8")
    )
    assert report["fertility"] == persisted["fertility"]
    assert set(report["fertility"]["groups"]) == {"general", "telecom"}


def test_fertility_rejects_invalid_token_ids():
    tokenizer = SimpleNamespace(
        get_vocab_size=lambda: 2,
        encode=lambda _text: SimpleNamespace(ids=[0, 2]),
        decode=lambda _ids: "probe",
    )

    with pytest.raises(ValueError, match="invalid IDs"):
        measure_tokenizer_fertility(tokenizer, {"general": ["probe"]})


def test_fertility_rejects_failed_round_trip():
    tokenizer = SimpleNamespace(
        get_vocab_size=lambda: 2,
        encode=lambda _text: SimpleNamespace(ids=[0]),
        decode=lambda _ids: "different",
    )

    with pytest.raises(ValueError, match="exact round trip"):
        measure_tokenizer_fertility(tokenizer, {"general": ["probe"]})
