# Video 1: From a Sentence to a Training Example

**Subtitle:** How recorded text supplies both a question and the next piece used to check the answer

**Learning objective:** Given a short sequence, create and explain its shifted input and target rows.

**Estimated runtime:** 11 minutes 45 seconds, including prediction pauses and the terminal demonstration.

**Production direction:** Compose for 16:9. Use one consistent cool color for input and one consistent warm color for target. Narration is spoken; visual directions, code, commands, outputs, and fact-check notes are not read word for word.

## 00:00 Hook

### Visual / Animation

- Open on four quiet interface cards: an improved email, a continued paragraph, a short summary, and a code suggestion.
- Collapse the cards into one line: `The opposite of hot is ___`.
- Hold the blank for two seconds before revealing `cold`.
- End on the question: `Where did the practice answer come from?`

### Narration

You have probably seen an AI improve an email, continue a paragraph, summarize a document, or suggest code. In every case, you give it some text and it produces more text.

Try a tiny version yourself: “The opposite of hot is...”

You probably thought of “cold.” The sentence was unfinished, but the pattern felt familiar enough for you to guess what comes next.

The model we will build also practices continuing text. But who writes all of its practice answers? With a large collection of writing, nobody could create a separate answer sheet for every position by hand.

Here is the useful surprise: the recorded text already contains the next piece. If we hide that piece, the earlier text becomes a question and the hidden piece becomes the value used to check the prediction.

By the end of this lesson, you will turn one sentence into those question-and-answer pairs by hand and with Python.

## 01:10 Intuition

### Visual / Animation

- Show the complete sentence as six word tiles: `The opposite of hot is cold`.
- Move a vertical cut from left to right.
- At each position, keep the words before the cut visible and briefly cover the recorded word after the cut.
- Stop before revealing the count and ask: `Six words. How many useful cuts?`

### Narration

Start with the complete recorded sentence:

```text
The opposite of hot is cold
```

Place a cut before the final word:

```text
The opposite of hot is | cold
```

The words before the cut are the part we show. The recorded word after the cut is the part we hide and ask the model to predict.

Now move the cut:

```text
The | opposite of hot is cold
The opposite | of hot is cold
The opposite of | hot is cold
The opposite of hot | is cold
The opposite of hot is | cold
```

Each useful cut creates one next-piece question. A six-word sentence therefore gives us five places where some earlier text can be used to predict a recorded next word.

Why not six? Inside this sentence, there is nothing before the first word. The other five words each have something before them.

This is the mechanism. Now that we can see it, we can give its parts stable names.

## 02:20 Technical Meaning

### Visual / Animation

- Return to the final cut.
- Label the left side `input`, the right side `target`, and the pair `training example`.
- Expand the five cuts into five rows, then compress them into one shifted two-row display.
- Add a small boundary card: `Words here are visible stand-ins; the real pipeline shifts token IDs.`

### Narration

The text we show the model is the **input**.

The recorded next piece used to check the model's prediction is the **target**.

An input paired with its target is a **training example**.

The target is not necessarily the only correct continuation. It is the continuation that appears in this particular training text. “Cold” is a natural continuation here, but in less constrained writing, several different continuations could make sense.

There is one more precision that will save us confusion later.

**Teaching simplification:** we are splitting this sentence into words because words are easy to inspect. The real repository first divides text into smaller or larger pieces called **tokens**, assigns those pieces numeric IDs, and shifts the IDs. Lesson 8 will explain how those pieces are created. For now, the visible words are stand-ins for the pieces the model actually receives.

Our five cuts expose five prediction positions. They are not five independently stored sentences. A training program can arrange the same relationship compactly as one shifted training window and calculate a prediction at every usable position.

## 03:30 Tiny Example

### Visual / Animation

- Build the five prefix questions one row at a time.
- Count from one to five.
- Replace them with two aligned rows labelled `inputs` and `targets`.
- Draw a guide from each input position to the target one place ahead.

### Narration

Let us write every question explicitly:

```text
The                         -> opposite
The opposite                -> of
The opposite of             -> hot
The opposite of hot         -> is
The opposite of hot is      -> cold
```

At the first position, the visible text is “The” and the recorded next word is “opposite.” At the final position, the visible text is “The opposite of hot is” and the recorded next word is “cold.”

For this simplified sentence, the count is:

```text
prediction positions = words - 1
                     = 6 - 1
                     = 5
```

Now arrange the same relationship in two rows. Remove the final word from the first row. Remove the first word from the second row.

```text
inputs:   The       opposite   of    hot   is
targets:  opposite  of         hot   is    cold
```

The target row is the original sequence shifted one position earlier. At each column, the item in the target row is what followed the item at that position in the recorded sequence.

This compact arrangement is important because the training code does not need to create and store five separate copies of the sentence. It can carry one input row and one aligned target row.

## 05:10 Repository Walkthrough

### Visual / Animation

- Open `matgpt/training/dataset.py` and isolate the three lines that create `window`, `x`, and `y`.
- Replace the long token stream with the toy window `[7, 20, 4, 2, 6]`.
- Animate the last ID leaving `x` and the first ID leaving `y`.
- Align each `x` position with its `y` target.
- Show a small shield over future positions labelled `cannot look ahead`.

### Narration

The repository applies exactly this shift to numeric IDs. In `matgpt/training/dataset.py`, it takes a window that is one position longer than the model's input:

```python
window = shard.data[start : start + context_length + 1]
x[row] = window[:-1]
y[row] = window[1:]
```

**Observed repository behavior:** `window[:-1]` removes the final ID to create the input row. `window[1:]` removes the first ID to create the target row.

Use a toy window small enough to check by hand:

```text
window = [ 7, 20, 4, 2, 6 ]
x      = [ 7, 20, 4, 2    ]
y      = [    20, 4, 2, 6 ]
```

The model receives the whole input row. It makes a next-piece prediction at each position, and each prediction is compared with the aligned ID in `y`.

At the second position, for example, the prediction can use the text up to that position, not just the ID `20` by itself. The repository's model prevents a position from using later positions, so it cannot simply read the answer from the future. Lesson 29 will open that prevention mechanism.

This does not mean that each isolated input word is the whole context. The two rows show alignment. The growing prefixes show the information available at successive positions. These are two views of the same next-piece task.

**Source fact:** the original Transformer paper describes shifted outputs together with masking that prevents a prediction from depending on later output positions.

**Observed repository behavior:** this project implements the decoder-only version of that causal relationship with shifted target IDs and causal self-attention.

## 07:20 Live Mini-Lab

### Visual / Animation

- Open `course/videos/001-computer-learning-from-text/lab.py`.
- Hold on the sentence and ask for two predictions: the number of positions and the shifted toy ID rows.
- Run the command in a full-width terminal.
- Highlight the five prefix questions, then the `x` and `y` rows.
- Change only the sentence to `Birds fly over the calm lake` and pause for a transfer prediction.

### Narration

Let us test the mental model before trusting it.

The sentence has six words. Predict how many prefix questions the program will print.

Then look at the toy window `[7, 20, 4, 2, 6]`. Predict `x` after the final ID is removed and `y` after the first ID is removed.

Now run:

```bash
uv run python course/videos/001-computer-learning-from-text/lab.py
```

The program prints five prefix questions. It also prints:

```text
window: [7, 20, 4, 2, 6]
x     : [7, 20, 4, 2]
y     : [20, 4, 2, 6]
```

That output is evidence for the preparation rule. It does not show a model learning yet; it shows how the questions and recorded targets are arranged before the later training calculation.

Now change only the sentence to “Birds fly over the calm lake.” Count before running. It also has six words, so the word-level demonstration should again produce five prediction positions.

The sentence changed, but the shift rule did not. That is the result we need: a mechanism we can transfer, not a single example we memorized.

## 09:40 Common Mistakes

### Visual / Animation

- Present four short misconception cards and correct them one at a time.
- Keep the corrected statements on screen as a checklist.
- End with `recorded target ≠ unique truth` and `word demo ≠ real tokenization`.

### Narration

Let us clear up four easy mistakes.

First, the target is not the only correct continuation. It is the recorded continuation in this training sequence. Other writing could continue differently.

Second, the shifted display does not turn `opposite -> of` into a context-free question. At that position, the model can use the earlier input positions too. The row is compact; the available context still grows from left to right.

Third, words are not the final units used by this repository. Words make today's relationship visible. The real system performs the shift on tokens after tokenization.

Fourth, next-token prediction describes the base pretraining task for the decoder-only model built in this course. It is not a claim that every LLM training phase uses only this objective. Post-training can use curated demonstrations, preferences, rewards, or other objectives.

One more boundary matters: raw text supplies recorded targets without a separate answer sheet, but people still make choices about sources, licenses, filtering, cleaning, and evaluation. “The text contains the target” does not mean the whole data pipeline happens without human decisions.

## 10:50 Recap And Exercise

### Visual / Animation

- Build the chain: `recorded sequence → shift by one → input row + target row → prediction at each position`.
- Reconstruct the original sentence from the two shifted rows.
- Show `Birds fly over the calm lake` and ask the learner to trace the final target.
- Pull back to the next lesson's question: `What complete system will use these examples?`

### Narration

Here is the complete mental model.

Start with a recorded sequence. Shift it by one position. The first view becomes the input row, and the one-step-ahead view becomes the target row. At each usable position, the model makes a next-piece prediction from the text available so far, and training compares that prediction with the recorded target.

In our word-level demonstration:

```text
The opposite of hot is cold
six words -> five prediction positions
```

In the repository's numeric preparation:

```text
window = [7, 20, 4, 2, 6]
x      = [7, 20, 4, 2]
y      = [20, 4, 2, 6]
```

Try the transfer case: “Birds fly over the calm lake.” What is the input at the final cut? What is the target? You should get “Birds fly over the calm” as the input and “lake” as the target.

Remember one sentence: **show the sequence so far; predict the recorded next piece**.

We now know what one training question looks like. That creates the next question naturally: what model, data, hardware, budget, and sequence of stages will turn billions of these prediction positions into a trained checkpoint? That is the map we will build in Lesson 2.

### Production Fact-Check Notes

- **Source fact:** Causal language modeling predicts the next token using only tokens to its left.
- **Observed repository behavior:** `PackedTokenDataset.sample_batch` creates `x` and `y` by shifting one token-ID window, while `GPT.forward` compares predictions at every position with the aligned targets.
- **Teaching simplification:** visible words stand in for tokens only for the hand-worked introduction. Prefix pairs are a conceptual expansion of the prediction positions inside one shifted window.
