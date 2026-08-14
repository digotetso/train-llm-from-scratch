# Video 1 Mini-Lab: From a Sentence to a Training Example

## Setup

- Start in the repository root.
- Use the Python already available for this project.
- No packages, downloads, or network connection are required.
- Open `course/videos/001-computer-learning-from-text/lab.py` before making the transfer change.

## Command

```bash
uv run python course/videos/001-computer-learning-from-text/lab.py
```

## Prediction

Before running the command, write down:

1. How many prediction positions a six-word sentence supplies in this word-level demonstration.
2. The final target in `The opposite of hot is cold`.
3. The values of `x` and `y` for `window = [7, 20, 4, 2, 6]`.

## Steps

1. Count the words in the sentence.
2. Predict the number of printed prefix questions.
3. Compute `window[:-1]` and `window[1:]` by hand.
4. Run the command.
5. Compare every printed line with your prediction.
6. Change the sentence to `Birds fly over the calm lake`.
7. Predict the final input, final target, and number of positions.
8. Run the command again and explain why the shift stayed the same.
9. Restore the original sentence so the checked lab keeps deterministic output.

## Expected Output

With the checked sentence:

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

## Explanation

The loop expands the sequence into visible prefix questions. Each position begins at one because a target needs at least one earlier word inside this demonstration.

The numeric example uses the same shift as `PackedTokenDataset.sample_batch`: `x` drops the final ID and `y` drops the first ID. The aligned value in `y` is the recorded next target for each position in `x`.

This lab demonstrates data preparation, not learning. It neither builds a model nor changes model parameters.

## Extension

For `Birds fly over the calm lake`, answer without running:

1. What is the final input?
2. What is the final target?
3. How many prediction positions are there?

Then invent a five-word sentence and trace both the expanded prefix questions and the compact shifted rows.
