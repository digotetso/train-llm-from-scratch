"""Decoder-only Transformer used for MatGPT base pretraining.

This file intentionally keeps the model readable. The architecture is still
modern enough for good small-model training: RMSNorm for stable normalization,
RoPE for position information, SwiGLU for the feed-forward block, tied token
embeddings, and PyTorch's built-in scaled-dot-product attention.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import torch
from torch import nn
from torch.nn import functional as F


@dataclass(frozen=True)
class GPTConfig:
    vocab_size: int
    context_length: int
    n_layers: int
    n_heads: int
    d_model: int
    d_ff: int
    dropout: float
    norm_eps: float
    rope_base: float
    tie_embeddings: bool
    use_bias: bool
    activation: str = "swiglu"

    # head_dim -> how many numbers each attention head gets
    @property
    def head_dim(self) -> int:
        return self.d_model // self.n_heads

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GPTConfig":
        return cls(**data)


class RMSNorm(nn.Module):
    """Root Mean Square LayerNorm.

    RMSNorm normalizes the size of each token vector without subtracting the
    mean. It is common in modern decoder-only language models and is slightly
    simpler than LayerNorm.
    """

    def __init__(self, dim: int, eps: float) -> None:
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
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
        return normed * self.weight


def _rotate_half(x: torch.Tensor) -> torch.Tensor:
    # Divide the final dimension into two equal parts.
    x1 = x[..., : x.shape[-1] // 2]
    x2 = x[..., x.shape[-1] // 2 :]

     # Change [x1, x2] into [-x2, x1].
    return torch.cat((-x2, x1), dim=-1)


class RotaryEmbedding(nn.Module):
    """Precompute RoPE sine/cosine tables for all positions in the context."""

    def __init__(self, dim: int, max_seq_len: int, base: float) -> None:
        super().__init__()
        inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2).float() / dim))
        positions = torch.arange(max_seq_len, dtype=torch.float)
        freqs = torch.einsum("i,j->ij", positions, inv_freq)
        emb = torch.cat((freqs, freqs), dim=-1)
        self.register_buffer("cos", emb.cos()[None, None, :, :], persistent=False)
        self.register_buffer("sin", emb.sin()[None, None, :, :], persistent=False)

    def forward(self, q: torch.Tensor, k: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        seq_len = q.shape[-2]
        cos = self.cos[:, :, :seq_len, :].to(dtype=q.dtype, device=q.device)
        sin = self.sin[:, :, :seq_len, :].to(dtype=q.dtype, device=q.device)

        # q × cos                     -> original-direction part
        # rotate_half(q) × sin        -> rotated-direction part
        # add them                    -> position-rotated query
        # The same process is applied to k.
        return (q * cos) + (_rotate_half(q) * sin), (k * cos) + (_rotate_half(k) * sin)


class CausalSelfAttention(nn.Module):
    """Multi-head self-attention where each token can only see earlier tokens."""

    def __init__(self, config: GPTConfig) -> None:
        super().__init__()
        if config.d_model % config.n_heads != 0:
            raise ValueError("d_model must be divisible by n_heads")
        self.config = config

        # Create learned math that turns each token vector
        # into 3 new vectors:
        # q = query
        # k = key
        # v = value
        self.qkv = nn.Linear(config.d_model, 3 * config.d_model, bias=config.use_bias)

        # Create a learned transformation.
        # It takes d_model numbers in.
        # It returns d_model numbers out.
        # So the shape stays the same, but the values can change.
        self.proj = nn.Linear(config.d_model, config.d_model, bias=config.use_bias)

        # y is the joined attention result.
        # self.proj(y) remixes the numbers using learned weights.
        # self.dropout(...) is a training trick we will explain later.
        self.dropout = nn.Dropout(config.dropout)

        # Create the RoPE position-information system.
        self.rope = RotaryEmbedding(
            # Numbers available to each attention head.
            config.head_dim,

            # Maximum number of token positions.
            config.context_length,

            # Controls RoPE's position frequencies.
            config.rope_base,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch, seq_len, d_model = x.shape

        # x is the current token number profiles.
        # self.qkv(x) creates query/key/value numbers all at once.
        qkv = self.qkv(x)

        # Split the big result into three separate parts:
        # q = queries
        # k = keys
        # v = values
        q, k, v = qkv.split(d_model, dim=-1)
        # Reshape from (batch, time, channels) into separate attention heads:
        # (batch, heads, time, head_dim). Each head attends independently.

        # q contains all query numbers for all tokens
        # This reshapes q so the model can split attention into multiple heads.
        # 1. batch = how many examples
        # 2. seq_len = how many tokens per example
        # 3. n_heads = how many attention heads
        # 4. head_dim = how many numbers each head gets

        # q.view(batch, seq_len, self.config.n_heads, self.config.head_dim) : reshapes q.k.v from [batch, seq_len, hidden_dim] ---> [batch, seq_len, n_heads, head_dim]
        # .transpose(1, 2):  swaps dimension 1 ans dimension 2, [batch, seq_len, n_heads, head_dim] becomes [batch, n_heads, seq_len, head_dim]


        # q starts with shape:
        # (batch, seq_len, d_model)

        # Split d_model into:
        # n_heads * head_dim
        # shape after view: (batch, seq_len, n_heads, head_dim)
        # q = q.view(batch, seq_len, self.config.n_heads, self.config.head_dim)

        # Rearrange dimensions so heads come before sequence length.
        # New shape:
        # (batch, n_heads, seq_len, head_dim)
        # q = q.transpose(1, 2)

        q = q.view(batch, seq_len, self.config.n_heads, self.config.head_dim).transpose(1, 2)
        k = k.view(batch, seq_len, self.config.n_heads, self.config.head_dim).transpose(1, 2)
        v = v.view(batch, seq_len, self.config.n_heads, self.config.head_dim).transpose(1, 2)
        q, k = self.rope(q, k)

        # is_causal=True applies the triangular mask internally, preventing the
        # model from looking at future tokens during next-token prediction.
        # This runs attention
        # We do not see the score calculation written out by hand here because PyTorch does it for us.
        # atten scores, weights

        # PyTorch:
        # 1. computes attention scores
        # 2. turns scores into weights
        # 3. uses weights to mix token information
        # 4. returns the mixed result as y

        y = F.scaled_dot_product_attention(
            # k,q,v  are specials transformed versions of token vectors
            q,
            k,
            v,

            # No extra custom mask is passed here
            attn_mask=None,

            # Dropout is a training regularization detail. We will explain later.
            dropout_p=self.config.dropout if self.training else 0.0,

            # True means each token cannot look at the future tokens
            is_causal=True,
        )


        # Before this line, attention output y has shape: batch, n_heads, seq_len, head_dim)

        # "y = y.transpose(1, 2).contiguous().view(batch, seq_len, d_model)"

        # Swap heads and sequence back:
        # (batch, seq_len, n_heads, head_dim)
        # y = y.transpose(1, 2)

        # Make memory layout clean for reshaping.
        # Do not worry deeply about this yet.
        # y = y.contiguous()

        # Join n_heads and head_dim back into d_model.
        # Since d_model = n_heads * head_dim,
        # shape becomes:
        # (batch, seq_len, d_model)

        y = y.transpose(1, 2).contiguous().view(batch, seq_len, d_model)
        return self.dropout(self.proj(y))


class MLP(nn.Module):
    """Transformer feed-forward network.

    SwiGLU is the default because it tends to train well in small GPT-style
    models while staying easy to understand.
    """

    def __init__(self, config: GPTConfig) -> None:
        super().__init__()
        self.activation = config.activation
        if config.activation == "swiglu":
            # w1 expands from d_model to d_ff.
            # Example: 256 -> 1024
            self.w1 = nn.Linear(config.d_model, config.d_ff, bias=config.use_bias)

            # w3 also expands from d_model to d_ff.
            # This is part of SwiGLU, which we will explain later.
            self.w3 = nn.Linear(config.d_model, config.d_ff, bias=config.use_bias)

            # w2 shrinks from d_ff back to d_model.
            # Example: 1024 -> 256
            self.w2 = nn.Linear(config.d_ff, config.d_model, bias=config.use_bias)

        elif config.activation == "gelu":
            self.net = nn.Sequential(
                nn.Linear(config.d_model, config.d_ff, bias=config.use_bias),
                nn.GELU(),
                nn.Linear(config.d_ff, config.d_model, bias=config.use_bias),
            )
        else:
            raise ValueError(f"Unsupported activation: {config.activation}")
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.activation == "swiglu":
            x = self.w2(F.silu(self.w1(x)) * self.w3(x))
        else:
            x = self.net(x)
        return self.dropout(x)


class Block(nn.Module):
    def __init__(self, config: GPTConfig) -> None:
        super().__init__()
        self.norm_1 = RMSNorm(config.d_model, config.norm_eps)

        #This creates attention part of the block
        # Its job: Lets token use information from other tokens
        self.attn = CausalSelfAttention(config)
        self.norm_2 = RMSNorm(config.d_model, config.norm_eps)
        self.mlp = MLP(config)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x contains the current number profiles for all tokens.
        # self.attn(...) lets each token look at useful earlier tokens.
        # The result is added back into x.

        # x is the current token information.
        # x
        # Step 1:
        # self.norm_1(x) prepares x before attention.
        # Normalize x so the numbers are stable.
        # self.norm_1(x)

        # self.attn(...) computes an attention update.
        # This update contains information gathered from useful previous tokens.
        # self.attn(self.norm_1(x))

        # Add the update back to the original x.
        # This keeps old information while adding new information.
        x = x + self.attn(self.norm_1(x))

        # x is the current token information after attention.
        # x

        # Step 2:
        # Normalize again.
        # self.norm_2(x) stabilizes the numbers before the MLP.
        self.norm_2(x)

        # self.mlp(...) transforms each token's number profile.
        # Run the MLP so each token can process its own number profile.
        # It does not mix tokens with each other like attention does.
        self.mlp(self.norm_2(x))

        # Add the MLP update back to the original x.
        # This is another residual connection.
        x = x + self.mlp(self.norm_2(x))
        return x


class GPT(nn.Module):
    def __init__(self, config: GPTConfig) -> None:
        super().__init__()
        self.config = config
        # create a look up table for token IDs
        # Each token ID gets a learned list of numbers
        # config.vocab_size,  # how many token IDs exist
        # config.d_model,    # how long each token's number profile is
        self.token_embedding = nn.Embedding(config.vocab_size, config.d_model)
        self.dropout = nn.Dropout(config.dropout)

        # Create a List of transformer Blocks
        # Each Block is one repeated processing layer
        # If n_layer is 12, then this creates 12 blocks
        # So the model processes embeddings through 12 repeated blocks.
        self.blocks = nn.ModuleList([Block(config) for _ in range(config.n_layers)])
        self.norm_f = RMSNorm(config.d_model, config.norm_eps)

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
        if config.tie_embeddings:
            self.lm_head.weight = self.token_embedding.weight
        self.apply(self._init_weights)

    def _init_weights(self, module: nn.Module) -> None:
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(
        self,
        input_ids: torch.Tensor,
        targets: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor | None]:
        if input_ids.shape[1] > self.config.context_length:
            raise ValueError("input sequence length exceeds model context_length")

        #? Convert token IDs into learned vectors, process them through decoder
        #? blocks, and project each position back to vocabulary logits.

        # Take token IDs like [7, 20, 45]
        # and replace each ID with its learned number profile.
        x = self.token_embedding(input_ids)
        x = self.dropout(x)

        # Take the current token number profiles.
        # Pass them through one block.
        # Then another.
        # Then another.
        # Keep updating x.
        for block in self.blocks:
            x = block(x)
        x = self.norm_f(x)
        logits = self.lm_head(x)
        loss = None
        if targets is not None:
            # For base pretraining, every target is the next token. The training
            # dataset creates x=tokens[:-1] and y=tokens[1:].

            # logits are the model's raw scores for possible next tokens.
            # targets are the correct next token IDs.

            # cross_entropy compares:
            # model scores vs correct answers

            # It returns one mistake score:
            # lower is better, higher is worse.
            loss = F.cross_entropy(
                logits.reshape(-1, logits.size(-1)),
                targets.reshape(-1),
                ignore_index=-100,
            )
        return logits, loss

    def crop_context(self, input_ids: torch.Tensor) -> torch.Tensor:
        return input_ids[:, -self.config.context_length :]


def model_from_config(cfg: dict[str, Any]) -> GPT:
    return GPT(GPTConfig.from_dict(cfg["model"]))


def count_parameters(model: nn.Module, trainable_only: bool = True) -> int:
    # Get the model's parameter tensors.
    params = model.parameters()

    # Keep only parameters that training is allowed to change.
    # `requires_grad=True`` means PyTorch should compute gradients for that parameter.
    if trainable_only:
        params = (p for p in params if p.requires_grad)

    # p.numel() counts the individual numbers in one tensor.
    # sum(...) adds the counts from every parameter tensor.
    return sum(p.numel() for p in params)


def estimate_mfu_tokens_per_step(batch_size: int, context_length: int, grad_accum: int) -> int:
    return batch_size * context_length * grad_accum
