# Video 1 Answer Key: From a Sentence to a Training Example

## Answers

1. The input is The opposite of hot is, and the target is cold.
2. The first word has no earlier word before it, while each of the other five words can be the recorded next target.
3. No. The target is the continuation recorded in this training text; other continuations may also be sensible.
4. Words make the shift easy to inspect by hand. The same positional relationship is later applied to token IDs produced by the tokenizer.
5. x is [7, 20, 4, 2], and y is [20, 4, 2, 6].

## Gap Explanations

1. If the two parts are reversed, revisit Simple Explanation. The model receives the text before the cut and is evaluated against the recorded word after it.
2. If the answer is six, revisit Tiny Math Or Text Example and ask what input would exist before the first word.
3. If the answer says the target is uniquely correct, revisit Misconception. Training supplies an observed continuation, not proof that every alternative is wrong.
4. If the answer says words are the real model input, revisit Technical Meaning. Words are the visible example; the repository shifts token IDs.
5. If either row is unchanged, revisit Commented Repository Code. x drops the final ID; y drops the first ID.

## Misconception Correction

A shifted row is a compact arrangement of prediction positions. It does not remove the earlier context available at later positions, and it does not claim that the recorded target is the only possible continuation.
