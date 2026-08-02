# Video 1 — From a Sentence to a Training Example

**Subtitle:** How one sentence creates many small questions with answers already inside it

**Estimated runtime:** 11 minutes 50 seconds, including prediction pauses and code demonstrations

### Production Direction

- **Format:** Compose for 16:9. Keep essential text inside the center-safe area.
- **Creative intent:** Clear, precise, and warm. Every animation should help the learner trace how text becomes a training example.
- **Motion language:** Calm and sharp. Use `cubic-bezier(0.22, 1, 0.36, 1)` for entrances, a 0.4-second base duration, 60-millisecond staggers, and match cuts or short crossfades between shots. Avoid bounce, spins, and decorative motion.
- **Visual hierarchy:** Give each shot one hero. Supporting labels enter after the hero and then remain still.
- **Color roles:** Use the course palette, with one consistent cool color for **input** and one consistent warm color for **target**. Do not change those roles later.
- **Text treatment:** Show only the sentence, term, code line, or question currently being explained. Keep code and terminal text static long enough to read.
- **Audio treatment:** Prose under **Narration** is spoken. Fenced code, terminal output, and visual directions are on-screen references and are not read word for word.

## 00:00 The AI We Are Going to Build

### Visual / Animation

- **00:00–00:12:** Open on four clean interface cards: an email improvement, a paragraph rewrite, a document summary, and a code suggestion. Reveal them one at a time with short crossfades.
- **00:12–00:22:** Match-cut to one prompt field. A short line of text is typed on the left; new text appears on the right. Keep the typed text as the hero.
- **00:22–00:38:** Replace the interface with the centered title `Large Language Model`, then reveal `LLM` beneath it. Hold long enough to read both.
- **00:38–00:54:** Books, article cards, and simple website pages reduce into clean lines of text that join one stream. Highlight a few neighboring words to suggest recurring language patterns.
- **00:54–01:00:** The text stream simplifies into the single sentence used in the next shot. Match-cut to the missing-word exercise.

### Narration

You’ve probably seen AI improve an email, rewrite a paragraph, summarize a document, or suggest a piece of code.

In every case, you give it some text, and it gives you new text.

In this course, we’re going to build and train that kind of AI from scratch, one step at a time. The system has a name: a **large language model**, or **LLM** for short.

An LLM is trained on huge collections of text—books, websites, articles, and more. Across those examples, it learns patterns in written language. It learns which words tend to follow others, how ideas connect, and how questions and answers are usually expressed.

That’s a huge process. So let’s make it small enough to see. We’ll start with one sentence and one missing word.

## 01:00 A Sentence You Can Finish

### Visual / Animation

- **01:00–01:12:** Center `The opposite of hot is ___` on a quiet background. Let the blank pulse once, then hold for a two-second learner prediction.
- **01:12–01:18:** Type `cold` into the blank in the warm target color. Do not add a celebratory effect; a small color change is enough.
- **01:18–01:33:** Pull back slightly and place the label `Text so far` under the visible words and `What comes next?` under `cold`.
- **01:33–01:45:** Crossfade to the question `How can an LLM learn to continue writing?`
- **01:45–01:50:** Add the lesson objective beneath it: `Turn one sentence into training examples`.

### Narration

Try this: “The opposite of hot is...”

You probably said “cold.”

You didn’t calculate it or look it up. The next word felt likely because the pattern was already familiar.

That tiny moment is the simplest version of what we’ll train our LLM to do: see the text so far and predict what comes next.

So the course’s big question is: How can an LLM learn to continue writing?

We won’t answer all of that at once. First, we need to see how one sentence becomes practice material. By the end, you’ll build it by hand and with a few lines of Python.


## 01:50 The Answer Is Already in the Sentence

### Visual / Animation

- **01:50–02:04:** Return to the completed sentence and highlight `cold` as the familiar continuation.
- **02:04–02:18:** Show three faint copies of the same phrase passing behind the main sentence to represent repeated exposure. Keep the main sentence still.
- **02:18–02:30:** Cover `cold` with a simple rectangle, pause, and then reveal it again. This is the only moving element.
- **02:30–02:40:** Split the frame into two labeled areas: `Words the LLM sees` and `Next word to guess`. Move the sentence prefix into the first and `cold` into the second.

### Narration

To turn that sentence into practice, first look at where your answer came from.

You’ve seen and heard the pattern “the opposite of hot is cold” before. Repeated exposure made the continuation familiar.

But the really useful part is that nobody had to create a separate answer sheet. “Cold” was already in the sentence. We simply hid it.

So ordinary text can supply both sides of the practice: the words the LLM sees and the next word it must guess.

All we need is a consistent way to separate those two parts. Let’s do that by hand.

## 02:40 Make One Example by Hand

### Visual / Animation

- **02:40–02:52:** Lay out the six words as separate, evenly spaced word tiles.
- **02:52–03:05:** Draw a vertical cut immediately before `cold`. Keep the first five tiles in the cool input color and change `cold` to the warm target color.
- **03:05–03:20:** Add the labels `input` below the first five words and `target` below `cold`.
- **03:20–03:32:** Draw one bracket around the input and target together. Label the bracket `one training example`.
- **03:32–03:50:** Replace the bracket with six small word counters and the question `6 words = how many examples?` Hold for the learner’s prediction.

### Narration

Take the complete sentence, “The opposite of hot is cold,” and place a cut between “is” and “cold.”

```text
The opposite of hot is cold
The opposite of hot is | cold
```

Everything to the left of that cut is what the LLM sees. We’ll call that the **input**.

The single word on the right is what it must guess. We’ll call that the **target**.

```text
input:  The opposite of hot is
target: cold
```

Put the input and target together, and you have one **training example**.

Notice the full chain: the sentence gave us the input, the sentence gave us the target, and the cut told us which was which. Nothing was invented or manually labelled.

One cut gave us one example. But nothing says the cut has to stay there. This sentence has six words, so before we move it, how many training examples do you think we can make?

## 03:50 One Sentence, Five Examples

### Visual / Animation

- **03:50–04:25:** Move the cut from left to right. At each position, leave behind one new input-and-target row. Use the same input and target colors in every row.
- **04:25–04:38:** Stack the five completed rows and count them from `1` to `5`.
- **04:38–04:53:** Reduce the rows into the formula `number of examples = number of words - 1`. Highlight the `- 1`, then point back to the first word.
- **04:53–05:10:** Scale from six word tiles to a compact block marked `100 words`, then reveal `99 examples`. Keep the quantities static after they land.

### Narration

If you guessed five, here’s why.

Move the cut from left to right. Each time it moves, the input grows by one word, and the word immediately after the cut becomes the new target.

```text
The                         -> opposite
The opposite                -> of
The opposite of             -> hot
The opposite of hot         -> is
The opposite of hot is      -> cold

```

By the time we reach “cold,” we’ve made five training examples from one six-word sentence.

In this simplified setup, the pattern is: number of examples equals number of words minus one.

```text
number of examples = number of words - 1
```

Why minus one? Because the first word has nothing before it to use as an input. Every word after it can take a turn as the target.

And this grows quickly. A passage with one hundred words can supply ninety-nine next-word examples without someone writing ninety-nine separate answers.

Five cuts are easy to make by hand. Millions are not. But the rule never changes—and repeating a clear rule is exactly what code is good at.

## 05:10 Build the Examples in Python

### Visual / Animation

- **05:10–05:25:** Match-cut from the formula to a code editor titled `training_examples.py`. Reveal the complete code without typing every character.
- **05:25–05:45:** Highlight `sentence.split()`. Animate the sentence once into six word tiles beside the code.
- **05:45–06:00:** Highlight the three `print` lines together, then show their three output lines in a small terminal panel.
- **06:00–06:30:** Step through the loop. Move a `position` marker from `1` to `5`; grow the cool input slice and advance the warm target one word each time.
- **06:30–06:42:** Hold on `words[:position]` and `words[position]` with matching color underlines that connect them to input and target.
- **06:42–06:50:** Show `How many example lines?` and hold without revealing the answer.

### Narration

So let’s ask Python to repeat the cuts for us.

We’ll put the sentence in a small file called `training_examples.py`. When the code calls `split`, the sentence becomes a list of six words.

```python
sentence = "The opposite of hot is cold"
words = sentence.split()

print("Sentence:", sentence)
print("Words:", words)
print("Number of words:", len(words))
print()

for position in range(1, len(words)):
    print(words[:position], "->", words[position])
```

Then the loop starts at position one. Starting at zero would give us no words before the target, so position one is the first useful cut.

At each position, the slice before it becomes the input, and the word at that position becomes the target. The loop moves once, prints the pair, and repeats.

That’s the same process we just did by hand. The code is only making it faster.

And once again, both parts come from the same list. There’s still no separate answer sheet.

Before we run it, hold onto your prediction: how many example lines should it print?

This loop shows each input growing from left to right. There’s also a more compact way to show the same relationship—one that lines every word up with the word that follows it.

## 06:50 The Same Sequence, Shifted One Place

### Visual / Animation

- **06:50–07:02:** Place the six word tiles in one centered row.
- **07:02–07:20:** Duplicate the row. Remove `cold` from the upper row and `The` from the lower row, then slide the lower row left by one word position.
- **07:20–07:35:** Label the upper row `inputs` in the cool color and the lower row `targets` in the warm color. Draw thin vertical guides between aligned words.
- **07:35–07:52:** Match-cut to `shifted_targets.py`. Highlight `words[:-1]`, then `words[1:]`, while the corresponding row lights up.
- **07:52–08:05:** Highlight `zip(inputs, targets)` and draw the five one-to-one connections in a 60-millisecond cascade.
- **08:05–08:20:** Dim the middle words. Hold on `The` and `cold` with the question `Which appears in only one list?`

### Narration

Start with the same six words and make two rows.

```text
The  opposite  of  hot  is  cold
```

In the first row, remove the last word. That gives us the inputs. In the second row, remove the first word. That gives us the targets.

```text
inputs:   The  opposite  of   hot  is
targets:       opposite  of   hot  is   cold
```

Now the second row sits one position ahead of the first. Each input word lines up with the word that comes next.

The file `shifted_targets.py` does exactly that. The first slice keeps every word except the last. The second keeps every word except the first. Then `zip` walks through both rows together and pairs the aligned words.

```python
words = "The opposite of hot is cold".split()

inputs = words[:-1]
targets = words[1:]

print("inputs :", inputs)
print("targets:", targets)
print()

for input_word, target_word in zip(inputs, targets):
    print(input_word, "->", target_word)
```

This isn’t a different task. It’s the same next-word relationship, arranged so we can see every position at once. Later, we’ll use this same shift with longer numeric sequences.

Before we run either program, make one more prediction. Which word will appear only in the inputs, and which will appear only in the targets?

## 08:20 Run, Observe, and Explain

### Visual / Animation

- **08:20–08:35:** Open a full-width terminal beside a narrow code panel. Keep the text large enough to read at normal video size.
- **08:35–09:00:** Enter `python training_examples.py`. Reveal the output one row at a time, synchronized with a five-step counter.
- **09:00–09:10:** Hold on `6 words` and `5 examples`; connect them with the `n - 1` formula.
- **09:10–09:40:** Enter `python shifted_targets.py`. Reveal the input row first, then slide in the target row one position later.
- **09:40–09:55:** Highlight `The` only in inputs and `cold` only in targets. Keep all middle words neutral.
- **09:55–10:05:** Edit only the sentence string to `the sun rises in the east`; leave the program unchanged.
- **10:05–10:10:** Show `Your prediction: ___ examples` and hold before moving on.

### Narration

Let’s test both predictions.

Run `training_examples.py`, and we get exactly five lines: six words, five possible cuts, five training examples.

```bash
python training_examples.py
```

```text
Sentence: The opposite of hot is cold
Words: ['The', 'opposite', 'of', 'hot', 'is', 'cold']
Number of words: 6

['The'] -> opposite
['The', 'opposite'] -> of
['The', 'opposite', 'of'] -> hot
['The', 'opposite', 'of', 'hot'] -> is
['The', 'opposite', 'of', 'hot', 'is'] -> cold
```

Then run `shifted_targets.py`. The same words appear in both rows, but the target row starts one position later.

```bash
python shifted_targets.py
```

```text
inputs : ['The', 'opposite', 'of', 'hot', 'is']
targets: ['opposite', 'of', 'hot', 'is', 'cold']

The -> opposite
opposite -> of
of -> hot
hot -> is
is -> cold
```

That leaves “The” only in the inputs, because nothing comes before it. And it leaves “cold” only in the targets, because nothing comes after it.

So far, the rule works for one sentence. But did we understand the rule, or did we just memorize this example?

Change only the sentence to “The sun rises in the east.” Don’t run it yet. Count the words and make your prediction.

```text
the sun rises in the east
```

It also has six words, so our rule says it should produce five examples. Run it, and that’s exactly what happens. The sentence changed; the rule didn’t.

At this point, we can say clearly what the task does. And that makes it easier to separate it from three things it does not do.

## 10:10 Three Easy Mistakes

### Visual / Animation

- **10:10–10:23:** Show a separate answer sheet beside the sentence, then cross out the answer sheet and reveal the target inside the sentence.
- **10:23–10:37:** Show `1 example`, then expand it into the five input-and-target rows and replace the label with `5 examples`.
- **10:37–10:51:** Place `meaning`, `summary`, and `truth` around the target. Fade each one out as it is rejected.
- **10:51–11:00:** Leave only `target = the next recorded word` centered on screen.

### Narration

First, nobody prepared a separate answer sheet. For this task, the next word was already in the text.

Second, one sentence did not give us only one example. Our six-word sentence gave us five because we could place the cut in five useful positions.

And third, the target was not the sentence’s meaning, summary, or truth. It was simply the next word in the recorded text.

That’s a narrow task, but it gives us a precise way to practise prediction. And once those three distinctions are clear, the whole lesson fits into one short chain.

## 11:00 The Mental Model

### Visual / Animation

- **11:00–11:28:** Build the causal chain one node at a time: `sentence` → `choose a cut` → `input` → `target` → `training example`. Land each arrow only after its source is visible.
- **11:28–11:37:** Place the original six-word sentence above the completed chain and show the five resulting examples beneath it.
- **11:37–11:44:** Clear the frame and hold the closing mental model: `Show the text so far. Predict what comes next.`
- **11:44–11:50:** Pull back to reveal a simple three-step course path: `training examples` → `learning system` → `measuring improvement`. End on the course title.

### Narration

Start with a sentence and choose a cut. The words before it are the input. The next word is the target. Together, they form one training example.

```text
sentence
  -> choose a cut
  -> words before the cut = input
  -> next word            = target
  -> input + target       = one training example
```

Move the cut, and the same sentence gives you another example. That’s how six words gave us five examples without a separate answer sheet.

Remember this: **show the text so far, then predict what comes next**.

We now have the first building block of language-model training. That leads to our next question: what system can learn from millions of these examples, what hardware will it need, and how will we know when it’s improving?
