# Telco Resumable Local Corpus Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare the selected-tokenizer 20M pilot and 12B main/cooldown corpus on a 24GB-RAM Mac in one exact-tokenization pass, publish bounded immutable text and uint16 token artifacts through Google Drive Stream files, and resume safely after interruption without starting model training.

**Architecture:** Extend the transactional journal from the tokenizer-candidate increment with a batch encoder, bounded packed-shard writer, disk guard, checksummed Drive publisher, and deterministic source-window orchestrator. Each committed unit contains immutable normalized JSONL and token artifacts no larger than the configured limits. The first full execution stops after a committed unit reaches at least 100M accepted quota tokens; `full_resume` continues the identical build identity to completion.

**Tech Stack:** Python 3.10+, Hugging Face `datasets` and `tokenizers`, SQLite, NumPy, psutil, PyYAML, JSON/JSONL, Jupyter Notebook JSON, pytest, Google Drive File Provider.

**Prerequisite:** Complete `docs/superpowers/plans/2026-08-09-telco-200m-tokenizer-candidate.md`, review its comparison, and create an approved tokenizer selection record. This plan consumes that record and never chooses a tokenizer itself.

## Global constraints

- `origin/main` remains canonical; execute on the feature branch and worktree created for this effort.
- Main and cooldown plans remain 10B and 2B quota tokens respectively.
- Quota tokens count tokenizer IDs before EOS; packed training tokens include one EOS per accepted document.
- Preserve whole-document quota behavior: the final document for an item may overshoot its exact target, and the recorded overshoot must be no greater than that document's token count.
- Use the existing `uint16`, `append_eos=True`, `shard_size_tokens=50_000_000` metadata contract. A safely sealed calibration, raw-size, or item-boundary shard may be shorter than the maximum.
- Use batch tokenization exactly once for every quality-accepted document. The same IDs drive exact quotas and binary output.
- Apply exact deduplication across sources, main, cooldown, validation, chunks, and resumes within a full-build identity. A pilot refresh is a separate fingerprinted build and deduplicates across all of its own sources, validation records, chunks, and resumes.
- Hold local active plus sealed-but-unpublished files below 20GiB; pause before filesystem free space falls below 25GiB by default.
- Publish only closed, fsynced, checksummed files beneath a fingerprinted Drive staging root.
- Never write a complete corpus manifest until every required quota, checksum, and license audit passes.
- Never delete old pilot artifacts or `.full.staging-*` directories.
- No code in this plan starts smoke, pilot, full, or evaluation model jobs.

---

## File structure

- `matgpt/data/local_tokens.py`: batch encoding and bounded packed token shard writer.
- `matgpt/data/local_publish.py`: disk guard, Drive staging publisher, checksum verification, and backpressure.
- `matgpt/data/local_corpus.py`: deterministic source windows, exact quotas, raw/token unit construction, retries, progress, calibration stop, and completion.
- `matgpt/data/local_state.py`: extend the journal with counters, artifact reconciliation, and clean-stop state.
- `matgpt/data/shard.py`: shared metadata construction for existing and local builders.
- `matgpt/data/telco_prepare.py`: recognize complete chunked manifests with exact tokenizer quotas.
- `matgpt/preflight.py`: validate published local-builder shard metadata without weakening existing checks.
- `scripts/prepare_telco_local.py`: add `pilot_refresh`, `full_calibration`, `full_resume`, and `status` stages.
- `notebooks/prepare_matgpt_telco_300m_local.ipynb`: extend the local data-only stage selector.
- `notebooks/train_matgpt_telco_300m_colab.ipynb`: restore and validate finalized prebuilt shards without re-tokenization.
- `docs/runbooks/local-telco-300m-data.md`: exact local, Drive, calibration, resume, Colab, and recovery commands.
- `tests/test_local_tokens.py`: batch/per-document and shard-byte equivalence.
- `tests/test_local_publish.py`: disk floor, spool cap, checksum mismatch, and reconciliation.
- `tests/test_local_corpus.py`: quota, one-pass, dedup, resume, retry, failure, and completion tests.
- `tests/test_telco_notebook_local.py`: local stage and no-training safety tests.
- `tests/test_telco_notebook_colab.py`: prebuilt-shard restore and manual full gate tests.

---

### Task 1: Batch-encode once and write bounded compatible token shards

**Files:**
- Create: `matgpt/data/local_tokens.py`
- Create: `tests/test_local_tokens.py`
- Modify: `matgpt/data/shard.py`
- Modify: `tests/test_shards.py`

**Interfaces:**
- Produces: `EncodedRecord`, `encode_record_batch`, `PackedShardWriter`, and `build_split_metadata`.
- `PackedShardWriter` accepts already encoded documents, appends EOS, emits immutable shards at or below the configured token maximum, and never holds a 50M-element Python list.

- [ ] **Step 1: Write a failing batch-equivalence test**

```python
import json
from pathlib import Path

from tokenizers import Tokenizer, models, pre_tokenizers

from matgpt.data.local_tokens import encode_record_batch


def _word_tokenizer(path: Path) -> Path:
    path.mkdir()
    tokenizer = Tokenizer(
        models.WordLevel(
            vocab={"[UNK]": 0, "<|eos|>": 1, "router": 2, "packet": 3},
            unk_token="[UNK]",
        )
    )
    tokenizer.pre_tokenizer = pre_tokenizers.WhitespaceSplit()
    tokenizer.save(str(path / "tokenizer.json"))
    return path


def test_batch_encoding_matches_individual_encoding(tmp_path: Path):
    tokenizer_dir = _word_tokenizer(tmp_path / "tokenizer")
    tokenizer = Tokenizer.from_file(str(tokenizer_dir / "tokenizer.json"))
    records = [
        {"document_id": "a", "text": "router packet"},
        {"document_id": "b", "text": "packet router router"},
    ]

    encoded = encode_record_batch(tokenizer, records)

    assert [item.ids for item in encoded] == [
        tuple(tokenizer.encode(record["text"]).ids) for record in records
    ]
    assert [item.quota_tokens for item in encoded] == [2, 3]
```

- [ ] **Step 2: Write a failing packed-byte equivalence test**

```python
import numpy as np

from matgpt.data.local_tokens import PackedShardWriter
from matgpt.data.shard import tokenize_jsonl_to_shards


def test_streaming_writer_matches_reference_bytes(tmp_path: Path):
    tokenizer_dir = _word_tokenizer(tmp_path / "tokenizer")
    tokenizer = Tokenizer.from_file(str(tokenizer_dir / "tokenizer.json"))
    metadata = {
        "tokenizer_sha256": "0" * 64,
        "special_token_ids": {"<|eos|>": 1},
    }
    (tokenizer_dir / "special_tokens.json").write_text(
        json.dumps(metadata) + "\n", encoding="utf-8"
    )
    records = [
        {"document_id": "a", "text": "router packet"},
        {"document_id": "b", "text": "packet router router"},
    ]
    source = tmp_path / "records.jsonl"
    source.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    reference = tokenize_jsonl_to_shards(
        source, tokenizer_dir, tmp_path / "reference", "main", 4
    )

    writer = PackedShardWriter(
        output_dir=tmp_path / "streaming",
        split="main",
        dtype="uint16",
        shard_size_tokens=4,
        eos_id=1,
    )
    for item in encode_record_batch(tokenizer, records):
        writer.append_document(item.ids)
    actual = writer.finalize()

    expected_bytes = b"".join(
        Path(shard["path"]).read_bytes() for shard in reference["shards"]
    )
    actual_bytes = b"".join(Path(shard["path"]).read_bytes() for shard in actual)
    assert actual_bytes == expected_bytes
    assert sum(shard["num_tokens"] for shard in actual) == 7
    assert np.fromfile(actual[0]["path"], dtype=np.uint16).tolist() == [2, 3, 1, 3]
```

- [ ] **Step 3: Run the focused tests and verify RED**

```bash
uv run --extra test pytest tests/test_local_tokens.py -q
```

Expected: collection fails because `matgpt.data.local_tokens` does not exist.

- [ ] **Step 4: Implement batch encoding and the bounded writer**

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
from tokenizers import Tokenizer

from matgpt.utils.hashing import sha256_file


@dataclass(frozen=True)
class EncodedRecord:
    record: Mapping[str, object]
    ids: tuple[int, ...]

    @property
    def quota_tokens(self) -> int:
        return len(self.ids)


def encode_record_batch(
    tokenizer: Tokenizer,
    records: Sequence[Mapping[str, object]],
) -> list[EncodedRecord]:
    encodings = tokenizer.encode_batch([str(record["text"]) for record in records])
    return [
        EncodedRecord(record=record, ids=tuple(int(token_id) for token_id in encoding.ids))
        for record, encoding in zip(records, encodings, strict=True)
    ]
```

Implement `PackedShardWriter` with a binary `.partial` handle and a small
NumPy block per append. Slice each document's IDs plus EOS at shard boundaries,
write `np.asarray(piece, dtype=np.uint16).tobytes(order="C")`, flush and
`os.fsync` before rename, then return `path` as the absolute local path,
`relative_path` as the safe publication path, index, byte size, token count, and
SHA-256. `build_split_metadata` drops the local `path` and writes
`relative_path` into its public `path` field. Reject token IDs outside the dtype
range. `seal_unit()` may
close a short immutable shard for a calibration, raw-byte, or item boundary;
`finalize()` seals only a non-empty remainder.

- [ ] **Step 5: Extract shared metadata construction**

Move metadata assembly in `matgpt/data/shard.py` behind:

```python
def build_split_metadata(
    *,
    split: str,
    tokenizer_sha256: str,
    dtype: str,
    append_eos: bool,
    shard_size_tokens: int,
    total_documents: int,
    shards: list[dict[str, object]],
) -> dict[str, object]:
```

Both the existing JSONL sharder and the local builder must call it. Store paths
relative to the shard metadata directory in newly generated metadata; retain a
reader compatibility test for existing absolute-path metadata.

- [ ] **Step 6: Verify focused and regression tests**

```bash
uv run --extra test pytest tests/test_local_tokens.py tests/test_shards.py tests/test_pretrain_smoke.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit batch packing**

```bash
git add matgpt/data/local_tokens.py matgpt/data/shard.py tests/test_local_tokens.py tests/test_shards.py
git commit -m "feat: stream exact tokens into bounded shards"
```

---

### Task 2: Enforce local disk limits and checksummed Drive publication

**Files:**
- Create: `matgpt/data/local_publish.py`
- Create: `tests/test_local_publish.py`
- Modify: `matgpt/data/local_state.py`
- Modify: `tests/test_local_build_state.py`

**Interfaces:**
- Produces: `StoragePolicy`, `StorageSnapshot`, `StoragePressure`, and `DrivePublisher`.
- Publisher lifecycle: `check_capacity`, `publish`, `reconcile`, and `status`.

- [ ] **Step 1: Write failing capacity and checksum tests**

```python
from pathlib import Path

import pytest

from matgpt.data.local_publish import (
    DrivePublisher,
    StoragePolicy,
    StoragePressure,
)


def test_capacity_pauses_before_free_floor(tmp_path: Path):
    publisher = DrivePublisher(
        local_root=tmp_path / "local",
        destination_root=tmp_path / "drive",
        policy=StoragePolicy(max_working_bytes=1_000, min_free_bytes=500),
        free_bytes=lambda _path: 499,
    )

    with pytest.raises(StoragePressure, match="free disk floor"):
        publisher.check_capacity(next_unit_bytes=1)


def test_publish_rechecks_destination_bytes_and_sha(tmp_path: Path):
    local = tmp_path / "local"
    local.mkdir()
    artifact = local / "main_00000.bin"
    artifact.write_bytes(b"abcdef")
    publisher = DrivePublisher(
        local_root=local,
        destination_root=tmp_path / "drive",
        policy=StoragePolicy(max_working_bytes=1_000, min_free_bytes=1),
        free_bytes=lambda _path: 10_000,
    )

    published = publisher.publish(artifact, "shards/main_00000.bin")

    assert published.size == 6
    assert Path(published.destination).read_bytes() == b"abcdef"
    assert published.sha256 == published.destination_sha256
```

- [ ] **Step 2: Write a failing corruption and reconciliation test**

```python
def test_reconcile_refuses_corrupt_destination(tmp_path: Path):
    local = tmp_path / "local"
    destination = tmp_path / "drive"
    local.mkdir()
    artifact = local / "chunk.jsonl"
    artifact.write_text("valid\n", encoding="utf-8")
    publisher = DrivePublisher(
        local_root=local,
        destination_root=destination,
        policy=StoragePolicy(max_working_bytes=1_000, min_free_bytes=1),
        free_bytes=lambda _path: 10_000,
    )
    published = publisher.publish(artifact, "text/chunk.jsonl")
    Path(published.destination).write_text("corrupt\n", encoding="utf-8")

    with pytest.raises(ValueError, match="checksum mismatch"):
        publisher.reconcile(published)
```

- [ ] **Step 3: Run tests and verify RED**

```bash
uv run --extra test pytest tests/test_local_publish.py -q
```

Expected: collection fails because `matgpt.data.local_publish` is absent.

- [ ] **Step 4: Implement capacity evidence and backpressure**

```python
@dataclass(frozen=True)
class StoragePolicy:
    max_working_bytes: int
    min_free_bytes: int


class StoragePressure(RuntimeError):
    pass


def check_capacity(self, next_unit_bytes: int) -> StorageSnapshot:
    active = sum(
        path.stat().st_size
        for path in self.local_root.rglob("*")
        if path.is_file()
    )
    free = int(self.free_bytes(self.local_root))
    if free - next_unit_bytes < self.policy.min_free_bytes:
        raise StoragePressure("free disk floor would be crossed")
    if active + next_unit_bytes > self.policy.max_working_bytes:
        raise StoragePressure("local working-set cap would be crossed")
    return StorageSnapshot(active_bytes=active, free_bytes=free)
```

Default `free_bytes` to `shutil.disk_usage(path).free`. Validate both roots are
absolute, distinct, and neither contains the other. Reject symlinks that escape
either root.

- [ ] **Step 5: Implement safe publication and journal reconciliation**

Copy to `<destination>.partial`, flush and fsync, rename atomically within the
destination directory, then re-read destination size and SHA-256. Never remove
the local sealed artifact before the journal records `published=1`. If the
destination already exists, accept it only when size and SHA match. Place a
checksum mismatch under `quarantine/` with a timestamp and fail; do not delete
the source artifact.

Extend `BuildJournal` with `artifact(unit_id, relative_path)`,
`mark_published(unit_id, relative_path, destination_sha256)`, and
`unpublished_artifacts()`. Require the destination hash to equal the committed
source hash in the same SQLite transaction.

- [ ] **Step 6: Verify publication behavior**

```bash
uv run --extra test pytest tests/test_local_publish.py tests/test_local_build_state.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit the publisher**

```bash
git add matgpt/data/local_publish.py matgpt/data/local_state.py tests/test_local_publish.py tests/test_local_build_state.py
git commit -m "feat: publish telco artifacts with disk guards"
```

---

### Task 3: Build the exact, deterministic, resumable corpus in one pass

**Files:**
- Create: `matgpt/data/local_corpus.py`
- Create: `tests/test_local_corpus.py`
- Modify: `matgpt/data/telco_prepare.py`
- Modify: `matgpt/data/quality.py`
- Modify: `matgpt/data/local_state.py`

**Interfaces:**
- Produces: `LocalCorpusRequest`, `LocalCorpusProgress`, `LocalCorpusResult`, and `build_local_corpus`.
- Consumes the approved tokenizer-selection record, main/cooldown plans, source registry, compiled matcher, journal, token writer, and publisher.

- [ ] **Step 1: Add a complete deterministic synthetic fixture**

Put these helpers at the top of `tests/test_local_corpus.py` so later tests have
no hidden dependency:

```python
import json
from pathlib import Path

from matgpt.data.local_corpus import LocalCorpusRequest
from matgpt.data.quality import DataQualityPolicy
from matgpt.data.sources import load_source_registry
from matgpt.tokenizer.train import train_tokenizer_from_jsonl
from matgpt.utils.hashing import sha256_file


REGISTRY_PATH = Path("configs/data/telco_300m_sources.yaml")
def _tiny_plan(stage: str) -> dict:
    items = [
        {
            "id": "common_pile_wikimedia",
            "source_id": "common_pile_wikimedia",
            "bucket_id": None,
            "role": "pretrain_general",
            "token_quota": 12,
        },
        {
            "id": "common_pile_github_archive",
            "source_id": "common_pile_github_archive",
            "bucket_id": None,
            "role": "pretrain_structured",
            "token_quota": 12,
        },
    ]
    for bucket in ("three_gpp", "rfc", "research", "patents", "semantic"):
        items.append(
            {
                "id": f"telco_common_corpus/{bucket}",
                "source_id": "telco_common_corpus",
                "bucket_id": bucket,
                "role": "pretrain_telecom",
                "token_quota": 12,
            }
        )
    items.sort(key=lambda item: item["id"])
    return {
        "version": 1,
        "stage": stage,
        "seed": 42,
        "total_tokens": 84,
        "quota_tolerance": 0.03,
        "validation_fraction": 0.2,
        "buffer_size": 3,
        "role_quotas": {
            "pretrain_general": 12,
            "pretrain_structured": 12,
            "pretrain_telecom": 60,
        },
        "items": items,
        "plan_sha256": (stage + "0" * 64)[:64],
    }


def _rows(kind: str) -> list[dict]:
    if kind == "general":
        return [{"text": f"general router prose {index}"} for index in range(50)]
    if kind == "structured":
        return [{"text": f"interface route code {index}"} for index in range(50)]
    collections = {
        "3GPP-TSG": "3GPP license",
        "IETF-RFCs": "IETF license",
        "IEEE-Access": "CC-BY-4.0",
        "USPTO": "public domain",
        "Wikidata-Telecom": "CC0-1.0",
    }
    return [
        {
            "identifier": f"{collection}-{index}",
            "collection": collection,
            "license": license_name,
            "token_count": 4,
            "text": f"telecom {collection} document {index}",
        }
        for collection, license_name in collections.items()
        for index in range(50)
    ]


def _loader(hf_name: str, **kwargs):
    if hf_name == "GSMA/Telco-Common-Corpus":
        return iter(_rows("telecom"))
    paths = kwargs.get("data_files") or []
    kind = "structured" if any("github_archive" in path for path in paths) else "general"
    return iter(_rows(kind))


def _write_tokenizer(root: Path) -> Path:
    tokenizer_dir = root / "tokenizer"
    fitting = root / "tokenizer_fit.jsonl"
    texts = [
        "general router prose interface route code telecom document",
        "🙂 café 你好 A space, then punctuation!",
        "3GPP RRC O-RAN IPv6 packet forwarding and radio access network",
    ]
    fitting.write_text(
        "".join(json.dumps({"text": text}) + "\n" for text in texts),
        encoding="utf-8",
    )
    train_tokenizer_from_jsonl(
        [fitting],
        tokenizer_dir,
        vocab_size=320,
        min_frequency=1,
        special_tokens=[
            "<|pad|>",
            "<|bos|>",
            "<|eos|>",
            "<|system|>",
            "<|user|>",
            "<|assistant|>",
            "<|end|>",
        ],
    )
    return tokenizer_dir


def make_corpus_request(
    root: Path,
    *,
    plans: list[dict],
    retry_delays: tuple[float, ...] = (0.0,),
) -> LocalCorpusRequest:
    root.mkdir(parents=True, exist_ok=True)
    tokenizer_dir = _write_tokenizer(root)
    tokenizer_sha = sha256_file(tokenizer_dir / "tokenizer.json")
    selection = root / "selection.json"
    selection.write_text(
        json.dumps(
            {
                "approved": True,
                "winner": "representative_200m",
                "selected_tokenizer_sha256": tokenizer_sha,
                "comparison_sha256": "c" * 64,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return LocalCorpusRequest(
        registry=load_source_registry(REGISTRY_PATH),
        plans=tuple(plans),
        tokenizer_dir=tokenizer_dir,
        tokenizer_selection_path=selection,
        local_root=root / "local",
        destination_root=root / "drive",
        quality_policy=DataQualityPolicy(
            enabled=True,
            min_chars=2,
            exact_dedup=True,
            contamination_patterns=[],
        ),
        batch_documents=4,
        shard_size_tokens=24,
        raw_unit_bytes=2_048,
        max_working_bytes=20 * 1024**2,
        min_free_bytes=1024**2,
        progress_interval_seconds=0,
        retry_delays=retry_delays,
    )
```

- [ ] **Step 2: Write a failing one-pass quota and global-dedup test**

```python
from collections import Counter

from matgpt.data.local_corpus import LocalCorpusRequest, build_local_corpus


def test_builder_counts_once_and_deduplicates_across_stages(
    tmp_path: Path, monkeypatch
):
    import matgpt.data.local_corpus as local_corpus

    encode_calls = Counter()
    real_encode = local_corpus.encode_record_batch

    def observed_encode(tokenizer, records):
        encode_calls.update(record["content_sha256"] for record in records)
        return real_encode(tokenizer, records)

    monkeypatch.setattr(local_corpus, "encode_record_batch", observed_encode)
    request = make_corpus_request(
        tmp_path,
        plans=[_tiny_plan("main"), _tiny_plan("cooldown")],
    )

    result = build_local_corpus(request, dataset_loader=_loader)

    assert result.status == "complete"
    assert all(count == 1 for count in encode_calls.values())
    assert result.manifest["quota_counting"]["method"] == "tokenizer_exact_one_pass"
    assert result.manifest["quality_filter"]["exact_dedup"] is True
    assert result.manifest["complete"] is True
```

The helper above writes a valid selected-tokenizer record, creates separate
`local` and `drive` roots, uses four-document batches, 24-token shard limits,
2KiB raw-unit limits, a 20MiB working cap, and a 1MiB free floor.

- [ ] **Step 3: Write failing resume and calibration-continuation tests**

```python
import pytest


def _artifact_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix in {".jsonl", ".bin"}
    }


def test_forced_interruption_resumes_byte_identically(tmp_path: Path):
    resumed_request = make_corpus_request(tmp_path / "resume", plans=[_tiny_plan("main")])
    commits = 0

    def stop_after_second(_unit):
        nonlocal commits
        commits += 1
        if commits == 2:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        build_local_corpus(
            resumed_request,
            dataset_loader=_loader,
            on_unit_committed=stop_after_second,
        )
    resumed = build_local_corpus(resumed_request, dataset_loader=_loader)

    clean_request = make_corpus_request(tmp_path / "clean", plans=[_tiny_plan("main")])
    clean = build_local_corpus(clean_request, dataset_loader=_loader)

    assert resumed.manifest["content_sha256"] == clean.manifest["content_sha256"]
    assert _artifact_bytes(resumed_request.destination_root) == _artifact_bytes(
        clean_request.destination_root
    )


def test_calibration_stop_resumes_same_identity(tmp_path: Path):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    calibrated = build_local_corpus(
        request, dataset_loader=_loader, stop_after_quota_tokens=24
    )
    identity = calibrated.build_identity_sha256

    assert calibrated.status == "calibration_complete"
    assert calibrated.accepted_quota_tokens >= 24
    completed = build_local_corpus(request, dataset_loader=_loader)

    assert completed.status == "complete"
    assert completed.build_identity_sha256 == identity
```

- [ ] **Step 4: Write failing retry and hard-failure tests**

Add three deterministic tests:

```python
def test_transient_loader_failure_retries_from_committed_cursor(tmp_path: Path):
    attempts = 0

    def flaky_loader(hf_name: str, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("temporary network failure")
        return _loader(hf_name, **kwargs)

    result = build_local_corpus(
        make_corpus_request(tmp_path, plans=[_tiny_plan("main")], retry_delays=(0.0,)),
        dataset_loader=flaky_loader,
    )
    assert result.status == "complete"
    assert attempts >= 2


def test_unknown_telco_collection_fails_without_manifest(tmp_path: Path):
    def drifting_loader(hf_name: str, **kwargs):
        if hf_name == "GSMA/Telco-Common-Corpus":
            return iter([
                {
                    "identifier": "bad-1",
                    "collection": "UNREVIEWED-COLLECTION",
                    "license": "unknown",
                    "token_count": 4,
                    "text": "schema drift",
                }
            ])
        return _loader(hf_name, **kwargs)

    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    with pytest.raises(ValueError, match="unknown collection"):
        build_local_corpus(request, dataset_loader=drifting_loader)
    assert not (request.destination_root / "manifest.json").exists()


def test_source_exhaustion_fails_without_rebalancing(tmp_path: Path):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    with pytest.raises(ValueError, match="exhausted before quota"):
        build_local_corpus(request, dataset_loader=lambda _name, **_kwargs: iter(()))
    assert not (request.destination_root / "manifest.json").exists()
```

Also add a missing document-license test using a Telco row whose `license` is an
empty string. Assert the error names `document-level license` and no complete
manifest exists.

- [ ] **Step 5: Run tests and verify RED**

```bash
uv run --extra test pytest tests/test_local_corpus.py -q
```

Expected: collection fails because `matgpt.data.local_corpus` is absent.

- [ ] **Step 6: Reuse and harden deterministic resumable source windows**

Reuse `iter_deterministic_source_windows` from the tokenizer plan. It consumes
raw rows until a window contains up to `buffer_size` normalized records, tracks
empty rejected rows in the absolute raw cursor, and sorts with the existing
seed/source/document/content key. Commit only after the current source window is fully processed. On
resume, use `dataset.skip(raw_cursor)` when available and `itertools.islice`
otherwise. This makes the raw cursor sufficient to reconstruct ordering without
storing an in-memory shuffle buffer.

Keep regression tests proving that cursor zero emits the same record order as
`iter_deterministic_buffered` and that resuming at every window boundary
reconstructs the uninterrupted sequence.

- [ ] **Step 7: Implement exact batch quota processing**

Define the request and result boundaries:

```python
@dataclass(frozen=True)
class LocalCorpusRequest:
    registry: SourceRegistry
    plans: tuple[Mapping[str, object], ...]
    tokenizer_dir: Path
    tokenizer_selection_path: Path
    local_root: Path
    destination_root: Path
    quality_policy: DataQualityPolicy
    batch_documents: int = 128
    shard_size_tokens: int = 50_000_000
    raw_unit_bytes: int = 268_435_456
    max_working_bytes: int = 20 * 1024**3
    min_free_bytes: int = 25 * 1024**3
    progress_interval_seconds: float = 30.0
    retry_delays: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0, 16.0)


@dataclass(frozen=True)
class LocalCorpusResult:
    status: str
    build_identity_sha256: str
    accepted_quota_tokens: int
    manifest: Mapping[str, object] | None
```

Load and verify the selected tokenizer SHA before opening the journal. Extend
`QualityFilter` so committed/pending exact-dedup membership can be injected;
do not load every hash into RAM. Normalize and quality-filter first, classify
validation via the existing stable hash, batch encode, then use each encoding
for quota count and token write. Never call `tokenizer.encode` again.

Seal a unit at the first completed source window after any of these conditions:

- packed shard reaches `shard_size_tokens`;
- raw JSONL bytes reach `raw_unit_bytes`;
- a mixture item reaches quota;
- the calibration accepted-token threshold is reached;
- the current stage completes.

The unit may contain zero or more training raw chunks/shards and zero or more
validation raw chunks/shards because a large completed source window can cross
an artifact boundary. No record merely encoded past a completed quota is marked
accepted or added to exact dedup state. Its journal transaction records input cursor, per-item exact
quota counters, document counts, quality counters, accepted hashes, license
counts, and artifact metadata. Publish and mark every artifact before releasing
its local copy.

- [ ] **Step 8: Implement clean stop, retries, and progress evidence**

Register a `SIGINT` handler that sets a stop event. Finish the current raw
window, seal/publish/commit it, write `status="stopped_cleanly"`, then return.
Forced termination leaves only `.partial` files; startup deletes those files
after verifying they are not referenced by a committed unit.

Retry only retryable source exceptions (`TimeoutError`, `ConnectionError`, and
configured HTTP 408/429/5xx) with bounded delays. Schema, collection, license,
fingerprint, quota, and checksum failures are not retried.

Write console and atomic `progress.json` updates at least every configured
interval with stage, source, bucket, cursor, item/stage quota, read/accepted/
held-out/rejected counts, rolling tokens/sec, elapsed, ETA, process RSS, active
local bytes, free bytes, unpublished bytes, published bytes, last unit, and
Drive verification status.

- [ ] **Step 9: Verify the orchestrator and regressions**

```bash
uv run --extra test pytest tests/test_local_corpus.py tests/test_telco_prepare.py tests/test_data_quality.py -q
```

Expected: all tests pass.

- [ ] **Step 10: Commit the one-pass builder**

```bash
git add matgpt/data/local_corpus.py matgpt/data/telco_prepare.py matgpt/data/quality.py matgpt/data/local_state.py tests/test_local_corpus.py tests/test_telco_prepare.py tests/test_data_quality.py
git commit -m "feat: build resumable exact telco corpus"
```

---

### Task 4: Finalize manifests, audits, and preflight compatibility

**Files:**
- Modify: `matgpt/data/local_corpus.py`
- Modify: `matgpt/data/shard.py`
- Modify: `matgpt/data/telco_prepare.py`
- Modify: `matgpt/preflight.py`
- Modify: `tests/test_local_corpus.py`
- Modify: `tests/test_preflight.py`
- Modify: `tests/test_training_core.py`

**Interfaces:**
- Produces a final corpus `manifest.json`, split metadata files, `quota_audit.json`, `license_audit.json`, `quality_audit.json`, and `calibration_report.json`.
- Existing preflight and `PackedTokenDataset` consume finalized published artifacts directly.

- [ ] **Step 1: Write a failing complete-manifest compatibility test**

```python
from matgpt.data.telco_prepare import corpus_has_exact_token_quotas


def test_complete_local_manifest_satisfies_exact_quota_contract(tmp_path: Path):
    request = make_corpus_request(
        tmp_path,
        plans=[_tiny_plan("main"), _tiny_plan("cooldown")],
    )
    result = build_local_corpus(request, dataset_loader=_loader)

    assert result.manifest is not None
    assert corpus_has_exact_token_quotas(
        request.destination_root,
        request.tokenizer_dir,
        request.plans,
    )
    assert result.manifest["complete"] is True
    assert result.manifest["build_identity_sha256"] == result.build_identity_sha256
```

- [ ] **Step 2: Write failing preflight and incomplete-staging tests**

```python
from matgpt.config import clone_config, load_config
from matgpt.preflight import build_preflight_report


def write_preflight_config_for_local_artifacts(
    tmp_path: Path,
    request: LocalCorpusRequest,
) -> dict:
    cfg = clone_config(load_config("configs/matgpt_telco_300m.yaml"))
    cfg["dataset"]["normalized_dir"] = str(request.destination_root)
    cfg["tokenizer"]["output_dir"] = str(request.tokenizer_dir)
    cfg["tokenizer"]["vocab_size"] = 320
    cfg["model"]["vocab_size"] = 320
    cfg["sharding"]["output_dir"] = str(request.destination_root / "shards")
    cfg["sharding"]["shard_size_tokens"] = 24
    cfg["run"]["output_dir"] = str(tmp_path / "run")
    return cfg


def test_published_shards_pass_existing_preflight(tmp_path: Path):
    request = make_corpus_request(
        tmp_path,
        plans=[_tiny_plan("main"), _tiny_plan("cooldown")],
    )
    build_local_corpus(request, dataset_loader=_loader)
    cfg = write_preflight_config_for_local_artifacts(tmp_path, request)

    report = build_preflight_report(cfg, require_t4=False, min_free_disk_gb=0)

    assert report["status"] == "pass"


def test_incomplete_staging_is_not_training_eligible(tmp_path: Path):
    request = make_corpus_request(tmp_path, plans=[_tiny_plan("main")])
    result = build_local_corpus(
        request, dataset_loader=_loader, stop_after_quota_tokens=24
    )

    assert result.status == "calibration_complete"
    assert not (request.destination_root / "manifest.json").exists()
    assert (request.destination_root / "calibration_report.json").exists()
```

- [ ] **Step 3: Run focused tests and verify RED**

```bash
uv run --extra test pytest tests/test_local_corpus.py tests/test_preflight.py -q
```

Expected: the complete local manifest or relative-shard metadata is not yet
recognized.

- [ ] **Step 4: Implement deterministic final metadata**

Aggregate committed journal rows rather than re-reading and re-tokenizing the
corpus. The final manifest must contain:

- `version`, `complete`, build identity and recipe/source/plan/tokenizer/
  contamination/format fingerprints;
- the existing `split_stats` shape required by preflight, alongside richer
  stage/item statistics;
- exact per-stage, role, item, source, bucket, document, quota-token, packed-
  token, character, and byte counts;
- whole-document overshoot per item;
- immutable source revisions and license counts;
- quality rejection counts and contamination engine/fingerprint;
- relative raw-chunk and shard paths with size and SHA-256;
- validation statistics;
- split metadata fingerprints and audit artifact fingerprints.

Define `content_sha256` over canonical logical counters and artifact relative
paths/checksums. Exclude timestamps, local roots, destination roots, rates, and
machine evidence so clean and resumed builds have the same content identity.

- [ ] **Step 5: Implement audit and eligibility rules**

Build `quota_audit.json` directly from journaled exact token counts. For every
item require `actual >= requested` and `actual - requested <= last_document_tokens`.
Require all selected source revisions and license-review states to match the
registry, every destination artifact to be published and verified, exactly one
EOS per accepted document, and every token ID below vocabulary size.

Update `corpus_has_exact_token_quotas` to accept both legacy
`method="tokenizer_exact"` and local `method="tokenizer_exact_one_pass"` while
requiring the same tokenizer and plan fingerprints. Do not relax the legacy
path.

Set `storage_format="chunked_prebuilt_v1"` and record safe relative raw chunk
lists under each `split_stats` entry. Add a shared iterator that resolves and
reads those lists for local audits, with the legacy `<split>.jsonl` fallback.
This avoids ever reconstructing a 54GB monolithic file.

- [ ] **Step 6: Resolve relative shard paths safely**

Update shard readers and preflight to resolve a relative artifact path against
the metadata file's directory, then prove its resolved path remains under the
configured shard root. Keep absolute in-root paths supported for old prepared
artifacts. Add path-traversal rejection coverage.

For `chunked_prebuilt_v1`, Colab preflight must not require copying or rescanning
all normalized text. Instead, `_check_dataset_manifest` verifies `complete`, the
builder/schema version, build identity, tokenizer/plan/source/contamination
fingerprints, and each quota/license/quality/overlap audit file's size and SHA.
`_check_dataset_overlap` consumes the signed overlap audit and requires
`overlap_count == 0`. The legacy JSONL scan remains unchanged for legacy
manifests. Add tests that a missing, changed, or path-traversing audit fails
closed.

- [ ] **Step 7: Verify manifest, preflight, and training-data compatibility**

```bash
uv run --extra test pytest tests/test_local_corpus.py tests/test_preflight.py tests/test_training_core.py tests/test_pretrain_smoke.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit finalization and compatibility**

```bash
git add matgpt/data/local_corpus.py matgpt/data/shard.py matgpt/data/telco_prepare.py matgpt/preflight.py tests/test_local_corpus.py tests/test_preflight.py tests/test_training_core.py
git commit -m "feat: finalize local telco corpus evidence"
```

---

### Task 5: Add pilot refresh, 100M calibration, resume, and status controls

**Files:**
- Modify: `scripts/prepare_telco_local.py`
- Modify: `notebooks/prepare_matgpt_telco_300m_local.ipynb`
- Modify: `tests/test_telco_notebook_local.py`
- Modify: `tests/test_tokenizer_candidate.py`
- Modify: `docs/runbooks/local-telco-300m-data.md`

**Interfaces:**
- CLI stages: existing tokenizer stages plus `pilot_refresh`, `full_calibration`, `full_resume`, and `status`.
- `pilot_refresh` prepares/verifies data artifacts only; GPU smoke, pilot training, and evaluation remain separate Colab actions.

- [ ] **Step 1: Write failing local-stage safety tests**

```python
def test_local_notebook_exposes_calibration_and_resume_stages():
    source = _source()
    for stage in ("pilot_refresh", "full_calibration", "full_resume", "status"):
        assert stage in source
    assert "STOP_AFTER_QUOTA_TOKENS = 100_000_000" in source
    assert "scripts/train.py" not in source
    assert "run_pretraining" not in source


def test_full_resume_requires_accepted_calibration():
    source = _source()
    assert "ACCEPT_CALIBRATION = False" in source
    assert "--accept-calibration" in source
```

- [ ] **Step 2: Run notebook tests and verify RED**

```bash
uv run --extra test pytest tests/test_telco_notebook_local.py -q
```

Expected: assertions fail because the later stages are absent.

- [ ] **Step 3: Implement `pilot_refresh`**

Read and verify `selection.json` and `comparison.json`.

- When `pilot_20m` is selected, fingerprint the existing pilot tokenizer,
  corpus, shards, preflight, smoke, pilot, and evaluation evidence. Write
  `pilot_refresh.json` with `action="reuse"` only if every fingerprint matches.
- When `representative_200m` is selected, build the 20M pilot corpus and shards
  with `build_local_corpus`, publish them to a new tokenizer-fingerprinted
  namespace, and write `action="rebuild"`, `status="ready_for_colab"`.
- Never claim refreshed pilot gates passed until Colab smoke, pilot, and
  evaluation evidence exists under the selected tokenizer fingerprint.

- [ ] **Step 4: Implement full controls**

`full_calibration` passes `stop_after_quota_tokens=100_000_000`. The resulting
report includes actual committed quota tokens, wall time, process CPU time,
peak RSS, source/network wait, encode throughput, contamination throughput,
publication throughput, mean and rolling overall throughput, projected 12B
wall time, Drive verification state, and the unchanged build identity.

`full_resume` requires both `--accept-calibration` and a calibration report with
the same build identity. Refuse when projected completion exceeds 48 hours or
the report records unrecovered storage pressure unless the operator explicitly
passes `--override-calibration-guard` and a non-empty `--override-reason`; record
that reason in operator evidence, not build identity.

`status` performs no source reads. It reports journal state, exact quotas,
last commit, local bytes, destination bytes, unpublished artifacts, free disk,
throughput, ETA, and whether calibration/full completion gates are satisfied.

- [ ] **Step 5: Extend the local notebook with live output**

Use these editable controls:

```python
RUN_STAGE = "status"  # @param ["tokenizer_sample", "tokenizer_candidate", "tokenizer_compare", "tokenizer_select", "pilot_refresh", "full_calibration", "full_resume", "status"]
STOP_AFTER_QUOTA_TOKENS = 100_000_000
ACCEPT_CALIBRATION = False  # @param {type:"boolean"}
OVERRIDE_CALIBRATION_GUARD = False  # @param {type:"boolean"}
OVERRIDE_REASON = ""
```

Render the exact CLI command before execution. Stream stdout/stderr line by
line with `subprocess.Popen`; do not use `capture_output=True`. Show the latest
`progress.json` and explain that closing the notebook kernel stops the local
process.

- [ ] **Step 6: Complete runbook commands and recovery table**

Document commands for all stages, expected Drive paths, how to check Drive's
cloud sync icon, safe `Ctrl-C`, forced-kill recovery, fingerprint mismatch,
source exhaustion, schema/license failure, checksum quarantine, disk pressure,
and a laptop sleep/reboot. State that the 100M calibration is retained as the
first part of the final build and that no GPU is required.

- [ ] **Step 7: Verify local controls**

```bash
uv run --extra test pytest tests/test_telco_notebook_local.py tests/test_tokenizer_candidate.py tests/test_local_corpus.py -q
python -m json.tool notebooks/prepare_matgpt_telco_300m_local.ipynb >/dev/null
```

Expected: all tests pass and notebook JSON is valid.

- [ ] **Step 8: Commit operator controls**

```bash
git add scripts/prepare_telco_local.py notebooks/prepare_matgpt_telco_300m_local.ipynb tests/test_telco_notebook_local.py tests/test_tokenizer_candidate.py docs/runbooks/local-telco-300m-data.md
git commit -m "feat: control telco calibration and resume"
```

---

### Task 6: Let Colab consume finalized prebuilt shards without duplicate work

**Files:**
- Modify: `notebooks/train_matgpt_telco_300m_colab.ipynb`
- Modify: `tests/test_telco_notebook_colab.py`
- Modify: `README.md`
- Modify: `docs/runbooks/local-telco-300m-data.md`

**Interfaces:**
- `PREPARED_DATA_MODE` is either `legacy_jsonl` or `prebuilt_shards`.
- In prebuilt mode, Colab copies the selected tokenizer, finalized corpus manifest/evidence, and token shards to `/content`, then runs existing preflight and benchmark gates.

- [ ] **Step 1: Write failing Colab routing tests**

```python
def test_colab_supports_prebuilt_shards_without_retokenizing():
    source = _code_after_heading("## 8. Prepare tokenizer and shards")
    assert 'PREPARED_DATA_MODE == "prebuilt_shards"' in source
    assert "restore_prebuilt_shards" in source
    assert "tokenize_and_shard.py" in source
    assert "if PREPARED_DATA_MODE == \"legacy_jsonl\"" in source


def test_prebuilt_full_training_still_requires_manual_approval():
    source = "\n".join(_source(cell) for cell in _cells())
    assert "FULL_APPROVED" in source
    assert "final corpus manifest is incomplete" in source
    assert "selected tokenizer fingerprint mismatch" in source
```

- [ ] **Step 2: Run notebook tests and verify RED**

```bash
uv run --extra test pytest tests/test_telco_notebook_colab.py -q
```

Expected: prebuilt mode assertions fail.

- [ ] **Step 3: Implement fingerprinted prebuilt restore**

Add:

```python
PREPARED_DATA_MODE = "prebuilt_shards"  # @param ["prebuilt_shards", "legacy_jsonl"]
```

In `prebuilt_shards` mode:

1. Require the approved tokenizer selection, final `complete: true` corpus
   manifest, quota/license/quality audits, split metadata, and shard files.
2. Verify source revision, plan, contamination, selected tokenizer, artifact
   size, checksum, dtype, EOS, and path-containment evidence before copying.
3. Copy immutable artifacts to `/content` for runtime I/O; rewrite only the
   local config paths and relative shard metadata resolution, never artifact
   identity.
4. Skip tokenizer training, corpus audit re-tokenization, and
   `tokenize_and_shard.py`.
5. Run the existing preflight, memory benchmark, smoke/pilot/full gates.

Keep the legacy path intact behind its explicit mode. Refuse full training when
the corpus is calibration-only or pilot-refresh gates do not match the selected
tokenizer.

- [ ] **Step 4: Add a synthetic restore integration test**

Extend the existing notebook harness to create a final relative-path shard
manifest in a fake Drive tree, execute cells through prepare, and assert:

- tokenizer and shards appear under the configured `/content` work root;
- checksums still match;
- the tokenization command was not invoked;
- preflight status is pass;
- `RUN_STAGE="full"` with `FULL_APPROVED=False` raises the existing approval
  assertion.

- [ ] **Step 5: Update top-level documentation**

Explain that the Mac creates data artifacts while Colab trains the model; list
the approved order:

```text
tokenizer_sample -> tokenizer_candidate -> tokenizer_compare -> tokenizer_select
-> pilot_refresh -> Colab smoke/pilot/evaluate -> full_calibration
-> review/accept -> full_resume -> Colab prepare/preflight/full
```

- [ ] **Step 6: Run full verification**

```bash
uv run --extra test pytest tests/test_telco_notebook_colab.py tests/test_telco_notebook_local.py tests/test_local_tokens.py tests/test_local_publish.py tests/test_local_corpus.py tests/test_preflight.py tests/test_pretrain_smoke.py -q
uv run --extra test pytest -q
python -m json.tool notebooks/prepare_matgpt_telco_300m_local.ipynb >/dev/null
python -m json.tool notebooks/train_matgpt_telco_300m_colab.ipynb >/dev/null
git diff --check origin/main...HEAD
```

Expected: all tests pass, both notebooks are valid JSON, and the complete diff
has no whitespace errors.

- [ ] **Step 7: Review operational invariants**

Before opening the pull request, inspect the full diff and prove:

- no local stage imports model-pretraining code;
- no automatic tokenizer selection or training approval exists;
- a calibration-only namespace has no final `manifest.json`;
- final completion requires every artifact published and verified;
- path traversal and fingerprint mismatch fail closed;
- existing legacy pilot and Colab paths remain covered;
- no cleanup command targets old artifacts or staging directories.

- [ ] **Step 8: Commit the Colab handoff**

```bash
git add notebooks/train_matgpt_telco_300m_colab.ipynb tests/test_telco_notebook_colab.py README.md docs/runbooks/local-telco-300m-data.md
git commit -m "feat: consume prebuilt telco shards in colab"
```

---

## Release gate

Stop after Task 6 and use the repository's review and release workflow. Do not
start the real 200M sample, 100M calibration, 12B preparation, or GPU training
from tests, CI, or release automation. After merge and local-main sync, the
operator starts each expensive stage explicitly and reviews its evidence before
the next gate.
