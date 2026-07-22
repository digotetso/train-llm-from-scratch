# Video 1 — Script 2: What Does It Mean for a Computer to Learn From Text?

## 00:00 Hook

[On screen: a rewritten email, an improved essay sentence, and a small code suggestion.]

You may already have asked an AI to rewrite an email, improve an essay, or suggest code. The reply can look as though the system is working with the meaning you see in the words. But underneath that familiar text box, the model calculates with numerical inputs.

That gives us a useful mystery to solve. You see meaningful text. The model needs numbers it can calculate with. Before we ask how a model learns from many examples, ask the smaller question that makes the rest possible: how can one written character receive a stable number without that number containing the character's meaning?

We will build the answer from one character, then use the completed idea to see what learning adds. By the end, you should be able to trace the chain rather than just repeat a definition.

## 00:45 One Character, One Stable Number

[On screen: `A` followed by a question mark.]

Start with one written mark: `A`. Suppose we ask Python for a number for it. Before seeing the result, make a prediction. Does Python invent a number each time we run the program, or does it follow a fixed agreement?

Run this small check:

```python
ord("A")
```

Python returns `65`. It will return `65` again because the program is following an established agreement, not making a fresh guess. First notice the behavior: one written item reliably leads to one agreed number in this case.

Now we can give the pieces their useful names. `A` is a character: one written item. Unicode is the shared agreement that gives defined characters agreed numbers. The number assigned to a character in that agreement is its code point. Python's `ord` reports that code point for one character, so `ord("A")` is `65`.

Here is the question a careful learner should ask immediately: does `65` contain what `A` means? No. In one context `A` can be a grade, in another a musical note, and in another part of a name. The code point stays fixed while people supply meaning from context. It is an identifier under an agreement, not a container for human meaning.

Keep that completed mechanism as a stable building block: a character can have a fixed numeric identifier. If one character can do that, what happens when the text is three characters long?

## 02:00 From One Character to Numeric Text

[On screen: `Cat` with one arrow from each character.]

Return to `Cat` and trace it one piece at a time. `C` maps to `67`, `a` maps to `97`, and `t` maps to `116`. Nothing in this trace asks what a cat is. The agreement only gives software a consistent way to distinguish the three characters.

```text
Text:        C    a    t
Code points: 67   97   116
```

At this point, the code-point sequence is already clear. There is also a storage and transmission layer. A byte is a stored number from 0 through 255. UTF-8 is a common rule for representing Unicode text as one or more bytes. For `Cat`, the UTF-8 bytes are also `67`, `97`, and `116`.

That match has a specific reason. These letters are in the ASCII range, where UTF-8 uses one byte with the same value as the code point. Do not turn this convenient example into a universal rule: other characters can use more than one UTF-8 byte, so a code point and a byte sequence are different ideas even when these lists look alike.

We can now compress the mechanism into a name we will reuse: **numeric text representation** is a stable way to give text a numerical form that software can store and process. We have not taught a model anything by making this representation. We have only changed the form of the data. That unfinished part is exactly where the next question comes from.

## 04:00 What Representation Still Cannot Do

What changed when `Cat` became `67, 97, 116`? The form changed. What did not change? No system made a better prediction, and no adjustable value was updated. Numeric text representation is necessary for a mathematical model to receive text as numbers, but it cannot by itself make the model improve.

So imagine a small prediction system. We show it examples. It produces a prediction. We compare that prediction with what actually happened and obtain a measured error. Then some adjustable internal numbers are changed. On a later example, the system makes another prediction. That is the smallest causal chain we need: examples lead to prediction, prediction leads to measured error, and measured error can lead to a change in adjustable values before a later prediction.

For intuition, imagine ten comparable predictions. Before an update, seven are mistakes. After an update, five are mistakes. Seven becoming five is a picture of fewer mistakes, not the repository's actual training calculation and not proof that the system will work on unseen examples. A real check needs a numeric error measure and separate examples as well.

Notice what this example lets you distinguish. Rewriting `Cat` as three numbers can be repeated perfectly without ever consulting an outcome. The later change from seven mistakes to five depends on comparing predictions with outcomes and changing something adjustable in response. The numbers in the input and the numbers inside the model have different jobs. One supplies a form the calculation can receive; the other are candidates for change when the prediction is wrong.

Now the names have something concrete to attach to. A model is a mathematical prediction system. Its adjustable internal numbers are parameters. Learning is the process in which examples and measured error change those parameters so later predictions can improve.

Close the two mechanisms into one distinction we can use. **Representation changes the form of the data. Learning changes the model's adjustable parameters using examples and measured error.** If that distinction is real, it should help us classify code in this repository instead of remaining a slogan.

## 06:00 Repository Walkthrough

[On screen: `normalize.py` flowing into `prepare.py`.]

Use the distinction we just built as a question: when this code runs, is it changing data, or is it changing model parameters? In `matgpt/data/normalize.py`, `normalize_text` begins by applying NFKC, a chosen Unicode normalization form. It then replaces Windows-style and older newline styles with `\n`, removes selected control characters, removes whitespace at the right edge of each line, strips whitespace from the outer edges, reduces long blank-line runs, and returns the cleaned text.

The trace matters. Source text enters the function. NFKC changes it according to the chosen form. Newline replacement makes line endings consistent. The line cleanup and outer stripping remove selected whitespace. The function returns the resulting text; it does not make a prediction or adjust a parameter.

The annotations `text: str` and `-> str` communicate the intended input and output types to readers and tools. Python does not enforce those annotations at runtime. In `matgpt/data/prepare.py`, `make_document_record` calls `normalize_text(text)`, stores the returned value under `text`, and records `num_chars` with `len(normalized)`.

There is an important boundary beside this convenience. NFKC is a **deliberate cleaning policy**, not a neutral copy. It is **not lossless**: `①` can become `1`, collapsing a source distinction. Some inputs can also **change character count**, so the source cannot always be reconstructed exactly. That is a data-policy choice, not a learning step.

The verdict follows our trace. The data changed, was stored, and was counted; no model parameter changed. This is preparation on the representation side of the distinction. Now we can test the smaller fixed part of that representation in the repository's own lab.

## 09:00 Live Mini-Lab

[On screen: terminal beside `lab.py`.]

Open `course/videos/001-computer-learning-from-text/lab.py`. Before you run anything, predict both lists. For `Cat`, what will the character-number list be? What will the UTF-8 byte list be? We have enough evidence to predict `[67, 97, 116]` for each list, specifically because these are ASCII-range characters.

The lab is exactly this:

```python
text = "Cat"

print("Human text:", text)
print("Character numbers:", [ord(character) for character in text])
print("UTF-8 bytes:", list(text.encode("utf-8")))
print("Can the mathematical model use this raw Python string as numeric input? No")
print("Learning begins after text is represented as numbers.")
```

From the repository root, run:

```bash
python course/videos/001-computer-learning-from-text/lab.py
```

It prints:

```text
Human text: Cat
Character numbers: [67, 97, 116]
UTF-8 bytes: [67, 97, 116]
Can the mathematical model use this raw Python string as numeric input? No
Learning begins after text is represented as numbers.
```

Read the evidence line by line. `Human text` shows the string as we read it. The `ord` list visits each character and reports its code point. `encode("utf-8")` produces the UTF-8 bytes, and `list` displays those bytes as integers. The final two lines state the boundary: the raw Python string is not the mathematical model's numeric input, and this conversion is before learning.

Now change only `Cat` to `A`. Predict both lists before rerunning: each should be `[65]`. The result follows the same fixed agreement. It did not practice, measure an error, or improve because repeated conversion is fixed behavior. Restore `text = "Cat"` afterward so the checked lab and its documented output remain intact.

## 12:00 Test the Distinction

Let's test whether the building blocks are doing real work. Suppose a different context uses `A` as a grade instead of as part of a word. Did Unicode need to change `65`? No. Context changed the human interpretation; the fixed identifier did not. That is how you can distinguish identifier from meaning.

Now ask a second diagnostic question. Suppose we run `ord("A")` a thousand times. Which adjustable value changed because of a measured error? None. The answer does not depend on how often you run it. If a process only follows the representation agreement, it is not learning.

Turn the question around. If a model receives numeric examples, makes predictions, measures error, and then one of its parameters changes, which side of our distinction is that? Learning. The representation made numerical input possible; the parameter update supplied the missing capability. These are connected steps, but they are not the same action.

## 13:00 Rebuild the Complete Chain

Rebuild the whole chain in ordinary language. A person can read `Cat` with memories and context. Software first follows an agreement that gives `C`, `a`, and `t` stable numbers: `67`, `97`, and `116`. UTF-8 can store those ASCII-range characters as matching byte values. This numeric text representation changes text into a numerical form; it does not put human meaning inside the numbers.

Then a model can use numerical inputs to make predictions. Examples reveal how its predictions compare with outcomes. Measured error can change its parameters, and later predictions may improve. That is the durable distinction: representation changes data form; learning changes adjustable model values.

Try a transfer exercise. For `A`, predict `ord("A")` before checking it, then explain why `65` is stable without claiming it contains every meaning of `A`. Next ask: what specific parameter changed after measured error? If you cannot point to a changed adjustable value, you have evidence of representation or preparation, not evidence that learning occurred.

We will spend numeric text representation in Video 2, where the next question is how a computer assigns stable character numbers. Because the representation-learning distinction is already built, we can investigate that agreement without mistaking it for training.

**Deferred vocabulary boundary:** **token**, **tensor**, **logit**, **gradient**, **attention**, and **embedding** are future terms. They are not explanations used in this Video 1 narration.
