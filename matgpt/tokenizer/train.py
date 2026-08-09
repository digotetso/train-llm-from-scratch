from __future__ import annotations

import hashlib
import json
import re
from array import array
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

import numpy as np
from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers

from matgpt.tokenizer.fertility import (
    WORD_PATTERN,
    load_probe_sets,
    measure_tokenizer_fertility,
)
from matgpt.tokenizer.io import load_tokenizer, load_tokenizer_metadata
from matgpt.utils.hashing import sha256_file, sha256_json, sha256_text
from matgpt.utils.paths import require_managed_path


_CHUNK_NAME = re.compile(r"^(fit|holdout)_(\d{5,})\.jsonl$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_FAILURE_DETAILS = 100
REQUIRED_VOCAB_SIZE = 32_768
REQUIRED_SPECIAL_TOKENS = (
    "<|pad|>",
    "<|bos|>",
    "<|eos|>",
    "<|system|>",
    "<|user|>",
    "<|assistant|>",
    "<|end|>",
)
REQUIRED_SPECIAL_TOKEN_IDS = {
    token: index for index, token in enumerate(REQUIRED_SPECIAL_TOKENS)
}


def has_required_special_token_ids(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == set(REQUIRED_SPECIAL_TOKEN_IDS)
        and all(
            type(value[token]) is int
            and value[token] == required_id
            for token, required_id in REQUIRED_SPECIAL_TOKEN_IDS.items()
        )
    )


def _require_non_negative_integer(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"Sample manifest {field_name} must be a non-negative integer.")
    return value


def _require_sha256(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest.")
    return value


def _read_jsonl_records(
    path: Path,
    *,
    consumed_files: list[dict[str, object]] | None = None,
) -> Iterator[dict[str, Any]]:
    digest = hashlib.sha256()
    consumed_bytes = 0
    records = 0
    with path.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            digest.update(raw_line)
            consumed_bytes += len(raw_line)
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError(
                    f"Sample chunk {path} is not UTF-8 at line {line_number}."
                ) from error
            if not line.strip():
                raise ValueError(f"Sample chunk {path} has a blank line at {line_number}.")
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Sample chunk {path} has invalid JSON at line {line_number}."
                ) from error
            if not isinstance(record, dict):
                raise ValueError(
                    f"Sample chunk {path} has a non-object row at line {line_number}."
                )
            text = record.get("text")
            if not isinstance(text, str) or not text:
                raise ValueError(
                    f"Sample chunk {path} has invalid text at line {line_number}."
                )
            content_sha256 = _require_sha256(
                record.get("content_sha256"),
                f"Sample chunk {path} content_sha256 at line {line_number}",
            )
            if sha256_text(text) != content_sha256:
                raise ValueError(
                    f"Sample chunk {path} content checksum mismatch at line {line_number}."
                )
            records += 1
            yield record
    if consumed_files is not None:
        consumed_files.append(
            {
                "path": str(path),
                "size": consumed_bytes,
                "sha256": digest.hexdigest(),
                "records": records,
            }
        )


def _enumerate_chunk_paths(root: Path, split: str) -> list[Path]:
    split_dir = require_managed_path(root, root / split, kind="directory")
    if not split_dir.exists():
        return []
    if split_dir.is_symlink() or not split_dir.is_dir():
        raise ValueError(f"Sample {split} path must be a real directory.")

    indexed_paths: list[tuple[int, Path]] = []
    for path in split_dir.iterdir():
        require_managed_path(root, path)
        match = _CHUNK_NAME.fullmatch(path.name)
        if (
            match is None
            or match.group(1) != split
            or path.is_symlink()
            or not path.is_file()
        ):
            raise ValueError(
                f"Sample contains unexpected sample entry: "
                f"{path.relative_to(root).as_posix()}"
            )
        indexed_paths.append((int(match.group(2)), path))
    indexed_paths.sort(key=lambda item: item[0])
    indices = [index for index, _ in indexed_paths]
    if indices != list(range(len(indices))):
        raise ValueError(f"Sample {split} chunk indexes must be contiguous from zero.")
    return [path for _, path in indexed_paths]


def _load_verified_sample_manifest(
    manifest_path: str | Path,
) -> tuple[
    dict[str, Any],
    dict[str, list[Path]],
    dict[Path, dict[str, object]],
]:
    path = Path(manifest_path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Sample manifest must be a real file.")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Sample manifest is invalid JSON: {path}") from error
    if not isinstance(manifest, dict):
        raise ValueError("Sample manifest must contain a JSON object.")
    if manifest.get("version") != 3:
        raise ValueError("Sample manifest version must be 3 with build provenance.")
    if manifest.get("complete") is not True:
        raise ValueError("Sample manifest must be complete before tokenizer use.")

    build_provenance = manifest.get("build_provenance")
    if not isinstance(build_provenance, Mapping):
        raise ValueError("Sample manifest requires complete build provenance.")
    build_provenance_sha256 = _require_sha256(
        manifest.get("build_provenance_sha256"),
        "Sample manifest build_provenance_sha256",
    )
    if sha256_json(build_provenance) != build_provenance_sha256:
        raise ValueError("Sample manifest build provenance checksum mismatch.")
    required_provenance = {
        "version",
        "workflow",
        "target_estimated_tokens",
        "role_quotas",
        "plan",
        "recipe",
        "sources",
        "quality_policy",
        "contamination_evidence",
        "format",
    }
    if not required_provenance.issubset(build_provenance):
        raise ValueError("Sample manifest build provenance is incomplete.")
    target_tokens = _require_non_negative_integer(
        build_provenance.get("target_estimated_tokens"),
        "build provenance target_estimated_tokens",
    )
    role_quotas = build_provenance.get("role_quotas")
    if (
        target_tokens < 1
        or not isinstance(role_quotas, Mapping)
        or not role_quotas
        or any(
            not isinstance(value, int) or isinstance(value, bool) or value < 1
            for value in role_quotas.values()
        )
        or sum(role_quotas.values()) != target_tokens
    ):
        raise ValueError("Sample manifest build provenance role quotas are invalid.")
    for field in (
        "plan",
        "recipe",
        "sources",
        "quality_policy",
        "contamination_evidence",
    ):
        component = build_provenance.get(field)
        if not isinstance(component, Mapping):
            raise ValueError(f"Sample manifest build provenance {field} is invalid.")
        _require_sha256(
            component.get("sha256"),
            f"Sample manifest build provenance {field} sha256",
        )
    format_evidence = build_provenance.get("format")
    if not isinstance(format_evidence, Mapping) or format_evidence.get("version") != 3:
        raise ValueError("Sample manifest build provenance format version must be 3.")

    expected_manifest_sha256 = _require_sha256(
        manifest.get("manifest_sha256"), "Sample manifest manifest_sha256"
    )
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256", None)
    if sha256_json(unsigned) != expected_manifest_sha256:
        raise ValueError("Sample manifest checksum mismatch.")

    paths_by_split = {
        split: _enumerate_chunk_paths(path.parent, split)
        for split in ("fit", "holdout")
    }
    artifact_digest = hashlib.sha256()
    artifact_count = 0
    content_digests = {"fit": hashlib.sha256(), "holdout": hashlib.sha256()}
    document_counts = {"fit": 0, "holdout": 0}
    artifact_by_path: dict[Path, dict[str, object]] = {}
    ordered_paths = sorted(
        (chunk for paths in paths_by_split.values() for chunk in paths),
        key=lambda chunk: chunk.relative_to(path.parent).as_posix(),
    )
    for chunk_path in ordered_paths:
        relative = chunk_path.relative_to(path.parent).as_posix()
        artifact = {
            "path": relative,
            "size": chunk_path.stat().st_size,
            "sha256": sha256_file(chunk_path),
        }
        artifact_by_path[chunk_path] = artifact
        artifact_digest.update(sha256_json(artifact).encode("utf-8"))
        artifact_count += 1
        split = chunk_path.parent.name
        for record in _read_jsonl_records(chunk_path):
            content_digests[split].update(
                str(record["content_sha256"]).encode("utf-8")
            )
            document_counts[split] += 1

    expected_artifact_count = _require_non_negative_integer(
        manifest.get("artifact_count"), "artifact_count"
    )
    if artifact_count != expected_artifact_count:
        raise ValueError("Sample manifest artifact count mismatch.")
    if artifact_digest.hexdigest() != _require_sha256(
        manifest.get("artifacts_sha256"), "Sample manifest artifacts_sha256"
    ):
        raise ValueError("Sample manifest artifact checksum mismatch.")

    count_fields = {"fit": "accepted_documents", "holdout": "holdout_documents"}
    digest_fields = {
        "fit": "fit_content_sha256",
        "holdout": "holdout_content_sha256",
    }
    for split in ("fit", "holdout"):
        expected_documents = _require_non_negative_integer(
            manifest.get(count_fields[split]), count_fields[split]
        )
        if document_counts[split] != expected_documents:
            raise ValueError(f"Sample manifest {split} document count mismatch.")
        if content_digests[split].hexdigest() != _require_sha256(
            manifest.get(digest_fields[split]),
            f"Sample manifest {digest_fields[split]}",
        ):
            raise ValueError(f"Sample manifest {split} content checksum mismatch.")
    return manifest, paths_by_split, artifact_by_path


def _iter_texts(
    input_paths: Iterable[str | Path],
    *,
    consumed_files: list[dict[str, object]] | None = None,
):
    # Read each prepared JSONL file.
    for path in input_paths:
        input_path = Path(path)
        digest = hashlib.sha256()
        consumed_bytes = 0
        records = 0
        with input_path.open("rb") as f:

            # Read one document record at a time.
            for raw_line in f:
                digest.update(raw_line)
                consumed_bytes += len(raw_line)
                line = raw_line.decode("utf-8")
                if not line.strip():
                    continue
                record = json.loads(line)

                # Get the actual document text.
                text = record.get("text", "")

                # Give non-empty text to tokenizer training.
                # yield provides one document at a time instead of loading the complete corpus into memory.
                if text:
                    records += 1
                    yield text
        if consumed_files is not None:
            consumed_files.append(
                {
                    "path": str(input_path),
                    "size": consumed_bytes,
                    "sha256": digest.hexdigest(),
                    "records": records,
                }
            )


def _count_texts(
    input_paths: Iterable[str | Path],
) -> tuple[int, int, list[dict[str, object]]]:
    count = 0
    total_chars = 0
    consumed_files: list[dict[str, object]] = []
    for text in _iter_texts(input_paths, consumed_files=consumed_files):
        count += 1
        total_chars += len(text)
    return count, total_chars, consumed_files


def _consumed_stream_report(files: list[dict[str, object]]) -> dict[str, object]:
    canonical_files = [
        {
            "path": str(file["path"]),
            "size": int(file["size"]),
            "sha256": str(file["sha256"]),
            "records": int(file["records"]),
        }
        for file in files
    ]
    return {
        "files": canonical_files,
        "file_count": len(canonical_files),
        "bytes": sum(int(file["size"]) for file in canonical_files),
        "records": sum(int(file["records"]) for file in canonical_files),
        "sha256": sha256_json(canonical_files),
    }


def _assert_consumption_matches(
    reference: list[dict[str, object]],
    observed: list[dict[str, object]],
    *,
    message: str,
) -> None:
    if _consumed_stream_report(reference) != _consumed_stream_report(observed):
        raise ValueError(message)


def _expected_consumption(
    paths: list[Path], artifacts: Mapping[Path, Mapping[str, object]]
) -> list[dict[str, object]]:
    return [
        {
            "path": str(path),
            "size": int(artifacts[path]["size"]),
            "sha256": str(artifacts[path]["sha256"]),
            "records": sum(1 for _ in _read_jsonl_records(path)),
        }
        for path in paths
    ]


def train_tokenizer_from_jsonl(
    input_paths: list[str | Path],
    output_dir: str | Path,
    vocab_size: int,
    min_frequency: int,
    special_tokens: list[str],
    probe_sets_path: str | Path | None = None,
    *,
    expected_consumption: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    paths = [Path(path) for path in input_paths]
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # A tool that splits text into tokens and turns those tokens into numbers
    # This creates a tokenizer
    # in simple terms, Create a tool that can learn useful text pieces
    # BPE is one method for deciding what the text pieces should be

    # BUIILDING THE VOCABULARY
    # 1. Create an empty BPE tokenizer.
    tokenizer = Tokenizer(models.BPE(unk_token=None))

    # Split input text into byte-level pieces before BPE processing.
    # add_prefix_space=False means the tokenizer does not automatically insert a space at the beginning of every input.
    tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)

    # Convert byte-level tokens back into readable text when decoding.
    tokenizer.decoder = decoders.ByteLevel()

    # 2. Configure how the tokenizer should learn. (creates BPE trainer)
    trainer = trainers.BpeTrainer(
        # Maximum requested number of vocabulary entries.
        vocab_size=vocab_size,
        # A pair must appear often enough before being merged.
        # A pair must occur at least this many times. we have set it to 2
        min_frequency=min_frequency,
         # Add required special tokens to the vocabulary.
        # Reserve vocabulary entries for these markers.
        special_tokens=special_tokens,
        initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
        show_progress=True,
    )

    num_documents, total_chars, count_consumption = _count_texts(paths)
    if num_documents == 0:
        raise ValueError("No training text found for tokenizer.")

    # 3. Study the training documents and build the vocabulary.
    training_consumption: list[dict[str, object]] = []
    tokenizer.train_from_iterator(
        _iter_texts(paths, consumed_files=training_consumption),
        trainer=trainer,
        length=num_documents,
    )

    total_tokens = 0
    scoring_consumption: list[dict[str, object]] = []
    for text in _iter_texts(paths, consumed_files=scoring_consumption):
        total_tokens += len(tokenizer.encode(text).ids)

    for observed in (training_consumption, scoring_consumption):
        _assert_consumption_matches(
            count_consumption,
            observed,
            message="Tokenizer inputs changed between tokenizer passes.",
        )
    if expected_consumption is not None:
        _assert_consumption_matches(
            expected_consumption,
            scoring_consumption,
            message="Tokenizer consumed bytes differ from the approved sample manifest.",
        )

    tokenizer_path = out / "tokenizer.json"
    # Save only after every consumed pass has been proven identical.
    tokenizer.save(str(tokenizer_path))

    # Ask the trained tokenizer for each special token's ID.
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
        "consumed_input": _consumed_stream_report(scoring_consumption),
    }
    if probe_sets_path is not None:
        report["fertility"] = measure_tokenizer_fertility(
            tokenizer,
            load_probe_sets(probe_sets_path),
        )
    (out / "tokenizer_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def train_tokenizer_from_manifest(
    manifest_path: str | Path,
    output_dir: str | Path,
    vocab_size: int,
    min_frequency: int,
    special_tokens: list[str],
    probe_sets_path: str | Path | None = None,
) -> dict[str, object]:
    """Train from every fit chunk after verifying the bounded sample manifest."""

    if vocab_size != REQUIRED_VOCAB_SIZE:
        raise ValueError("Tokenizer vocab_size must be exactly 32768.")
    if tuple(special_tokens) != REQUIRED_SPECIAL_TOKENS:
        raise ValueError("Tokenizer requires the exact ordered special tokens.")
    manifest, paths_by_split, artifacts = _load_verified_sample_manifest(manifest_path)
    if not paths_by_split["fit"]:
        raise ValueError("Sample manifest contains no fit chunks.")
    report = train_tokenizer_from_jsonl(
        paths_by_split["fit"],
        output_dir,
        vocab_size,
        min_frequency,
        special_tokens,
        probe_sets_path,
        expected_consumption=_expected_consumption(paths_by_split["fit"], artifacts),
    )
    if report.get("algorithm") != "byte_level_bpe":
        raise ValueError("Tokenizer algorithm must be byte_level_bpe.")
    if report.get("vocab_size_requested") != REQUIRED_VOCAB_SIZE:
        raise ValueError("Tokenizer vocab_size_requested must be exactly 32768.")
    if report.get("vocab_size_actual") != REQUIRED_VOCAB_SIZE:
        raise ValueError("Tokenizer vocab_size_actual must be exactly 32768.")
    if not has_required_special_token_ids(report.get("special_token_ids")):
        raise ValueError("Tokenizer special token IDs do not match the required order.")
    report["fitting_manifest_sha256"] = manifest["manifest_sha256"]
    report_path = Path(output_dir) / "tokenizer_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


@dataclass
class _MetricAccumulator:
    documents: int = 0
    tokens: int = 0
    utf8_bytes: int = 0
    words: int = 0
    tokens_per_word: array = field(default_factory=lambda: array("d"))

    def add(self, *, token_count: int, byte_count: int, word_count: int) -> None:
        self.documents += 1
        self.tokens += token_count
        self.utf8_bytes += byte_count
        self.words += word_count
        self.tokens_per_word.append(token_count / max(1, word_count))

    def report(self) -> dict[str, int | float]:
        if not self.documents:
            return {
                "documents": 0,
                "tokens": 0,
                "utf8_bytes": 0,
                "words": 0,
                "tokens_per_word": 0.0,
                "p50_tokens_per_word": 0.0,
                "p95_tokens_per_word": 0.0,
            }
        values = np.asarray(self.tokens_per_word, dtype=np.float64)
        return {
            "documents": self.documents,
            "tokens": self.tokens,
            "utf8_bytes": self.utf8_bytes,
            "words": self.words,
            "tokens_per_word": self.tokens / max(1, self.words),
            "p50_tokens_per_word": float(np.quantile(values, 0.50, method="higher")),
            "p95_tokens_per_word": float(np.quantile(values, 0.95, method="higher")),
        }


def _input_paths_for_evaluation(
    input_paths: list[str | Path],
) -> tuple[list[Path], str | None, list[dict[str, object]] | None]:
    if not input_paths:
        raise ValueError("Tokenizer evaluation requires at least one input path.")
    supplied = [Path(path) for path in input_paths]
    if len(supplied) == 1 and supplied[0].name == "manifest.json":
        manifest, paths_by_split, artifacts = _load_verified_sample_manifest(supplied[0])
        if not paths_by_split["holdout"]:
            raise ValueError("Sample manifest contains no holdout chunks.")
        return (
            paths_by_split["holdout"],
            str(manifest["manifest_sha256"]),
            _expected_consumption(paths_by_split["holdout"], artifacts),
        )

    candidate_chunks = [
        path
        for path in supplied
        if path.parent.name == "holdout"
        and _CHUNK_NAME.fullmatch(path.name) is not None
    ]
    if candidate_chunks:
        if len(candidate_chunks) != len(supplied):
            raise ValueError("Cannot mix sample holdout chunks with arbitrary inputs.")
        roots = {path.parent.parent.resolve() for path in supplied}
        if len(roots) != 1:
            raise ValueError("Sample holdout chunks must share one manifest root.")
        root = next(iter(roots))
        manifest, paths_by_split, artifacts = _load_verified_sample_manifest(
            root / "manifest.json"
        )
        expected = [path.resolve() for path in paths_by_split["holdout"]]
        if [path.resolve() for path in supplied] != expected:
            raise ValueError("Evaluation must use every holdout chunk in manifest order.")
        return (
            paths_by_split["holdout"],
            str(manifest["manifest_sha256"]),
            _expected_consumption(paths_by_split["holdout"], artifacts),
        )

    for path in supplied:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Tokenizer evaluation input must be a real file: {path}")
    return supplied, None, None


def _required_dimension(record: Mapping[str, Any], field_name: str, path: Path) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Evaluation record in {path} has invalid {field_name}.")
    return value


def _special_token_failures(
    tokenizer: Tokenizer, metadata: Mapping[str, Any]
) -> list[dict[str, object]]:
    recorded = metadata.get("special_token_ids")
    if not isinstance(recorded, Mapping) or not recorded:
        return [{"reason": "missing_special_token_ids"}]
    failures: list[dict[str, object]] = []
    if not has_required_special_token_ids(recorded):
        failures.append(
            {
                "reason": "special_token_set_mismatch",
                "expected": REQUIRED_SPECIAL_TOKEN_IDS,
                "recorded": dict(recorded),
            }
        )
    vocabulary_size = tokenizer.get_vocab_size()
    for token, required_id in REQUIRED_SPECIAL_TOKEN_IDS.items():
        recorded_id = recorded.get(token)
        actual_id = tokenizer.token_to_id(str(token))
        if (
            not isinstance(recorded_id, int)
            or isinstance(recorded_id, bool)
            or recorded_id < 0
            or recorded_id >= vocabulary_size
            or recorded_id != required_id
            or actual_id != recorded_id
        ):
            failures.append(
                {
                    "token": token,
                    "recorded_id": recorded_id,
                    "actual_id": actual_id,
                }
            )
    return failures


def _tokenizer_identity_failures(
    tokenizer: Tokenizer, metadata: Mapping[str, Any]
) -> list[str]:
    failures: list[str] = []
    if (
        metadata.get("algorithm") != "byte_level_bpe"
        or type(tokenizer.model).__name__ != "BPE"
        or type(tokenizer.pre_tokenizer).__name__ != "ByteLevel"
        or type(tokenizer.decoder).__name__ != "ByteLevel"
    ):
        failures.append("algorithm")
    if metadata.get("vocab_size_requested") != REQUIRED_VOCAB_SIZE:
        failures.append("vocab_size_requested")
    if metadata.get("vocab_size_actual") != REQUIRED_VOCAB_SIZE:
        failures.append("vocab_size_actual")
    if tokenizer.get_vocab_size() != REQUIRED_VOCAB_SIZE:
        failures.append("tokenizer_vocab_size")
    special_token_ids = metadata.get("special_token_ids")
    if not has_required_special_token_ids(special_token_ids):
        failures.append("special_token_ids")
    return failures


def evaluate_tokenizer_on_jsonl(
    tokenizer_dir: str | Path,
    input_paths: list[str | Path],
    probe_sets_path: str | Path,
) -> dict[str, object]:
    """Evaluate one tokenizer on a verified shared holdout and fixed probes."""

    paths, manifest_sha256, expected_consumption = _input_paths_for_evaluation(
        input_paths
    )
    tokenizer_path = Path(tokenizer_dir) / "tokenizer.json"
    tokenizer_sha256 = sha256_file(tokenizer_path)
    tokenizer = load_tokenizer(tokenizer_dir)
    if sha256_file(tokenizer_path) != tokenizer_sha256:
        raise ValueError("Tokenizer bytes changed during evaluation.")
    probe_path = Path(probe_sets_path)
    if probe_path.is_symlink() or not probe_path.is_file():
        raise ValueError("Tokenizer probe set must be a real file.")
    probe_sets_sha256 = sha256_file(probe_path)
    probe_sets = load_probe_sets(probe_path)
    if sha256_file(probe_path) != probe_sets_sha256:
        raise ValueError("Tokenizer probe bytes changed during evaluation.")
    pre_consumption = [
        {
            "path": str(path),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
            "records": sum(1 for _ in _read_jsonl_records(path)),
        }
        for path in paths
    ]

    overall = _MetricAccumulator()
    roles: dict[str, _MetricAccumulator] = {}
    sources: dict[str, _MetricAccumulator] = {}
    buckets: dict[str, _MetricAccumulator] = {}
    round_trip_failures = 0
    round_trip_failure_details: list[dict[str, object]] = []
    consumed_files: list[dict[str, object]] = []
    for path in paths:
        for record_index, record in enumerate(
            _read_jsonl_records(path, consumed_files=consumed_files), start=1
        ):
            text = str(record["text"])
            role = _required_dimension(record, "role", path)
            source = _required_dimension(record, "source_id", path)
            raw_bucket = record.get("bucket_id")
            if raw_bucket is not None and (
                not isinstance(raw_bucket, str) or not raw_bucket.strip()
            ):
                raise ValueError(f"Evaluation record in {path} has invalid bucket_id.")
            bucket = raw_bucket if raw_bucket is not None else "__none__"
            token_ids = [int(token_id) for token_id in tokenizer.encode(text).ids]
            if not token_ids:
                raise ValueError(f"Tokenizer produced no IDs for holdout text in {path}.")
            decoded = tokenizer.decode(token_ids)
            if decoded != text:
                round_trip_failures += 1
                if len(round_trip_failure_details) < _MAX_FAILURE_DETAILS:
                    round_trip_failure_details.append(
                        {
                            "path": str(path),
                            "record": record_index,
                            "content_sha256": record["content_sha256"],
                        }
                    )
            measurements = {
                "token_count": len(token_ids),
                "byte_count": len(text.encode("utf-8")),
                "word_count": len(WORD_PATTERN.findall(text)),
            }
            overall.add(**measurements)
            roles.setdefault(role, _MetricAccumulator()).add(**measurements)
            sources.setdefault(source, _MetricAccumulator()).add(**measurements)
            buckets.setdefault(bucket, _MetricAccumulator()).add(**measurements)

    if not overall.documents:
        raise ValueError("Tokenizer evaluation inputs contain no documents.")
    _assert_consumption_matches(
        pre_consumption,
        consumed_files,
        message="Tokenizer evaluation inputs changed during scoring.",
    )
    if expected_consumption is not None:
        _assert_consumption_matches(
            expected_consumption,
            consumed_files,
            message="Tokenizer evaluation inputs changed after manifest verification.",
        )

    probe_groups: dict[str, dict[str, int | float]] = {}
    probe_overall = _MetricAccumulator()
    for group_name, texts in sorted(probe_sets.items()):
        group = _MetricAccumulator()
        for probe_index, text in enumerate(texts, start=1):
            token_ids = [int(token_id) for token_id in tokenizer.encode(text).ids]
            if not token_ids:
                raise ValueError(f"Tokenizer produced no IDs for probe {text!r}.")
            if tokenizer.decode(token_ids) != text:
                round_trip_failures += 1
                if len(round_trip_failure_details) < _MAX_FAILURE_DETAILS:
                    round_trip_failure_details.append(
                        {"probe_group": group_name, "probe": probe_index}
                    )
            measurements = {
                "token_count": len(token_ids),
                "byte_count": len(text.encode("utf-8")),
                "word_count": len(WORD_PATTERN.findall(text)),
            }
            group.add(**measurements)
            probe_overall.add(**measurements)
        probe_groups[group_name] = group.report()

    try:
        tokenizer_metadata = load_tokenizer_metadata(tokenizer_dir)
    except (OSError, json.JSONDecodeError):
        tokenizer_metadata = {}
    if not isinstance(tokenizer_metadata, Mapping) or not tokenizer_metadata:
        tokenizer_metadata = {}
        special_token_failure_details = [
            {"reason": "missing_or_invalid_special_token_metadata"}
        ]
    else:
        special_token_failure_details = _special_token_failures(
            tokenizer, tokenizer_metadata
        )
    tokenizer_identity_failure_details = _tokenizer_identity_failures(
        tokenizer, tokenizer_metadata
    )
    overall_report = overall.report()
    probe_report = probe_overall.report()
    if (
        sha256_file(tokenizer_path) != tokenizer_sha256
        or sha256_file(probe_path) != probe_sets_sha256
    ):
        raise ValueError("Tokenizer or probe bytes changed during evaluation.")
    special_tokens = tokenizer_metadata.get("special_token_ids")
    return {
        **overall_report,
        "roles": {name: accumulator.report() for name, accumulator in sorted(roles.items())},
        "sources": {
            name: accumulator.report() for name, accumulator in sorted(sources.items())
        },
        "buckets": {
            name: accumulator.report() for name, accumulator in sorted(buckets.items())
        },
        "probe_metrics": {"overall": probe_report, "groups": probe_groups},
        "probe_p50_tokens_per_word": probe_report["p50_tokens_per_word"],
        "probe_p95_tokens_per_word": probe_report["p95_tokens_per_word"],
        "round_trip_failures": round_trip_failures,
        "round_trip_failure_details": round_trip_failure_details,
        "special_token_failures": len(special_token_failure_details),
        "special_token_failure_details": special_token_failure_details,
        "tokenizer_identity_failures": len(tokenizer_identity_failure_details),
        "tokenizer_identity_failure_details": tokenizer_identity_failure_details,
        "algorithm": tokenizer_metadata.get("algorithm"),
        "vocab_size_requested": tokenizer_metadata.get("vocab_size_requested"),
        "vocab_size_actual": tokenizer_metadata.get("vocab_size_actual"),
        "special_token_ids": tokenizer_metadata.get("special_token_ids"),
        "input_file_checksums": [
            {
                "path": file["path"],
                "size": file["size"],
                "sha256": file["sha256"],
            }
            for file in consumed_files
        ],
        "input_files_sha256": _consumed_stream_report(consumed_files)["sha256"],
        "consumed_input": _consumed_stream_report(consumed_files),
        "probe_sets_sha256": probe_sets_sha256,
        "special_tokens_sha256": sha256_json(special_tokens),
        "sample_manifest_sha256": manifest_sha256,
        "tokenizer_sha256": tokenizer_sha256,
    }


def train_tokenizer_from_config(cfg: dict) -> dict[str, object]:

    ds_cfg = cfg["dataset"]
    normalized_dir = Path(ds_cfg["normalized_dir"])
    training_splits = ds_cfg.get("training_splits")
    if training_splits:
        input_paths = [
            normalized_dir / f"{split}.jsonl"
            for split in dict.fromkeys(training_splits.values())
        ]
    else:
        input_paths = [normalized_dir / f"{ds_cfg['train_split']}.jsonl"]

    tokenizer_cfg = cfg["tokenizer"]
    return train_tokenizer_from_jsonl(
        input_paths=input_paths,
        output_dir=tokenizer_cfg["output_dir"],
        vocab_size=tokenizer_cfg["vocab_size"],
        min_frequency=tokenizer_cfg["min_frequency"],
        special_tokens=tokenizer_cfg["special_tokens"],
        probe_sets_path=tokenizer_cfg.get("probe_sets_path"),
    )
