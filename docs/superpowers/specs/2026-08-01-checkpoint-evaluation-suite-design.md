# Checkpoint Evaluation Suite Design

Date: 2026-08-01

Status: Approved

## 1. Purpose

The completed MatGPT-Mini run preserved checkpoints near 100M, 150M, 170M,
and 200M processed token positions. The existing final comparison evaluated
`latest.pt` and `best.pt` on one reproducible sample of the validation corpus
and three generated stories. That evidence is enough to show that training
worked, but it is too narrow to determine confidently whether the 170M
checkpoint is genuinely better than the 200M checkpoint.

This feature adds a repeatable checkpoint-evaluation suite that answers three
questions:

1. Which checkpoint predicts held-out TinyStories text most accurately across
   several matched validation samples?
2. Which checkpoint repeats words, phrases, and sentences least often during
   generation?
3. Which checkpoint best preserves characters, objects, locations, state
   changes, and simple causes across a story?

The suite will produce evidence for checkpoint selection. It will not resume
training or automatically authorize a larger model run.

## 2. Verified Starting Point

- The validation split and prepared shards are already fixed for the completed
  run.
- `PackedTokenDataset` owns a NumPy random-number generator. Its seed selects a
  reproducible collection of windows from the unchanged validation shards.
- One configured evaluation contains 64 batches of 16 windows, each containing
  256 target positions: 262,144 token predictions per checkpoint and seed.
- `scripts/evaluate.py` currently derives all randomness from `run.seed` and
  records one `evaluation_seed`; it does not expose independent validation and
  generation seeds.
- `scripts/evaluate_tasks.py` already scores local multiple-choice JSONL tasks
  by comparing model loss on each possible continuation.
- The configured generation set contains only three prompts, which is too small
  for a checkpoint-quality conclusion.

## 3. Goals And Acceptance Criteria

The feature is complete when:

- Validation data, tokenizer, model architecture, batch size, context length,
  precision, and number of evaluation batches remain identical across every
  checkpoint comparison.
- A caller can set a validation seed without changing the training seed or the
  checkpoint-compatible configuration hash.
- A caller can set a separate generation seed, and sample generation resets the
  random-number generators immediately before generation.
- The default single-checkpoint evaluation remains compatible with the current
  notebook workflow.
- A comparison command accepts two or more labelled checkpoints and runs the
  same predeclared list of validation and generation seeds for each checkpoint.
- The default validation seed list contains exactly ten values and is recorded
  in every output artifact.
- Detailed results retain checkpoint identity, fingerprints, seeds, per-seed
  validation loss, perplexity, task results, prompts, generations, and
  repetition measurements.
- The summary reports per-checkpoint validation mean, sample standard deviation,
  minimum, maximum, and paired seed win counts. It does not hide individual
  seed results or declare a winner from one favorable run.
- Repetition measurements cover repeated 3-grams, repeated 4-grams, repeated
  sentences, consecutive duplicate words, and distinct 2-gram/3-gram ratios.
- A versioned set of 50 fixed story prompts drives generation for five fixed
  generation seeds, producing 250 stories per checkpoint.
- A versioned set of 100 multiple-choice consistency examples contains 25
  character/pronoun, 25 object/attribute/ownership, 25 location/state-change,
  and 25 cause/effect examples.
- Consistency examples use matched continuation choices and counterbalanced
  facts where practical so generic word frequency is less likely to dominate
  the score.
- The task report includes overall accuracy, per-category accuracy, and the
  choice losses for every example.
- A deterministic blinded LLM-judge export selects 50 generations per
  checkpoint, removes checkpoint labels, shuffles the stories, splits them into
  bounded judge batches, and writes a separate answer key.
- This conversation's LLM is the primary qualitative judge. No external API is
  required: the repository exports judge-ready JSONL and imports the structured
  judgments produced here after the real checkpoint run.
- The judge rubric scores character consistency, object/location consistency,
  causal coherence, and overall consistency on `0..2`, with cited story
  evidence and a short reason required for every judgment.
- A scoring command validates completed LLM-judgment JSONL and reports means,
  score counts, and flagged-error counts for each checkpoint after joining it
  to the blinded answer key.
- Human review is optional and may use the same blinded batches and result
  schema as an audit of the LLM judge.
- Unit and integration tests cover deterministic seeding, paired comparisons,
  metric edge cases, task categories, asset counts, blind export, malformed LLM
  judgments, CLI parsing, and backward-compatible single-checkpoint evaluation.
- The README documents the commands, output artifacts, interpretation limits,
  and the rule that seeds must be selected before inspecting results.

## 4. Non-Goals

This increment will not:

- Change the prepared TinyStories validation split or training data.
- Change the original training seed, configuration snapshot, tokenizer, or
  checkpoint contents.
- Continue pretraining or launch the 59M experiment.
- Download checkpoints from Google Drive automatically.
- Treat generated-text metrics as a substitute for validation loss.
- Treat LLM judgment as a replacement for validation loss, deterministic
  consistency tasks, or automatic repetition metrics. The LLM is the primary
  qualitative judge, but its scores remain one evidence source among several.
- Call an external LLM API, require API credentials, or incur model-API cost.
- Claim statistical certainty from ten seeds; ten paired runs are the initial
  evidence set and may be extended when results remain close.
- Add an exhaustive sequential sweep over every validation-token position in
  this first increment. The paired multi-seed evaluator remains compatible with
  adding that mode later.

## 5. Considered Approaches

### 5.1 Extend Only `scripts/evaluate.py`

This is the smallest code change, but shell loops would have to coordinate
checkpoint labels, seeds, aggregation, generated-text metrics, and blinded
review files. Important fairness rules would live outside the repository and
would be easy to apply inconsistently.

### 5.2 Reusable Evaluation Modules Plus One Comparison Command

This is the selected approach. Small pure functions handle repetition,
aggregation, and blinded LLM-judge preparation. A comparison command owns the
experiment protocol and calls existing model, validation, generation, and task
scoring code. This adds more code than a shell loop but makes the protocol
testable, reviewable, and repeatable.

### 5.3 Notebook-Only Evaluation Cells

This would be convenient in Colab, but it would couple evaluation logic to
notebook state and make unit testing and local review difficult. The notebook
may call the finished command later; it will not be the source of truth.

## 6. Architecture

### 6.1 Seed Separation

`scripts/evaluate.py` will accept optional `--validation-seed` and
`--generation-seed` arguments.

- The validation seed initializes only the validation dataset sampler.
- The generation seed resets Python, NumPy, and PyTorch random state immediately
  before sample generation.
- Defaults preserve the intended existing convention: validation uses
  `run.seed + 1`, generation uses `run.seed`.
- The output records `validation_seed` and `generation_seed` explicitly. The
  legacy `evaluation_seed` field remains as a compatibility alias for the run
  seed so existing summary checks continue to work.

Changing an evaluation seed must not modify the loaded configuration or bypass
checkpoint compatibility validation.

### 6.2 Repetition Metrics

A new `matgpt.eval.repetition` module will expose pure functions that normalize
generated text consistently and return:

- token count and sentence count;
- consecutive duplicate-word count;
- repeated 3-gram and 4-gram extra-occurrence counts and rates;
- duplicate-sentence extra-occurrence count and rate;
- distinct 2-gram and 3-gram ratios.

An “extra occurrence” counts repetitions after the first occurrence. Empty and
very short strings return defined zero-valued rates rather than division errors.
The detailed output retains raw counts so the rates remain auditable.

### 6.3 Consistency Tasks

`MultipleChoiceExample` will gain a required non-empty `category` in the new
asset while remaining backward-compatible with older JSONL files that omit it.
The scorer will preserve the category in every example result and aggregate
accuracy by category.

The committed `evals/story_consistency.jsonl` file will contain 100 fixed
examples. IDs will begin with the category name, making accidental duplication
and category-count failures easy to diagnose. Asset-validation tests will
enforce unique IDs, two or more non-empty choices, a valid answer, exact category
counts, and no duplicate prompt/choice combinations.

### 6.4 Fixed Generation Prompts

`evals/story_prompts.jsonl` will contain 50 unique prompt records with stable
IDs. Prompts will cover character introductions, object discovery, simple goals,
locations, social situations, and cause/effect setups while remaining suitable
for a TinyStories base model. Prompts are continuations, not chat instructions.

### 6.5 Checkpoint Comparison Command

`scripts/compare_checkpoints.py` will accept:

```text
--config PATH
--checkpoint LABEL=PATH              repeat two or more times
--validation-seeds 1001,...,1010
--generation-seeds 2001,...,2005
--prompts evals/story_prompts.jsonl
--task evals/story_consistency.jsonl
--review-per-checkpoint 50
--review-seed 3001
--output-dir PATH
```

For each checkpoint, the command will:

1. Load and compatibility-check the checkpoint.
2. Evaluate the same validation windows for every listed validation seed.
3. Run the fixed consistency task once.
4. Reset randomness and generate all prompts for every generation seed.
5. Attach repetition measurements to every generated story.
6. Persist a detailed per-checkpoint JSON artifact.

After all checkpoints finish, the command will write:

- `comparison_summary.json` with aggregate and paired results;
- `checkpoints/<label>.json` with complete evidence;
- `llm_judge/batches/judge_batch_<NN>.jsonl` with checkpoint identity removed;
- `llm_judge/review_key.json` with the identity mapping;
- `llm_judge/judge_prompt.md` with the fixed rubric, instructions, and result
  schema;
- `llm_judge/results/` as the target directory for this LLM's completed JSONL
  judgments.

Checkpoint labels, seeds, IDs, and output paths will be validated before model
loading so malformed invocations fail early without partial evidence.

### 6.6 Blinded LLM Judgment And Scoring

The comparison command will select exactly 50 generations per checkpoint with
a fixed review seed, anonymize them with opaque review IDs, shuffle them, and
split the combined set into JSONL batches of at most 20 stories. Checkpoint
label, checkpoint path, training-token count, validation score, and generation
seed will not appear in judge-visible batches.

`judge_prompt.md` will instruct this conversation's LLM to evaluate each story
independently and return one JSON object per review ID with:

```json
{
  "review_id": "review-0001",
  "character_consistency": 0,
  "object_location_consistency": 1,
  "causal_coherence": 1,
  "overall_consistency": 1,
  "flags": ["character_swap"],
  "evidence": "The dog is later called a cat.",
  "reason": "The story is understandable but changes the main animal."
}
```

All four scores must be integers from `0` to `2`. `flags` must contain only
documented labels such as `character_swap`, `object_swap`, `location_conflict`,
`state_reversal`, `causal_break`, `ending_break`, or `none`. Evidence and reason
must be non-empty and bounded in length.

`scripts/score_story_judgments.py` will accept one or more completed judgment
JSONL files and the private review key. It will reject missing, duplicate,
unknown, malformed, or out-of-range judgments. It will write a JSON summary
containing per-checkpoint score means, score distributions, flag counts, and
joined row-level evidence.

A human reviewer may optionally judge the same blinded batches with the same
schema. Human results are stored and reported separately; they do not silently
overwrite the LLM results.

## 7. Data Flow

```text
fixed validation shards + predeclared validation seeds
  -> identical sampled windows for every checkpoint
  -> per-seed loss and perplexity
  -> paired checkpoint summary

fixed prompts + predeclared generation seeds
  -> generated stories
  -> repetition metrics
  -> aggregate repetition summary
  -> deterministic blinded LLM-judge batches
  -> this LLM returns structured judgments
  -> validated judgments joined through private key

fixed consistency JSONL
  -> continuation losses
  -> overall and per-category accuracy
```

The detailed artifacts are the source of truth. Summaries are derived views and
must be reproducible from those artifacts.

## 8. Failure Handling

- Duplicate checkpoint labels, duplicate seeds, empty seed lists, invalid seed
  syntax, missing files, and unsafe labels fail before evaluation begins.
- Non-finite validation loss, task loss, perplexity, or repetition rate fails
  the run and identifies the checkpoint and seed.
- Existing output directories are not silently overwritten unless an explicit
  replacement option is added in a later design.
- A partial model-evaluation failure leaves completed detailed files for
  diagnosis but does not write a successful comparison summary.
- LLM-judgment scoring never guesses missing scores or silently drops rows.
- Judge-visible batches fail validation if they expose checkpoint labels,
  checkpoint paths, token counts, validation scores, or generation seeds.

## 9. Test Strategy

Implementation will follow red-green-refactor in small increments.

1. Unit tests for repetition metrics, including empty text, short text,
   punctuation/case normalization, overlapping repeated n-grams, repeated
   sentences, and consecutive duplicate words.
2. Unit tests for seed parsing, checkpoint argument validation, aggregation,
   and paired win counts using hand-checkable numbers.
3. Existing task-evaluator tests extended for category propagation and
   per-category aggregation.
4. Asset-contract tests for the 50 prompts and 100 categorized consistency
   examples.
5. Unit tests for deterministic blind selection, batch-size limits, identity
   removal, answer-key completeness, judgment-schema validation, allowed flags,
   and aggregate LLM score reporting.
6. CLI tests with tiny synthetic model/data fixtures where feasible; model
   arithmetic will not be mocked when the existing small real components can
   run cheaply.
7. Focused tests first, followed by the full local `pytest` suite.

Local tests prove code behavior and asset shape. They do not prove which real
checkpoint wins; that conclusion requires running the suite with the preserved
TinyStories tokenizer, shards, and checkpoints on suitable hardware.

## 10. Decision Report

The suite will not reduce all measurements to an unexplained single score. The
report will show:

- validation-loss mean and variability;
- seed-by-seed paired wins;
- consistency accuracy overall and by category;
- repetition rates and generated-length distribution;
- blinded LLM-judge results once completed;
- optional human-audit results when supplied.

A checkpoint is a strong stopping-point candidate only when its lower validation
loss repeats across matched seeds and its consistency or repetition results do
not materially regress. When different measurements favor different
checkpoints, the report will state the trade-off rather than manufacture a
winner. LLM judgments remain auditable because every score retains the opaque
review ID, evidence sentence, reason, and post-review checkpoint mapping.

## 11. Rollback And Operational Impact

The feature adds evaluation-only modules, scripts, and assets. It does not alter
training state, checkpoints, prepared data, or model architecture. Rollback is
therefore a normal code revert. Generated comparison artifacts belong under a
run-specific output directory and remain outside source control unless the user
explicitly promotes a summary into project documentation.
