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
        normed = x * torch.rsqrt(x.pow(2).mean(dim=-1, keepdim=True) + self.eps)
        return normed * self.weight


def _rotate_half(x: torch.Tensor) -> torch.Tensor:
    x1 = x[..., : x.shape[-1] // 2]
    x2 = x[..., x.shape[-1] // 2 :]
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
        return (q * cos) + (_rotate_half(q) * sin), (k * cos) + (_rotate_half(k) * sin)


class CausalSelfAttention(nn.Module):
    """Multi-head self-attention where each token can only see earlier tokens."""

    def __init__(self, config: GPTConfig) -> None:
        super().__init__()
        if config.d_model % config.n_heads != 0:
            raise ValueError("d_model must be divisible by n_heads")
        self.config = config
        self.qkv = nn.Linear(config.d_model, 3 * config.d_model, bias=config.use_bias)
        self.proj = nn.Linear(config.d_model, config.d_model, bias=config.use_bias)
        self.dropout = nn.Dropout(config.dropout)
        self.rope = RotaryEmbedding(config.head_dim, config.context_length, config.rope_base)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch, seq_len, d_model = x.shape
        qkv = self.qkv(x)
        q, k, v = qkv.split(d_model, dim=-1)
        # Reshape from (batch, time, channels) into separate attention heads:
        # (batch, heads, time, head_dim). Each head attends independently.
        q = q.view(batch, seq_len, self.config.n_heads, self.config.head_dim).transpose(1, 2)
        k = k.view(batch, seq_len, self.config.n_heads, self.config.head_dim).transpose(1, 2)
        v = v.view(batch, seq_len, self.config.n_heads, self.config.head_dim).transpose(1, 2)
        q, k = self.rope(q, k)
        # is_causal=True applies the triangular mask internally, preventing the
        # model from looking at future tokens during next-token prediction.
        y = F.scaled_dot_product_attention(
            q,
            k,
            v,
            attn_mask=None,
            dropout_p=self.config.dropout if self.training else 0.0,
            is_causal=True,
        )
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
            self.w1 = nn.Linear(config.d_model, config.d_ff, bias=config.use_bias)
            self.w3 = nn.Linear(config.d_model, config.d_ff, bias=config.use_bias)
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
        self.attn = CausalSelfAttention(config)
        self.norm_2 = RMSNorm(config.d_model, config.norm_eps)
        self.mlp = MLP(config)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.norm_1(x))
        x = x + self.mlp(self.norm_2(x))
        return x


class GPT(nn.Module):
    def __init__(self, config: GPTConfig) -> None:
        super().__init__()
        self.config = config
        self.token_embedding = nn.Embedding(config.vocab_size, config.d_model)
        self.dropout = nn.Dropout(config.dropout)
        self.blocks = nn.ModuleList([Block(config) for _ in range(config.n_layers)])
        self.norm_f = RMSNorm(config.d_model, config.norm_eps)
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

        # Convert token IDs into learned vectors, process them through decoder
        # blocks, and project each position back to vocabulary logits.
        x = self.token_embedding(input_ids)
        x = self.dropout(x)
        for block in self.blocks:
            x = block(x)
        x = self.norm_f(x)
        logits = self.lm_head(x)
        loss = None
        if targets is not None:
            # For base pretraining, every target is the next token. The training
            # dataset creates x=tokens[:-1] and y=tokens[1:].
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
    params = model.parameters()
    if trainable_only:
        params = (p for p in params if p.requires_grad)
    return sum(p.numel() for p in params)


def estimate_mfu_tokens_per_step(batch_size: int, context_length: int, grad_accum: int) -> int:
    return batch_size * context_length * grad_accum
