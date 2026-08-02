# Video 1 — Before AI Can Learn: How Computers Represent and Prepare Text

*Script 4*

**Subtitle:** How software identifies characters, stores text, and applies consistent cleanup before later AI work

## 00:00 The Big Question and Today’s First Step

You may have seen an AI clarify an email, improve a sentence, or suggest a piece of code. The result can feel immediate: you enter words, and useful new words appear.

That familiar experience gives us the larger question for this course:

> **How can AI learn from written examples?**

We cannot jump from the text box straight to learning. First, we need to understand what software receives.

Software must tell characters apart and represent text in a form that can be stored or sent. We may also choose to apply the same cleanup steps to every example.

So today we will answer one smaller question:

> **How do computers represent and prepare text before AI can learn from it?**

By the end, you will be able to explain:

1. how a fixed number can identify each example character;
2. how the same text becomes a sequence of small storage units;
3. how a short function applies fixed cleanup steps to an example string; and
4. why character numbers, storage sequences, and prepared text serve different purposes.

We will reason through each question by hand, then test our explanations with two Python files.

## 01:20 Three Foundations We Need First

Before we study how AI learns from written text, we need three foundations.

We need a dependable way to identify characters, a representation that can be stored or sent, and explicit choices about which source differences to preserve or change.

Each foundation answers a different question about the same text. They are related, but they do not form one fixed sequence. Different programs use them in different ways.

Later lessons will show how prepared text becomes input for AI training. We will explain each new mechanism when we reach it.

For today, keep these three questions in view:

```text
Written text
├── Which characters are present?
├── How can the text be stored or sent?
└── Which source differences should we preserve or change?
```

We will answer them one at a time. Each answer becomes a building block we can reuse.

## 02:20 Three Questions About Written Text

Let’s make those questions concrete.

When software sees `C`, `a`, or `🐱`, it needs a dependable answer:

> Which written character is this?

A fixed character number answers that first question without explaining what the character means in a sentence.

Once we understand character identity, our next teaching question appears: how can a file store or send the text? A file needs an ordered sequence of small units.

We must also decide which spaces, line endings, and alternate character forms to preserve or change.

The three answers serve different purposes. We begin with character identity because it creates the storage question.

## 03:10 How Can Software Identify a Character?

Look at `A`. You and I recognize it immediately, but software still needs a dependable way to tell it apart from `B`, `a`, or `🐱`.

Before we name the rule, make a prediction: does Python invent a new number for `A`, or follow a number fixed by an agreed standard?

Unicode is a character-numbering standard. In our examples, each character has a fixed number called a **code point**.

Python already has a function that reports the code point for a one-character string. It is named `ord`.

```python
ord("A")
```

Python reports:

```text
65
```

The number `65` identifies `A` in Unicode. It does not explain what `A` means.

`A` could be a grade, a musical note, or part of a name. Its code-point number stays the same.

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

`ord` works with one code point at a time. Some visible symbols contain several code points, but today’s examples each use one. We will return to multi-code-point text later.

We can now identify the example characters. But identification creates the next question: how can software store or send those characters?

## 04:45 How Can Software Store or Send Text?

Before we name the storage method, predict: will every character in our examples fit into exactly one small storage unit?

Software stores data in small units called **bytes**. When we turn Python’s byte sequence into a list, each byte appears as a non-negative number from `0` through `255`.

To turn text into an ordered byte sequence, we will use a standard called **UTF-8**.

For `Cat`, the code-point numbers are:

```text
[67, 97, 116]
```

You already know the character numbers for `Cat`. Before we look at its bytes, do you expect the values to match those character numbers or differ from them?

Its UTF-8 byte numbers are also:

```text
[67, 97, 116]
```

The matching lists may tempt us to think they are always equivalent. In this example, the emoji `🐱` uses one code point:

```text
[128049]
```

Before we check its bytes, make a prediction: will it need one byte or several?

Its UTF-8 representation has four byte numbers:

```text
[240, 159, 144, 177]
```

The four byte numbers work together, in order, to store or send `🐱`.

For `Cat`, the code-point numbers happen to match the UTF-8 byte numbers. The cat emoji shows that this match is not a general rule.

A code-point number identifies an example character. A UTF-8 byte sequence represents the text for storage or transmission.

We can now identify characters and represent text as bytes. But incoming text can still contain extra spaces, empty lines, different line-ending marks, or alternate character forms. That creates our preparation question.

## 06:45 How Can We Prepare Text Consistently?

[On screen: a short text sample with extra spaces, two consecutive line endings, `①`, and `ﬀ`]

Look at the sample. It has spaces around the lines, an empty line, a circled digit, and one joined symbol, `ﬀ`, that looks like two lowercase f’s.

Should every difference remain? There is no universal answer. We first decide what the next use of the text requires.

Suppose we want two non-empty lines, with surrounding whitespace removed from each line.

When several chosen cleanup steps are applied together, we call the whole process **text preparation**.

The circled digit and the joined symbol require another choice. Should our prepared text keep `①` distinct from `1`, or map both forms to one consistent result?

For this example, we choose one consistent result. Before we reveal it, what do you think `①` will become?

First, look only at this change: `①` becomes `1`.

When a rule maps selected alternate character forms to a consistent Unicode representation, that step is called **normalization**.

**NFKC** is the name of one Unicode normalization form. In our examples, it changes `①` to `1` and `ﬀ` to `ff`.

Trace both changes:

```text
① -> 1
length 1 -> 1

ﬀ -> ff
length 1 -> 2
```

The first keeps a Python string length of `1`. The second changes the length from `1` to `2`.

Normalization is one text-preparation step. It is not the whole preparation process.

NFKC can remove distinctions that matter in some text. That is why NFKC is a chosen rule for this example, not a universal definition of clean text.

We now understand one character-normalization step. Let’s combine it with spacing and line cleanup, then trace the complete result.

## 08:50 Build a Complete Text-Preparation Example

Our source string contains extra spaces and two consecutive line endings. Those marks are easy to miss when a terminal prints the string normally.

Python can make hidden marks such as `\r\n` and surrounding spaces visible in the terminal. The function that gives us this view is `repr`.

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

`import unicodedata` gives us Python’s standard Unicode tools, including the normalization function used below.

Follow the function from top to bottom.

The first line inside the function applies the NFKC changes we just traced.

The next line separates the string at the line boundaries Python recognizes. The method that performs this step is `splitlines`.

For every line, the code removes surrounding whitespace with `strip`. The following line keeps only the lines that still contain text.

The final line rebuilds the text with one `\n` between the remaining lines. The method that performs this step is `join`.

The complete trace is:

```text
source string
-> NFKC normalization
-> split at recognized line boundaries
-> remove surrounding whitespace from each line
-> remove empty lines
-> join the remaining lines with \n
-> prepared string
```

These steps define preparation for this example. Code, poetry, or other text may need different choices.

Now let’s predict, run both files, and compare the results.

## 10:50 Predict, Run, and Explain

[On screen: If Python is not installed, visit https://www.python.org/downloads/]

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

First, trace the `Cat` output. Python visits `C`, `a`, and `t` in order. `ord` reports each code-point number. `text.encode("utf-8")` creates the ordered byte sequence, and `list(...)` exposes each byte as a number.

Then trace the emoji. One code-point number identifies it in this example, while four byte numbers represent it for storage or transmission.

Now change the first assignment, `text = "Cat"`, to `text = "A"`. Before you run it, predict the two lines:

```text
Code-point numbers: [65]
UTF-8 byte numbers: [65]
```

Run the same command and compare the result with your prediction. Then restore `Cat`.

Now turn to `text_preparation.py`.

Before we run the second file, write the exact prepared string you expect. Which characters, spaces, and lines will remain?

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

`strip` removes the surrounding whitespace. The next list keeps only the lines that still contain text. Finally, `join` rebuilds the two remaining lines with one `\n`.

Now replace `①` with `Cat`. Before you run the file again, predict the complete new prepared string. Then identify which cleanup steps produce the same result as before.

Run, compare, and explain the result. Then restore `①`.

You have now used the same reasoning pattern twice: predict the result, trace each operation, and check whether the explanation still works after one input changes.

## 13:30 What These Foundations Let Us Explain

We began with this question:

> **How can AI learn from written examples?**

Today we built three foundations for written input. The learning mechanism comes later.

Here is the idea to carry forward:

```text
character -> code-point number -> identity
text + UTF-8 -> byte sequence -> storage or transmission
source text + chosen cleanup steps -> prepared text
```

Before reading the results, answer three questions. What purpose does each `Cat` list serve? What do the two `🐱` lists tell us? What will the preparation steps change?

Now compare your answers with the evidence.

```text
Cat
code-point numbers -> [67, 97, 116]
UTF-8 bytes       -> [67, 97, 116]

🐱
code-point number -> [128049]
UTF-8 bytes       -> [240, 159, 144, 177]

NFKC
① -> 1
ﬀ -> ff
```

For `Cat`, one list identifies characters while the other represents UTF-8 bytes. For `🐱`, one code point identifies the character while four bytes represent it in UTF-8.

NFKC keeps `①` at length `1`, but changes `ﬀ` from length `1` to `2`. The other steps remove surrounding whitespace and the empty line, then rebuild two lines.

The pattern is now clear: character numbers identify, byte sequences store or send, individual cleanup steps make chosen changes, and text preparation applies those steps together.

These foundations give later lessons a traceable starting point. They do not yet explain meaning or learning.

Stable character numbers let software decide which characters belong in a collection. Video 2 will use that building block to ask how we can construct the collection dependably.
