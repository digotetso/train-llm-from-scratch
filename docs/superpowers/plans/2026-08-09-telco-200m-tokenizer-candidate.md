# Telco 200M Tokenizer Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, train, evaluate, and explicitly select a 32,768-token byte-level BPE candidate from a deterministic 200M-token representative Telco mixture without starting model training.

**Architecture:** Add an isolated tokenizer-candidate configuration, a compiled Aho-Corasick contamination matcher, and a resumable chunked bootstrap-sample builder backed by an exact SQLite journal. Train the candidate from the chunk manifest, evaluate both tokenizers on the same stable holdout, and persist a deterministic comparison report plus an operator-approved selection record.

**Tech Stack:** Python 3.10+, Hugging Face `datasets`, Hugging Face `tokenizers`, `pyahocorasick`, SQLite, NumPy, PyYAML, JSON/JSONL, Jupyter Notebook JSON, pytest, Google Drive File Provider.

## Global Constraints

- The candidate fitting target is exactly `200_000_000` estimated bootstrap tokens.
- Role quotas are exactly `128_333_333` general, `61_666_667` telecom, and `10_000_000` structured tokens.
- Keep vocabulary size `32_768`, byte-level BPE, seed `42`, and the existing ordered special-token list.
- Evaluation-only, post-training, and RAG-only sources never enter fitting data.
- Open Telco contamination decisions must match the existing reference behavior.
- The comparison holdout is excluded from the pilot and candidate fitting inputs by the existing stable hash rule.
- No command or notebook stage in this plan may import or call model-pretraining entry points.
- Tokenizer replacement remains an explicit operator decision; comparison never selects automatically.
- Existing pilot tokenizer and checkpoints are preserved.
- Follow red-green-refactor for every production behavior and commit after every independently passing task.

---

## File structure

- `configs/data/telco_300m_tokenizer_candidate.yaml`: candidate sample size, labels, comparison thresholds, and local safety defaults.
- `matgpt/data/contamination.py`: reference and compiled multi-pattern matcher implementations plus pattern fingerprinting.
- `matgpt/data/local_state.py`: exact SQLite journal, immutable build identity, committed-unit records, and resume validation.
- `matgpt/data/local_sample.py`: deterministic estimated-quota sampling, bounded JSONL chunks, progress events, and resume orchestration.
- `matgpt/tokenizer/candidate.py`: candidate config loading, sample-plan construction, holdout evaluation, comparison, and explicit selection records.
- `scripts/prepare_telco_local.py`: authoritative non-training CLI for tokenizer sample, train, compare, and select stages.
- `notebooks/prepare_matgpt_telco_300m_local.ipynb`: thin local UI that invokes the CLI without duplicating domain logic.
- `docs/runbooks/local-telco-300m-data.md`: Mac/Drive setup, commands, evidence, interruption, and recovery.
- `tests/test_contamination_matcher.py`: matcher equivalence and fingerprint tests.
- `tests/test_local_build_state.py`: journal transaction and fingerprint safety tests.
- `tests/test_local_tokenizer_sample.py`: chunk/resume/holdout/progress tests.
- `tests/test_tokenizer_candidate.py`: plan, evaluation, recommendation, and explicit-selection tests.
- `tests/test_telco_notebook_local.py`: local notebook safety and stage tests.

---

### Task 1: Define and validate the 200M candidate recipe

**Files:**
- Create: `configs/data/telco_300m_tokenizer_candidate.yaml`
- Create: `matgpt/tokenizer/candidate.py`
- Create: `tests/test_tokenizer_candidate.py`

**Interfaces:**
- Consumes: `load_source_registry(path)`, `load_mixture_config(path)`, and `build_mixture_plan(registry, mixture, stage, total_tokens=...)`.
- Produces: `TokenizerCandidateConfig`, `load_tokenizer_candidate_config(path)`, and `build_tokenizer_sample_plan(registry, mixture, config)`.

- [ ] **Step 1: Write failing configuration and quota tests**

```python
from pathlib import Path

import pytest

from matgpt.data.mixture import load_mixture_config
from matgpt.data.sources import load_source_registry
from matgpt.tokenizer.candidate import (
    build_tokenizer_sample_plan,
    load_tokenizer_candidate_config,
)


def test_candidate_recipe_builds_exact_200m_combined_role_plan():
    config = load_tokenizer_candidate_config(
        "configs/data/telco_300m_tokenizer_candidate.yaml"
    )
    plan = build_tokenizer_sample_plan(
        load_source_registry("configs/data/telco_300m_sources.yaml"),
        load_mixture_config("configs/data/telco_300m_mixture.yaml"),
        config,
    )

    assert plan["stage"] == "pilot"
    assert plan["total_tokens"] == 200_000_000
    assert plan["role_quotas"] == {
        "pretrain_general": 128_333_333,
        "pretrain_structured": 10_000_000,
        "pretrain_telecom": 61_666_667,
    }
    assert sum(item["token_quota"] for item in plan["items"]) == 200_000_000


def test_candidate_recipe_rejects_unknown_keys(tmp_path: Path):
    path = tmp_path / "candidate.yaml"
    path.write_text(
        "version: 1\nsample_tokens: 200000000\nmixture_stage: pilot\n"
        "baseline_label: pilot_20m\ncandidate_label: representative_200m\n"
        "comparison:\n  max_general_regression: 0.01\n"
        "  max_telecom_regression: 0.0\n"
        "  max_probe_p95_regression: 0.01\n"
        "  min_overall_improvement: 0.01\n"
        "  min_telecom_improvement: 0.02\n"
        "local:\n  max_working_gib: 20\n  min_free_gib: 25\n"
        "unexpected: true\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown keys"):
        load_tokenizer_candidate_config(path)
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
uv run --extra test pytest tests/test_tokenizer_candidate.py -q
```

Expected: collection fails because `matgpt.tokenizer.candidate` does not exist.

- [ ] **Step 3: Add the checked-in candidate configuration**

```yaml
version: 1
sample_tokens: 200000000
mixture_stage: pilot
baseline_label: pilot_20m
candidate_label: representative_200m
comparison:
  max_general_regression: 0.01
  max_telecom_regression: 0.0
  max_probe_p95_regression: 0.01
  min_overall_improvement: 0.01
  min_telecom_improvement: 0.02
local:
  max_working_gib: 20
  min_free_gib: 25
```

- [ ] **Step 4: Implement strict loading and sample-plan construction**

Implement this public shape in `matgpt/tokenizer/candidate.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from matgpt.data.mixture import build_mixture_plan


@dataclass(frozen=True)
class TokenizerCandidateConfig:
    sample_tokens: int
    mixture_stage: str
    baseline_label: str
    candidate_label: str
    max_general_regression: float
    max_telecom_regression: float
    max_probe_p95_regression: float
    min_overall_improvement: float
    min_telecom_improvement: float
    max_working_gib: int
    min_free_gib: int


def load_tokenizer_candidate_config(
    path: str | Path,
) -> TokenizerCandidateConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Tokenizer candidate config must be a mapping.")
    allowed = {
        "version", "sample_tokens", "mixture_stage", "baseline_label",
        "candidate_label", "comparison", "local",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"Tokenizer candidate config contains unknown keys: {sorted(unknown)}")
    if raw.get("version") != 1:
        raise ValueError("Tokenizer candidate config version must be 1.")
    comparison = raw.get("comparison")
    local = raw.get("local")
    if not isinstance(comparison, Mapping) or not isinstance(local, Mapping):
        raise ValueError("Tokenizer candidate config requires comparison and local mappings.")
    return TokenizerCandidateConfig(
        sample_tokens=int(raw["sample_tokens"]),
        mixture_stage=str(raw["mixture_stage"]),
        baseline_label=str(raw["baseline_label"]),
        candidate_label=str(raw["candidate_label"]),
        max_general_regression=float(comparison["max_general_regression"]),
        max_telecom_regression=float(comparison["max_telecom_regression"]),
        max_probe_p95_regression=float(comparison["max_probe_p95_regression"]),
        min_overall_improvement=float(comparison["min_overall_improvement"]),
        min_telecom_improvement=float(comparison["min_telecom_improvement"]),
        max_working_gib=int(local["max_working_gib"]),
        min_free_gib=int(local["min_free_gib"]),
    )


def build_tokenizer_sample_plan(registry, mixture, config: TokenizerCandidateConfig) -> dict[str, Any]:
    return build_mixture_plan(
        registry,
        mixture,
        config.mixture_stage,
        total_tokens=config.sample_tokens,
    )
```

Add validation for positive sample/disk values, non-empty safe labels, fractions in `[0, 1)`, and the exact `200_000_000` checked-in production target.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```bash
uv run --extra test pytest tests/test_tokenizer_candidate.py tests/test_telco_mixture.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit the candidate recipe**

```bash
git add configs/data/telco_300m_tokenizer_candidate.yaml matgpt/tokenizer/candidate.py tests/test_tokenizer_candidate.py
git commit -m "feat: define 200m telco tokenizer candidate"
```

---

### Task 2: Replace quadratic contamination scans with an equivalent compiled matcher

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `matgpt/data/contamination.py`
- Modify: `matgpt/data/quality.py`
- Create: `tests/test_contamination_matcher.py`
- Modify: `tests/test_data_quality.py`

**Interfaces:**
- Consumes: normalized case-folded patterns from `load_contamination_patterns`.
- Produces: `pattern_fingerprint(patterns) -> str`, `NaiveContaminationMatcher`, `AhoCorasickContaminationMatcher`, and `build_contamination_matcher(patterns)`; `QualityFilter` accepts an optional matcher. The compatibility contract is the contamination boolean, because the existing filter exposes only accept/reject rather than a matched-pattern identity.

- [ ] **Step 1: Write matcher-equivalence and fingerprint tests**

```python
from matgpt.data.contamination import (
    AhoCorasickContaminationMatcher,
    NaiveContaminationMatcher,
    pattern_fingerprint,
)


def test_aho_matcher_is_equivalent_to_reference_for_unicode_and_overlaps():
    patterns = ["rrc connection", "connection", "o-ran", "café"]
    reference = NaiveContaminationMatcher(patterns)
    compiled = AhoCorasickContaminationMatcher(patterns)
    texts = [
        "An RRC CONNECTION is established.",
        "The O-RAN radio unit.",
        "Serve café traffic.",
        "No benchmark phrase appears.",
    ]

    assert [reference.contains(text.casefold()) for text in texts] == [
        compiled.contains(text.casefold()) for text in texts
    ]


def test_pattern_fingerprint_is_order_independent_and_content_sensitive():
    assert pattern_fingerprint(["beta", "alpha"]) == pattern_fingerprint(
        ["alpha", "beta"]
    )
    assert pattern_fingerprint(["alpha"]) != pattern_fingerprint(["beta"])
```

- [ ] **Step 2: Run tests and verify RED**

```bash
uv run --extra test pytest tests/test_contamination_matcher.py -q
```

Expected: import fails because `matgpt.data.contamination` is absent.

- [ ] **Step 3: Add the supported compiled dependency**

Add `pyahocorasick>=2.1.0` to project dependencies and update the lockfile:

```bash
uv lock
```

Use the documented API: add each Unicode key with `Automaton.add_word`, call
`make_automaton`, and detect the first result from `Automaton.iter`.

- [ ] **Step 4: Implement reference and compiled matchers**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

import ahocorasick

from matgpt.utils.hashing import sha256_json


class ContaminationMatcher(Protocol):
    engine: str

    def contains(self, folded_text: str) -> bool:
        raise NotImplementedError


def _canonical_patterns(patterns: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({pattern for pattern in patterns if pattern}))


def pattern_fingerprint(patterns: Iterable[str]) -> str:
    return sha256_json(list(_canonical_patterns(patterns)))


@dataclass(frozen=True)
class NaiveContaminationMatcher:
    patterns: tuple[str, ...]
    engine: str = "naive_reference"

    def __init__(self, patterns: Iterable[str]) -> None:
        object.__setattr__(self, "patterns", _canonical_patterns(patterns))

    def contains(self, folded_text: str) -> bool:
        return any(pattern in folded_text for pattern in self.patterns)


class AhoCorasickContaminationMatcher:
    engine = "pyahocorasick"

    def __init__(self, patterns: Iterable[str]) -> None:
        self.patterns = _canonical_patterns(patterns)
        self.automaton = ahocorasick.Automaton()
        for index, pattern in enumerate(self.patterns):
            self.automaton.add_word(pattern, (index, pattern))
        self.automaton.make_automaton()

    def contains(self, folded_text: str) -> bool:
        return next(self.automaton.iter(folded_text), None) is not None


def build_contamination_matcher(patterns: Iterable[str]) -> ContaminationMatcher:
    canonical = _canonical_patterns(patterns)
    if not canonical:
        return NaiveContaminationMatcher(())
    return AhoCorasickContaminationMatcher(canonical)
```

- [ ] **Step 5: Inject the matcher into `QualityFilter`**

Change construction to:

```python
class QualityFilter:
    def __init__(self, policy: DataQualityPolicy, contamination_matcher=None) -> None:
        self.policy = policy
        self.contamination_matcher = contamination_matcher or build_contamination_matcher(
            policy.contamination_patterns
        )
```

Replace the `any(...)` expression with:

```python
if self.contamination_matcher.contains(folded):
    return "benchmark_contamination"
```

Extend `report()` with `contamination_engine` and
`contamination_patterns_sha256`.

- [ ] **Step 6: Prove equivalence and regression safety**

```bash
uv run --extra test pytest tests/test_contamination_matcher.py tests/test_data_quality.py tests/test_telco_prepare.py -q
```

Expected: all tests pass, including the existing contamination behavior.

- [ ] **Step 7: Commit the optimized matcher**

```bash
git add pyproject.toml uv.lock matgpt/data/contamination.py matgpt/data/quality.py tests/test_contamination_matcher.py tests/test_data_quality.py
git commit -m "perf: compile telco contamination patterns"
```

---

### Task 3: Add an exact transactional resume journal

**Files:**
- Create: `matgpt/data/local_state.py`
- Create: `tests/test_local_build_state.py`

**Interfaces:**
- Produces: `BuildIdentity`, `UnitCommit`, and `BuildJournal` with `open`, `committed_hashes`, `commit_unit`, `mark_published`, `units`, and `close`.
- Later tasks depend on one SQLite transaction atomically recording accepted hashes, counters, cursor, and immutable artifact metadata.

- [ ] **Step 1: Write failing identity and transaction tests**

```python
from pathlib import Path

import pytest

from matgpt.data.local_state import BuildIdentity, BuildJournal, UnitCommit


def _identity(tokenizer_sha256: str | None = None) -> BuildIdentity:
    return BuildIdentity(
        version=1,
        mode="tokenizer_sample",
        plan_sha256="a" * 64,
        source_registry_sha256="b" * 64,
        contamination_sha256="c" * 64,
        quality_policy_sha256="e" * 64,
        tokenizer_sha256=tokenizer_sha256,
        format_sha256="d" * 64,
    )


def test_journal_commits_hashes_cursor_and_artifacts_atomically(tmp_path: Path):
    with BuildJournal.open(tmp_path / "state.sqlite3", _identity()) as journal:
        journal.commit_unit(
            UnitCommit(
                unit_id="fit-00000",
                stage="pilot",
                source_id="common_pile_wikimedia",
                row_cursor=123,
                quota_tokens=500,
                accepted_hashes=("1" * 64, "2" * 64),
                artifacts=({"path": "fit_00000.jsonl", "size": 80, "sha256": "3" * 64},),
            )
        )

    with BuildJournal.open(tmp_path / "state.sqlite3", _identity()) as journal:
        assert journal.committed_hashes(("1" * 64, "9" * 64)) == {"1" * 64}
        assert journal.units()[0].row_cursor == 123
        assert journal.units()[0].published is False


def test_journal_refuses_changed_build_identity(tmp_path: Path):
    path = tmp_path / "state.sqlite3"
    BuildJournal.open(path, _identity()).close()

    with pytest.raises(ValueError, match="identity mismatch"):
        BuildJournal.open(path, _identity(tokenizer_sha256="e" * 64))
```

- [ ] **Step 2: Run tests and verify RED**

```bash
uv run --extra test pytest tests/test_local_build_state.py -q
```

Expected: import fails because `matgpt.data.local_state` is absent.

- [ ] **Step 3: Implement the immutable data types and schema**

```python
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from matgpt.utils.hashing import sha256_json


@dataclass(frozen=True)
class BuildIdentity:
    version: int
    mode: str
    plan_sha256: str
    source_registry_sha256: str
    contamination_sha256: str
    quality_policy_sha256: str
    tokenizer_sha256: str | None
    format_sha256: str

    @property
    def sha256(self) -> str:
        return sha256_json(asdict(self))


@dataclass(frozen=True)
class UnitCommit:
    unit_id: str
    stage: str
    source_id: str
    row_cursor: int
    quota_tokens: int
    accepted_hashes: tuple[str, ...]
    artifacts: tuple[dict[str, object], ...]
    published: bool = False
```

Create SQLite tables `metadata`, `units`, `artifacts`, and `seen_hashes`. Store the canonical
identity JSON and SHA on first open. Enable foreign keys, WAL mode, and
`synchronous=FULL`. `artifacts` has a composite primary key of
`(unit_id, relative_path)`, a foreign key to `units`, size, source SHA-256,
published flag, destination SHA-256, and publication timestamp. This normalized
table is the publisher boundary used by the second plan.

- [ ] **Step 4: Implement one-transaction `commit_unit`**

Use an explicit transaction:

```python
with self.connection:
    self.connection.execute(
        "INSERT INTO units(unit_id, stage, source_id, row_cursor, quota_tokens, artifacts_json, published) VALUES (?, ?, ?, ?, ?, ?, 0)",
        (
            unit.unit_id,
            unit.stage,
            unit.source_id,
            unit.row_cursor,
            unit.quota_tokens,
            json.dumps(unit.artifacts, sort_keys=True),
        ),
    )
    self.connection.executemany(
        "INSERT INTO seen_hashes(content_sha256, unit_id) VALUES (?, ?)",
        ((digest, unit.unit_id) for digest in unit.accepted_hashes),
    )
    self.connection.executemany(
        "INSERT INTO artifacts(unit_id, relative_path, size, sha256, published) VALUES (?, ?, ?, ?, 0)",
        (
            (
                unit.unit_id,
                str(artifact["path"]),
                int(artifact["size"]),
                str(artifact["sha256"]),
            )
            for artifact in unit.artifacts
        ),
    )
```

Reject duplicate unit IDs and duplicate committed document hashes. Implement
context-manager methods and deterministic `ORDER BY unit_id` reads.

- [ ] **Step 5: Verify journal behavior**

```bash
uv run --extra test pytest tests/test_local_build_state.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit the journal**

```bash
git add matgpt/data/local_state.py tests/test_local_build_state.py
git commit -m "feat: add transactional telco build journal"
```

---

### Task 4: Build and resume bounded tokenizer-sample chunks

**Files:**
- Create: `matgpt/data/local_sample.py`
- Create: `tests/test_local_tokenizer_sample.py`
- Modify: `matgpt/data/telco_prepare.py`

**Interfaces:**
- Consumes: existing source normalization, deterministic buffering, validation assignment, mixture plan, `QualityFilter`, and `BuildJournal`.
- Produces: `LocalSampleRequest`, `ProgressEvent`, `build_tokenizer_sample(request, dataset_loader=None, progress_sink=None, on_unit_committed=None) -> dict`.

- [ ] **Step 1: Write the failing uninterrupted-versus-resume test**

```python
import json
from pathlib import Path

import pytest

from matgpt.data.local_sample import LocalSampleRequest, build_tokenizer_sample
from matgpt.data.quality import DataQualityPolicy
from matgpt.data.sources import load_source_registry


def _tiny_plan():
    return {
        "version": 1,
        "stage": "pilot",
        "seed": 42,
        "total_tokens": 2_000,
        "quota_tolerance": 0.03,
        "validation_fraction": 0.2,
        "buffer_size": 8,
        "role_quotas": {"pretrain_general": 2_000},
        "items": [
            {
                "id": "common_pile_wikimedia",
                "source_id": "common_pile_wikimedia",
                "bucket_id": None,
                "role": "pretrain_general",
                "token_quota": 2_000,
            }
        ],
        "plan_sha256": "f" * 64,
    }


def _fake_telco_loader(_dataset_id: str, **_kwargs):
    return iter(
        {
            "text": f"Document {index} explains deterministic telecom routing behavior.",
        }
        for index in range(10_000)
    )


def _files(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*.jsonl"))
    }


def test_interrupted_sample_resumes_byte_identically(tmp_path: Path):
    registry = load_source_registry("configs/data/telco_300m_sources.yaml")
    tiny_plan = _tiny_plan()
    request = LocalSampleRequest(
        registry=registry,
        plan=tiny_plan,
        output_dir=tmp_path / "resumed",
        state_path=tmp_path / "resumed.sqlite3",
        quality_policy=DataQualityPolicy(enabled=True, min_chars=2, exact_dedup=True),
        chunk_bytes=300,
        progress_interval_seconds=0,
    )
    commits = 0

    def interrupt_after_first(_unit):
        nonlocal commits
        commits += 1
        if commits == 1:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        build_tokenizer_sample(
            request,
            dataset_loader=_fake_telco_loader,
            on_unit_committed=interrupt_after_first,
        )
    resumed = build_tokenizer_sample(request, dataset_loader=_fake_telco_loader)

    clean_request = LocalSampleRequest(
        registry=request.registry,
        plan=request.plan,
        output_dir=tmp_path / "clean",
        state_path=tmp_path / "clean.sqlite3",
        quality_policy=request.quality_policy,
        chunk_bytes=300,
        progress_interval_seconds=0,
    )
    clean = build_tokenizer_sample(clean_request, dataset_loader=_fake_telco_loader)

    assert resumed["manifest_sha256"] == clean["manifest_sha256"]
    assert _files(request.output_dir) == _files(clean_request.output_dir)
```

- [ ] **Step 2: Add holdout and progress-event tests**

```python
def test_sample_holdout_is_disjoint_and_progress_reports_quota(tmp_path: Path):
    registry = load_source_registry("configs/data/telco_300m_sources.yaml")
    tiny_plan = _tiny_plan()
    events = []
    request = LocalSampleRequest(
        registry=registry,
        plan=tiny_plan,
        output_dir=tmp_path / "sample",
        state_path=tmp_path / "state.sqlite3",
        quality_policy=DataQualityPolicy(enabled=True, min_chars=2, exact_dedup=True),
        chunk_bytes=300,
        progress_interval_seconds=0,
    )
    manifest = build_tokenizer_sample(
        request,
        dataset_loader=_fake_telco_loader,
        progress_sink=events.append,
    )
    fit_hashes = set(manifest["fit_content_sha256"])
    holdout_hashes = set(manifest["holdout_content_sha256"])

    assert fit_hashes.isdisjoint(holdout_hashes)
    assert events[-1].accepted_estimated_tokens >= tiny_plan["total_tokens"]
    assert events[-1].requested_estimated_tokens == tiny_plan["total_tokens"]
```

- [ ] **Step 3: Run tests and verify RED**

```bash
uv run --extra test pytest tests/test_local_tokenizer_sample.py -q
```

Expected: import fails because `matgpt.data.local_sample` is absent.

- [ ] **Step 4: Expose stable reusable preparation helpers**

Promote the private source iterator and validation predicate without changing
their behavior:

```python
iter_normalized_source = _iter_normalized_source
is_validation_record = _is_validation_record
```

Update existing internal calls to use the public names and retain regression
coverage in `tests/test_telco_prepare.py`. Also add
`iter_deterministic_source_windows(source, dataset, stage, quality_filter, seed,
buffer_size, start_raw_cursor=0)`. Each window reads raw rows until it has up to
`buffer_size` successfully normalized records, counts empty rejected rows in the
raw cursor, sorts normalized records with the existing key, and yields a frozen
`SourceWindow(next_raw_cursor, records)`. When resuming, enumerate rows from the
absolute `start_raw_cursor` so diagnostics and generated identifiers remain
stable. Test that flattening all windows from cursor zero exactly matches the
existing normalize-then-`iter_deterministic_buffered` chain, including empty
rows, and that restarting at each returned raw cursor reconstructs the remaining
uninterrupted sequence.

- [ ] **Step 5: Implement request and progress types**

```python
@dataclass(frozen=True)
class LocalSampleRequest:
    registry: SourceRegistry
    plan: Mapping[str, object]
    output_dir: Path
    state_path: Path
    quality_policy: DataQualityPolicy
    chunk_bytes: int = 268_435_456
    progress_interval_seconds: float = 30.0


@dataclass(frozen=True)
class ProgressEvent:
    stage: str
    source_id: str
    row_cursor: int
    accepted_documents: int
    accepted_estimated_tokens: int
    requested_estimated_tokens: int
    elapsed_seconds: float
    tokens_per_second: float
    eta_seconds: float | None


def build_tokenizer_sample(
    request: LocalSampleRequest,
    dataset_loader=None,
    progress_sink=None,
    on_unit_committed=None,
) -> dict[str, object]:
    """Build or resume the deterministic candidate sample."""
```

Validate positive chunk size and non-negative progress interval.

- [ ] **Step 6: Implement deterministic chunk commit and resume**

Use the same sorted source order, source loader kwargs, normalized record schema,
buffered ordering, quality decisions, and validation hash rule as the existing
builder. Write `fit/fit_00000.jsonl` and `holdout/holdout_00000.jsonl` at document
boundaries. Before a record is accepted, check both committed journal hashes and
the current unit's pending hashes. Commit only after a complete deterministic
source window, record that window's next raw cursor, and resume with
`dataset.skip(raw_cursor)` when supported or `itertools.islice` otherwise. This
keeps the resume cursor sufficient without serializing a partially shuffled
buffer.

On a unit boundary:

```python
handle.flush()
handle.close()
artifact = {
    "path": str(final_path.relative_to(request.output_dir)),
    "size": final_path.stat().st_size,
    "sha256": sha256_file(final_path),
}
journal.commit_unit(
    UnitCommit(
        unit_id=unit_id,
        stage=str(request.plan["stage"]),
        source_id=source.id,
        row_cursor=row_cursor,
        quota_tokens=unit_tokens,
        accepted_hashes=tuple(pending_hashes),
        artifacts=(artifact,),
    )
)
```

Write a final manifest only after all item quotas complete. Manifest digests must
be based on logical content and relative artifact paths so independent output
roots have identical identity. Preserve whole-document quota behavior.

- [ ] **Step 7: Verify resume and existing preparation**

```bash
uv run --extra test pytest tests/test_local_tokenizer_sample.py tests/test_telco_prepare.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit resumable sampling**

```bash
git add matgpt/data/local_sample.py matgpt/data/telco_prepare.py tests/test_local_tokenizer_sample.py tests/test_telco_prepare.py
git commit -m "feat: resume chunked tokenizer sampling"
```

---

### Task 5: Train and compare tokenizer candidates on the shared holdout

**Files:**
- Modify: `matgpt/tokenizer/train.py`
- Modify: `matgpt/tokenizer/candidate.py`
- Modify: `tests/test_tokenizer.py`
- Modify: `tests/test_tokenizer_candidate.py`

**Interfaces:**
- Produces: `train_tokenizer_from_manifest`, `evaluate_tokenizer_on_jsonl`, `compare_tokenizers`, and `write_tokenizer_selection`.
- Comparison output includes candidate eligibility, recommendation, per-role metrics, p50/p95 fragmentation, probe metrics, fingerprints, and reasons.

- [ ] **Step 1: Write a failing multi-chunk training test**

```python
def test_train_tokenizer_from_manifest_reads_all_fit_chunks(tmp_path: Path):
    fit = tmp_path / "fit"
    fit.mkdir()
    (fit / "fit_00000.jsonl").write_text(
        json.dumps({"text": "RRC connection setup."}) + "\n", encoding="utf-8"
    )
    (fit / "fit_00001.jsonl").write_text(
        json.dumps({"text": "A router forwards packets."}) + "\n", encoding="utf-8"
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"fit": {"chunks": ["fit/fit_00000.jsonl", "fit/fit_00001.jsonl"]}}),
        encoding="utf-8",
    )

    report = train_tokenizer_from_manifest(
        manifest,
        tmp_path / "tokenizer",
        vocab_size=320,
        min_frequency=1,
        special_tokens=SPECIAL_TOKENS,
    )

    assert report["num_training_documents"] == 2
```

- [ ] **Step 2: Write failing comparison-gate tests**

```python
from matgpt.tokenizer.candidate import TokenizerCandidateConfig


def candidate_config() -> TokenizerCandidateConfig:
    return TokenizerCandidateConfig(
        sample_tokens=200_000_000,
        mixture_stage="pilot",
        baseline_label="pilot_20m",
        candidate_label="representative_200m",
        max_general_regression=0.01,
        max_telecom_regression=0.0,
        max_probe_p95_regression=0.01,
        min_overall_improvement=0.01,
        min_telecom_improvement=0.02,
        max_working_gib=20,
        min_free_gib=25,
    )


def evaluation(
    *,
    overall_tokens: int,
    general_tokens: int,
    telecom_tokens: int,
    probe_p95: float,
) -> dict[str, object]:
    return {
        "tokens": overall_tokens,
        "roles": {
            "pretrain_general": {"tokens": general_tokens},
            "pretrain_telecom": {"tokens": telecom_tokens},
            "pretrain_structured": {
                "tokens": overall_tokens - general_tokens - telecom_tokens
            },
        },
        "probe_p95_tokens_per_word": probe_p95,
        "round_trip_failures": 0,
        "special_token_failures": 0,
    }


def test_comparison_recommends_candidate_only_when_thresholds_and_guards_pass():
    config = candidate_config()
    baseline = evaluation(overall_tokens=10_000, general_tokens=6_000, telecom_tokens=3_000, probe_p95=4.0)
    candidate = evaluation(overall_tokens=9_850, general_tokens=6_030, telecom_tokens=2_900, probe_p95=4.02)

    report = compare_tokenizers(baseline, candidate, config)

    assert report["eligible"] is True
    assert report["recommended_winner"] == "representative_200m"
    assert report["overall_improvement_fraction"] == pytest.approx(0.015)


def test_comparison_blocks_candidate_when_telecom_regresses():
    config = candidate_config()
    baseline = evaluation(overall_tokens=10_000, general_tokens=6_000, telecom_tokens=3_000, probe_p95=4.0)
    candidate = evaluation(overall_tokens=9_800, general_tokens=5_700, telecom_tokens=3_100, probe_p95=4.0)

    report = compare_tokenizers(baseline, candidate, config)

    assert report["eligible"] is False
    assert "telecom_regression" in report["guardrail_failures"]
    assert report["recommended_winner"] == "pilot_20m"


def test_comparison_blocks_any_round_trip_failure():
    config = candidate_config()
    baseline = evaluation(overall_tokens=10_000, general_tokens=6_000, telecom_tokens=3_000, probe_p95=4.0)
    candidate = evaluation(overall_tokens=9_700, general_tokens=5_900, telecom_tokens=2_850, probe_p95=3.9)
    candidate["round_trip_failures"] = 1

    report = compare_tokenizers(baseline, candidate, config)

    assert report["eligible"] is False
    assert "round_trip_failure" in report["guardrail_failures"]
```

- [ ] **Step 3: Run tests and verify RED**

```bash
uv run --extra test pytest tests/test_tokenizer.py tests/test_tokenizer_candidate.py -q
```

Expected: imports fail for the new functions.

- [ ] **Step 4: Implement manifest-based training**

Resolve each manifest chunk relative to the manifest directory, reject absolute
or parent-traversal paths, verify each recorded checksum, and pass the ordered
paths to `train_tokenizer_from_jsonl`. Persist the fitting manifest SHA in the
tokenizer report.

- [ ] **Step 5: Implement held-out evaluation**

Define:

```python
def evaluate_tokenizer_on_jsonl(
    tokenizer_dir: str | Path,
    input_paths: list[str | Path],
    probe_sets_path: str | Path,
) -> dict[str, object]:
```

For every document, verify exact round trip and collect tokens, UTF-8 bytes,
`WORD_PATTERN` words, per-document tokens-per-word, role, source, and bucket.
Return exact totals plus deterministic p50/p95 using NumPy's `method="higher"`.
Include input-file checksums and tokenizer SHA.

- [ ] **Step 6: Implement comparison and explicit selection**

```python
def _improvement(baseline: int, candidate: int) -> float:
    return (baseline - candidate) / baseline


def compare_tokenizers(baseline: dict, candidate: dict, config: TokenizerCandidateConfig) -> dict:
    general_regression = -_improvement(
        baseline["roles"]["pretrain_general"]["tokens"],
        candidate["roles"]["pretrain_general"]["tokens"],
    )
    telecom_improvement = _improvement(
        baseline["roles"]["pretrain_telecom"]["tokens"],
        candidate["roles"]["pretrain_telecom"]["tokens"],
    )
    overall_improvement = _improvement(baseline["tokens"], candidate["tokens"])
    probe_regression = (
        candidate["probe_p95_tokens_per_word"] / baseline["probe_p95_tokens_per_word"]
    ) - 1.0
    failures = []
    if baseline["round_trip_failures"] or candidate["round_trip_failures"]:
        failures.append("round_trip_failure")
    if baseline["special_token_failures"] or candidate["special_token_failures"]:
        failures.append("special_token_failure")
    if telecom_improvement < -config.max_telecom_regression:
        failures.append("telecom_regression")
    if general_regression > config.max_general_regression:
        failures.append("general_regression")
    if probe_regression > config.max_probe_p95_regression:
        failures.append("probe_p95_regression")
    eligible = not failures
    recommend_candidate = eligible and (
        overall_improvement >= config.min_overall_improvement
        or telecom_improvement >= config.min_telecom_improvement
    )
    return {
        "eligible": eligible,
        "recommended_winner": config.candidate_label if recommend_candidate else config.baseline_label,
        "guardrail_failures": failures,
        "overall_improvement_fraction": overall_improvement,
        "telecom_improvement_fraction": telecom_improvement,
        "general_regression_fraction": general_regression,
        "probe_p95_regression_fraction": probe_regression,
        "baseline": baseline,
        "candidate": candidate,
    }
```

`write_tokenizer_selection` requires an explicit winner equal to a compared
label, records the comparison SHA, selected tokenizer SHA, operator timestamp,
and `approved: true`, and refuses candidate selection when `eligible` is false.

- [ ] **Step 7: Verify training and comparison**

```bash
uv run --extra test pytest tests/test_tokenizer.py tests/test_tokenizer_candidate.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit tokenizer evaluation and selection**

```bash
git add matgpt/tokenizer/train.py matgpt/tokenizer/candidate.py tests/test_tokenizer.py tests/test_tokenizer_candidate.py
git commit -m "feat: compare and select telco tokenizers"
```

---

### Task 6: Add the safe local CLI, notebook, and runbook

**Files:**
- Create: `scripts/prepare_telco_local.py`
- Create: `notebooks/prepare_matgpt_telco_300m_local.ipynb`
- Create: `docs/runbooks/local-telco-300m-data.md`
- Create: `tests/test_telco_notebook_local.py`
- Modify: `tests/test_tokenizer_candidate.py`
- Modify: `README.md`

**Interfaces:**
- CLI stages in this increment: `tokenizer_sample`, `tokenizer_candidate`, `tokenizer_compare`, and `tokenizer_select`.
- The notebook only assembles and runs CLI commands; it never imports training modules.

- [ ] **Step 1: Write failing CLI and notebook safety tests**

```python
import json
from pathlib import Path


NOTEBOOK = Path("notebooks/prepare_matgpt_telco_300m_local.ipynb")


def _source() -> str:
    payload = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    return "\n".join(
        "".join(cell.get("source", [])) for cell in payload["cells"]
    )


def test_local_notebook_exposes_only_data_and_tokenizer_stages():
    source = _source()
    for stage in (
        "tokenizer_sample",
        "tokenizer_candidate",
        "tokenizer_compare",
        "tokenizer_select",
    ):
        assert stage in source
    assert "scripts/train.py" not in source
    assert "run_pretraining" not in source
    assert "FULL_APPROVED" not in source


def test_local_notebook_requires_distinct_local_and_drive_roots():
    source = _source()
    assert "LOCAL_WORK_ROOT.resolve() != DRIVE_PUBLISH_ROOT.resolve()" in source
    assert "Stream files" in source
```

- [ ] **Step 2: Run tests and verify RED**

```bash
uv run --extra test pytest tests/test_telco_notebook_local.py -q
```

Expected: failure because the notebook is absent.

- [ ] **Step 3: Implement the authoritative CLI**

Use subparsers or a required `--stage` choice. Shared required arguments are:

```text
--sources configs/data/telco_300m_sources.yaml
--mixture configs/data/telco_300m_mixture.yaml
--candidate-config configs/data/telco_300m_tokenizer_candidate.yaml
--model-config configs/matgpt_telco_300m.yaml
--work-dir <local path>
--drive-dir <streamed Drive path>
```

Stage-specific requirements:

- `tokenizer_sample`: repeated `--contamination-patterns`; creates/resumes sample.
- `tokenizer_candidate`: `--sample-manifest`; creates candidate without overwrite.
- `tokenizer_compare`: `--baseline-tokenizer`, `--candidate-tokenizer`, and
  `--holdout-manifest`; writes comparison JSON.
- `tokenizer_select`: `--comparison`, `--winner`, and `--approve`; writes the
  selection record but never copies over either tokenizer.

Return non-zero on missing evidence, unsafe paths, fingerprint mismatch, or an
ineligible requested candidate.

- [ ] **Step 4: Create the thin local notebook**

The first cell uses explicit editable settings:

```python
RUN_STAGE = "tokenizer_sample"  # @param ["tokenizer_sample", "tokenizer_candidate", "tokenizer_compare", "tokenizer_select"]
LOCAL_WORK_ROOT = Path.home() / "matgpt_work" / "matgpt_telco_300m"
DRIVE_PUBLISH_ROOT = Path.home() / "Library/CloudStorage/GoogleDrive-ACCOUNT/My Drive/matgpt_artifacts/matgpt_telco_300m"
TOKENIZER_WINNER = ""  # Set only after reviewing comparison.json
APPROVE_SELECTION = False

assert LOCAL_WORK_ROOT.resolve() != DRIVE_PUBLISH_ROOT.resolve()
```

Add cells for environment evidence, Drive Stream-files warning, command preview,
stage execution with live output, and result-file links. Do not use
`capture_output=True`; use `subprocess.Popen` and print each line as it arrives.

- [ ] **Step 5: Write the local runbook**

Document:

- 24GB RAM and current 100GiB-free-disk evidence;
- keeping Drive in Stream mode and avoiding “Available offline” for the artifact tree;
- plugging in the Mac and disabling sleep;
- how to discover the real mounted `My Drive` path;
- every stage and expected output;
- safe interruption and rerun behavior;
- how to inspect progress and disk backpressure;
- why no GPU is required;
- the explicit comparison-review and selection gate;
- that selecting `representative_200m` requires refreshing pilot gates.

- [ ] **Step 6: Verify the first deliverable**

```bash
uv run --extra test pytest tests/test_contamination_matcher.py tests/test_local_build_state.py tests/test_local_tokenizer_sample.py tests/test_tokenizer.py tests/test_tokenizer_candidate.py tests/test_telco_notebook_local.py -q
uv run --extra test pytest -q
python -m json.tool notebooks/prepare_matgpt_telco_300m_local.ipynb >/dev/null
git diff --check origin/main...HEAD
```

Expected: all tests pass, notebook JSON is valid, and diff check is clean.

- [ ] **Step 7: Commit the operator workflow**

```bash
git add scripts/prepare_telco_local.py notebooks/prepare_matgpt_telco_300m_local.ipynb docs/runbooks/local-telco-300m-data.md tests/test_telco_notebook_local.py tests/test_tokenizer_candidate.py README.md
git commit -m "feat: add local telco tokenizer workflow"
```

---

## Deliverable gate

Stop after Task 6. Review the complete diff and run the full suite. Do not start
the real 200M sample from tests or release automation. The operator explicitly
starts `tokenizer_sample` only after both this plan and the resumable local
corpus-builder plan are implemented, reviewed, merged, and the original project
folder is synchronized to `origin/main`.
