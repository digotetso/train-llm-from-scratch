# Checkpoint Evaluation Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible suite that compares preserved checkpoints with matched validation seeds, automatic repetition measurements, fixed consistency tasks, and blinded story judgments performed by this conversation's LLM.

**Architecture:** Pure evaluation modules own repetition, aggregation, prompt loading, and blinded-judge logic. Existing language-model and multiple-choice evaluators remain the model-facing primitives. A new orchestration CLI evaluates labelled checkpoints one at a time and persists detailed evidence, while a separate scoring CLI validates and aggregates anonymized LLM judgments.

**Tech Stack:** Python 3.10+, PyTorch, NumPy, existing MatGPT tokenizer/checkpoint utilities, standard-library JSON/JSONL/statistics/random/path handling, pytest.

## Global Constraints

- Keep the prepared TinyStories validation dataset, tokenizer, model architecture, and checkpoints unchanged.
- Never modify `run.seed` or the loaded configuration to select evaluation samples.
- Use the same predeclared validation seeds, generation seeds, prompt set, task set, and generation settings for every checkpoint.
- Default to validation seeds `1001..1010`, generation seeds `2001..2005`, review seed `3001`, 50 judged stories per checkpoint, and judge batches of at most 20 stories.
- Do not call an external LLM API or require API credentials; this conversation's LLM consumes exported blinded batches.
- Human judging is optional and must be reported separately from LLM judgments.
- Do not overwrite an existing comparison output directory.
- Preserve existing single-checkpoint evaluation behavior and the legacy `evaluation_seed` field.
- Follow red-green-refactor for every behavior change and commit each independently reviewable increment.

## File Structure

- Create `matgpt/eval/repetition.py`: pure generated-text repetition measurements.
- Create `matgpt/eval/assets.py`: strict JSONL prompt loading and asset validation.
- Modify `matgpt/eval/tasks.py`: preserve categories and report per-category accuracy.
- Create `matgpt/eval/comparison.py`: CLI value parsing and deterministic validation/repetition aggregation.
- Create `matgpt/eval/judge.py`: blind selection, judge-batch generation, judgment validation, and aggregation.
- Modify `scripts/evaluate.py`: independent validation and generation seed controls.
- Create `scripts/compare_checkpoints.py`: real checkpoint orchestration and artifact writing.
- Create `scripts/score_story_judgments.py`: validated import and scoring of LLM or optional human judgments.
- Create `evals/story_prompts.jsonl`: 50 fixed continuation prompts.
- Create `evals/story_consistency.jsonl`: 100 fixed continuation-choice checks.
- Create `evals/story_judge_prompt.md`: fixed blinded-judge rubric and JSONL response contract.
- Create `tests/test_eval_repetition.py`: repetition unit tests.
- Create `tests/test_eval_assets.py`: prompt and consistency-asset contract tests.
- Create `tests/test_eval_comparison.py`: parsing and paired aggregation unit tests.
- Create `tests/test_eval_judge.py`: blind-bundle and judgment-scoring unit tests.
- Create `tests/test_compare_checkpoints.py`: orchestration CLI tests with tiny local fakes.
- Create `tests/test_score_story_judgments.py`: scoring CLI tests.
- Modify `tests/test_eval_tasks.py`: category behavior tests.
- Modify `tests/test_run_summary.py`: explicit seed and backward-compatibility tests.
- Modify `README.md`: operator commands, evidence interpretation, and limitations.

---

### Task 1: Generated-Text Repetition Measurements

**Files:**
- Create: `tests/test_eval_repetition.py`
- Create: `matgpt/eval/repetition.py`

**Interfaces:**
- Produces: `measure_repetition(text: str) -> dict[str, int | float]`
- Produces: `aggregate_repetition(rows: Iterable[dict[str, int | float]]) -> dict[str, float]`

- [ ] **Step 1: Write failing tests for exact counts and empty-input behavior**

```python
from matgpt.eval.repetition import aggregate_repetition, measure_repetition


def test_measure_repetition_counts_repeated_words_phrases_and_sentences():
    result = measure_repetition(
        "Go go home. The little dog ran home. The little dog ran home!"
    )

    assert result["word_count"] == 13
    assert result["sentence_count"] == 3
    assert result["consecutive_duplicate_words"] == 1
    assert result["repeated_3gram_occurrences"] == 3
    assert result["repeated_4gram_occurrences"] == 2
    assert result["duplicate_sentence_occurrences"] == 1
    assert result["repeated_3gram_rate"] == 3 / 11
    assert result["repeated_4gram_rate"] == 2 / 10
    assert result["duplicate_sentence_rate"] == 1 / 3


def test_measure_repetition_defines_zero_rates_for_empty_text():
    result = measure_repetition("")

    assert result["word_count"] == 0
    assert result["repeated_3gram_rate"] == 0.0
    assert result["distinct_2gram_ratio"] == 0.0


def test_aggregate_repetition_averages_each_rate():
    result = aggregate_repetition(
        [measure_repetition("A cat ran."), measure_repetition("A cat. A cat.")]
    )

    assert result["story_count"] == 2
    assert result["mean_duplicate_sentence_rate"] == 0.25
```

- [ ] **Step 2: Run the focused tests and verify the import fails**

Run: `pytest tests/test_eval_repetition.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'matgpt.eval.repetition'`.

- [ ] **Step 3: Implement normalized word/sentence extraction and auditable metrics**

```python
from __future__ import annotations

import re
from collections import Counter
from statistics import mean
from typing import Iterable


WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?", re.IGNORECASE)
SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")
RATE_FIELDS = (
    "repeated_3gram_rate",
    "repeated_4gram_rate",
    "duplicate_sentence_rate",
    "distinct_2gram_ratio",
    "distinct_3gram_ratio",
)


def _extra_occurrences(values: list[tuple[str, ...]] | list[str]) -> int:
    return sum(count - 1 for count in Counter(values).values() if count > 1)


def _ngrams(words: list[str], size: int) -> list[tuple[str, ...]]:
    return [tuple(words[index : index + size]) for index in range(len(words) - size + 1)]


def measure_repetition(text: str) -> dict[str, int | float]:
    words = [match.group(0).lower() for match in WORD_RE.finditer(text)]
    sentences = [
        " ".join(WORD_RE.findall(match.group(0).lower()))
        for match in SENTENCE_RE.finditer(text)
        if WORD_RE.search(match.group(0))
    ]
    bigrams, trigrams, fourgrams = (_ngrams(words, size) for size in (2, 3, 4))
    repeated_3 = _extra_occurrences(trigrams)
    repeated_4 = _extra_occurrences(fourgrams)
    duplicate_sentences = _extra_occurrences(sentences)
    return {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "consecutive_duplicate_words": sum(
            left == right for left, right in zip(words, words[1:])
        ),
        "total_3grams": len(trigrams),
        "repeated_3gram_occurrences": repeated_3,
        "repeated_3gram_rate": repeated_3 / len(trigrams) if trigrams else 0.0,
        "total_4grams": len(fourgrams),
        "repeated_4gram_occurrences": repeated_4,
        "repeated_4gram_rate": repeated_4 / len(fourgrams) if fourgrams else 0.0,
        "duplicate_sentence_occurrences": duplicate_sentences,
        "duplicate_sentence_rate": duplicate_sentences / len(sentences) if sentences else 0.0,
        "distinct_2gram_ratio": len(set(bigrams)) / len(bigrams) if bigrams else 0.0,
        "distinct_3gram_ratio": len(set(trigrams)) / len(trigrams) if trigrams else 0.0,
    }


def aggregate_repetition(rows: Iterable[dict[str, int | float]]) -> dict[str, float]:
    items = list(rows)
    return {
        "story_count": len(items),
        **{
            f"mean_{field}": mean(float(item[field]) for item in items) if items else 0.0
            for field in RATE_FIELDS
        },
        "mean_word_count": mean(float(item["word_count"]) for item in items) if items else 0.0,
    }
```

- [ ] **Step 4: Run focused tests and correct only implementation defects**

Run: `pytest tests/test_eval_repetition.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the repetition increment**

```bash
git add matgpt/eval/repetition.py tests/test_eval_repetition.py
git commit -m "feat: measure generated story repetition"
```

### Task 2: Categorized Consistency Task Results

**Files:**
- Modify: `tests/test_eval_tasks.py`
- Modify: `matgpt/eval/tasks.py`

**Interfaces:**
- Extends: `MultipleChoiceExample.category: str`
- Extends: encoded example rows with `category`
- Extends: `score_multiple_choice_examples(...)` result with `categories`

- [ ] **Step 1: Add failing tests for category propagation and aggregation**

```python
def test_load_multiple_choice_examples_preserves_category(tmp_path: Path):
    path = tmp_path / "mc.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "character-001",
                "category": "character",
                "prompt": "Mia was a girl. Mia said",
                "choices": [" she", " he"],
                "answer": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert load_multiple_choice_examples(path)[0].category == "character"


def test_score_multiple_choice_examples_reports_category_accuracy():
    model = PreferenceModel(preferred_token_id=2)
    result = score_multiple_choice_examples(
        model=model,
        encoded_examples=[
            {"id": "a", "category": "character", "prompt_ids": [1], "choice_ids": [[2], [3]], "answer_index": 0},
            {"id": "b", "category": "character", "prompt_ids": [1], "choice_ids": [[2], [3]], "answer_index": 1},
            {"id": "c", "category": "object", "prompt_ids": [1], "choice_ids": [[2], [3]], "answer_index": 0},
        ],
        device=torch.device("cpu"),
        precision="fp32",
    )

    assert result["categories"] == {
        "character": {"total": 2, "correct": 1, "accuracy": 0.5},
        "object": {"total": 1, "correct": 1, "accuracy": 1.0},
    }
```

- [ ] **Step 2: Verify the new assertions fail against the existing result schema**

Run: `pytest tests/test_eval_tasks.py -q`

Expected: FAIL because `category` and `categories` are absent.

- [ ] **Step 3: Add backward-compatible category handling**

Implement these exact rules in `matgpt/eval/tasks.py`:

```python
@dataclass(frozen=True)
class MultipleChoiceExample:
    id: str
    prompt: str
    choices: list[str]
    answer_index: int
    category: str = "uncategorized"
```

Read `category = str(row.get("category", "uncategorized")).strip()` and reject an empty category. Preserve it in encoded and row-level results. Build `categories` from row-level `correct` values in sorted category order. Older task files without a category must continue to produce `uncategorized`.

- [ ] **Step 4: Run task tests**

Run: `pytest tests/test_eval_tasks.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the categorized-task increment**

```bash
git add matgpt/eval/tasks.py tests/test_eval_tasks.py
git commit -m "feat: report consistency task categories"
```

### Task 3: Fixed Prompt And Consistency Assets

**Files:**
- Create: `tests/test_eval_assets.py`
- Create: `matgpt/eval/assets.py`
- Create: `evals/story_prompts.jsonl`
- Create: `evals/story_consistency.jsonl`
- Create: `evals/story_judge_prompt.md`

**Interfaces:**
- Produces: `StoryPrompt(id: str, category: str, text: str)`
- Produces: `load_story_prompts(path: str | Path) -> list[StoryPrompt]`
- Produces: `validate_consistency_asset(path: str | Path) -> dict[str, int]`

- [ ] **Step 1: Write failing asset-contract tests**

```python
from collections import Counter
from pathlib import Path

from matgpt.eval.assets import load_story_prompts, validate_consistency_asset


ROOT = Path(__file__).resolve().parents[1]


def test_story_prompt_asset_has_50_unique_base_model_continuations():
    prompts = load_story_prompts(ROOT / "evals" / "story_prompts.jsonl")

    assert len(prompts) == 50
    assert len({prompt.id for prompt in prompts}) == 50
    assert len({prompt.text for prompt in prompts}) == 50
    assert all(prompt.text.strip() and not prompt.text.endswith("?") for prompt in prompts)


def test_consistency_asset_has_25_examples_in_each_category():
    counts = validate_consistency_asset(ROOT / "evals" / "story_consistency.jsonl")

    assert counts == {
        "cause_effect": 25,
        "character": 25,
        "location_state": 25,
        "object_attribute": 25,
    }


def test_judge_prompt_defines_blinding_scores_flags_and_jsonl_contract():
    text = (ROOT / "evals" / "story_judge_prompt.md").read_text(encoding="utf-8")

    for required in (
        "character_consistency",
        "object_location_consistency",
        "causal_coherence",
        "overall_consistency",
        "character_swap",
        "Return exactly one JSON object per input line",
    ):
        assert required in text
```

- [ ] **Step 2: Verify tests fail because the loader and assets do not exist**

Run: `pytest tests/test_eval_assets.py -q`

Expected: FAIL with the missing `matgpt.eval.assets` module.

- [ ] **Step 3: Implement strict prompt and consistency-asset validation**

`load_story_prompts` must reject malformed JSON, non-object lines, missing or blank `id`, `category`, or `text`, duplicate IDs, and duplicate text. `validate_consistency_asset` must call `load_multiple_choice_examples`, require exactly the four approved categories, enforce unique IDs and prompt/choice tuples, require IDs to start with `<category>-`, and return sorted category counts.

- [ ] **Step 4: Add 50 prompts and 100 counterbalanced consistency examples**

Use this prompt record shape:

```json
{"id":"prompt-001","category":"character","text":"Once upon a time, a quiet girl named Mara found"}
```

Use this task record shape:

```json
{"id":"object_attribute-001","category":"object_attribute","prompt":"Lily put the red ball in the box. Tom carried a blue kite. Later, Lily opened the box and found the","choices":[" red ball."," blue kite."],"answer":0}
```

Create exactly 25 records for each approved category. Counterbalance names, pronouns, objects, colours, owners, locations, state changes, and answer indexes across the file. Keep paired choices grammatically parallel and close in token length.

- [ ] **Step 5: Add the fixed LLM judge prompt**

The committed prompt must instruct the judge to use only the supplied story, ignore writing style except where it causes ambiguity, score each dimension from `0` to `2`, cite concrete evidence, use only the allowed flags, avoid comparing stories with one another, and emit JSONL without Markdown fences.

- [ ] **Step 6: Run asset and existing task tests**

Run: `pytest tests/test_eval_assets.py tests/test_eval_tasks.py -q`

Expected: PASS with exact counts `50` and `100`.

- [ ] **Step 7: Commit the fixed-assets increment**

```bash
git add evals matgpt/eval/assets.py tests/test_eval_assets.py
git commit -m "feat: add fixed story evaluation assets"
```

### Task 4: Independent Validation And Generation Seeds

**Files:**
- Modify: `tests/test_run_summary.py`
- Modify: `scripts/evaluate.py`

**Interfaces:**
- Adds CLI: `--validation-seed INTEGER`
- Adds CLI: `--generation-seed INTEGER`
- Adds output: `validation_seed`, `generation_seed`
- Preserves output: `evaluation_seed == cfg["run"]["seed"]`

- [ ] **Step 1: Extend the existing CLI test with explicit seeds**

Add a parametrized case that invokes:

```python
argv = [
    "evaluate.py",
    "--config", "config.yaml",
    "--checkpoint", str(checkpoint),
    "--validation-seed", "1001",
    "--generation-seed", "2001",
]
```

Capture `PackedTokenDataset.from_metadata(..., seed=...)` and require seed `1001`. Require `set_seed` calls `[17, 2001]`: the first establishes reproducible model setup and the second resets randomness immediately before generation. Require the artifact fields:

```python
{
    "evaluation_seed": 17,
    "validation_seed": 1001,
    "generation_seed": 2001,
}
```

Add a default case requiring validation seed `18` and generation seed `17`.

- [ ] **Step 2: Verify the parser rejects the new flags**

Run: `pytest tests/test_run_summary.py::test_evaluate_cli_persists_default_and_explicit_outputs -q`

Expected: FAIL with `unrecognized arguments: --validation-seed ...`.

- [ ] **Step 3: Implement independent seed selection without mutating config**

Parse both optional integers, derive defaults after loading config, pass only `validation_seed` to `PackedTokenDataset.from_metadata`, call `set_seed(generation_seed)` immediately before `generate_samples`, and persist all three seed fields. Keep artifact fingerprint validation unchanged.

- [ ] **Step 4: Run evaluation-script regression tests**

Run: `pytest tests/test_run_summary.py -q`

Expected: PASS, including artifact mismatch protection.

- [ ] **Step 5: Commit seed separation**

```bash
git add scripts/evaluate.py tests/test_run_summary.py
git commit -m "feat: separate validation and generation seeds"
```

### Task 5: Checkpoint Specification And Paired Aggregation

**Files:**
- Create: `tests/test_eval_comparison.py`
- Create: `matgpt/eval/comparison.py`

**Interfaces:**
- Produces: `CheckpointSpec(label: str, path: Path)`
- Produces: `parse_seed_list(raw: str, name: str) -> list[int]`
- Produces: `parse_checkpoint_specs(values: Sequence[str], require_files: bool = True) -> list[CheckpointSpec]`
- Produces: `summarize_validation(results: Mapping[str, Sequence[Mapping[str, float | int]]]) -> dict[str, object]`
- Produces: `summarize_generations(generations: Sequence[Mapping[str, object]]) -> dict[str, object]`

- [ ] **Step 1: Write failing parsing and aggregation tests**

```python
import pytest

from matgpt.eval.comparison import (
    parse_checkpoint_specs,
    parse_seed_list,
    summarize_validation,
)


def test_parse_seed_list_preserves_predeclared_order_and_rejects_duplicates():
    assert parse_seed_list("1001,1002,1003", "validation") == [1001, 1002, 1003]
    with pytest.raises(ValueError, match="duplicate validation seed"):
        parse_seed_list("1001,1001", "validation")


def test_parse_checkpoint_specs_rejects_unsafe_or_duplicate_labels(tmp_path):
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    with pytest.raises(ValueError, match="unsafe checkpoint label"):
        parse_checkpoint_specs([f"../bad={checkpoint}"])
    with pytest.raises(ValueError, match="duplicate checkpoint label"):
        parse_checkpoint_specs([f"mini={checkpoint}", f"mini={checkpoint}"])


def test_summarize_validation_uses_matched_seed_pairs():
    result = summarize_validation(
        {
            "170m": [{"seed": 1, "loss": 1.7}, {"seed": 2, "loss": 1.8}],
            "200m": [{"seed": 1, "loss": 1.8}, {"seed": 2, "loss": 1.7}],
        }
    )

    assert result["checkpoints"]["170m"]["mean_loss"] == 1.75
    assert result["pairs"][0]["left_wins"] == 1
    assert result["pairs"][0]["right_wins"] == 1
    assert result["pairs"][0]["mean_loss_difference"] == 0.0
```

- [ ] **Step 2: Run focused tests and verify the module is missing**

Run: `pytest tests/test_eval_comparison.py -q`

Expected: FAIL with missing module.

- [ ] **Step 3: Implement strict parsing and finite paired summaries**

Use label pattern `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`, seed range `0 <= seed < 2**63`, `statistics.mean`, and `statistics.stdev` with `0.0` for a single observation. Reject non-finite losses, repeated seeds, and unequal seed sets across checkpoints. Pair labels in sorted order and treat losses equal within `1e-12` as ties.

`summarize_generations` must call `aggregate_repetition` and additionally report generation count plus minimum, mean, and maximum word count.

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/test_eval_comparison.py -q`

Expected: PASS.

- [ ] **Step 5: Commit comparison primitives**

```bash
git add matgpt/eval/comparison.py tests/test_eval_comparison.py
git commit -m "feat: aggregate paired checkpoint evidence"
```

### Task 6: Blinded LLM-Judge Bundle And Judgment Scoring

**Files:**
- Create: `tests/test_eval_judge.py`
- Create: `matgpt/eval/judge.py`

**Interfaces:**
- Produces: `ALLOWED_FLAGS: frozenset[str]`
- Produces: `build_judge_bundle(generations_by_checkpoint, per_checkpoint: int, review_seed: int, batch_size: int = 20) -> dict[str, object]`
- Produces: `validate_judgments(rows, expected_review_ids) -> list[dict[str, object]]`
- Produces: `summarize_judgments(rows, review_key) -> dict[str, object]`
- Produces: `write_judge_bundle(root: Path, bundle: Mapping[str, object], prompt_text: str) -> None`

- [ ] **Step 1: Write failing blind-selection tests**

```python
from matgpt.eval.judge import build_judge_bundle


def _generations(label: str) -> list[dict[str, object]]:
    return [
        {
            "generation_id": f"{label}-{index}",
            "prompt_id": f"p-{index}",
            "prompt": "Once upon a time",
            "text": f"Story {index}",
            "generation_seed": 2000 + index,
        }
        for index in range(6)
    ]


def test_build_judge_bundle_is_deterministic_balanced_and_blinded():
    source = {"170m": _generations("170m"), "200m": _generations("200m")}
    first = build_judge_bundle(source, per_checkpoint=4, review_seed=3001, batch_size=3)
    second = build_judge_bundle(source, per_checkpoint=4, review_seed=3001, batch_size=3)

    assert first == second
    assert [len(batch) for batch in first["batches"]] == [3, 3, 2]
    assert len(first["review_key"]) == 8
    assert all(set(row) == {"review_id", "prompt", "text"} for batch in first["batches"] for row in batch)
    assert {item["checkpoint_label"] for item in first["review_key"].values()} == {"170m", "200m"}
```

- [ ] **Step 2: Write failing judgment-schema and aggregate tests**

```python
import pytest

from matgpt.eval.judge import summarize_judgments, validate_judgments


def test_validate_and_summarize_llm_judgments():
    rows = [
        {
            "review_id": "review-0001",
            "character_consistency": 2,
            "object_location_consistency": 1,
            "causal_coherence": 1,
            "overall_consistency": 1,
            "flags": ["object_swap"],
            "evidence": "The ball becomes a kite.",
            "reason": "One object changes, while the characters remain stable.",
        }
    ]
    checked = validate_judgments(rows, {"review-0001"})
    result = summarize_judgments(
        checked,
        {"review-0001": {"checkpoint_label": "170m", "generation_id": "g1"}},
    )

    assert result["checkpoints"]["170m"]["mean_overall_consistency"] == 1.0
    assert result["checkpoints"]["170m"]["flag_counts"] == {"object_swap": 1}


def test_validate_judgments_rejects_missing_and_out_of_range_scores():
    with pytest.raises(ValueError, match="overall_consistency"):
        validate_judgments([{"review_id": "review-0001"}], {"review-0001"})
```

- [ ] **Step 3: Run focused tests and verify the module is missing**

Run: `pytest tests/test_eval_judge.py -q`

Expected: FAIL with missing module.

- [ ] **Step 4: Implement deterministic blinding and leak-free batches**

Select `per_checkpoint` rows independently with `random.Random(review_seed)`, combine and shuffle them, then assign sequential opaque IDs after shuffling. Judge rows contain only `review_id`, `prompt`, and `text`. The private key preserves `checkpoint_label`, `generation_id`, `prompt_id`, and `generation_seed`. Reject insufficient generations, duplicate generation IDs, invalid batch sizes, and non-positive sample counts.

- [ ] **Step 5: Implement strict judgment validation and aggregation**

Require the exact score fields, integer values in `0..2` with booleans rejected, non-empty evidence/reason no longer than 500 characters, and allowed non-duplicated flags. `none` cannot appear with any other flag. Require exactly one result for every expected review ID. Aggregate all four mean scores, each score's `0/1/2` distribution, and flag counts per checkpoint.

- [ ] **Step 6: Implement atomic bundle writing**

Create the new `llm_judge` directory only when absent. Write batches as sorted-key JSONL, the key as deterministic JSON, the prompt as UTF-8 Markdown, and an empty `results/` directory. Fail before writing when any judge-visible row contains a forbidden identity field.

- [ ] **Step 7: Run judge tests**

Run: `pytest tests/test_eval_judge.py -q`

Expected: PASS.

- [ ] **Step 8: Commit blinded judging**

```bash
git add matgpt/eval/judge.py tests/test_eval_judge.py
git commit -m "feat: prepare blinded LLM story judgments"
```

### Task 7: Story-Judgment Scoring CLI

**Files:**
- Create: `tests/test_score_story_judgments.py`
- Create: `scripts/score_story_judgments.py`

**Interfaces:**
- CLI: `--key PATH --judgments PATH [--judgments PATH ...] --reviewer llm|human --output PATH`
- Consumes: `validate_judgments`, `summarize_judgments`

- [ ] **Step 1: Write a failing CLI test using two judgment files**

Create a two-row review key and two one-row judgment JSONL files under `tmp_path`. Invoke `main()` with `--reviewer llm`. Assert that the output contains `reviewer: "llm"`, both joined rows, and separate aggregates for checkpoint labels `170m` and `200m`. Add failure cases for duplicate review IDs across input files and an unknown ID.

- [ ] **Step 2: Verify the script import fails**

Run: `pytest tests/test_score_story_judgments.py -q`

Expected: FAIL because the script does not exist.

- [ ] **Step 3: Implement strict JSON/JSONL loading and output**

Use `argparse`, reject non-object JSONL rows with file and line number, load `review_key.json` as an object, validate before aggregation, set the reviewer field only from the CLI enum, and persist deterministic finite JSON through `write_evaluation_result`. Refuse when output already exists.

- [ ] **Step 4: Run scoring CLI tests**

Run: `pytest tests/test_score_story_judgments.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the scoring CLI**

```bash
git add scripts/score_story_judgments.py tests/test_score_story_judgments.py
git commit -m "feat: score blinded story judgments"
```

### Task 8: Multi-Checkpoint Evaluation Orchestration

**Files:**
- Create: `tests/test_compare_checkpoints.py`
- Create: `scripts/compare_checkpoints.py`

**Interfaces:**
- Consumes all modules from Tasks 1-6.
- CLI matches the arguments in design section 6.5.
- Produces: detailed checkpoint JSON, `comparison_summary.json`, and `llm_judge/` bundle.

- [ ] **Step 1: Write failing tests for early argument validation**

Test pure `parse_args`/`validate_request` behavior through `main()` with monkeypatched model-loading probes. Duplicate labels, duplicate seeds, one checkpoint, missing prompt/task files, and an existing output directory must fail before any model-loading probe is called.

- [ ] **Step 2: Write a failing tiny end-to-end orchestration test**

Monkeypatch only hardware and artifact boundaries: config loading, checkpoint loading/application, tokenizer loading, model construction, dataset construction, `evaluate_loss`, task evaluation, and sample generation. Keep real parsing, repetition, aggregation, artifact writing, and judge-bundle logic. Evaluate two labelled fake checkpoints with two validation seeds, two generation seeds, two prompts, one task result, and one judged story per checkpoint. Assert:

```python
assert summary["protocol"]["validation_seeds"] == [1001, 1002]
assert summary["protocol"]["generation_seeds"] == [2001, 2002]
assert summary["validation"]["pairs"][0]["seed_count"] == 2
assert len(list((output / "llm_judge" / "batches").glob("*.jsonl"))) == 1
assert not any("checkpoint" in row for row in judge_rows)
```

- [ ] **Step 3: Verify the comparison script is missing**

Run: `pytest tests/test_compare_checkpoints.py -q`

Expected: FAIL because `scripts.compare_checkpoints` cannot be imported.

- [ ] **Step 4: Implement model-independent request validation**

Add explicit defaults `1001..1010`, `2001..2005`, review seed `3001`, review count `50`, and judge batch size `20`. Resolve input files and reject the output directory before calling `get_device` or loading config/model data.

- [ ] **Step 5: Implement one-checkpoint-at-a-time evaluation**

Load config, device, tokenizer, and prompt records once. For each checkpoint: construct a fresh model, load and compatibility-check payload fingerprints using the same logic as `scripts/evaluate.py`, apply state, recreate `PackedTokenDataset` for each validation seed, run the consistency task once, reset the generation seed before generating the 50 prompt texts, attach stable IDs and repetition metrics, and persist `checkpoints/<label>.json`. Delete the model reference before starting the next checkpoint and call `torch.cuda.empty_cache()` only when CUDA is active.

- [ ] **Step 6: Aggregate and persist the comparison and judge bundle**

Use the detailed in-memory rows to build validation and repetition summaries. Record config fingerprint, checkpoint labels/paths, all protocol settings, task results, and artifact-relative paths. Create blinded batches from the completed generations and copy the committed judge prompt text. Write `comparison_summary.json` only after every checkpoint and the judge bundle succeed.

- [ ] **Step 7: Run focused orchestration tests**

Run: `pytest tests/test_compare_checkpoints.py -q`

Expected: PASS.

- [ ] **Step 8: Run all evaluation tests**

Run: `pytest tests/test_eval_repetition.py tests/test_eval_assets.py tests/test_eval_tasks.py tests/test_eval_comparison.py tests/test_eval_judge.py tests/test_score_story_judgments.py tests/test_compare_checkpoints.py tests/test_run_summary.py -q`

Expected: PASS.

- [ ] **Step 9: Commit orchestration**

```bash
git add scripts/compare_checkpoints.py tests/test_compare_checkpoints.py
git commit -m "feat: compare preserved training checkpoints"
```

### Task 9: Operator Documentation And Final Verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Documents the exact comparison and LLM-judging workflow.

- [ ] **Step 1: Add a failing documentation contract test**

Add to `tests/test_eval_assets.py`:

```python
def test_readme_documents_checkpoint_comparison_and_llm_judging():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for required in (
        "scripts/compare_checkpoints.py",
        "1001,1002,1003,1004,1005,1006,1007,1008,1009,1010",
        "scripts/score_story_judgments.py",
        "this conversation's LLM",
        "same validation dataset",
        "Human review is optional",
    ):
        assert required in text
```

- [ ] **Step 2: Verify the documentation contract fails**

Run: `pytest tests/test_eval_assets.py::test_readme_documents_checkpoint_comparison_and_llm_judging -q`

Expected: FAIL because the new commands are not documented.

- [ ] **Step 3: Document the complete operator workflow**

Add a README section that explains:

1. Download or mount the four preserved checkpoints and prepared artifacts.
2. Run `scripts/compare_checkpoints.py` with fixed labels and paths.
3. Give each anonymized `judge_batch_<NN>.jsonl` plus `judge_prompt.md` to this conversation's LLM without the review key.
4. Save returned JSONL under `llm_judge/results/`.
5. Run `scripts/score_story_judgments.py --reviewer llm`.
6. Compare validation, consistency-task, repetition, and LLM-judge evidence without changing seeds after seeing results.

State that ten seeds are an initial paired sample, LLM judgments are qualitative evidence, and human review is optional.

- [ ] **Step 4: Run documentation and full tests**

Run: `pytest tests/test_eval_assets.py -q`

Expected: PASS.

Run: `pytest -q`

Expected: all tests pass with no warnings or errors.

- [ ] **Step 5: Run static repository checks**

Run: `python -m compileall -q matgpt scripts`

Expected: exit code `0`.

Run: `git diff --check origin/main...HEAD`

Expected: no output.

- [ ] **Step 6: Review the complete feature diff**

Run: `git diff --stat origin/main...HEAD`

Run: `git diff --name-status origin/main...HEAD`

Run: `git diff origin/main...HEAD -- matgpt/eval scripts tests evals README.md`

Confirm there are no unrelated course/video changes, secrets, generated checkpoint artifacts, or weakened existing assertions.

- [ ] **Step 7: Commit documentation**

```bash
git add README.md tests/test_eval_assets.py
git commit -m "docs: explain checkpoint evaluation workflow"
```

- [ ] **Step 8: Perform release handoff**

Push `feat/checkpoint-evaluation-suite`, open a pull request against `main`, verify required checks, merge through GitHub, fetch `origin`, and fast-forward local `main` only when its existing local and uncommitted work can be preserved without rewriting history. If the dirty/ahead local `main` prevents safe synchronization, stop after the merged remote PR and report that exact residual state rather than modifying it.
