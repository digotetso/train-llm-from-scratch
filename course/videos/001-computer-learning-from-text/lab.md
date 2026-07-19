# Video 1 Mini-Lab: Turn `Cat` Into Agreed Numbers

## Setup

- Start in the repository root.
- Use the Python already available for this project.
- No packages, downloads, or network connection are required.
- Open `course/videos/001-computer-learning-from-text/lab.py` when a step asks you to change the text.

## Command

```bash
python course/videos/001-computer-learning-from-text/lab.py
```

## Prediction

Before running the command, write down:

1. The three character numbers you predict for `Cat`.
2. The three UTF-8 bytes you predict for `Cat`.
3. Whether those numbers contain the human meaning of the word.

## Steps

1. Confirm that the first line of `lab.py` is `text = "Cat"`.
2. Run the command from the repository root.
3. Compare both printed lists with your prediction.
4. Change the first line to `text = "A"`.
5. Predict the two new lists before rerunning the command.
6. Run the command and compare the output with your prediction.
7. Explain aloud why `65` is an agreed representation of `A`, not the human meaning of `A`.
8. Restore the first line to `text = "Cat"` so the checked lab has deterministic output.

## Expected Output

With `text = "Cat"`:

```text
Human text: Cat
Character numbers: [67, 97, 116]
UTF-8 bytes: [67, 97, 116]
Can arithmetic use the raw string directly? No
Learning begins after text is represented as numbers.
```

With `text = "A"`, the first three lines become:

```text
Human text: A
Character numbers: [65]
UTF-8 bytes: [65]
```

## Explanation

`ord` follows the Unicode agreement and shows the number assigned to each character. `encode("utf-8")` applies the UTF-8 storage rule, and `list` displays the resulting bytes as ordinary numbers.

For these simple English letters, the two lists match. The result shows numeric representation, not human meaning and not learning. The script follows fixed rules; it does not adjust itself after seeing examples.

## Extension

Complete this sentence in your own words:

> The number `65` represents __________, but it does not contain __________.

Then give two different human uses of `A` that keep the same character number.
