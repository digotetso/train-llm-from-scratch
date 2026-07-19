# Video 1 Evidence: What Does It Mean for a Computer to Learn From Text?

## Repository Anchors

- **Source fact:** [`matgpt/data/normalize.py`](../../../matgpt/data/normalize.py) defines `normalize_text`. The excerpt actually shown in the lesson applies NFKC, makes newline styles consistent, removes right-edge whitespace from each line, removes outer whitespace, and returns the result.
- **Observed code behavior:** [`matgpt/data/prepare.py`](../../../matgpt/data/prepare.py) imports `normalize_text` and calls it in `make_document_record`. The shown excerpt stores the cleaned text under `text` and its character count under `num_chars`.
- **Observed code behavior:** [`lab.py`](lab.py) uses Python's built-in `ord` and `str.encode` behavior to display the agreed character numbers and UTF-8 bytes for `Cat`.
- **Observed test behavior:** [`tests/test_course_structure.py`](../../../tests/test_course_structure.py) checks the exact outline, single produced video, artifact headings, quiz alignment, lab source and output, teaching warnings, prompt alignment, and evidence contract.
- **Teaching analogy:** The library-card comparison in the script and lesson illustrates an agreed identifier versus meaning. It is not repository behavior.

## Commands Run

From the repository root:

```bash
uv run pytest tests/test_course_structure.py -v
python course/videos/001-computer-learning-from-text/lab.py
rg -n '\b(token|tensor|logit|gradient|attention)\b' course/videos/001-computer-learning-from-text
uv run pytest -v
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
  Can the mathematical model use this raw Python string as numeric input? No
  Learning begins after text is represented as numbers.
  ```

- The beginner-language scan found the advanced terms only in explicit deferred-vocabulary boundaries, the scan command itself, and the future-claims list. None is used to explain the Video 1 objective.
- During the review follow-up, the corrected stronger contract produced the intended RED result: `4 failed, 6 passed in 0.18s`. The failures identified the old lab prompt, missing NFKC warning, inconsistent prompt references, and incomplete evidence contract.
- After the content fixes, the focused contract reported `10 passed in 0.11s`.
- The full verbose repository suite reported `153 passed in 6.82s`.

## Unverified Claims

- Future details of tokenization, token embeddings, tensors, logits, gradients, and attention are intentionally deferred to their approved videos.
- The tiny `7`-mistakes-to-`5`-mistakes example is a teaching illustration. It is not observed output from a repository training run.
- The library-card comparison is a teaching analogy. It is not a claim about the repository implementation.
