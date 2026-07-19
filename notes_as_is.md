Questions
What does d_model mean here? size of an embedding,
What does d_ff mean here? MLP hidden dimension
Why does the MLP shrink back to d_model at the end? to keep the size of a token throughtout
Exercise
If:
d_model = 512
d_ff = 2048
What are the sizes for:
expand: ? -> ? 2048
shrink: ? -> ? 512




8:41 PM






Worked for 6s



Good.
Your concepts are correct:
d_model = normal token vector size / model width
d_ff = bigger hidden size inside the MLP
Your answer:
to keep the size of a token throughout
is right. More polished:
The MLP shrinks back to d_model so the next part of the Transformer receives the expected shape.
Exercise correction:
Given:
d_model = 512
d_ff = 2048
The full answer is:
expand: 512 -> 2048
shrink: 2048 -> 512
You wrote the ending sizes correctly; just include both sides.
Lesson 31: Activation Inside The MLP
If the MLP only did straight-line math, it would be limited.
So it uses a special function that bends the math and lets the model learn richer patterns.
Analogy: a light dimmer.
Instead of only ON/OFF, the model can smoothly decide how much signal should pass through.
Technical term: activation function.
Beginner meaning:
activation = a function that controls and bends the signal
This repo uses something called SwiGLU.
Do not worry about the full name yet. Beginner meaning:
SwiGLU helps the MLP decide which information to let through strongly and which to reduce.
Repo location: [matgpt/model/gpt.py (line 148)](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:148)
x = self.w2(F.silu(self.w1(x)) * self.w3(x))
Slow comments:
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
Tiny example of a gate:
information = 10
gate = 0.2

passed information = 10 * 0.2 = 2
Another:
information = 10
gate = 0.9

passed information = 10 * 0.9 = 9
So the MLP can control what information flows through.
Questions
In beginner terms, what does an activation function do?
What does a gate do?
In 10 * 0.2 = 2, did the gate let a lot through or a little?
Exercise
Compute:
information = 8
gate = 0.5

passed information = ?

8:41 PM






In beginner terms, what does an activation function do? help MLP to decide which info to let through
What does a gate do? let info through or block it
In 10 * 0.2 = 2, did the gate let a lot through or a little? yes
Exercise
Compute:
information = 8
gate = 0.5

passed information = ? 4




6:39 AM






Worked for 5s



Good.
Your first two answers are right:
activation function = helps control/bend the signal
gate = lets information through strongly, weakly, or almost not at all
Small correction:
For:
10 * 0.2 = 2
The gate let through a little, not a lot. Since 0.2 is small, only 20% of the information passed through.
Your exercise is correct:
information = 8
gate = 0.5

passed information = 8 * 0.5 = 4
So 0.5 lets through half.
Quick check before moving on:
If:
information = 12
gate = 0.25
what is:
passed information = ?

6:39 AM






3




6:41 AM






Worked for 7s



Correct.
information = 12
gate = 0.25
passed information = 12 * 0.25 = 3
So the gate lets through one quarter of the signal.
Lesson 32: One Transformer Block
Now we can assemble the block.
Repo location: [matgpt/model/gpt.py (line 164)](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:164)
def forward(self, x: torch.Tensor) -> torch.Tensor:
    x = x + self.attn(self.norm_1(x))
    x = x + self.mlp(self.norm_2(x))
    return x
Beginner explanation:
A Transformer block improves token profiles in two main steps:
1. attention: tokens look at useful earlier tokens
2. MLP: each token processes its own information
Slow comments:
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
Analogy:
attention = ask classmates for useful context
MLP = think privately about your updated notes
residual = keep your original notes and add improvements
normalization = keep everything at a manageable volume
Shape usually stays the same:
input x:  (batch, seq_len, d_model)
output x: (batch, seq_len, d_model)
Questions
What are the two main parts of a Transformer block?
What does attention do?
What does the MLP do?
Why do we add updates back to x?
Exercise
If:
x shape entering block = (2, 4, 8)
what is the usual shape after one Transformer block?

6:41 AM






Questions
What are the two main parts of a Transformer block? attention and MLP
What does attention do?  lets each token look at useful ealier tokens
What does the MLP do?  each toke process its own info
Why do we add updates back to x? moe make original token profile better instead of throwing the original information
Exercise
If:
x shape entering block = (2, 4, 8)
what is the usual shape after one Transformer block? (2, 4, 8)




8:04 AM






Worked for 5s



Correct.
Small typo fixes:
earlier, not ealier
token, not toke
Your ideas are right:
Transformer block = attention + MLP
attention = tokens look at useful earlier tokens
MLP = each token processes its own information
residual = keep original information and add improvements
Your exercise is correct:
input shape:  (2, 4, 8)
output shape: (2, 4, 8)
Lesson 33: Stacking Many Blocks
One Transformer block improves token profiles once.
A GPT model uses many blocks in a row.
Analogy:
Draft 1 -> edit -> edit -> edit -> final improved draft
Each block refines the token information a bit more.
Repo location: [matgpt/model/gpt.py (line 176)](/Users/digotetsomatema/AI-Projects-2026/train-llm-from-scratch/matgpt/model/gpt.py:176)
self.blocks = nn.ModuleList([Block(config) for _ in range(config.n_layers)])
Slow comments:
# Create many Transformer blocks.
# config.n_layers decides how many.
self.blocks = nn.ModuleList(
    [Block(config) for _ in range(config.n_layers)]
)
Then during the forward pass:
for block in self.blocks:
    x = block(x)
Slow comments:
# Send x through each block one by one.
# Each block updates the token profiles.
for block in self.blocks:
    x = block(x)
In the 8M config:
n_layers: 6
So the model runs:
block 1
block 2
block 3
block 4
block 5
block 6
Shape usually stays:
(batch, seq_len, d_model)
but the numbers become more useful.
Questions
What does n_layers control?
If n_layers = 6, how many Transformer blocks are used?
If x enters block 1 with shape (2, 4, 8), what shape usually comes out of block 6?
Exercise
If:
n_layers = 12
x shape before first block = (3, 10, 16)
what is the usual shape after all 12 blocks?

8:04 AM






















Approve for me

5.5Extra High








Work locallyLocal