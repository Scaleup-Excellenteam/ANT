"""Regression/sanity pass for Member 1's normalize() fix (commit ded3bf1): punctuation is now
DELETED (e.g. "don't" -> "dont"), not replaced with a space (the old, buggy behavior would have
produced "don t"). These tests exercise the REAL `init_offline.normalize()` end-to-end through
Member 2's matcher/scorer/get_best_k_completions -- no normalization logic is duplicated here.

Covers: apostrophes, hyphens, commas, periods, mid-word punctuation, punctuation at the query's
edges, repeated whitespace combined with punctuation, and case combined with punctuation.
"""

from init_offline import normalize
from matching.completions import get_best_k_completions
from matching.verifier import verify_match

OFFICIAL_SENTENCE = "To be or not to be, that is the question."


class TestNormalizeDeletesPunctuation:
    """Sanity-check the CONTRACT this whole file relies on, directly against Member 1's real
    function -- if this ever changes again, these fail first and loudly."""

    def test_apostrophe_deleted_not_spaced(self):
        assert normalize("don't") == "dont"

    def test_hyphen_deleted_not_spaced(self):
        assert normalize("state-of-the-art") == "stateoftheart"

    def test_comma_deleted_not_spaced(self):
        assert normalize("hello,world") == "helloworld"

    def test_period_deleted_not_spaced(self):
        assert normalize("hello.world") == "helloworld"

    def test_punctuation_with_adjacent_space_unaffected(self):
        # comma already followed by a real space -- deleting it doesn't merge the words
        assert normalize("be, that") == "be that"

    def test_repeated_whitespace_collapses(self):
        assert normalize("hello    world") == "hello world"

    def test_uppercase_lowered(self):
        assert normalize("DON'T") == "dont"


class TestApostropheContraction:
    def test_query_with_apostrophe_matches_corpus_with_apostrophe(self, make_index):
        index = make_index(["I don't know the answer."])
        results = get_best_k_completions("don't", index=index)
        assert len(results) == 1
        assert results[0].completed_sentence == "I don't know the answer."

    def test_query_without_apostrophe_matches_corpus_with_apostrophe(self, make_index):
        index = make_index(["I don't know the answer."])
        results = get_best_k_completions("dont", index=index)
        assert len(results) == 1
        assert results[0].completed_sentence == "I don't know the answer."

    def test_both_forms_produce_identical_score(self, make_index):
        index = make_index(["I don't know the answer."])
        with_apostrophe = get_best_k_completions("don't", index=index)
        without_apostrophe = get_best_k_completions("dont", index=index)
        assert with_apostrophe[0].score == without_apostrophe[0].score


class TestHyphenatedCompound:
    def test_hyphenated_and_unhyphenated_query_are_equivalent(self, make_index):
        index = make_index(["This is a state-of-the-art solution."])
        hyphenated = verify_match(normalize("state-of-the-art"), normalize(
            "This is a state-of-the-art solution."
        ))
        unhyphenated = verify_match(normalize("stateoftheart"), normalize(
            "This is a state-of-the-art solution."
        ))
        assert hyphenated == unhyphenated
        assert hyphenated.edit_type == "exact"

    def test_hyphenated_query_end_to_end(self, make_index):
        index = make_index(["This is a state-of-the-art solution."])
        results = get_best_k_completions("state-of-the-art", index=index)
        assert len(results) == 1
        assert results[0].completed_sentence == "This is a state-of-the-art solution."


class TestCommaGluedWords:
    def test_comma_glued_and_plain_query_are_equivalent(self, make_index):
        index = make_index(["Say hello,world to everyone."])
        glued = verify_match(normalize("hello,world"), normalize("Say hello,world to everyone."))
        plain = verify_match(normalize("helloworld"), normalize("Say hello,world to everyone."))
        assert glued == plain
        assert glued.edit_type == "exact"


class TestOfficialSentenceStillCorrect:
    def test_be_comma_that_still_scores_14(self, question_index):
        results = get_best_k_completions("be, that", index=question_index)
        assert len(results) == 1
        assert results[0].completed_sentence == OFFICIAL_SENTENCE
        assert results[0].score == 14


class TestWhitespaceAndPunctuationTogether:
    def test_repeated_spaces_plus_punctuation(self, make_index):
        index = make_index(["I don't know the answer."])
        # extra spaces around a punctuation mark that itself gets deleted
        results = get_best_k_completions("don't    know", index=index)
        assert len(results) == 1
        assert results[0].completed_sentence == "I don't know the answer."
        assert results[0].score == 2 * len("dont know")  # exact match, no penalty


class TestCasePlusPunctuationTogether:
    def test_uppercase_with_apostrophe(self, make_index):
        index = make_index(["I don't know the answer."])
        results = get_best_k_completions("DON'T", index=index)
        assert len(results) == 1
        assert results[0].completed_sentence == "I don't know the answer."


class TestMidWordPunctuation:
    def test_punctuation_inside_a_word_not_just_boundaries(self, make_index):
        # the hyphen sits strictly inside the word, not at a word boundary
        index = make_index(["A well-known fact about this topic."])
        results = get_best_k_completions("wellknown", index=index)
        assert len(results) == 1
        assert results[0].completed_sentence == "A well-known fact about this topic."


class TestPunctuationAtQueryEdges:
    def test_leading_and_trailing_punctuation_stripped(self, make_index):
        index = make_index(["Hello there, friend."])
        results = get_best_k_completions(",hello.", index=index)
        assert len(results) == 1
        assert results[0].completed_sentence == "Hello there, friend."
