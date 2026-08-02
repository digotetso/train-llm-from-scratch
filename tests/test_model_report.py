from matgpt.config import load_config
from matgpt.model.report import build_model_report, parse_size_label


def test_parse_size_label_reads_millions_from_run_name():
    assert parse_size_label("matgpt_tiny_59m_babylm") == 59_000_000
    assert parse_size_label("matgpt_mini_8m_tinystories") == 8_000_000
    assert parse_size_label("matgpt_experiment") is None


def test_tiny_config_keeps_12_layers_and_uses_59m_name():
    cfg = load_config("configs/matgpt_tiny_59m.yaml")

    report = build_model_report(cfg)

    assert cfg["run"]["name"] == "matgpt_tiny_59m_babylm"
    assert cfg["model"]["n_layers"] == 12
    assert report["size_label_parameters"] == 59_000_000
    assert report["parameter_count"] == 58_733_056
    assert report["size_label_matches"] is True


def test_mini_config_has_exact_trainable_parameter_count():
    cfg = load_config("configs/matgpt_mini_8m.yaml")

    report = build_model_report(cfg)

    assert report["size_label_parameters"] == 8_000_000
    assert report["parameter_count"] == 8_391_936
    assert report["size_label_matches"] is True


def test_telco_config_has_exact_trainable_parameter_count():
    cfg = load_config("configs/matgpt_telco_300m.yaml")

    report = build_model_report(cfg)

    assert cfg["model"] == {
        "vocab_size": 32768,
        "context_length": 2048,
        "n_layers": 20,
        "n_heads": 16,
        "d_model": 1024,
        "d_ff": 3072,
        "dropout": 0.0,
        "norm_eps": 1.0e-5,
        "rope_base": 10000.0,
        "tie_embeddings": True,
        "use_bias": False,
        "activation": "swiglu",
    }
    assert report["size_label_parameters"] == 300_000_000
    assert report["parameter_count"] == 306_226_176
    assert report["size_label_matches"] is True
