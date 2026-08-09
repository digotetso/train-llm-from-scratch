import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from matgpt.tokenizer.io import load_tokenizer, load_tokenizer_metadata
from matgpt.tokenizer.fertility import load_probe_sets, measure_tokenizer_fertility
from matgpt.tokenizer.train import (
    evaluate_tokenizer_on_jsonl,
    train_tokenizer_from_jsonl,
    train_tokenizer_from_manifest,
)
from matgpt.utils.hashing import sha256_file, sha256_json, sha256_text

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


def write_sample_manifest(
    root: Path,
    *,
    fit_records: list[list[dict[str, object]]],
    holdout_records: list[list[dict[str, object]]],
) -> Path:
    artifacts: list[dict[str, object]] = []
    content_digests = {"fit": hashlib.sha256(), "holdout": hashlib.sha256()}
    document_counts = {"fit": 0, "holdout": 0}
    for split, chunks in (("fit", fit_records), ("holdout", holdout_records)):
        split_dir = root / split
        split_dir.mkdir(parents=True, exist_ok=True)
        for index, records in enumerate(chunks):
            path = split_dir / f"{split}_{index:05d}.jsonl"
            path.write_text(
                "".join(
                    json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                    for record in records
                ),
                encoding="utf-8",
            )
            artifacts.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
            for record in records:
                content_digests[split].update(
                    str(record["content_sha256"]).encode("utf-8")
                )
                document_counts[split] += 1

    artifact_digest = hashlib.sha256()
    for artifact in sorted(artifacts, key=lambda item: str(item["path"])):
        artifact_digest.update(sha256_json(artifact).encode("utf-8"))
    manifest = {
        "version": 1,
        "complete": True,
        "accepted_documents": document_counts["fit"],
        "holdout_documents": document_counts["holdout"],
        "fit_content_sha256": content_digests["fit"].hexdigest(),
        "holdout_content_sha256": content_digests["holdout"].hexdigest(),
        "artifact_count": len(artifacts),
        "artifacts_sha256": artifact_digest.hexdigest(),
    }
    manifest["manifest_sha256"] = sha256_json(manifest)
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest_path


def sample_record(
    text: str,
    *,
    role: str = "pretrain_general",
    source_id: str = "sample_source",
    bucket_id: str | None = None,
) -> dict[str, object]:
    digest = sha256_text(text)
    return {
        "text": text,
        "content_sha256": digest,
        "text_sha256": digest,
        "role": role,
        "source_id": source_id,
        "bucket_id": bucket_id,
    }


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


def test_train_tokenizer_from_manifest_reads_all_verified_fit_chunks(tmp_path: Path):
    manifest = write_sample_manifest(
        tmp_path,
        fit_records=[
            [sample_record("RRC connection setup.")],
            [sample_record("A router forwards packets.")],
        ],
        holdout_records=[[sample_record("Held-out routing document.")]],
    )

    report = train_tokenizer_from_manifest(
        manifest,
        tmp_path / "tokenizer",
        vocab_size=320,
        min_frequency=1,
        special_tokens=SPECIAL_TOKENS,
    )

    assert report["num_training_documents"] == 2
    assert report["fitting_manifest_sha256"] == json.loads(
        manifest.read_text(encoding="utf-8")
    )["manifest_sha256"]


def test_train_tokenizer_from_manifest_rejects_unexpected_fit_entry(tmp_path: Path):
    manifest = write_sample_manifest(
        tmp_path,
        fit_records=[[sample_record("RRC connection setup.")]],
        holdout_records=[],
    )
    (tmp_path / "fit" / "notes.txt").write_text("not a chunk", encoding="utf-8")

    with pytest.raises(ValueError, match="unexpected sample entry"):
        train_tokenizer_from_manifest(
            manifest,
            tmp_path / "tokenizer",
            vocab_size=320,
            min_frequency=1,
            special_tokens=SPECIAL_TOKENS,
        )


def test_evaluate_tokenizer_reports_streamed_holdout_and_probe_metrics(
    tmp_path: Path,
):
    corpus = tmp_path / "train.jsonl"
    tokenizer_dir = tmp_path / "tokenizer"
    probes = tmp_path / "probes.yaml"
    write_corpus(corpus)
    train_tokenizer_from_jsonl(
        [corpus],
        tokenizer_dir,
        vocab_size=320,
        min_frequency=1,
        special_tokens=SPECIAL_TOKENS,
    )
    probes.write_text(
        "version: 1\ngroups:\n  general:\n    - General prose.\n"
        "  telecom:\n    - RRC connection.\n",
        encoding="utf-8",
    )
    manifest = write_sample_manifest(
        tmp_path / "sample",
        fit_records=[[sample_record("Fitting text.")]],
        holdout_records=[
            [
                sample_record(
                    "A router forwards packets.",
                    role="pretrain_general",
                    source_id="general_source",
                )
            ],
            [
                sample_record(
                    "The gNodeB establishes an RRC connection.",
                    role="pretrain_telecom",
                    source_id="telco_source",
                    bucket_id="ran",
                )
            ],
        ],
    )

    report = evaluate_tokenizer_on_jsonl(tokenizer_dir, [manifest], probes)

    assert report["documents"] == 2
    assert report["roles"]["pretrain_general"]["documents"] == 1
    assert report["roles"]["pretrain_telecom"]["documents"] == 1
    assert report["sources"]["telco_source"]["documents"] == 1
    assert report["buckets"]["ran"]["documents"] == 1
    assert report["p50_tokens_per_word"] <= report["p95_tokens_per_word"]
    assert report["probe_metrics"]["groups"]["telecom"]["documents"] == 1
    assert report["probe_p95_tokens_per_word"] > 0
    assert report["round_trip_failures"] == 0
    assert report["special_token_failures"] == 0
    assert report["sample_manifest_sha256"] == json.loads(
        manifest.read_text(encoding="utf-8")
    )["manifest_sha256"]
    assert len(report["input_file_checksums"]) == 2


def test_evaluate_tokenizer_records_missing_or_invalid_special_metadata_as_failure(
    tmp_path: Path,
):
    corpus = tmp_path / "train.jsonl"
    tokenizer_dir = tmp_path / "tokenizer"
    probes = tmp_path / "probes.yaml"
    write_corpus(corpus)
    train_tokenizer_from_jsonl(
        [corpus],
        tokenizer_dir,
        vocab_size=320,
        min_frequency=1,
        special_tokens=SPECIAL_TOKENS,
    )
    (tokenizer_dir / "special_tokens.json").unlink()
    probes.write_text(
        "version: 1\ngroups:\n  general:\n    - General prose.\n",
        encoding="utf-8",
    )
    manifest = write_sample_manifest(
        tmp_path / "sample",
        fit_records=[[sample_record("Fitting text.")]],
        holdout_records=[[sample_record("Held-out text.")]],
    )

    report = evaluate_tokenizer_on_jsonl(tokenizer_dir, [manifest], probes)

    assert report["special_token_failures"] == 1
    assert report["special_token_failure_details"] == [
        {"reason": "missing_or_invalid_special_token_metadata"}
    ]

    (tokenizer_dir / "special_tokens.json").write_text("[]\n", encoding="utf-8")
    invalid_report = evaluate_tokenizer_on_jsonl(tokenizer_dir, [manifest], probes)

    assert invalid_report["special_token_failures"] == 1
    assert invalid_report["special_token_failure_details"] == [
        {"reason": "missing_or_invalid_special_token_metadata"}
    ]


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
