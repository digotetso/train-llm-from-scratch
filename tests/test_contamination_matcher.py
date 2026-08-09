from matgpt.data.contamination import (
    AhoCorasickContaminationMatcher,
    NaiveContaminationMatcher,
    pattern_fingerprint,
)


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


def test_aho_matcher_retains_no_per_pattern_payloads_after_compilation():
    matcher = AhoCorasickContaminationMatcher(["alpha", "beta"])

    assert not hasattr(matcher, "patterns")
    assert all(value is None for _, value in matcher.automaton.items())
