import json
import sys
from pathlib import Path

import pytest

from scripts import score_story_judgments as scoring_script
from matgpt.utils.hashing import sha256_file


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


def _comparison_fixture(tmp_path: Path, labels: tuple[str, ...]) -> Path:
    checkpoints = {}
    for label in labels:
        checkpoint = tmp_path / f"{label}.pt"
        checkpoint.write_bytes(label.encode())
        checkpoints[label] = {
            "path": str(checkpoint.resolve()),
            "binding": {
                "path": str(checkpoint.resolve()),
                "size": checkpoint.stat().st_size,
                "sha256": sha256_file(checkpoint),
            },
            "evidence": f"checkpoints/{label}.json",
        }
    path = tmp_path / "comparison_summary.json"
    path.write_text(json.dumps({
        "artifact_identity": {"config_sha256": "c" * 64},
        "checkpoints": checkpoints,
    }), encoding="utf-8")
    return path


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
    comparison = _comparison_fixture(tmp_path, ("170m", "200m"))
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
            "--comparison-summary",
            str(comparison),
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
    assert result["comparison"]["sha256"] == sha256_file(comparison)
    assert result["artifact_identity"] == {"config_sha256": "c" * 64}
    assert set(result["checkpoints"]) == {"170m", "200m"}
    assert all(row["size"] > 0 for row in result["checkpoints"].values())


@pytest.mark.parametrize("mutation", ("replaced", "zero_byte", "path_only"))
def test_score_story_judgments_rejects_stale_or_unbound_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
):
    comparison = _comparison_fixture(tmp_path, ("170m",))
    comparison_payload = json.loads(comparison.read_text(encoding="utf-8"))
    checkpoint = tmp_path / "170m.pt"
    if mutation == "replaced":
        checkpoint.write_bytes(b"replacement checkpoint bytes")
    elif mutation == "zero_byte":
        checkpoint.write_bytes(b"")
    else:
        comparison_payload["checkpoints"]["170m"].pop("binding")
        comparison.write_text(json.dumps(comparison_payload), encoding="utf-8")
    key = tmp_path / "review_key.json"
    key.write_text(json.dumps({
        "review-0001": {"checkpoint_label": "170m", "generation_id": "g1"}
    }), encoding="utf-8")
    judgments = tmp_path / "judgments.jsonl"
    _write_jsonl(judgments, [_judgment("review-0001", 2)])
    output = tmp_path / "scored.json"
    monkeypatch.setattr(sys, "argv", [
        "score_story_judgments.py", "--key", str(key), "--judgments",
        str(judgments), "--reviewer", "llm", "--comparison-summary",
        str(comparison), "--output", str(output),
    ])

    with pytest.raises(ValueError, match="checkpoint"):
        scoring_script.main()

    assert not output.exists()


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
    comparison = _comparison_fixture(tmp_path, ("170m",))
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
            "--comparison-summary",
            str(comparison),
            "--output",
            str(tmp_path / "scored.json"),
        ],
    )

    with pytest.raises(ValueError, match=expected_error):
        scoring_script.main()
