import json

import pytest

from matgpt.eval.judge import (
    build_judge_bundle,
    summarize_judgments,
    validate_judgments,
    write_judge_bundle,
)


def _generations(label: str) -> list[dict[str, object]]:
    return [
        {
            "generation_id": f"{label}-{index}",
            "prompt_id": f"p-{index}",
            "prompt": "Once upon a time",
            "text": f"Story {index}",
            "generation_seed": 2000 + index,
        }
        for index in range(6)
    ]


def _judgment(review_id: str, **updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "review_id": review_id,
        "character_consistency": 2,
        "object_location_consistency": 1,
        "causal_coherence": 1,
        "overall_consistency": 1,
        "flags": ["object_swap"],
        "evidence": "The ball becomes a kite.",
        "reason": "One object changes, while the characters remain stable.",
    }
    row.update(updates)
    return row


def test_build_judge_bundle_is_deterministic_balanced_and_blinded():
    source = {"170m": _generations("170m"), "200m": _generations("200m")}
    first = build_judge_bundle(
        source, per_checkpoint=4, review_seed=3001, batch_size=3
    )
    second = build_judge_bundle(
        source, per_checkpoint=4, review_seed=3001, batch_size=3
    )

    assert first == second
    assert [len(batch) for batch in first["batches"]] == [3, 3, 2]
    assert len(first["review_key"]) == 8
    assert all(
        set(row) == {"review_id", "prompt", "text"}
        for batch in first["batches"]
        for row in batch
    )
    assert {
        item["checkpoint_label"] for item in first["review_key"].values()
    } == {"170m", "200m"}


def test_validate_and_summarize_llm_judgments():
    checked = validate_judgments([_judgment("review-0001")], {"review-0001"})
    result = summarize_judgments(
        checked,
        {"review-0001": {"checkpoint_label": "170m", "generation_id": "g1"}},
    )

    assert result["checkpoints"]["170m"]["mean_overall_consistency"] == 1.0
    assert result["checkpoints"]["170m"]["flag_counts"] == {"object_swap": 1}
    assert result["checkpoints"]["170m"]["overall_consistency_distribution"] == {
        "0": 0,
        "1": 1,
        "2": 0,
    }


def test_validate_judgments_rejects_missing_out_of_range_and_boolean_scores():
    missing = _judgment("review-0001")
    del missing["overall_consistency"]
    with pytest.raises(ValueError, match="overall_consistency"):
        validate_judgments([missing], {"review-0001"})

    with pytest.raises(ValueError, match="0, 1, or 2"):
        validate_judgments(
            [_judgment("review-0001", overall_consistency=3)], {"review-0001"}
        )
    with pytest.raises(ValueError, match="0, 1, or 2"):
        validate_judgments(
            [_judgment("review-0001", causal_coherence=True)], {"review-0001"}
        )


def test_validate_judgments_requires_exact_review_coverage_and_valid_flags():
    with pytest.raises(ValueError, match="missing review ids"):
        validate_judgments([_judgment("review-0001")], {"review-0001", "review-0002"})
    with pytest.raises(ValueError, match="unknown review id"):
        validate_judgments([_judgment("review-9999")], {"review-0001"})
    with pytest.raises(ValueError, match="cannot be combined"):
        validate_judgments(
            [_judgment("review-0001", flags=["none", "object_swap"])],
            {"review-0001"},
        )


def test_write_judge_bundle_writes_blinded_batches_and_refuses_overwrite(tmp_path):
    bundle = build_judge_bundle(
        {"170m": _generations("170m"), "200m": _generations("200m")},
        per_checkpoint=2,
        review_seed=3001,
        batch_size=3,
    )

    write_judge_bundle(tmp_path, bundle, "Judge prompt")

    batch_paths = sorted((tmp_path / "llm_judge" / "batches").glob("*.jsonl"))
    rows = [
        json.loads(line)
        for path in batch_paths
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 4
    assert all(set(row) == {"review_id", "prompt", "text"} for row in rows)
    assert (tmp_path / "llm_judge" / "results").is_dir()
    with pytest.raises(FileExistsError):
        write_judge_bundle(tmp_path, bundle, "Judge prompt")
