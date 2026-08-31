import pytest

from init_offline import normalize
from matching.scoring import score_match
from matching.verifier import verify_match

SENTENCE = normalize("To be or not to be, that is the question.")


class TestOfficialExamples:
    """PROJECT_SPEC.md section 6.3 -- the required acceptance table."""

    @pytest.mark.parametrize(
        "query,expected_score,expected_type",
        [
            ("To be", 10, "exact"),
            ("or Not", 12, "exact"),
            ("be, that", 14, "exact"),
            ("2o be", 3, "substitution"),
            ("to pe", 6, "substitution"),
            ("or knot", 8, "deletion"),
            ("or nt", 8, "insertion"),
        ],
    )
    def test_official_matches(self, query, expected_score, expected_type):
        result = verify_match(normalize(query), SENTENCE)
        assert result is not None
        assert result.edit_type == expected_type
        assert score_match(result) == expected_score

    def test_official_no_match(self):
        assert verify_match(normalize("not be"), SENTENCE) is None

    def test_substitution_position_2o_be_is_1(self):
        result = verify_match(normalize("2o be"), SENTENCE)
        assert result.edit_position == 1

    def test_substitution_position_to_pe_is_4(self):
        result = verify_match(normalize("to pe"), SENTENCE)
        assert result.edit_position == 4

    def test_deletion_position_or_knot_is_4(self):
        result = verify_match(normalize("or knot"), SENTENCE)
        assert result.edit_position == 4

    def test_insertion_position_or_nt_is_5(self):
        result = verify_match(normalize("or nt"), SENTENCE)
        assert result.edit_position == 5


class TestAdditionalEdgeCases:
    def test_two_mistakes_rejected(self):
        # "2o pe" needs a substitution at pos 1 AND pos 4 to reach "to be" -- 2 edits, no match.
        assert verify_match(normalize("2o pe"), SENTENCE) is None

    def test_mistake_at_beginning(self):
        result = verify_match(normalize("Xo be"), SENTENCE)
        assert result is not None
        assert result.edit_type == "substitution"
        assert result.edit_position == 1

    def test_mistake_in_middle(self):
        # "or xot" -> substitute 'x' for 'n' at position 4 of "or not"
        result = verify_match(normalize("or xot"), SENTENCE)
        assert result is not None
        assert result.edit_type == "substitution"
        assert result.edit_position == 4

    def test_mistake_at_end(self):
        # "to bx" -> substitute 'x' for 'e' at position 5
        result = verify_match(normalize("to bx"), SENTENCE)
        assert result is not None
        assert result.edit_type == "substitution"
        assert result.edit_position == 5

    def test_exact_match_in_middle_of_sentence(self):
        result = verify_match(normalize("not to be"), SENTENCE)
        assert result is not None
        assert result.edit_type == "exact"

    def test_mid_word_substring_match(self):
        # "question" contains "est" entirely inside a word, not at a word boundary.
        result = verify_match(normalize("est"), SENTENCE)
        assert result is not None
        assert result.edit_type == "exact"

    def test_repeated_spaces_normalize_identically(self):
        collapsed = verify_match(normalize("to   be"), SENTENCE)
        single = verify_match(normalize("to be"), SENTENCE)
        assert collapsed == single

    def test_punctuation_in_query_is_ignored(self):
        with_punct = verify_match(normalize("to be,"), SENTENCE)
        without_punct = verify_match(normalize("to be"), SENTENCE)
        assert with_punct is not None
        assert with_punct.edit_type == "exact"
        assert with_punct == without_punct

    def test_case_insensitive(self):
        upper = verify_match(normalize("TO BE"), SENTENCE)
        lower = verify_match(normalize("to be"), SENTENCE)
        assert upper == lower

    def test_one_character_exact_match(self):
        result = verify_match(normalize("t"), SENTENCE)
        assert result is not None
        assert result.edit_type == "exact"
        assert result.matching_characters == 1

    def test_empty_query_no_match(self):
        assert verify_match("", SENTENCE) is None

    def test_no_match_when_sentence_lacks_characters_entirely(self):
        assert verify_match(normalize("xyz123"), SENTENCE) is None
