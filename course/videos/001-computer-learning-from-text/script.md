# Video 1: What Does It Mean for a Computer to Learn From Text?

## 00:00 Hook

[On screen: `cat`]

When you read `cat`, you may picture an animal or remember a pet. That meaning comes from your experience. You've seen AI work with text too: it can rewrite an essay, improve an email, or write code.

But here's the puzzle. On your computer, the text box shows words, while the model underneath works by calculating with numbers. So how does the text you type become numbers the model can use—and why is that conversion not yet learning?

By the end, you'll explain the difference with three letters, three numbers, and a tiny Python file. To get there, let's start with a smaller question: how can a number identify something without containing its meaning?
 
## 00:45 Analogy

**Teaching analogy:** Imagine a library where every book has a number. It helps the librarian find the right book, while the story stays inside. That number is an **identifier**: it tells us which book, not what the story means.

Text systems do something similar: agreed numbers help software tell characters apart. But the analogy only takes us so far. Here is its **limit**: a library number can point to a whole book, while text systems represent individual characters and stored forms. This bridge explains identification, not learning.

Now return to Python and predict: does it invent a new number for `A` every time, or follow a fixed agreement? Hold your answer, and let's find out.

## 02:00 Technical Meaning

Now that you have a prediction, let's find out what rule Python actually follows. Take `C`, `a`, and `t`. Python processes each one as a **character**—one item from a string, just like a space or a question mark.

Software needs a shared agreement that distinguishes those characters. **Unicode** is that shared standard. It assigns each encoded character an integer identifier called a **code point**. Python's `ord` function reports the code point for one character:

```python
ord("C")  # 67
ord("a")  # 97
ord("t")  # 116
```

Before looking ahead, compare those calls. If we run `ord("C")` again tomorrow, should the answer improve or change? No. Python is following a fixed agreement. The number identifies `C`; it does not contain the fact that `Cat` names an animal.

So far, we have one agreed number for each character. But when text is stored or sent, there is another layer: the **byte**. A byte is eight bits and can hold an unsigned value from 0 through 255. **UTF-8** is a widely used rule that represents Unicode text as one or more bytes for each code point.

For the simple English letters in `Cat`, the code-point values and the UTF-8 byte values match. Those letters are in the ASCII range, and UTF-8 stores each one as a single byte with the same value. That is a property of this example, not a universal rule. Other characters can require several UTF-8 bytes. Video 4 will build that mechanism carefully.

We can now explain how text gets a numeric form, but that still does not explain learning. For that, we need a **model**: a mathematical prediction system with adjustable numbers called **parameters**. It receives numeric input and produces a prediction. During training, we measure how wrong that prediction is and use the error to adjust the parameters. At this stage, that parameter change is what we mean by **learning**.

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

Our tiny example gives us the idea. Now let's see where the representation side appears in this project.

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

Let's follow the value from top to bottom. `text: str` and `-> str` communicate the expected input and output types; Python does not enforce those annotations at runtime. `str(text)` first asks Python for a string form of the input.

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

Now let's test the same ideas ourselves. Open `course/videos/001-computer-learning-from-text/lab.py`.

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

By now, two common mistakes should stand out. The first is saying, “The number `65` is the meaning of `A`.” But `65` identifies the character `A` under the Unicode agreement. `A` might be a school grade, a musical note, a blood type, or one letter in a word. Its human meaning changes with context while its code point stays the same.

Try this diagnostic question: if another character system assigned a different number to `A`, would people have to change what `A` means? No. The number is a representation, not the meaning.

The second mistake is saying that conversion is learning. `ord` applies a fixed mapping. It returns the same result no matter how many examples you show it. Learning requires something adjustable: training measures prediction error and changes model parameters in response.

## 13:00 Recap And Exercise

We've followed the idea from human meaning to represented text and then to learning. Now let's rebuild the answer in plain language.

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
