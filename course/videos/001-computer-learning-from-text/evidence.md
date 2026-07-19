# Video 1 Evidence: What Does It Mean for a Computer to Learn From Text?

## Repository Anchors

- [`matgpt/data/normalize.py`](../../../matgpt/data/normalize.py) defines `normalize_text`. The lesson's excerpt shows the function's actual order: Unicode consistency, newline consistency, control-character removal, line-edge cleanup, outer cleanup, and blank-line limiting.
- [`matgpt/data/prepare.py`](../../../matgpt/data/prepare.py) imports `normalize_text` and calls it in `make_document_record`. The returned record stores the cleaned text under `text` and its character count under `num_chars`.
- [`lab.py`](lab.py) uses Python's standard-library `ord` and `str.encode` behavior to display the agreed character numbers and UTF-8 bytes for `Cat`.
- [`tests/test_course_structure.py`](../../../tests/test_course_structure.py) checks the 64 numbered outline entries, all required Video 1 artifacts, and the lab's two deterministic numeric lines.

The repository anchors establish source facts and code behavior. The library-card explanation in the script and lesson is explicitly labeled as a teaching analogy rather than repository behavior.

## Commands Run

From the repository root:

```bash
uv run pytest tests/test_course_structure.py -v
python course/videos/001-computer-learning-from-text/lab.py
rg -n '\b(token|tensor|logit|gradient|attention)\b' course/videos/001-computer-learning-from-text
```

## Observed Output

Observed locally on 2026-07-19:

- Before `course/` existed, the focused test collected two tests and failed both. The first failure was `FileNotFoundError: course/outline.md`; the second was `AssertionError: script.md`. This was the intended RED result.
- After the course files were added, the focused test reported `2 passed in 0.10s`.
- The direct lab run exited successfully and printed:

  ```text
  Human text: Cat
  Character numbers: [67, 97, 116]
  UTF-8 bytes: [67, 97, 116]
  Can arithmetic use the raw string directly? No
  Learning begins after text is represented as numbers.
  ```

- The beginner-language scan found the advanced terms only in explicit deferred-vocabulary boundaries, the scan command itself, and the future-claims list. None is used to explain the Video 1 objective.
- The full repository suite reported `145 passed in 7.56s`.

## Unverified Claims

- Future details of tokenization, token embeddings, tensors, logits, gradients, and attention are intentionally deferred to their approved videos.
- The tiny `7`-mistakes-to-`5`-mistakes example is a teaching illustration. It is not observed output from a repository training run.
- The library-card comparison is a teaching analogy. It is not a claim about the repository implementation.
