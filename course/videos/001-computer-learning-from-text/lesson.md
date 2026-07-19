# Video 1: What Does It Mean for a Computer to Learn From Text?

## Prerequisites

- Run `python path/to/file.py` from a terminal.
- Read a Python string such as `"Cat"` and a list such as `[67, 97, 116]`.
- No machine-learning knowledge is assumed.

## Learning Objective

Explain why text must be represented as numbers before a mathematical model can learn patterns from it.

## Simple Explanation

When a person reads `cat`, memories and meaning may come to mind. A program is not given those experiences. It receives data that follows agreed storage rules.

The written items `C`, `a`, and `t` can each be represented by an agreed number. Numbers give a program values it can store, compare, count, and use in calculations. Those agreed numbers do not contain the human meaning of the word.

After text has a numeric form, a number-based guessing system can use many examples. It learns when its adjustable internal numbers change so later guesses become less wrong across those examples.

## Analogy And Its Limitation

**Teaching analogy:** A library gives a book an identifier so it can store and find that book. The identifier helps the system, but it does not contain the book's story or emotional meaning.

Character numbers play a similar identifying role. They let software handle written characters without containing the characters' human meaning.

**Limitation:** A library identifier often names one whole physical book. Text systems can represent individual characters and smaller storage pieces. The analogy explains an agreement between identifier and item; it does not explain the whole text pipeline or how a model learns.

## Technical Meaning

- A **character** is one written item, such as a letter, digit, space, or punctuation mark.
- **Unicode** is a shared standard that assigns defined characters agreed numbers.
- `ord` is a Python function that returns the Unicode number for one character.
- A **byte** is a stored number from 0 through 255.
- **UTF-8** is a common rule for representing Unicode text as one or more bytes.
- A **model** is a mathematical guessing system with adjustable internal numbers.
- A **pattern** is a repeatable relationship in examples that can help a guess.
- **Learning** is the adjustment of a model's internal numbers so prediction mistakes become smaller across examples.

Representation and learning are different actions. `ord("A")` follows a fixed agreement and returns `65`; it does not improve through practice. A model learns only when its adjustable values change in response to measured mistakes.

## Tiny Math Or Text Example

```text
Text:              C    a    t
Unicode numbers:  67   97   116
UTF-8 bytes:      67   97   116
```

For these three simple English letters, both numeric lists happen to match. Other writing systems can require more than one UTF-8 byte for a character; that detail is reserved for Video 4.

Imagine ten model guesses with seven mistakes. After an adjustment, imagine ten comparable guesses with five mistakes:

```text
Before adjustment: 7 mistakes out of 10
After adjustment:  5 mistakes out of 10
Change:             2 fewer mistakes
```

This tiny count is an intuition for improvement, not a description of the repository's full training calculation.

## Commented Repository Code

`matgpt/data/normalize.py` begins the local text pipeline by making source text consistent:

```python
def normalize_text(text: str) -> str:
    # Apply one agreed Unicode form to equivalent text.
    text = unicodedata.normalize("NFKC", str(text))

    # Replace two possible source newline styles with one style.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove right-edge spaces per line and outer spaces overall.
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines).strip()
    return text  # Give the cleaned text back to the caller.
```

Input: a source value treated as text. Output: cleaned, consistent text. `NFKC` is the name of a Unicode consistency rule; its details are intentionally deferred to Video 5. The full function also removes certain non-printing control characters and reduces long runs of blank lines.

`matgpt/data/prepare.py` then stores the cleaned value:

```python
# Clean the source text before storing the document record.
normalized = normalize_text(text)

return {
    "text": normalized,             # Text used by later pipeline steps.
    "num_chars": len(normalized),   # Count of cleaned characters.
}
```

This is preparation, not learning. The function receives text, cleans it, and records the result. Later videos follow the result into its numeric forms and into the model.

## Misconception

**Wrong idea:** Character number `65` is the human meaning of `A`.

**Correction:** `65` is an agreed Unicode number for the character. The same `A` can mean a grade, a musical note, a blood type, or part of a word. The numeric identifier stays the same while the human meaning changes with context.

**Check:** Ask whether changing the numeric agreement would force people to change what the character means. If not, the number is a representation rather than the meaning.

A second wrong idea is that running `ord` performs learning. `ord` follows a fixed rule. Learning requires adjustable model values, examples, measured mistakes, and changes that reduce those mistakes.

## Recap

1. Programs receive represented data rather than a person's understanding.
2. Characters must have agreed numeric representations before mathematical operations can use them.
3. Character numbers and UTF-8 bytes do not contain human meaning.
4. Learning starts after representation: a model's internal numbers are adjusted so guesses become less wrong across examples.

## Deferred Vocabulary Boundary

**Token**, **tensor**, **logit**, **gradient**, and **attention** are future terms, not explanations used by this lesson. **Token embedding** is only named to prevent the misconception that a Unicode number is a learned representation; its meaning is deferred to Videos 11 and 23.
