# Video 1 — Script 4: What Does It Mean for a Computer to Learn From Text?

## 00:00 The Result and the Question

You may already have seen an AI clarify an email, improve an essay sentence, or suggest a piece of code. The result can feel immediate: you write words, and useful new words appear. But that experience leaves a fair question unanswered. How can a system improve at tasks like these from written examples?

Language models can learn from many text examples. In practice, that collection is often very large, but large scale is not the definition of learning. The important idea is that examples give the system something to work from and something to improve against. We have experienced the useful output; that does not mean we have yet seen the machinery that produces it.

So let's begin this course with a map. It will show the whole journey from training text to repeated improvement. Then, instead of pretending that a quick tour makes every stop familiar, we will open one first step completely. By the end of this video, you will know why written text must take a numerical form before the later mathematical work can begin.

## 00:50 The Whole Journey in One Map

Here is the route. Read each arrow as a dependency: one stage supplies something the next stage needs. This is not a recipe you must memorize today. It is a promise about where our questions will lead.

```text
Training text
-> reusable text pieces [token]
-> one identifier per piece [token ID]
-> use the ID to select a learned number list [embedding]
-> model calculations
-> prediction
-> compare with the known training target
-> measured error
-> closed update method
-> changed parameters
-> repeat across examples
```

Start with training text: written examples provide the material for the journey. A later dividing rule turns that material into reusable text pieces; we call each resulting piece a token. Each defined piece receives one identifier, a token ID. That identifier lets the system select a learned number list, called an embedding. The learned list can then enter a mathematical system that makes an answer using internal numbers that can change; we call that system the model, and its work model calculations.

The system makes a numerical answer for the current training task; we call that answer a prediction. We compare that answer with the known training target already supplied by the example, which gives us a measured error: a number that says how far apart they are. A later process uses that information to change the model's adjustable internal numbers, its parameters; that process is the update method. Repeating that process across examples can make later answers less wrong.

Notice the discipline of this map. Each label gives us a job and a name, not the mechanism hiding inside it. `Cat` could enter as a label at the left of this route, but we will not make up a dividing rule, an identifier, a learned list, or a numerical answer for it. The arrows show dependency order, and any one arrow can hide a whole later lesson.

## 03:00 Close the Boxes We Have Not Opened

Being able to locate a labeled box is different from understanding how the box works. We can point to the dividing rule that produces tokens, but we have not learned that rule. We can point to token IDs and embeddings, but we have not learned how identifiers are assigned or how learned number lists are selected. We can point to model calculations, prediction math, target comparison, measured error, and the update method, but their mechanisms remain closed for now.

One distinction matters immediately because it keeps the route honest: token -> token ID -> use the ID to select an embedding. A token ID is an integer identifier. It tells the system which learned number list to select. A token ID does not become an embedding, and it is not represented by an embedding. These are different numerical objects with different jobs.

We will return to the dividing rule and token IDs in Video 11, to learned number lists in Video 23, and to prediction, comparison, measured error, and controlled updates in Videos 37-40. For now, those boxes stay closed. That restraint gives us one question we can truly open today: why must written text receive a numerical form before any later mathematical box can use it?

## 04:00 Why Text Needs a Numerical Form

Put one written `A` before a program. Before we check, make a prediction: does `ord("A")` invent a number for this `A`, or does it follow a stable agreement that software follows? It follows the agreement. In Python, `ord("A") == 65`.

What did we just observe? We gave the program one written item and it returned the agreed number for that item. The written item is a character. Unicode is the shared standard that defines characters and agreed numbers. The number assigned to a character by that standard is called its code point. So `65` is the code point for `A`; `ord` did not discover or create a new meaning for it.

That last part matters. `65` stays fixed while `A` can mean a grade on a report, a musical note, a blood type, or part of a name. The number identifies the written character under an agreement. It does not carry the human meaning that the character takes from its context.

Let's check that this is a repeatable rule rather than a fact to memorize about one letter. Trace `Cat` by hand: `C -> 67`, `a -> 97`, and `t -> 116`. Each character has its own code point, so the character-number list is `[67, 97, 116]`. Inspect each step: text becomes characters, and each character follows the stable Unicode agreement to one number.

There is one more storage step worth separating from that trace. A byte is a stored number from 0 through 255. UTF-8 is a common rule for storing Unicode text as one or more bytes. Before we reveal the bytes for `Cat`, predict whether its byte list will be `[67, 97, 116]`. It will: these characters are in the ASCII range, where UTF-8 uses one byte with the same value for each of them. That is a useful match, not a universal rule; other characters can need more than one UTF-8 byte.

We have earned a name for this fixed conversion. Text representation changes text into a numerical form that software can store and process. This is an early representation layer: it is not a token ID or an embedding, and it is not yet the model's precise numerical input. Those remain later boxes on our map. What we do know is why those later number-based boxes cannot begin with raw writing.

## 06:30 Representation Is Not Learning

Now ask a sharper question: during the character and byte conversions, what changed, and what stayed fixed? The form changed from written characters to code points and then to stored bytes. The Unicode and UTF-8 rules stayed fixed. Nothing practiced, compared an answer with an example, or adjusted itself. So representation cannot by itself be learning.

Look back at the still-closed part of our roadmap. Learning needs a chain we have only named: model answer -> known target -> measured error -> closed update method -> changed parameters -> later answer. For today's distinction, we need only two labels from that chain. A model is the mathematical system that makes the answer. Its parameters are the adjustable internal numbers that the closed update method can change; a later answer can therefore differ from an earlier one.

Here is a tiny picture of possible improvement. Imagine ten comparable answers with seven mistakes. After an update, imagine ten comparable answers with five mistakes. The move from seven to five is a way to picture an update making these answers less wrong. It is not the repository's training calculation, and it cannot prove performance on unseen examples. Separate examples still matter when we want to know whether improvement carries beyond the examples used for adjustment.

That gives us two compact rules we can reuse. Representation changes the form of the data. Learning changes adjustable model parameters using examples and measured error. The character and byte trace belongs to the first rule; the map's answer, target, error, and closed update chain belongs to the second.

We can now spend that distinction on a concrete repository question. When `normalize_text` makes source text consistent, which side does it belong to: representation or learning? Keep that prediction in mind as we open the repository's preparation step next.

## 08:00 Apply the Distinction to the Repository

Here is the function. As you read it, keep our question narrow: does `normalize_text` change data, model parameters, or both?

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

Trace the data from top to bottom. First, `str(text)` produces a string, and NFKC normalization makes selected Unicode forms consistent. Newline replacement then turns two newline styles into `\n`, while `_CONTROL_RE` removes selected control characters. Next, the list step removes trailing whitespace from each line; joining rebuilds the lines, and `strip` removes outer whitespace. Finally, `_BLANK_LINES_RE` limits a run of blank lines to one blank line, and the function returns the prepared text.

NFKC is deliberate and not lossless. For example, `①` can become `1`. A distinction present in the source can collapse, and character count can change. That is a preparation policy, not a neutral copy.

The annotation `text: str` communicates the intended input type, and `-> str` communicates the intended return type. Python does not automatically enforce those annotations at runtime. In fact, the first operation explicitly calls `str`.

The preparation code then uses the result:

```python
normalized = normalize_text(text)
"text": normalized,
"num_chars": len(normalized),
```

The stored text and its measured length therefore describe the normalized result. Our prediction can now be precise: this is preparation on the text-representation side. The data changed, but no measured error changed a model parameter.

## 10:30 Predict, Run, and Explain

Now use a tiny program to test the representation rule:

```python
text = "Cat"

print("Human text:", text)
print("Character numbers:", [ord(character) for character in text])
print("UTF-8 bytes:", list(text.encode("utf-8")))
print("Can the mathematical model use this raw Python string as numeric input? No")
print("Learning begins after text is represented as numbers.")
```

Before running it, predict both lists for `Cat`: the character-number list and the UTF-8 byte list. Then run:

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

Line by line, `ord` follows the Unicode agreement from each character to its code point. `encode("utf-8")` converts the string into stored bytes according to UTF-8. `list` exposes those byte values so we can compare them. For these three characters, the values match; that match is not guaranteed for every character.

Change only `"Cat"` to `"A"`. Predict again before running: the code-point list should be `[65]`, and the UTF-8 byte list should also be `[65]`. Rerun the same command, observe the two lists, and explain them with the same fixed agreements. Then restore `"Cat"`. This predict-run-observe-explain-change-predict-compare loop tests the rule rather than your memory of one output.

These character numbers are not token IDs or embeddings. We have proved an early representation step, so we return to the map without opening those later boxes.

## 13:00 Return to the Whole Map

Here is the whole route in ordinary language. Training text is divided into reusable pieces. Each piece receives an identifier that selects a learned number list. Model calculations use those lists to make an answer. The answer is compared with the known target to measure error. A closed update method uses that information to change adjustable parameters, and the process repeats across examples.

The exact path we earned today is: written character -> stable code point -> stored UTF-8 bytes -> prepared numerical data. The later boxes now have a valid input dependency, but their mechanisms remain closed.

Keep the dividing line: Representation changes the form of the data. Learning changes adjustable model parameters using examples and measured error.

Try one transfer exercise. Classify each action before checking your reasoning: applying a fixed rule that turns a newline style into `\n`; using examples and measured error to change an adjustable parameter. The first is representation and preparation because it changes data under a fixed rule. The second is learning because it changes adjustable model state through the learning chain.

We can now ask Video 2's question without pretending text is already numeric: how can software use stable character numbers to build a dependable character set?
