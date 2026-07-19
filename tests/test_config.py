from pathlib import Path

import pytest
import torch

from matgpt.config import load_config, validate_config
from matgpt.utils.hashing import sha256_file, sha256_text
from matgpt.utils.seed import set_seed


def test_loads_mini_config_and_validates():
    cfg = load_config("configs/matgpt_mini_8m.yaml")

    assert cfg["run"]["name"] == "matgpt_mini_8m_tinystories"
    assert cfg["model"]["d_model"] == 256
    assert cfg["tokenizer"]["vocab_size"] == cfg["model"]["vocab_size"]
    validate_config(cfg)


def test_config_validation_rejects_bad_head_dimension():
    cfg = load_config("configs/matgpt_mini_8m.yaml")
    cfg["model"]["n_heads"] = 7

    with pytest.raises(ValueError, match="d_model must be divisible"):
        validate_config(cfg)


def test_config_rejects_byte_bpe_vocab_smaller_than_alphabet_and_specials():
    cfg = load_config("configs/matgpt_mini_8m.yaml")
    cfg["tokenizer"]["vocab_size"] = 262
    cfg["model"]["vocab_size"] = 262

    with pytest.raises(ValueError, match="at least 263"):
        validate_config(cfg)


def test_hash_helpers_are_stable(tmp_path: Path):
    path = tmp_path / "sample.txt"
    path.write_text("same text\n", encoding="utf-8")

    assert sha256_text("same text\n") == sha256_file(path)
    assert sha256_text("same text\n") != sha256_text("different\n")


def test_set_seed_reproducible_for_torch():
    set_seed(123)
    first = torch.rand(4)
    set_seed(123)
    second = torch.rand(4)

    assert torch.equal(first, second)
