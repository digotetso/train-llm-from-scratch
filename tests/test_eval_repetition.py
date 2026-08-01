from matgpt.eval.repetition import aggregate_repetition, measure_repetition


def test_measure_repetition_counts_repeated_words_phrases_and_sentences():
    result = measure_repetition(
        "Go go home. The little dog ran home. The little dog ran home!"
    )

    assert result["word_count"] == 13
    assert result["sentence_count"] == 3
    assert result["consecutive_duplicate_words"] == 1
    assert result["repeated_3gram_occurrences"] == 4
    assert result["repeated_4gram_occurrences"] == 3
    assert result["duplicate_sentence_occurrences"] == 1
    assert result["repeated_3gram_rate"] == 4 / 11
    assert result["repeated_4gram_rate"] == 3 / 10
    assert result["duplicate_sentence_rate"] == 1 / 3


def test_measure_repetition_defines_zero_rates_for_empty_text():
    result = measure_repetition("")

    assert result["word_count"] == 0
    assert result["repeated_3gram_rate"] == 0.0
    assert result["distinct_2gram_ratio"] == 0.0


def test_aggregate_repetition_averages_each_rate():
    result = aggregate_repetition(
        [measure_repetition("A cat ran."), measure_repetition("A cat. A cat.")]
    )

    assert result["story_count"] == 2
    assert result["mean_duplicate_sentence_rate"] == 0.25
