# Video 1: From a Sentence to a Training Example

**Subtitle:** How text becomes input and target data for next-token prediction

**Learning objective:** Given a short sequence, create and explain its shifted input and target rows.

**Estimated runtime:** 11 minutes 45 seconds, including prediction pauses and the terminal demonstration.

**Production direction:** Compose for 16:9. Use one consistent cool color for input and one consistent warm color for target. Narration is spoken; visual directions, code, commands, outputs, and fact-check notes are not read word for word.

## 00:00 Hook

### Visual / Animation

- Open on four simple interface cards: an improved email, a continued paragraph, a short answer, and a code suggestion.
- Bring in the title: `Large Language Model (LLM)`.
- Replace the cards with one line: `The opposite of hot is ___`.
- Hold the blank for two seconds before revealing `cold`.
- End on the question: `How do we train an LLM from text?`

### Narration

Hi.

I’m sure you’ve seen what systems such as ChatGPT, Claude, and Gemini can do. They can improve an email, answer a question, continue a paragraph, and even suggest code.

These systems are built around a **large language model**, or **LLM** for short. An LLM is a mathematical model with many learned parameters. During base pretraining, it learns patterns from a large amount of text.

But how do we train an LLM from text?

Let’s make that question smaller. Complete this sentence:

```text
The opposite of hot is ...
```

You probably thought of “cold.” You saw the words so far and predicted what comes next.

That is where we will start. We will take one complete sentence and turn it into practice data for a language model. By the end of this lesson, you will do it by hand and with a few lines of Python.

## 01:10 Intuition

### Visual / Animation

- Show the complete sentence as six word tiles: `The opposite of hot is cold`.
- Place a vertical cut before `cold`.
- Move the cut from left to right while the input grows.
- Stop before revealing the count and ask: `Six words. How many prediction positions?`

### Narration

Start with the complete sentence:

```text
The opposite of hot is cold
```

We already know the final word is “cold.” So the answer is already inside the text. We only need to hide it.

Place a cut before the final word:

```text
The opposite of hot is | cold
```

The **words before the cut** are shown to the model. The **recorded word after the cut** is what we ask the model to predict.

Now move the cut:

```text
The | opposite of hot is cold
The opposite | of hot is cold
The opposite of | hot is cold
The opposite of hot | is cold
The opposite of hot is | cold
```

Each cut gives us a new place to make a prediction. We call each place a **prediction position**.

Our sentence has six words and five prediction positions. Why five? The first word has no earlier word before it. Every word after the first can be the next recorded word.

Now that the idea is clear, let’s name the two sides of the cut.

## 02:20 Technical Meaning

### Visual / Animation

- Return to the final cut.
- Label the left side `input`, the right side `target`, and the pair `training example`.
- Show `text → tokenization → tokens → token IDs`.
- Add a small boundary card: `Words are the simple example. The real pipeline shifts token IDs.`

### Narration

The text we give the model is the **input**.

The recorded next word in this example is the **target**.

The input and its target form a **training example**.

During training, the model makes a prediction from the input. We compare that prediction with the target. Later in the course, we will see how that comparison becomes a loss and how the loss is used to adjust the model’s parameters.

One point is important here. The target is not always the only possible answer. It is the continuation recorded in this training text. Another continuation may also make sense, but this is the one the model sees in this example.

So far, we have used words because they are easy to see. A real language model does not split every sentence into words exactly as we did.

The process of breaking text into smaller pieces is called **tokenization**. Each piece is a **token**. A token may be a whole word, part of a word, punctuation, or another unit chosen by the tokenizer.

The tokenizer assigns an integer to each token. That integer is called a **token ID**. A list of token IDs is a **sequence**.

**Teaching simplification:** the words on screen are stand-ins for tokens. The real repository applies this same shift to token IDs.

Our five cuts help us see five prediction positions. They are not five independently stored sentences. The code keeps the relationship compactly in one shifted training window.

## 03:30 Tiny Example

### Visual / Animation

- Build the five prefix questions one row at a time.
- Count from one to five.
- Replace them with two aligned rows labelled `inputs` and `targets`.
- Draw a guide from each input position to the target one place ahead.

### Narration

Let’s write the five prediction questions:

```text
The                         -> opposite
The opposite                -> of
The opposite of             -> hot
The opposite of hot         -> is
The opposite of hot is      -> cold
```

Look at the first row. The input is “The,” and the target is “opposite.”

Now look at the last row. The input is “The opposite of hot is,” and the target is “cold.”

For this simple word-level example:

```text
prediction positions = number of words - 1
                     = 6 - 1
                     = 5
```

Writing every growing input helps us understand the idea. But we do not need to store five copies of the sentence. We can show the same relationship with two shifted rows.

Remove the last word to create the input row. Then remove the first word to create the target row:

```text
inputs:   The       opposite   of    hot   is
targets:  opposite  of         hot   is    cold
```

The target row is one position ahead of the input row. At every column, the target is the recorded word that came next.

The same rule works with token IDs. Let’s look at the exact code used by this repository.

## 05:10 Repository Walkthrough

### Visual / Animation

- Open `matgpt/training/dataset.py` and isolate the three lines that create `window`, `x`, and `y`.
- Replace the long token stream with the toy window `[7, 20, 4, 2, 6]`.
- Animate the last ID leaving `x` and the first ID leaving `y`.
- Align each `x` position with its `y` target.
- Show a small shield over future positions labelled `cannot look ahead`.

### Narration

In the training code, we begin with a short window of token IDs. The window contains one extra ID so we can create both the input and the target:

```python
window = shard.data[start : start + context_length + 1]
x[row] = window[:-1]
y[row] = window[1:]
```

The input is called `x`. The target is called `y`.

`window[:-1]` removes the last token ID. That gives us `x`.

`window[1:]` removes the first token ID. That gives us `y`.

Now use a small window that we can check by hand:

```text
window = [ 7, 20, 4, 2, 6 ]
x      = [ 7, 20, 4, 2    ]
y      = [    20, 4, 2, 6 ]
```

The model receives the whole input row. It makes a prediction at each position, and each prediction is compared with the token ID in the same position in `y`.

At the second position, the model can use the text up to that position. It cannot look at later positions. The model uses a **causal mask** to block that future information. We will open that mechanism later in the course.

The shifted rows do not mean that each isolated input word is the whole context. The rows show the alignment. The growing inputs show the context available at each position. They are two views of the same next-token prediction task.

That is exactly what this repository does: `window[:-1]` creates the input row, `window[1:]` creates the target row, and causal self-attention stops each position from reading future positions.

## 07:20 Live Mini-Lab

### Visual / Animation

- Open `course/videos/001-computer-learning-from-text/lab.py`.
- Hold on the sentence and ask for two predictions: the number of positions and the shifted toy ID rows.
- Run the command in a full-width terminal.
- Highlight the five prefix questions, then the `x` and `y` rows.
- Change only the sentence to `Birds fly over the calm lake` and pause for a transfer prediction.

### Narration

Now let’s test the rule with Python.

Before we run anything, make two predictions.

First, our sentence has six words. How many prediction positions should the program print?

Second, for the window `[7, 20, 4, 2, 6]`, what should `x` and `y` contain?

Pause here if you need a moment.

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

That is the shift we just made by hand. The program is preparing training data. It is not training a model yet.

Now change the sentence to:

```text
Birds fly over the calm lake
```

Count the words before you run the program again. This sentence also has six words, so it should also give us five prediction positions.

The sentence changed, but the rule stayed the same. That tells us we understand the rule instead of memorizing one answer.

## 09:40 Common Mistakes

### Visual / Animation

- Present four short correction cards one at a time.
- Keep the corrected statements on screen as a checklist.
- End with `recorded target ≠ unique truth` and `word example ≠ real tokenization`.

### Narration

Before we finish, let’s make four points clear.

First, the target is not always the only correct continuation. It is the recorded continuation in this sequence.

Second, one item in `x` is not the whole input by itself. At each position, the model can use the earlier input positions too.

Third, we used words in our first example because they are easy to see. That is a teaching simplification. The real model works with tokens and token IDs.

Fourth, next-token prediction is the base pretraining task for the decoder-only model in this course. It is not the only way every LLM is trained. Post-training can use demonstrations, preferences, rewards, and other objectives.

And although the text supplies the targets, people still choose, license, filter, clean, and evaluate the training data.

## 10:50 Recap And Exercise

### Visual / Animation

- Build the chain: `recorded text → tokens → token IDs → shift by one → x + y`.
- Reconstruct the original sentence from the two shifted rows.
- Show `Birds fly over the calm lake` and ask the learner to trace the final target.
- Transform the first token ID into a small vector labelled `embedding`.
- End on the question: `How does a token ID become numbers the network can use?`

### Narration

There are two key points to remember.

First, nobody needs to write a separate answer sheet for every next-token prediction. The target is already in the recorded text.

Second, one sequence gives us several prediction positions. We keep them compactly by shifting the sequence by one position.

Here is the complete chain:

```text
recorded text
→ tokens
→ token IDs
→ one shifted training window
→ input row x and target row y
→ next-token prediction at each position
```

For our numeric example:

```text
window = [7, 20, 4, 2, 6]
x      = [7, 20, 4, 2]
y      = [20, 4, 2, 6]
```

Now try one final example: “Birds fly over the calm lake.” At the final cut, the input is “Birds fly over the calm,” and the target is “lake.”

That’s it. We started with a sentence and created the input and target data used for next-token prediction.

But a token ID is only an identifier. The number `20` does not contain the meaning of a token. The training program gives token IDs to the model, and the model’s first step converts each ID into an **embedding**. An embedding is a learned vector of numbers that the network can work with.

That gives us the next question: how does a token ID become an embedding? That is what we will build in Lesson 2.

### Production Fact-Check Notes

- **Source fact:** Causal language modeling predicts the next token using only earlier tokens.
- **Observed repository behavior:** `PackedTokenDataset.sample_batch` creates `x` and `y` by shifting one token-ID window, while `GPT.forward` compares predictions at every position with the aligned targets.
- **Teaching simplification:** visible words stand in for tokens only for the hand-worked introduction. Prefix pairs are a conceptual expansion of the prediction positions inside one shifted window.
