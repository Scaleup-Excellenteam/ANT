"""Scoring -- kept strictly separate from match detection (`verifier.py`) so it can be
unit-tested in isolation against the official worked-example table
(PROJECT_SPEC.md section 6.3 / SPEC_MEMBER_2_MATCHING.md).

Formula (PROJECT_SPEC.md section 6):
    score = 2 * matching_characters - edit_penalty

Positions are 1-based, computed on the normalized query. For insertion/deletion, the
position is where the character would be inserted / was deleted.
"""

from .models import MatchResult

_SUBSTITUTION_PENALTY_BY_POSITION = {1: 5, 2: 4, 3: 3, 4: 2}
_SUBSTITUTION_PENALTY_DEFAULT = 1  # position 5+

_INSERTION_DELETION_PENALTY_BY_POSITION = {1: 10, 2: 8, 3: 6, 4: 4}
_INSERTION_DELETION_PENALTY_DEFAULT = 2  # position 5+


def edit_penalty(edit_type: str, position: int) -> int:
    """The penalty for a single edit, per PROJECT_SPEC.md section 6.1 / 6.2."""
    if edit_type == "exact":
        return 0
    if edit_type == "substitution":
        return _SUBSTITUTION_PENALTY_BY_POSITION.get(position, _SUBSTITUTION_PENALTY_DEFAULT)
    if edit_type in ("insertion", "deletion"):
        return _INSERTION_DELETION_PENALTY_BY_POSITION.get(
            position, _INSERTION_DELETION_PENALTY_DEFAULT
        )
    raise ValueError(f"Unknown edit_type: {edit_type!r}")


def score_match(match: MatchResult) -> int:
    """score = 2 * matching_characters - edit_penalty, per PROJECT_SPEC.md section 6."""
    penalty = edit_penalty(match.edit_type, match.edit_position)
    return 2 * match.matching_characters - penalty
