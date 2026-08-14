# Video 1: From a Sentence to a Training Example

## Prerequisites

- Run a Python file from the repository root.
- Read a Python string, list, loop, and slice such as `values[:-1]`.
- No machine-learning or tokenization knowledge is assumed.

## Learning Objective

Given a short recorded sequence, explain and create:

- the input available at each prediction position;
- the recorded next target;
- the compact shifted input and target rows.

Success means you can trace the rule on a changed sentence and on a short list of numeric IDs.

## Simple Explanation

Consider:

```text
The opposite of hot is cold
```

Put a cut before `cold`. The text before the cut is shown to the model. The recorded word after the cut is used to check what the model predicted.

Move the cut left and repeat. Every word except the first can act as a recorded next target because every one of those words has earlier text before it.

```text
The                         -> opposite
The opposite                -> of
The opposite of             -> hot
The opposite of hot         -> is
The opposite of hot is      -> cold
```

The sentence contains both sides of each question. It supplies the earlier text and the recorded continuation, so no separate answer sheet is required for this base-pretraining task.

## Analogy And Its Limitation

**Teaching analogy:** Imagine making study cards from a completed sentence. The front shows the sentence up to one cut. The back shows the next recorded word. Moving the cut creates another card.

The analogy captures one relationship: earlier context on one side, recorded next piece on the other.

**Limitation:** The repository does not store millions of word-based flashcards. It tokenizes text, samples numeric windows, shifts each window once, and calculates a prediction at every usable position. The analogy explains the expanded questions; it does not describe the storage layout or the model calculation.

## Technical Meaning

- An **input** is the information made available to the model for a prediction.
- A **target** is the recorded value used to check that prediction.
- A **training example** pairs an input with a target for the training task.
- A **prediction position** is one location in a sequence where the model predicts the next piece.
- A **shifted target row** is the recorded sequence moved by one position so every input position aligns with its next target.

The target is an observed continuation, not a declaration that every alternative is wrong.

**Teaching simplification:** This lesson begins with words because the cuts are visible. The real repository trains on numeric token IDs. Lesson 8 explains how text becomes tokens and token IDs; Lesson 16 returns to full context windows, shifted targets, and batches.

In a decoder-only causal model, a prediction at one position may use the input through that position but not later positions. Lesson 29 explains the causal mask that enforces this.

## Tiny Math Or Text Example

The sentence has six words:

```text
[The, opposite, of, hot, is, cold]
```

Within this simplified word sequence:

```text
prediction positions = sequence length - 1
                     = 6 - 1
                     = 5
```

The compact shifted form is:

```text
inputs:   [The,      opposite, of,  hot, is]
targets:  [opposite, of,       hot, is,  cold]
```

For a numeric window:

```text
window = [7, 20, 4, 2, 6]
x      = [7, 20, 4, 2]
y      = [20, 4, 2, 6]
```

The second row is one position ahead of the first. It contains the next recorded ID for every position in `x`.

## Commented Repository Code

`PackedTokenDataset.sample_batch` in `matgpt/training/dataset.py` creates the actual training rows:

```python
# Read one extra ID so both shifted rows have context_length positions.
window = np.asarray(
    shard.data[start : start + self.context_length + 1],
    dtype=np.int64,
)

# Drop the final ID to create the model input.
x[row] = window[:-1]

# Drop the first ID to align each input with the recorded next ID.
y[row] = window[1:]
```

Later, `matgpt/training/pretrain.py` passes both rows to the model:

```python
_, loss = train_model(x, targets=y)
```

Inside `matgpt/model/gpt.py`, the model produces a prediction at every input position and compares those predictions with the aligned targets. Its attention call uses `is_causal=True`, which prevents a position from looking at later positions.

This is one shifted training window with several prediction positions. It is equivalent to expanding the prefix questions for understanding, but it is more compact than storing each prefix as a separate sentence.

## Misconception

**Wrong idea 1:** The target is the one true continuation.

**Correction:** The target is the continuation recorded in this text. Several other continuations may be grammatical, useful, or true.

**Wrong idea 2:** In the shifted rows, each single input word is the entire context for its paired target.

**Correction:** Each position can use the input through that position. The rows show alignment, while the growing-prefix view shows the available context.

**Wrong idea 3:** The model trains directly on the words shown here.

**Correction:** Words are a teaching stand-in. The repository shifts numeric token IDs.

**Wrong idea 4:** Every stage used to train every LLM is next-token prediction.

**Correction:** Next-token prediction is the base-pretraining objective used by this course's decoder-only model. Post-training can use other datasets and objectives.

## Recap

1. Begin with a recorded sequence.
2. Use the sequence so far as input.
3. Use the recorded next piece as the target.
4. Move one position and repeat.
5. Store the relationship compactly by removing the final item for `x` and the first item for `y`.
6. Treat each aligned column as one prediction position, with access only to the input available so far.

Compact mental model: **show the sequence so far; predict the recorded next piece**.
