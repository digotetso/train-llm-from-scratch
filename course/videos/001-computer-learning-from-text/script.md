# Video 1: What Does It Mean for a Computer to Learn From Text?

## 00:00 Hook

Put the word `cat` on screen.

When you read this word, you may picture an animal. You may remember a pet, a sound, or a moment from your life.

The computer does not receive those thoughts, feelings, or memories. It receives only the text we give it, stored according to agreed rules.

That difference is the starting point for everything we will learn in this course.

By the end of this lesson, you will be able to explain why text needs a numeric form before a mathematical model can learn from it. We will start with only three letters, three numbers, and a tiny Python program you can run yourself.

## 00:45 Analogy

**Teaching analogy:** Imagine a library that gives every book an identifier.

That identifier helps the library store the book, find it, and tell it apart from every other book. But the identifier does not contain the book's story. It does not contain the reader's feelings about the story either.

Character numbers work in a similar way. They help software identify and handle written characters, but the numbers do not contain the human meaning of those characters.

The analogy has a limit. A library identifier often refers to a whole book. Text systems work with characters and other smaller pieces, and an identifier alone does not explain how a model learns. For now, keep only the central idea: an agreed number can identify something without containing its meaning.

So, what agreed number does a computer use for a character such as `A`? Let us look.

## 02:00 Technical Meaning

We will introduce the technical words one at a time.

A **character** is one written item, such as `C`, `a`, `t`, a space, or a question mark.

**Unicode** is a shared standard for representing written characters. It assigns each encoded character an integer called a **code point**. Python's `ord` function lets us inspect that number:

```python
ord("C")  # 67
ord("a")  # 97
ord("t")  # 116
```

These numbers identify the characters. They do not tell the computer that `Cat` names an animal.

The same point becomes clearer with uppercase `A`. Its code point is always `65`, whether `A` is a school grade, a musical note, a blood type, or one letter inside a word. The number stays the same while the meaning changes with context.

There is one more representation we need to name. A **bit** is a `0` or a `1`. A **byte** contains eight bits and can represent one of 256 values, from 0 through 255. **UTF-8** is a widely used rule for representing Unicode text as one or more bytes.

For the simple English letters in `Cat`, the Unicode code points and UTF-8 byte values happen to match. These letters belong to an older set of common characters called ASCII, which UTF-8 represents with one byte each. This is not true for every character. Video 4 will show examples that need more than one UTF-8 byte.

Now we can define a **model** in plain language. A model is a mathematical prediction system. Inside it are adjustable numbers called **parameters**.

The model receives numbers and produces a prediction, such as what written item may come next. During training, we compare that prediction with the expected answer and measure the error. **Learning** happens when training adjusts the parameters so the model's predictions become less wrong across many examples.

This gives us an important distinction:

- Text representation uses fixed agreements to turn text into numbers.
- Learning changes the model's adjustable numbers using examples and measured errors.

Representation gives the model something numerical to work with. Learning is what changes the model.

## 04:00 Tiny Example

Suppose we show a model these three examples:

```text
cat sat
cat ran
cat slept
```

In every example, a space follows `cat`, and an action word comes after the space. We do not give the model a dictionary definition of `cat`, and we do not label one word as an animal and another as an action. We give it represented examples.

Now shrink the example even further and look only at `Cat`:

```text
Human-readable text: C    a    t
Agreed numbers:      67   97   116
```

These numbers let a program store the characters, count them, and compare one sequence with another. But the distance between `67` and `97` does not tell us anything meaningful about the relationship between `C` and `a`. Numeric processing is not the same as understanding the word.

Next, imagine that a model makes ten predictions and gets seven wrong. Training adjusts its parameters. On ten comparable examples later, it gets five wrong.

```text
Before training: 7 mistakes out of 10
After training:  5 mistakes out of 10
Change:          2 fewer mistakes
```

This is only a simple picture of improvement. The real repository measures error with a more precise calculation that we will learn later.

For now, remember the sequence: the model processes examples, makes predictions, measures errors, and updates its parameters. Repeated relationships in those examples can help later predictions. We call a repeatable relationship a **pattern**.

The fixed character numbers did not learn anything. The model's adjustable parameters changed.

## 06:00 Repository Walkthrough

Now let us connect that idea to the repository.

**Source fact:** The repository does not send remote, unprocessed text directly into training. It first makes the text more consistent and stores the prepared result. The relevant code lives in `matgpt/data/normalize.py` and `matgpt/data/prepare.py`.

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

Let us read it from top to bottom.

`def normalize_text` creates a function named `normalize_text`. The notation `text: str` says we expect text as input, and `-> str` says we expect text back. These are type hints for readers and tools; they do not force the type by themselves at runtime.

`str(text)` converts the input into a Python string. Then `unicodedata.normalize("NFKC", ...)` applies a Unicode consistency rule named NFKC. The next line turns different newline styles into one consistent style. The bracketed expression processes one line at a time and removes whitespace from each line's right edge. This compact Python form is called a list comprehension. Finally, `strip()` removes whitespace around the whole result, and `return text` gives that result back.

Here is an important warning. NFKC is a **deliberate cleaning policy**. It is **not lossless**. For example, it changes the circled character `①` into plain `1`. That may be useful when we want those forms treated alike, but the original distinction is lost. Normalization can also **change character count**, so we cannot always rebuild the exact source text from the normalized result. Video 5 will explain this choice and its tradeoffs carefully.

The full function also removes certain non-printing control characters and reduces long runs of blank lines. We left those operations out of this excerpt so we can focus on today's idea.

Now look at the point where `prepare.py` uses the function:

```python
# First preparation operation: normalize the source text.
normalized = normalize_text(text)

return {
    # Other record fields are omitted from this excerpt.
    "text": normalized,
    "num_chars": len(normalized),
}
```

**Observed code behavior:** `normalize_text(text)` receives source text and returns normalized text. The record stores that text and the length Python reports for the string. That length does not always match the number of visible symbols a person sees, because one visible symbol can involve more than one code point.

Most importantly, this code is preparing data. It is not updating model parameters, so it is not the learning step.

We have now seen the repository code. Next, let us make the text-to-number idea visible with a tiny lab.

## 09:00 Live Mini-Lab

Open `course/videos/001-computer-learning-from-text/lab.py`.

```python
text = "Cat"

print("Human text:", text)
print("Character numbers:", [ord(character) for character in text])
print("UTF-8 bytes:", list(text.encode("utf-8")))
print("Can the mathematical model use this raw Python string as numeric input? No")
print("Learning begins after text is represented as numbers.")
```

Before you run it, predict the two lists. For `Cat`, both should be `[67, 97, 116]`.

From the repository root, run:

```bash
python course/videos/001-computer-learning-from-text/lab.py
```

Read the output one line at a time.

`Human text` shows the form that is useful to us as readers. The list comprehension visits each character, and `ord(character)` returns its Unicode code point. `text.encode("utf-8")` creates the UTF-8 bytes. Wrapping the result in `list(...)` displays those bytes as ordinary integers.

The sentence `Can the mathematical model use this raw Python string as numeric input? No` is deliberately specific. Python can perform text operations on a string, but this mathematical model requires numbers as its input. Later lessons will show the exact numeric representation that reaches the model.

For `Cat`, the character-number list and byte list match. Remember why: we deliberately chose simple ASCII-range letters. Do not assume the two lists always match.

Now change only this line:

```python
text = "A"
```

Predict the output, then run the lab again. Both lists should contain `[65]`. Python followed an agreed representation. It did not discover what `A` means.

Finally, change the line back to `text = "Cat"` so the lab matches the documented output.

## 12:00 Common Mistake

A common mistake is saying, "The number `65` is the meaning of `A`."

It is not. `65` is the Unicode code point assigned to the character `A`. The character can mean different things in different situations, but the code point remains `65`.

Here is a useful check. Imagine that another character-mapping system assigned a different number to `A`. Would people suddenly stop using `A` as a school grade or musical note? No. The number is a representation of the character, not its human meaning.

Another mistake is saying that converting text into numbers is already learning. Calling `ord("A")` follows a fixed rule and returns the same answer every time. It does not improve through practice. Learning happens later, when training changes model parameters in response to prediction errors.

## 13:00 Recap And Exercise

Let us bring the whole lesson together.

1. A person can connect text with memories, feelings, and meaning. The computer receives only the represented input.
2. Unicode and UTF-8 provide agreed ways to represent written characters with numbers.
3. Those numbers identify or encode text. They do not contain human meaning, and producing them is not learning.
4. Learning happens when training changes a model's parameters so its predictions improve across examples.

Check your understanding aloud:

- Does a computer naturally understand `cat` like a human?
- What does `ord("A")` return, and what does that number represent?
- Is character number `65` the human meaning of `A`?
- Why must text become numbers before a mathematical model can use it?
- In one sentence, what does learning mean at this stage?

For the exercise, run the mini-lab with `A` and record the output. Then complete this sentence:

> The number 65 is assigned to ___, but it does not encode ___.

Return the lab to `Cat` when you finish.

In the next video, we will slow down and examine how computers store characters as agreed numbers.

Here is the idea to carry with you: **representing text gives the computer numbers to work with. Learning changes the model's internal numbers so its predictions improve.**

### Vocabulary Deferred to Later Videos

The terms **token**, **tensor**, **logit**, **gradient**, and **attention** are intentionally deferred. Each one will begin with plain-language intuition in its own later video.
