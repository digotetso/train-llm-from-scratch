# Video 1 — Before AI Can Learn: How Computers Represent and Prepare Text

**Subtitle:** How to inspect raw text, understand Unicode characters, and prepare consistent data before tokenization

---

## 00:00 From Written Text to Training Data

[On screen: A short text sample]

```text
  Lesson ①: Ａ cat ﬀ  
  second line  
```

You've probably seen AI rewrite an email, improve a sentence, summarize a document, or write a piece of code.

You type some text, and the AI produces new text. The type of AI behind this is called a **large language model**, or **LLM**. An LLM is a computer system that learns patterns in language and uses those patterns to predict and generate appropriate text.

To learn how to do this, the model is trained on a vast collection of text, such as books, articles, websites, and other written material.


Suppose we have this piece of text and want to use it to train a large language model.

How do we go from written text like this to an AI model that can complete sentences, answer questions, or generate code?

We cannot simply place the text inside the model and ask it to learn.

A large language model is a mathematical system. The neural network operates on numerical values, not directly on a Python string or a written sentence.

Eventually, a tokenizer will divide the text into pieces called **tokens** and convert those tokens into numbers called **token IDs**. The model will then use those IDs to retrieve numerical vectors that it can process.

But we should not rush to tokenization.

First, we need to inspect the text itself.

Look closely at our example.

It contains extra spaces, an empty line, a circled digit, a wide version of the letter `A`, and a joined symbol that looks like two lowercase f’s.

Before converting text into token IDs, we need to ask:

> **What problems might be hiding in our source text, and which of them should we fix?**

That is the focus of this lesson.

We will learn how software identifies characters, why similar-looking text can still be different, and how to prepare source text consistently before tokenization.

---

## 01:30 Where This Lesson Fits

Let’s place today’s lesson inside the larger LLM training process.

A simplified version looks like this:

```text
Raw source text
        ↓
Inspect and prepare the text
        ↓
Tokenize the text
        ↓
Convert tokens into token IDs
        ↓
Create training examples
        ↓
Train the language model
```

Today, we are concentrating on the first part:

```text
Raw source text
        ↓
Inspect and prepare the text
```

We will not create tokens in this lesson.

We will not build a vocabulary.

We will not yet create the numerical input that is passed into the model.

Instead, we will make sure that we understand the text we are about to give to the tokenizer.

That preparation matters because inconsistent source text can create unnecessary variation in the data.

---

## 02:30 Why Raw Text Can Be Messy

Large language models are often trained using enormous collections of text.

That text may come from:

- websites;
- books;
- news articles;
- academic papers;
- forums;
- documentation;
- conversations;
- and code repositories.

When text comes from many different sources, it is rarely perfectly consistent.

One document may contain spaces at the beginning of every line.

Another may contain several empty lines between paragraphs.

One source may use tabs, while another uses ordinary spaces.

Different systems may use different line-ending characters.

Copied web pages may include navigation menus, repeated headings, advertisements, or other unwanted material.

The same visible idea may also be written using different Unicode characters.

For example:

```text
①    1

Ａ    A

ﬀ    ff
```

To a human reader, the forms in each pair may appear to serve the same purpose.

The circled `①` and the ordinary `1` both represent the number one.

The wide `Ａ` and the ordinary `A` both look like an uppercase A.

The symbol `ﬀ` looks like two lowercase f’s joined together.

But a computer does not identify characters only by how they look.

As far as the computer is concerned, these examples contain different Unicode code-point sequences.

Before we change anything, we need a way to inspect those differences.

---

## 03:55 Inspect Before You Clean

Consider this Python string:

```python
source = "  Lesson ①: Ａ cat ﬀ  \r\n\r\n\tsecond line  "
```

If we print the string normally, some of its details may be difficult to see.

```python
print(source)
```

The spaces, tab, empty line, and line-ending characters are present, but the normal output does not make all of them obvious.

Python provides a function called `repr` that gives us a more revealing representation of the string.

```python
print(repr(source))
```

The output is:

```text
'  Lesson ①: Ａ cat ﬀ  \r\n\r\n\tsecond line  '
```

Now we can see several hidden details:

```text
Two spaces before Lesson
Two spaces after ﬀ
\r\n\r\n between the lines
\t before second line
Two spaces at the end
```

The sequence `\t` represents a tab.

The sequence `\r\n` represents one type of line ending.

Because two line endings appear one after the other, they create an empty line.

`repr` makes escaped control characters such as tabs and line endings visible. It also shows us the beginning and end of the string by placing quotation marks around it.

Ordinary spaces still appear as blank spaces.

When we want to make those spaces completely obvious, we can temporarily replace them with a visible marker:

```python
print(source.replace(" ", "·"))
```

The output begins like this:

```text
··Lesson·①:·Ａ·cat·ﬀ··
```

We are not changing the dataset yet.

We are only inspecting it.

That distinction matters.

Before applying cleanup rules, we should understand exactly what the source contains.

---

## 05:30 Similar-Looking Text Can Still Be Different

Let’s focus on these two forms:

```text
①    1
```

Most people immediately understand that both can represent the number one.

But computers do not automatically assume that characters with similar meanings should be treated as the same character.

To understand why, we need to learn how software identifies written characters.

Computers use an international standard called **Unicode**.

Unicode provides code points for encoded characters used in writing systems around the world.

It includes letters, digits, punctuation marks, mathematical symbols, emoji, and many other symbols.

A **code point** is the numerical identifier used for an encoded Unicode character.

You can think of it as an identification number.

It answers this question:

> **Which encoded character is this?**

A code point does not explain what the character means in a sentence.

For example, the ordinary digit `1` and the circled digit `①` have different code points.

That means they are different Unicode characters, even when people use them to communicate a closely related idea.

---

## 06:55 Inspecting Code Points with Python

Python has a built-in function named `ord`.

The `ord` function returns the Unicode code point of a one-character string as an integer.

Let’s inspect the circled digit and the ordinary digit.

```python
print(ord("①"))
print(ord("1"))
```

Python prints:

```text
9312
49
```

The two numbers are different.

```text
① → 9312
1 → 49
```

Unicode code points are usually written in hexadecimal using the prefix `U+`.

We can display that notation in Python like this:

```python
print(f"U+{ord('①'):04X}")
print(f"U+{ord('1'):04X}")
```

The result is:

```text
U+2460
U+0031
```

So we can describe the two characters more completely:

```text
① → decimal 9312 → U+2460
1 → decimal 49   → U+0031
```

The code points confirm that the two forms are different Unicode characters.

---

## 08:10 More Similar-Looking Examples

Now compare the wide uppercase A with the ordinary uppercase A.

```python
print(ord("Ａ"))
print(ord("A"))
```

The result is:

```text
65313
65
```

In standard Unicode notation:

```text
Ａ → U+FF21
A → U+0041
```

Again, the characters look closely related, but their code points are different.

Now consider the joined `ﬀ` symbol.

```python
print(ord("ﬀ"))
```

Python reports:

```text
64256
```

In Unicode notation:

```text
ﬀ → U+FB00
```

The symbol `ﬀ` is represented by one Unicode code point in this Python string.

The ordinary text `ff` contains two code points:

```python
print([ord(character) for character in "ff"])
```

Python prints:

```text
[102, 102]
```

In Unicode notation:

```text
ﬀ  → [U+FB00]

ff → [U+0066, U+0066]
```

A human reader may interpret the two forms similarly.

But the computer receives different code-point sequences.

---

## 09:35 A Note About Characters and Code Points

In simple examples, one visible character is often represented by one Unicode code point.

But that is not always true.

A visible symbol can sometimes be created from multiple code points working together.

For example, an accented letter may be represented as one precomposed code point or as a base letter followed by a combining mark.

Emoji can also contain several code points that appear to the user as one visible symbol.

For this reason, we should be careful with the word **character**.

In this lesson, we are inspecting Unicode code points inside Python strings.

Python’s `len()` function counts the number of code points in a string, not necessarily the number of visible symbols that a person perceives.

We will return to more complex Unicode examples later.

For now, our examples are enough to reveal an important fact:

> Text that looks similar to a person can still contain different Unicode code-point sequences.

---

## 10:35 Why These Differences Matter

You may be wondering:

> If people can understand both forms, why should we change them?

The answer depends on the purpose of the dataset.

Suppose one source writes:

```text
Lesson ①
```

while another writes:

```text
Lesson 1
```

If we leave them unchanged, the tokenizer receives two different code-point sequences.

Because the input sequences are different, the tokenizer may divide them differently or assign different token IDs.

This introduces variation into the training data, even when the writers intended to express the same idea.

The same problem can happen with:

```text
ＡI
```

and:

```text
AI
```

or with text containing the single ligature code point `ﬀ` instead of two ordinary `f` code points.

Making selected forms consistent can reduce unnecessary variation before tokenization.

But that does not mean every difference should always be removed.

Some distinctions may carry important information.

Exact forms may matter in:

- source code;
- mathematical notation;
- passwords;
- poetry;
- historical documents;
- names;
- or specialised writing systems.

Text preparation is therefore not about making every source identical.

It is about deciding which differences matter for the task and applying those decisions consistently.

For this lesson, we will choose to replace these compatibility forms with ordinary forms:

```text
① → 1

Ａ → A

ﬀ → ff
```

To apply these changes consistently, we can use Unicode normalization.

---

## 12:15 What Is Unicode Normalization?

Unicode normalization converts selected Unicode sequences into a standardized form.

Python supports several Unicode normalization forms.

For this example, we will use **NFKC**.

NFKC means **Unicode Normalization Form KC**.

The letter `K` indicates compatibility.

Technically, NFKC applies compatibility decomposition and then canonical composition.

You do not need to memorise those technical steps yet.

For this lesson, the important idea is that NFKC maps selected compatibility forms to more ordinary representations.

In our examples:

```text
① → 1

Ａ → A

ﬀ → ff
```

Python provides Unicode tools through its standard `unicodedata` module.

Here is how we apply NFKC normalization:

```python
import unicodedata

result = unicodedata.normalize("NFKC", "①")

print(result)
```

The output is:

```text
1
```

Now try all three examples:

```python
import unicodedata

print(unicodedata.normalize("NFKC", "①"))
print(unicodedata.normalize("NFKC", "Ａ"))
print(unicodedata.normalize("NFKC", "ﬀ"))
```

Python prints:

```text
1
A
ff
```

---

## 13:50 Normalization Can Change the Length

Normalization may change the number of code points in a Python string.

The circled digit begins as one code point and becomes one code point:

```text
①
Python length: 1

↓

1
Python length: 1
```

The ligature begins as one code point and becomes two:

```text
ﬀ
Python length: 1

↓

ff
Python length: 2
```

We can verify this in Python:

```python
import unicodedata

before = "ﬀ"
after = unicodedata.normalize("NFKC", before)

print("Before:", repr(before))
print("Before length:", len(before))

print("After:", repr(after))
print("After length:", len(after))
```

The result is:

```text
Before: 'ﬀ'
Before length: 1
After: 'ff'
After length: 2
```

This shows that normalization can change more than appearance.

It can change the code-point sequence and the Python string length.

---

## 14:55 Normalization Is a Choice

NFKC is useful when compatibility forms should be treated consistently.

But it is not a universal cleanup rule for every dataset.

NFKC can remove distinctions that may matter for some tasks.

For example, a project working with mathematical notation, historical typography, or specialised source text may need to preserve forms that another project would normalize.

We should therefore not say:

> NFKC makes text correct.

A more accurate statement is:

> **NFKC applies a particular set of Unicode compatibility rules.**

Whether those rules are appropriate depends on the dataset and the goal of the project.

For our example, we have deliberately chosen these preparation rules:

```text
Convert selected compatibility forms using NFKC.
Remove surrounding whitespace from each line.
Remove empty lines.
Use one consistent line separator.
```

Together, these choices define our preparation process.

Another project may choose different rules.

---

## 15:55 Dataset Preparation and Tokenizer Normalization

There is one more distinction to understand.

In this course, we are applying some preparation rules before tokenization.

```text
Raw source text
        ↓
Dataset-level preparation
        ↓
Tokenizer
```

This is useful for tasks such as:

- removing unwanted documents;
- cleaning repeated website material;
- handling selected formatting;
- and applying dataset-wide consistency rules.

However, some tokenizer pipelines also include their own normalization stage.

A tokenizer may perform operations such as Unicode normalization, lowercasing, or handling accents before it divides the text into tokens.

So normalization can happen at different levels.

```text
Dataset-level preparation
→ prepares the larger collection of source text

Tokenizer normalization
→ applies the exact rules expected by that tokenizer
```

The important rule is consistency.

The same tokenizer rules used when preparing training data must also be used when the trained model later receives new text.

For today’s example, we will apply NFKC during our dataset-preparation step so that we can see exactly what it changes.

---

## 17:05 Building the Complete Preparation Function

Let’s return to our original source string:

```python
source = "  Lesson ①: Ａ cat ﬀ  \r\n\r\n\tsecond line  "
```

We want the prepared result to be:

```text
Lesson 1: A cat ff
second line
```

Create a file named:

```text
text_preparation.py
```

Add the following code:

```python
import unicodedata


def prepare_text(text):
    normalized_text = unicodedata.normalize("NFKC", text)

    lines = normalized_text.splitlines()

    stripped_lines = [
        line.strip()
        for line in lines
    ]

    non_empty_lines = [
        line
        for line in stripped_lines
        if line
    ]

    prepared_text = "\n".join(non_empty_lines)

    return prepared_text


source = "  Lesson ①: Ａ cat ﬀ  \r\n\r\n\tsecond line  "

print("Source text:")
print(repr(source))

print()

print("Prepared text:")
print(repr(prepare_text(source)))
```

Let’s trace the function one step at a time.

---

## 18:15 Step One: Normalize the Unicode Text

The first line inside the function is:

```python
normalized_text = unicodedata.normalize("NFKC", text)
```

This applies the NFKC rules we selected.

The important changes are:

```text
① → 1

Ａ → A

ﬀ → ff
```

After normalization, the underlying string is:

```python
"  Lesson 1: A cat ff  \r\n\r\n\tsecond line  "
```

The surrounding spaces, tab, line endings, and empty line still remain.

Unicode normalization only addresses the selected Unicode differences.

It does not perform every preparation step for us.

---

## 19:05 Step Two: Separate the Lines

The next line is:

```python
lines = normalized_text.splitlines()
```

The `splitlines` method separates the string at the line boundaries Python recognises.

Our source contains two consecutive `\r\n` line endings.

That gives us three strings:

```text
Line 1: "  Lesson 1: A cat ff  "
Line 2: ""
Line 3: "\tsecond line  "
```

The second string is empty.

It represents the blank line in the source text.

---

## 19:55 Step Three: Remove Surrounding Whitespace

Next, we use:

```python
stripped_lines = [
    line.strip()
    for line in lines
]
```

The `strip` method removes whitespace from the beginning and end of each line.

The results are:

```text
Line 1: "Lesson 1: A cat ff"
Line 2: ""
Line 3: "second line"
```

The spaces around the first line are removed.

The tab before `second line` is removed.

The spaces after `second line` are also removed.

Notice that we are removing only surrounding whitespace.

We are not removing every space inside the sentence.

That is deliberate.

Internal spaces may carry meaning, and some types of text—such as code or poetry—may depend on exact spacing.

---

## 20:50 Step Four: Remove Empty Lines

The next part is:

```python
non_empty_lines = [
    line
    for line in stripped_lines
    if line
]
```

This keeps only strings that still contain text.

Before this step, we have:

```text
"Lesson 1: A cat ff"
""
"second line"
```

After it, we have:

```text
"Lesson 1: A cat ff"
"second line"
```

The empty line has been removed.

Again, this is a project-specific choice.

Paragraph breaks may be important in a real dataset.

For this teaching example, we have decided that the empty line is unnecessary.

---

## 21:40 Step Five: Rebuild the Text

The final preparation step is:

```python
prepared_text = "\n".join(non_empty_lines)
```

The `join` method combines the remaining lines.

It places one newline character, written as `\n`, between them.

The final result is:

```text
Lesson 1: A cat ff
second line
```

The complete process is:

```text
Raw source text
        ↓
Apply NFKC normalization
        ↓
Split the text into lines
        ↓
Remove surrounding whitespace
        ↓
Remove empty lines
        ↓
Join the remaining lines with \n
        ↓
Prepared text
```

Each step addresses one selected issue.

Together, the steps turn inconsistent source text into the form we have chosen for this dataset.

---

## 22:45 Inspecting Code Points in Python

Now create a second file named:

```text
inspect_characters.py
```

Add this code:

```python
examples = [
    ("①", "1"),
    ("Ａ", "A"),
    ("ﬀ", "ff"),
]


def code_points(text):
    return [
        f"U+{ord(character):04X}"
        for character in text
    ]


for first_form, second_form in examples:
    print("First form:", repr(first_form))
    print("Python length:", len(first_form))
    print("Decimal code points:", [
        ord(character)
        for character in first_form
    ])
    print("Unicode notation:", code_points(first_form))

    print()

    print("Second form:", repr(second_form))
    print("Python length:", len(second_form))
    print("Decimal code points:", [
        ord(character)
        for character in second_form
    ])
    print("Unicode notation:", code_points(second_form))

    print("\n" + "-" * 30 + "\n")
```

Before running the file, make a prediction.

Will `①` and `1` have the same code point?

Will `Ａ` and `A` have the same code point?

Will `ﬀ` and `ff` have the same Python string length?

Run:

```bash
python inspect_characters.py
```

The important results are:

```text
① → [9312]   → [U+2460]
1 → [49]     → [U+0031]

Ａ → [65313] → [U+FF21]
A → [65]     → [U+0041]

ﬀ → [64256]   → [U+FB00]
ff → [102, 102] → [U+0066, U+0066]
```

The output confirms our explanation.

These forms may look similar or communicate similar ideas to a human reader.

But they do not contain the same Unicode code-point sequences.

---

## 24:30 Predict, Run, and Explain

Return to:

```text
text_preparation.py
```

Before running the file, predict the exact prepared result.

Ask yourself:

- What will happen to `①`?
- What will happen to `Ａ`?
- What will happen to `ﬀ`?
- What will happen to the surrounding spaces?
- What will happen to the tab?
- What will happen to the empty line?
- Which line separator will remain?

Now run:

```bash
python text_preparation.py
```

The output is:

```text
Source text:
'  Lesson ①: Ａ cat ﬀ  \r\n\r\n\tsecond line  '

Prepared text:
'Lesson 1: A cat ff\nsecond line'
```

Trace every change:

```text
① became 1
Ａ became A
ﬀ became ff
surrounding whitespace was removed
the tab before second line was removed
the empty line was removed
the remaining lines were joined with \n
```

The important skill is not simply running the program.

The important skill is being able to explain why every part of the output changed.

---

## 25:45 Test the Rules with a New Example

Now change the source string to:

```python
source = "  Chapter ②: Ｂig oﬀice  \n\n  final line  "
```

Before running the program, predict the result.

NFKC will make these changes:

```text
② → 2

Ｂ → B

ﬀ → ff
```

The surrounding whitespace and empty line will also be removed.

The expected prepared text is:

```text
Chapter 2: Big office
final line
```

Run the program and compare the result with your prediction.

Then ask:

> **Does the same explanation still work when the input changes?**

If it does, you understand the process rather than merely remembering one output.

---

## 26:45 What We Have Learned

We began with source text that we wanted to use for LLM training.

Our larger goal is eventually to convert the text into numerical input that a model can process.

But before doing that, we inspected the text and found several inconsistencies.

We learned that:

```text
① and 1 are different Unicode characters.

Ａ and A are different Unicode characters.

ﬀ and ff are different Unicode code-point sequences.
```

Unicode code points help software identify encoded characters.

Python’s `ord` function allows us to inspect those code points.

The code points helped us understand why similar-looking forms can still be different to a computer.

We then selected preparation rules for our example.

We used NFKC normalization to convert selected compatibility forms into ordinary forms.

We also removed surrounding whitespace, removed an empty line, and rebuilt the text using one consistent line separator.

The result was prepared text that can be passed to the next stage.

---

## 27:50 Code Points Are Not Token IDs

There is one final distinction we need to make.

Today, we examined numbers such as:

```text
① → 9312 → U+2460

1 → 49 → U+0031

Ａ → 65313 → U+FF21

A → 65 → U+0041
```

These are Unicode code points.

They identify encoded characters.

They are not automatically the numerical inputs that we give to an LLM.

Most language models use a tokenizer.

The tokenizer takes prepared text, divides it into tokens, and assigns each token an ID from its vocabulary.

Those numbers are called **token IDs**.

```text
Unicode code point
→ identifies an encoded Unicode character

Token ID
→ identifies a token in a particular tokenizer vocabulary
```

Different tokenizers can divide the same text differently.

They can therefore produce different token sequences and different token IDs.

After tokenization, the model uses those token IDs to retrieve numerical embedding vectors.

Those vectors are what the neural network processes mathematically.

The larger path is:

```text
Raw source text
        ↓
Inspect the text
        ↓
Apply chosen preparation rules
        ↓
Prepared text
        ↓
Tokenize the text
        ↓
Token IDs
        ↓
Embedding vectors
        ↓
Neural-network calculations
        ↓
Learning
```

Today, we completed the first part of that journey.

We did not train the model.

We did not build a vocabulary.

We did not create token IDs.

We prepared the source text so that the later stages can process it consistently.

In the next lesson, we will begin answering the next question:

> **How can a tokenizer divide text into reusable pieces and assign each piece an ID?**