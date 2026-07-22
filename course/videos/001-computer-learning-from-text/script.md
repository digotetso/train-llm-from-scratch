# Video 1: What Does It Mean for a Computer to Learn From Text?

## 00:00 Hook

Put the word `cat` on screen.

When a person reads this word, it may activate memories and concepts. A computer receives only characters represented as data according to defined rules.The computer sees only the text, not what the text personally means to a human. That difference is our whole lesson.

By the end, you will be able to explain why text must be represented as numbers before a mathematical model can learn patterns from it. We will not assume any machine-learning knowledge. We will use three letters, three numbers, and a tiny Python file you can run yourself.

## 00:45 Direct Explanation

Programs represent written characters according to fixed standards. Unicode assigns each encoded character a **code point**, which is an integer. For example, uppercase `A` has code point `65`. Python returns that value every time because the assignment is defined by the standard; it is not learned from examples or changed during training.

A code point identifies a character. It does not encode the meaning that character has in context. `A` keeps code point `65` whether it denotes a school grade, a musical note, a blood type, or one letter inside a word.

Keep two categories separate: fixed numeric representations of text, and adjustable numeric values inside a model. Text representation supplies numeric data. Learning is the later process that updates the model's values from training examples.

## 02:00 Technical Meaning

Let us name the simple ideas.

For this lesson, a **character** is one element processed from a Python string, such as `C`, `a`, `t`, a space, or a question mark. **Unicode** is a shared standard that assigns a code point to each encoded character. Python's `ord` function returns the code point for one character.

```python
ord("C")  # 67
ord("a")  # 97
ord("t")  # 116
```

These values identify the encoded characters. They do not encode the fact that `Cat` names an animal. A different character-mapping system could use different numeric values without changing the word's human meaning.

A **byte** is eight bits and, when interpreted as an unsigned integer, has a value from 0 through 255. **UTF-8** is a widely used encoding that represents Unicode text as one or more bytes per code point. The letters in `Cat` are in the ASCII range, whose values UTF-8 preserves as single bytes. Their code-point values and UTF-8 byte values therefore match. Other characters can require multiple UTF-8 bytes. Video 4 will examine that carefully.

Now define a **model** in the smallest useful way: it is a set of mathematical operations with adjustable numeric values called **parameters**. Given numeric input, a model can produce a prediction, such as which written item is likely to come next. During training, an error measure compares predictions with expected outputs. At this stage, **learning** means updating the parameters with the aim of reducing average prediction error across many examples.

Text must therefore have a numeric representation for two separate reasons. First, software needs defined rules for storing and exchanging text. Second, a model's mathematical operations require numeric inputs. Encoding applies fixed mappings; learning updates separate model parameters based on examples.

## 04:00 Tiny Example

Suppose our three examples are:

```text
cat sat
cat ran
cat slept
```

In all three examples, a space follows `cat`, followed by a word describing an action. The program initially receives only represented values; no categories for animals or actions are supplied.

For an even smaller hand-check, use only `Cat`:

```text
Human-readable text: C    a    t
Agreed numbers:      67   97   116
```

Those numbers let a program check that the first value is `67`, count three values, or compare two numeric sequences for equality. The arithmetic distance between `67` and `97` does not describe a relationship between the meanings of `C` and `a`. These operations demonstrate numeric processing, not semantic information about the word `Cat`.

Suppose a model produces ten predictions and seven are incorrect. After training, it produces ten predictions on comparable examples and five are incorrect. This simple count illustrates improvement; actual training uses a numeric error measure rather than only counting incorrect predictions. The exact update method comes much later in the course. For today, keep this sequence in mind: process examples, produce predictions, measure error, update parameters using that error, and evaluate later predictions.

No dictionary definition of `cat` is supplied. During training, repeated statistical relationships in the examples affect parameter updates. We call such a repeatable relationship a **pattern**. A model can also memorize parts of its training data, so later evaluation uses separate examples to check whether performance extends beyond that data.

These character numbers are not learned meanings or **token embeddings**. The term `token embedding` is reserved for a later lesson and is not needed to explain today's idea.

## 06:00 Repository Walkthrough

**Source fact:** This repository does not pass remote, unprocessed text directly into training. Its data-preparation code first normalizes the text and stores the result. The relevant functions are in `matgpt/data/normalize.py` and `matgpt/data/prepare.py`.

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

Read the function from top to bottom. The first line names the function. `text: str` says the input is expected to be text, and `-> str` says the returned result is also text. These type annotations communicate expectations; they do not enforce the types at runtime. `str(text)` converts the input value to a Python string. `unicodedata.normalize("NFKC", ...)` applies the Unicode NFKC normalization form, including canonical and compatibility mappings. The next line makes different newline styles consistent. The list comprehension removes trailing whitespace from every line. `strip()` removes whitespace at the beginning and end of the whole string. Finally, `return text` returns the normalized value.

**Normalization-policy warning:** NFKC is a deliberate cleaning policy, not lossless cleanup. For example, it changes the circled character `①` into plain `1`. That can be useful when we want both forms treated alike, but it maps two distinct source characters to the same normalized output. Some inputs can also change character count, so the exact original text cannot always be recovered from the normalized result. Video 5 will explain the mechanics and tradeoffs; for now, remember that normalization is a choice, not a lossless copy.

The full repository function also removes certain non-printing control characters and limits runs of blank lines. This excerpt includes only the operations relevant to today's lesson.

Now look at a simplified excerpt showing where `prepare.py` uses that function:

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

**Observed code behavior:** `normalize_text(text)` receives source text and returns normalized text. The full record stores that text, its Python string length, and other metadata omitted above. `len(normalized)` does not always equal the number of symbols a person sees because one visible symbol can use multiple code points. This code does not perform model learning; it prepares consistent data for later operations.

A function can prepare data for training without updating model parameters. This function normalizes text. Numeric conversion and model operations occur later.

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

Before running it, predict the two lists. We already checked each character, so write `[67, 97, 116]` for both. This lab displays two numeric views of text for inspection. It does not yet show the exact numeric representation that the model will receive; later lessons add those steps.

From the repository root, run:

```bash
python course/videos/001-computer-learning-from-text/lab.py
```

Read the output one line at a time. `Human text` shows the form useful to us as readers. The list comprehension processes each character. `ord(character)` returns its Unicode code point. `text.encode("utf-8")` returns the UTF-8 byte sequence, and `list(...)` converts that sequence into integers for display. The question "Can the mathematical model use this raw Python string as numeric input? No" is deliberately narrow: Python can work with strings as text, but the mathematical model needs numeric input. Encoding is preparation, not learning, and later lessons will show the model's actual input representation.

For `Cat`, both lists show `67`, `97`, and `116`. Do not conclude that these lists always match. We chose simple English letters for this first hand-check.

Now change only this line:

```python
text = "A"
```

Predict again, then rerun the file. Both lists should contain `65`. `ord("A")` returned the assigned code point; it did not infer a semantic interpretation of `A` from examples.

Finally, change the line back to `text = "Cat"` so the lab matches the documented output.

## 12:00 Common Mistake

The common mistake is saying, "The number `65` is the meaning of `A`."

It is not. `65` is an agreed Unicode number for the character `A`. Human meaning depends on use and context. `A` could be a school grade, a musical note, a blood type, or one letter inside a word. The character number stays the same across those uses.

Use this check whenever the distinction becomes unclear: if a different character-mapping system assigned another number to the same character, would its human meaning have to change? No. The number is a representation, not the meaning itself.

Another mistake is saying that conversion alone is learning. The `ord` call applies a fixed mapping and returns the same result regardless of examples. Learning occurs when training updates model parameters in response to measured prediction error.

## 13:00 Recap And Exercise

Restate our objective: explain why text must be represented as numbers before a mathematical model can learn patterns from it.

Here is the explanation in four steps:

1. A program's input is represented data; a person's interpretation is not included in that data.
2. Standards such as Unicode and UTF-8 define numeric representations of written characters.
3. Code points and bytes identify or encode text; they do not encode human meaning and are not evidence of learning.
4. Learning updates model parameters with the aim of reducing average prediction error across many examples.

Check yourself aloud:

- Does the encoded input for `cat` include a person's semantic interpretation?
- What does `ord("A")` return?
- Does code-point value `65` encode every interpretation of `A`?
- Why does a mathematical model need numeric input?
- What changes when a model learns?

For the exercise, run the mini-lab with `A`, record the output, and write one sentence completing this statement: "The number 65 is assigned to ___, but it does not encode ___."

Then return the file to `Cat`. In the next video, we will examine assigned character numbers in more detail. Today's conclusion is limited to this sequence: text receives a numeric representation before training updates model parameters to reduce prediction error.

### Vocabulary Deferred to Later Videos

The terms **token**, **tensor**, **logit**, **gradient**, and **attention** are intentionally not taught or used as explanations in Video 1. Each will be introduced from plain language in its approved later video.
