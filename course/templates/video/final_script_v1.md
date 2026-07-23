# Video 1 — Before AI Can Learn: How Computers Represent and Prepare Text

*Script 4*

**Subtitle:** How Unicode identifies characters, how UTF-8 stores them as bytes, and how text is prepared before tokenization and AI training

## 00:00 The Big Question and Today’s First Step

You may have seen an AI clarify an email, improve a sentence, or suggest a piece of code. The result can feel immediate: you enter words, and useful new words appear.

That experience raises the larger question for this course:

> **How can AI learn from written examples?**

We will build the answer one step at a time. Before AI can learn from text, software must first be able to identify the characters, store the text, and prepare it consistently. Later stages can split the prepared text into reusable pieces and turn those pieces into the numerical input used during training.

So this video focuses on one prerequisite question:

> **How do computers represent and prepare text before AI can learn from it?**

By the end, you will be able to explain:

1. how Unicode gives characters  numerical identifiers;
2. how UTF-8 stores text as bytes;
3. how the repository normalizes and cleans source text; and
4. why these early numerical forms are not yet token IDs, embeddings, or the numerical input used during later training.

## 01:00 Where This Video Fits in AI Training

Here is the course route. Each stage supplies something a later stage needs. Treat this as a dependency map, not a complete explanation. We will details of each stage as the course progresses.

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

Use the map only to place today’s work.

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


[show messy text example]

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

## 04:20 Identifying Characters with Code-Point Numbers

Look at `A`. You and I recognize it immediately, but software still needs a dependable way to tell it apart from `B`, `a`, or `🐱`.

That gives us a small question. If two computers inspect `A`, should they invent separate numbers, or should they follow the same fixed assignment?

Before we name the rule, make a prediction: does Python invent a new number for `A`, or follow a fixed number?

[On screen: If Python is not installed, visit https://www.python.org/downloads/]

Unicode is a character-numbering standard. For each single character in today’s examples, it assigns a code-point number.

Python already includes a function named `ord`. It reports the code-point number for one character.

```python
ord("A")
```

Python reports:

```text
65
```

The number `65` identifies `A`. It does not explain what `A` means.

In one sentence, `A` could be a grade. In another, it could be a musical note or part of a name. The context changes, but the code-point number stays the same.

Now trace `Cat` one character at a time:

```text
C -> 67
a -> 97
t -> 116
```

So the three code-point numbers are:

```text
[67, 97, 116]
```

Some visible symbols are built from several code points. We will leave that case for a later lesson.

We can now identify the example characters. But identification creates the next question: how can software store or send those characters?

## 05:50 Representing Text with UTF-8 Bytes

Before we name the storage method, predict: will every single character always need exactly one small storage unit?

A byte is a small unit of storage. Python displays each byte as a non-negative number from `0` through `255`.

UTF-8 turns text into an ordered sequence of bytes that software can store or send.

For `Cat`, the code-point numbers are:

```text
[67, 97, 116]
```

Its UTF-8 byte numbers are also:

```text
[67, 97, 116]
```

That match can tempt us into treating the two lists as the same thing. Let’s test that idea with `🐱`.

The emoji has this code-point number:

```text
[128049]
```

Its UTF-8 representation has four byte numbers:

```text
[240, 159, 144, 177]
```

The four byte numbers work together, in order, to store or send `🐱`.

For `Cat`, the code-point numbers happen to match the UTF-8 byte numbers. The cat emoji proves that this match is not a rule.

A code-point number identifies an example character. A UTF-8 byte sequence represents the text for storage or transmission.

Now we can identify the characters and represent the text as bytes. Yet the same visible text can still arrive with extra spaces, empty lines, or special character forms. That creates our preparation question.

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

The next line turns Windows-style `\r\n` and standalone `\r` into `\n`. `_CONTROL_RE` then removes selected control characters, and the list step removes trailing whitespace from each line.

Joining rebuilds the text, while `strip()` removes outer whitespace. Finally, `_BLANK_LINES_RE` limits each run of blank lines to one blank line, and the function returns the prepared string.

The repository then uses the prepared result:

```python
normalized = normalize_text(text)
"text": normalized,
"num_chars": len(normalized),
```

Both the stored text and `num_chars` describe the normalized result, not the untouched source.

The output of `normalize_text` is still Unicode text. It has been prepared according to the repository's policy, but later stages have not yet divided it into reusable pieces or produced the numerical input used during training.

So:

```text
source text
-> apply fixed preparation rules
-> prepared Unicode text
-> later AI-training stages [closed]
```

We have traced the policy from input to output. Before moving farther, let’s test whether we can predict the simpler representation steps ourselves.

## 10:45 Predict, Run, and Explain

Create a file named `character_representation.py`, then place this complete example inside it:

```python
text = "Cat"
print("Text:", text)
print("Code-point numbers:", [ord(character) for character in text])
print("UTF-8 byte numbers:", list(text.encode("utf-8")))

print()

text = "🐱"
print("Text:", text)
print("Code-point numbers:", [ord(character) for character in text])
print("UTF-8 byte numbers:", list(text.encode("utf-8")))
```

Before we run the file, predict both lists for `Cat`. Then predict whether `🐱` will have one code-point number and whether it will use one byte or several.

Run:

```bash
python character_representation.py
```

The program prints:

```text
Text: Cat
Code-point numbers: [67, 97, 116]
UTF-8 byte numbers: [67, 97, 116]

Text: 🐱
Code-point numbers: [128049]
UTF-8 byte numbers: [240, 159, 144, 177]
```

Trace the first half. Python visits `C`, `a`, and `t` in order. `ord` reports the code-point number for each character, while `encode` creates the ordered UTF-8 byte sequence.

Then trace the emoji. One code-point number identifies it in this example, while four byte numbers represent it for storage or transmission.

Now replace the first `Cat` with `A`. Before you run it, predict the two lines:

```text
Code-point numbers: [65]
UTF-8 byte numbers: [65]
```

Run the same command and compare the result with your prediction. Then restore `Cat`.

This loop gives us evidence for two separate jobs: code-point numbers identify the example characters, while UTF-8 byte sequences represent the text for storage or transmission.

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
