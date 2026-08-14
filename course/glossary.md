# Course Glossary

Read the simple meaning first. Use the technical meaning when the mechanism is comfortable. A term's first video is where its mechanism is taught, not merely where a boundary note may mention its name.

## Text

**Simple meaning:** Written material, such as a sentence, article, or program.

**Technical meaning:** Recorded symbols that later pipeline stages represent and divide into model-readable units.

**First video:** Video 1

## Input

**Simple meaning:** The information shown to the model before it makes a prediction.

**Technical meaning:** The sequence positions made available to the model for a training or inference calculation.

**First video:** Video 1

## Target

**Simple meaning:** The recorded next piece used to check a prediction.

**Technical meaning:** The observed value aligned with a model output for the training objective. It is not necessarily the only acceptable continuation.

**First video:** Video 1

## Training Example

**Simple meaning:** One practice question together with the recorded value used to check it.

**Technical meaning:** An input paired with a target for one evaluation term in the training objective.

**First video:** Video 1

## Prediction Position

**Simple meaning:** One place where the model is asked what comes next.

**Technical meaning:** A sequence index whose model output is compared with the aligned next-piece target.

**First video:** Video 1

## Shifted Targets

**Simple meaning:** A copy of a sequence moved by one place so each input lines up with what followed it.

**Technical meaning:** For a window `w`, the repository forms `x = w[:-1]` and `y = w[1:]`, producing equal-length input and target rows.

**First video:** Video 1

## Model

**Simple meaning:** A number-based system that makes predictions.

**Technical meaning:** A mathematical function with adjustable parameters that maps input values to output scores or predictions.

**First video:** Video 2

## Learning

**Simple meaning:** Changing a model so its predictions improve on the training task.

**Technical meaning:** Updating model parameters using measured error from training examples.

**First video:** Video 2 for the course map; Video 20 for the complete mechanism

## Character

**Simple meaning:** One written item, such as a letter, digit, space, or punctuation mark.

**Technical meaning:** An abstract unit in a writing system that can be assigned a standard number.

**First video:** Video 4

## Number Representation

**Simple meaning:** An agreed way to use numbers to stand for something else.

**Technical meaning:** A mapping between information and numeric values that a program can store and process.

**First video:** Video 4

## Unicode

**Simple meaning:** A shared character list used by computer systems around the world.

**Technical meaning:** A standard that assigns each defined character a unique number called a code point.

**First video:** Video 5

## UTF-8

**Simple meaning:** A widely used rule for storing Unicode text as bytes.

**Technical meaning:** A variable-length encoding that represents a Unicode code point with one to four bytes.

**First video:** Video 5

## Token

**Simple meaning:** One piece produced when the tokenizer divides text.

**Technical meaning:** A vocabulary unit represented by one token ID. It may be a whole word, part of a word, punctuation, whitespace, or another learned unit.

**First video:** Video 8

## Token ID

**Simple meaning:** The agreed vocabulary number for one token.

**Technical meaning:** An integer index used to select and process a token inside the model pipeline.

**First video:** Video 8

## Pattern

**Simple meaning:** A repeated relationship that can make one continuation more likely than another.

**Technical meaning:** A statistical regularity learned from data and represented by model parameters.

**First video:** Video 24
