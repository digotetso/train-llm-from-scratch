# Video 1 — What Does It Mean for a Computer to Learn From Text?

**Subtitle:** How software identifies characters with fixed numbers, and what has to change before we can call anything learning

## 00:00 The Question Behind This Course

You have probably seen software rewrite an email, answer a question, or suggest a line of code. You enter words, and useful new words appear.

In this course we are going to build that kind of software ourselves, one step at a time. That gives us a large question to answer:

> **How can software learn from written examples?**

It is tempting to skip ahead to the answer. Today we are going to slow down and ask something smaller and sharper:

> **What does the word learn actually mean here, and what does it not mean?**

This matters more than it might seem. Almost every confusing thing you will read about this topic comes from mixing up two very different steps.

One step turns writing into numbers. The other step changes numbers in response to mistakes.

They look similar from the outside. They are not the same, and only one of them is learning.

By the end of this lesson you will be able to tell them apart using three letters, one number that never changes, and one number that does.

## 01:15 What You Bring That Software Does Not

[On screen: the word `cat`]

Read this word: `cat`.

You may have pictured an animal. You may have remembered a specific animal you know. Perhaps you heard the word in your head.

None of that arrived with the letters. You brought it. It came from your life outside this screen.

Now think about what a program receives when the same word arrives. It gets three characters, one after another, and nothing else.

There is no picture, no memory, and no sound attached. So before software can learn anything at all from writing, it needs something more basic.

It needs a dependable way to tell one character apart from another.

That sounds almost too simple to be worth a step. But everything later in this course rests on it, so let us make sure it is solid.

Here is a question to hold on to while we look:

> When software answers the same question many times, should the answer ever improve?

## 02:30 How Can Software Tell One Character From Another?

Look at the letter `A`. You recognise it instantly. Software still needs a dependable way to separate it from `B`, from `a`, and from every other character.

Before we name the rule, make a prediction. Does Python invent a new number for `A` each time it looks, or follow a number fixed by an agreed standard?

Hold your answer.

Unicode is a character-numbering standard. In our examples, each character has a fixed number called a **code point**.

Python already has a function that reports the code point for a one-character string. It is named `ord`.

```python
ord("A")
```

Python reports:

```text
65
```

That number identifies `A`. It does not explain what `A` means.

The letter `A` might be a grade on an essay, a musical note, or a blood type. Its code point stays `65` in every one of those situations.

Now trace the word `Cat`, one character at a time:

```text
C -> 67
a -> 97
t -> 116
```

So the three numbers are:

```text
[67, 97, 116]
```

Notice that we asked three separate questions and received three separate answers. `ord` works with one character at a time, which is why we traced `Cat` letter by letter.

We now have a dependable way to identify characters. The next question is whether that ability, on its own, is worth calling learning.

## 04:30 A Fixed Rule Never Gets Better

Let us put the question to a test we can run.

Create a file named `character_numbers.py` and place this complete example inside it:

```python
text = "Cat"
print("Text:", text)
print("Character numbers:", [ord(character) for character in text])

print()

print("Reading the same letter five times:")
for attempt in range(1, 6):
    print("attempt", attempt, "->", ord("A"))
```

The first part reports the three numbers for `Cat`. The second part asks Python for the same letter five times in a row.

Before you run it, predict the five answers. Will the fifth attempt be better than the first?

Open a terminal in the folder containing the file, then run:

```bash
python character_numbers.py
```

The program prints:

```text
Text: Cat
Character numbers: [67, 97, 116]

Reading the same letter five times:
attempt 1 -> 65
attempt 2 -> 65
attempt 3 -> 65
attempt 4 -> 65
attempt 5 -> 65
```

Five attempts. One answer, repeated exactly.

This is worth pausing on. Practice did nothing here. The fifth answer is not sharper than the first, because `ord` has nothing inside it that could change.

It follows an agreement, and an agreement that drifted would be broken rather than improved.

Picture what a drifting agreement would cost. You save a file today and open it again next year. You send it to someone whose software was written by strangers on another continent.

If the number for `A` had quietly improved in the meantime, the writing would arrive damaged. Staying the same is not a limitation here. It is the entire point.

So turning text into numbers is real and necessary work. It is simply not learning.

## 06:30 What Would Getting Better Even Mean?

If a fixed rule cannot learn, what would we need to add?

Three things, and we can name all of them in plain language first.

We need something adjustable, so there is something to change. We need a way to be wrong, so we can tell whether a change helped. We need a rule for changing, so the adjustment is not random.

Let us build the smallest possible example that has all three.

Here are our written examples:

```text
cat sat
cat ran
cat slept
```

We will ask a deliberately small question about them: how long is a line?

Be clear about what this is. Later in the course, the thing being predicted will be the next piece of writing, which is far more interesting.

Today we want the mechanism visible, so we keep the question tiny enough to check by hand.

Our adjustable thing will be a single number, and we will call it the guess. It starts at zero, which is badly wrong on purpose.

Our way of being wrong is the difference between the true length and the guess. We will call that the error.

Our rule for changing is to move the guess a small part of the way toward the truth, again and again.

Before we run anything, predict. If the guess starts at zero and the lines are seven, seven, and nine characters long, which direction should the guess move?

## 08:30 Watch One Number Change

Create a second file named `first_learning.py` with this complete example:

```python
examples = ["cat sat", "cat ran", "cat slept"]

guess = 0.0
step = 0.1

for round_number in range(1, 6):
    total_error = 0.0
    for example in examples:
        error = len(example) - guess
        guess = guess + step * error
        total_error = total_error + abs(error)
    print("round", round_number, "guess", round(guess, 2), "total error", round(total_error, 2))
```

Let us follow it from the top.

The first line holds our three written examples. Then `guess` starts at zero, and `step` is set to one tenth.

The outer loop repeats the whole exercise five times. Each repetition is a round.

Inside a round, we visit every example. For each one, `len(example)` gives the true length, and `error` is how far the guess sits from that truth.

Now look at the line that does the actual work:

```python
guess = guess + step * error
```

This moves the guess one tenth of the way toward the truth. Not all the way, which would make it lurch after every example, and not nowhere.

Why move only part of the way, instead of jumping straight to the true length? Because each example is a single piece of evidence. We want the guess to settle near what all three examples suggest, not to lurch toward whichever one it saw last.

The last line adds up how wrong we were across the round, using `abs` so that being too low and being too high both count as error.

Notice what is missing. Nothing in this file describes cats, or sitting, or running. We never wrote down the answer. The examples are the only source.

## 10:30 Predict, Run, and Explain

Before you run it, write down two predictions. Will the guess rise or fall across the rounds? Will the total error rise or fall?

Run:

```bash
python first_learning.py
```

The program prints:

```text
round 1 guess 2.1 total error 20.97
round 2 guess 3.63 total error 15.29
round 3 guess 4.74 total error 11.14
round 4 guess 5.55 total error 8.12
round 5 guess 6.14 total error 5.92
```

Read the two columns separately.

The guess climbs from `2.1` to `6.14`. The total error falls from `20.97` to `5.92`.

Now compare that with the run before. `ord` gave five identical answers. This file gave five different ones, and each was less wrong than the last.

That difference is the whole lesson.

Let us also be honest about where it landed. Our three lines are seven, seven, and nine characters long, so their average is about `7.67`.

After five rounds the guess is `6.14`, which is not there yet. It is closer than it was, and it would keep closing with more rounds.

Getting less wrong is not the same as being finished, and that will stay true for the rest of this course.

Now change one thing. Set `step` to `0.5` instead of `0.1`.

Predict before you run. A larger step moves further each time, so the guess should climb faster. Watch where it finishes, and compare that with the average of `7.67`.

Run the file again. The final guess is `8.14`, which has gone past the average rather than settling on it.

That is the lurching we were trying to avoid. With a large step, whichever example comes last in a round pulls the guess hard toward itself, and the last one here is the longest line.

So a bigger step is not simply faster. It trades steadiness for speed, and we will meet that trade again later. Restore `step` to `0.1`.

Finally, change the examples. Replace `cat slept` with `cat`, which is much shorter, and predict which direction the final guess should move.

Run, compare, and explain what you see. Then restore `cat slept`.

You have now used the same pattern twice: predict the result, run it, and check whether your explanation survives a changed input.

## 13:00 Two Ideas That Are Easy to Confuse

Two mistakes are worth naming, because both are common and both sound reasonable.

The first is saying that `65` is the meaning of `A`. It is not. It identifies the character under an agreement, while the meaning shifts with context and the number does not.

The second is saying that turning text into numbers is learning. It is not. We watched `ord` answer five times without improving, because it has nothing inside it to adjust.

Now we can name the two ideas properly.

**Representation** turns writing into numbers by following fixed agreements. It is dependable precisely because it never changes.

**Learning** changes adjustable numbers in response to measured error. Those adjustable numbers have a name: they are called **parameters**.

A system with parameters that are adjusted this way is called a **model**.

## 14:00 What We Can Now Explain

We began with a large question about how software learns from written examples. Today we answered a smaller one.

Here is the idea to carry forward:

```text
character -> code point -> a fixed number that identifies
examples + error + a rule for changing -> parameters that adjust
```

Our first file gave the same answer five times and improved nothing. Our second file gave a different answer every round, and each one was less wrong.

Both files were working with writing. Only the second one was learning.

So when you hear that a system learned from text, you now have a precise question to ask. What was adjustable, how was the error measured, and what changed as a result?

One thing is still missing. Our second file learned the length of a line, which no one actually wants.

Video 2 fixes that. We will turn a sentence into a learning example, so the thing being predicted is the writing itself.
