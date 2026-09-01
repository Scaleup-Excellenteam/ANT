import logging

import pytest

from matching.completions import get_best_k_completions
from matching.models import AutoCompleteData

OFFICIAL_SENTENCE = "To be or not to be, that is the question."


class TestOfficialExamplesEndToEnd:
    @pytest.mark.parametrize(
        "query,expected_score",
        [
            ("To be", 10),
            ("or Not", 12),
            ("be, that", 14),
            ("2o be", 3),
            ("to pe", 6),
            ("or knot", 8),
            ("or nt", 8),
        ],
    )
    def test_top_result_matches_official_score(self, question_index, query, expected_score):
        results = get_best_k_completions(query, index=question_index)
        assert len(results) == 1
        assert results[0].completed_sentence == OFFICIAL_SENTENCE
        assert results[0].score == expected_score

    def test_no_match_returns_empty_list(self, question_index):
        assert get_best_k_completions("not be", index=question_index) == []


class TestAutoCompleteDataContract:
    def test_fields_are_populated_from_the_record(self, make_index):
        index = make_index(["hello world"])
        results = get_best_k_completions("hello", index=index)
        assert len(results) == 1
        result = results[0]
        assert isinstance(result, AutoCompleteData)
        assert result.completed_sentence == "hello world"
        assert result.source_text == "synthetic.txt"
        assert result.offset == 0  # 0-based, per Member 1's current contract
        assert result.score == 10  # exact, 5 matching chars: 2*5


class TestRankingAndTieBreak:
    def test_equal_scores_sorted_alphabetically(self, make_index):
        index = make_index(["banana split", "apple split", "cherry split"])
        results = get_best_k_completions("split", index=index)
        sentences = [r.completed_sentence for r in results]
        assert sentences == ["apple split", "banana split", "cherry split"]
        assert len({r.score for r in results}) == 1  # confirm this is truly a tie

    def test_higher_score_ranks_above_lower_score(self, make_index):
        index = make_index(["exact match here", "exakt match here"])
        results = get_best_k_completions("exact", index=index)
        assert results[0].completed_sentence == "exact match here"
        assert results[0].score > results[1].score


class TestResultCountBounds:
    def test_more_than_5_matches_returns_only_best_5(self, make_index):
        lines = [f"{letter} common word" for letter in "abcdefg"]  # 7 identical-score matches
        index = make_index(lines)
        results = get_best_k_completions("common", index=index)
        assert len(results) == 5
        # alphabetical tie-break should keep the first 5 alphabetically
        assert [r.completed_sentence for r in results] == sorted(lines)[:5]

    def test_fewer_than_5_matches_returns_only_those_available(self, make_index):
        index = make_index(["only one sentence here", "completely unrelated text"])
        results = get_best_k_completions("only one", index=index)
        assert len(results) == 1
        assert results[0].completed_sentence == "only one sentence here"

    def test_empty_prefix_returns_empty_list(self, make_index):
        index = make_index(["some sentence"])
        assert get_best_k_completions("", index=index) == []
        assert get_best_k_completions("   ...   ", index=index) == []


class TestDuplicateSentences:
    def test_identical_text_different_offsets_stay_distinct(self, make_index):
        index = make_index(["repeat me exactly", "repeat me exactly"])
        results = get_best_k_completions("repeat me exactly", index=index)
        assert len(results) == 2
        offsets = sorted(r.offset for r in results)
        assert offsets == [0, 1]
        assert all(r.completed_sentence == "repeat me exactly" for r in results)


def test_query_pipeline_logs_aggregate_counts_and_timing(make_index, caplog):
    index = make_index(["python language", "python tutorial", "unrelated text"])
    with caplog.at_level(logging.DEBUG):
        results = get_best_k_completions("python", index=index)

    messages = [record.getMessage() for record in caplog.records]
    assert len(results) == 2
    assert any("Query received" in message for message in messages)
    assert any("Candidates generated:" in message for message in messages)
    assert any("verified=" in message for message in messages)
    assert any("Scoring/ranking completed" in message for message in messages)
    assert any("Returned 2 results in" in message for message in messages)
