# Video 1: What Does It Mean for a Computer to Learn From Text?

## 00:00 Hook

[On screen: `cat`]

When you read `cat`, you probably do more than notice three letters. You may picture an animal, remember a pet, or hear the word in your head. Your experience supplies meaning almost instantly.

Now think about what you may have seen an AI system do. It can rewrite an essay, improve an email, or write code. You type in text, and useful text comes back.

But what does the computer receive when you type? It does not receive your memories or your idea of a cat. Underneath the familiar text box, its mathematical operations work with numbers.

So here is our question: before an AI system can do those useful things with text, how does the text you type become something its mathematics can work with?

By the end, you will be able to explain why text needs a numeric form and why creating that form is not yet learning. We will build the answer with three letters, three numbers, and a tiny Python file you can run yourself.

First, we need a smaller question: how can a number identify something without containing its meaning?

## 00:45 Analogy

**Teaching analogy:** Imagine that a library gives every book an identifier. The identifier helps the library distinguish and locate the book. It does not contain the book's story, and it does not recreate what a reader feels while reading it.

Written characters also need agreed identifiers so software can store and process them consistently. An identifier answers, “Which item is this?” It does not answer, “What does this mean here?”

Here is the analogy's **limit**: a library identifier may refer to a whole physical book, while text systems represent individual written items and their stored forms. The analogy also does not explain learning. It only gives us a bridge from an item to an agreed identifier.

Now return to the actual system. Which agreed number will Python report for the letter `A`, and why will that answer stay the same every time?

## 02:00 Technical Meaning

Let us name the mechanism one part at a time.

For this lesson, a **character** is one item Python processes from a string, such as `C`, `a`, `t`, a space, or a question mark.

Software needs a shared agreement that distinguishes those characters. **Unicode** is that shared standard. It assigns each encoded character an integer identifier called a **code point**. Python's `ord` function reports the code point for one character:

```python
ord("C")  # 67
ord("a")  # 97
ord("t")  # 116
```

Before looking ahead, compare those calls. If we run `ord("C")` again tomorrow, should the answer improve or change? No. Python is following a fixed agreement. The number identifies `C`; it does not contain the fact that `Cat` names an animal.

There is one more representation layer to distinguish. A **byte** is eight bits and can hold an unsigned value from 0 through 255. **UTF-8** is a widely used rule that represents Unicode text as one or more bytes for each code point.

For the simple English letters in `Cat`, the code-point values and the UTF-8 byte values match. Those letters are in the ASCII range, and UTF-8 stores each one as a single byte with the same value. That is a property of this example, not a universal rule. Other characters can require several UTF-8 bytes. Video 4 will build that mechanism carefully.

Now we can define the other half of our question. A **model** is a mathematical prediction system with adjustable numbers called **parameters**. It receives numeric input and produces a prediction. During training, we measure how wrong a prediction is and use that measured error to adjust the parameters. At this stage, that parameter change is what we mean by **learning**.

Now that we understand both actions, we can give the distinction a stable name. **Text representation** changes the form of the input by following fixed agreements. **Learning** changes the model's adjustable parameters using examples and measured error.

We can now use this representation–learning distinction as a building block:

> Text representation follows fixed agreements. Learning changes adjustable model parameters using examples and measured error.

## 04:00 Tiny Example

Let's use that building block immediately. Start with the representation side and predict the three code points for `Cat`. Then compare your answer with this trace:

```text
Human-readable text: C    a    t
Agreed numbers:      67   97   116
```

Those numbers let a program count values, compare sequences, or select a value by position. But the arithmetic distance between `67` and `97` is not the difference in meaning between `C` and `a`. The numbers represent the characters under an agreement; they do not carry the human meaning of the word.

Now keep that representation fixed and move to the learning side. Suppose the training examples include:

```text
cat sat
cat ran
cat slept
```

What repeats? Each line begins with `cat`, followed by a space and then an action word. No label says “animal” or “action.” The examples only supply repeated relationships that can affect later predictions.

Now imagine a model makes ten predictions and gets seven wrong. Training uses those mistakes to adjust its parameters. On comparable later examples, it gets five wrong. Seven mistakes becoming five gives us a small intuition for improvement: predictions changed after measured error changed the adjustable numbers.

Real training uses a numeric error measure rather than this simple mistake count. A model may also memorize its training examples, so we check improvement on separate examples it did not train on. We will build the exact update method much later. For now, the causal chain is enough: examples lead to predictions, predictions produce measurable error, and that error guides parameter changes.

## 06:00 Repository Walkthrough

**Source fact:** This repository does not send remote, unprocessed text straight into training. It first normalizes the text and stores the result. The relevant code lives in `matgpt/data/normalize.py` and `matgpt/data/prepare.py`.

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

Read the changes from top to bottom. `text: str` and `-> str` communicate the expected input and output types; Python does not enforce those annotations at runtime. `str(text)` first asks Python for a string form of the input.

Next, `unicodedata.normalize("NFKC", ...)` applies a chosen Unicode normalization form. Then the `replace` calls turn different newline styles into `\n`. The list comprehension removes trailing whitespace from each line. The final `strip()` removes whitespace from the outer edges, and `return text` gives the normalized string back to the caller.

**Normalization-policy warning:** NFKC is a deliberate cleaning policy, not lossless cleanup. For example, it changes the circled character `①` into plain `1`. That can be useful when both forms should be treated alike, but it also collapses a distinction in the source. Some inputs can change character count, so the original text cannot always be recovered exactly. Video 5 will examine that tradeoff. For now, keep one point: normalization is a choice, not a lossless copy.

The full repository function also removes selected non-printing control characters and limits runs of blank lines. The excerpt shows only the operations needed for today's trace.

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

**Observed code behavior:** `normalize_text(text)` receives source text and returns normalized text. The record stores that result and the Python string length reported by `len(normalized)`, along with other metadata omitted here. That length does not always equal the number of symbols a person sees, because one visible symbol can involve multiple code points.

What changed in this walkthrough? The text became more consistent, and the record captured its normalized form and length. What did not change? No model parameter was updated. This is data preparation, not learning. That distinction leads directly to our lab: can we inspect fixed numeric representations without pretending the inspection itself teaches the model?

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

Before you run it, predict both numeric lists. We already traced each character, so write down `[67, 97, 116]` for the character numbers. Will the UTF-8 list match for these three letters? Our earlier rule says yes.

From the repository root, run:

```bash
python course/videos/001-computer-learning-from-text/lab.py
```

Now explain each observed line. `Human text` shows the form useful to us as readers. The list comprehension visits one character at a time, and `ord(character)` reports its Unicode code point. `text.encode("utf-8")` produces the UTF-8 bytes, while `list(...)` displays those bytes as ordinary integers.

For `Cat`, both lists contain `67`, `97`, and `116`. The match confirms our prediction for these ASCII-range letters. It does not prove that code points and UTF-8 bytes always match.

The line `Can the mathematical model use this raw Python string as numeric input? No` makes a narrow claim. Python can perform text operations on a string. The mathematical model needs numeric input, and later lessons will show the representation it actually receives. This file demonstrates preparation; it does not update parameters.

Now change only one input:

```python
text = "A"
```

Predict again before rerunning the file. Both lists should contain `65`. When the output confirms that prediction, ask what caused it. `ord("A")` followed the same fixed agreement as before. It did not practice, measure an error, or improve.

Finally, return the line to `text = "Cat"` so the lab matches the documented output.

## 12:00 Common Mistake

The first common mistake is saying, “The number `65` is the meaning of `A`.”

It is not. `65` identifies the character `A` under the Unicode agreement. `A` might be a school grade, a musical note, a blood type, or one letter in a word. Its human meaning changes with context while its code point stays the same.

Try this diagnostic question: if another character system assigned a different number to `A`, would people have to change what `A` means? No. The number is a representation, not the meaning.

The second mistake is saying that conversion is learning. `ord` applies a fixed mapping. It returns the same result no matter how many examples you show it. Learning requires something adjustable: training measures prediction error and changes model parameters in response.

## 13:00 Recap And Exercise

Let us rebuild the answer in plain language.

When you read `cat`, you bring meaning from your experience. Software first handles represented text. Unicode gives characters code points, and UTF-8 represents those characters as bytes. Those fixed mappings make the text usable as data, but applying them does not teach a model anything.

A model begins to learn only when it makes predictions, measures error, and changes its adjustable parameters so later predictions can improve.

Check the model in your own head:

- What does `ord("A")` return, and why is that answer stable?
- Why does `65` identify `A` without containing every meaning of `A`?
- What must change before we can say learning occurred?
- If the input changes from `Cat` to `A`, which parts of your trace should change and which rule stays fixed?

For the exercise, run the mini-lab with `A`, record the output, and complete this sentence: “The number 65 is assigned to ___, but it does not encode ___.” Then return the file to `Cat`.

The representation–learning distinction is now one of our building blocks, not just a sentence to memorize. Text representation gives the model numbers it can work with. Learning changes the model's adjustable numbers—its parameters—so later predictions can improve.

In the next lesson, we will use the representation side of that building block to ask a more precise question: how does a computer assign stable numbers to written characters? Because we already know this is representation rather than learning, we can focus on how those agreed numbers are assigned.

### Vocabulary Deferred to Later Videos

The terms **token**, **tensor**, **logit**, **gradient**, and **attention** are intentionally not taught or used as explanations in Video 1. Each will be introduced from plain language in its approved later video.
