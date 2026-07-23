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

Before a later rule can divide text into tokens, three jobs must be handled.

### Job 1: Identify the characters

Software needs a stable answer to one question:

> Which written character is this?

Unicode supplies that shared system. Each character has a numerical identifier called a **code point**.

### Job 2: Store or transmit the text

The text must be stored or sent. UTF-8 represents it as one or more **bytes**.

### Job 3: Prepare the text

Source text can contain different Unicode forms, newline styles, trailing spaces, or repeated blank lines. A preparation policy decides which features to make consistent.

The jobs connect, but they are not interchangeable:

```text
code point -> identifies a character
UTF-8 byte -> stores part of the encoded text
preparation rule -> changes text according to a chosen policy
```

Later stages add token IDs and embeddings, which have different jobs again. Keep this boundary visible:

```text
Unicode code point ≠ UTF-8 byte ≠ token ID ≠ embedding
```

All four involve numbers, but the numbers do different work.

We will begin by giving each character a stable identity. That building block will let us ask a different question about storage.

## 04:20 Representing Characters with Unicode

Consider the character `A`. Before checking, predict what Python will do with:

```python
ord("A")
```

Does Python invent a number for this particular `A`, or follow a shared agreement?

```python
ord("A") == 65
```

Python follows Unicode, a shared standard that assigns agreed numbers to characters. The assigned number is called a **code point**, so `65` is the code point for `A`.

The code point identifies the written character. It does not contain the character’s meaning.

Depending on context, `A` might be a school grade, a musical note, a blood type, or part of a name. Its Unicode code point remains `65` in every case.

Now trace the word `Cat` one character at a time:

```text
C -> 67
a -> 97
t -> 116
```

That gives us:

```text
[67, 97, 116]
```

This is an early numerical representation of the text. It is not yet the numerical input used during later AI training.

A code point now gives each character a stable identity. It still does not tell us which storage units represent the text, so that becomes our next question.

## 05:50 Storing Unicode Text with UTF-8

A byte is a small unit of storage. When we display its unsigned value, it is a number from `0` through `255`. UTF-8 is a common rule for representing Unicode text as one or more bytes.

You know the code points for `Cat`. Before looking, will its UTF-8 byte values match or differ?

For `Cat`, Python shows this UTF-8 byte list:

```text
[67, 97, 116]
```

For these basic Latin characters, UTF-8 uses one byte with the same value as the code point.

These characters are in a range historically called ASCII. The matching values are convenient, but they are not a universal rule. Other characters can use several UTF-8 bytes.

The values match here, but their jobs differ. A code point identifies a character. A byte stores part of its UTF-8 representation.

Neither the code-point list nor the byte list is a list of token IDs or embeddings.

We can now identify and store the characters. Yet source files can still differ in Unicode form, newlines, or invisible controls. How should the repository make those differences consistent?

## 07:00 Preparing Text Consistently

Representation identifies and stores the text. **Preparation** applies the project’s chosen consistency rules before later processing.

A text-preparation policy may:

- normalize selected Unicode forms;
- make newline styles consistent;
- remove selected control characters;
- remove trailing or outer whitespace; or
- reduce repeated blank lines.

A preparation rule can deliberately remove a distinction from the source.

For example, NFKC changes the circled digit `①` into the ordinary digit `1`. Both results contain one Python character, but a distinction in the source has disappeared.

```text
① -> 1
```

Character count can change in a different example. NFKC changes the single typographic ligature `ﬀ` into the two characters `ff`, so the Python string length changes from `1` to `2`.

```text
ﬀ -> ff
length 1 -> 2
```

The rule does not ask what the writer meant. It applies the chosen policy consistently.

> **Prepared text follows a chosen policy. It is not necessarily a lossless copy of the source.**

Now the name **text preparation** refers to a job we understand. How does this repository perform that job, step by step?

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

The annotations tell readers that this function expects and returns text; `str(text)` is the operation that explicitly asks Python for a string.

Now follow every operation in source order:

```text
str(text)
-> NFKC
-> newline standardization
-> selected control-character removal
-> per-line trailing-whitespace removal
-> outer stripping
-> blank-line-run limiting
-> return prepared string
```

After `str(text)` supplies a string, `unicodedata.normalize("NFKC", ...)` applies the compatibility rule we just tested with `①` and `ﬀ`.

The next line standardizes Windows and older Mac newlines as `\n`. `_CONTROL_RE` then removes the selected control characters, and the list step removes trailing whitespace from each line.

Joining rebuilds the text, while `strip()` removes outer whitespace. Finally, `_BLANK_LINES_RE` limits each run of blank lines to one blank line, and the function returns the prepared string.

The repository then uses the prepared result:

```python
normalized = normalize_text(text)
"text": normalized,
"num_chars": len(normalized),
```

Both the stored text and `num_chars` describe the normalized result, not the untouched source.

The output of `normalize_text` is still Unicode text. It has been prepared according to the repository's policy, but later stages have not yet divided it into reusable pieces or produced the numerical input used during training.

A precise description is:

```text
source text
-> apply fixed preparation rules
-> prepared Unicode text
-> later AI-training stages [closed]
```

We have traced the policy from input to output. Before moving farther, let’s test whether we can predict the simpler representation steps ourselves.

## 10:45 Predict, Run, and Explain

Use this companion file to inspect the representation of `Cat`:

```python
text = "Cat"

print("Human-readable text:", text)
print("Unicode code points:", [ord(character) for character in text])
print("UTF-8 bytes:", list(text.encode("utf-8")))
print("Ready for later AI training? Not yet")
print("Tokens, token IDs, and embeddings belong to later stages.")
```

Before you run it, pause. Predict both lists:

- the Unicode code-point list; and
- the UTF-8 byte list.

Can you also explain why the values should match for these three characters? Now run:

```bash
python course/templates/video/final_script_v1_lab.py
```

You should observe five lines:

```text
Human-readable text: Cat
Unicode code points: [67, 97, 116]
UTF-8 bytes: [67, 97, 116]
Ready for later AI training? Not yet
Tokens, token IDs, and embeddings belong to later stages.
```

Now explain the result from the rules:

- `ord(character)` follows the Unicode agreement from each character to its code point;
- `text.encode("utf-8")` converts the Unicode string into UTF-8 bytes; and
- `list(...)` exposes the individual byte values so that we can inspect them.

For `Cat`, the two lists match because these characters are in the ASCII range. The final two lines remind us that representation and preparation are only the early stages.

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

This companion lab does not call `normalize_text`; it tests character representation and byte encoding. Keep the preparation prediction separate.

Under the repository’s NFKC policy, predict both results:

```text
① -> ?
ﬀ -> ?
```

The prepared forms are:

```text
① -> 1
ﬀ -> ff
```

These examples still test different jobs:

```text
ord and UTF-8 encoding -> inspect character representation and storage
normalize_text         -> prepare source text according to repository rules
```

Predict, run, observe, explain, change, and compare. That cycle tests the rules instead of your memory of one output.

## 13:20 Return to the Whole Route

We began with one larger question:

> **How can AI learn from written examples?**

Today we solved one prerequisite in three steps:

```text
Unicode code point -> identifies a character
UTF-8 byte        -> stores part of the encoded text
preparation rule  -> makes a selected feature consistent
```

These stages produce prepared Unicode text. They have not divided it into pieces, assigned identifiers to those pieces, or selected learned number lists.

The later route is:

```text
prepared text
-> reusable text pieces [tokens]
-> one identifier per piece [token ID]
-> learned number list selected using that ID [embedding]
-> later AI-training stages [closed]
```

So “turning text into numbers” is too vague. Different numerical forms have different jobs:

- code points identify characters;
- bytes store encoded text;
- token IDs identify tokens; and
- embeddings are learned number lists selected using token IDs.

You can now draw a clean boundary between today’s fixed rules and the later training process:

> **Representing and preparing text changes the data according to fixed rules. Later training uses examples and measured error to change adjustable internal numbers.**

Use that distinction now. Classify each action by its job:

1. `ord("A")` returns `65`.
2. UTF-8 stores `Cat` as `[67, 97, 116]`.
3. A repository rule converts `\r\n` to `\n`.
4. A tokenizer divides prepared text into reusable pieces.
5. A later training step changes adjustable internal numbers after measuring error.

The answers are:

1. Unicode character representation;
2. byte encoding for storage or transmission;
3. text preparation;
4. a later AI-training input step; and
5. a later training change.

One building block now carries forward: a code point is a stable character identifier. Software can use those identifiers to collect characters consistently.

That creates Video 2’s question:

> **How can software use stable character numbers to build a dependable character set?**
