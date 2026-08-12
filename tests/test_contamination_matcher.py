import matgpt.data.contamination as contamination

from matgpt.data.contamination import (
    AhoCorasickContaminationMatcher,
    NaiveContaminationMatcher,
    pattern_fingerprint,
)
from matgpt.utils.hashing import sha256_json


def test_aho_matcher_is_equivalent_to_reference_for_unicode_and_overlaps():
    patterns = ["rrc connection", "connection", "o-ran", "café"]
    reference = NaiveContaminationMatcher(patterns)
    compiled = AhoCorasickContaminationMatcher(patterns)
    texts = [
        "An RRC CONNECTION is established.",
        "The O-RAN radio unit.",
        "Serve café traffic.",
        "No benchmark phrase appears.",
    ]

    assert [reference.contains(text.casefold()) for text in texts] == [
        compiled.contains(text.casefold()) for text in texts
    ]


def test_pattern_fingerprint_is_order_independent_and_content_sensitive():
    assert pattern_fingerprint(["beta", "alpha"]) == pattern_fingerprint(
        ["alpha", "beta"]
    )
    assert pattern_fingerprint(["alpha"]) != pattern_fingerprint(["beta"])


def test_ordered_pattern_fingerprint_matches_manifest_identity_semantics():
    assert hasattr(contamination, "ordered_pattern_fingerprint")
    fingerprint = contamination.ordered_pattern_fingerprint

    assert fingerprint(["beta", "alpha", "alpha"]) == sha256_json(
        ["beta", "alpha", "alpha"]
    )
    assert fingerprint(["beta", "alpha"]) != fingerprint(["alpha", "beta"])


def test_aho_matcher_retains_no_per_pattern_payloads_after_compilation():
    matcher = AhoCorasickContaminationMatcher(["alpha", "beta"])

    assert not hasattr(matcher, "patterns")
    assert all(value is None for _, value in matcher.automaton.items())
