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

## 07:00 Preparing Text with Explicit Cleanup Steps

We can now identify the characters and store the text. But stored text can still contain differences that matter to software, even when a reader barely notices them.

[On screen: a short text sample with extra spaces, mixed line endings, `①`, and `ﬀ`]

Look at the sample. It has spaces around the lines, an empty line, a circled digit, and a joined `ﬀ` symbol.

Should every difference remain? There is no universal answer. We first choose what the next use of the text requires.

Suppose we want two non-empty lines with no surrounding whitespace. We also choose to replace the two special-looking forms with simpler forms.

We can choose one fixed cleanup step, such as removing the extra spaces around a line.

Each cleanup step follows a fixed choice. The complete sequence of steps is called **text preparation**.

Now consider the circled digit. Before we name the operation, predict whether our chosen cleanup leaves it alone or changes it.

First, look only at this change: `①` becomes `1`.

One possible cleanup step replaces certain special-looking characters with simpler equivalents. Changing text into a chosen standard form is called **normalization**.

**NFKC** is the name of one Unicode normalization rule. In these examples, it changes `①` to `1` and `ﬀ` to `ff`.

Trace both changes:

```text
① -> 1
length 1 -> 1

ﬀ -> ff
length 1 -> 2
```

The first change keeps the same length. The second turns one character into two, so the length changes.

Normalization is one preparation step. It is not the whole preparation job.

These cleanup steps may change or remove details from the original text.

We have named the larger job and one step inside it. Now we need a complete example that shows every chosen step from source text to prepared text.

## 08:15 Build a Self-Contained Text-Preparation Example

Our source string contains extra spaces and two ways of marking a new line. Those marks are easy to miss when a terminal prints the string normally.

`repr` makes hidden marks such as `\r\n` and surrounding spaces visible in the terminal.

Create a file named `text_preparation.py` with this complete example:

```python
import unicodedata


def prepare_text(text):
    text = unicodedata.normalize("NFKC", text)
    lines = [line.strip() for line in text.splitlines()]
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines)


source = "  ① cat ﬀ  \r\n\r\n  second line  "

print("Source text:", repr(source))
print("Prepared text:", repr(prepare_text(source)))
```

Follow the function from top to bottom.

The first line inside the function applies the NFKC change we just traced. Next, `splitlines` splits the string wherever Python recognizes a common line-ending mark.

For each line, `strip` removes surrounding whitespace. The next line keeps only lines that still contain something.

Finally, `join` puts the remaining lines back together. It places one `\n` between them.

The complete trace is:

```text
source string
-> NFKC normalization
-> split into lines using common line-ending marks
-> remove surrounding whitespace from each line
-> remove empty lines
-> join the remaining lines with \n
-> prepared string
```

These are the cleanup choices in this example. Code, poetry, or other text may need different choices.

The mechanism is now visible. Let’s predict the result, run both files, and compare the evidence with our mental model.

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

Open a terminal in the folder containing the two files.

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

Now turn to `text_preparation.py`.

Before we run the second file, predict which parts of the source text will change.

Run:

```bash
python text_preparation.py
```

The program prints:

```text
Source text: '  ① cat ﬀ  \r\n\r\n  second line  '
Prepared text: '1 cat ff\nsecond line'
```

Follow the source through the function. NFKC changes `①` and `ﬀ`. Then `splitlines` creates three lines, including the empty middle line.

`strip` removes the surrounding spaces. The filter removes the empty line. Finally, `join` rebuilds the two remaining lines with one `\n`.

Now replace `①` with `Cat`. Before you run the file again, predict which parts of the output will change and which cleanup steps will behave the same way.

Run, compare, and explain the result. Then restore `①`.

We have now completed both loops: predict, run, observe, trace, change one input, and predict again.

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
