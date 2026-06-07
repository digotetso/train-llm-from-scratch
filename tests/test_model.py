import torch

from matgpt.model.generation import generate
from matgpt.model.gpt import GPT, GPTConfig, count_parameters


def tiny_config(vocab_size: int = 64) -> GPTConfig:
    return GPTConfig(
        vocab_size=vocab_size,
        context_length=8,
        n_layers=2,
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


def test_gpt_forward_shape_and_loss_are_finite():
    model = GPT(tiny_config())
    input_ids = torch.randint(0, 64, (2, 8))
    logits, loss = model(input_ids, targets=input_ids)

    assert logits.shape == (2, 8, 64)
    assert loss is not None
    assert torch.isfinite(loss)
    assert count_parameters(model) > 0


def test_causal_attention_does_not_leak_future_tokens():
    torch.manual_seed(0)
    model = GPT(tiny_config())
    model.eval()
    first = torch.tensor([[1, 2, 3, 4, 5, 6, 7, 8]])
    second = torch.tensor([[1, 2, 3, 40, 41, 42, 43, 44]])

    with torch.no_grad():
        first_logits, _ = model(first)
        second_logits, _ = model(second)

    assert torch.allclose(first_logits[:, :3], second_logits[:, :3], atol=1e-5)


def test_generation_stops_at_eos():
    class EosModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.config = tiny_config(vocab_size=10)

        def forward(self, input_ids, targets=None):
            logits = torch.zeros(input_ids.shape[0], input_ids.shape[1], 10)
            logits[:, -1, 2] = 100.0
            return logits, None

    output = generate(
        EosModel(),
        input_ids=torch.tensor([[1, 5]]),
        max_new_tokens=5,
        eos_id=2,
        temperature=0.0,
    )

    assert output.tolist() == [[1, 5, 2]]
