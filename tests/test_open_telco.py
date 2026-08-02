import json
from pathlib import Path

import pytest

from matgpt.data.sources import load_source_registry
from matgpt.eval.open_telco import (
    SUPPORTED_MULTIPLE_CHOICE_CONFIGS,
    convert_open_telco_row,
    prepare_open_telco_evals,
)
from matgpt.eval.tasks import load_multiple_choice_examples


REGISTRY_PATH = Path("configs/data/telco_300m_sources.yaml")


@pytest.mark.parametrize(
    "config",
    ["teleqna", "oranbench", "srsranbench", "sixg_bench"],
)
def test_multiple_choice_configs_convert_to_local_schema(config: str):
    row = {
        "question": "Which protocol carries routing reachability?",
        "choices": ["BGP", "RRC"],
        "answer": 0,
        "category": "routing",
    }

    converted = convert_open_telco_row("GSMA/ot-lite", config, 7, row)

    assert converted["id"] == f"GSMA/ot-lite/{config}/7"
    assert converted["prompt"] == row["question"]
    assert converted["choices"] == row["choices"]
    assert converted["answer"] == 0
    assert converted["category"] == "routing"
    assert converted["source_index"] == 7
    assert len(converted["content_sha256"]) == 64


def test_conversion_uses_subject_or_task_name_as_category():
    teleqna = convert_open_telco_row(
        "GSMA/ot-lite",
        "teleqna",
        0,
        {
            "question": "Question?",
            "choices": ["A", "B"],
            "answer": 1,
            "subject": "5G core",
        },
    )
    sixg = convert_open_telco_row(
        "GSMA/ot-lite",
        "sixg_bench",
        1,
        {
            "question": "Question?",
            "choices": ["A", "B"],
            "answer": 1,
            "task_name": "semantic communication",
        },
    )

    assert teleqna["category"] == "5G core"
    assert sixg["category"] == "semantic communication"


def test_non_multiple_choice_config_fails_explicitly():
    with pytest.raises(
        ValueError,
        match="not supported by the multiple-choice evaluator",
    ):
        convert_open_telco_row(
            "GSMA/ot-lite",
            "telemath",
            0,
            {"question": "1 + 1?", "answer": 2.0},
        )


def test_conversion_rejects_out_of_range_answer():
    with pytest.raises(ValueError, match="outside choices"):
        convert_open_telco_row(
            "GSMA/ot-lite",
            "teleqna",
            0,
            {"question": "Question?", "choices": ["A", "B"], "answer": 2},
        )


def _evaluation_rows(config: str) -> list[dict]:
    return [
        {
            "question": f"{config} question {index}?",
            "choices": ["first", "second", "third"],
            "answer": index % 3,
            "subject": "telecom",
            "category": "radio",
        }
        for index in range(3)
    ]


def test_materializer_streams_pinned_configs_and_promotes_atomically(tmp_path: Path):
    registry = load_source_registry(REGISTRY_PATH)
    calls: list[dict] = []

    def loader(hf_name: str, **kwargs):
        calls.append({"hf_name": hf_name, **kwargs})
        return iter(_evaluation_rows(kwargs["name"]))

    training_dir = tmp_path / "training"
    training_dir.mkdir()
    (training_dir / "manifest.json").write_text("training", encoding="utf-8")
    output = tmp_path / "evaluations"
    manifest = prepare_open_telco_evals(
        registry=registry,
        source_id="open_telco_lite",
        configs=("teleqna", "oranbench"),
        output_dir=output,
        dataset_loader=loader,
    )

    assert manifest["complete"] is True
    assert manifest["dataset_id"] == "GSMA/ot-lite"
    assert manifest["revision"] == "1c0f2eac3ad0baa29704b147a95fea283b2906c7"
    assert set(manifest["configs"]) == {"teleqna", "oranbench"}
    assert len(calls) == 2
    assert all(call["streaming"] is True for call in calls)
    assert all(call["split"] == "test" for call in calls)
    assert all(len(call["revision"]) == 40 for call in calls)
    assert not list(tmp_path.glob(".evaluations.staging-*"))
    assert (training_dir / "manifest.json").read_text(encoding="utf-8") == "training"
    for config in ("teleqna", "oranbench"):
        examples = load_multiple_choice_examples(output / f"{config}.jsonl")
        assert len(examples) == 3


def test_materializer_rejects_training_source_before_loading(tmp_path: Path):
    registry = load_source_registry(REGISTRY_PATH)
    calls = []

    with pytest.raises(ValueError, match="evaluation_only"):
        prepare_open_telco_evals(
            registry=registry,
            source_id="telco_common_corpus",
            configs=("teleqna",),
            output_dir=tmp_path / "bad",
            dataset_loader=lambda *args, **kwargs: calls.append((args, kwargs)),
        )

    assert calls == []


def test_materializer_failure_cleans_staging_and_preserves_existing_output(
    tmp_path: Path,
):
    registry = load_source_registry(REGISTRY_PATH)
    output = tmp_path / "evaluations"
    output.mkdir()
    (output / "sentinel").write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        prepare_open_telco_evals(
            registry=registry,
            source_id="open_telco_lite",
            configs=("teleqna",),
            output_dir=output,
            dataset_loader=lambda *_args, **_kwargs: iter(()),
        )

    assert (output / "sentinel").read_text(encoding="utf-8") == "keep"
    assert not list(tmp_path.glob(".evaluations.staging-*"))


def test_supported_config_set_is_intentionally_bounded():
    assert SUPPORTED_MULTIPLE_CHOICE_CONFIGS == frozenset(
        {"teleqna", "oranbench", "srsranbench", "sixg_bench"}
    )
