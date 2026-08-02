# Video 1 — From a Sentence to a Training Example

**Narration-only recording script**

The headings and timestamps are silent recording landmarks. They match the production script and include time for predictions, code, terminal output, and other on-screen demonstrations.

## 00:00 The AI We Are Going to Build

You’ve probably seen AI improve an email, rewrite a paragraph, summarize a document, or suggest a piece of code.

In most cases, you give it some text, and it gives you new text.

In this course, we’re going to build and train that kind of AI from scratch, one step at a time. The system has a name: a large language model, or LLM for short.

An LLM is trained on huge collections of text—books, websites, articles, and more. Across those examples, it learns patterns in written language. It learns which words tend to follow others, how ideas connect, and how questions and answers are usually expressed.

That’s a huge process. So let’s make it small enough to see. We’ll start with one sentence and one missing word.

## 01:00 A Sentence You Can Finish

Try this: “The opposite of hot is...”

You probably said “cold.”

You didn’t calculate it or look it up. The next word felt likely because the pattern was already familiar.

That tiny moment is the simplest version of what we’ll train our LLM to do: given these words so far, predict what comes next.

So the course’s big question is: How can an LLM learn to continue writing?

We won’t answer all of that at once. First, we need to see how one sentence becomes practice material. By the end, you’ll build it by hand and with a few lines of Python.

## 01:50 The Answer Is Already in the Sentence

To turn that sentence into training data, first look at where your answer came from.

You’ve seen and heard the pattern “the opposite of hot is cold” before. Repeated exposure made the continuation familiar.

But the really useful part is that nobody had to create a separate answer sheet. “Cold” was already in the sentence. We simply hid it.

So ordinary text can supply both sides of the training data: the words the LLM sees and the next word it must guess.

All we need is a consistent way to separate those two parts. Let’s do that by hand.

## 02:40 Make One Example by Hand

Take the complete sentence, “The opposite of hot is cold,” and place a cut between “is” and “cold.”

Everything to the left of that cut is what the LLM sees. We’ll call that the input.

The single word on the right is what it must guess. We’ll call that the target.

Put the input and target together, and you have one training example.

Notice the full chain: the sentence gave us the input, the sentence gave us the target, and the cut told us which was which. Nothing was invented or manually labelled.

One cut gave us one example. But nothing says the cut has to stay there. This sentence has six words, so before we move it, how many training examples do you think we can make?

## 03:50 One Sentence, Five Examples

If you predicted five, here’s why.

Move the cut from left to right. Each time it moves, the input grows by one word, and the word immediately after the cut becomes the new target.

By the time we reach “cold,” we’ve made five training examples from one six-word sentence.

In this simplified setup, the pattern is: number of examples equals number of words minus one.

Why minus one? Because the first word has nothing before it to use as an input. Every word after it can take a turn as the target.

And this grows quickly. A passage with one hundred words can supply ninety-nine next-word examples without someone writing ninety-nine separate answers.

Five cuts are easy to make by hand. Millions are not. But the rule never changes—and repeating a clear rule is exactly what code is good at.

## 05:10 Build the Examples in Python

So let’s ask Python to repeat the cuts for us.

We’ll put the sentence in a small file called `training_examples.py`. When the code calls `split`, the sentence becomes a list of six words.

Then the loop starts at position one. Starting at zero would give us no words before the target, so position one is the first useful cut.

At each position, the slice before it becomes the input, and the word at that position becomes the target. The loop moves once, prints the pair, and repeats.

That’s the same process we just did by hand. The code is only making it faster.

And once again, both parts come from the same list. There’s still no separate answer sheet.

Before we run it, hold onto your prediction: how many example lines should it print?

This loop shows each input growing from left to right. There’s also a more compact way to show the same relationship—one that lines up every word with the word that follows it.

## 06:50 The Same Sequence, Shifted One Place

Start with the same six words and make two rows.

In the first row, remove the last word. That gives us the inputs. In the second row, remove the first word. That gives us the targets.

Now the second row sits one position ahead of the first. Each input word lines up with the word that comes next.

The file `shifted_targets.py` does exactly that. The first slice keeps every word except the last. The second keeps every word except the first. Then `zip` walks through both rows together and pairs the aligned words.

This isn’t a different task. It’s the same next-word relationship, arranged so we can see every position at once. Later, we’ll use this same shift with longer numeric sequences.

Before we run either program, make one more prediction. Which word will appear only in the inputs, and which will appear only in the targets?

## 08:20 Run, Observe, and Explain

Let’s test both predictions.

Run `training_examples.py`, and we get exactly five lines: six words, five possible cuts, five training examples.

Then run `shifted_targets.py`. The same words appear in both rows, but the target row starts one position later.

That leaves “The” only in the inputs, because nothing comes before it. And it leaves “cold” only in the targets, because nothing comes after it.

So far, the rule works for one sentence. But did we understand the rule, or did we just memorize this example?

Change only the sentence to “The sun rises in the east.” Don’t run it yet. Count the words and make your prediction.

It also has six words, so our rule says it should produce five examples. Run it, and that’s exactly what happens. The sentence changed; the rule didn’t.

At this point, we can see clearly how training examples are created

## 10:10 Keypoints 

There two keypoints , that you need to underscore 
 
First, nobody prepared a separate answer sheet. The next word or target was already in the text.

Second, one sentence did not give us only one example. Our six-word sentence gave us five because we could place the cut in five useful positions.


## 11:00 The Mental Model

Start with a sentence and choose a cut. The words before it are the input. The next word is the target. Together, they form one training example.

Move the cut, and the same sentence gives you another example. That’s how six words gave us five examples without a separate answer sheet.

Thats it, this how LLM training examples are created

We now have the first building block of language-model training. That leads to our next question: what system can learn from millions of these examples, what hardware will it need, and how will we know when it’s improving?
