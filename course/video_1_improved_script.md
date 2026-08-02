# Video 1: What Does It Mean for a Computer to Learn From Text?

## 00:00 Hook

[On screen: `cat`]

When you read `cat`, you probably picture an animal, remember a pet, or think of a sound. The word has meaning because of your experience.

AI can work with text too. It can rewrite an essay, improve an email, or generate code. But underneath the text box, a model performs calculations with numbers.

[On screen: `cat` → `67 97 116`]

So how does text become numbers a model can use? And why is that conversion **not yet learning**?

By the end, you'll be able to explain the difference using three letters, three numbers, and a tiny Python file.

First, we need a smaller idea: a number can identify something without containing its meaning.

## 00:45 Analogy

Imagine a library where every book has a label.  The number helps the librarian locate the correct book, but it does not contain the story. It is an **identifier**: it tells us which book we mean, not what the book means.

Text systems use numbers in a similar way. Shared numeric identifiers let software distinguish one written character from another.


## 02:00 Technical Meaning

Take the word `Cat`. In this example, Python program can visit the string one character at a time: `C`, then `a`, then `t`.

Software needs a shared way to distinguish those characters. **Unicode** provides that shared standard. It assigns each character an number called a **code point**.

Python's `ord` function reports the ***code point*** for a one-character string, for example:

```python
ord("C")  # 67
ord("a")  # 97
ord("t")  # 116
```

If we run `ord("C")` again tomorrow, the result will still be `67`. Python is applying a fixed mapping. It is not practicing, measuring an error, or improving.

And `67` does not contain the meaning of `C`. It identifies the encoded character. The meaning of that character still depends on context.

There is another layer when text is stored or transmitted: **bytes**. A byte contains eight bits and can represent an unsigned value from `0` through `255`. **UTF-8** is a widely used encoding that represents each Unicode code point with one or more bytes.

For the English letters in `Cat`, the code-point values and UTF-8 byte values happen to match:

```text
C → 67
a → 97
t → 116
```

That works because these letters are in the ASCII range, which UTF-8 stores as one byte with the same numeric value. It is not a universal rule. Other characters can require several UTF-8 bytes; Video 4 will build that mechanism carefully.

We can now explain how text receives a numeric form. But numeric representation alone is not learning.

A **model** is a mathematical prediction system with adjustable numbers called **parameters**. During training, the model makes predictions, we measure the prediction error, and an update process changes those parameters. Those parameter changes are what we mean by **learning** in this course.

[On screen: two-column contrast]

```text
REPRESENTATION                         LEARNING
Changes the form of the input          Changes the model's parameters
Uses fixed standards and rules         Uses examples and measured error
Does not improve through repetition    Can improve later predictions
```

Keep this sentence as our first building block:

> Representation changes the form of the data. Learning changes the model's adjustable parameters using examples and measured error.

## 04:00 Tiny Example

Let's apply that distinction.

First, the representation side. Predict the code points for `Cat`, then compare your answer with this trace:

```text
Human-readable text:   C    a    t
Unicode code points:   67   97   116
```

Those numbers let software store, compare, and process the characters consistently. But the arithmetic distance between `67` and `97` does not measure the difference in meaning between `C` and `a`. These values are identifiers under an agreed system, not semantic coordinates.

Now move to the learning side. Imagine a model is being trained to predict what text is likely to come next, and its examples include:

```text
cat sat
cat ran
cat slept
```

The examples do not explicitly explain grammar or define the word `cat`. They simply provide repeated relationships: certain text tends to appear after other text.

Suppose the model makes ten predictions on a set of examples and gets seven wrong. Training measures that error and adjusts the model's parameters. On comparable new examples, it later gets five wrong.

That change gives us a small intuition for learning: the predictions improved **after measured error changed the adjustable parameters**.

Real training uses a numeric error measure rather than a simple mistake count. We also evaluate the model on examples it did not train on, because doing well only on the training examples could be memorization.

For now, remember the causal chain:

```text
examples → predictions → measured error → parameter updates → new predictions
```

Encoding text does not perform any of those parameter updates. It prepares the input so the model can participate in that chain.

## 06:00 Repository Walkthrough

Now let's find the representation side in this project.

This repository does not pass untouched source text directly into training. It first normalizes the text and stores the normalized result. The relevant code is in `matgpt/data/normalize.py` and `matgpt/data/prepare.py`.

Start with this simplified excerpt from `normalize.py`:

```python
def normalize_text(text: str) -> str:
    # Apply Unicode canonical and compatibility normalization.
    text = unicodedata.normalize("NFKC", str(text))

    # Use one newline style even if the source used another style.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove trailing whitespace from each line.
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines).strip()
    return text
```

Follow the value from top to bottom.

The annotations `text: str` and `-> str` communicate the intended input and output types. They do not, by themselves, force Python to enforce those types at runtime. The call `str(text)` asks Python for a string form of the input.

Next, `unicodedata.normalize("NFKC", ...)` applies the repository's chosen Unicode normalization policy. The two `replace` calls convert different newline styles to `\n`. The list comprehension removes trailing whitespace from each line. Finally, `strip()` removes whitespace from the outer edges, and the function returns the normalized string.

[On screen: `①` → `1`]

One important warning: **NFKC normalization is a policy choice, not a lossless copy operation.** For example, it changes the circled character `①` into the plain character `1`. That can be useful when those forms should be treated alike, but it also removes a distinction from the source. Normalization can even change the string length, so the original text cannot always be reconstructed exactly. Video 5 will examine that tradeoff.

The full repository function also removes selected non-printing control characters and limits runs of blank lines. This excerpt shows only the operations needed for today's trace.

Now follow the normalized value into this simplified excerpt from `prepare.py`:

```python
# First preparation operation: normalize the source text.
normalized = normalize_text(text)

return {
    # Other record fields are omitted from this excerpt.
    # Preserve the normalized text for later processing.
    "text": normalized,

    # Record the normalized string length reported by Python.
    "num_chars": len(normalized),
}
```

The call to `normalize_text(text)` returns a normalized string. The record stores that string and the length reported by Python, along with other metadata omitted here.

That length is not always the number of symbols a person sees on screen. One visible symbol can be built from multiple code points, so visual appearance and Python string length do not always match.

Now ask the key question: what changed?

The **data** changed. Its Unicode form, newline style, and whitespace became more consistent. The record also stored the resulting text and length.

What did not change?

No model parameter was updated. This is data preparation, not learning.

## 09:00 Live Mini-Lab

Let's test the same distinction ourselves. Open:

```text
course/videos/001-computer-learning-from-text/lab.py
```

Use this version of the lab:

```python
text = "Cat"

code_points = [ord(character) for character in text]
utf8_bytes = list(text.encode("utf-8"))

print("Human text:", text)
print("Unicode code points:", code_points)
print("UTF-8 bytes:", utf8_bytes)
print("Did this conversion update model parameters? No")
print("Representation prepares data; training performs learning.")
```

Before running it, predict the two numeric lists. We've already traced the characters, so both should be:

```text
[67, 97, 116]
```

From the repository root, run:

```bash
python course/videos/001-computer-learning-from-text/lab.py
```

You should see:

```text
Human text: Cat
Unicode code points: [67, 97, 116]
UTF-8 bytes: [67, 97, 116]
Did this conversion update model parameters? No
Representation prepares data; training performs learning.
```

Now explain each line.

`Human text` displays the form that is convenient for us to read. The list comprehension visits one character at a time, and `ord(character)` reports its Unicode code point. `text.encode("utf-8")` produces UTF-8 bytes, while `list(...)` displays those byte values as ordinary integers.

For `Cat`, the two lists match because all three letters are in the ASCII range. The result confirms our prediction for this example. It does not prove that Unicode code points and UTF-8 bytes always match.

Most importantly, the script inspects and converts data. It does not make predictions, calculate an error, or update model parameters. Nothing in this file trains a model.

Now change only the input:

```python
text = "A"
```

Predict the result before rerunning the file. Both numeric lists should contain `65`.

When the output confirms your prediction, ask what caused it. It wasn't practice or improvement. Python followed the same fixed standards as before.

Finally, return the line to:

```python
text = "Cat"
```

That keeps the lab aligned with the documented output.

## 12:00 Common Mistakes

Two mistakes are especially common here.

The first is saying, “`65` is the meaning of `A`.”

It isn't. `65` identifies the encoded character `A` under Unicode. Depending on context, `A` could be a school grade, a musical note, a blood type, an article, or one character inside a word. Its meaning changes with context while its code point remains stable.

Use this diagnostic question: if another character system assigned a different number to `A`, would people have to change what `A` means?

No. The number is a representation, not the meaning.

The second mistake is saying that conversion is learning.

`ord` applies a fixed mapping. Running it repeatedly does not make it more accurate. Learning requires something adjustable: training measures prediction error and changes model parameters in response.

Representation is necessary for learning, but it is not itself learning.

## 13:00 Recap and Exercise

Let's rebuild the answer in plain language.

When you read `cat`, you bring meaning from your experience. Software first works with a representation of the text. Unicode assigns code points to encoded characters, and UTF-8 represents those code points as bytes. Those fixed mappings make text usable as data, but applying them does not teach a model anything.

A model learns only when training uses examples and measured error to change its adjustable parameters, allowing later predictions to improve.

[On screen]

> Representation changes the data. Learning changes the model.

Check your understanding:

- What does `ord("A")` return, and why is the answer stable?
- Why can `65` identify `A` without containing every meaning of `A`?
- What must change before we can say that learning occurred?
- If the input changes from `Cat` to `A`, which outputs change, and which rule stays fixed?

For the exercise, run the mini-lab with `A`, record the output, and complete this sentence:

> The number `65` is assigned to ______, but it does not encode ______.

Then return the input to `Cat`.

The representation–learning distinction is now one of our building blocks. Text representation gives a model numbers it can ultimately work with. Learning changes the model's adjustable numbers—its parameters—so later predictions can improve.

In the next lesson, we will focus on the representation side and ask a more precise question: how does a computer assign stable numbers to written characters?

### Vocabulary Deferred to Later Videos

The terms **token**, **tensor**, **logit**, **gradient**, and **attention** are intentionally not used as explanations in Video 1. Each term will be introduced from plain language in its approved later lesson.
