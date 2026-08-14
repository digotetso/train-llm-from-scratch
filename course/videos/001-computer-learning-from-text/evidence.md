# Video 1 Evidence: From a Sentence to a Training Example

## Repository Anchors

- **Observed repository behavior:** [`matgpt/training/dataset.py`](../../../matgpt/training/dataset.py) samples `context_length + 1` IDs, assigns `window[:-1]` to `x`, and assigns `window[1:]` to `y`.
- **Observed repository behavior:** [`matgpt/training/pretrain.py`](../../../matgpt/training/pretrain.py) calls the model with `x` and `targets=y`.
- **Observed repository behavior:** [`matgpt/model/gpt.py`](../../../matgpt/model/gpt.py) converts `input_ids` with `self.token_embedding(input_ids)`, produces scores at every input position, compares them with the aligned targets, and calls scaled dot-product attention with `is_causal=True`.
- **Observed test behavior:** [`tests/test_training_core.py`](../../../tests/test_training_core.py) verifies that every sampled target row is shifted one position relative to its input row.
- **Observed code behavior:** [`lab.py`](lab.py) expands visible word-prefix questions and applies the same slice relationship to `[7, 20, 4, 2, 6]`.

## Primary Sources

- **Attention Is All You Need:** Vaswani et al. describe decoder outputs offset by one position and masking that prevents a prediction at one position from depending on later positions: <https://arxiv.org/abs/1706.03762>.
- **GPT-2 training objective:** OpenAI describes GPT-2's base objective as predicting the next word from the previous text: <https://openai.com/index/better-language-models/>.
- **Causal language modeling:** Hugging Face's official task guide defines causal language modeling as predicting the next token using only tokens to the left and shows inputs used as one-position-shifted labels: <https://huggingface.co/docs/transformers/main/tasks/language_modeling>.

The repository itself is the source of truth for where this project performs the shift. External sources support the general causal-language-model relationship.

## Commands Run

From the repository root:

```bash
uv run python course/videos/001-computer-learning-from-text/lab.py
uv run --extra test pytest tests/test_course_structure.py tests/test_video_001_teaching_style.py -v
uv run --extra test pytest -o addopts='' -q
git diff --check
```

## Observed Output

Observed on 2026-08-14:

- The direct lab command exited successfully and printed:

  ```text
  Sentence: The opposite of hot is cold
  Words: ['The', 'opposite', 'of', 'hot', 'is', 'cold']
  Prediction positions: 5

  Prefix questions:
  ['The'] -> opposite
  ['The', 'opposite'] -> of
  ['The', 'opposite', 'of'] -> hot
  ['The', 'opposite', 'of', 'hot'] -> is
  ['The', 'opposite', 'of', 'hot', 'is'] -> cold

  Shifted toy ID window:
  window: [7, 20, 4, 2, 6]
  x     : [7, 20, 4, 2]
  y     : [20, 4, 2, 6]
  ```

- The focused Lesson 1 and course-structure suite reported `19 passed`.
- The full repository suite collected 761 tests and completed with 747 passed
  and 14 skipped. The skips are optional Manim-dependent checks in the current
  environment; no test failed.

## Simplifications And Boundaries

- **Words versus tokens:** The hand-worked example uses words so a beginner can see the cut. The repository trains on token IDs. Word boundaries and token boundaries are not generally identical.
- **Examples versus prediction positions:** Expanding every prefix is a useful conceptual view. The implementation carries one shifted training window with several prediction positions, not several independently stored copies of the sentence.
- **Target versus truth:** A target is the continuation recorded in the selected text. It is not necessarily the only sensible, grammatical, or factual continuation.
- **Data-provided targets versus human decisions:** Base-pretraining text supplies next-token targets without a separate manual answer sheet. Dataset sourcing, licensing, filtering, cleaning, splitting, and evaluation still require deliberate choices.
- **Training scope:** Next-token prediction describes this course's decoder-only base-pretraining objective. It does not describe every possible post-training objective.
- **Token IDs versus embeddings:** The training code passes token IDs into `GPT.forward`. The model then looks up one embedding vector for each ID before the Transformer blocks process the sequence.
- **Deferred mechanism:** This lesson names causal look-ahead prevention only to explain why the model cannot read future targets. Lesson 29 teaches the causal mask itself.
- **Legacy visual assets:** The checked-in Manim and After Effects assets correspond to the superseded Lesson 1 and have not been rebuilt for this script.
