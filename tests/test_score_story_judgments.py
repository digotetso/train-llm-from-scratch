import json
import sys
from pathlib import Path

import pytest

from scripts import score_story_judgments as scoring_script


def _judgment(review_id: str, overall: int) -> dict[str, object]:
    return {
        "review_id": review_id,
        "character_consistency": 2,
        "object_location_consistency": 2,
        "causal_coherence": overall,
        "overall_consistency": overall,
        "flags": ["none"] if overall == 2 else ["causal_break"],
        "evidence": "The ending follows the earlier event.",
        "reason": "The sequence is internally consistent.",
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


def test_score_story_judgments_cli_joins_key_and_aggregates_two_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    key_path = tmp_path / "review_key.json"
    key_path.write_text(
        json.dumps(
            {
                "review-0001": {
                    "checkpoint_label": "170m",
                    "generation_id": "170m-p1-s1",
                    "prompt_id": "p1",
                    "generation_seed": 2001,
                },
                "review-0002": {
                    "checkpoint_label": "200m",
                    "generation_id": "200m-p1-s1",
                    "prompt_id": "p1",
                    "generation_seed": 2001,
                },
            }
        ),
        encoding="utf-8",
    )
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    _write_jsonl(first, [_judgment("review-0001", 2)])
    _write_jsonl(second, [_judgment("review-0002", 1)])
    output = tmp_path / "scored.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "score_story_judgments.py",
            "--key",
            str(key_path),
            "--judgments",
            str(first),
            "--judgments",
            str(second),
            "--reviewer",
            "llm",
            "--output",
            str(output),
        ],
    )

    scoring_script.main()

    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["reviewer"] == "llm"
    assert len(result["judgments"]) == 2
    assert result["judgments"][0]["checkpoint_label"] == "170m"
    assert set(result["summary"]["checkpoints"]) == {"170m", "200m"}


@pytest.mark.parametrize(
    ("rows", "expected_error"),
    [
        (
            [_judgment("review-0001", 2), _judgment("review-0001", 2)],
            "duplicate review id",
        ),
        ([_judgment("review-9999", 2)], "unknown review id"),
    ],
)
def test_score_story_judgments_cli_rejects_duplicate_or_unknown_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rows: list[dict[str, object]],
    expected_error: str,
):
    key_path = tmp_path / "review_key.json"
    key_path.write_text(
        json.dumps(
            {
                "review-0001": {
                    "checkpoint_label": "170m",
                    "generation_id": "g1",
                }
            }
        ),
        encoding="utf-8",
    )
    judgments = tmp_path / "judgments.jsonl"
    _write_jsonl(judgments, rows)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "score_story_judgments.py",
            "--key",
            str(key_path),
            "--judgments",
            str(judgments),
            "--reviewer",
            "llm",
            "--output",
            str(tmp_path / "scored.json"),
        ],
    )

    with pytest.raises(ValueError, match=expected_error):
        scoring_script.main()
