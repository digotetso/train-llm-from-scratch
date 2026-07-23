# Video 1 — Before AI Can Learn: How Computers Represent and Prepare Text

*Script 4*

**Subtitle:** How character numbers, UTF-8 bytes, and simple cleanup prepare written text for later AI work

## 00:00 The Big Question and Today’s First Step

You may have seen an AI clarify an email, improve a sentence, or suggest a piece of code. The result can feel immediate: you enter words, and useful new words appear.

That familiar experience gives us the larger question for this course:

> **How can AI learn from written examples?**

We cannot answer that question by jumping straight from the text box to learning. First, we need to understand what software receives and what must happen to the written text.

Software needs to tell written characters apart. It needs a form that can be stored or sent. It may also need to apply the same chosen cleanup steps to every example.

So today we will answer one smaller question:

> **How do computers represent and prepare text before AI can learn from it?**

By the end, you will be able to explain:

1. how a fixed number can identify each example character;
2. how the same text becomes a sequence of small storage numbers;
3. how a short function applies fixed cleanup steps to an example string; and
4. why character numbers, storage numbers, and prepared text have different jobs.

We will check each job by hand, then test it with two Python files.

## 01:00 Where This Video Fits

These three jobs begin a longer route. Each supplies something a later step needs.

Text is split into reusable pieces. Each piece is called a **token**.

Each token receives a number. That number is called a **token ID**.

That token ID is linked to an **embedding**—a learned list of numbers used to represent useful features of the token during later processing.

An embedding is not a dictionary definition of the token.

These are names for later steps. We have not explained how they work yet, so we will leave them for later and focus on the three jobs in front of us.

Now compress the route:

```text
Written text
-> identify each example character with a number
-> represent the text as an ordered sequence of small storage units
-> apply fixed cleanup steps
-> prepared text
-> later text and AI-learning steps [closed]
```

## 03:00 Three Jobs Before Text Can Be Split into Pieces

### Job 1: Identify an example character

Software needs a dependable answer when it sees `C`, `a`, or `🐱`:

> Which written character is this?

A fixed character number identifies it without explaining what it means in a sentence.

### Job 2: Represent the text for storage or transmission

Character identity does not tell us how a file stores the text. Storage needs an ordered sequence of small units.

### Job 3: Apply explicit cleanup steps

Written text can arrive with extra spaces, empty lines, different line-ending marks, or special-looking character forms. We must choose which differences to keep and which to change.

The jobs connect in this order:

```text
character number -> identifies an example character
storage sequence -> stores or sends the text
fixed cleanup steps -> produce the chosen prepared text
```

These numbers are not interchangeable.

The character number becomes our first building block. Then we can ask how the same character is stored.

## 04:20 Identifying Characters with Code-Point Numbers

Look at `A`. You and I recognize it immediately, but software still needs a dependable way to tell it apart from `B`, `a`, or `🐱`.

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

The match can make the lists look equivalent. Let’s test that idea with `🐱`.

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

Our source string contains extra spaces and two consecutive line endings. Those marks are easy to miss when a terminal prints the string normally.

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

Now let’s predict, run both files, and compare the results.

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

Today we completed the earlier part of that route. Here is the compact summary:

```text
code-point number -> identifies an example character
UTF-8 byte sequence -> stores or sends the text
fixed cleanup step -> changes one chosen text feature
text preparation -> applies the chosen cleanup steps in order
```

Now test that summary on every example.

For `Cat`, predict the three code-point numbers and the three UTF-8 byte numbers. The lists happen to match:

```text
[67, 97, 116]
```

The matching values do not make the jobs identical. One list identifies the example characters. The other is the ordered storage sequence.

For `🐱`, predict whether you need one code-point number or several. Then predict whether its UTF-8 form needs one byte or several.

Our observed result was:

```text
code-point number -> [128049]
UTF-8 bytes -> [240, 159, 144, 177]
```

One number identifies the emoji in this example. Four bytes work together to store or send it.

Now move to the cleanup example.

Under NFKC, predict both changes:

```text
① -> ?
ﬀ -> ?
```

The rule gives:

```text
① -> 1
ﬀ -> ff
```

The first string keeps its length. The second changes from length `1` to length `2`.

Finally, imagine the same text arrives with mixed line endings. Predict what `prepare_text` does with those marks, the surrounding spaces, and the empty line.

`splitlines` separates the lines. The remaining steps remove surrounding whitespace, remove the empty line, and join the two kept lines with `\n`.

Notice what you can now distinguish. A character number identifies. A byte sequence stores or sends. A cleanup step changes one selected feature. Text preparation combines the chosen steps.

Those are four reusable building blocks, not four labels to memorize.

Stable character numbers let software decide which characters belong in a collection. Video 2 asks how to build that collection dependably.
