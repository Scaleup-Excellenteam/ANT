import pytest

from matching.models import MatchResult
from matching.scoring import edit_penalty, score_match


class TestEditPenalty:
    def test_exact_is_zero(self):
        assert edit_penalty("exact", None) == 0

    @pytest.mark.parametrize(
        "position,expected", [(1, 5), (2, 4), (3, 3), (4, 2), (5, 1), (6, 1), (100, 1)]
    )
    def test_substitution_penalty_by_position(self, position, expected):
        assert edit_penalty("substitution", position) == expected

    @pytest.mark.parametrize(
        "position,expected", [(1, 10), (2, 8), (3, 6), (4, 4), (5, 2), (6, 2), (100, 2)]
    )
    def test_insertion_penalty_by_position(self, position, expected):
        assert edit_penalty("insertion", position) == expected

    @pytest.mark.parametrize(
        "position,expected", [(1, 10), (2, 8), (3, 6), (4, 4), (5, 2), (6, 2), (100, 2)]
    )
    def test_deletion_penalty_by_position(self, position, expected):
        assert edit_penalty("deletion", position) == expected

    def test_unknown_edit_type_raises(self):
        with pytest.raises(ValueError):
            edit_penalty("bogus", 1)


class TestScoreMatch:
    """The official worked-example table, PROJECT_SPEC.md section 6.3, exercised directly
    against MatchResult -> score (the matcher is tested separately in test_verifier.py).
    """

    def test_exact_to_be(self):
        # "To be" -> 5 matching chars incl. space, no penalty: 2*5 = 10
        match = MatchResult(edit_type="exact", edit_position=None, matching_characters=5)
        assert score_match(match) == 10

    def test_exact_or_not(self):
        # "or Not" -> 6 matching chars: 2*6 = 12
        match = MatchResult(edit_type="exact", edit_position=None, matching_characters=6)
        assert score_match(match) == 12

    def test_exact_be_that(self):
        # "be, that" -> "be that" normalized, 7 matching chars: 2*7 = 14
        match = MatchResult(edit_type="exact", edit_position=None, matching_characters=7)
        assert score_match(match) == 14

    def test_substitution_2o_be(self):
        # substitute pos 1, 4 matching chars: 2*4 - 5 = 3
        match = MatchResult(edit_type="substitution", edit_position=1, matching_characters=4)
        assert score_match(match) == 3

    def test_substitution_to_pe(self):
        # substitute pos 4, 4 matching chars: 2*4 - 2 = 6
        match = MatchResult(edit_type="substitution", edit_position=4, matching_characters=4)
        assert score_match(match) == 6

    def test_deletion_or_knot(self):
        # delete extra char at pos 4, 6 matching chars: 2*6 - 4 = 8
        match = MatchResult(edit_type="deletion", edit_position=4, matching_characters=6)
        assert score_match(match) == 8

    def test_insertion_or_nt(self):
        # insert missing char at pos 5, 5 matching chars: 2*5 - 2 = 8
        match = MatchResult(edit_type="insertion", edit_position=5, matching_characters=5)
        assert score_match(match) == 8
