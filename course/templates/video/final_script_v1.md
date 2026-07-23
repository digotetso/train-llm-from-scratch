# Video 1 — Before AI Can Learn: How Computers Represent and Prepare Text

*Script 4*

**Subtitle:** How Unicode identifies characters, how UTF-8 stores them as bytes, and how text is prepared before tokenization and AI training

## 00:00 The Big Question and Today’s First Step

You may have seen an AI clarify an email, improve a sentence, or suggest a piece of code. The result can feel immediate: you enter words, and useful new words appear.

That experience raises the larger question for this course:

> **How can AI learn from written examples?**

We will build the answer one step at a time. Before AI can learn from text, software must first be able to identify the characters, store the text, and prepare it consistently. Later stages can divide the prepared text into reusable pieces and turn those pieces into the numerical input used during training.

So this video focuses on one prerequisite question:

> **How do computers represent and prepare text before AI can learn from it?**

By the end, you will be able to explain:

1. how Unicode gives characters stable numerical identifiers;
2. how UTF-8 stores text as bytes;
3. how the repository normalizes and cleans source text; and
4. why these early numerical forms are not yet token IDs, embeddings, or the numerical input used during later training.

## 01:00 Where This Video Fits in AI Training

Here is the larger route that this course will follow. Read it as a dependency map: each stage supplies something a later stage needs. The map shows those dependencies without pretending that every arrow is already explained.

```text
Written source text
├── represented in software
│   ├── characters have Unicode code points
│   └── UTF-8 represents the text as bytes
│
└── prepared for later processing
    └── normalize and clean the source text
        -> prepared training text
        -> reusable text pieces [tokens]
        -> one identifier per piece [token ID]
        -> use the ID to select a learned number list [embedding]
        -> later AI-training stages [closed]
```

You do not need to memorize the route. We will use it to keep today’s work in the right place.

First, software needs a stable way to tell one written character from another. A shared system supplies that identifier; we call the system **Unicode**, and we call each identifier a **code point**.

The text also needs a form that can be stored or sent between systems. **UTF-8** does that job by representing Unicode text as bytes. Preparation rules can then make selected features of the source text consistent.

After preparation, a later rule can divide the text into reusable pieces, called **tokens**. Each piece can receive one integer identifier, called a **token ID**. That ID can select a learned number list, called an **embedding**.

Those names are signposts, not explanations. Every arrow can hide a mechanism that deserves its own lesson, so we close the remaining AI-training stages for now.

Today we will open only three jobs: identify the characters, represent the text as bytes, and prepare the text consistently. Once those jobs make sense, their names can become building blocks for the later route.

## 03:00 Three Jobs Before Tokenization

Before a training system can tokenize text, three different jobs must be handled.

### Job 1: Identify the characters

The software needs a stable answer to this question:

> Which written character is this?

Unicode provides the shared character system. Each character has a numerical identifier called a **code point**.

### Job 2: Store or transmit the text

The software also needs a way to store the text or send it between systems. UTF-8 represents Unicode text as one or more **bytes**.

### Job 3: Prepare the text

Source text can contain different Unicode forms, newline styles, selected control characters, trailing spaces, or repeated blank lines. A preparation policy decides which of these features to make consistent.

These jobs are connected, but they are not interchangeable:

```text
code point -> identifies a character
UTF-8 byte -> stores part of the encoded text
preparation rule -> changes text according to a chosen policy
```

The later training pipeline introduces more numerical forms:

```text
token ID -> identifies a token
embedding -> learned number list selected for that token ID
```

One boundary is therefore especially important:

```text
Unicode code point ≠ UTF-8 byte ≠ token ID ≠ embedding
```

All four can involve numbers, but the numbers have different jobs.

## 04:20 Representing Characters with Unicode

Consider the written character `A`.

Before checking, predict what Python will do with this expression:

```python
ord("A")
```

Does Python invent a number for this particular `A`? No. It follows the Unicode standard.

```python
ord("A") == 65
```

`A` is a **character**. Unicode is a shared standard that defines characters and assigns agreed numbers to them. The number assigned to a character is called its **code point**.

Therefore, `65` is the Unicode code point for `A`. Python’s `ord` function did not discover the meaning of `A`, and it did not create a new number. It followed the Unicode agreement.

The code point identifies the written character. It does not contain the character’s meaning.

Depending on context, `A` might be a school grade, a musical note, a blood type, or part of a name. Its Unicode code point remains `65` in every case.

Now trace the word `Cat` one character at a time:

```text
C -> 67
a -> 97
t -> 116
```

The code-point list is therefore:

```text
[67, 97, 116]
```

Each character follows the same stable Unicode agreement.

This is an early numerical representation of the text. It is not yet the sequence of numbers that a language model uses in its calculations.

## 05:50 Storing Unicode Text with UTF-8

A **byte** is a stored number from `0` through `255`. UTF-8 is a common rule for storing Unicode text as one or more bytes.

For `Cat`, the UTF-8 byte list is:

```text
[67, 97, 116]
```

That happens to match the code-point list. These three characters are in the ASCII range, where UTF-8 uses one byte with the same numerical value as the code point.

But this match is not universal. Other characters can require more than one UTF-8 byte.

This gives us two related but separate observations:

```text
C, a, t have Unicode code points 67, 97, and 116
"Cat" is stored in UTF-8 as bytes 67, 97, and 116
```

For this example, the values match. Their jobs are still different. A code point identifies a character under the Unicode standard. A byte stores part of the UTF-8 encoding.

Neither the code-point list nor the byte list is a list of token IDs or embeddings.

## 07:00 Preparing Text Consistently

Representation tells software which characters it has and how the text can be stored. Preparation decides how the project wants that source text to be handled before later processing.

A text-preparation policy may:

- normalize selected Unicode forms;
- make newline styles consistent;
- remove selected control characters;
- remove trailing or outer whitespace; or
- reduce repeated blank lines.

Preparation is not always a neutral copy. A chosen rule may deliberately remove a distinction from the source.

For example, NFKC normalization can change:

```text
① -> 1
```

The source contains a circled digit. The normalized result contains an ordinary digit. A distinction in the source has collapsed, and the character count can change.

That gives us an important principle:

> **Prepared text follows a chosen policy. It is not necessarily a lossless copy of the source.**

Now we can inspect the repository’s preparation function with the right question:

> **What changes in the text before it becomes prepared training data?**

## 08:15 Apply Text Preparation in the Repository

Here is the function:

```python
def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_RE.sub("", text)
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines).strip()
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text
```

Trace the text from top to bottom.

First, `str(text)` produces a Python string. The annotation `text: str` communicates the intended input type, and `-> str` communicates the intended return type. Python does not automatically enforce those annotations at runtime. The explicit call to `str` performs the conversion here.

Next, `unicodedata.normalize("NFKC", ...)` makes selected Unicode forms consistent.

Then these replacements:

```python
text.replace("\r\n", "\n").replace("\r", "\n")
```

convert different newline styles to `\n`.

The next line removes the selected control characters defined by the repository:

```python
text = _CONTROL_RE.sub("", text)
```

The list step removes trailing whitespace from every line:

```python
lines = [line.rstrip() for line in text.split("\n")]
```

Joining rebuilds the text, and `strip()` removes whitespace from the beginning and end:

```python
text = "\n".join(lines).strip()
```

Finally, `_BLANK_LINES_RE` limits a run of blank lines to one blank line, and the function returns the prepared string.

The repository then uses the prepared result:

```python
normalized = normalize_text(text)
"text": normalized,
"num_chars": len(normalized),
```

Both the stored text and `num_chars` describe the normalized result, not the untouched source.

The output of `normalize_text` is still Unicode text. It has been prepared according to the repository’s policy, but it has not been divided into tokens or converted into token IDs or embeddings.

A precise description is:

```text
source text
-> apply fixed preparation rules
-> prepared Unicode text
-> later tokenization and model-input steps
```

## 10:45 Predict, Run, and Explain

Use this small program to inspect the representation of `Cat`:

```python
text = "Cat"

print("Human-readable text:", text)
print("Unicode code points:", [ord(character) for character in text])
print("UTF-8 bytes:", list(text.encode("utf-8")))
print("Model-ready training input? Not yet")
print("Later stages produce tokens, token IDs, and embeddings.")
```

Before running it, predict:

- the Unicode code-point list; and
- the UTF-8 byte list.

Then run:

```bash
python course/videos/001-computer-learning-from-text/lab.py
```

The expected output is:

```text
Human-readable text: Cat
Unicode code points: [67, 97, 116]
UTF-8 bytes: [67, 97, 116]
Model-ready training input? Not yet
Later stages produce tokens, token IDs, and embeddings.
```

Line by line:

- `ord(character)` follows the Unicode agreement from each character to its code point;
- `text.encode("utf-8")` converts the Unicode string into UTF-8 bytes; and
- `list(...)` exposes the individual byte values so that we can inspect them.

For `Cat`, the two numerical lists match because the characters are in the ASCII range.

Now change only this line:

```python
text = "A"
```

Before running the program again, predict the result:

```text
Unicode code points: [65]
UTF-8 bytes: [65]
```

Run the same command, compare the result with your prediction, and explain it using the same Unicode and UTF-8 rules. Then restore `Cat`.

You can apply the same predict-and-explain method to the preparation function. Under the repository’s NFKC policy, predict what happens to:

```text
①
```

The prepared character is:

```text
1
```

The representation example and the preparation example test different jobs:

```text
ord and UTF-8 encoding -> inspect character representation and storage
normalize_text         -> prepare source text according to repository rules
```

This cycle—predict, run, observe, explain, change, and compare—tests the rules instead of your memory of one output.

## 13:20 Return to the Whole Route

We began with the larger question:

> **How can AI learn from written examples?**

This video opened the prerequisite stages that prepare text for the later training pipeline.

First, Unicode gives characters stable code points:

```text
A -> 65
```

Second, UTF-8 represents Unicode text as bytes for storage or transmission:

```text
Cat -> [67, 97, 116]
```

Third, preparation rules make selected features of source text consistent:

```text
source text -> normalized, prepared text
```

These stages make text usable for the next parts of the pipeline. They do not yet produce token IDs, embeddings, predictions, or parameter updates.

The later route is:

```text
prepared text
-> tokens
-> token IDs
-> embeddings
-> model calculations
-> prediction
-> measured error
-> updated parameters
```

Do not collapse the early stages into one vague idea of “turning text into numbers.” Different numerical forms have different jobs:

- code points identify characters;
- bytes store encoded text;
- token IDs identify tokens; and
- embeddings provide learned numerical values for model calculations.

This is where the brief boundary with learning belongs:

> **Representing and preparing text changes the data according to fixed rules. Training changes adjustable model parameters by using examples and measured error.**

The distinction matters, but it is not the main subject of this video. The main subject is how written text becomes consistent computer data on the way to AI training.

Before moving on, classify each action by its job:

1. `ord("A")` returns `65`.
2. UTF-8 stores `Cat` as `[67, 97, 116]`.
3. A repository rule converts `\r\n` to `\n`.
4. A tokenizer divides prepared text into reusable pieces.
5. A training update changes model parameters after measuring error.

The answers are:

1. Unicode character representation;
2. byte encoding for storage or transmission;
3. text preparation;
4. a later model-input step; and
5. model learning.

We are now ready for Video 2’s question:

> **How can software use stable character numbers to build a dependable character set?**
