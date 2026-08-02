# Video 1 — Script 3: What Does It Mean for a Computer to Learn From Text?

## 00:00 The Question Under the Text Box

[On screen: an email being rewritten, one essay sentence becoming clearer, and a short code suggestion.]

You've probably seen an AI do something useful with text. It can clarify a rough email, improve an essay sentence, or suggest code for a small programming task.

Because both sides of that exchange are readable, it's easy to picture the system receiving words as you do. You connect a sentence with experience and meaning. But the useful result doesn't reveal the mechanism that produced it.

Under the familiar text box, the model works through calculations, and calculations need numerical input. That gives us our question: how can a system that calculates with numbers begin with text and eventually produce coherent output, such as a rewritten email, an improved essay, or working code?

That journey contains several mechanisms, so we'll begin with the first bridge: how written text receives a numerical form, and why crossing that bridge is not yet learning. By the end, you'll be able to trace the difference. We only need one character to begin.

## 00:45 One Character, One Stable Number

[On screen: `A`, followed by `ord("A")`.]

Start with `A`. Python can report a number for this one written item. Before we look at the result, predict what will happen if we run the same instruction twice. Will Python invent a fresh number on each run, or will it follow a stable standard?

```python
ord("A")
```

The result is `65`. Run it again and it is still `65`. Python is following a fixed standard that connects this written item with this number.

Now we can give each part a useful name. `A` is a **character**: one written item. A digit, space, or question mark is a character too.

The shared standard is **Unicode**. Its job here is to give software a consistent way to identify defined characters. For each defined character, Unicode assigns an integer called a **code point**. Python's `ord` function reports that code point for one character. So `ord("A")` returns the code point `65`.

At this point, you may be wondering whether `65` somehow contains the meaning of `A`. Try changing the context. `A` might be a school grade, a musical note, a blood type, or one letter in a name. The human meaning changes, but Python still reports `65`.

So the number identifies the character under a standard; it does not contain all the meanings people can give that character. We now have one stable character-to-number mapping. The next question is what this looks like when the text contains more than one character.

## 02:00 From One Character to Text Representation

[On screen: `Cat`, separated into `C`, `a`, and `t`.]

Take the text `Cat`. Python can visit it one character at a time. The same rule we used for `A` gives us `67` for `C`, `97` for `a`, and `116` for `t`.

```text
Text:        C    a    t
Code points: 67   97   116
```

These values distinguish the three characters. They say nothing about whiskers or animals. Those associations come from human experience, not the distance between `67`, `97`, and `116`.

There is one more layer we need for this example. When text is stored or sent, software works with **bytes**. A byte can hold an unsigned value from `0` through `255`. **UTF-8** is a widely used rule for representing a Unicode character as one or more bytes.

Before seeing the bytes for `Cat`, make a prediction. Will their values match the three code points we just traced?

```text
UTF-8 bytes: 67   97   116
```

They do match in this case. `C`, `a`, and `t` are in the ASCII range, and UTF-8 stores each of them as one byte with the same value as its code point. That convenient match is not a general rule. Other characters can require more than one UTF-8 byte, so a code point and a byte sequence remain different ideas even when these two short lists look identical.

We can now give this process a name we'll reuse: **text representation**—changing text into a numerical form that software can store and process. Our `Cat` trace demonstrates an early representation layer; later lessons will continue the path toward the precise numerical input used by the model.

Now use this building block to ask a sharper question. When we represented `Cat` with numbers, what changed—and did anything learn?

## 04:00 What Representation Still Cannot Explain

The form of the data changed. We began with three readable characters and produced code points and bytes. But the rules doing that conversion stayed fixed. Unicode did not revise the code point for `C`, and UTF-8 did not become better at representing `Cat` after another attempt.

So what would learning require that we have not seen? Imagine a numerical system receiving examples and producing an answer. We compare that answer with the intended outcome and calculate a measured error. The error guides changes to adjustable numbers inside the system. A later example then produces an answer using those changed values.

Now the technical names have something concrete to describe. A **model** is the mathematical system producing those answers. Its adjustable internal numbers are called **parameters**. **Learning** is the process in which examples and measured error change those parameters so later answers can improve.

For a small intuition, suppose a model makes ten comparable attempts and seven are wrong. After its parameters are adjusted, suppose five of ten later attempts are wrong. Seven becoming five gives us a simple picture of improvement after a change.

It isn't the repository's training calculation, and it doesn't prove improvement on unseen examples. Real training uses a numerical error measure and checks separate examples too. For now, the count shows the missing action: measured error changed something adjustable.

That is exactly what `ord("A")` and UTF-8 never do. They apply stable rules. You can run them a thousand times, but no parameter changes because an earlier result was wrong.

We can therefore keep one distinction and use it throughout the course:

> Representation changes the form of the data.
>
> Learning changes adjustable model parameters using examples and measured error.

We have built that distinction from observable steps. Now it can do some work for us. When this repository normalizes and stores text, which side of the distinction are we looking at?

## 06:00 Apply the Distinction to the Repository

[On screen: `matgpt/data/normalize.py`, followed by `matgpt/data/prepare.py`.]

Before we trace the code, predict the category. Does `normalize_text` change the text data, change model parameters, or does it do both? Keep the representation–learning distinction in mind while we follow the value.

Here is the current function:

```python
def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_RE.sub("", text)
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines).strip()
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text
```

The value enters as `text`. `str(text)` first asks Python for its string form, and NFKC applies the project's chosen Unicode normalization policy. The next line makes newline styles consistent. Then the function removes selected control characters, removes trailing whitespace from each line, strips whitespace from the outer edges, and limits long runs of blank lines. Finally, it returns the resulting string.

The annotations `text: str` and `-> str` communicate the intended input and output to readers and tools. Python does not enforce those annotations at runtime; that is why `str(text)` still performs a real operation.

One caution belongs here. NFKC is a deliberate, non-lossless cleaning policy. For example, `①` can become `1`. That can be useful when the project wants those forms treated alike, but it collapses a distinction from the source. Character count can change too, so the original input cannot always be reconstructed exactly.

The returned value then reaches `prepare.py`:

```python
normalized = normalize_text(text)

return {
    "text": normalized,
    "num_chars": len(normalized),
}
```

The record stores the normalized text and its Python string length. We can now answer our prediction. The data changed, but no measured error adjusted a model parameter. This is preparation, so it belongs on the text representation side of our distinction. The repository's mini-lab lets us inspect an even smaller part of that representation directly.

## 09:00 Predict, Run, Explain

[On screen: `course/videos/001-computer-learning-from-text/lab.py`.]

Here is the complete lab:

```python
text = "Cat"

print("Human text:", text)
print("Character numbers:", [ord(character) for character in text])
print("UTF-8 bytes:", list(text.encode("utf-8")))
print("Can the mathematical model use this raw Python string as numeric input? No")
print("Learning begins after text is represented as numbers.")
```

Use the rule we already built to predict both lists, then run:

```bash
python course/videos/001-computer-learning-from-text/lab.py
```

The observed output is:

```text
Human text: Cat
Character numbers: [67, 97, 116]
UTF-8 bytes: [67, 97, 116]
Can the mathematical model use this raw Python string as numeric input? No
Learning begins after text is represented as numbers.
```

The first line displays the string for us. The list comprehension visits one character at a time, and `ord` reports each code point. `encode("utf-8")` produces the UTF-8 bytes, while `list` displays their values as ordinary integers. The two lists match because this example uses ASCII-range characters, not because code points and bytes are always the same.

The final two lines mark the boundary. Python can perform text operations on a string, but the mathematical model requires numerical input. Printing these representations does not update any parameter.

Now change only `Cat` to `A`. Use the same rule to predict again: both lists should be `[65]`. When the output confirms that result, notice why it was predictable. Python followed the same stable standard; it did not learn from the earlier run. Restore `Cat` when you finish.

## 12:00 Two Questions That Keep the Model Honest

Our trace gives us two useful questions whenever an explanation starts to blur. First, is an identifier being mistaken for meaning? Put `A` in a report card and then in a piece of music. Its human interpretation changes with context, while its Unicode code point remains `65`. The identifier helps software distinguish the character; people supply the meaning.

That answer leads naturally to the second question: did any adjustable value change because an error was measured? Run `ord("A")` a thousand times and the answer is still no. The fixed mapping is doing representation work. If examples produce answers, measured error, and parameter changes, then we have crossed into learning.

These questions are useful because representation and learning are connected without being the same action. Representation makes numerical processing possible. Learning adds a system that can change in response to error.

## 13:00 Rebuild the Complete Chain

Let's return to the text box and rebuild what now sits underneath our original question. You enter text carrying meaning for you. Software identifies its characters through stable numerical standards. Unicode assigns code points, and UTF-8 represents those characters as bytes for storage or transmission. Further preparation can then produce the precise numerical input a model requires.

Once numerical input exists, a model can produce an answer. Training compares that answer with an outcome, calculates a measured error, and uses that error to change parameters. A later answer is produced with those changed internal values and may improve. That is the complete distinction we needed today:

> Representation changes the form of the data.
>
> Learning changes adjustable model parameters using examples and measured error.

Try transferring the model rather than memorizing the sentence. For `A`, explain why `65` remains stable even when the human context changes. Then ask what evidence you would need before claiming that learning occurred. You should be able to point to an answer, measured error, and a changed parameter—not merely a new numeric form for the text.

We can now use text representation as a building block in Video 2. Since written characters need stable numbers, how does a computer assign those numbers consistently? That question takes us deeper without confusing the assignment rule with training.

**Deferred vocabulary boundary:** **token**, **tensor**, **logit**, **gradient**, **attention**, and **embedding** are future terms and are not used to explain this lesson.
