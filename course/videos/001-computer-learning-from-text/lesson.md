# Video 1: From a Sentence to a Training Example

## Prerequisites

- Run a Python file from the repository root.
- Read a Python string, list, loop, and slice such as `values[:-1]`.
- No machine-learning or tokenization knowledge is assumed.

## Learning Objective

Given a short sequence, create and explain:

- the input at each prediction position;
- the recorded next target;
- the compact shifted `x` and `y` rows.

You have understood the lesson when you can apply the same rule to a different sentence and a short list of token IDs.

## Simple Explanation

Start with a complete sentence:

```text
The opposite of hot is cold
```

Hide the final word:

```text
The opposite of hot is | cold
```

The words before the cut are the **input**. The recorded word after the cut is the **target**. Together, the input and target form a **training example**.

Move the cut from left to right:

```text
The                         -> opposite
The opposite                -> of
The opposite of             -> hot
The opposite of hot         -> is
The opposite of hot is      -> cold
```

The sentence contains both the input and the recorded target. It acts as its own answer sheet for this next-token prediction task.

## Analogy And Its Limitation

You can think of the cut as covering the next word of a completed sentence. The visible side asks the question. The covered side contains the recorded answer.

This only explains the input-target relationship. The repository does not store millions of separate word questions. It tokenizes the text and keeps several prediction positions compactly inside one shifted token-ID window.

## Technical Meaning

- An **input** is the information available to the model when it makes a prediction.
- A **target** is the recorded next value used to check that prediction.
- A **training example** pairs an input with a target.
- A **prediction position** is one place where the model predicts the next token.
- **Tokenization** breaks text into pieces called **tokens**.
- A **token ID** is the integer used to identify one token.
- A **sequence** is an ordered list of tokens or token IDs.

The target is the continuation recorded in the selected text. It is not a claim that every other continuation is wrong.

**Teaching simplification:** We begin with words because the cuts are easy to see. The repository trains on token IDs. Lesson 9 explains how the tokenizer creates tokens and token IDs. Lesson 17 returns to full context windows, shifted targets, and batches.

In this decoder-only causal model, each prediction position can use the input up to that position, but it cannot use later positions. Lesson 29 explains the causal mask that enforces this rule.

## Tiny Math Or Text Example

Our sentence contains six words:

```text
[The, opposite, of, hot, is, cold]
```

For this word-level demonstration:

```text
prediction positions = sequence length - 1
                     = 6 - 1
                     = 5
```

We can write the same relationship as two shifted rows:

```text
inputs:   [The,      opposite, of,  hot, is]
targets:  [opposite, of,       hot, is,  cold]
```

Now use numeric token IDs:

```text
window = [7, 20, 4, 2, 6]
x      = [7, 20, 4, 2]
y      = [20, 4, 2, 6]
```

`y` is one position ahead of `x`. Every position in `x` lines up with its recorded next token ID in `y`.

## Commented Repository Code

`PackedTokenDataset.sample_batch` in `matgpt/training/dataset.py` creates the real training rows:

```python
# Read one extra token ID so x and y have the required length.
window = np.asarray(
    shard.data[start : start + self.context_length + 1],
    dtype=np.int64,
)

# Remove the final token ID to create the input row.
x[row] = window[:-1]

# Remove the first token ID to create the target row.
y[row] = window[1:]
```

Later, `matgpt/training/pretrain.py` passes both rows to the model:

```python
_, loss = train_model(x, targets=y)
```

Inside `matgpt/model/gpt.py`, the model predicts at every position and compares those predictions with the aligned targets. Its attention call uses `is_causal=True`, so a position cannot read future positions.

The growing-prefix view and the shifted-row view describe the same task. The first makes the available context easy to see. The second is how the code keeps the relationship compact.

## Misconception

**Wrong idea 1:** The target is the only correct continuation.

**Correction:** The target is the continuation recorded in this text. Other continuations may also make sense.

**Wrong idea 2:** Each item in `x` is the entire input for the item beside it in `y`.

**Correction:** At each position, the model can also use the earlier positions in `x`.

**Wrong idea 3:** The model trains directly on the words in the example.

**Correction:** Words make the first example easy to inspect. The repository shifts token IDs.

**Wrong idea 4:** Every stage of LLM training uses only next-token prediction.

**Correction:** Next-token prediction is the base-pretraining objective used in this course. Post-training may use other data and objectives.

## Recap

1. Start with recorded text.
2. Break the text into tokens and assign token IDs.
3. Shift one token-ID window by one position.
4. Remove the last ID to create `x`.
5. Remove the first ID to create `y`.
6. Predict the next token at each position and compare it with the aligned target.

Compact mental model: **show the sequence so far; predict the recorded next token**.

A token ID is only an identifier. In Lesson 2, the model will convert each token ID into an **embedding**, a learned vector of numbers that the network can use.
