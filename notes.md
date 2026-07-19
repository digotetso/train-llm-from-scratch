

# Lesson 1: What Does It Mean For A Computer To Learn From Text?
# #1 NORMILIZATION

```python
# This file prepares raw text so it is cleaner and more consistent.
[matgpt/data/normalize.py (line 1)](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/data/normalize.py:1).

import re
import unicodedata

# This pattern finds invisible control characters.
# These are characters that may exist in text files but do not look like normal letters.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# This pattern finds 3 or more blank lines in a row.
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    # Convert the input into a string and standardize Unicode.
    # Example: the full-width character "Ａ" becomes normal "A".
    text = unicodedata.normalize("NFKC", str(text))

    # Different systems write new lines differently.
    # This changes Windows/Mac-style line endings into one standard "\n".
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove invisible control characters.
    text = _CONTROL_RE.sub("", text)

    # Remove extra spaces from the end of each line.
    lines = [line.rstrip() for line in text.split("\n")]

    # Put the cleaned lines back together and remove extra space at the start/end.
    text = "\n".join(lines).strip()

    # If there are too many blank lines, reduce them to just two.
    text = _BLANK_LINES_RE.sub("\n\n", text)

    # Return the cleaned text.
    return text

```


## UNICODE
- Unicode is a big universal character system.

e.g :
A  = U+0041
Ａ = U+FF21
é  = U+00E9
🙂 = U+1F642
你 = U+4F60

*** Normalization makes equivalent or similar-looking characters more consistent. ***



``` python
import unicodedata

text = "Ａpple"
clean = unicodedata.normalize("NFKC", text)

print(clean)
```

 "Ａ" != "A" ---> Not equal

A  = U+0041   LATIN CAPITAL LETTER A
Ａ = U+FF21   FULLWIDTH LATIN CAPITAL LETTER A

# Apple
`Ａ  becomes  A`

So the model does not learn that:
Apple
Ａpple
are completely different words.

## Key take-ways
1. Does the computer naturally understand "cat"?
A computer does not naturally understand "cat" as an animal. At first, "cat" is just characters stored in memory. For a model to work with it, the text must eventually be converted into numbers.
Tiny correction: converting to numbers is necessary, but it does not automatically create understanding. It only makes the text usable for math.

2. Why clean text first?
We clean text so the computer sees consistent input. If two things mean the same thing, like "Ａ" and "A", we usually want them represented the same way. Otherwise the model wastes effort learning accidental differences.

3. Why change "Ａ" into "A"?
Exactly: because they look similar and mean the same thing here, but the computer sees different character codes.

3. What does normalize_text() do?

normalize_text() takes messy raw text and turns it into cleaner, more consistent text by:
- standardizing similar-looking characters,
- standardizing line breaks,
- removing invisible control characters,
- removing trailing spaces,
- reducing too many blank lines.icode.

So the core idea is:
`Raw messy text` -> `cleaner consistent text`

#  Lesson 2 will be: What is text to a computer?
- Simplest explanation: text is not “meaning” to a computer. Text is stored as symbols, and each symbol has a number behind it.
- text = unicodedata.normalize("NFKC", str(text)) --> This line mainly handles Unicode character normalization. standardize Unicode characters into a more common form
- 65 does not naturally mean "A" inside the computer.
    It is just an agreed code:
    `65 -> "A"`
    Humans and programs agree on that mapping through standards like Unicode.


# Lesson 3: Why Characters Are Not Enough

`chacter` vs `word` vs `subword` tokens ?

    `Unicode` is the catalog; `UTF-8` is the translation layer. `Unicode` defines the characters and assigns them numbers, while `UTF-8` determines how those numbers are saved as data.

``` python
from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers
tokenizer.decoder = decoders.ByteLevel() # This tells the tokenizer how to turn token pieces back into readable text.
```

`text -> tokenizer -> tokens`
`tokens -> decoder -> text again`

> A tokenizer might split it like this:
    "I"   " like"   " cats"   "."
    Then it may assign each token a number:
    "I"      -> 10
    " like"  -> 25`
    " cats"  -> 87
    "."      -> 4
    So the sentence becomes:
    [10, 25, 87, 4]
*Important:* these numbers are still just codes. The number 87 does not naturally mean “cats.” It is just the ID for that token.


# Lesson 4: Tokens Become Token IDs
- After text is split into tokens, each token gets a number.

```python
# Take the text.
# Split it into tokens.
# Convert those tokens into token IDs.
# Store the result in ids.
ids = tokenizer.encode(record["text"]).ids
if append_eos:
    ids.append(eos_id)
```

> The model does arithmetic. Arithmetic needs numbers. So text must become numbers first.


# Lesson 5: What Is A Sequence?
- A sequence is an ordered list.
And for LLMs:
- A sequence is a list of token IDs in the order they appeared in text.
- order matters

# Lesson 6: How A Sequence Becomes A Learning Exercise

```python

# Take a slice from the long token stream.
# Example window:
# [7, 20, 45, 4, 2]
window = np.asarray(
    shard.data[start : start + self.context_length + 1],
    dtype=np.int64,
)
Beginner meaning:
Pick a short ordered piece from the long training data.
Then:
# x is what the model is allowed to see.
# It removes the last token.
#
# If window is:
# [7, 20, 45, 4, 2]
#
# x becomes:
# [7, 20, 45, 4]
x[row] = window[:-1]
Then:
# y is what the model should learn to predict.
# It removes the first token.
#
# If window is:
# [7, 20, 45, 4, 2]
#
# y becomes:
# [20, 45, 4, 2]
y[row] = window[1:]

# So training creates:
x: [7, 20, 45, 4]
y: [20, 45, 4, 2]

This means:
'''
7 should predict 20
20 should predict 45
45 should predict 4
4 should predict 2
'''
```


# Lesson 7: What Is Context?
- previous tokens the model can look at when predicting the next token

"""
'''
<!-- # Pick a short piece from the long token stream.
# If context_length is 4, we grab 5 tokens.
# Why 5? Because we need:
# 4 tokens for x
# 4 shifted tokens for y -->
window = shard.data[start : start + self.context_length + 1]

window: [10, 25, 33, 4, 2]
x:      [10, 25, 33, 4]
y:      [25, 33, 4, 2]

# Lesson 8: What Is A Batch?
- A batch is a group of training examples processed together.

If:
batch_size = 3
context_length = 4
then x will hold:
3 rows
4 token IDs per row
Example:
x = [
  [10, 25, 33, 4],
  [7, 20, 45, 4],
  [11, 26, 34, 4]
]
And y might be:
y = [
  [25, 33, 4, 2],
  [20, 45, 4, 2],
  [26, 34, 4, 2]
]


# Lesson 9: What Is Shape?
- Simplest explanation: shape describes the size of a block of numbers.

```python
# Create an empty number table for input examples.
# Number of rows = batch_size.
# Number of columns = context_length.
x = np.empty((batch_size, self.context_length), dtype=np.int64)

# Create another number table for target answers.
# It has the same shape as x.
y = np.empty((batch_size, self.context_length), dtype=np.int64)
```

## Tiny example:
- batch_size = 3
- context_length = 5
Then:
x shape = (3, 5)
y shape = (3, 5)

# Lesson 10: What Is A Tensor?
- Simplest explanation: a tensor is an organized block of numbers that a model can do math with.

[
  [10, 25, 33],
  [7, 20, 45]
]


```python
# In the repo, this appears in [matgpt/training/dataset.py (line 59)](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/dataset.py:59):
return torch.from_numpy(x).to(device), torch.from_numpy(y).to(device)

Slow explanation:
# x and y started as NumPy arrays.
# NumPy arrays are blocks of numbers Python can work with.

1. torch.from_numpy(x)
means:
2. Turn x into a PyTorch tensor.

4. PyTorch is the library the model uses for training.

5. .to(device)

means:
Move the tensor to the place where math will happen.
That place might be:
CPU = normal computer processor
GPU = faster processor for model training
So the full line means:
Turn x and y into PyTorch tensors, then move them to CPU or GPU.

```


pyTorch models work with tensors,
and tensors can be moved to the CPU or GPU for math.
Efficiency is part of it, especially on GPU, but the first reason is: the model expects PyTorch tensors.


# Lesson 11: Why Token IDs Are Not Enough
- A token ID is just a label.

```
" pizza" -> 45
But 45 by itself does not tell the model anything rich about pizza. It is just an ID.
Analogy: a student ID like 45 does not tell you the student’s name, age, class, or interests. To learn more, you look up the student’s profile.
The model does something similar. It uses the token ID to look up a small list of numbers for that token.
Technical term: that list of numbers is called an embedding.
```

- embedding = a learned number profile for a token


# Lesson 12: Shape After Embeddings
- Before embeddings, x contains token IDs.
- After embedding lookup, each token ID becomes a list of numbers.

x = [
  [10, 25],
  [7, 20]
]

`Shape:` (2, 2)


After embedding lookup, each token ID becomes a list of numbers.
If:
d_model = 3
then every token becomes 3 numbers.
Example lookup:
10 -> [0.1, 0.2, 0.3]
25 -> [0.4, 0.5, 0.6]
7  -> [0.7, 0.8, 0.9]
20 -> [1.0, 1.1, 1.2]
So:
x = [
  [10, 25],
  [7, 20]
]
becomes:
[
  [
    [0.1, 0.2, 0.3],
    [0.4, 0.5, 0.6]
  ],
  [
    [0.7, 0.8, 0.9],
    [1.0, 1.1, 1.2]
  ]
]
Shape:
(2, 2, 3)
Meaning:
2 examples
2 tokens per example
3 numbers per token



# Lesson 13: What Happens After Embedding?
1. Simplest Explanation
- After token IDs become embeddings, the model starts mixing and changing those number profiles so they become useful for predicting the next token.
At first:
- token ID -> embedding vector
Then the model transforms those vectors.
2. Analogy
Imagine each token gets a rough student profile card:
" pizza" -> [food-ish, noun-ish, common-ish]
The model then updates the profile based on nearby words.
In:
I like pizza
the " pizza" profile is understood in the context of "I like".
3. Technical Term
A layer is one processing step that transforms the embeddings.
Beginner meaning:
layer = a block of math that changes number profiles into better number profiles
In this repo, many layers are stacked.
4. Where This Appears In The Repo
In [matgpt/model/gpt.py (line 176)](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:176):
self.blocks = nn.ModuleList([Block(config) for _ in range(config.n_layers)])
5. Code Explained Slowly
# Create a list of Transformer blocks.
# Each Block is one repeated processing layer.
self.blocks = nn.ModuleList(
    [Block(config) for _ in range(config.n_layers)]
)
If:
n_layers = 6
then this creates:
6 Blocks
In the 8M config:
n_layers: 6
So the model processes embeddings through 6 repeated blocks.
Then in the forward pass:
for block in self.blocks:
    x = block(x)
Meaning:
Take the current token number profiles.
Pass them through one block.
Then another.
Then another.
Keep updating x.
The shape usually stays the same:
(batch_size, context_length, d_model)
But the numbers inside become more useful.
6. Tiny Example
Before layer:
" pizza" embedding = [0.2, -0.1, 0.4]
After one layer, maybe:
[0.5, 0.3, -0.2]
After another layer:
[0.8, 0.1, -0.6]
Same shape, changed numbers.



# Lesson 14: Why Tokens Need To Look At Other Tokens
1. Simplest Explanation
A token often needs earlier tokens to understand what it should mean.
Example:
The dog chased the ball because it
What does "it" refer to? Maybe "ball", maybe "dog". You need earlier words to decide.
So the model should not treat each token alone. Each token needs information from nearby previous tokens.
2. Analogy
Imagine hearing only one word:
bank
You do not know if it means a money bank or a river bank.
But with context:
I deposited money at the bank
now you know.
The word uses surrounding words to become clearer.
3. Technical Term
This idea is called attention.
Beginner meaning:
attention = letting a token look at other useful tokens
For now, attention means:
Each token asks: which previous tokens should I pay attention to?
4. Where This Appears In The Repo
In [matgpt/model/gpt.py (line 160)](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:160):
self.attn = CausalSelfAttention(config)
And in [matgpt/model/gpt.py (line 165)](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:165):
x = x + self.attn(self.norm_1(x))
5. Code Explained Slowly
<!-- # This creates the attention part of the block.
# Its job: let tokens use information from other tokens. -->
self.attn = CausalSelfAttention(config)

Now the forward pass:
<!-- # x contains the current number profiles for all tokens.
# self.attn(...) lets each token look at useful earlier tokens.
# The result is added back into x. -->
x = x + self.attn(self.norm_1(x))

Do not worry about norm_1 or x + yet. We will explain them later.
For today, focus only on:
self.attn(...)
Meaning:
Let token vectors mix information from other token vectors.
6. Tiny Example
Sentence:
The dog chased the ball
When processing "ball", attention might look strongly at:
"chased"
"dog"
because those earlier words help explain the situation.
With token IDs, the model does not see words directly, but the idea is the same:
token profile for " ball"
looks at token profiles for useful previous tokens


# Lesson 15: Why Attention Cannot Look Into The Future
- Simplest explanation: when predicting the next token, the model must only use what came before.

-Analogy:

The cat drank milk because it was _____
You should guess using only the words before the blank. If someone shows you the answer first, you are not learning.

- Technical term: causal attention.

- Beginner meaning:
causal attention = attention that only looks backward, not forward
In the repo, this appears in [matgpt/model/gpt.py (line 112)](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:112):
y = F.scaled_dot_product_attention(
    q,
    k,
    v,
    attn_mask=None,
    dropout_p=self.config.dropout if self.training else 0.0,
    is_causal=True,
)
Slow explanation:
<!-- # This runs attention.  -->
y = F.scaled_dot_product_attention(

    # q, k, v are special transformed versions of token vectors.
    # We will explain them later.
    q,
    k,
    v,

    # No extra custom mask is passed here.
    attn_mask=None,

    # Dropout is a training regularization detail. We will explain later.
    dropout_p=self.config.dropout if self.training else 0.0,

    # This is the key part for now:
    # True means each token cannot look at future tokens.
    is_causal=True,
)
- Tiny example:
Tokens:
[The, cat, drank, milk]
When processing "drank", the model may look at:
The
cat
drank
But not:
milk
because "milk" is in the future.

# Lesson 16 : attention scores
# Lesson 17 : attention weights
# Lesson 18 Attention mixes information
Simplest explanation: after attention weights are chosen, the model uses them to mix information from earlier tokens.

<!-- # PyTorch:
# 1. computes attention scores
# 2. turns scores into weights
# 3. uses we`````````````````````````ights to mix token information
# 4. returns the mixed result as y
y = F.scaled_dot_product_attention(...) -->



# Lesson 19: Query, Key, Value
# Lesson 20: Attention Heads
- Simplest explanation: one attention head is one way of looking at the text.
- But language has many kinds of relationships. One head might notice “who did the action,” another might notice “what object is referred to,” another might notice punctuation or grammar.


`example:`
This reshapes ; q,k,v from [batch, seq_len, hidden_dim] ---> [batch, seq_len, n_heads, head_dim]

`So instead of one big vector of size hidden_dim, it splits it into several smaller attention heads.`

e.g
`[2, 5, 32]` becomes `[2, 5, 4, 8]`

- 2 examples in the batch
- 5 tokens per example
- 4 attention heads
- 8 numbers per head


Then this part
`.transpose(1, 2)`

swaps dimension 1 and dimension 2.

So:

`[batch, seq_len, n_heads, head_dim]`

becomes:

`[batch, n_heads, seq_len, head_dim]`

Example:

`[2, 5, 4, 8]`

becomes:

`[2, 4, 5, 8]`

>This layout is more convenient for attention, because each head can process the whole sequence separately.>



esson 21: Why d_model Must Divide Cleanly By n_heads
Simplest explanation: the model splits each token’s number profile across attention heads.
If:
d_model = 24
n_heads = 6
then each head gets:
head_dim = 4
because:
24 / 6 = 4
Analogy: you have 24 cards and 6 people. Each person gets 4 cards. Clean split.
But if:
d_model = 25
n_heads = 6
then:
25 / 6 = not clean
You cannot split 25 numbers evenly across 6 heads.
Technical rule:
d_model must be divisible by n_heads
Repo location: [matgpt/config.py (line 32)](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/config.py:32)
if model["d_model"] % model["n_heads"] != 0:
    raise ValueError("d_model must be divisible by n_heads")
Slow comments:
# % means remainder.
# If d_model divided by n_heads leaves a remainder,
# the split across heads would not be even.
if model["d_model"] % model["n_heads"] != 0:

    # Stop early with a clear error message.
    raise ValueError("d_model must be divisible by n_heads")
Repo also computes head size in [matgpt/model/gpt.py (line 35)](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:35):
@property
def head_dim(self) -> int:
    return self.d_model // self.n_heads
Slow comments:
# head_dim means how many numbers each attention head gets.
def head_dim(self) -> int:

    # // means integer division.
    # Example: 24 // 6 = 4
    return self.d_model // self.n_heads
Questions
Why must d_model divide cleanly by n_heads?
If d_model = 32 and n_heads = 8, what is head_dim?
Is d_model = 30, n_heads = 8 valid? Why or why not?
Exercise
For each, say valid or invalid:
A: d_model = 64, n_heads = 8
B: d_model = 60, n_heads = 8
C: d_model = 128, n_heads = 4

8:14 AM






Questions
Why must d_model divide cleanly by n_heads? its technical rule , that d_model must be divisible by n_heads,
If d_model = 32 and n_heads = 8, what is head_dim? 4
Is d_model = 30, n_heads = 8 valid? Why or why not? not vaild d_model/n_heads produces odd number
Exercise
For each, say valid or invalid:
A: d_model = 64, n_heads = 8  valid
B: d_model = 60, n_heads = 8 invalid
C: d_model = 128, n_heads = 4 valid







Good. Your exercise answers are correct:
A: 64 / 8 = 8    -> valid
B: 60 / 8 = 7.5  -> invalid
C: 128 / 4 = 32  -> valid
Small correction: for d_model = 30, n_heads = 8, the issue is not that it produces an “odd number.” The issue is that it produces not a whole number:
30 / 8 = 3.75
Each head needs the same number of values, so 3.75 values per head is
impossible.

# Lesson 22: Reshaping Into Attention Heads

Simplest explanation: after creating query/key/value numbers, the model rearranges them so each attention head gets its own slice.
Analogy: you have one long row of 16 cards and 4 people.
16 cards / 4 people = 4 cards each
So you split:
[16 numbers] -> [4 heads, 4 numbers each]
Technical term: this is called reshaping.
Repo location: [matgpt/model/gpt.py (line 106)](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:106)
q = q.view(batch, seq_len, self.config.n_heads, self.config.head_dim).transpose(1, 2)
Slow comments:
<!-- # q starts with shape:
# (batch, seq_len, d_model)

# Split d_model into:
# n_heads * head_dim
q = q.view(batch, seq_len, self.config.n_heads, self.config.head_dim)

# Rearrange dimensions so heads come before sequence length.
# New shape:
# (batch, n_heads, seq_len, head_dim)
q = q.transpose(1, 2) -->
Tiny example:
batch = 2
seq_len = 5
d_model = 16
n_heads = 4
head_dim = 4
Before reshape:
q shape = (2, 5, 16)
After view:
q shape = (2, 5, 4, 4)
After transpose:
q shape = (2, 4, 5, 4)
Meaning:
2 examples
4 heads
5 tokens
4 numbers per head
Questions
What does reshaping do in beginner terms?
If d_model = 16 and n_heads = 4, what is head_dim?
If q starts as (2, 5, 16), why can it become (2, 5, 4, 4)?
Exercise
Given:
batch = 3
seq_len = 6
d_model = 24
n_heads = 6
What is:
head_dim = ?
shape after view = ?



Correct.

```text
d_model = 32
n_heads = 8
head_dim = 32 / 8 = 4
```

So:

```text
shape after view = (2, 10, 8, 4)
```

Meaning:

```text
2 examples
10 tokens
8 heads
4 numbers per head
```

**Lesson 23: Why The Code Uses `transpose`**

After `view`, the shape is:

```text
(batch, seq_len, n_heads, head_dim)
```

Example:

```text
(2, 10, 8, 4)
```

But PyTorch’s attention function wants heads before sequence length:

```text
(batch, n_heads, seq_len, head_dim)
```

So the code swaps the `seq_len` and `n_heads` positions.

Technical term: **transpose**.

Beginner meaning:

```text
transpose = swap two dimensions
```

Repo line: [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:106)

```python
q = q.view(batch, seq_len, self.config.n_heads, self.config.head_dim).transpose(1, 2)
```

Slow comments:

```python
# First reshape:
# (batch, seq_len, d_model)
# becomes:
# (batch, seq_len, n_heads, head_dim)
q = q.view(batch, seq_len, self.config.n_heads, self.config.head_dim)

# Then swap dimension 1 and dimension 2.
#
# Dimension 0 = batch
# Dimension 1 = seq_len
# Dimension 2 = n_heads
# Dimension 3 = head_dim
#
# After swapping 1 and 2:
# (batch, n_heads, seq_len, head_dim)
q = q.transpose(1, 2)
```

Tiny example:

```text
before transpose: (2, 10, 8, 4)
after transpose:  (2, 8, 10, 4)
```

Same numbers, different organization.

**Questions**

1. What does transpose do in beginner terms?
2. If shape is `(2, 10, 8, 4)`, what is shape after `transpose(1, 2)`?
3. Does transpose change the numbers themselves, or only their arrangement?

**Exercise**

Given:

```text
shape after view = (3, 6, 6, 4)
```

What is the shape after:

```python
transpose(1, 2)
```


Correct.

```text
d_model = 32
n_heads = 8
head_dim = 32 / 8 = 4
```

So:

```text
shape after view = (2, 10, 8, 4)
```

Meaning:

```text
2 examples
10 tokens
8 heads
4 numbers per head
```

# **Lesson 23: Why The Code Uses `transpose`**

After `view`, the shape is:

```text
(batch, seq_len, n_heads, head_dim)
```

Example:

```text
(2, 10, 8, 4)
```

But PyTorch’s attention function wants heads before sequence length:

```text
(batch, n_heads, seq_len, head_dim)
```

So the code swaps the `seq_len` and `n_heads` positions.

Technical term: **transpose**.

Beginner meaning:

```text
transpose = swap two dimensions
```

Repo line: [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:106)

```python
q = q.view(batch, seq_len, self.config.n_heads, self.config.head_dim).transpose(1, 2)
```

Slow comments:

```python
# First reshape:
# (batch, seq_len, d_model)
# becomes:
# (batch, seq_len, n_heads, head_dim)
q = q.view(batch, seq_len, self.config.n_heads, self.config.head_dim)

# Then swap dimension 1 and dimension 2.
#
# Dimension 0 = batch
# Dimension 1 = seq_len
# Dimension 2 = n_heads
# Dimension 3 = head_dim
#
# After swapping 1 and 2:
# (batch, n_heads, seq_len, head_dim)
q = q.transpose(1, 2)
```

Tiny example:

```text
before transpose: (2, 10, 8, 4)
after transpose:  (2, 8, 10, 4)
```

Same numbers, different organization.

**Questions**

1. What does transpose do in beginner terms?
2. If shape is `(2, 10, 8, 4)`, what is shape after `transpose(1, 2)`?
3. Does transpose change the numbers themselves, or only their arrangement?

**Exercise**

Given:

```text
shape after view = (3, 6, 6, 4)
```

What is the shape after:

```python
transpose(1, 2)
```

# Lesson 24: Why Attention Wants (batch, heads, tokens, head_dim)


We do **not** swap them because `seq_len` and `n_heads` mean the same kind of thing. They are very different.

We swap them because **attention is calculated separately for each head across all tokens**.

Start:

```python
q.shape = (batch, seq_len, d_model)
```

Example:

```python
(batch, seq_len, d_model) = (2, 5, 12)
```

Meaning:

```text
2 examples in batch
5 tokens per example
12 features per token
```

Now split `d_model` into heads:

```python
q = q.view(batch, seq_len, n_heads, head_dim)
```

Example:

```python
(2, 5, 3, 4)
```

Meaning:

```text
2 examples
5 tokens
3 attention heads
4 features per head
```

At this point, the shape is:

```text
(batch, tokens, heads, head_features)
```

But attention wants this shape:

```text
(batch, heads, tokens, head_features)
```

So we do:

```python
q = q.transpose(1, 2)
```

Changing:

```text
(batch, seq_len, n_heads, head_dim)
```

into:

```text
(batch, n_heads, seq_len, head_dim)
```

Why?

Because each head must do attention over the token sequence.

For attention, we compute something like:

```python
scores = q @ k.transpose(-2, -1)
```

With shape:

```python
q = (batch, n_heads, seq_len, head_dim)
k = (batch, n_heads, seq_len, head_dim)
```

Then:

```python
q @ k.transpose(-2, -1)
```

becomes:

```text
(batch, n_heads, seq_len, head_dim)
@
(batch, n_heads, head_dim, seq_len)
=
(batch, n_heads, seq_len, seq_len)
```

That final shape means:

```text
For every batch,
for every head,
each token compares itself with every other token.
```

Example:

```text
(batch, heads, tokens, tokens)
(2, 3, 5, 5)
```

So for each of the 3 heads, we get a `5 x 5` attention matrix.

That matrix answers:

```text
How much should token 1 attend to token 1, 2, 3, 4, 5?
How much should token 2 attend to token 1, 2, 3, 4, 5?
...
```

The reason we put `n_heads` before `seq_len` is to make PyTorch treat each head like a separate attention worker.

Simple intuition:

```text
Before transpose:
(batch, token, head, features)

After transpose:
(batch, head, token, features)
```

We want:

```text
Head 1 looks at all tokens
Head 2 looks at all tokens
Head 3 looks at all tokens
```

Not:

```text
Token 1 contains all heads
Token 2 contains all heads
```

So the transpose organizes the tensor in the most convenient way for parallel attention.

In short:

```python
.transpose(1, 2)
```

is done so that attention can be calculated **per head, across the full sequence of tokens**.

Without it, the matrix multiplication would not naturally produce:

```text
(batch, n_heads, seq_len, seq_len)
```

which is the attention pattern we need.


Correct. All of it.

Tiny wording polish:

```text
seq_len = number of tokens per example
```

And:

```text
separate heads let the model look at different aspects of the sequence
```

Your shape explanation is exactly right:

```text
(4, 6, 12, 8)

4  = batch size / number of examples
6  = number of attention heads
12 = number of tokens per example
8  = numbers per head
```

**Lesson 25: Joining Attention Heads Back Together**

Simplest explanation: after each head looks at the sequence in its own way, the model joins their results back into one token profile.

Analogy: 6 readers each write notes about the same sentence. At the end, you combine their notes into one full report.

Technical term: this is often called **concatenating heads**.

Beginner meaning:

```text
concatenate = join pieces side by side
```

Repo location: [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:120)

```python
y = y.transpose(1, 2).contiguous().view(batch, seq_len, d_model)
```

Slow comments:

```python
# Before this line, attention output y has shape:
# (batch, n_heads, seq_len, head_dim)

# Swap heads and sequence back:
# (batch, seq_len, n_heads, head_dim)
y = y.transpose(1, 2)

# Make memory layout clean for reshaping.
# Do not worry deeply about this yet.
y = y.contiguous()

# Join n_heads and head_dim back into d_model.
# Since d_model = n_heads * head_dim,
# shape becomes:
# (batch, seq_len, d_model)
y = y.view(batch, seq_len, d_model)
```

Tiny example:

```text
batch = 2
seq_len = 10
n_heads = 8
head_dim = 4
```

Before joining:

```text
(2, 8, 10, 4)
```

After transpose:

```text
(2, 10, 8, 4)
```

After joining heads:

```text
(2, 10, 32)
```

because:

```text
8 heads * 4 numbers per head = 32
```

**Questions**

1. What does concatenate mean in beginner terms?
2. If `n_heads = 8` and `head_dim = 4`, what is `d_model`?
3. Why does the model join the heads back together?

**Exercise**

Given:

```text
batch = 3
seq_len = 6
n_heads = 6
head_dim = 4
```

What is the final shape after joining heads back together?

Use:

```text
(batch, seq_len, d_model)
```







Correct. All of it.

Tiny wording polish:

```text
seq_len = number of tokens per example
```

And:

```text
separate heads let the model look at different aspects of the sequence
```

Your shape explanation is exactly right:

```text
(4, 6, 12, 8)

4  = batch size / number of examples
6  = number of attention heads
12 = number of tokens per example
8  = numbers per head
```

# **Lesson 25: Joining Attention Heads Back Together**

Simplest explanation: after each head looks at the sequence in its own way, the model joins their results back into one token profile.

Analogy: 6 readers each write notes about the same sentence. At the end, you combine their notes into one full report.

Technical term: this is often called **concatenating heads**.

Beginner meaning:

```text
concatenate = join pieces side by side
```

Repo location: [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:120)

```python
y = y.transpose(1, 2).contiguous().view(batch, seq_len, d_model)
```

Slow comments:

```python
# Before this line, attention output y has shape:
# (batch, n_heads, seq_len, head_dim)

# Swap heads and sequence back:
# (batch, seq_len, n_heads, head_dim)
y = y.transpose(1, 2)

# Make memory layout clean for reshaping.
# Do not worry deeply about this yet.
y = y.contiguous()

# Join n_heads and head_dim back into d_model.
# Since d_model = n_heads * head_dim,
# shape becomes:
# (batch, seq_len, d_model)
y = y.view(batch, seq_len, d_model)
```

Tiny example:

```text
batch = 2
seq_len = 10
n_heads = 8
head_dim = 4
```

Before joining:

```text
(2, 8, 10, 4)
```

After transpose:

```text
(2, 10, 8, 4)
```

After joining heads:

```text
(2, 10, 32)
```

because:

```text
8 heads * 4 numbers per head = 32
```

**Questions**

1. What does concatenate mean in beginner terms?
2. If `n_heads = 8` and `head_dim = 4`, what is `d_model`?
3. Why does the model join the heads back together?

**Exercise**

Given:

```text
batch = 3
seq_len = 6
n_heads = 6
head_dim = 4
```

What is the final shape after joining heads back together?

Use:

```text
(batch, seq_len, d_model)
```


Correct.

Your answers:

```text
concatenate = join pieces side by side
```

Correct.

```text
n_heads = 8
head_dim = 4
d_model = 8 * 4 = 32
```

Correct.

```text
final shape = (3, 6, 24)
```

Correct, because:

```text
d_model = n_heads * head_dim
d_model = 6 * 4 = 24
```

Your explanation is also good:

```text
The model joins heads back together so the different attention views become one combined token profile again.
```

# **Lesson 26: The Projection After Attention**

After attention heads are joined, the model has a combined result.

But it does one more step: it passes that combined result through another learned transformation.

Simplest explanation:

```text
attention gathers information
projection cleans/re-mixes that information into the form the model wants next
```

Analogy: 6 readers give you notes. You combine all notes into one big report. Then an editor rewrites the report into a clean final version.

Technical term: this learned transformation is called a **projection**.

Beginner meaning:

```text
projection = learned math that remixes numbers into a new useful form
```

Repo location: [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:96)

```python
self.proj = nn.Linear(config.d_model, config.d_model, bias=config.use_bias)
```

Slow comments:

```python
# Create a learned transformation.
# It takes d_model numbers in.
# It returns d_model numbers out.
# So the shape stays the same, but the values can change.
self.proj = nn.Linear(config.d_model, config.d_model, bias=config.use_bias)
```

Then [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:121):

```python
return self.dropout(self.proj(y))
```

Slow comments:

```python
# y is the joined attention result.
# self.proj(y) remixes the numbers using learned weights.
# self.dropout(...) is a training trick we will explain later.
return self.dropout(self.proj(y))
```

Tiny example:

```text
before projection: [0.2, 0.5, -0.1, 0.7]
after projection:  [0.4, -0.2, 0.9, 0.1]
```

Same length, changed numbers.

**Questions**

1. In beginner terms, what does projection do?
2. Does this projection change the shape from `(batch, seq_len, d_model)`?
3. Why might the model want to remix the joined attention result?

**Exercise**

If attention output has shape:

```text
(3, 6, 24)
```

and projection is:

```python
nn.Linear(24, 24)
```

what is the output shape?


Small wording polish:

```text
Projection remixes numbers into a new useful form.
```

```text
It does not change the shape here because nn.Linear(24, 24) takes 24 numbers in and returns 24 numbers out.
```

Your exercise is right:

```text
input shape:  (3, 6, 24)
output shape: (3, 6, 24)
```

# **Lesson 27: Residual Connections**

Look at this line in the repo:

[matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:165)

```python
x = x + self.attn(self.norm_1(x))
```

Simplest explanation: the model keeps the original `x` and adds the attention result to it.

```text
new x = old x + attention update
```

Analogy: imagine editing a document.

You do not throw away the original paragraph. You add improvements to it.

```text
original paragraph + edits = improved paragraph
```

Technical term: this is called a **residual connection**.

Beginner meaning:

```text
residual connection = keep the old information and add an update
```

Slow code explanation:

```python
# x is the current token information.
x

# self.norm_1(x) prepares x before attention.
# We will explain normalization later.
self.norm_1(x)

# self.attn(...) computes an attention update.
# This update contains information gathered from useful previous tokens.
self.attn(self.norm_1(x))

# Add the update back to the original x.
# This keeps old information while adding new information.
x = x + self.attn(self.norm_1(x))
```

Tiny number example:

```text
old x = 10
attention update = 3

new x = old x + update
new x = 10 + 3
new x = 13
```

For vectors:

```text
old x = [1, 2, 3]
update = [0.5, -1, 2]

new x = [1.5, 1, 5]
```

Why this matters:

```text
The model can improve token information without completely replacing it.
```

**Questions**

1. In beginner terms, what is a residual connection?
2. In `x = x + update`, what does the first `x` help preserve?
3. If `x = [2, 4]` and `update = [1, -3]`, what is the new `x`?

**Exercise**

Compute:

```text
old x = [1, 5, 2]
attention update = [3, -2, 4]

new x = ?
```




Correct.

Your residual definition is good:

```text
original token information + attention update
```

More polished:

```text
A residual connection keeps the original information and adds a learned update.
```

Your arithmetic is also correct:

```text
x = [2, 4]
update = [1, -3]
new x = [3, 1]
```

And:

```text
old x = [1, 5, 2]
update = [3, -2, 4]
new x = [4, 3, 6]
```

# **Lesson 28: Normalization Before Attention**

Look again at:

```python
x = x + self.attn(self.norm_1(x))
```

We already understand:

```text
x + attention update
```

Now focus on:

```python
self.norm_1(x)
```

Simplest explanation: normalization keeps numbers in a steady range before the model does more math.

Analogy: imagine several people speaking at different volumes. One whispers, one shouts. Before recording them, you adjust volumes so they are easier to process.

Normalization does something similar for numbers.

Technical term: this repo uses **RMSNorm**.

Beginner meaning:

```text
RMSNorm = scale a token’s number profile so its size is more stable
```

Repo location: [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:44)

```python
class RMSNorm(nn.Module):
```

Important line: [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:57)

```python
normed = x * torch.rsqrt(x.pow(2).mean(dim=-1, keepdim=True) + self.eps)
```

Slow comments:

```python
# x is a token's number profile.
# Example: [3, 4]

# x.pow(2) squares each number.
# [3, 4] -> [9, 16]

# mean(...) gets the average squared size.
# [9, 16] average = 12.5

# + self.eps adds a tiny safety number so we do not divide by zero.

# torch.rsqrt(...) means reciprocal square root.
# It helps scale the vector down or up.

# x * ... scales the original numbers to a more stable size.
normed = x * torch.rsqrt(x.pow(2).mean(dim=-1, keepdim=True) + self.eps)
```

Do not worry if the math feels a little new. The beginner idea is enough for now:

```text
RMSNorm keeps token vectors from becoming too huge or too tiny.
```

**Questions**

1. In beginner terms, why do we normalize numbers before attention?
2. Does normalization change the shape of `x`?
3. What is the main beginner idea of RMSNorm?

**Exercise**

If:

```text
x shape = (2, 4, 3)
```

after RMSNorm, what is the shape?

Correct.

Your answers:

```text
Normalize so numbers do not become too big or too tiny.
Normalization does not change shape.
RMSNorm scales a token's number profile so its size is more stable.
```

And:

```text
x shape before RMSNorm = (2, 4, 3)
x shape after RMSNorm  = (2, 4, 3)
```

Exactly.

# **Lesson 29: The MLP Part Of A Transformer Block**

We have seen this line:

```python
x = x + self.attn(self.norm_1(x))
```

That is the attention update.

Now look at the next line in [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:166):

```python
x = x + self.mlp(self.norm_2(x))
```

Simplest explanation:

```text
attention mixes information between tokens.
MLP thinks about each token's information more deeply.
```

Analogy:

Attention is like asking classmates for useful context.

MLP is like sitting quietly and processing your own notes after hearing everyone.

Technical term: **MLP** means **multi-layer perceptron**.

Beginner meaning:

```text
MLP = a small stack of learned math that transforms each token's number profile
```

Slow code comments:

```python
# x is the current token information after attention.
x

# self.norm_2(x) stabilizes the numbers before the MLP.
self.norm_2(x)

# self.mlp(...) transforms each token's number profile.
# It does not mix tokens with each other like attention does.
self.mlp(self.norm_2(x))

# Add the MLP update back to the original x.
# This is another residual connection.
x = x + self.mlp(self.norm_2(x))
```

Important beginner distinction:

```text
attention: tokens look at other tokens
MLP: each token gets transformed on its own
```

Shape usually stays the same:

```text
before MLP: (batch, seq_len, d_model)
after MLP:  (batch, seq_len, d_model)
```

**Questions**

1. In beginner terms, what does the MLP do?
2. What is the difference between attention and MLP?
3. Does this MLP block usually change the shape of `x`?

**Exercise**

If:

```text
x shape before MLP = (2, 4, 3)
```

what is the usual shape after:

```python
x = x + self.mlp(self.norm_2(x))
```

Correct.

Your answers:

```text
Normalize so numbers do not become too big or too tiny.
Normalization does not change shape.
RMSNorm scales a token's number profile so its size is more stable.
```

And:

```text
x shape before RMSNorm = (2, 4, 3)
x shape after RMSNorm  = (2, 4, 3)
```

Exactly.

# **Lesson 29: The MLP Part Of A Transformer Block**

We have seen this line:

```python
x = x + self.attn(self.norm_1(x))
```

That is the attention update.

Now look at the next line in [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:166):

```python
x = x + self.mlp(self.norm_2(x))
```

Simplest explanation:

```text
attention mixes information between tokens.
MLP thinks about each token's information more deeply.
```

Analogy:

Attention is like asking classmates for useful context.

MLP is like sitting quietly and processing your own notes after hearing everyone.

Technical term: **MLP** means **multi-layer perceptron**.

Beginner meaning:

```text
MLP = a small stack of learned math that transforms each token's number profile
```

Slow code comments:

```python
# x is the current token information after attention.
x

# self.norm_2(x) stabilizes the numbers before the MLP.
self.norm_2(x)

# self.mlp(...) transforms each token's number profile.
# It does not mix tokens with each other like attention does.
self.mlp(self.norm_2(x))

# Add the MLP update back to the original x.
# This is another residual connection.
x = x + self.mlp(self.norm_2(x))
```

Important beginner distinction:

```text
attention: tokens look at other tokens
MLP: each token gets transformed on its own
```

Shape usually stays the same:

```text
before MLP: (batch, seq_len, d_model)
after MLP:  (batch, seq_len, d_model)
```

**Questions**

1. In beginner terms, what does the MLP do?
2. What is the difference between attention and MLP?
3. Does this MLP block usually change the shape of `x`?

**Exercise**

If:

```text
x shape before MLP = (2, 4, 3)
```

what is the usual shape after:

```python
x = x + self.mlp(self.norm_2(x))
```


Correct.

Small formatting fix:

```text
(2, 4, 3)
```

Your explanation is right:

```text
MLP transforms each token’s number profile individually.
Attention lets tokens look at each other.
MLP usually keeps the same shape.
```

# **Lesson 30: Expanding And Shrinking Inside The MLP**

The MLP usually does two big things:

```text
1. expand the token profile
2. shrink it back
```

Analogy: imagine taking a short note and expanding it into a detailed draft, then summarizing it back into a better short note.

```text
short note -> detailed draft -> improved short note
```

Technical terms:

```text
d_model = normal token profile size
d_ff = larger hidden size inside the MLP
```

Repo config: [configs/matgpt_mini_8m.yaml](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/configs/matgpt_mini_8m.yaml:63)

```yaml
d_model: 256
d_ff: 1024
```

Beginner meaning:

```text
Each token normally has 256 numbers.
Inside the MLP, it expands to 1024 numbers.
Then it shrinks back to 256.
```

Repo code: [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:135)

```python
self.w1 = nn.Linear(config.d_model, config.d_ff, bias=config.use_bias)
self.w3 = nn.Linear(config.d_model, config.d_ff, bias=config.use_bias)
self.w2 = nn.Linear(config.d_ff, config.d_model, bias=config.use_bias)
```

Slow comments:

```python
# w1 expands from d_model to d_ff.
# Example: 256 -> 1024
self.w1 = nn.Linear(config.d_model, config.d_ff, bias=config.use_bias)

# w3 also expands from d_model to d_ff.
# This is part of SwiGLU, which we will explain later.
self.w3 = nn.Linear(config.d_model, config.d_ff, bias=config.use_bias)

# w2 shrinks from d_ff back to d_model.
# Example: 1024 -> 256
self.w2 = nn.Linear(config.d_ff, config.d_model, bias=config.use_bias)
```

For now, focus on:

```text
MLP expands, works in a bigger space, then shrinks back.
```

**Questions**

1. What does `d_model` mean here?
2. What does `d_ff` mean here?
3. Why does the MLP shrink back to `d_model` at the end?

**Exercise**

If:

```text
d_model = 512
d_ff = 2048
```

What are the sizes for:

```text
expand: ? -> ?
shrink: ? -> ?
```

information = 8
gate = 0.5

passed information = ?

Good.

Your concepts are correct:

```text
d_model = normal token vector size / model width
d_ff = bigger hidden size inside the MLP
```

Your answer:

```text
to keep the size of a token throughout
```

is right. More polished:

```text
The MLP shrinks back to d_model so the next part of the Transformer receives the expected shape.
```

Exercise correction:

Given:

```text
d_model = 512
d_ff = 2048
```

The full answer is:

```text
expand: 512 -> 2048
shrink: 2048 -> 512
```

You wrote the ending sizes correctly; just include both sides.

# **Lesson 31: Activation Inside The MLP**

If the MLP only did straight-line math, it would be limited.

So it uses a special function that bends the math and lets the model learn richer patterns.

Analogy: a light dimmer.

Instead of only ON/OFF, the model can smoothly decide how much signal should pass through.

Technical term: **activation function**.

Beginner meaning:

```text
activation = a function that controls and bends the signal
```

This repo uses something called **SwiGLU**.

Do not worry about the full name yet. Beginner meaning:

```text
SwiGLU helps the MLP decide which information to let through strongly and which to reduce.
```

Repo location: [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:148)

```python
x = self.w2(F.silu(self.w1(x)) * self.w3(x))
```

Slow comments:

```python
# self.w1(x) expands the token profile.
self.w1(x)

# F.silu(...) is an activation function.
# It bends/controls the expanded signal.
F.silu(self.w1(x))

# self.w3(x) creates another expanded signal.
self.w3(x)

# * means element-by-element multiply.
# This acts like a gate:
# some information passes strongly,
# some information is reduced.
F.silu(self.w1(x)) * self.w3(x)

# self.w2(...) shrinks the result back to d_model.
x = self.w2(F.silu(self.w1(x)) * self.w3(x))
```

Tiny example of a gate:

```text
information = 10
gate = 0.2

passed information = 10 * 0.2 = 2
```

Another:

```text
information = 10
gate = 0.9

passed information = 10 * 0.9 = 9
```

So the MLP can control what information flows through.

**Questions**

1. In beginner terms, what does an activation function do?
2. What does a gate do?
3. In `10 * 0.2 = 2`, did the gate let a lot through or a little?

**Exercise**

Compute:

```text
information = 8
gate = 0.5

passed information = ?
```


Correct.

```text
information = 12
gate = 0.25
passed information = 12 * 0.25 = 3
```

So the gate lets through one quarter of the signal.

# **Lesson 32: One Transformer Block**

Now we can assemble the block.

Repo location: [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:164)

```python
def forward(self, x: torch.Tensor) -> torch.Tensor:
    x = x + self.attn(self.norm_1(x))
    x = x + self.mlp(self.norm_2(x))
    return x
```

Beginner explanation:

```text
A Transformer block improves token profiles in two main steps:
1. attention: tokens look at useful earlier tokens
2. MLP: each token processes its own information
```

Slow comments:

```python
def forward(self, x):
    # Step 1:
    # Normalize x so the numbers are stable.
    # Run attention so tokens can use information from earlier tokens.
    # Add that attention update back to the original x.
    x = x + self.attn(self.norm_1(x))

    # Step 2:
    # Normalize again.
    # Run the MLP so each token can process its own number profile.
    # Add that MLP update back to x.
    x = x + self.mlp(self.norm_2(x))

    # Return the improved token profiles.
    return x
```

Analogy:

```text
attention = ask classmates for useful context
MLP = think privately about your updated notes
residual = keep your original notes and add improvements
normalization = keep everything at a manageable volume
```

Shape usually stays the same:

```text
input x:  (batch, seq_len, d_model)
output x: (batch, seq_len, d_model)
```

**Questions**

1. What are the two main parts of a Transformer block?
2. What does attention do?
3. What does the MLP do?
4. Why do we add updates back to `x`?

**Exercise**

If:

```text
x shape entering block = (2, 4, 8)
```

what is the usual shape after one Transformer block?


Correct.

Small typo fixes:

```text
earlier, not ealier
token, not toke
```

Your ideas are right:

```text
Transformer block = attention + MLP
attention = tokens look at useful earlier tokens
MLP = each token processes its own information
residual = keep original information and add improvements
```

Your exercise is correct:

```text
input shape:  (2, 4, 8)
output shape: (2, 4, 8)
```

# **Lesson 33: Stacking Many Blocks**

One Transformer block improves token profiles once.

A GPT model uses many blocks in a row.

Analogy:

```text
Draft 1 -> edit -> edit -> edit -> final improved draft
```

Each block refines the token information a bit more.

Repo location: [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:176)

```python
self.blocks = nn.ModuleList([Block(config) for _ in range(config.n_layers)])
```

Slow comments:

```python
# Create many Transformer blocks.
# config.n_layers decides how many.
self.blocks = nn.ModuleList(
    [Block(config) for _ in range(config.n_layers)]
)
```

Then during the forward pass:

```python
for block in self.blocks:
    x = block(x)
```

Slow comments:

```python
# Send x through each block one by one.
# Each block updates the token profiles.
for block in self.blocks:
    x = block(x)
```

In the 8M config:

```yaml
n_layers: 6
```

So the model runs:

```text
block 1
block 2
block 3
block 4
block 5
block 6
```

Shape usually stays:

```text
(batch, seq_len, d_model)
```

but the numbers become more useful.

**Questions**

1. What does `n_layers` control?
2. If `n_layers = 6`, how many Transformer blocks are used?
3. If `x` enters block 1 with shape `(2, 4, 8)`, what shape usually comes out of block 6?

**Exercise**

If:

```text
n_layers = 12
x shape before first block = (3, 10, 16)
```

what is the usual shape after all 12 blocks?

Correct. Clean answers.

```text
n_layers controls how many Transformer blocks are created.
n_layers = 6 means 6 blocks.
Shape usually stays the same through the blocks.
```

Your exercise is correct:

```text
before 12 blocks: (3, 10, 16)
after 12 blocks:  (3, 10, 16)
```

The numbers inside change, but the shape stays the same.


# **Lesson 34: From Token Profiles To Vocabulary Scores**

After all Transformer blocks, the model has improved token profiles.

But we need a next-token prediction.

So the model must turn each token profile into scores for every possible next token.

Example:

```text
possible next tokens:
" pizza"
" dog"
"."
"<|eos|>"
...
```

The model gives each possible token a score.

Technical term: these raw scores are called **logits**.

Beginner meaning:

```text
logits = raw scores for possible next tokens
```

They are not probabilities yet. They are just scores.

Repo location: [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:178)

```python
self.lm_head = nn.Linear(config.d_model, config.vocab_size, bias=False)
```

Slow comments:

```python
# lm_head turns each final token profile into vocabulary scores.
#
# It takes d_model numbers in.
# It outputs vocab_size numbers.
#
# Example:
# d_model = 256
# vocab_size = 8192
#
# For each token position:
# 256-number profile -> 8192 scores
self.lm_head = nn.Linear(config.d_model, config.vocab_size, bias=False)
```

Then in [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:206):

```python
logits = self.lm_head(x)
```

Slow comments:

```python
# x shape before:
# (batch, seq_len, d_model)

# logits shape after:
# (batch, seq_len, vocab_size)

# Each position now has one score for every token in the vocabulary.
logits = self.lm_head(x)
```

Tiny example:

```text
vocab:
0 = " cat"
1 = " dog"
2 = " pizza"
3 = "."
```

For one position, logits might be:

```text
[0.2, 1.5, 3.0, -0.5]
```

Highest score is:

```text
3.0 for " pizza"
```

So the model currently likes `" pizza"` most.

**Questions**

1. In beginner terms, what are logits?
2. Are logits probabilities yet?
3. If `vocab_size = 8192`, how many logits does the model output per token position?

**Exercise**

If:

```text
x shape = (2, 4, 8)
vocab_size = 100
```

After:

```python
logits = self.lm_head(x)
```

what is the logits shape?


Correct.

```text
logits = raw scores for possible next tokens
logits are not probabilities yet
vocab_size = 8192 -> 8192 logits per token position
```

Your exercise is also correct:

```text
x shape = (2, 4, 8)
vocab_size = 100
logits shape = (2, 4, 100)
```

Meaning:

```text
2 examples
4 token positions per example
100 possible next-token scores at each position
```

# **Lesson 35: From Logits To Probabilities**

Simplest explanation: logits are raw scores. To choose a next token, we often want probabilities.

Example logits:

```text
" cat"   -> 1.0
" dog"   -> 2.0
" pizza" -> 5.0
```

The biggest logit is `" pizza"`, so it should get the highest probability.

Technical term: **softmax**.

Beginner meaning:

```text
softmax = turns raw scores into probabilities that add up to 1
```

Example:

```text
logits:
[1.0, 2.0, 5.0]

after softmax, maybe:
[0.02, 0.05, 0.93]
```

The probabilities add to:

```text
0.02 + 0.05 + 0.93 = 1.00
```

Repo location: [matgpt/model/generation.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/generation.py:48)

```python
probs = F.softmax(next_logits, dim=-1)
```

Slow comments:

```python
# next_logits are raw scores for the next token.
# F.softmax turns those scores into probabilities.
# dim=-1 means "apply softmax across the vocabulary scores."
probs = F.softmax(next_logits, dim=-1)
```

**Questions**

1. In beginner terms, what does softmax do?
2. Do probabilities after softmax add up to 1?
3. If one token has a much larger logit, should it get a higher or lower probability?

**Exercise**

Which token is most likely before softmax?

```text
" cat"   -> logit 0.5
" dog"   -> logit 3.0
" pizza" -> logit 1.0
```


Correct.

Small typo polish:

```text
softmax turns raw scores into probabilities
```

And yes:

```text
probabilities add up to 1
bigger logit -> higher probability
```

Your exercise answer is correct:

```text
" dog"
```

because `3.0` is the highest logit.



# **Lesson 36: How The Model Knows It Was Wrong**

Simplest explanation: after the model predicts probabilities, we compare them to the correct next token.

Example:

```text
Correct next token: " dog"
```

Model probabilities:

```text
" cat"   -> 0.10
" dog"   -> 0.80
" pizza" -> 0.10
```

This is good because the correct token got high probability.

But if the model says:

```text
" cat"   -> 0.80
" dog"   -> 0.05
" pizza" -> 0.15
```

that is bad because the correct token got low probability.

Technical term: **loss**.

Beginner meaning:

```text
loss = a mistake score
```

Low loss means:

```text
the model gave high probability to the correct answer
```

High loss means:

```text
the model gave low probability to the correct answer
```

Repo location: [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:211)

```python
loss = F.cross_entropy(
    logits.reshape(-1, logits.size(-1)),
    targets.reshape(-1),
    ignore_index=-100,
)
```

Slow comments:

```python
# logits are the model's raw scores for possible next tokens.
# targets are the correct next token IDs.

# cross_entropy compares:
# model scores vs correct answers

# It returns one mistake score:
# lower is better, higher is worse.
loss = F.cross_entropy(...)
```

Do not worry about `reshape` yet. The beginner idea is:

```text
cross_entropy computes the loss.
loss tells us how wrong the model was.
```

**Questions**

1. In beginner terms, what is loss?
2. Is lower loss better or worse?
3. If the correct token gets high probability, should loss be high or low?

**Exercise**

Correct token:

```text
" dog"
```

Which prediction has lower loss?

```text
A:
" dog" -> 0.90

B:
" dog" -> 0.10
```

Correct.

Your answers:

```text
loss = tells us how wrong the model was
lower loss = better
correct token high probability = low loss
```

Exercise:

```text
A: " dog" -> 0.90
B: " dog" -> 0.10
```

A has lower loss because the model gave the correct token much higher probability.


# **Lesson 37: The Tiny Math Behind Loss**

Simplest explanation:

```text
Loss rewards high probability for the correct token.
Loss punishes low probability for the correct token.
```

Technical idea:

```text
loss = -log(probability of correct token)
```

Do not let `log` scare you. For now, think:

```text
log helps turn probability into a penalty score
```

Tiny examples:

```text
Correct token probability = 0.90
loss = -log(0.90)
loss ≈ 0.11
```

Low loss. Good.

```text
Correct token probability = 0.10
loss = -log(0.10)
loss ≈ 2.30
```

Higher loss. Bad.

```text
Correct token probability = 0.01
loss = -log(0.01)
loss ≈ 4.61
```

Very high loss. Very bad.

Repo location: [matgpt/model/gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:211)

```python
loss = F.cross_entropy(...)
```

Slow comment:

```python
# Cross entropy does the softmax + -log(correct probability) work for us.
# It returns a mistake score.
# Lower is better.
loss = F.cross_entropy(...)
```

**Questions**

1. If the correct token probability is high, what happens to loss?
2. If the correct token probability is very low, what happens to loss?
3. In beginner terms, what does `-log(correct probability)` do?

**Exercise**

Which has lower loss?

```text
A: correct token probability = 0.80
B: correct token probability = 0.20
```

Correct.

Tiny spelling polish:

```text
penalty, not penality
```

Your answers are right:

```text
high correct-token probability -> lower loss
low correct-token probability -> higher loss
-log(correct probability) -> turns probability into a penalty score
```

And yes:

```text
A has lower loss because 0.80 is better than 0.20.
```

# **Lesson 38: What Changes When A Model Learns?**

Simplest explanation:

```text
The model learns by changing its internal numbers.
```

Those internal numbers control how token IDs become embeddings, how attention works, how the MLP works, and how logits are produced.

Technical term: these learnable internal numbers are called **parameters**.

Beginner meaning:

```text
parameters = numbers inside the model that training changes
```

Analogy: imagine a sound mixer with many knobs. At first, the knobs are random. Training slowly adjusts the knobs so the output sounds better.

Repo examples:

```python
self.token_embedding = nn.Embedding(config.vocab_size, config.d_model)
```

This has learnable numbers for token embeddings.

```python
self.lm_head = nn.Linear(config.d_model, config.vocab_size, bias=False)
```

This has learnable numbers for turning token profiles into logits.

Slow explanation:

```python
# nn.Embedding creates a lookup table.
# The values in that table are parameters.
# Training changes them.
self.token_embedding = nn.Embedding(...)
```

```python
# nn.Linear creates learned math.
# Its weights are parameters.
# Training changes them too.
self.lm_head = nn.Linear(...)
```

Important idea:

```text
The code structure stays the same.
The parameter values change.
```

**Questions**

1. In beginner terms, what are parameters?
2. Does training usually change the Python code, or the numbers inside the model?
3. Give one repo example of something that contains parameters.

**Exercise**

Fill in the blank:

```text
Training tries to reduce ______ by adjusting the model’s ______.
```

Correct.

Tiny spelling polish:

```text
penalty, not penality
```

Your answers are right:

```text
high correct-token probability -> lower loss
low correct-token probability -> higher loss
-log(correct probability) -> turns probability into a penalty score
```

And yes:

```text
A has lower loss because 0.80 is better than 0.20.
```

**Lesson 38: What Changes When A Model Learns?**

Simplest explanation:

```text
The model learns by changing its internal numbers.
```

Those internal numbers control how token IDs become embeddings, how attention works, how the MLP works, and how logits are produced.

Technical term: these learnable internal numbers are called **parameters**.

Beginner meaning:

```text
parameters = numbers inside the model that training changes
```

Analogy: imagine a sound mixer with many knobs. At first, the knobs are random. Training slowly adjusts the knobs so the output sounds better.

Repo examples:

```python
self.token_embedding = nn.Embedding(config.vocab_size, config.d_model)
```

This has learnable numbers for token embeddings.

```python
self.lm_head = nn.Linear(config.d_model, config.vocab_size, bias=False)
```

This has learnable numbers for turning token profiles into logits.

Slow explanation:

```python
# nn.Embedding creates a lookup table.
# The values in that table are parameters.
# Training changes them.
self.token_embedding = nn.Embedding(...)
```

```python
# nn.Linear creates learned math.
# Its weights are parameters.
# Training changes them too.
self.lm_head = nn.Linear(...)
```

Important idea:

```text
The code structure stays the same.
The parameter values change.
```

**Questions**

1. In beginner terms, what are parameters?
2. Does training usually change the Python code, or the numbers inside the model?
3. Give one repo example of something that contains parameters.

**Exercise**

Fill in the blank:

```text
Training tries to reduce ______ by adjusting the model’s ______.
```

Correct.

Small clarification on question 2:

You wrote:

```text
no
```

Better answer:

```text
Training changes the numbers inside the model, not the Python code.
```

Everything else is right:

```text
parameters = learnable internal model numbers
example = embeddings
training tries to reduce loss by adjusting the model’s parameters
```

That sentence is a big milestone. That is the core of training.

# **Lesson 39: Gradients**

Now the question is:

```text
How does the model know how to adjust the parameters?
```

It uses something called a **gradient**.

Simplest explanation:

```text
gradient = direction and strength for how to change a parameter to reduce loss
```

Analogy: imagine you are on a hill and want to walk downhill. The slope tells you which way is down and how steep it is.

A gradient is like that slope.

Technical term: **gradient**.

Beginner meaning:

```text
gradient = signal that tells a parameter how changing it affects loss
```

If changing a parameter upward increases loss, the model may move it downward.

If changing a parameter upward decreases loss, the model may move it upward.

Repo location: [matgpt/training/pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:216)

```python
scaler.scale(scaled_loss).backward()
```

Slow comments:

```python
# scaled_loss is the mistake score for this training step.
# backward() computes gradients.
# Gradients tell each parameter how it contributed to the loss.
scaler.scale(scaled_loss).backward()
```

Ignore `scaler` for now. Beginner version:

```python
loss.backward()
```

means:

```text
compute gradients
```

**Questions**

1. In beginner terms, what is a gradient?
2. Does a gradient directly mean “the answer,” or does it tell how to adjust parameters?
3. What does `backward()` compute?

**Exercise**

Fill in the blank:

```text
Loss tells us how wrong the model is.
Gradients tell us how to change the ______ to reduce that loss.
```

Correct. More precise spelling:

```text
gradients
```

`backward()` computes gradients.

# **Lesson 40: Optimizer**

Simplest explanation:

```text
gradients say how to change parameters.
optimizer actually changes the parameters.
```

Analogy: gradients are like advice from a coach:

```text
move this knob up
move this knob down
move this knob only a little
```

The optimizer is the person turning the knobs.

Technical term: **optimizer**.

Beginner meaning:

```text
optimizer = the tool that updates model parameters using gradients
```

Repo location: [matgpt/training/pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:221)

```python
scaler.step(optimizer)
```

Slow comments:

```python
# Gradients have already been computed by backward().
# optimizer knows how to use those gradients.
# step(...) updates the model parameters.
scaler.step(optimizer)
```

Ignore `scaler` for now. Beginner version:

```python
optimizer.step()
```

means:

```text
change the model parameters using the gradients
```

Tiny number example:

```text
parameter = 10
gradient says: move down by 2

new parameter = 8
```

In real training, the update is usually much smaller and more careful.

**Questions**

1. In beginner terms, what does an optimizer do?
2. Does `backward()` update parameters, or only compute gradients?
3. What does `optimizer.step()` do?

**Exercise**

Fill in the blanks:

```text
backward() computes ______.
optimizer.step() updates ______.
```

Correct.

Small spelling polish:

```text
step size, not stp size
wildly, not widly
```

And yes:

```yaml
learning_rate: 3.0e-4
```

is the learning rate. It means:

```text
0.0003
```

Correct.

Small spelling polish:

```text
parameters
computes
gradients
```

Your core understanding is right:

```text
backward() computes gradients.
optimizer.step() updates parameters using gradients.
```

# **Lesson 41: Learning Rate**

Simplest explanation:

```text
learning rate controls how big each parameter update is
```

If learning rate is too big:

```text
the model may jump wildly and fail to learn
```

If learning rate is too small:

```text
the model may learn very slowly
```

Analogy: walking downhill.

A small step is safe but slow.

A huge jump might overshoot and fall past the good spot.

Technical term: **learning rate**.

Beginner meaning:

```text
learning rate = step size for parameter updates
```

Repo config: [configs/matgpt_mini_8m.yaml](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/configs/matgpt_mini_8m.yaml:79)

```yaml
learning_rate: 5.0e-4
```

That means:

```text
0.0005
```

Small number, because neural network parameter updates usually need to be careful.

Repo use: [matgpt/training/pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:200)

```python
lr = cosine_warmup_lr(...)
set_optimizer_lr(optimizer, lr)
```

Slow comments:

```python
# Decide the learning rate for this step.
lr = cosine_warmup_lr(...)

# Tell the optimizer to use that learning rate.
set_optimizer_lr(optimizer, lr)
```

**Questions**

1. In beginner terms, what does learning rate control?
2. What can happen if learning rate is too large?
3. What can happen if learning rate is too small?

**Exercise**

Which is the learning rate in this config?

```yaml
learning_rate: 3.0e-4
weight_decay: 0.1
grad_clip: 1.0
```

# **Lesson 42: Learning Rate Schedule**

Simplest explanation: the learning rate can change during training.

Instead of using one fixed step size forever, the repo does this:

```text
start small -> increase safely -> slowly decrease
```

Analogy: driving a car.

At the start, you accelerate carefully. In the middle, you move faster. Near the destination, you slow down so you do not overshoot.

Technical term: **learning rate schedule**.

Beginner meaning:

```text
learning rate schedule = a plan for changing the learning rate during training
```

Repo config: [configs/matgpt_mini_8m.yaml](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/configs/matgpt_mini_8m.yaml:79)

```yaml
learning_rate: 5.0e-4
min_learning_rate: 5.0e-5
warmup_ratio: 0.02
```

Slow meaning:

```text
learning_rate      = highest planned learning rate
min_learning_rate  = lowest final learning rate
warmup_ratio       = first small part of training used to warm up
```

Repo code: [matgpt/training/pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:200)

```python
lr = cosine_warmup_lr(...)
set_optimizer_lr(optimizer, lr)
```

Slow comments:

```python
# Decide the learning rate for this training step.
lr = cosine_warmup_lr(...)

# Give that learning rate to the optimizer.
set_optimizer_lr(optimizer, lr)
```

**Questions**

1. In beginner terms, what is a learning rate schedule?
2. Why might training start with a small learning rate?
3. What does `min_learning_rate` mean?

**Exercise**

Which value is the highest planned learning rate?

```yaml
learning_rate: 5.0e-4
min_learning_rate: 5.0e-5
warmup_ratio: 0.02
```


Correct.

Your answers:

```text
learning rate schedule = plan for changing learning rate during training
start small = safer beginning
min_learning_rate = lowest learning rate used near the end
highest planned learning rate = 5.0e-4
```

Good.

# **Lesson 43: Warmup**

Simplest explanation:

```text
warmup means starting with a small learning rate and gradually increasing it.
```

Analogy: before running fast, you warm up your body. You do not instantly sprint at full speed.

Training is similar. At the beginning, the model’s parameters are mostly random. Big updates too early can make training unstable.

Technical term:

```text
warmup = early training phase where learning rate rises gradually
```

Repo config:

```yaml
warmup_ratio: 0.02
```

Beginner meaning:

```text
Use the first 2% of training to warm up the learning rate.
```

Repo code: [matgpt/training/pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:187)

```python
warmup_steps = max(1, int(total_steps * cfg["training"]["warmup_ratio"]))
```

Slow comments:

```python
# total_steps = total number of training steps planned.
# warmup_ratio = fraction used for warmup.
# Example: 1000 steps * 0.02 = 20 warmup steps.
warmup_steps = max(1, int(total_steps * cfg["training"]["warmup_ratio"]))
```

Tiny example:

```text
total_steps = 1000
warmup_ratio = 0.02

warmup_steps = 1000 * 0.02 = 20
```

So the first 20 steps gradually increase the learning rate.

**Questions**

1. In beginner terms, what is warmup?
2. Why is warmup useful at the start of training?
3. If `total_steps = 2000` and `warmup_ratio = 0.05`, how many warmup steps?

**Exercise**

Compute:

```text
total_steps = 500
warmup_ratio = 0.10

warmup_steps = ?
```

Correct.

```text
total_steps = 3000
warmup_ratio = 0.02
warmup_steps = 3000 * 0.02 = 60
```

# **Lesson 44: Cosine Decay**

After warmup, the repo slowly lowers the learning rate.

Simplest explanation:

```text
warmup: learning rate goes up
decay: learning rate slowly goes down
```

Analogy: when driving toward a destination, you speed up at first, then slow down as you get closer so you do not overshoot.

Technical term: **cosine decay**.

Beginner meaning:

```text
cosine decay = a smooth plan for lowering the learning rate over time
```

Repo location: [matgpt/training/optim.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/optim.py:35)

```python
def cosine_warmup_lr(
    step: int,
    warmup_steps: int,
    total_steps: int,
    max_lr: float,
    min_lr: float,
) -> float:
```

Slow meaning:

```text
step         = current training step
warmup_steps = how long warmup lasts
total_steps  = full training length
max_lr       = highest learning rate
min_lr       = lowest learning rate
```

Important beginner idea:

```text
The function returns the learning rate for the current step.
```

Questions:

1. What happens to the learning rate during warmup?
2. What happens to the learning rate during decay?
3. Why might slowing down near the end of training be useful?

Exercise:

If:

```text
max_lr = 0.001
min_lr = 0.0001
```

which one is used as the higher learning rate?

Correct.

Small wording polish:

```text
warmup = learning rate increases
decay = learning rate decreases
slowing near the end helps avoid overshooting
```

And yes:

```text
max_lr = 0.001
min_lr = 0.0001
higher learning rate = 0.001
```

# **Lesson 45: One Training Step**

Now let’s connect the pieces.

Simplest explanation: one training step is one cycle of practice and improvement.

```text
1. get examples
2. make predictions
3. compute loss
4. compute gradients
5. update parameters
```

Repo location: [matgpt/training/pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:196)

Slow beginner version:

```python
# Put model in training mode.
train_model.train()

# Clear old gradients.
optimizer.zero_grad(set_to_none=True)

# Get x and y from the dataset.
x, y = train_dataset.sample_batch(...)

# Model predicts next-token logits and computes loss.
_, loss = train_model(x, targets=y)

# Compute gradients.
loss.backward()

# Update parameters.
optimizer.step()
```

The real repo has extra details like FP16 scaling and gradient accumulation, but the heart is:

```text
batch -> prediction -> loss -> gradients -> parameter update
```

Analogy: student practice.

```text
questions -> answers -> grade mistakes -> understand corrections -> improve
```

**Questions**

1. What are the five basic parts of one training step?
2. Why do we clear old gradients before computing new ones?
3. Which step changes the model parameters: `backward()` or `optimizer.step()`?

**Exercise**

Fill in the order:

```text
compute gradients
sample batch
update parameters
compute loss
make predictions
```

Correct order:

```text
1. ?
2. ?
3. ?
4. ?
5. ?
```


Good. Your ordering is correct.

Polished version:

```text
1. sample batch
2. make predictions
3. compute loss
4. compute gradients
5. update parameters
```

Your answer about clearing old gradients is also right:

```text
clear old gradients = start with a clean slate
```

And yes:

```text
backward() computes gradients
optimizer.step() changes parameters
```

Small correction to your “five parts” sentence: put loss before gradients.

```text
batch -> predictions -> loss -> gradients -> parameter update
```

# **Lesson 46: Gradient Accumulation**

Simplest explanation: sometimes one big batch does not fit in GPU memory. So the repo uses several smaller batches, collects their gradients, then updates once.

Analogy: instead of carrying one huge basket, you carry several small baskets to the same table, then count everything together.

Technical term: **gradient accumulation**.

Beginner meaning:

```text
gradient accumulation = collect gradients from multiple small batches before one optimizer update
```

Repo config:

```yaml
micro_batch_size: 16
gradient_accumulation_steps: 8
```

Meaning:

```text
Use 8 small batches before one parameter update.
```

Effective batch size:

```text
16 * 8 = 128 examples
```

Repo location: [matgpt/training/pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:209)

```python
for _ in range(cfg["training"]["gradient_accumulation_steps"]):
    x, y = train_dataset.sample_batch(cfg["training"]["micro_batch_size"], device)
    ...
    scaler.scale(scaled_loss).backward()
```

Slow meaning:

```text
Repeat several times:
1. get a small batch
2. compute loss
3. compute gradients
4. add those gradients to the current stored gradients
```

Then after the loop:

```python
scaler.step(optimizer)
```

Meaning:

```text
Now update parameters once using the accumulated gradients.
```

**Questions**

1. In beginner terms, what is gradient accumulation?
2. Why use several small batches instead of one huge batch?
3. If `micro_batch_size = 4` and `gradient_accumulation_steps = 8`, what is the effective batch size?

**Exercise**

Compute:

```text
micro_batch_size = 16
gradient_accumulation_steps = 4

effective batch size = ?
```


Correct.

```text
gradient accumulation = collect gradients from multiple small batches before one optimizer update
```

Correct.

```text
micro_batch_size = 4
gradient_accumulation_steps = 8
effective batch size = 4 * 8 = 32
```

Correct.

Exercise:

```text
micro_batch_size = 16
gradient_accumulation_steps = 4
effective batch size = 16 * 4 = 64
```

Correct.

# **Lesson 47: Tokens Per Step**

In language model training, we often measure progress by **tokens processed**, not just steps.

Simplest explanation:

```text
tokens per step = how many token positions the model trains on before one optimizer update
```

Formula:

```text
tokens_per_step = micro_batch_size * context_length * gradient_accumulation_steps
```

Why?

```text
micro_batch_size = examples per small batch
context_length = tokens per example
gradient_accumulation_steps = number of small batches before update
```

Repo location: [matgpt/training/pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:188)

```python
tokens_per_step = (
    cfg["training"]["micro_batch_size"]
    * cfg["model"]["context_length"]
    * cfg["training"]["gradient_accumulation_steps"]
)
```

Tiny example:

```text
micro_batch_size = 4
context_length = 8
gradient_accumulation_steps = 2

tokens_per_step = 4 * 8 * 2 = 64
```

Meaning:

```text
one optimizer update trains on 64 token positions
```

**Questions**

1. In beginner terms, what does `tokens_per_step` mean?
2. Why do we multiply by `context_length`?
3. If `micro_batch_size = 2`, `context_length = 10`, `gradient_accumulation_steps = 4`, what is `tokens_per_step`?

**Exercise**

Compute:

```text
micro_batch_size = 16
context_length = 256
gradient_accumulation_steps = 8

tokens_per_step = ?
```


Correct.

```text
micro_batch_size = 4
context_length = 512
gradient_accumulation_steps = 16

tokens_per_step = 4 * 512 * 16 = 32768
```

So:

```text
tokens_per_step = 32,768
```

# **Lesson 48: `max_tokens`**

Simplest explanation:

```text
max_tokens = total number of training tokens the run is aiming to process
```

If:

```text
tokens_per_step = 32,768
max_tokens = 200,000,000
```

then the run keeps training until it has processed about 200 million token positions.

Repo config:

```yaml
max_tokens: 200000000
```

Repo code:

```python
while state["global_step"] < total_steps and state["tokens_processed"] < cfg["training"]["max_tokens"]:
```

Beginner meaning:

```text
Keep training while we have not reached the planned number of steps
and have not reached the planned number of tokens.
```

Tiny formula:

```text
rough steps needed = max_tokens / tokens_per_step
```

**Questions**

1. In beginner terms, what does `max_tokens` mean?
2. If `tokens_per_step` is bigger, do we need more steps or fewer steps to reach the same `max_tokens`?
3. Why might LLM training measure progress in tokens instead of only steps?

**Exercise**

Compute rough steps:

```text
max_tokens = 1,000
tokens_per_step = 100

rough steps needed = ?
```

Correct.

Small typo polish:

```text
training, not traaing
tokens, not tokes
```

Your answers are right:

```text
max_tokens = maximum number of training tokens the run aims to process
bigger tokens_per_step = fewer steps needed
rough steps = 1000 / 100 = 10
```

# **Lesson 49: Validation Loss**

Simplest explanation:

```text
training loss tells us how well the model is doing on data it learns from.
validation loss tells us how well it does on separate data held aside for checking.
```

Analogy: homework vs exam.

```text
training data = homework practice
validation data = exam questions not used for practice
```

If the model improves on training data but gets worse on validation data, it may be memorizing instead of learning useful patterns.

Technical term: **validation loss**.

Beginner meaning:

```text
validation loss = mistake score on held-out checking data
```

Repo location: [matgpt/eval/lm.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/eval/lm.py:8)

```python
def evaluate_loss(model, dataset, batch_size, eval_batches, device, precision) -> float:
```

Slow comments:

```python
# This function checks model loss on a dataset.
# Usually this dataset is the validation dataset.
def evaluate_loss(...):
```

Inside it:

```python
model.eval()
```

Meaning:

```text
Put the model in evaluation mode.
We are checking it, not training it.
```

Then:

```python
x, y = dataset.sample_batch(batch_size, device)
_, loss = model(x, targets=y)
```

Meaning:

```text
Get validation examples.
Ask the model to predict.
Compute the mistake score.
```

Then:

```python
return sum(losses) / max(1, len(losses))
```

Meaning:

```text
Average the losses from several validation batches.
```

**Questions**

1. In beginner terms, what is validation loss?
2. Why do we use data held aside from training?
3. If training loss goes down but validation loss goes up, what might be happening?

**Exercise**

Which is better?

```text
Run A: validation loss = 2.0
Run B: validation loss = 3.5
```

Assume both are measured the same way.



Good work. Your answers are mostly correct.

Small correction: when training loss goes down but validation loss goes up, the model **is learning**, but it may be learning the training data too specifically. In beginner terms: it is getting good at the homework answers, but worse at a new exam. The technical term is **overfitting**.

# **Lesson 50: Overfitting**
Simplest explanation: overfitting means the model becomes too good at the examples it trained on, but not good enough on new examples.

Analogy: imagine memorizing exact practice questions instead of understanding the subject. You may score well on the practice sheet, but badly when the teacher changes the wording.

Technical term: **overfitting** = training loss improves, but validation loss stops improving or gets worse.

Where it appears in the repo:

[matgpt/eval/lm.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/eval/lm.py:12)

```python
@torch.no_grad()        # Do not train or compute gradients during evaluation.
def evaluate_loss(...):
    was_training = model.training

    model.eval()        # Put model in checking mode, not learning mode.
    losses = []

    for _ in range(eval_batches):
        x, y = dataset.sample_batch(batch_size, device)  # Get validation examples.
        _, loss = model(x, targets=y)                    # Measure how wrong it is.
        losses.append(float(loss.detach().cpu()))         # Store the loss number.

    if was_training:
        model.train()   # Put model back into training mode afterward.

    return sum(losses) / max(1, len(losses))  # Average validation loss.
```

And here:

[matgpt/training/pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:242)

```python
val_loss = evaluate_loss(
    model=train_model,
    dataset=val_dataset,       # Use validation data, not training data.
    batch_size=cfg["training"]["micro_batch_size"],
    eval_batches=cfg["training"]["eval_batches"],
    device=device,
    precision=cfg["training"]["precision"],
)

if val_loss < state["best_val_loss"]:     # Is this the best validation loss so far?
    state["best_val_loss"] = val_loss     # Remember the new best score.

    if cfg["training"]["save_best"]:
        save_checkpoint(... "best.pt" ...) # Save the best model checkpoint.
```

Tiny example:

```text
Step 1:
training loss = 4.0
validation loss = 4.2

Step 1000:
training loss = 1.0
validation loss = 5.0
```

The model got much better on training data, but worse on validation data. That is a warning sign for overfitting.

**Beginner Questions**
1. In beginner terms, what is overfitting?
2. If training loss goes down and validation loss also goes down, is that usually good or bad?
3. Why does the repo save `best.pt` when validation loss improves?

**Exercise**
Which run looks more likely to generalize better?

Run A:
training loss = 0.8
validation loss = 4.5

Run B:
training loss = 1.4
validation loss = 2.0

# **Lesson 51: Perplexity**

Simplest explanation: **perplexity is another way to read loss**. It tells us how “confused” the model is when choosing the next token.

Analogy: imagine a multiple-choice question. If you are choosing between 2 likely answers, you are less confused. If you are choosing between 50 likely answers, you are more confused. Perplexity is like the model’s “effective number of choices.”

Technical term: **perplexity** is calculated from loss:

```text
perplexity = exp(loss)
```

`exp` means “raise the number `e` to this power.” For now, just remember: **higher loss becomes higher perplexity**.

Where it appears in the repo:

[matgpt/eval/lm.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/eval/lm.py:42)

```python
def perplexity(loss: float) -> float:
    # Convert loss into perplexity.
    # min(loss, 50.0) prevents the number from becoming too huge.
    return math.exp(min(loss, 50.0))
```

And the training loop records it here:

[matgpt/training/pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:277)

```python
val_metrics = {
    "global_step": state["global_step"],      # Which training step we are at.
    "tokens_processed": state["tokens_processed"],  # How many tokens trained on.
    "val_loss": val_loss,                     # Mistake score on validation data.
    "val_perplexity": perplexity(val_loss),   # Confusion score from validation loss.
    "lr": lr,                                 # Current learning rate.
    "peak_memory_mb": _peak_memory_mb(device),
}
```

Tiny example:

```text
If loss = 0.69:
perplexity ≈ 2
Meaning: the model is roughly as confused as choosing between 2 likely tokens.

If loss = 1.39:
perplexity ≈ 4
Meaning: the model is roughly as confused as choosing between 4 likely tokens.
```

So:

```text
lower loss -> lower perplexity -> better
higher loss -> higher perplexity -> worse
```

**Beginner Questions**

1. In beginner terms, what does perplexity measure?
2. Is lower perplexity better or worse?
3. If validation loss goes down, what usually happens to validation perplexity?

**Exercise**

Which model is better?

```text
Model A:
validation loss = 1.0
validation perplexity = 2.7

Model B:
validation loss = 2.0
validation perplexity = 7.4
```

Reply with your answers, and I’ll check them before we move on.

# **Lesson 51: Perplexity**

Simplest explanation: **perplexity is another way to read loss**. It tells us how “confused” the model is when choosing the next token.

Analogy: imagine a multiple-choice question. If you are choosing between 2 likely answers, you are less confused. If you are choosing between 50 likely answers, you are more confused. Perplexity is like the model’s “effective number of choices.”

Technical term: **perplexity** is calculated from loss:

```text
perplexity = exp(loss)
```

`exp` means “raise the number `e` to this power.” For now, just remember: **higher loss becomes higher perplexity**.

Where it appears in the repo:

[matgpt/eval/lm.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/eval/lm.py:42)

```python
def perplexity(loss: float) -> float:
    # Convert loss into perplexity.
    # min(loss, 50.0) prevents the number from becoming too huge.
    return math.exp(min(loss, 50.0))
```

And the training loop records it here:

[matgpt/training/pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:277)

```python
val_metrics = {
    "global_step": state["global_step"],      # Which training step we are at.
    "tokens_processed": state["tokens_processed"],  # How many tokens trained on.
    "val_loss": val_loss,                     # Mistake score on validation data.
    "val_perplexity": perplexity(val_loss),   # Confusion score from validation loss.
    "lr": lr,                                 # Current learning rate.
    "peak_memory_mb": _peak_memory_mb(device),
}
```

Tiny example:

```text
If loss = 0.69:
perplexity ≈ 2
Meaning: the model is roughly as confused as choosing between 2 likely tokens.

If loss = 1.39:
perplexity ≈ 4
Meaning: the model is roughly as confused as choosing between 4 likely tokens.
```

So:

```text
lower loss -> lower perplexity -> better
higher loss -> higher perplexity -> worse
```

**Beginner Questions**

1. In beginner terms, what does perplexity measure?
2. Is lower perplexity better or worse?
3. If validation loss goes down, what usually happens to validation perplexity?

**Exercise**

Which model is better?

```text
Model A:
validation loss = 1.0
validation perplexity = 2.7

Model B:
validation loss = 2.0
validation perplexity = 7.4
```

Reply with your answers, and I’ll check them before we move on.


# **Lesson 52: Generated Samples**

Simplest explanation: a **generated sample** is text the model writes so we can inspect how it is behaving.

Loss and perplexity are numbers. They are useful, but they do not show us what the model actually says.

Analogy: imagine a student gets a math score of 80%. That number helps, but you may still want to read the student’s written work. Maybe the answer is right but the reasoning is messy. Generated samples are like reading the model’s written work.

Technical term: **generation** means the model starts from some text, predicts the next token, adds it, then predicts the next token again, and keeps going.

Where it appears in the repo:

[configs/matgpt_mini_8m.yaml](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/configs/matgpt_mini_8m.yaml:97)

```yaml
evaluation:
  max_new_tokens: 120        # Let the model add up to 120 new tokens.
  temperature: 0.8           # Controls how random the choices are.
  top_k: 50                  # Limit choices to likely tokens.
  top_p: 0.95                # Another way to limit choices to likely tokens.
  prompts:
    - "Once upon a time"     # Starting text for the model.
    - "The little dog wanted to"
    - "Lily found a small box"
```

A **prompt** is the starting text we give the model.

The training loop uses those prompts here:

[matgpt/training/pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:300)

```python
if _is_due(state["tokens_processed"], cfg["training"]["sample_interval_tokens"], tokens_per_step):
    # If enough training tokens have passed, generate sample text.
    samples = generate_samples(
        model=train_model,                         # The model being trained.
        tokenizer=tokenizer,                       # Converts text <-> token IDs.
        prompts=cfg["evaluation"]["prompts"],      # Starting texts from config.
        max_new_tokens=cfg["evaluation"]["max_new_tokens"],
        eos_id=eos_id,                             # Stop if end token appears.
        temperature=cfg["evaluation"]["temperature"],
        top_k=cfg["evaluation"]["top_k"],
        top_p=cfg["evaluation"]["top_p"],
        device=device,
    )

    # Save the generated text to a samples JSON file.
    _write_samples(sample_dir / f"samples_{state['tokens_processed']:012d}.json", samples, dict(state))
```

And the sample function is here:

[matgpt/eval/lm.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/eval/lm.py:46)

```python
@torch.no_grad()
def generate_samples(...):
    samples = []  # Store generated outputs here.

    for prompt in prompts:
        # Convert prompt text into token IDs.
        input_ids = torch.tensor([tokenizer.encode(prompt).ids], dtype=torch.long, device=device)

        # Ask the model to continue the prompt.
        output = generate(...)

        # Convert output token IDs back into readable text.
        samples.append({
            "prompt": prompt,
            "text": tokenizer.decode(output[0].detach().cpu().tolist()),
        })

    return samples
```

Tiny example:

```text
Prompt:
"Once upon a time"

Possible generated sample:
"Once upon a time there was a small girl who found a red ball."
```

The sample lets us ask: is the model forming words, staying on topic, repeating itself, or producing nonsense?

**Beginner Questions**

1. In beginner terms, why do we generate sample text during training?
2. Is generated text a number like loss, or readable text we inspect?
3. Does `@torch.no_grad()` mean we are training the model or just checking it?

**Exercise**

Using this config idea:

```yaml
sample_interval_tokens: 5000000
max_new_tokens: 120
prompts:
  - "Once upon a time"
```

In your own words, what will the repo do every `5,000,000` training tokens?


Your answers are correct.

Small cleanup: generated samples help us see whether the model is producing **coherent readable text** or nonsense. And yes, every `5,000,000` training tokens, the repo uses the prompt, generates up to `120` new tokens, and saves the sample text.

# **Lesson 53: Checkpoints**

Simplest explanation: a **checkpoint** is a saved copy of the training progress.

Analogy: imagine playing a long video game. You save your game so if the computer shuts down, you do not start from the beginning. Training an LLM is similar: it can take hours or days, so we save progress.

Technical term: a **checkpoint** is a file that stores the model’s learned numbers and training state.

Where it appears in the repo:

[matgpt/training/checkpoint.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/checkpoint.py:33)

```python
payload = {
    "model": model.state_dict(),        # The model's learned parameters.
    "optimizer": optimizer.state_dict(),# Optimizer memory, not just model weights.
    "scaler": scaler.state_dict(),      # Mixed precision training state.
    "state": state,                     # Step count, tokens processed, best loss.
    "config": config,                   # Settings used for this run.
    "extra": extra or {},               # Metadata like hashes and parameter count.
    "rng_state": capture_rng_state(),   # Random-number state for reproducibility.
}
```

Beginner translation: the checkpoint does not only save “the model.” It also saves enough surrounding information to continue training safely.

The repo saves `best.pt` here:

[matgpt/training/pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:287)

```python
if val_loss < state["best_val_loss"]:
    # If this validation loss is the best so far,
    # remember it and save a best checkpoint.
    state["best_val_loss"] = val_loss

    if cfg["training"]["save_best"]:
        save_checkpoint(checkpoint_dir / "best.pt", ...)
```

And it saves `latest.pt` here:

[matgpt/training/pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:318)

```python
if _is_due(state["tokens_processed"], cfg["training"]["checkpoint_interval_tokens"], tokens_per_step):
    # Save the most recent training progress.
    save_checkpoint(checkpoint_dir / "latest.pt", ...)
```

Tiny example:

```text
latest.pt = where training most recently stopped
best.pt   = the checkpoint with the best validation loss so far
```

So if training crashes, you usually resume from `latest.pt`.
If you want to evaluate or use the best model, you usually use `best.pt`.

**Beginner Questions**

1. In beginner terms, what is a checkpoint?
2. What is the difference between `latest.pt` and `best.pt`?
3. Why is it useful to save optimizer state too, not only model parameters?

**Exercise**

Which checkpoint would you use?

```text
A. Training crashed and you want to continue from the most recent progress.
B. Training finished and you want to evaluate the best validation model.
```

Answer like:

```text
A -> ?
B -> ?
```

Your answers are correct, with two small refinements:

- The filenames are `latest.pt` and `best.pt`, not `.py`.
- `latest.pt` contains the most recently **saved** progress. Because checkpoints are saved periodically, it might be slightly earlier than the exact moment training stopped.

The optimizer answer is partly correct. Saving its state allows a smoother restart because the optimizer remembers information from earlier updates, including its step count and moving averages of previous gradients. Without that memory, the model parameters resume, but the optimizer behaves as though it has just started.

Exercise answers:

```text
A -> latest.pt
B -> best.pt
```

# Lesson 54: Resuming Training

<!-- ### 1. Simplest Explanation -->

Resuming means loading saved training progress and continuing from there.

The model does not have to restart its learning from zero.

<!-- ### 2. Analogy -->

Imagine reading a 500-page book.

A checkpoint is your bookmark. Resuming means opening the book at the bookmark instead of returning to page 1.

<!-- ### 3. Technical Term -->

Loading a checkpoint and continuing training is called **resuming training**.

<!-- ### 4. Where It Appears -->
<!--  -->
The command-line option appears in [scripts/pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/scripts/pretrain.py:18):

```python
# Let the user provide a checkpoint file.
parser.add_argument(
    "--resume-from",
    default=None,
    help="Full checkpoint path to resume from.",
)
```

You might run:

```bash
uv run python scripts/pretrain.py \
  --config configs/matgpt_mini_8m.yaml \
  --resume-from path/to/latest.pt
```

<!-- ### 5. How the Checkpoint Is Loaded -->

In [pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:174):

```python
# Default state for completely new training.
state = {
    "global_step": 0,
    "tokens_processed": 0,
    "best_val_loss": float("inf"),
}

# Did the user provide a checkpoint?
if resume_from is not None:
    payload = load_checkpoint(
        resume_from,       # File to load.
        model=model,       # Restore learned model parameters.
        optimizer=optimizer, # Restore optimizer memory.
        scaler=scaler,     # Restore numerical-scaling information.
        map_location=device, # Load onto the current CPU or GPU.
        restore_rng=True,  # Restore random-number progress.
    )

    # Restore step number, token count, and best validation loss.
    state.update(payload["state"])
```

We will explain `scaler` and `RNG` separately later. For now, the key idea is that resuming restores more than model parameters.

<!-- ### 6. Tiny Example -->

Suppose the checkpoint says:

```text
global_step = 2,000
tokens_processed = 65,536,000
best_val_loss = 2.1
```

After loading it, training continues around step `2,001`, rather than step `1`.

<!-- ### 7. Beginner Questions -->

1. In beginner terms, what does resuming training mean?
2. Does resuming from `latest.pt` normally start at step zero?
3. Name two things restored from the checkpoint.

<!-- ### 8. Exercise -->

A checkpoint contains:

```text
global_step = 500
tokens_processed = 1,000,000
```

After loading it, should training behave as though it has processed:

```text
A. 0 tokens
B. 1,000,000 tokens
```

Explain your answer in one sentence.

Your answers are correct.

A clearer exercise explanation would be:

> **B**, because the checkpoint restores `tokens_processed = 1,000,000`, so training continues from that recorded progress.

“Model parameters and optimizer” is also correct. More precisely: **model parameters** and **optimizer state**.

# Lesson 55: Why Training Uses Randomness

### 1. Simplest Explanation

The dataset may contain millions of token sequences. The model usually does not read them in exactly the same order every time.

Instead, the training code randomly chooses examples for each batch.

### 2. Analogy

Imagine studying with flashcards.

If you always study the cards in exactly the same order, you may memorize their order. Shuffling the cards helps you learn the information itself.

Training data is shuffled or sampled for a similar reason.

### 3. Technical Term

A **random number generator**, shortened to **RNG**, produces numbers that the program uses to make random choices.

The repository uses an RNG to choose:

- Which data shard to read.
- Where inside that shard to begin a training sequence.

### 4. Where It Appears

This happens in [dataset.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/dataset.py:60).

### 5. Code Explained Slowly

```python
# Randomly choose which data shard each batch example comes from.
shard_indices = self.rng.choice(
    len(self.shards),    # Number of available shards.
    size=batch_size,     # Choose one shard for each batch row.
    p=self.weights,      # Larger shards have a greater chance.
)

# Randomly choose a starting token position inside the selected shard.
start = int(
    self.rng.integers(
        0,
        shard.num_tokens - self.context_length - 1,
    )
)
```

A **shard** is one piece of a large dataset. We will study shards deeply in a later data lesson.

### 6. Tiny Example

Suppose a shard contains:

```text
[10, 25, 33, 4, 7, 20, 45, 4]
```

With `context_length = 3`, the RNG might choose `start = 2`.

The selected window becomes:

```text
[33, 4, 7, 20]
```

Then:

```text
x = [33, 4, 7]
y = [4, 7, 20]
```

Another random choice might start somewhere else.

### 7. Beginner Questions

1. In beginner terms, why does training randomly choose examples?
2. What does RNG stand for?
3. What two choices does the dataset’s RNG make?
4. Does randomness change the original stored dataset, or only choose where to read from it?

### 8. Exercise

Given:

```text
tokens = [10, 20, 30, 40, 50, 60]
context_length = 2
start = 1
```

The selected window needs `context_length + 1 = 3` tokens.

Fill in:

```text
window = ?
x = ?
y = ?
```

Your answers and exercise are correct.

One refinement:

> Random sampling gives the model varied examples and prevents it from depending on a fixed data order.

It can **reduce** order-based memorization, but it cannot guarantee that the model will not overfit. Overfitting is still possible.

# Lesson 56: Random Seeds

### 1. Simplest Explanation

A computer’s “random” choices usually come from a repeatable process.

A **seed** is the starting number for that process.

When we use the same seed under the same conditions, the computer will usually make the same sequence of random choices.

### 2. Analogy

Imagine a card-shuffling machine with numbered instructions:

```text
Instruction 42 -> shuffle the cards in this particular order
Instruction 7  -> shuffle them in a different order
```

Using instruction `42` again produces the same shuffle.

The seed acts like that instruction number.

### 3. Technical Term

This is called a **random seed**.

Computer-generated randomness is often called **pseudorandomness** because it looks random but comes from a repeatable mathematical process.

### 4. Where It Appears

The Mini model uses seed `42` in [matgpt_mini_8m.yaml](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/configs/matgpt_mini_8m.yaml:3):

```yaml
run:
  seed: 42
```

The seed is applied in [seed.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/utils/seed.py:10).

### 5. Code Explained Slowly

```python
def set_seed(seed: int, deterministic: bool = False) -> None:
    # Give Python's random-number system the starting seed.
    random.seed(seed)

    # Give NumPy's random-number system the same seed.
    np.random.seed(seed)

    # Give PyTorch's CPU random-number system the same seed.
    torch.manual_seed(seed)

    # If a GPU is available, seed its random-number systems too.
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
```

Several systems are seeded because Python, NumPy, and PyTorch each have their own random-number generators.

### 6. Tiny Example

Imagine a fake RNG:

```text
seed 42 -> 3, 8, 1, 6
seed 42 -> 3, 8, 1, 6
seed 7  -> 9, 2, 5, 4
```

The numbers look random, but the same seed produces the same sequence.

This helps us repeat experiments and investigate problems.

Using the same seed improves repeatability, but exact results can still differ when hardware, code, settings, or some GPU operations differ.

### 7. Beginner Questions

1. In beginner terms, what is a random seed?
2. What usually happens when two runs use the same seed under the same conditions?
3. Why does the repo seed Python, NumPy, and PyTorch separately?
4. Does using the same seed guarantee identical results under every possible condition?

### 8. Exercise

Suppose:

```text
seed 10 -> batch starting positions [5, 20, 8]
seed 25 -> batch starting positions [9, 2, 30]
```

Fill in:

```text
Run A uses seed 10 -> ?
Run B uses seed 10 -> ?
Run C uses seed 25 -> ?
```

Which two runs should choose the same starting positions?

All your answers are correct. The exercise is:

```text
Run A -> [5, 20, 8]
Run B -> [5, 20, 8]
Run C -> [9, 2, 30]

Same positions: A and B
```

One precision: the same seed normally produces the same **random choices** under the same conditions. Exact training results can still vary because of hardware and certain GPU operations.

# Lesson 57: RNG State

### 1. Simplest Explanation

A seed tells an RNG where to **start**.

The **RNG state** tells us where the RNG has currently reached after making several random choices.

### 2. Analogy

Imagine a playlist:

```text
Song 1 -> Song 2 -> Song 3 -> Song 4
```

The seed chooses the playlist. The RNG state acts like a bookmark showing that you are currently at Song 3.

Restarting with only the seed returns to Song 1. Restoring the state continues from Song 3.

### 3. Technical Term

The RNG’s current saved position and internal information are called its **random number generator state**, or **RNG state**.

### 4. Where It Appears

The repo captures RNG state in [checkpoint.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/checkpoint.py:12).

### 5. Code Explained Slowly

```python
def capture_rng_state() -> dict[str, Any]:
    state = {
        # Save Python RNG's current position.
        "python": random.getstate(),

        # Save NumPy RNG's current position.
        "numpy": np.random.get_state(),

        # Save PyTorch CPU RNG's current position.
        "torch_cpu": torch.get_rng_state(),
    }

    # Save GPU RNG state when a GPU is being used.
    if torch.cuda.is_available():
        state["torch_cuda"] = torch.cuda.get_rng_state_all()

    return state
```

The state is placed inside every checkpoint:

```python
payload = {
    # Other checkpoint information...
    "rng_state": capture_rng_state(),
}
```

When resuming, the repo restores it:

```python
if restore_rng:
    restore_rng_state(payload.get("rng_state"))
```

### 6. Tiny Example

Suppose seed `42` produces:

```text
5, 8, 2, 9, 4
```

Training already used:

```text
5, 8, 2
```

If we restore the saved RNG state, the next number should be:

```text
9
```

If we only restart from seed `42`, the RNG returns to the beginning, and the next number becomes:

```text
5
```

### 7. Beginner Questions

1. What is the difference between an RNG seed and RNG state?
2. Why does a checkpoint save RNG state?
3. After restoring the state, should random choices continue from the saved position or restart at the beginning?
4. Does the repo save only Python’s RNG state?

### 8. Exercise

An RNG sequence is:

```text
10, 30, 20, 50, 40
```

Training has already used:

```text
10, 30, 20
```

Fill in:

```text
Next number after restoring RNG state = ?
Next number after restarting from the original seed = ?
```

All your answers are correct. The exercise is:

```text
Run A -> [5, 20, 8]
Run B -> [5, 20, 8]
Run C -> [9, 2, 30]

Same positions: A and B
```

One precision: the same seed normally produces the same **random choices** under the same conditions. Exact training results can still vary because of hardware and certain GPU operations.

# Lesson 57: RNG State

### 1. Simplest Explanation

A seed tells an RNG where to **start**.

The **RNG state** tells us where the RNG has currently reached after making several random choices.

### 2. Analogy

Imagine a playlist:

```text
Song 1 -> Song 2 -> Song 3 -> Song 4
```

The seed chooses the playlist. The RNG state acts like a bookmark showing that you are currently at Song 3.

Restarting with only the seed returns to Song 1. Restoring the state continues from Song 3.

### 3. Technical Term

The RNG’s current saved position and internal information are called its **random number generator state**, or **RNG state**.

### 4. Where It Appears

The repo captures RNG state in [checkpoint.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/checkpoint.py:12).

### 5. Code Explained Slowly

```python
def capture_rng_state() -> dict[str, Any]:
    state = {
        # Save Python RNG's current position.
        "python": random.getstate(),

        # Save NumPy RNG's current position.
        "numpy": np.random.get_state(),

        # Save PyTorch CPU RNG's current position.
        "torch_cpu": torch.get_rng_state(),
    }

    # Save GPU RNG state when a GPU is being used.
    if torch.cuda.is_available():
        state["torch_cuda"] = torch.cuda.get_rng_state_all()

    return state
```

The state is placed inside every checkpoint:

```python
payload = {
    # Other checkpoint information...
    "rng_state": capture_rng_state(),
}
```

When resuming, the repo restores it:

```python
if restore_rng:
    restore_rng_state(payload.get("rng_state"))
```

### 6. Tiny Example

Suppose seed `42` produces:

```text
5, 8, 2, 9, 4
```

Training already used:

```text
5, 8, 2
```

If we restore the saved RNG state, the next number should be:

```text
9
```

If we only restart from seed `42`, the RNG returns to the beginning, and the next number becomes:

```text
5
```

### 7. Beginner Questions

1. What is the difference between an RNG seed and RNG state?
2. Why does a checkpoint save RNG state?
3. After restoring the state, should random choices continue from the saved position or restart at the beginning?
4. Does the repo save only Python’s RNG state?

### 8. Exercise

An RNG sequence is:

```text
10, 30, 20, 50, 40
```

Training has already used:

```text
10, 30, 20
```

Fill in:

```text
Next number after restoring RNG state = ?
Next number after restarting from the original seed = ?
```

Your answers are correct.

The exercise is exactly right:

```text
Next after restoring RNG state = 50
Next after restarting from seed = 10
```

One refinement: a checkpoint saves RNG state specifically so resumed training continues making random choices from the same saved position. “Save progress” is correct, but this explains which progress is being preserved.

# Lesson 58: Dataset RNG State

### 1. Simplest Explanation

The training dataset and validation dataset each have their own random-number generator.

That means each dataset has its own random-choice progress to save.

### 2. Analogy

Imagine two people reading different books:

```text
Training reader   -> bookmark at page 80
Validation reader -> bookmark at page 25
```

Saving only one bookmark would lose the other reader’s position.

### 3. Technical Term

These are **independent RNG states**.

The training RNG tracks random training examples. The validation RNG tracks random validation examples.

### 4. Where It Appears

The dataset creates its RNG in [dataset.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/dataset.py:31):

```python
# Create this dataset's own random-number generator.
self.rng = np.random.default_rng(seed)
```

### 5. Code Explained Slowly

The dataset can return its current RNG position:

```python
def get_rng_state(self):
    # Read this dataset RNG's current internal position.
    return self.rng.bit_generator.state
```

It can also restore a saved position:

```python
def set_rng_state(self, state):
    # Move this dataset RNG back to its saved position.
    self.rng.bit_generator.state = state
```

The training code saves both dataset states in [pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:108):

```python
checkpoint_state["dataset_rng_state"] = {
    # Save random sampling progress for training data.
    "train": train_dataset.get_rng_state(),

    # Save random sampling progress for validation data.
    "validation": val_dataset.get_rng_state(),
}
```

### 6. Tiny Example

Suppose the next choices should be:

```text
Training dataset   -> start position 500
Validation dataset -> start position 90
```

After restoring both RNG states, each dataset continues with its own correct next choice.

### 7. Beginner Questions

1. Why do the training and validation datasets need separate RNG states?
2. What does `get_rng_state()` do?
3. What does `set_rng_state(state)` do?
4. Why would saving only the training dataset’s RNG state be incomplete?

### 8. Exercise

A checkpoint records:

```text
Training RNG next position   = 700
Validation RNG next position = 120
```

After restoring the checkpoint, fill in:

```text
Next training position = ?
Next validation position = ?
```

Should both datasets continue from the same position? Explain briefly.

Most answers are correct. One important correction:

```text
get_rng_state() -> reads/returns the RNG’s current progress
set_rng_state(state) -> restores the RNG to provided saved progress
```

`set_rng_state()` does not save the state. The checkpoint code handles saving it.

Your exercise is correct:

```text
Next training position = 700
Next validation position = 120
```

They should not continue from the same position because they are separate datasets with separate RNGs.

# Lesson 59: Reproducibility

### 1. Simplest Explanation

Reproducibility means being able to repeat a training experiment and obtain the same or very similar results.

### 2. Analogy

Imagine following a cake recipe.

To reproduce the same cake, you need the same:

- Ingredients
- Measurements
- Oven settings
- Cooking steps

Using only the same oven temperature is not enough.

Similarly, using only the same random seed is not enough to reproduce training completely.

### 3. Technical Term

The ability to repeat an experiment reliably is called **reproducibility**.

Exact identical results are called **determinism**. We will study that separately.

### 4. Where It Appears

The repo starts its random systems from the configured seed in [pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:134):

```python
# Start random systems from the configured seed.
set_seed(cfg["run"]["seed"])
```

It gives the two datasets predictable but different seeds:

```python
train_dataset = PackedTokenDataset.from_metadata(
    ...,
    seed=cfg["run"]["seed"],      # For example: 42
)

val_dataset = PackedTokenDataset.from_metadata(
    ...,
    seed=cfg["run"]["seed"] + 1,  # For example: 43
)
```

Training might therefore use seed `42`, while validation uses seed `43`.

### 5. Why Different Dataset Seeds?

The datasets should make separate random choices, but those choices should still be repeatable.

```text
Training seed   = 42
Validation seed = 43
```

This prevents both datasets from sharing the exact same random-number sequence.

### 6. Tiny Example

Run A uses:

```text
code version = 1
dataset = A
seed = 42
configuration = X
```

Run B uses exactly the same setup. Its results should usually be reproducible.

Run C changes the dataset. Even with seed `42`, it is no longer the same experiment.

### 7. Beginner Questions

1. In beginner terms, what does reproducibility mean?
2. Is using the same seed alone enough to reproduce an entire experiment?
3. Why does validation use `seed + 1`?
4. What is the difference between reproducibility and exact determinism?

### 8. Exercise

Compare these runs:

```text
Run A: dataset X, config Y, code version 1, seed 42
Run B: dataset X, config Y, code version 1, seed 42
Run C: dataset X, config Y, code version 1, seed 99
```

Answer:

```text
Which two runs are set up to be the most reproducible?
What changed in the remaining run?
```

All your answers are correct.

A slightly fuller answer for validation is:

> Validation uses `seed + 1` so it has a different but still repeatable random sequence from training.

Your reproducibility versus determinism distinction is also accurate.

# Lesson 60: Deterministic Training

### 1. Simplest Explanation

Deterministic training means that repeating the same calculation with the same inputs should produce exactly the same result.

### 2. Analogy

Imagine two machines:

- Machine A always follows one fixed route.
- Machine B may choose whichever route is fastest.

Both reach the destination, but Machine B’s exact path may vary.

Deterministic training asks the computer to follow repeatable calculation routes.

### 3. Technical Term

A **deterministic algorithm** produces the same output whenever it receives the same input under the same conditions.

Some fast GPU calculations are not strictly deterministic.

### 4. Where It Appears

The option appears in [seed.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/utils/seed.py:10):

```python
def set_seed(seed: int, deterministic: bool = False):
```

`deterministic=False` means strict deterministic behavior is disabled by default.

### 5. Code Explained Slowly

```python
if deterministic:
    # Ask PyTorch to prefer repeatable calculation methods.
    torch.use_deterministic_algorithms(
        True,
        warn_only=True,
    )

    # Disable automatic searching for the fastest GPU method.
    torch.backends.cudnn.benchmark = False
else:
    # Allow PyTorch to search for faster GPU methods.
    torch.backends.cudnn.benchmark = True
```

`warn_only=True` means PyTorch gives a warning when an operation may not be deterministic instead of immediately stopping the program.

The training code calls:

```python
set_seed(cfg["run"]["seed"])
```

It does not pass `deterministic=True`. Therefore, this repo uses seeds for repeatability but does not enable its strict deterministic mode by default.

### 6. Why Not Always Enable It?

Deterministic operations can sometimes be:

- Slower
- Less optimized
- Unavailable for certain calculations

There is often a tradeoff between exact repeatability and training speed.

Even deterministic settings may depend on using the same hardware, software versions, and environment.

### 7. Tiny Example

```text
Normal mode:
Run A loss = 2.314201
Run B loss = 2.314205

Deterministic mode:
Run A loss = 2.314201
Run B loss = 2.314201
```

The normal results are extremely close, while the deterministic results are exactly equal in this simplified example.

### 8. Beginner Questions

1. In beginner terms, what does deterministic mean?
2. Does the repo enable strict deterministic mode by default?
3. Why might deterministic training be slower?
4. Can the same seed help reproducibility without guaranteeing exact determinism?

### 9. Exercise

Choose the better mode for each situation:

```text
A. You are debugging a small test and need the results to repeat exactly.
B. You are doing a long training run and maximum speed is more important.
```

Fill in:

```text
A -> deterministic or normal?
B -> deterministic or normal?
```

All your answers are correct.

Your determinism definition is especially good:

> The same input produces the same result every time.

# Lesson 61: Checkpoint Compatibility

### 1. Simplest Explanation

A checkpoint should normally be resumed using the same model setup, tokenizer, and dataset that created it.

Otherwise, the saved model numbers may no longer match the new training setup.

### 2. Analogy

Imagine saving progress in one edition of a game and loading it into a completely different edition.

A saved location called `room 25` might mean:

```text
Old edition: kitchen
New edition: basement
```

The save file’s numbers still exist, but they now mean different things.

### 3. Technical Terms

A training **artifact** is an important file or piece of data used during training, such as:

- Configuration
- Tokenizer
- Dataset manifest

**Compatibility** means those artifacts correctly match the checkpoint.

A **hash** is a calculated digital fingerprint. If a file changes, its hash usually changes too.

### 4. Where It Appears

The repo records fingerprints in [pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:166):

```python
extra = {
    # Fingerprint of the training configuration.
    "config_sha256": sha256_text(config_to_yaml(cfg)),

    # Fingerprint of the tokenizer.
    "tokenizer_sha256": tokenizer_metadata["tokenizer_sha256"],

    # Fingerprint representing the prepared dataset.
    "dataset_manifest_hash": _optional_file_hash(
        Path(cfg["dataset"]["normalized_dir"]) / "manifest.json"
    ),
}
```

`SHA-256` is the particular fingerprint calculation being used.

### 5. Checking Before Resume

```python
for key in (
    "config_sha256",
    "tokenizer_sha256",
    "dataset_manifest_hash",
):
    checkpoint_value = checkpoint_extra.get(key)
    current_value = expected_extra.get(key)

    # Different fingerprints mean something changed.
    if checkpoint_value != current_value:
        mismatches.append(key)

# Stop instead of performing an unsafe resume.
if mismatches:
    raise ValueError("Checkpoint artifact mismatch")
```

The configuration sets `allow_artifact_mismatch: false`, so mismatches are rejected by default.

### 6. Tiny Example

Suppose the old tokenizer says:

```text
token ID 25 -> " dog"
```

A different tokenizer says:

```text
token ID 25 -> " airplane"
```

The checkpoint learned that ID `25` means `" dog"`. Resuming with the new tokenizer would incorrectly treat its learned information as relating to `" airplane"`.

### 7. Beginner Questions

1. In beginner terms, what does checkpoint compatibility mean?
2. What is a hash?
3. Which three fingerprints does the repo compare?
4. Why can changing the tokenizer make checkpoint resuming unsafe?

### 8. Exercise

Checkpoint fingerprints:

```text
config    = ABC
tokenizer = DEF
dataset   = GHI
```

Current fingerprints:

```text
config    = ABC
tokenizer = XYZ
dataset   = GHI
```

Answer:

```text
Which artifact changed?
Should the repo normally allow the resume?
Why?
```

Your exercise is correct. The tokenizer changed, so the repo should normally refuse to resume.

Two refinements:

- The three fingerprints are **configuration**, **tokenizer**, and **dataset manifest**.
- A tokenizer mismatch is dangerous because the same token ID may represent different text. The checkpoint’s learned embeddings would then be attached to the wrong tokens.

Your hash explanation is good. More precisely, a hash is the fixed-size fingerprint produced by a hashing algorithm. This repo uses SHA-256.

# Lesson 62: What Is a Corpus?

### 1. Simplest Explanation

Before training, we need a large collection of text for the model to learn from.

### 2. Analogy

Imagine teaching someone to write stories by giving them a library containing thousands of stories.

Each story is one document. The entire library is the corpus.

### 3. Technical Terms

A **document** is one piece of text, such as one story or article.

A **corpus** is the complete collection of documents used for language training.

A **dataset** is an organized collection of data. In this project, the dataset contains text documents.

### 4. Where It Appears

The Mini model uses TinyStories, configured in [matgpt_mini_8m.yaml](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/configs/matgpt_mini_8m.yaml:17):

```yaml
dataset:
  # Name of the source dataset.
  hf_name: roneneldan/TinyStories

  # The field containing the actual story text.
  text_field: text

  # Names of the training and validation collections.
  train_split: train
  validation_split: validation
```

`hf_name` identifies a dataset available through Hugging Face, a platform and software library for sharing machine-learning datasets.

### 5. Creating One Document Record

In [prepare.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/data/prepare.py:34):

```python
def make_document_record(dataset_name, split, index, text, source_id=None):
    # Clean and standardize the document's text.
    normalized = normalize_text(text)

    # Choose an identifier for this source document.
    source = str(source_id) if source_id is not None else str(index)

    return {
        # Unique name for this document.
        "id": f"{dataset_name}/{split}/{source}",

        # Dataset from which the document came.
        "dataset": dataset_name,

        # Whether this is training or validation data.
        "split": split,

        # The cleaned text used later in the pipeline.
        "text": normalized,

        # Number of characters in the cleaned text.
        "num_chars": len(normalized),
    }
```

### 6. Tiny Example

Raw corpus:

```text
Document 1: "The cat slept."
Document 2: "A dog ran home."
```

Prepared records might contain:

```text
Record 1: id=TinyStories/train/1, text="The cat slept."
Record 2: id=TinyStories/train/2, text="A dog ran home."
```

Together, those two documents form a tiny corpus.

### 7. Beginner Questions

1. What is a document?
2. What is a corpus?
3. What does `text_field: text` tell the preparation code?
4. Why does each document need an ID?

### 8. Exercise

Given:

```text
Story 1: "Lily found a box."
Story 2: "Sam opened the door."
Story 3: "The dog was happy."
```

Answer:

```text
How many documents are there?
What is the corpus?
Is one story alone the complete corpus in this example?
```

Your first, second, and third answers are correct.

For the document ID, your idea is right. A clearer answer is:

> Each document needs an ID so the pipeline can uniquely identify, track, debug, and trace it back to its source.

Exercise correction:

```text
Number of documents = 3
Corpus = all three stories together
One story alone = not the complete corpus
```

# Lesson 63: JSONL Files

### 1. Simplest Explanation

After preparing the documents, the repo stores them in a text file.

Each line of the file represents one document.

### 2. Analogy

Imagine a notebook where each line contains one completed form:

```text
Line 1: Form for Story 1
Line 2: Form for Story 2
Line 3: Form for Story 3
```

Each form contains labeled information such as the document ID and text.

### 3. Technical Terms

**JSON** is a text format that stores labeled values:

```json
{"id": "story-1", "text": "The cat slept."}
```

Here:

```text
"id"   -> label
"story-1" -> value
"text" -> label
"The cat slept." -> value
```

**JSONL** means JSON Lines. It stores one JSON object on each line.

### 4. Where It Appears

The repo writes JSONL in [prepare.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/data/prepare.py:110).

### 5. Code Explained Slowly

```python
# Open the output file for writing text.
with out.open("w", encoding="utf-8") as f:

    # Process one document record at a time.
    for record in records:

        # Convert the Python record into JSON text.
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)

        # Write the JSON, followed by a newline.
        f.write(line + "\n")

        # Count the document that was written.
        document_count += 1
```

The newline `"\n"` ends the current line so the next document begins on a new line.

### 6. Tiny Example

A two-document JSONL file could contain:

```json
{"id":"story-1","text":"The cat slept."}
{"id":"story-2","text":"The dog ran."}
```

This file has:

```text
2 lines
2 JSON records
2 documents
```

JSONL is useful because the program can process one document at a time without loading the entire corpus into memory.

### 7. Beginner Questions

1. What does JSON store?
2. What does JSONL mean?
3. How many documents normally appear on one JSONL line?
4. Why does the code add `"\n"` after each record?

### 8. Exercise

Given this JSONL:

```json
{"id":"doc-1","text":"Hello world."}
{"id":"doc-2","text":"The sun is bright."}
{"id":"doc-3","text":"Sam likes pizza."}
```

Answer:

```text
How many JSONL lines are there?
How many documents are there?
What is the ID of the second document?
What is the text of the third document?
```

All your answers are correct.

A small wording improvement:

> JSONL stores each record on a separate line. `"\n"` ends the current line so the next record starts on a new line.

# Lesson 64: Filtering Text That Is Too Short

### 1. Simplest Explanation

Not every document is useful for training.

A document containing only `"Hi"` or an empty string may provide too little language for the model to learn from. The repo can reject documents that are too short.

### 2. Analogy

Imagine studying from books, but some “books” contain only one word.

Those tiny books add little useful teaching material, so a librarian removes them before creating the study collection.

### 3. Technical Term

A **data-quality filter** checks documents and removes ones that fail chosen quality rules.

This lesson focuses only on the **minimum character length** rule.

A character is one text symbol, including letters, spaces, and punctuation.

### 4. Where It Appears

The Mini configuration sets the minimum in [matgpt_mini_8m.yaml](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/configs/matgpt_mini_8m.yaml:31):

```yaml
quality:
  # Turn quality checking on.
  enabled: true

  # Reject documents containing fewer than 20 characters.
  min_chars: 20
```

### 5. Code Explained Slowly

The check appears in [quality.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/data/quality.py:69):

```python
# Get the document's cleaned text.
text = str(record.get("text", ""))

# Get its recorded character count.
num_chars = int(record.get("num_chars", len(text)))

# Is the document shorter than the allowed minimum?
if num_chars < self.policy.min_chars:
    # Record why this document was rejected.
    return "too_short"
```

Returning `"too_short"` tells the pipeline not to include that document.

### 6. Tiny Example

Suppose:

```text
min_chars = 10
```

Then:

```text
"Hi."         -> 3 characters  -> rejected
"The cat ran." -> 12 characters -> accepted
```

The rule is “fewer than 10,” so a document containing exactly 10 characters would be accepted.

### 7. Beginner Questions

1. In beginner terms, what does a data-quality filter do?
2. What does `min_chars: 20` mean?
3. Is a document with exactly 20 characters rejected?
4. What rejection reason does the repo record for a short document?

### 8. Exercise

Given:

```text
min_chars = 8

Document A: num_chars = 3
Document B: num_chars = 8
Document C: num_chars = 15
```

Fill in:

```text
Document A -> accepted or rejected?
Document B -> accepted or rejected?
Document C -> accepted or rejected?
```

Which document receives the `"too_short"` rejection reason?

All your answers are correct.

A small wording improvement:

> JSONL stores each record on a separate line. `"\n"` ends the current line so the next record starts on a new line.

# Lesson 64: Filtering Text That Is Too Short

### 1. Simplest Explanation

Not every document is useful for training.

A document containing only `"Hi"` or an empty string may provide too little language for the model to learn from. The repo can reject documents that are too short.

### 2. Analogy

Imagine studying from books, but some “books” contain only one word.

Those tiny books add little useful teaching material, so a librarian removes them before creating the study collection.

### 3. Technical Term

A **data-quality filter** checks documents and removes ones that fail chosen quality rules.

This lesson focuses only on the **minimum character length** rule.

A character is one text symbol, including letters, spaces, and punctuation.

### 4. Where It Appears

The Mini configuration sets the minimum in [matgpt_mini_8m.yaml](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/configs/matgpt_mini_8m.yaml:31):

```yaml
quality:
  # Turn quality checking on.
  enabled: true

  # Reject documents containing fewer than 20 characters.
  min_chars: 20
```

### 5. Code Explained Slowly

The check appears in [quality.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/data/quality.py:69):

```python
# Get the document's cleaned text.
text = str(record.get("text", ""))

# Get its recorded character count.
num_chars = int(record.get("num_chars", len(text)))

# Is the document shorter than the allowed minimum?
if num_chars < self.policy.min_chars:
    # Record why this document was rejected.
    return "too_short"
```

Returning `"too_short"` tells the pipeline not to include that document.

### 6. Tiny Example

Suppose:

```text
min_chars = 10
```

Then:

```text
"Hi."         -> 3 characters  -> rejected
"The cat ran." -> 12 characters -> accepted
```

The rule is “fewer than 10,” so a document containing exactly 10 characters would be accepted.

### 7. Beginner Questions

1. In beginner terms, what does a data-quality filter do?
2. What does `min_chars: 20` mean?
3. Is a document with exactly 20 characters rejected?
4. What rejection reason does the repo record for a short document?

### 8. Exercise

Given:

```text
min_chars = 8

Document A: num_chars = 3
Document B: num_chars = 8
Document C: num_chars = 15
```

Fill in:

```text
Document A -> accepted or rejected?
Document B -> accepted or rejected?
Document C -> accepted or rejected?
```

Which document receives the `"too_short"` rejection reason?


All answers are correct.

More precisely:

```text
min_chars: 20
```

means a document must contain **at least 20 characters**. The exact rejection label in the code is `"too_short"`.

# Lesson 65: Exact Deduplication

### 1. Simplest Explanation

Sometimes the same document appears multiple times in a dataset.

The repo can keep the first copy and reject later identical copies.

### 2. Analogy

Imagine a study book accidentally containing the same page 100 times.

That page would receive too much attention, while also wasting study time. Removing repeated copies creates a better-balanced book.

### 3. Technical Term

**Deduplication** means removing duplicates.

**Exact deduplication** removes documents whose cleaned text is exactly the same.

It does not necessarily detect sentences that have similar meanings but different wording.

### 4. Where It Appears

The Mini configuration enables it:

```yaml
quality:
  exact_dedup: true
```

The quality filter keeps fingerprints it has already seen in [quality.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/data/quality.py:63):

```python
# Start with an empty collection of seen document hashes.
self.seen_hashes = set()
```

A `set` is a collection that makes it efficient to check whether a value has already been seen.

### 5. Code Explained Slowly

```python
# Is exact deduplication enabled, and have we seen this hash?
if (
    self.policy.exact_dedup
    and record["text_sha256"] in self.seen_hashes
):
    # Reject this document as an exact duplicate.
    return "duplicate_exact"
```

When a new document is accepted:

```python
if self.policy.exact_dedup:
    # Remember this document's fingerprint.
    self.seen_hashes.add(record["text_sha256"])
```

The hash is calculated from normalized text. Identical normalized documents normally receive the same hash.

### 6. Tiny Example

```text
Document A: "The cat slept." -> hash ABC
Document B: "The dog ran."   -> hash XYZ
Document C: "The cat slept." -> hash ABC
```

Processing result:

```text
A -> accepted; remember ABC
B -> accepted; remember XYZ
C -> rejected; ABC was already seen
```

Removing duplicates saves training compute and reduces the chance of the model overlearning repeated text.

### 7. Beginner Questions

1. In beginner terms, what is deduplication?
2. What does `exact_dedup: true` enable?
3. What does `seen_hashes` remember?
4. What rejection reason is recorded for an exact duplicate?
5. Does exact deduplication guarantee removal of differently worded text with the same meaning?

### 8. Exercise

Given:

```text
Document A -> hash 111
Document B -> hash 222
Document C -> hash 111
Document D -> hash 333
Document E -> hash 222
```

Assume documents are processed from A to E.

Fill in:

```text
A -> accepted or rejected?
B -> accepted or rejected?
C -> accepted or rejected?
D -> accepted or rejected?
E -> accepted or rejected?
```

Which documents receive `"duplicate_exact"`?

Your answers and exercise are correct.

One important precision about `casefold()`:

> It helps match capitalization variants such as `"BLUE"` and `"blue"`.

It does not recognize different words with similar meanings.

# Lesson 67: Hash-Based Train/Validation Splitting

### 1. Simplest Explanation

Some source datasets contain only training documents and no separate validation set.

The repo must then choose a small group of documents for validation.

### 2. Analogy

Imagine every document receives a permanent ticket number between `0` and `1`.

The rule might be:

```text
Ticket below 0.01  -> validation
Ticket 0.01 or more -> training
```

The same document always receives the same ticket, so it stays in the same group whenever preparation runs again.

### 3. Technical Terms

A **dataset split** divides documents into groups such as training and validation.

A **hash-based split** uses each document’s hash to decide its group.

The BabyLM configuration requests:

```yaml
validation_fraction: 0.01
```

This means approximately `1%` of documents become validation data.

### 4. Where It Appears

BabyLM has no provided validation split, as configured in [matgpt_tiny_59m.yaml](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/configs/matgpt_tiny_59m.yaml:22):

```yaml
train_split: train
validation_split: null
generated_validation_split: validation
validation_fraction: 0.01
```

`null` means no source validation split was provided.

### 5. Code Explained Slowly

The assignment happens in [prepare.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/data/prepare.py:96):

```python
# Convert part of the document hash into a number from 0 to 1.
value = int(record["text_sha256"][:16], 16) / float(16**16 - 1)

# Small values go to validation.
if value < validation_fraction:
    return "validation"

# Everything else goes to training.
return "train"
```

The hash begins as hexadecimal text. `int(..., 16)` turns that text into a number. Dividing by the largest possible value scales it to approximately:

```text
0.0 <= value <= 1.0
```

### 6. Tiny Example

Suppose:

```text
validation_fraction = 0.10
```

That means approximately `10%` validation data.

```text
Document A -> hash value 0.04 -> validation
Document B -> hash value 0.72 -> training
Document C -> hash value 0.10 -> training
```

C goes to training because the rule uses `< 0.10`, not `<= 0.10`.

Using the content hash makes the result stable even if document order changes.

### 7. Beginner Questions

1. Why might the repo need to create a validation split?
2. What does `validation_fraction: 0.01` mean?
3. If a hash value is below the validation fraction, which split receives it?
4. Why is a content hash more stable than selecting every tenth row?
5. Does `validation_split: null` mean the repo will never use validation?

### 8. Exercise

Given:

```text
validation_fraction = 0.20

Document A -> value 0.05
Document B -> value 0.19
Document C -> value 0.20
Document D -> value 0.81
```

Fill in:

```text
A -> training or validation?
B -> training or validation?
C -> training or validation?
D -> training or validation?
```

Your exercise is completely correct.

Two important corrections:

- `validation_fraction: 0.01` means approximately **1% of the documents**, not 1% of one document.
- A content hash stays stable when document **order** changes. If the document’s text changes, its hash usually changes, so its split assignment may also change.

# Lesson 68: Dataset Manifest

### 1. Simplest Explanation

After preparing the corpus, the repo creates a summary file describing what was prepared.

### 2. Analogy

A manifest is like a packing list attached to a shipment:

```text
Package name: TinyStories
Language: English
Training documents: 100,000
Validation documents: 5,000
```

You do not need to open every box to understand what the shipment contains.

### 3. Technical Term

A **dataset manifest** is a file containing information about a prepared dataset.

Information describing other data is called **metadata**.

The manifest is metadata about the corpus rather than the actual training text.

### 4. Where It Appears

The repo creates `manifest.json` in [prepare.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/data/prepare.py:321):

```python
return write_manifest(
    normalized_dir / "manifest.json",
    dataset_name=ds_cfg["hf_name"],
    version_or_commit=ds_cfg.get("revision"),
    license_name=ds_cfg["license"],
    stage=ds_cfg["stage"],
    language=ds_cfg["language"],
    split_stats=split_stats,
    quality_report=quality_filter.report(),
)
```

### 5. Code Explained Slowly

```python
manifest = {
    # Which dataset was prepared?
    "dataset_name": dataset_name,

    # Which dataset version was used?
    "version_or_commit": version_or_commit or "unknown",

    # What rules allow this dataset to be used?
    "license": license_name,

    # What kind of training is it intended for?
    "stage": stage,

    # What language does it contain?
    "language": language,

    # Information about training and validation files.
    "split_stats": split_stats,
}
```

The quality-filter report is added:

```python
manifest["quality_filter"] = quality_report
```

Finally, the manifest receives its own fingerprint:

```python
manifest["manifest_sha256"] = sha256_json(manifest)
```

This fingerprint helps checkpoints detect whether the prepared dataset information changed.

### 6. Tiny Example

```json
{
  "dataset_name": "TinyStories",
  "language": "en",
  "split_stats": {
    "train": {
      "document_count": 100
    },
    "validation": {
      "document_count": 10
    }
  }
}
```

This says the prepared corpus contains:

```text
100 training documents
10 validation documents
```

It does not contain the text of those 110 documents.

### 7. Beginner Questions

1. In beginner terms, what is a dataset manifest?
2. Does the manifest contain the complete training text?
3. What does metadata mean?
4. Why does the manifest contain split statistics?
5. Why does the repo calculate a hash for the manifest?

### 8. Exercise

Given:

```json
{
  "dataset_name": "MyStories",
  "language": "en",
  "split_stats": {
    "train": {"document_count": 800},
    "validation": {"document_count": 200}
  }
}
```

Answer:

```text
What is the dataset name?
What language does it contain?
How many training documents are recorded?
How many validation documents are recorded?
How many total documents are recorded?
```

Your answers and calculations are correct.

Two refinements:

- A manifest describes a **prepared** dataset, not a “prepaid” dataset.
- Metadata means any information describing other data, not only statistics.
- The manifest hash helps detect changes when compared with a previously recorded hash. The hash alone does not prevent changes.

The extra `3` after `"language": "en"` appears to be a typing mistake; it would make the shown JSON invalid, but your interpretation is correct.

# Lesson 69: Training a Tokenizer

### 1. Simplest Explanation

The tokenizer must first study the training corpus to decide which text pieces should belong to its vocabulary.

This happens before LLM training begins.

### 2. Analogy

Imagine creating a dictionary for a new language.

You read many documents, notice commonly used pieces, and choose which ones deserve entries in the dictionary.

After creating the dictionary, each entry receives a number.

### 3. Technical Term

**Tokenizer training** means examining a corpus and building a vocabulary of useful text pieces.

This is different from model training:

```text
Tokenizer training -> learns which text pieces exist
Model training     -> learns how those pieces relate and what comes next
```

### 4. Where It Appears

The repo reads the prepared training JSONL in [train.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/tokenizer/train.py:12):

```python
def _iter_texts(input_paths):
    # Read each prepared JSONL file.
    for path in input_paths:
        with Path(path).open("r", encoding="utf-8") as f:

            # Read one document record at a time.
            for line in f:
                record = json.loads(line)

                # Get the actual document text.
                text = record.get("text", "")

                # Give non-empty text to tokenizer training.
                if text:
                    yield text
```

`yield` provides one document at a time instead of loading the complete corpus into memory.

### 5. Building the Vocabulary

```python
# Create an empty BPE tokenizer.
tokenizer = Tokenizer(models.BPE(unk_token=None))

# Configure how the tokenizer should learn.
trainer = trainers.BpeTrainer(
    vocab_size=vocab_size,
    min_frequency=min_frequency,
    special_tokens=special_tokens,
)

# Study the training documents and build the vocabulary.
tokenizer.train_from_iterator(
    _iter_texts(input_paths),
    trainer=trainer,
    length=num_documents,
)

# Save the learned tokenizer.
tokenizer.save("tokenizer.json")
```

We will explain BPE and `min_frequency` separately.

The repo uses only the prepared training split:

```python
train_split = cfg["dataset"]["train_split"]
input_path = normalized_dir / f"{train_split}.jsonl"
```

### 6. Tiny Example

Training corpus:

```text
"The cat sleeps."
"The cat runs."
"The dog sleeps."
```

The tokenizer may notice frequently repeated pieces such as:

```text
"The"
" cat"
" sleeps"
"."
```

It builds a vocabulary from useful pieces and assigns each one a token ID.

### 7. Beginner Questions

1. In beginner terms, what does tokenizer training do?
2. Is tokenizer training the same as LLM model training?
3. What does `_iter_texts()` provide to the tokenizer?
4. Why does the repo use the training JSONL instead of the validation JSONL?
5. What file stores the trained tokenizer?

### 8. Exercise

Put these steps in order:

```text
A. Save tokenizer.json
B. Read text from train.jsonl
C. Build a vocabulary from the text
D. Use the trained tokenizer to convert text into token IDs
```

Answer:

```text
1. ?
2. ?
3. ?
4. ?
```

Your concept answers are correct.

The exercise order for this repo is:

```text
1. B — Read text from train.jsonl
2. C — Build a vocabulary from the text
3. A — Save tokenizer.json
4. D — Load the saved tokenizer and convert text into token IDs
```

An in-memory tokenizer could encode text before being saved, but this repo saves it first, then the later sharding stage loads and uses it.

# Lesson 70: Byte Pair Encoding

### 1. Simplest Explanation

The tokenizer begins with very small text pieces. It repeatedly joins commonly occurring neighboring pieces to create larger tokens.

### 2. Analogy

Imagine building with letter blocks:

```text
c + a + t
```

If `"cat"` appears frequently, we might first join:

```text
c + a -> ca
```

Then:

```text
ca + t -> cat
```

Now `"cat"` can be represented with one token instead of three smaller pieces.

### 3. Technical Term

This method is called **Byte Pair Encoding**, or **BPE**.

A **pair** means two neighboring pieces.

A **merge** means joining a frequently occurring pair into one new vocabulary entry.

The repo uses byte-level starting pieces. We will study what “byte-level” means in the next lesson. For intuition, our examples use letters.

### 4. Where It Appears

The repo creates a BPE tokenizer in [train.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/tokenizer/train.py:53):

```python
# Create a tokenizer that learns using BPE merges.
tokenizer = Tokenizer(models.BPE(unk_token=None))
```

It creates the BPE trainer:

```python
trainer = trainers.BpeTrainer(
    # Maximum requested number of vocabulary entries.
    vocab_size=vocab_size,

    # A pair must appear often enough before being merged.
    min_frequency=min_frequency,

    # Add required special tokens to the vocabulary.
    special_tokens=special_tokens,
)
```

### 5. BPE Process

Using the toy corpus:

```text
cat cat cat
```

Start with small pieces:

```text
c a t
c a t
c a t
```

Count neighboring pairs:

```text
c + a appears 3 times
a + t appears 3 times
```

Suppose BPE chooses `c + a`:

```text
ca t
ca t
ca t
```

A later merge can create:

```text
ca + t -> cat
```

The vocabulary now contains the useful piece `"cat"`.

### 6. Why This Helps

Common text can use fewer tokens:

```text
Before merge: [c, a, t] -> 3 tokens
After merge:  [cat]     -> 1 token
```

Less common words can still be represented using smaller pieces.

### 7. Beginner Questions

1. What does BPE stand for?
2. In beginner terms, what does BPE do?
3. What is a pair?
4. What is a merge?
5. Why might a common word eventually become one token?
6. Does BPE require every word to become a complete token?

### 8. Exercise

Toy corpus:

```text
go go go
```

Initial pieces:

```text
g o
g o
g o
```

Answer:

```text
Which neighboring pair appears three times?
What new token could BPE create?
After that merge, how many tokens represent each "go"?
```

All your BPE answers are correct. Nice and clean.

# Lesson 71: What “Byte-Level” Means

### 1. Simplest Explanation

Before BPE joins common pieces, this tokenizer represents text using very small computer storage units called bytes.

### 2. Analogy

Think of bytes as basic building blocks:

```text
bytes -> merged token pieces -> token IDs
```

Because bytes are smaller than words, they provide building blocks for many kinds of text.

### 3. Technical Terms And Math

A **bit** is one binary value:

```text
0 or 1
```

A **byte** contains 8 bits.

Eight bits can create:

```text
2^8 = 256
```

different patterns. Therefore, one byte represents a number from:

```text
0 to 255
```

Text is converted into bytes using an **encoding**. UTF-8 is the common text encoding used by this repo’s files.

For example:

```text
"A" -> UTF-8 byte 65
"B" -> UTF-8 byte 66
```

Some Unicode characters need multiple bytes.

### 4. Byte-Level BPE

Byte-level BPE:

1. Represents text using byte-based pieces.
2. Finds frequently neighboring pieces.
3. Merges them into larger tokens.

Simplified example:

```text
"A" + "B" -> common pair -> token "AB"
```

### 5. Where It Appears

In [train.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/tokenizer/train.py:61):

```python
# Split input text into byte-level pieces before BPE processing.
tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(
    add_prefix_space=False
)

# Convert byte-level tokens back into readable text when decoding.
tokenizer.decoder = decoders.ByteLevel()
```

`add_prefix_space=False` means the tokenizer does not automatically insert a space at the beginning of every input.

### 6. Important Repo Finding

A byte-level tokenizer should include all 256 byte symbols if we want guaranteed coverage of any UTF-8 input.

The current trainer does not explicitly provide:

```python
initial_alphabet=pre_tokenizers.ByteLevel.alphabet()
```

I verified this locally with a tiny tokenizer trained only on `"cat cat"`:

```text
"cat" -> encoded correctly
"🙂"  -> produced no token IDs
```

So the repo currently uses byte-level processing, but it does not guarantee coverage of unseen bytes. This is a robustness gap we should fix before real pretraining.

### 7. Tiny Example

```text
Text: "AB"
UTF-8 bytes: [65, 66]
```

If `"AB"` occurs frequently, BPE can merge that byte sequence into one learned token.

### 8. Beginner Questions

1. What is a bit?
2. How many bits are in one byte?
3. Why can one byte represent 256 different values?
4. In beginner terms, what does byte-level BPE do?
5. What does the byte-level decoder do?
6. Does the repo currently guarantee coverage of every possible byte?

### 9. Exercise

Given:

```text
"A" -> byte 65
"B" -> byte 66
"C" -> byte 67
```

Fill in:

```text
"ABC" -> byte sequence ?
How many bytes are in this simplified example?
If "AB" is merged into one token, how many token pieces represent "ABC"?
```

Your corrected answers are right.

Small wording fixes:

- There are not “two bits”; a bit has **two possible values**, `0` and `1`.
- The byte sequence is `[65, 66, 67]`, using commas.
- After merging, `[AB, C]` contains `2` token pieces.

# Lesson 72: Minimum Frequency

### 1. Simplest Explanation

BPE should not create a new token for every pair it sees once.

A pair must appear enough times before it is considered useful for merging.

### 2. Analogy

Imagine creating a phrasebook.

If you hear a phrase 1,000 times, adding it to the phrasebook is probably useful. If you hear a strange phrase only once, it may not deserve its own entry.

### 3. Technical Term

**Frequency** means how many times something occurs.

`min_frequency` means the minimum number of times a pair must appear before BPE is allowed to merge it.

### 4. Where It Appears

Both repo configurations use:

```yaml
min_frequency: 2
```

The value is given to the trainer in [train.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/tokenizer/train.py:65):

```python
trainer = trainers.BpeTrainer(
    # Requested vocabulary limit.
    vocab_size=vocab_size,

    # A pair must occur at least this many times.
    min_frequency=min_frequency,

    special_tokens=special_tokens,
)
```

### 5. Tiny Example

Suppose:

```text
min_frequency = 2
```

Pair counts:

```text
c + a -> appears 5 times
x + q -> appears 1 time
d + o -> appears 2 times
```

Results:

```text
c + a -> eligible for merging
x + q -> not eligible
d + o -> eligible
```

**Eligible** means the pair is allowed to be considered. It does not guarantee that BPE will merge it because other pairs may be more frequent, and the vocabulary has a size limit.

### 6. Why This Helps

Minimum frequency helps prevent the vocabulary from filling with rare, possibly accidental text combinations.

A value that is too high may also be harmful because useful but less common pieces might never be merged.

### 7. Beginner Questions

1. What does frequency mean?
2. What does `min_frequency: 2` mean?
3. Is a pair appearing exactly twice eligible?
4. Why might we avoid merging a pair that appears only once?
5. Does being eligible guarantee that a pair will be merged?

### 8. Exercise

Given:

```text
min_frequency = 3

Pair A appears 7 times
Pair B appears 2 times
Pair C appears 3 times
Pair D appears 1 time
```

Fill in:

```text
Pair A -> eligible or not?
Pair B -> eligible or not?
Pair C -> eligible or not?
Pair D -> eligible or not?
```

Which pairs are allowed to be considered for merging?

All your answers are correct. Pair A and Pair C are eligible.

Small spelling refinement: we avoid letting the vocabulary become **populated** with rare pieces.

# Lesson 73: Vocabulary Size

### 1. Simplest Explanation

Vocabulary size controls how many different token entries the tokenizer is allowed to learn.

### 2. Analogy

Imagine a dictionary:

- A small dictionary contains fewer entries, so uncommon words must be built from smaller pieces.
- A large dictionary contains more entries, so more words and phrases can have their own entries.

A larger dictionary is useful, but it also takes more space.

### 3. Technical Term

`vocab_size` is the requested maximum number of tokens in the tokenizer’s vocabulary.

The Mini configuration requests:

```yaml
vocab_size: 8192
```

This means token IDs are intended to range from:

```text
0 through 8191
```

because counting begins at zero.

### 4. Where It Appears

The tokenizer trainer receives it in [train.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/tokenizer/train.py:65):

```python
trainer = trainers.BpeTrainer(
    # Try to build a vocabulary containing up to this many entries.
    vocab_size=vocab_size,
    min_frequency=min_frequency,
    special_tokens=special_tokens,
)
```

The report records both values:

```python
metadata = {
    # What we requested.
    "vocab_size_requested": vocab_size,

    # What the tokenizer actually created.
    "vocab_size_actual": tokenizer.get_vocab_size(),
}
```

The actual size can be smaller if the corpus does not contain enough eligible pieces.

### 5. Why The Model Must Match

The model also uses:

```yaml
model:
  vocab_size: 8192
```

The repo checks this in [config.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/config.py:45):

```python
if model["vocab_size"] != tokenizer["vocab_size"]:
    raise ValueError("model.vocab_size must match tokenizer.vocab_size")
```

The model needs one embedding entry and one output logit position for every possible token ID.

### 6. Vocabulary Size And Model Parameters

The embedding table contains:

```text
vocab_size × d_model
```

learnable numbers.

For the Mini configuration:

```text
8192 × 256 = 2,097,152
```

So its token embedding table contains `2,097,152` learnable numbers.

A larger vocabulary can reduce the number of tokens needed for common text, but it also increases model memory and calculation cost.

### 7. Beginner Questions

1. What does `vocab_size` control?
2. With `vocab_size = 8192`, what is the highest intended token ID?
3. Why can the actual vocabulary be smaller than the requested vocabulary?
4. Why must the model and tokenizer vocabulary settings match?
5. What is the embedding-table size formula?

### 8. Exercise

Given:

```text
vocab_size = 1000
d_model = 64
```

Calculate:

```text
Embedding-table numbers = vocab_size × d_model = ?
How many logits does the model produce at each token position?
What is the highest intended token ID?
```

All five answers are correct.

# Lesson 74: Special Tokens

### 1. Simplest Explanation

Special tokens are reserved markers that communicate structure rather than ordinary text meaning.

### 2. Analogy

A book contains words, but it also contains structural markers:

```text
Chapter begins
Chapter ends
Speaker changes
Blank space
```

Special tokens play a similar role for a model.

### 3. Technical Term

A **special token** is a reserved vocabulary entry used as a control or boundary marker.

It still has a token ID, but BPE does not need to discover it from frequent text. The tokenizer trainer adds it directly.

### 4. Where It Appears

The configured tokens are in [matgpt_mini_8m.yaml](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/configs/matgpt_mini_8m.yaml:44):

```yaml
special_tokens:
  - "<|pad|>"
  - "<|bos|>"
  - "<|eos|>"
  - "<|system|>"
  - "<|user|>"
  - "<|assistant|>"
  - "<|end|>"
```

Their intended meanings are:

```text
<|pad|>       -> fills unused positions when padding is needed
<|bos|>       -> beginning of a sequence
<|eos|>       -> end of a sequence or document
<|system|>    -> beginning of system instructions
<|user|>      -> beginning of a user message
<|assistant|> -> beginning of an assistant message
<|end|>       -> general structured-content ending marker
```

### 5. Adding Them To The Vocabulary

In [train.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/tokenizer/train.py:68):

```python
trainer = trainers.BpeTrainer(
    vocab_size=vocab_size,
    min_frequency=min_frequency,

    # Reserve vocabulary entries for these markers.
    special_tokens=special_tokens,
)
```

The repo records their assigned IDs:

```python
special_token_ids = {
    # Ask the trained tokenizer for each special token's ID.
    token: tokenizer.token_to_id(token)
    for token in special_tokens
}
```

### 6. Which Token Is Used During Base Pretraining?

The sharding code uses `<|eos|>` in [shard.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/data/shard.py:61):

```python
# Find the EOS token's ID.
eos_id = tokenizer.token_to_id("<|eos|>")

# Add EOS after every document.
if append_eos:
    ids.append(eos_id)
```

The current sharding pipeline does not automatically append `<|bos|>` or the chat-role tokens. It primarily uses `<|eos|>` to separate documents.

The packed training batches also do not currently require padding, so `<|pad|>` is reserved but generally unused there.

### 7. Tiny Example

Suppose:

```text
"The cat slept." -> [10, 25, 40, 4]
<|eos|>          -> 2
```

Stored document sequence:

```text
[10, 25, 40, 4, 2]
```

The final `2` tells the model that the document ended.

### 8. Beginner Questions

1. What is a special token?
2. Does BPE need to discover special tokens from repeated text?
3. Which special token does the sharding code append after each document?
4. Does the current sharding code automatically append `<|bos|>`?
5. Why might `<|pad|>` be unnecessary for packed, fixed-length training batches?

### 9. Exercise

Choose the most suitable special token:

```text
A. Mark the end of a training document.
B. Mark the beginning of a user message.
C. Fill an unused position in a padded batch.
D. Mark the beginning of an assistant message.
```

Fill in:

```text
A -> ?
B -> ?
C -> ?
D -> ?
```

All your answers are correct.

# Lesson 75: Token Shards

### 1. Simplest Explanation

After tokenization, the repo creates one long stream of token IDs and divides it into smaller files.

Each smaller file is called a shard.

### 2. Analogy

Imagine a book containing five million pages. It would be difficult to handle as one physical volume.

Instead, we divide it into:

```text
Volume 1
Volume 2
Volume 3
```

The story continues across the volumes. Token shards work similarly.

### 3. Technical Term

A **shard** is one smaller piece of a larger dataset.

The shards contain token IDs that have already been calculated. Training does not need to tokenize the original text repeatedly.

### 4. Where It Appears

The Mini configuration specifies:

```yaml
sharding:
  output_dir: matgpt/data/shards/matgpt_mini_8m
  shard_size_tokens: 5000000
```

This asks the repo to store up to `5,000,000` token IDs in each shard.

### 5. Building A Shard

In [shard.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/data/shard.py:76):

```python
# Read one prepared JSONL record at a time.
for line in f:
    record = json.loads(line)

    # Convert the document text into token IDs.
    ids = tokenizer.encode(record["text"]).ids

    # Mark the end of the document.
    if append_eos:
        ids.append(eos_id)

    # Add each ID to the current shard.
    for token_id in ids:
        shard_tokens.append(int(token_id))

        # Has the shard reached its requested size?
        if len(shard_tokens) >= shard_size_tokens:
            # Write this shard to disk.
            shards.append(
                _flush_shard(
                    shard_tokens,
                    out,
                    split,
                    len(shards),
                    dtype,
                )
            )

            # Start collecting the next shard.
            shard_tokens = []
```

After all documents are processed, the remaining partial shard is also saved:

```python
if shard_tokens:
    shards.append(_flush_shard(...))
```

### 6. Shard Filenames

The repo creates names such as:

```text
train_00000.bin
train_00001.bin
train_00002.bin
```

`.bin` means the token IDs are stored in a compact binary format rather than readable JSON text. We will examine that format separately.

### 7. Tiny Example

Given:

```text
token stream = [10, 20, 30, 40, 50, 60, 70]
shard_size_tokens = 3
```

The shards become:

```text
Shard 0 -> [10, 20, 30]
Shard 1 -> [40, 50, 60]
Shard 2 -> [70]
```

The final shard can be smaller than the requested shard size.

### 8. Why Use Shards?

- Tokenization is performed once instead of during every training step.
- Smaller files are easier to load and manage.
- Training can randomly select among multiple shards.
- Checkpoints can record repeatable data-sampling progress.

### 9. Beginner Questions

1. What is a token shard?
2. What does `shard_size_tokens: 5000000` mean?
3. Why does training read token IDs instead of tokenizing JSONL repeatedly?
4. Can the final shard contain fewer tokens than the requested size?
5. What does the `.bin` filename ending indicate?

### 10. Exercise

Given:

```text
total token IDs = 13
shard_size_tokens = 5
```

Fill in:

```text
Number of shards = ?
Shard 0 size = ?
Shard 1 size = ?
Shard 2 size = ?
```

Is the final shard full or partial?

All your answers and shard-size calculations are correct.

## Lesson 76: `uint16` Token Storage

## 1. Simplest Explanation

Every token ID is a non-negative whole number.

The repo stores those numbers in a compact format called `uint16`.

### 2. Analogy

Imagine choosing boxes for storing numbered cards.

A smaller box uses less space, but it can only hold numbers up to a certain limit. A larger box supports bigger numbers but uses more storage.

### 3. Technical Terms And Math

`uint16` means:

```text
u    -> unsigned: no negative numbers
int  -> integer: whole numbers
16   -> uses 16 bits
```

Because one byte contains 8 bits:

```text
16 bits ÷ 8 = 2 bytes
```

A 16-bit unsigned integer has:

```text
2^16 = 65,536 possible values
```

Its mathematical range is:

```text
0 through 65,535
```

### 4. Where It Appears

The Mini configuration uses:

```yaml
sharding:
  dtype: uint16
```

The available formats appear in [shard.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/data/shard.py:20):

```python
DTYPES = {
    # Two bytes for each token ID.
    "uint16": np.uint16,

    # Four bytes for each token ID.
    "uint32": np.uint32,
}
```

`dtype` means **data type**: the format used to store each number.

### 5. Writing The Binary File

```python
# Convert the token-ID list into compact uint16 numbers.
array = np.asarray(tokens, dtype=DTYPES[dtype])

# Write those numbers directly into the .bin file.
array.tofile(path)
```

For `uint16`:

```text
1 token ID    -> 2 bytes
1,000 IDs     -> 2,000 bytes
5,000,000 IDs -> 10,000,000 bytes
```

This does not include small filesystem or metadata overhead.

### 6. Vocabulary Limit

The repo checks:

```python
if dtype == "uint16" and tokenizer.get_vocab_size() > 65535:
    raise ValueError(...)
```

Mathematically, `uint16` has 65,536 values. This repo applies the slightly more conservative rule:

```text
vocab_size <= 65,535
```

The Mini vocabulary is only `8,192`, so it fits comfortably.

### 7. Tiny Example

```text
Token IDs: [10, 500, 8191]
```

All fit in `uint16` because each is between `0` and `65,535`.

This would not fit:

```text
Token ID: 70,000
```

A larger format such as `uint32` would be required.

### 8. Beginner Questions

1. What does `uint16` mean?
2. How many bytes does one `uint16` value use?
3. Why are token IDs suitable for an unsigned type?
4. What is the mathematical range of `uint16`?
5. Why does `uint16` use less storage than `uint32`?

### 9. Exercise

Given:

```text
number of token IDs = 10,000
storage type = uint16
```

Answer:

```text
How many bytes are required for the token IDs?
Can token ID 60,000 fit in uint16?
Can token ID 70,000 fit in uint16?
Which repo type could store token ID 70,000?
```

All three answers are correct:

```text
uint16: 2,500 × 2 = 5,000 bytes
uint32: 2,500 × 4 = 10,000 bytes
uint16 uses less storage
```

# Lesson 77: Memory Mapping

### 1. Simplest Explanation

Training needs small sections of very large shard files.

Memory mapping lets the program access the needed section without first loading the complete file into memory.

### 2. Analogy

Imagine a massive reference book.

You do not photocopy the entire book whenever you need one paragraph. You open the book at the required page and read only that section.

### 3. Technical Term

A **memory-mapped file** makes a file on disk behave somewhat like an array of numbers.

The operating system loads the required parts as the program accesses them.

NumPy provides this through `np.memmap`.

### 4. Where It Appears

The dataset loads each shard in [dataset.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/dataset.py:37):

```python
# Read the shard metadata file.
metadata = json.loads(
    Path(metadata_path).read_text(encoding="utf-8")
)

# Find out whether the token IDs use uint16 or uint32.
dtype = NUMPY_DTYPES[metadata["dtype"]]
```

Then it creates a memory map:

```python
PackedShard(
    # Location of the binary shard.
    path=Path(shard["path"]),

    # Number of token IDs in the shard.
    num_tokens=int(shard["num_tokens"]),

    # Make the binary file accessible like a NumPy array.
    data=np.memmap(
        shard["path"],
        mode="r",
        dtype=dtype,
    ),
)
```

`mode="r"` means **read-only**. Training may read the shard, but it should not modify it.

### 5. Reading A Small Slice

Later, the dataset reads only one window:

```python
window = np.asarray(
    shard.data[
        start : start + self.context_length + 1
    ],
    dtype=np.int64,
)
```

Suppose:

```text
start = 100
context_length = 4
```

The requested positions are:

```text
100, 101, 102, 103, 104
```

That is `5` token IDs because the dataset needs:

```text
context_length + 1
```

It then creates shifted `x` and `y` rows.

### 6. Why This Helps

- Large shard files do not need to be fully loaded first.
- The dataset can quickly access random token positions.
- Memory use remains more manageable.
- Shards remain unchanged because they are opened read-only.

The operating system may load surrounding storage blocks for efficiency, but the program does not explicitly read the entire shard.

### 7. Beginner Questions

1. In beginner terms, what does memory mapping allow the program to do?
2. What does `np.memmap` make the shard behave like?
3. What does `mode="r"` mean?
4. Why must the code read the shard’s stored `dtype`?
5. If `context_length = 8`, how many token IDs are needed for one window?

### 8. Exercise

A memory-mapped shard contains `1,000,000` token IDs.

The dataset requests:

```text
start = 200
context_length = 4
```

Answer:

```text
Which token positions are requested?
How many token IDs are requested?
Does the code explicitly load all 1,000,000 token IDs?
Can training modify the shard when mode="r"?
```


All your memory-mapping answers are correct.

# Lesson 78: Weighted Shard Sampling

### 1. Simplest Explanation

Larger shards contain more possible training examples, so the repo selects them more often than smaller shards.

### 2. Analogy

Imagine two bags:

```text
Bag A contains 90 cards.
Bag B contains 10 cards.
```

If you choose each bag 50% of the time, cards in the small bag will be seen much more often relative to how many cards it contains.

A fairer method gives Bag A about a 90% chance and Bag B about a 10% chance.

### 3. Technical Terms

A **sampling weight** describes how strongly an item should be considered during random selection.

A **probability** is a number from `0` to `1` describing how likely something is.

All selection probabilities must add up to:

```text
1.0
```

### 4. Where It Appears

The weights are calculated in [dataset.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/dataset.py:34):

```python
# Estimate how many starting positions each shard provides.
weights = np.asarray(
    [
        shard.num_tokens - context_length
        for shard in self.shards
    ],
    dtype=np.float64,
)

# Convert the raw weights into probabilities that add to 1.
self.weights = weights / weights.sum()
```

The repo then uses those probabilities:

```python
shard_indices = self.rng.choice(
    # Number of available shards.
    len(self.shards),

    # Choose one shard for every batch row.
    size=batch_size,

    # Use the calculated probabilities.
    p=self.weights,
)
```

### 5. Tiny Example

Suppose:

```text
context_length = 10

Shard A has 100 tokens.
Shard B has 40 tokens.
```

Raw weights:

```text
A = 100 - 10 = 90
B = 40 - 10 = 30
```

Total:

```text
90 + 30 = 120
```

Probabilities:

```text
A = 90 / 120 = 0.75
B = 30 / 120 = 0.25
```

Therefore, A should be selected approximately 75% of the time and B approximately 25% of the time over many choices.

It does not mean every group of four selections must contain exactly three A selections. Random results vary in the short term.

### 6. Why Subtract Context Length?

A training example needs a complete window of consecutive tokens.

Positions too close to the end of a shard cannot provide a full window, so the shard’s usable size is slightly smaller than its total token count.

### 7. Beginner Questions

1. Why should a larger shard usually be selected more often?
2. What is a sampling weight?
3. Why does the code divide each weight by `weights.sum()`?
4. What must all shard probabilities add up to?
5. Does probability `0.75` guarantee exactly three selections out of every four?

### 8. Exercise

Given:

```text
context_length = 10

Shard A tokens = 70
Shard B tokens = 30
```

Calculate:

```text
Raw weight A = ?
Raw weight B = ?
Total raw weight = ?
Probability A = ?
Probability B = ?
```

Which shard should be selected more often?


All your weighted-sampling answers and calculations are correct.

# Lesson 79: Packed Token Streams

### 1. Simplest Explanation

The repo joins tokenized documents into one continuous sequence, placing `<|eos|>` between them.

This avoids wasting space on padding.

### 2. Analogy

Imagine placing several stories on one long paper roll:

```text
Story A | END | Story B | END | Story C | END
```

The stories share one roll, but the `END` markers show where each story stops.

### 3. Technical Term

**Packing** means joining multiple tokenized documents into a continuous token stream.

A **packed token stream** contains real token IDs throughout, rather than filling unused positions with padding.

### 4. Where It Appears

In [shard.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/data/shard.py:76), each document is encoded:

```python
# Turn the current document into token IDs.
ids = tokenizer.encode(record["text"]).ids

# Add a boundary marker after the document.
if append_eos:
    ids.append(eos_id)
```

Those IDs are appended to the same shard list:

```python
for token_id in ids:
    # Continue the shared token stream.
    shard_tokens.append(int(token_id))
```

The list is not cleared after each document. It is cleared only when the current shard becomes full.

### 5. Tiny Example

Suppose:

```text
Document A -> [10, 11]
Document B -> [20, 21, 22]
EOS ID     -> 2
```

The packed stream becomes:

```text
[10, 11, 2, 20, 21, 22, 2]
```

There are seven useful token positions and no padding.

### 6. Windows Can Cross Document Boundaries

The dataset selects windows from anywhere in the packed stream.

A window may therefore contain:

```text
[11, 2, 20, 21, 22]
```

This crosses from Document A into Document B.

The `<|eos|>` token tells the model that one document ended. The next token after EOS begins another document.

The current repo does not reset attention or add a special attention mask at document boundaries. Within a sampled window, tokens after EOS can still attend to earlier visible tokens from the previous document. This is a simple and common packing approach, though stricter document-separated attention is another possible design.

### 7. Why Pack Documents?

- Less padding is needed.
- More training positions contain real text.
- Storage and GPU work are used more efficiently.
- Short documents can contribute to full-length training windows.

### 8. Beginner Questions

1. In beginner terms, what does packing mean?
2. Which token separates documents in the packed stream?
3. Why does packing reduce the need for padding?
4. Can a training window cross a document boundary?
5. Does this repo reset attention at every EOS boundary?

### 9. Exercise

Given:

```text
Document A -> [10, 11]
Document B -> [20, 21, 22]
EOS ID     -> 2
```

Answer:

```text
Complete packed stream = ?
Total number of token IDs = ?
```

Then suppose:

```text
context_length = 4
start = 1
```

Fill in:

```text
window = ?
x = ?
y = ?
```

Does this window cross a document boundary?

All your packed-stream answers are correct, including the shifted `x` and `y`.

# Lesson 80: Shard Metadata

### 1. Simplest Explanation

Training needs instructions telling it:

- Which shard files exist
- Where they are stored
- How many tokens they contain
- How each token ID is stored

Those instructions are stored in a metadata file.

### 2. Analogy

Imagine several numbered storage boxes.

A catalog tells you:

```text
Box 0 -> shelf A, 5,000 items
Box 1 -> shelf B, 5,000 items
Box 2 -> shelf C, 2,000 items
```

The catalog is not the stored material. It tells you how to find and interpret the material.

### 3. Technical Term

**Shard metadata** is information describing the binary token shards.

This differs from the earlier corpus manifest:

```text
Corpus manifest -> describes prepared text documents
Shard metadata  -> describes tokenized binary files
```

### 4. Where It Appears

The repo builds metadata in [shard.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/data/shard.py:114):

```python
metadata = {
    # Is this training or validation data?
    "split": split,

    # Which prepared JSONL file was tokenized?
    "input_path": str(Path(input_path)),

    # Fingerprint of the tokenizer that produced the IDs.
    "tokenizer_sha256": tokenizer_metadata["tokenizer_sha256"],

    # Are IDs stored as uint16 or uint32?
    "dtype": dtype,

    # Was EOS added after documents?
    "append_eos": append_eos,

    # How many documents and token IDs were processed?
    "total_documents": total_documents,
    "total_tokens": total_tokens,

    # Information about every binary shard.
    "shards": shards,
}
```

It writes files such as:

```text
train_metadata.json
validation_metadata.json
```

### 5. Information About One Shard

When a shard is written, the repo records:

```python
return {
    # Binary file location.
    "path": str(path),

    # Shard number.
    "index": shard_index,

    # Number of token IDs in this shard.
    "num_tokens": int(array.size),

    # Fingerprint for detecting file changes.
    "sha256": sha256_file(path),
}
```

### 6. How Training Uses It

In [dataset.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/dataset.py:38):

```python
# Load the metadata instructions.
metadata = json.loads(
    Path(metadata_path).read_text(encoding="utf-8")
)

# Find the correct storage type.
dtype = NUMPY_DTYPES[metadata["dtype"]]

# Open every listed shard as a memory-mapped array.
for shard in metadata["shards"]:
    data = np.memmap(
        shard["path"],
        mode="r",
        dtype=dtype,
    )
```

Without the correct `dtype`, the program could interpret the binary bytes incorrectly.

### 7. Tiny Example

```json
{
  "split": "train",
  "dtype": "uint16",
  "total_tokens": 8,
  "shards": [
    {"path": "train_00000.bin", "num_tokens": 5},
    {"path": "train_00001.bin", "num_tokens": 3}
  ]
}
```

This describes two shards containing eight token IDs in total.

### 8. Beginner Questions

1. What does shard metadata describe?
2. Does shard metadata contain the actual token IDs?
3. Why does training need the shard path?
4. Why does training need the correct `dtype`?
5. What is the difference between the corpus manifest and shard metadata?

### 9. Exercise

Given:

```json
{
  "split": "validation",
  "dtype": "uint16",
  "total_documents": 40,
  "total_tokens": 12000,
  "shards": [
    {"path": "validation_00000.bin", "num_tokens": 5000},
    {"path": "validation_00001.bin", "num_tokens": 5000},
    {"path": "validation_00002.bin", "num_tokens": 2000}
  ]
}
```

Answer:

```text
Which split is described?
How many documents were processed?
How many shards exist?
How many total tokens are recorded?
Is the final shard full-sized compared with the first two?
```

All your shard-metadata answers are correct.

# Lesson 81: Characters Per Token

### 1. Simplest Explanation

A tokenizer report tells us approximately how much text each token represents.

### 2. Analogy

Imagine packing letters into boxes:

```text
Box A holds 1 letter.
Box B holds 3 letters.
```

If each box represents one token, Box B stores the same text using fewer boxes.

### 3. Technical Term

**Characters per token** is the average number of text characters represented by one token.

The formula is:

```text
characters per token = total characters ÷ total tokens
```

### 4. Where It Appears

The repo first counts the tokens in [train.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/tokenizer/train.py:90):

```python
# Begin with zero counted tokens.
total_tokens = 0

# Read every training document again.
for text in _iter_texts(input_paths):

    # Tokenize the text and count its token IDs.
    total_tokens += len(tokenizer.encode(text).ids)
```

It then calculates the average:

```python
"chars_per_token": (
    total_chars / total_tokens
    if total_tokens
    else 0.0
)
```

The `else 0.0` avoids division by zero if there are no tokens.

The result is written to:

```text
tokenizer_report.json
```

### 5. Tiny Example

Suppose the corpus contains:

```text
total characters = 1,200
total tokens = 400
```

Then:

```text
chars_per_token = 1,200 ÷ 400
                = 3
```

On average, each token represents three characters.

### 6. Why It Matters

If two tokenizers process the same corpus:

```text
Tokenizer A -> 3 characters per token
Tokenizer B -> 2 characters per token
```

Tokenizer A uses fewer tokens for that text.

This can allow more readable text to fit inside a fixed context length and can reduce training work.

However, a higher value is not automatically better. We must also check:

- Whether text encodes and decodes correctly
- Whether unusual text is supported
- Whether vocabulary pieces are useful
- Vocabulary size and model cost
- Performance across the languages we care about

Compare this metric only under similar conditions, especially the same corpus and normalization.

### 7. Beginner Questions

1. What does characters per token measure?
2. What is its formula?
3. If one token represents more characters on average, does the same text usually require more or fewer tokens?
4. Where does the repo save this measurement?
5. Is the highest possible characters-per-token value automatically the best tokenizer?

### 8. Exercise

Two tokenizers process the same `1,000`-character corpus:

```text
Tokenizer A produces 400 tokens.
Tokenizer B produces 500 tokens.
```

Calculate:

```text
Tokenizer A characters per token = ?
Tokenizer B characters per token = ?
Which tokenizer represents this corpus with fewer tokens?
Does this metric alone prove that tokenizer is better overall?
```

All your answers and calculations are correct.

# Lesson 82: Tokenizer Round-Trip Testing

### 1. Simplest Explanation

After converting text into token IDs, the tokenizer should usually be able to convert those IDs back into the original text exactly.

### 2. Analogy

Imagine translating a message into a secret code and then translating it back:

```text
Original message -> secret code -> recovered message
```

If the recovered message differs, information was lost or changed.

### 3. Technical Term

This process is called an **encode-decode round trip**:

```text
text -> encode -> token IDs -> decode -> text
```

A successful round trip satisfies:

```python
tokenizer.decode(tokenizer.encode(text).ids) == text
```

### 4. Encode And Decode

**Encoding** converts text into token IDs:

```text
"A cat." -> [10, 25, 4]
```

**Decoding** converts token IDs back into readable text:

```text
[10, 25, 4] -> "A cat."
```

Spaces and punctuation must also be recovered correctly.

### 5. Where It Appears

The repository tests this in [test_tokenizer.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/tests/test_tokenizer.py:50):

```python
# Original readable text.
text = "A token is text."

# Encode the text into token IDs.
ids = tokenizer.encode(text).ids

# Decode the IDs and require the exact original text.
assert tokenizer.decode(ids) == text
```

If the decoded result differs, the test fails.

### 6. Tiny Example

Successful round trip:

```text
Original: "The cat."
IDs:      [10, 25, 4]
Decoded:  "The cat."
Result:   pass
```

Failed round trip:

```text
Original: "The cat."
IDs:      [10, 25, 4]
Decoded:  "Thecat."
Result:   fail
```

The second result lost a space.

### 7. Important Test Gap

The current repo test uses text similar to its tiny training corpus. It does not test unseen Unicode characters.

Earlier, we verified that a tokenizer trained only on `"cat cat"` could not encode an unseen emoji because the complete byte alphabet was not added.

A stronger test suite should include:

- Accented text such as `"café"`
- Non-Latin writing
- Emoji
- Newlines and unusual spacing
- Characters absent from the tokenizer-training sample

We will address that robustness gap before real pretraining.

### 8. Beginner Questions

1. What does encoding do?
2. What does decoding do?
3. What is an encode-decode round trip?
4. What equality should hold for a successful round trip?
5. Why should spaces and punctuation be checked?
6. What important kinds of text are missing from the current repo test?

### 9. Exercise

Decide whether each round trip passes or fails:

```text
A:
Original = "Hello!"
Decoded  = "Hello!"

B:
Original = "Hello world"
Decoded  = "Helloworld"

C:
Original = "café"
Decoded  = "caf"
```

Answer:

```text
A -> pass or fail?
B -> pass or fail? What changed?
C -> pass or fail? What changed?
```

All your round-trip answers are correct.

# Lesson 83: The Initial Byte Alphabet

### 1. Simplest Explanation

Before BPE learns merges, the tokenizer needs a complete collection of basic pieces.

For byte-level BPE, that collection should contain all 256 possible byte values.

### 2. Analogy

Imagine building a dictionary of words but forgetting to include some alphabet letters.

Even if the dictionary contains many common words, it cannot spell a new word containing a missing letter.

The byte alphabet provides all the basic “letters” before BPE creates larger pieces.

### 3. Technical Term

An **alphabet** is the tokenizer’s collection of starting symbols.

For byte-level BPE:

```text
initial alphabet = all 256 byte symbols
```

BPE then adds merged tokens on top of that starting alphabet.

### 4. Root Cause In This Repo

The repo currently creates the trainer without an initial alphabet:

```python
trainer = trainers.BpeTrainer(
    vocab_size=vocab_size,
    min_frequency=min_frequency,
    special_tokens=special_tokens,
)
```

The trainer therefore learns starting symbols only from bytes it sees in the training corpus.

That is why a tokenizer trained only on `"cat cat"` could not encode an unseen emoji.

### 5. The Intended Configuration

The trainer should receive:

```python
trainer = trainers.BpeTrainer(
    vocab_size=vocab_size,
    min_frequency=min_frequency,
    special_tokens=special_tokens,

    # Include all 256 byte symbols even when some are unseen.
    initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
)
```

I verified this locally:

```text
Initial byte alphabet size = 256
Training text = "cat cat"
Unseen test text = "🙂"
Decoded result = "🙂"
Round trip passed = yes
```

This confirms the missing initial alphabet is the root cause.

### 6. Vocabulary Budget

The requested vocabulary size includes:

```text
special tokens + initial alphabet + BPE merges
```

This repo has seven special tokens:

```text
256 byte symbols + 7 special tokens = 263 required entries
```

Therefore, a full byte-level tokenizer needs a requested vocabulary size of at least `263` before adding any learned merges.

The repo’s real vocabulary sizes, `8,192` and `16,384`, are large enough. Some tiny tests currently request only `128`, so those tests must be adjusted when the bug is fixed.

### 7. Tiny Example

The emoji `"🙂"` uses these four UTF-8 bytes:

```text
[240, 159, 153, 130]
```

Even if the emoji never appeared during tokenizer training, the complete byte alphabet contains all four basic byte pieces. The tokenizer can therefore encode and reconstruct it.

### 8. Beginner Questions

1. What is an initial tokenizer alphabet?
2. How many symbols are in the complete byte alphabet?
3. Why did the current tiny tokenizer fail on an unseen emoji?
4. What does `ByteLevel.alphabet()` provide?
5. Why must vocabulary size include room for the alphabet and special tokens?

### 9. Exercise

Given:

```text
requested vocab size = 300
byte alphabet entries = 256
special tokens = 7
```

Calculate:

```text
Entries required before BPE merges = ?
Maximum vocabulary entries remaining for learned merges = ?
```

Then answer:

```text
If an unseen character uses bytes [195, 169], can a tokenizer with the complete byte alphabet represent those bytes?
Why?
```

All your answers and calculations are correct:

```text
Required before merges = 256 + 7 = 263
Remaining for merges = 300 - 263 = 37
```

Your unseen-character explanation is correct because UTF-8 represents Unicode characters using byte sequences, and the complete alphabet provides all possible byte pieces.

# Lesson 84: The Complete Data Pipeline

### 1. Simplest Explanation

A data pipeline is the ordered journey from raw text to training examples the model can use.

### 2. Analogy

Think of a factory line:

```text
raw material
-> clean it
-> label it
-> convert it
-> package it
-> deliver it
```

Each stage prepares the output needed by the next stage.

### 3. Technical Term

A **data pipeline** is an ordered set of processing steps that transforms raw data into a usable final form.

In this repo:

```text
Raw text
-> normalized JSONL
-> trained tokenizer
-> token IDs
-> packed binary shards
-> x and y training tensors
```

### 4. Stage 1: Prepare The Corpus

Command:

```bash
python scripts/prepare_dataset.py \
  --config configs/matgpt_mini_8m.yaml
```

Main code:

```python
cfg = load_config(args.config)  # Read settings.
set_seed(cfg["run"]["seed"])    # Make preparation repeatable.
manifest = prepare_hf_dataset(cfg)  # Prepare the corpus.
```

Outputs:

```text
train.jsonl
validation.jsonl
manifest.json
```

This stage normalizes, filters, deduplicates, and splits documents.

### 5. Stage 2: Train The Tokenizer

Command:

```bash
python scripts/train_tokenizer.py \
  --config configs/matgpt_mini_8m.yaml
```

Main code:

```python
cfg = load_config(args.config)
set_seed(cfg["run"]["seed"])
report = train_tokenizer_from_config(cfg)
```

Outputs:

```text
tokenizer.json
special_tokens.json
tokenizer_report.json
```

Before a real run, the missing complete byte alphabet must be fixed and tested.

### 6. Stage 3: Create Token Shards

Command:

```bash
python scripts/tokenize_and_shard.py \
  --config configs/matgpt_mini_8m.yaml
```

Main code:

```python
cfg = load_config(args.config)
set_seed(cfg["run"]["seed"])
metadata = tokenize_splits_from_config(cfg)
```

Outputs:

```text
train_00000.bin
validation_00000.bin
train_metadata.json
validation_metadata.json
```

This stage encodes text, appends EOS, packs token IDs, and writes binary shards.

### 7. Stage 4: Sample Training Examples

The dataset:

1. Reads shard metadata.
2. Opens shards with memory mapping.
3. Randomly chooses a shard.
4. Randomly chooses a starting position.
5. Reads `context_length + 1` token IDs.
6. Creates shifted `x` and `y` tensors.

Tiny example:

```text
window = [10, 20, 30, 40, 50]

x = [10, 20, 30, 40]
y = [20, 30, 40, 50]
```

These tensors are ready for next-token training.

### 8. Beginner Questions

1. What is a data pipeline?
2. What does dataset preparation produce?
3. Why must the tokenizer be trained before shard creation?
4. Why must shard creation happen before pretraining?
5. What is the final output of the data pipeline that the model receives?
6. Which tokenizer robustness problem must be fixed before a real run?

### 9. Exercise

Put these steps in order:

```text
A. Create shifted x and y tensors
B. Train the BPE tokenizer
C. Normalize and filter raw documents
D. Encode documents into packed token shards
E. Save normalized JSONL and its manifest
```

Answer:

```text
1. ?
2. ?
3. ?
4. ?
5. ?
```


## Lesson 84 Check

Your ordering is completely correct:

1. Normalize and filter documents.
2. Save JSONL files and the manifest.
3. Train the BPE tokenizer.
4. Encode and pack documents into token shards.
5. Create shifted `x` and `y` tensors.

A few important corrections:

- **Tokenizer before sharding:** The trained tokenizer provides fixed vocabulary and BPE merge rules. Sharding uses it to encode text. Appending EOS and packing happen during **sharding**, not tokenizer training.
- **Shards before pretraining:** Pretraining reads ready-made token IDs efficiently. The model does not perform BPE merges itself.
- **Final model input:** The dataset produces `x` and `y`, not `x` and `x`.
  - `x` contains the tokens the model sees.
  - `y` contains the correct next tokens it should predict.
- **Tokenizer robustness problem:** The tokenizer needs the complete 256-symbol byte alphabet using `ByteLevel.alphabet()`. We should also test encode-decode round trips using unseen Unicode characters such as emoji.

# Lesson 85: What Is a Smoke Test?

## 1. Simplest Explanation

Before starting an expensive training run, we run training for only a few steps.

This checks whether the main parts of the system can work together without immediately failing.

## 2. Analogy

Imagine preparing for a long road trip.

Before leaving, you start the car and drive around the block. That short drive does not prove the car can complete the entire journey, but it can reveal obvious problems.

A short training run serves the same purpose.

## 3. Technical Term

This short preliminary run is called a **smoke test**.

A smoke test answers:

> “Can the basic training system start and operate without an obvious failure?”

It does not answer:

> “Will the finished model be good?”

## 4. Where It Appears in the Repo

The command is documented in [README.md](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/README.md:79):

```bash
python scripts/pretrain.py \
  --config configs/matgpt_mini_8m.yaml \
  --max-steps 20
```

The `--max-steps` option is defined in [scripts/pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/scripts/pretrain.py:15).

## 5. Code Explained Slowly

Here is the relevant code with beginner comments:

```python
# Create the command-line option named --max-steps.
parser.add_argument(
    "--max-steps",

    # Convert the provided value, such as 20, into an integer.
    type=int,

    # If the option is missing, do not apply a short-run limit.
    default=None,

    # Explain the purpose of this option.
    help="Optional short-run override for smoke tests.",
)

# Start pretraining and pass the short-run limit into it.
result = run_pretraining(
    cfg,
    resume_from=args.resume_from,
    max_steps_override=args.max_steps,
)
```

The limit is applied in [pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:192):

```python
# Calculate how many steps the complete training run needs.
total_steps = _steps_from_tokens(cfg)

# Check whether the user requested a short run.
if max_steps_override is not None:

    # Stop after the requested number of additional steps,
    # unless the complete run requires even fewer steps.
    total_steps = min(
        total_steps,
        state["global_step"] + max_steps_override,
    )
```

From a new run:

```text
global_step = 0
max_steps_override = 20
```

Therefore, training stops after at most 20 steps.

When resuming from step 500, `--max-steps 20` allows at most 20 additional steps, stopping around step 520.

## 6. Tiny Example

Suppose complete training requires `50,000` steps.

```bash
python scripts/pretrain.py --config config.yaml --max-steps 10
```

The smoke test runs at most `10` steps, not `50,000`.

It can catch problems with:

- Loading configuration
- Loading tokenizer and shards
- Creating `x` and `y`
- Running the model
- Computing loss and gradients
- Updating parameters

It does **not** prove that the model will learn well or remain stable for the complete run.

## 7. Beginner Questions

1. In beginner terms, what is a smoke test?
2. Why should we run one before expensive GPU training?
3. From a new run, what does `--max-steps 20` mean?
4. Does a successful smoke test prove that the final model will be good?
5. Name two training-system problems a smoke test might detect.

## 8. Exercise

The full training target is `50,000` steps.

You run:

```bash
python scripts/pretrain.py --config config.yaml --max-steps 12
```

Answer:

1. What is the maximum number of steps in this new smoke-test run?
2. Does this permanently change the value inside the configuration file?
3. Should the resulting model be treated as the final trained model?


Your smoke-test answers are all correct. You understand both its purpose and its limitation: it checks whether training works mechanically, but it does not measure final model quality.

# Lesson 86: CPU, GPU, and Device

## 1. Simplest Explanation

Training requires performing a huge number of calculations.

Those calculations must happen on some piece of computer hardware. In PyTorch, the place where calculations happen is called a **device**.

The main choices are:

- **CPU:** The computer’s general-purpose processor.
- **GPU:** A processor designed to perform many similar calculations simultaneously.

## 2. Analogy

Imagine calculating 1,000 multiplication problems.

A CPU is like having a few highly capable workers. A GPU is like having hundreds or thousands of workers handling many calculations at the same time.

LLM training contains enormous amounts of similar matrix arithmetic, so a suitable GPU is usually much faster.

## 3. Technical Terms

**CPU** means Central Processing Unit.

**GPU** means Graphics Processing Unit. GPUs were originally designed for graphics, but their ability to perform many calculations simultaneously makes them useful for model training.

**CUDA** is technology that allows PyTorch to use supported NVIDIA GPUs.

A PyTorch **device** describes where a model or tensor is stored and processed:

```python
torch.device("cpu")
torch.device("cuda")
```

## 4. Where It Appears in the Repo

The repo chooses a device in [pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:35):

```python
def get_device() -> torch.device:
    return torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )
```

## 5. Code Explained Slowly

```python
def get_device() -> torch.device:
    # Ask PyTorch whether a supported NVIDIA GPU is available.
    gpu_is_available = torch.cuda.is_available()

    # Use the GPU when one is available.
    # Otherwise, perform the calculations on the CPU.
    device_name = "cuda" if gpu_is_available else "cpu"

    # Create and return a PyTorch device description.
    return torch.device(device_name)
```

The selected device is used when creating the model:

```python
# Decide where training calculations will happen.
device = get_device()

# Create the model.
model = GPT(GPTConfig.from_dict(cfg["model"]))

# Move the model's parameters to the selected device.
model = model.to(device)
```

The training batch is also moved to that device:

```python
# Create x and y and place them on the same device as the model.
x, y = train_dataset.sample_batch(
    batch_size,
    device,
)
```

The model, `x`, and `y` must normally be on the same device. A GPU model cannot directly calculate using a tensor that remains in CPU memory.

## 6. Tiny Example

Suppose CUDA is available:

```text
get_device() -> cuda
model          -> cuda
x              -> cuda
y              -> cuda
```

Training can proceed.

This arrangement is incorrect:

```text
model -> cuda
x     -> cpu
y     -> cpu
```

PyTorch will normally report a device mismatch error.

The current repo checks for NVIDIA CUDA. On a computer without CUDA, including a typical Mac, it selects the CPU.

## 7. Beginner Questions

1. In beginner terms, what does a device describe?
2. What is the difference between a CPU and a GPU?
3. Why are GPUs useful for LLM training?
4. What device does the repo select when CUDA is available?
5. What device does it select when CUDA is unavailable?
6. Why must the model, `x`, and `y` usually be on the same device?

## 8. Exercise

Suppose:

```python
torch.cuda.is_available() == False
```

Answer:

1. Which device will `get_device()` return?
2. If the model is on `cuda` but `x` is on `cpu`, is that arrangement valid?
3. What does this operation do?

```python
x = x.to(device)
```

# Lesson 87: What Does “Training From Scratch” Mean?

## 1. Simplest Explanation

Training from scratch means the model begins without previously learned language knowledge.

Its internal parameters start as small initial numbers. Training gradually changes those numbers using loss and gradients.

## 2. Analogy

Imagine a new student who has never studied a language.

The student has a working brain and a learning process, but has not yet learned vocabulary, grammar, or meaning.

Similarly, the model already has its Transformer structure, but its parameters have not learned useful language patterns.

## 3. Technical Term: Weight Initialization

The starting values given to the model’s parameters are called **initial weights**.

Creating those starting values is called **weight initialization**.

Many parameters receive small random values near zero:

```text
0.012, -0.007, 0.025, -0.018
```

They are numbers, but they do not yet contain learned language knowledge.

Here, “from scratch” specifically means:

> The model parameters are not loaded from a pretrained-model checkpoint.

The tokenizer is still trained before model pretraining. “From scratch” does not mean using an untrained tokenizer.

## 4. Where It Appears in the Repo

The model is created in [pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:147):

```python
model = GPT(GPTConfig.from_dict(cfg["model"])).to(device)
```

Its parameters are initialized in [gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:348).

## 5. Code Explained Slowly

```python
# Visit the model's layers and run _init_weights on them.
self.apply(self._init_weights)
```

The initialization function is:

```python
def _init_weights(self, module: nn.Module) -> None:
    # Check whether this module is a linear transformation.
    if isinstance(module, nn.Linear):

        # Give its weights small random starting values.
        torch.nn.init.normal_(
            module.weight,
            mean=0.0,
            std=0.02,
        )

        # If the layer has bias parameters, start them at zero.
        if module.bias is not None:
            torch.nn.init.zeros_(module.bias)

    # Embedding-table entries also receive small random values.
    elif isinstance(module, nn.Embedding):
        torch.nn.init.normal_(
            module.weight,
            mean=0.0,
            std=0.02,
        )
```

`mean=0.0` means the random values are centred around zero.

`std=0.02` controls their spread. Most values should begin fairly close to zero, commonly within a few hundredths of zero.

Not every parameter starts randomly:

- Linear and embedding weights start with small random values.
- Linear biases start at `0`.
- RMSNorm weights start at `1`.

## 6. Tiny Number Example

Suppose one parameter begins as:

```text
initial parameter = 0.020
```

Training computes:

```text
gradient = 0.500
learning rate = 0.010
```

A simplified update is:

```text
new parameter = old parameter - learning_rate × gradient
new parameter = 0.020 - (0.010 × 0.500)
new parameter = 0.015
```

Repeated updates gradually turn initial numbers into learned parameters.

The random seed helps make the same initialization repeatable.

## 7. Beginner Questions

1. In beginner terms, what does training a model from scratch mean?
2. Do the initial random parameters already contain learned language knowledge?
3. What is weight initialization?
4. What does `mean=0.0` tell us about the random values?
5. Does every model parameter start with a random value?
6. How does the random seed affect initialization?
7. Is training from scratch the same as using an untrained tokenizer?

## 8. Exercise

Classify each situation:

**A.** Create a new model with randomly initialized parameters and begin training.

**B.** Load a pretrained model’s parameters and continue training.

**C.** Load `latest.pt` after your own training run crashed.

Answer:

1. Which situation begins model training from scratch?
2. Which situation begins with parameters that already learned something?
3. Which situation resumes interrupted training?
4. Calculate this simplified update:

```text
old parameter = 0.030
gradient = 0.400
learning rate = 0.010

new parameter = ?
```

# Lesson 88: Why Not Initialize Every Weight to Zero?

## 1. Simplest Explanation

Different parts of the model need opportunities to learn different things.

If many parts start with exactly the same value and perform the same work, they may receive the same updates and remain identical. This wastes the model’s capacity.

Small random starting values make the parts slightly different.

## 2. Analogy

Imagine giving eight students:

- The same information
- The same instructions
- The same starting answer
- The same corrections

They may continue producing identical answers. Having eight students would provide little benefit.

Giving them slightly different starting points allows them to develop different approaches.

## 3. Technical Term: Breaking Symmetry

When identical model units behave identically, we call this **symmetry**.

Using different random starting weights is called **breaking symmetry**.

It allows different:

- Attention heads
- Embedding entries
- MLP units
- Transformer layers

to learn different patterns.

Random initialization does not assign them specific jobs. It simply prevents them from being identical at the beginning.

## 4. Where It Appears in the Repo

The repo initializes linear weights randomly in [gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:350):

```python
if isinstance(module, nn.Linear):
    torch.nn.init.normal_(
        module.weight,
        mean=0.0,
        std=0.02,
    )
```

Embeddings are also initialized randomly:

```python
elif isinstance(module, nn.Embedding):
    torch.nn.init.normal_(
        module.weight,
        mean=0.0,
        std=0.02,
    )
```

## 5. Code Explained Slowly

```python
torch.nn.init.normal_(
    # The parameter numbers that will be initialized.
    module.weight,

    # Centre the possible values around zero.
    mean=0.0,

    # Keep the random values small.
    std=0.02,
)
```

This might produce values such as:

```text
[0.012, -0.018, 0.006, 0.025]
```

The numbers are small, but they are not identical.

Some parameters can safely start at zero:

```python
torch.nn.init.zeros_(module.bias)
```

Starting biases at zero is acceptable here because the layer’s weights are already different and random.

## 6. Tiny Number Example

Suppose two units both start at zero:

```text
Unit A weight = 0
Unit B weight = 0
```

They both receive gradient `0.3`, with learning rate `0.1`:

```text
A = 0 - (0.1 × 0.3) = -0.03
B = 0 - (0.1 × 0.3) = -0.03
```

They are still identical.

Now give them different starting values:

```text
Unit A weight =  0.02
Unit B weight = -0.01
```

For input `2`:

```text
A output = 2 ×  0.02 =  0.04
B output = 2 × -0.01 = -0.02
```

They begin differently and can develop differently during training.

## 7. Beginner Questions

1. Why can initializing all weights to zero be a problem?
2. In beginner terms, what is symmetry?
3. What does breaking symmetry mean?
4. Do random initial values already contain learned knowledge?
5. Why are the repo’s random values small?
6. Why can biases start at zero even though weights start randomly?

## 8. Exercise

Two units begin with:

```text
Unit A weight = 0
Unit B weight = 0
gradient for both = 0.4
learning rate = 0.05
```

Answer:

1. What is Unit A’s new weight?
2. What is Unit B’s new weight?
3. Are the two units still identical?
4. What could the repo do at initialization to make them different?
# Lesson 89: What Does “8M Parameters” Mean?

## 1. Simplest Explanation

A model contains many adjustable numbers called **parameters**.

“8M parameters” means the model contains approximately eight million learnable numbers.

```text
M = million
B = billion
```

For example:

```text
8M = approximately 8,000,000
7B = approximately 7,000,000,000
```

## 2. Analogy

Imagine a machine containing millions of adjustable knobs.

During training:

- Gradients say how each knob contributed to the error.
- The optimizer adjusts the knobs.
- Together, their settings store what the model has learned.

The **parameter count** is the number of adjustable knobs.

## 3. Technical Term: Parameter Count

A parameter is normally stored inside a tensor.

The parameter count is the total number of individual numbers across all trainable parameter tensors.

For a parameter tensor with shape `(2, 3)`:

```text
number of parameters = 2 × 3 = 6
```

Having more parameters gives a model more capacity to learn patterns, but does not automatically make it better. Larger models also need more data, memory, calculations, and training time.

## 4. Where It Appears in the Repo

The repo counts parameters in [gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:411):

```python
def count_parameters(
    model: nn.Module,
    trainable_only: bool = True,
) -> int:
    params = model.parameters()

    if trainable_only:
        params = (p for p in params if p.requires_grad)

    return sum(p.numel() for p in params)
```

## 5. Code Explained Slowly

```python
# Get the model's parameter tensors.
params = model.parameters()
```

Examples include embedding, attention, and MLP weight tensors.

```python
# Keep only parameters that training is allowed to change.
params = (p for p in params if p.requires_grad)
```

`requires_grad=True` means PyTorch should compute gradients for that parameter.

```python
# p.numel() counts the individual numbers in one tensor.
# sum(...) adds the counts from every parameter tensor.
return sum(p.numel() for p in params)
```

The count is saved with the training run in [pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:179).

## 6. The Repo’s Mini Model

I ran:

```bash
python scripts/model_report.py \
  --config configs/matgpt_mini_8m.yaml
```

The actual result is:

```text
parameter count = 8,391,936
```

The name “8M” is a convenient rounded size label. It does not mean the model contains exactly `8,000,000` parameters.

## 7. Tiny Example

Suppose a tiny model has these parameter tensors:

```text
Embedding weights: shape (10, 3)
Linear weights:    shape (3, 4)
Linear bias:       shape (4,)
```

Calculate each count:

```text
Embedding = 10 × 3 = 30
Weights   =  3 × 4 = 12
Bias      =          4

Total = 30 + 12 + 4 = 46 parameters
```

## 8. Beginner Questions

1. In beginner terms, what is a parameter count?
2. What does `8M` mean?
3. Does an “8M” label always mean exactly `8,000,000` parameters?
4. What does `p.numel()` count?
5. What does `requires_grad=True` mean?
6. Does having more parameters automatically guarantee a better model?
7. What is the repo’s actual Mini-model parameter count?

## 9. Exercise

A model contains:

```text
Embedding table: shape (500, 32)
MLP weight:      shape (32, 64)
MLP bias:        shape (64,)
```

Calculate:

1. Embedding parameters = ?
2. MLP weight parameters = ?
3. MLP bias parameters = ?
4. Total parameter count = ?
5. Would “18K parameters” be a reasonable rounded label?

# Lesson 90: What Is Numerical Precision?

## 1. Simplest Explanation

Model parameters and calculations contain decimal numbers such as:

```text
0.012345
-1.8372
```

A computer has limited space for storing each number. **Precision** describes how much numerical detail that storage format can preserve.

## 2. Analogy

Imagine measuring an object with two rulers:

- One ruler has many fine markings.
- One ruler has fewer markings.

The detailed ruler records a more exact measurement but requires more information. The simpler ruler uses less information but may round the measurement.

Numerical precision creates a similar trade-off.

## 3. Technical Terms

**Floating point** is a computer format for representing decimal-like numbers.

```text
FP32 = 32-bit floating point
FP16 = 16-bit floating point
```

Because eight bits make one byte:

```text
FP32 = 32 ÷ 8 = 4 bytes per number
FP16 = 16 ÷ 8 = 2 bytes per number
```

FP16 uses half as many bytes per stored number as FP32, but it represents numbers with less detail and a smaller safe range.

## 4. Tiny Precision Example

Suppose the desired number is:

```text
0.123456
```

A higher-precision format may preserve more digits:

```text
FP32 approximation: 0.123456
```

A lower-precision format might store a more rounded approximation:

```text
FP16 approximation: 0.1235
```

These values are illustrative. The exact stored result depends on the floating-point format.

## 5. Where It Appears in the Repo

The Mini configuration selects FP16 in [matgpt_mini_8m.yaml](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/configs/matgpt_mini_8m.yaml:81):

```yaml
training:
  precision: fp16
```

The training loop uses that setting in [pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:240):

```python
with autocast_context(device, cfg["training"]["precision"]):
    _, loss = train_model(x, targets=y)
```

## 6. Code Explained Slowly

The relevant logic is in [amp.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/amp.py:8):

```python
# If training is not using a CUDA GPU,
# do not enable CUDA's automatic precision selection.
if device.type != "cuda":
    return nullcontext()

# If the configuration requests fp16,
# let PyTorch use FP16 for suitable CUDA calculations.
if precision == "fp16":
    return torch.autocast(
        device_type="cuda",
        dtype=torch.float16,
    )
```

`nullcontext()` means “do nothing special.”

`autocast` means PyTorch automatically runs suitable calculations in lower precision while keeping other calculations in a safer precision.

Important distinction:

> `precision: fp16` does not simply convert every model parameter permanently to FP16.

The repo uses **automatic mixed precision**, which we will study separately in the next lesson.

## 7. Memory Example

Suppose we store `1,000,000` numbers:

```text
FP32: 1,000,000 × 4 bytes = 4,000,000 bytes
FP16: 1,000,000 × 2 bytes = 2,000,000 bytes
```

FP16 requires half the storage for those numbers.

However, total training memory also includes gradients, optimizer state, temporary calculations, and batches. Parameter storage is only one part.

## 8. Beginner Questions

1. In beginner terms, what does numerical precision describe?
2. What does `FP` stand for?
3. How many bits and bytes does one FP32 number use?
4. How many bits and bytes does one FP16 number use?
5. Which format preserves more numerical detail: FP32 or FP16?
6. Why can FP16 help GPU training?
7. Does `precision: fp16` mean every model parameter is permanently stored as FP16?
8. What does `nullcontext()` mean here?

## 9. Exercise

A model contains `2,000,000` numbers.

Calculate:

1. FP32 storage = `2,000,000 × 4` = ? bytes
2. FP16 storage = `2,000,000 × 2` = ? bytes
3. Which format uses less storage?
4. How many bytes are saved by using FP16?
5. If no CUDA GPU is available, does this repo enable CUDA FP16 autocasting?

# Lesson 91: What Is Automatic Mixed Precision?

## 1. Simplest Explanation

Training does not have to use the same numerical precision for every calculation.

It can use:

- FP16 for calculations that work safely with less detail.
- FP32 for calculations that need more numerical detail.

This combination can make training faster while reducing some of FP16’s risks.

## 2. Analogy

Imagine measuring two things:

- The length of a room does not require a microscopic ruler.
- The thickness of a human hair requires a finer ruler.

Using the most detailed ruler for every measurement can be wasteful. Using only a rough ruler can produce inaccurate results.

Instead, you choose the appropriate ruler for each job.

## 3. Technical Term: AMP

**AMP** means **Automatic Mixed Precision**.

- **Mixed** means using more than one precision.
- **Automatic** means PyTorch chooses suitable precision for supported calculations.
- **Precision** means how much numerical detail the format preserves.

AMP tries to combine FP16’s speed and lower memory use with FP32’s larger numerical range and detail.

## 4. Where It Appears in the Repo

The training loop uses AMP in [pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:240):

```python
with autocast_context(
    device,
    cfg["training"]["precision"],
):
    _, loss = train_model(x, targets=y)
    scaled_loss = (
        loss
        / cfg["training"]["gradient_accumulation_steps"]
    )
```

## 5. Code Explained Slowly

The word `with` creates a temporary context:

```python
with autocast_context(device, precision):
    # Automatic precision selection applies here.
    _, loss = train_model(x, targets=y)

# The autocast context has ended here.
```

The context is created in [amp.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/amp.py:8):

```python
def autocast_context(device, precision):
    # CUDA AMP is unavailable when we are not using a CUDA GPU.
    if device.type != "cuda":
        return nullcontext()

    # Enable automatic FP16 selection when requested.
    if precision == "fp16":
        return torch.autocast(
            device_type="cuda",
            dtype=torch.float16,
        )

    # Otherwise, do nothing special.
    return nullcontext()
```

`torch.autocast(...)` does not simply force everything to FP16. PyTorch follows rules for choosing the precision of supported operations.

The model’s main parameters also normally remain FP32 in this repo. Autocast mainly changes suitable calculations and their temporary results during the forward pass.

## 6. Tiny Example

Imagine a forward pass containing:

```text
1. A large matrix multiplication
2. A numerically sensitive loss calculation
```

AMP might use:

```text
Matrix multiplication -> FP16
Sensitive calculation -> FP32
```

This is an illustration. PyTorch’s autocast rules decide the actual precision for each supported operation.

## 7. Why AMP Helps

Possible benefits include:

- Faster calculations on compatible GPUs
- Less memory for selected temporary tensors
- More numerical safety than forcing every calculation into FP16

AMP does not eliminate every FP16 problem. Very small gradients can still become difficult to represent. We will handle that in the next lesson.

## 8. Beginner Questions

1. In beginner terms, what is mixed precision?
2. What does AMP stand for?
3. Why is AMP called “mixed”?
4. Who chooses the precision of supported operations inside `autocast`: you or PyTorch?
5. Does autocast permanently convert every model parameter to FP16?
6. What does the `with` block control?
7. Name two possible benefits of AMP.
8. Does this repo enable CUDA AMP when training on the CPU?

## 9. Exercise

Given:

```python
with autocast_context(device, "fp16"):
    logits, loss = model(x, targets=y)

optimizer.step()
```

Answer:

1. Which lines are inside the autocast context?
2. Is `optimizer.step()` inside that context?
3. Does `"fp16"` mean every operation is forced to FP16?
4. If `device.type == "cpu"`, what context does the repo return?
5. Why might mixed FP16 and FP32 calculations be safer than forcing everything into FP16?

# Lesson 92: What Is Gradient Scaling?

## 1. Simplest Explanation

During FP16 training, some gradients can be extremely small.

FP16 may be unable to represent such a tiny number and may store it as zero. A zero gradient gives the optimizer no useful adjustment direction.

**Gradient scaling** temporarily makes gradients larger so they survive the FP16 calculation.

## 2. Analogy

Imagine text printed so small that a scanner cannot see it.

You can:

1. Enlarge the page.
2. Scan the visible text.
3. Reduce the measurements back to their original size.

Gradient scaling follows the same idea.

## 3. Technical Term: Underflow

When a number is too small for a numerical format to represent, it may become zero. This is called **underflow**.

Gradient scaling helps prevent FP16 gradient underflow:

```text
Tiny loss
   -> multiply by a large scale
   -> run backward()
   -> produce larger gradients
   -> divide gradients by the scale
   -> optimizer receives correct-sized gradients
```

## 4. Tiny Number Example

Suppose the true gradient is:

```text
0.00000002
```

Use a scale of `1,000`:

```text
scaled gradient = 0.00000002 × 1,000
                = 0.00002
```

After backward calculation:

```text
unscaled gradient = 0.00002 ÷ 1,000
                  = 0.00000002
```

The intended gradient is unchanged, but the temporary larger value is easier for FP16 to preserve.

## 5. Where It Appears in the Repo

The scaler is created in [amp.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/amp.py:24):

```python
def make_grad_scaler(device, precision):
    enabled = (
        device.type == "cuda"
        and precision == "fp16"
    )

    return torch.amp.GradScaler(
        "cuda",
        enabled=enabled,
    )
```

It is enabled only for CUDA FP16 training.

## 6. Training Code Explained Slowly

The training code is in [pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:248):

```python
# Temporarily multiply the loss by the scaler's scale.
# backward() then produces temporarily enlarged gradients.
scaler.scale(scaled_loss).backward()

# Divide gradients by the scale to restore their real sizes.
scaler.unscale_(optimizer)

# Clip the real, unscaled gradients if they are too large.
grad_norm = torch.nn.utils.clip_grad_norm_(
    model.parameters(),
    cfg["training"]["grad_clip"],
)

# Update parameters when the gradients contain valid numbers.
scaler.step(optimizer)

# Adjust the scale for future training steps.
scaler.update()
```

`scaler.update()` can change the scale automatically. If scaling produces numbers that are too large, PyTorch can reduce the scale.

## 7. Two Different Uses of “Scale”

This repo contains:

```python
scaled_loss = loss / gradient_accumulation_steps
```

That division keeps gradient accumulation correctly averaged.

Then:

```python
scaler.scale(scaled_loss)
```

That operation temporarily multiplies the loss to protect FP16 gradients.

They are different operations with different purposes.

## 8. Beginner Questions

1. What problem does gradient scaling help prevent?
2. In beginner terms, what is underflow?
3. Why does the scaler multiply the loss before `backward()`?
4. Why must gradients be unscaled before the optimizer uses them?
5. Does gradient scaling intentionally change the final gradient value?
6. When does this repo enable its gradient scaler?
7. What does `scaler.update()` do?
8. Are loss division for accumulation and FP16 gradient scaling the same operation?

## 9. Exercise

Suppose:

```text
true gradient = 0.000002
scale         = 1,000
```

Calculate:

1. Temporarily scaled gradient = ?
2. Gradient after unscaling = ?
3. Which value should the optimizer ultimately use?
4. Put these operations in order:
   - Update the scale
   - Backward using scaled loss
   - Optimizer step
   - Unscale gradients
   - Clip gradients


      - Update the scale
   - Backward using scaled loss
 - Unscale gradients
   - Clip gradients
   - Optimizer step


# Lesson 93: What Is Gradient Clipping?

## 1. Simplest Explanation

Sometimes the model produces unusually large gradients.

Large gradients can cause the optimizer to make a dangerously large parameter update. This can make training unstable.

**Gradient clipping** limits the gradients to a safe maximum size before the optimizer uses them.

## 2. Analogy

Imagine steering a car.

Small steering corrections help you stay on the road. Suddenly turning the steering wheel as far as possible could send the car off the road.

Gradient clipping limits an extreme correction while preserving its general direction.

## 3. Technical Term: Gradient Norm

A model has many gradients. The **gradient norm** summarizes their combined size as one number.

For the simple gradient vector:

```text
gradients = [3, 4]
```

The norm is:

```text
norm = sqrt(3² + 4²)
     = sqrt(9 + 16)
     = sqrt(25)
     = 5
```

This calculation is called the **L2 norm**.

## 4. How Clipping Works

Suppose:

```text
gradient norm = 5
maximum norm  = 1
```

The gradients are too large, so we scale them by:

```text
scale factor = maximum norm / current norm
             = 1 / 5
             = 0.2
```

Apply that scale to every gradient:

```text
[3, 4] × 0.2 = [0.6, 0.8]
```

The new norm is:

```text
sqrt(0.6² + 0.8²) = 1
```

The gradient direction remains the same, but its overall size becomes smaller.

If the norm is already below the limit, clipping does not need to reduce it.

## 5. Where It Appears in the Repo

The Mini configuration sets the maximum norm in [matgpt_mini_8m.yaml](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/configs/matgpt_mini_8m.yaml:93):

```yaml
grad_clip: 1.0
```

The training loop applies it in [pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:254).

## 6. Code Explained Slowly

```python
# Restore the gradients' real sizes after FP16 gradient scaling.
scaler.unscale_(optimizer)

# Calculate the combined gradient norm.
# If it exceeds grad_clip, scale the gradients down.
grad_norm = torch.nn.utils.clip_grad_norm_(
    # Parameters whose gradients should be examined.
    model.parameters(),

    # Maximum allowed combined gradient norm.
    cfg["training"]["grad_clip"],
)

# Let the optimizer use the clipped gradients.
scaler.step(optimizer)
```

The repo unscales first because clipping must examine the gradients’ real sizes, not the temporarily enlarged values created by `GradScaler`.

The returned `grad_norm` is recorded in the training metrics:

```python
"grad_norm": float(grad_norm.detach().cpu())
```

This helps us notice unusually large gradients.

## 7. Important Limitation

Gradient clipping is a safety guard. It does not necessarily fix the underlying reason gradients became large.

Possible causes might include:

- Learning rate too high
- Unstable numerical calculations
- Problematic data
- A model or training bug

## 8. Beginner Questions

1. In beginner terms, what does gradient clipping do?
2. What does a gradient norm summarize?
3. What is the norm of `[3, 4]`?
4. If `grad_clip=1.0` and the norm is `0.6`, must it be reduced?
5. If `grad_clip=1.0` and the norm is `5.0`, must it be reduced?
6. Why does the repo unscale gradients before clipping?
7. Does norm clipping mainly change the gradient’s direction or its size?
8. Does clipping guarantee that the cause of large gradients is fixed?

## 9. Exercise

Given:

```text
gradients    = [6, 8]
maximum norm = 2
```

Calculate:

1. Original norm = `sqrt(6² + 8²)` = ?
2. Scale factor = `maximum norm / original norm` = ?
3. New first gradient = `6 × scale factor` = ?
4. New second gradient = `8 × scale factor` = ?
5. New gradient norm = ?
6. If the original norm had been `1.5`, would clipping reduce it?

# Lesson 94: What Is Numerical Overflow?

## 1. Simplest Explanation

A numerical format can represent numbers only within a certain range.

If a calculation produces a number that is too large for the format, the computer cannot store the normal result. This is called **overflow**.

## 2. Analogy

Imagine a display that can show numbers only up to:

```text
99,999
```

If a calculation produces `150,000`, the display cannot show the correct result.

Floating-point formats also have maximum representable values.

## 3. Technical Terms: Range And Infinity

A format’s **range** describes how small or large its representable values can be.

The largest finite positive FP16 value is:

```text
65,504
```

A larger FP16 result may become:

```text
inf
```

`inf` means **infinity**. Here, it acts as a special value indicating that the result exceeded the format’s finite range.

A very large negative value may become:

```text
-inf
```

## 4. Tiny Example

Suppose this multiplication happens in FP16:

```text
50,000 × 2 = 100,000
```

But:

```text
100,000 > 65,504
```

Therefore, FP16 cannot store the normal finite result. It may become:

```text
inf
```

## 5. Underflow Versus Overflow

```text
Underflow:
Number is too small in magnitude
Possible result -> 0

Overflow:
Number is too large in magnitude
Possible result -> inf or -inf
```

Both can damage training calculations.

## 6. Connection To Gradient Scaling

Gradient scaling multiplies the loss to protect tiny gradients:

```python
scaler.scale(scaled_loss).backward()
```

But if the chosen scale becomes too large, the enlarged gradients might overflow.

This creates a balancing problem:

```text
Scale too small -> possible underflow
Scale too large -> possible overflow
```

PyTorch’s `GradScaler` adjusts its scale to find a workable size.

## 7. Where It Appears in the Repo

The scaler is created in [amp.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/amp.py:24):

```python
enabled = (
    device.type == "cuda"
    and precision == "fp16"
)

scaler = torch.amp.GradScaler(
    "cuda",
    enabled=enabled,
)
```

The training loop uses it in [pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:252):

```python
# Enlarge the loss before backward.
scaler.scale(scaled_loss).backward()

# Later, let the scaler perform the optimizer step.
scaler.step(optimizer)

# Adjust the scale for the next step.
scaler.update()
```

The repo does not manually check for FP16 overflow in this block. It delegates that work to PyTorch’s `GradScaler`.

We will examine what `scaler.step()` does after detecting an unsafe value in the next lesson.

## 8. Beginner Questions

1. In beginner terms, what is numerical overflow?
2. What does numerical range describe?
3. What is the largest finite positive FP16 value?
4. What does `inf` mean?
5. What is the difference between underflow and overflow?
6. Why can an excessively large gradient scale cause overflow?
7. Does the repo manually check for overflow here, or delegate it to `GradScaler`?
8. Why does `scaler.update()` sometimes need to reduce the scale?

## 9. Exercise

Assume FP16’s maximum finite value is `65,504`.

For each calculation, say whether the result is inside the finite FP16 range or may overflow:

```text
A. 20,000 × 2 = 40,000
B. 40,000 × 2 = 80,000
C. -30,000 × 2 = -60,000
D. -40,000 × 2 = -80,000
```

Then calculate:

```text
true gradient = 0.1
scale         = 1,000,000

scaled gradient = ?
```

Is that scaled gradient within FP16’s finite range?


# Lesson 95: Why Can GradScaler Skip an Optimizer Step?

## 1. Simplest Explanation

The optimizer should update parameters only when the gradients contain usable numbers.

If gradients contain broken numerical values, using them could corrupt the model’s parameters.

`GradScaler` checks for these values and can skip the update.

## 2. Analogy

Imagine a bank employee preparing account changes.

Before applying them, a safety system checks the amounts:

```text
Deposit: 50       -> usable
Withdrawal: 20    -> usable
Deposit: infinity -> invalid
```

If any amount is invalid, the system rejects the complete transaction rather than damaging the accounts.

## 3. Technical Terms

A **finite** value is an ordinary number within the numerical format’s range:

```text
0.5
-12.7
65,000
```

**Non-finite** values include:

```text
inf   -> positive infinity
-inf  -> negative infinity
NaN   -> Not a Number
```

`NaN` is a special value representing an undefined or invalid numerical result. One simplified example is:

```text
0 ÷ 0 -> NaN
```

## 4. Why Skipping Matters

Suppose:

```text
parameter     = 2
learning rate = 0.1
gradient      = inf
```

A normal update would attempt:

```text
new parameter = 2 - (0.1 × inf)
              = -inf
```

The parameter would become unusable.

If the optimizer step is skipped:

```text
parameter remains 2
```

That gives training a chance to continue later with a smaller gradient scale.

## 5. Where It Appears in the Repo

The relevant code is in [pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:255):

```python
# Unscale gradients and check them for inf or NaN.
scaler.unscale_(optimizer)

# Clip the gradients.
grad_norm = torch.nn.utils.clip_grad_norm_(
    model.parameters(),
    cfg["training"]["grad_clip"],
)

# Update parameters only if gradients are safe.
scaler.step(optimizer)

# Adjust the scale for future steps.
scaler.update()
```

## 6. Code Explained Slowly

Because the repo explicitly calls:

```python
scaler.unscale_(optimizer)
```

PyTorch:

1. Restores the gradients’ real sizes.
2. Checks whether they contain `inf` or `NaN`.
3. Remembers the check result.

Then:

```python
scaler.step(optimizer)
```

behaves like this simplified logic:

```python
if gradients_are_finite:
    optimizer.step()
else:
    # Do not corrupt the model parameters.
    skip_the_update()
```

Finally:

```python
scaler.update()
```

can reduce the gradient scale after an unsafe result.

The repo delegates this detection to PyTorch’s `GradScaler`; it does not write the `inf` and `NaN` check manually.

## 7. Tiny Example

Safe case:

```text
parameter = 2
gradient  = 0.5
lr        = 0.1

new parameter = 2 - (0.1 × 0.5)
              = 1.95
```

Unsafe case:

```text
parameter = 2
gradient  = inf

optimizer step is skipped
parameter remains 2
```

## 8. Beginner Questions

1. What is a finite number?
2. What does `NaN` stand for?
3. Why is an `inf` or `NaN` gradient unsafe?
4. Where does the repo’s scaler check gradients for non-finite values?
5. What does `scaler.step(optimizer)` do when gradients are finite?
6. What does it do when any gradient is `inf` or `NaN`?
7. Why might `scaler.update()` reduce the scale after a skipped step?
8. Does the repo implement the check manually?

## 9. Exercise

Decide whether the optimizer update should run or be skipped:

```text
A. gradients = [0.2, -0.4, 0.1]
B. gradients = [0.2, inf, 0.1]
C. gradients = [NaN, -0.4, 0.1]
```

Then calculate:

```text
parameter     = 5
gradient      = 0.5
learning rate = 0.1
```

1. New parameter if the gradient is finite = ?
2. Parameter value if the update is skipped = ?


# Lesson 96: What Is BF16?

## 1. Simplest Explanation

BF16 is another format for storing and calculating decimal-like numbers.

Like FP16, it uses 16 bits, or 2 bytes, per number. However, it uses those bits differently.

- FP16 keeps more fine detail.
- BF16 can represent a much wider range of sizes.

## 2. Analogy

Imagine two maps of the same physical size.

- Map A shows one small city with many street details.
- Map B shows an entire country with fewer street details.

FP16 is more like Map A: more detail, smaller range.

BF16 is more like Map B: wider range, less detail.

## 3. How Floating-Point Bits Are Used

Floating-point formats divide their bits into three parts:

- **Sign:** whether the number is positive or negative
- **Exponent:** controls the size range
- **Fraction:** controls numerical detail

Their simplified layouts are:

```text
FP16:  1 sign bit + 5 exponent bits + 10 fraction bits = 16
BF16:  1 sign bit + 8 exponent bits +  7 fraction bits = 16
FP32:  1 sign bit + 8 exponent bits + 23 fraction bits = 32
```

BF16 uses the same number of exponent bits as FP32. That gives it a range similar to FP32, but with less fine detail.

## 4. Range Comparison

```text
FP16 maximum: approximately 65,504
BF16 maximum: approximately 3.39 × 10³⁸
FP32 maximum: approximately 3.40 × 10³⁸
```

Therefore:

```text
70,000 stored as FP16 -> inf
70,000 stored as BF16 -> approximately 70,144
```

BF16 keeps the value finite, but rounds it because it has fewer fraction bits.

## 5. Detail Comparison

I stored `0.123456` using PyTorch:

```text
FP16 -> 0.12347412109375
BF16 -> 0.12353515625
```

Both are approximations. Here, FP16 stays closer because it has more fraction bits.

The main trade-off is:

```text
FP16 -> finer detail, smaller range
BF16 -> less detail, much wider range
FP32 -> finer detail and wide range, but twice the storage
```

## 6. Where It Appears in the Repo

The repo supports BF16 autocasting in [amp.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/amp.py:15):

```python
# Use FP16 autocasting when requested.
if precision == "fp16":
    return torch.autocast(
        device_type="cuda",
        dtype=torch.float16,
    )

# Use BF16 autocasting when requested.
if precision == "bf16":
    return torch.autocast(
        device_type="cuda",
        dtype=torch.bfloat16,
    )
```

## 7. Why The Scaler Is Different

The repo enables `GradScaler` only for FP16:

```python
enabled = (
    device.type == "cuda"
    and precision == "fp16"
)
```

It does not enable it for BF16.

BF16’s much wider numerical range makes gradient overflow and underflow less likely, so BF16 training commonly does not require gradient scaling.

The Mini configuration currently chooses FP16:

```yaml
training:
  precision: fp16
```

## 8. Beginner Questions

1. How many bits and bytes does BF16 use?
2. What does the exponent part mainly control?
3. What does the fraction part mainly control?
4. Which has more fraction bits: FP16 or BF16?
5. Which has the wider numerical range: FP16 or BF16?
6. Why can BF16 represent `70,000` while FP16 overflows?
7. Does the repo enable `GradScaler` for BF16?
8. Which precision does the current Mini configuration request?

## 9. Exercise

Complete this table:

```text
Format | Bits | Bytes | Approximate maximum
FP16   | ?    | ?     | ?
BF16   | ?    | ?     | ?
FP32   | ?    | ?     | ?
```

Then answer:

1. Which format uses less memory: FP16 or BF16?
2. Which format would you choose between FP16 and BF16 if you specifically needed to keep `100,000` finite?
3. Which of those two formats has more fraction bits and therefore more fine detail?
4. If the repo configuration changes from `fp16` to `bf16`, will `GradScaler` remain enabled?

# Lesson 97: Detecting Numerical Instability In Metrics

## 1. Simplest Explanation

Training records important numbers as it runs.

By watching those numbers, we can detect signs that calculations are becoming unstable before wasting a long training run.

## 2. Analogy

A car dashboard shows speed, fuel, and temperature.

A single number does not explain every problem, but warning values can tell you when to stop and investigate.

Training metrics serve as the model’s dashboard.

## 3. Technical Term: Metric

A **metric** is a recorded measurement.

The repo records metrics such as:

- `train_loss`: training mistake score
- `val_loss`: validation mistake score
- `grad_norm`: combined gradient size
- `lr`: current learning rate
- `tokens_per_second`: training speed
- `peak_memory_mb`: highest recorded GPU memory use

## 4. Strong Instability Signals

These are strong numerical warning signs:

```text
train_loss = NaN
train_loss = inf
grad_norm  = NaN
grad_norm  = inf
```

A sudden large but finite value is a warning, not automatic proof:

```text
usual grad_norm = about 1.2
new grad_norm   = 500
```

You should examine whether it happens once or repeatedly and what happened to the loss and learning rate.

## 5. Tiny Example

Healthy-looking trend:

```text
Step | Train loss | Gradient norm
10   | 4.2        | 1.3
20   | 4.0        | 1.1
30   | 3.8        | 1.4
```

Clearly unstable trend:

```text
Step | Train loss | Gradient norm
10   | 4.2        | 1.3
20   | 7.9        | 40.0
30   | inf        | inf
40   | NaN        | NaN
```

`NaN` or `inf` requires immediate investigation.

## 6. Where It Appears In The Repo

The repo constructs its training metrics in [pretrain.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/training/pretrain.py:277):

```python
train_metrics = {
    # Current optimizer-step counter.
    "global_step": state["global_step"],

    # Total training token positions processed.
    "tokens_processed": state["tokens_processed"],

    # Current training mistake score.
    "train_loss": step_loss,

    # Current learning rate.
    "lr": lr,

    # Combined gradient size before clipping reduced it.
    "grad_norm": float(grad_norm.detach().cpu()),

    # Processing speed.
    "tokens_per_second": tokens_per_second,

    # Highest recorded CUDA memory use.
    "peak_memory_mb": _peak_memory_mb(device),
}
```

It writes them to CSV:

```python
append_csv_row(metrics_path, train_metrics)
```

The output path is:

```text
runs/<run-name>/metrics.csv
```

## 7. Important Gradient-Norm Detail

PyTorch’s `clip_grad_norm_()` returns the norm it measured before reducing the gradients.

Therefore, with:

```yaml
grad_clip: 1.0
```

you might still see:

```text
grad_norm = 5.0
```

in `metrics.csv`.

This means the measured norm was `5.0`; clipping then reduced the gradients before the optimizer update.

## 8. Current Observability Gap

The repo currently does not explicitly log:

- The current `GradScaler` scale
- How many optimizer updates were skipped

This means `metrics.csv` can reveal `NaN`, `inf`, and unusual norms, but it does not directly show every GradScaler decision.

## 9. Beginner Questions

1. In beginner terms, what is a metric?
2. Name two metrics that can reveal numerical instability.
3. What does `train_loss = NaN` tell you?
4. Is one large but finite gradient norm definite proof of a broken run?
5. Why is the learning rate useful when investigating a loss spike?
6. Why can logged `grad_norm` be greater than `grad_clip`?
7. Where does the repo save its metrics?
8. Does the repo currently log the GradScaler scale or skipped-update count?

## 10. Exercise

Classify each row as **normal-looking**, **warning**, or **clearly unstable**:

```text
A. train_loss = 3.8, grad_norm = 1.2
B. train_loss = 4.1, grad_norm = 80.0
C. train_loss = inf, grad_norm = inf
D. train_loss = NaN, grad_norm = NaN
```

Then answer:

1. Which rows require immediate investigation?
2. If `grad_clip=1.0` and the logged norm is `80.0`, can clipping still reduce the gradients before the update?
3. Which two GradScaler measurements are missing from the current metrics?

# Lesson 98: Why Does A Transformer Need Position Information?

## 1. Simplest Explanation

Word order changes meaning:

```text
The dog chased the cat.
The cat chased the dog.
```

Both sentences contain similar tokens, but the order tells us who performed the action.

The model therefore needs information about where each token appears.

## 2. Analogy

Imagine students sitting in numbered seats.

A name badge tells you **who** the student is:

```text
Student: Mary
```

The seat number tells you **where** Mary is:

```text
Position: seat 3
```

A token embedding is like the name badge. Position information is like the seat number.

## 3. Why Embeddings Are Not Enough

Suppose `" dog"` has token ID `25`.

Its embedding might be:

```text
token 25 -> [0.2, -0.1, 0.4]
```

The embedding lookup returns the same learned profile wherever that token appears:

```text
Position 0: " dog" -> [0.2, -0.1, 0.4]
Position 4: " dog" -> [0.2, -0.1, 0.4]
```

The embedding identifies the token, but does not by itself say whether it is at position `0` or position `4`.

## 4. Technical Term: Positional Information

**Positional information** tells the model where tokens occur and helps it reason about their order or distance.

Positions usually begin at zero:

```text
Tokens:    ["The", " dog", " runs", "."]
Positions: [  0,      1,       2,    3 ]
```

The token sequence is already stored in order, but the same Transformer calculations are applied to every token position. The model needs a numerical signal that makes positions distinguishable during attention.

## 5. Causal Mask Versus Position Information

These have different jobs:

```text
Causal mask:
Controls which tokens are visible.
Prevents looking into the future.

Position information:
Helps describe where visible tokens occur.
```

The causal mask says:

> “You may look at these earlier tokens.”

Position information helps say:

> “This token is nearby, while that token is farther back.”

## 6. The Repo’s Method: RoPE

The repo uses **RoPE**, meaning **Rotary Position Embedding**.

RoPE changes the query and key number profiles according to their positions before attention scores are calculated.

It is created in [gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:129):

```python
# Create the RoPE position-information system.
self.rope = RotaryEmbedding(
    # Numbers available to each attention head.
    config.head_dim,

    # Maximum number of token positions.
    config.context_length,

    # Controls RoPE's position frequencies.
    config.rope_base,
)
```

## 7. Code Explained Slowly

During attention:

```python
# q contains queries for every token position.
# k contains keys for every token position.
# v contains the information that can be collected.
q, k, v = ...
```

Then:

```python
# Modify queries and keys using their positions.
q, k = self.rope(q, k)
```

RoPE is applied to:

```text
queries -> yes
keys    -> yes
values  -> no
```

It changes the numbers inside `q` and `k`, but does not change their shapes.

The Mini configuration supports positions up to its context length:

```yaml
context_length: 256
rope_base: 10000.0
```

We will explain the actual rotation and its mathematics in the next lesson.

## 8. Tiny Example

Consider:

```text
Sequence A: dog bites man
Sequence B: man bites dog
```

Using fake token IDs:

```text
dog   -> 5
bites -> 9
man   -> 7
```

The sequences are:

```text
A = [5, 9, 7]
B = [7, 9, 5]
```

They contain the same token IDs, but at different positions. Position information helps attention distinguish these arrangements.

## 9. Beginner Questions

1. Why is token order important?
2. Does a token embedding automatically change when the same token appears at a different position?
3. In beginner terms, what does positional information provide?
4. What is the difference between a causal mask and position information?
5. What does RoPE stand for?
6. Which attention parts receive RoPE: queries, keys, or values?
7. Does RoPE normally change the shape of `q` and `k`?
8. What is the maximum number of token positions in the Mini configuration?

## 10. Exercise

Given:

```text
Tokens: ["Mary", " likes", " pizza", "."]
```

Fill in the positions:

```text
"Mary"   -> position ?
" likes" -> position ?
" pizza" -> position ?
"."      -> position ?
```

Then answer:

1. If `"Mary"` appears again at position `10`, is its basic token embedding looked up from a different token ID?
2. What extra information distinguishes the two occurrences?
3. Does RoPE add another token to the sequence, or modify query and key numbers?

# Lesson 99: What Does “Rotation” Mean In RoPE?

## 1. Simplest Explanation

RoPE changes pairs of query and key numbers by rotating them.

Each token position uses a particular rotation. Therefore, the resulting query and key numbers carry position information.

## 2. Analogy

Imagine a clock hand.

The hand’s length stays the same, but its direction changes as it rotates:

```text
12 o'clock -> pointing upward
3 o'clock  -> pointing right
6 o'clock  -> pointing downward
```

RoPE similarly changes a vector’s direction without normally changing its length.

## 3. A Two-Number Vector

Consider:

```text
vector = [x, y]
```

You can imagine:

- `x` as the horizontal coordinate
- `y` as the vertical coordinate

A 90-degree counterclockwise rotation changes:

```text
[x, y] -> [-y, x]
```

For example:

```text
[2, 1] -> [-1, 2]
```

## 4. Rotation Formula

For an angle `θ`, pronounced “theta”:

```text
new_x = x × cos(θ) - y × sin(θ)
new_y = x × sin(θ) + y × cos(θ)
```

In vector form:

```text
rotated = original × cos(θ)
        + rotate_half(original) × sin(θ)
```

For `90°`:

```text
cos(90°) = 0
sin(90°) = 1
```

Therefore:

```text
[2, 1] × 0 + [-1, 2] × 1
= [-1, 2]
```

## 5. Rotation Preserves Length

Before rotation:

```text
length = sqrt(2² + 1²)
       = sqrt(5)
```

After rotation:

```text
length = sqrt((-1)² + 2²)
       = sqrt(5)
```

The numbers changed, but the vector’s overall length stayed the same.

## 6. Where It Appears In The Repo

The helper appears in [gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:78):

```python
def _rotate_half(x: torch.Tensor) -> torch.Tensor:
    # Divide the final dimension into two equal parts.
    x1 = x[..., : x.shape[-1] // 2]
    x2 = x[..., x.shape[-1] // 2 :]

    # Change [x1, x2] into [-x2, x1].
    return torch.cat((-x2, x1), dim=-1)
```

For a two-number vector:

```text
x  = [2, 1]
x1 = [2]
x2 = [1]

rotate_half(x) = [-1, 2]
```

For four numbers:

```text
x  = [1, 2, 3, 4]
x1 = [1, 2]
x2 = [3, 4]

rotate_half(x) = [-3, -4, 1, 2]
```

## 7. Applying The Rotation

The repo applies the full formula here:

```python
return (
    (q * cos) + (_rotate_half(q) * sin),
    (k * cos) + (_rotate_half(k) * sin),
)
```

Slowly:

```text
q × cos                     -> original-direction part
rotate_half(q) × sin        -> rotated-direction part
add them                    -> position-rotated query
```

The same process is applied to `k`.

Different positions receive different sine and cosine values. We will explain how those values are created in the next lesson.

## 8. Position Zero

At an angle of zero:

```text
cos(0) = 1
sin(0) = 0
```

Therefore:

```text
rotated = original × 1 + rotate_half(original) × 0
        = original
```

So a zero-angle rotation leaves the vector unchanged.

## 9. Beginner Questions

1. In beginner terms, what does RoPE rotate?
2. What happens to `[x, y]` after a 90-degree counterclockwise rotation?
3. What does `_rotate_half([2, 1])` produce?
4. Does an ideal rotation change the vector’s length?
5. What are `cos(0)` and `sin(0)`?
6. Why does a zero-angle rotation leave the vector unchanged?
7. Which vectors does the repo rotate: `q`, `k`, or `v`?
8. Does rotation change the shapes of `q` and `k`?

## 10. Exercise

Given:

```text
q = [4, 3]
```

For a 90-degree rotation:

1. `rotate_half(q)` = ?
2. Rotated `q` = ?
3. Original length = `sqrt(4² + 3²)` = ?
4. Rotated length = ?
5. Did the length change?

Then calculate:

```text
x = [1, 2, 3, 4]
```

What does the repo’s `_rotate_half(x)` return?

# Lesson 100: How Does RoPE Choose Rotation Angles?

## 1. Simplest Explanation

RoPE gives each token position a rotation angle.

The basic idea is:

```text
angle = position × frequency
```

As the position increases, the rotation angle changes.

## 2. Analogy

Imagine several clock hands moving at different speeds:

- One hand moves quickly.
- One hand moves slowly.
- Each moment gives the hands a different arrangement.

RoPE uses several rotation speeds. Together, their angles create a useful position pattern.

## 3. Technical Terms

A **frequency** tells us how quickly an angle changes from one position to the next.

```text
frequency = 1.0 -> angle changes quickly
frequency = 0.1 -> angle changes slowly
```

RoPE’s trigonometric functions use **radians** to measure angles.

```text
1 radian is approximately 57.3 degrees
```

You do not need to memorize that conversion yet.

## 4. Tiny Example

Suppose RoPE has two frequencies:

```text
frequencies = [1.0, 0.1]
positions   = [0, 1, 2]
```

Calculate `position × frequency`:

```text
Position 0 -> [0 × 1.0, 0 × 0.1] = [0,   0]
Position 1 -> [1 × 1.0, 1 × 0.1] = [1, 0.1]
Position 2 -> [2 × 1.0, 2 × 0.1] = [2, 0.2]
```

The first pair rotates faster than the second pair.

## 5. Where It Appears In The Repo

The angle tables are built in [gpt.py](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:87):

```python
inv_freq = 1.0 / (
    base ** (
        torch.arange(0, dim, 2).float()
        / dim
    )
)

positions = torch.arange(
    max_seq_len,
    dtype=torch.float,
)

freqs = torch.einsum(
    "i,j->ij",
    positions,
    inv_freq,
)
```

## 6. Code Explained Slowly

For a tiny example:

```text
dim  = 4
base = 100
```

This line creates the pair indices:

```python
torch.arange(0, dim, 2)
```

Result:

```text
[0, 2]
```

Then the repo calculates:

```text
frequency 0 = 1 / 100^(0/4) = 1
frequency 1 = 1 / 100^(2/4) = 0.1
```

So:

```text
inv_freq = [1.0, 0.1]
```

This line creates all token positions:

```python
positions = torch.arange(max_seq_len)
```

If `max_seq_len=3`:

```text
positions = [0, 1, 2]
```

Finally:

```python
freqs = torch.einsum("i,j->ij", positions, inv_freq)
```

Here, `einsum` creates a multiplication table:

```text
freqs = [
  [0,   0],
  [1, 0.1],
  [2, 0.2],
]
```

Its shape is:

```text
(number of positions, number of frequencies)
= (3, 2)
```

## 7. Creating Sine And Cosine Tables

The repo continues:

```python
# Duplicate frequencies so paired vector parts use matching angles.
emb = torch.cat((freqs, freqs), dim=-1)

# Calculate and store cosine values for every position.
self.register_buffer(
    "cos",
    emb.cos()[None, None, :, :],
    persistent=False,
)

# Calculate and store sine values for every position.
self.register_buffer(
    "sin",
    emb.sin()[None, None, :, :],
    persistent=False,
)
```

A **buffer** is a tensor stored with the model that is not a learned parameter.

The sine and cosine values are computed from fixed formulas. Training does not learn them.

## 8. The Mini Model

The Mini configuration uses:

```yaml
context_length: 256
n_heads: 8
d_model: 256
rope_base: 10000.0
```

Therefore:

```text
head_dim = 256 ÷ 8 = 32
positions = 0 through 255
number of frequencies = 32 ÷ 2 = 16
```

Before duplication:

```text
freqs shape = (256, 16)
```

After duplication:

```text
position-angle shape = (256, 32)
```

## 9. Beginner Questions

1. What is the basic formula for a RoPE angle?
2. What does frequency control?
3. Which changes angles faster: frequency `1.0` or `0.1`?
4. Why is every angle at position zero equal to zero?
5. What does `torch.arange(max_seq_len)` create?
6. What does `einsum("i,j->ij", positions, inv_freq)` do here?
7. Are the RoPE sine and cosine tables learned parameters?
8. How many RoPE frequencies does the Mini model use per head?

## 10. Exercise

Given:

```text
positions   = [0, 1, 2, 3]
frequencies = [1.0, 0.25]
```

Complete the angle table:

```text
Position 0 -> [?, ?]
Position 1 -> [?, ?]
Position 2 -> [?, ?]
Position 3 -> [?, ?]
```

Then answer:

1. Which frequency rotates faster?
2. What is the angle-table shape?
3. If `head_dim=8`, how many frequencies are created before duplication?
4. Are those frequencies changed by the optimizer?