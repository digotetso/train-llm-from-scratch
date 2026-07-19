# Video 1: What Does It Mean for a Computer to Learn From Text?

## 00:00 Hook

Put the word `cat` on screen.

When you read this word, you may picture an animal. You may remember a pet, a sound, or a story. Now place the same three letters into a Python program. Does the computer receive any of those memories or ideas?

No. The program receives data arranged according to agreed rules. That difference is our whole lesson.

By the end, you will be able to explain why text must be represented as numbers before a mathematical model can learn patterns from it. We will not assume any machine-learning knowledge. We will use three letters, three numbers, and a tiny Python file you can run yourself.

## 00:45 Analogy

**Teaching analogy:** Imagine a library card. A book may make you laugh, teach you history, or remind you of someone. The library gives that book an agreed identifier, perhaps `417`. The identifier helps a system store and find the book. But the number `417` does not contain the plot, mood, or meaning of the book.

Text begins with a similar separation. People agree that a written character can be represented by a number. The number lets programs store, copy, and compare the character. It does not place a human understanding of that character inside the machine.

**Where the analogy stops:** A library identifier often names a whole physical book. Text representation can work character by character and, at the storage level, with smaller numeric pieces. The analogy explains agreed identifiers; it does not explain the full text system or learning process.

Here is the question to keep asking: is this number an agreed label, or is it learned meaning? Today, the first character numbers are agreed labels.

## 02:00 Technical Meaning

Let us name the simple ideas.

A **character** is one written item, such as `C`, `a`, `t`, a space, or a question mark. **Unicode** is a shared standard that assigns defined characters agreed numbers. Python's `ord` function lets us inspect the Unicode number for one character.

```python
ord("C")  # 67
ord("a")  # 97
ord("t")  # 116
```

These facts tell us how the characters are represented. They do not tell us that `Cat` names an animal. If we changed the agreement, the stored numbers could change while the human meaning stayed the same.

A **byte** is a small stored number from 0 through 255. **UTF-8** is a widely used rule for turning Unicode text into one or more bytes. For the three simple English letters in `Cat`, the Unicode character numbers and UTF-8 bytes happen to match. They do not always match for characters from the rest of the world's writing systems. Video 4 will examine that carefully.

Now define a **model** in the smallest useful way: it is a number-based guessing system with internal numbers that can be adjusted. A guess might be, "What written item is likely to come next?" At this stage, **learning** means adjusting those internal numbers so the guesses become less wrong across many examples.

The input must therefore become numbers for two separate reasons. First, programs need an agreed representation for the text. Second, mathematical operations need numeric values. Representation gets the text through the door; learning adjusts other internal numbers from repeated examples.

## 04:00 Tiny Example

Suppose our three examples are:

```text
cat sat
cat ran
cat slept
```

A person notices that a space often follows `cat`, and then a word describing an action appears. A program does not begin with the ideas of animals, spaces, or actions. It begins with represented data.

For an even smaller hand-check, use only `Cat`:

```text
Human-readable text: C    a    t
Agreed numbers:      67   97   116
```

Those numbers allow arithmetic and comparison. For example, a program can check that the first value is `67`, count three values, or compare two numeric sequences. None of those operations proves that the program knows what a cat is.

Now imagine a model makes ten guesses and seven are wrong. After its internal numbers are adjusted, it makes ten more guesses and only five are wrong on comparable examples. The exact adjustment method comes much later in the course. For today, the important point is the direction: examples lead to measured mistakes; measured mistakes guide changes; useful changes make later guesses less wrong.

This is not memorizing a dictionary definition of `cat`. It is finding repeatable relationships in represented examples. We call such a repeatable relationship a **pattern**.

One boundary before we continue: these character numbers are not learned meaning, and they are not the later representation called a **token embedding**. That phrase is only a signpost for a future lesson. We are not using it to explain today's idea.

## 06:00 Repository Walkthrough

**Source fact:** This repository does not send remote raw text directly into training. Its preparation path first makes the text consistent and stores the cleaned result. The relevant functions are in `matgpt/data/normalize.py` and `matgpt/data/prepare.py`.

Start with this commented excerpt from `normalize.py`:

```python
def normalize_text(text: str) -> str:
    # Put equivalent-looking text into one agreed form.
    text = unicodedata.normalize("NFKC", str(text))

    # Use one newline style even if the source used another style.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove extra space from the right side of each line.
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines).strip()
    return text
```

Read the function from top to bottom. The first line names the function. `text: str` says the input is expected to be text, and `-> str` says the returned result is also text. The input named `text` is the raw value. `str(text)` ensures Python treats that value as text. The operation named `normalize` makes equivalent forms follow one agreement; `NFKC` is the name of that Unicode agreement, and its detailed rules belong to Video 5. The next line makes different newline styles consistent. The list line removes space at the right edge of every line. `strip()` removes space at the beginning and end of the whole text. Finally, `return text` gives the cleaned value back.

The full repository function also removes certain non-printing control characters and limits runs of blank lines. We are deliberately previewing its job, not teaching every cleaning rule today.

Now look at the point where `prepare.py` uses that function:

```python
# First pipeline step: make source text consistent.
normalized = normalize_text(text)

return {
    # Preserve the cleaned text for later processing.
    "text": normalized,

    # Record how many characters the cleaned text contains.
    "num_chars": len(normalized),
}
```

**Observed code behavior:** `normalize_text(text)` receives source text and returns cleaned text. The returned record stores that cleaned text and its character count. This block does not yet perform model learning. It prepares consistent data for later steps.

That distinction matters. A repository path can be part of a learning system without every function doing the learning itself. Here, cleaning is preparation. Numeric representation and later model operations build on top of that preparation.

## 09:00 Live Mini-Lab

Open `course/videos/001-computer-learning-from-text/lab.py`.

```python
text = "Cat"

print("Human text:", text)
print("Character numbers:", [ord(character) for character in text])
print("UTF-8 bytes:", list(text.encode("utf-8")))
print("Can arithmetic use the raw string directly? No")
print("Learning begins after text is represented as numbers.")
```

Before running it, predict the two lists. We already checked each character, so write `[67, 97, 116]` for both.

From the repository root, run:

```bash
python course/videos/001-computer-learning-from-text/lab.py
```

Read the output one line at a time. `Human text` shows the form useful to us as readers. The list operation visits each character. `ord(character)` asks for its agreed Unicode number. `text.encode("utf-8")` applies the UTF-8 storage rule, and `list(...)` displays each resulting byte as an ordinary number.

For `Cat`, both lists show `67`, `97`, and `116`. Do not conclude that these lists always match. We chose simple English letters for this first hand-check.

Now change only this line:

```python
text = "A"
```

Predict again, then rerun the file. Both lists should contain `65`. Ask yourself: did Python discover the meaning of the letter `A`, or did it follow an agreed representation? It followed an agreement.

Finally, change the line back to `text = "Cat"` so the lab matches the documented output.

## 12:00 Common Mistake

The common mistake is saying, "The number `65` is the meaning of `A`."

It is not. `65` is an agreed Unicode number for the character `A`. Human meaning depends on use and context. `A` could be a school grade, a musical note, a blood type, or one letter inside a word. The character number stays the same across those uses.

Use this debugging question whenever the idea becomes blurry: if the agreed number changed but people still read the same character, would its human meaning have to change? No. That shows the number is a representation, not the meaning itself.

Another mistake is saying that conversion alone is learning. The `ord` call follows a fixed rule; it does not improve from examples. Learning begins when a model's adjustable internal numbers change in response to measured mistakes.

## 13:00 Recap And Exercise

Return to our objective: explain why text must be represented as numbers before a mathematical model can learn patterns from it.

Here is the explanation in four steps:

1. A program receives represented data, not a person's understanding of a word.
2. Agreed systems such as Unicode and UTF-8 let programs represent written characters with numbers.
3. Those first numbers identify text; they are not human meaning and are not themselves evidence of learning.
4. Learning means adjusting a model's internal numbers so its guesses become less wrong across many examples.

Check yourself aloud:

- Does a computer naturally understand `cat` like a human?
- What does `ord("A")` return?
- Does `65` contain every human meaning of `A`?
- Why does a mathematical model need numeric input?
- What changes when a model learns?

For the exercise, run the mini-lab with `A`, record the output, and write one sentence completing this frame: "The number 65 represents ___, but it does not contain ___."

Then return the file to `Cat`. In the next video, we will slow down and examine agreed character numbers themselves. Today, stop at the boundary: text becomes numeric data first; learning is the later adjustment that makes repeated guesses less wrong.

### Deferred Vocabulary Boundary

The terms **token**, **tensor**, **logit**, **gradient**, and **attention** are intentionally not taught or used as explanations in Video 1. Each will be introduced from plain language in its approved later video.
