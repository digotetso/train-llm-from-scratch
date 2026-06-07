import torch

from matgpt.model.gpt import GPT, GPTConfig
from matgpt.training.optim import build_optimizer
from matgpt.training.pretrain import train_on_fixed_batch


def test_train_on_fixed_batch_reduces_loss():
    torch.manual_seed(0)
    model = GPT(
        GPTConfig(
            vocab_size=32,
            context_length=8,
            n_layers=1,
            n_heads=4,
            d_model=32,
            d_ff=96,
            dropout=0.0,
            norm_eps=1.0e-5,
            rope_base=10000.0,
            tie_embeddings=True,
            use_bias=False,
            activation="swiglu",
        )
    )
    optimizer = build_optimizer(model, "adamw", learning_rate=5e-3, weight_decay=0.0, betas=(0.9, 0.95))
    x = torch.tensor([[1, 2, 3, 4, 5, 6, 7, 8]] * 4)
    y = torch.tensor([[2, 3, 4, 5, 6, 7, 8, 9]] * 4)

    losses = train_on_fixed_batch(
        model=model,
        optimizer=optimizer,
        x=x,
        y=y,
        steps=12,
        device=torch.device("cpu"),
    )

    assert losses[-1] < losses[0]
