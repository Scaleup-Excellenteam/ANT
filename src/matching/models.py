"""Shared data records for the Matching phase (Member 2).

`AutoCompleteData` is the fixed output contract with Member 3 (Serving), per
PROJECT_SPEC.md section 5.1 / SPEC_MEMBER_2_MATCHING.md -- field names and types must not
change without updating that contract.

`MatchResult` is Member 2's own internal record: the output of the <=1-edit substring
verifier (`verifier.py`), consumed by the scoring function (`scoring.py`). Kept here (rather
than in either of those modules) so both can import it without a circular dependency.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AutoCompleteData:
    completed_sentence: str
    source_text: str
    offset: int
    score: int


@dataclass(frozen=True)
class MatchResult:
    """The result of verifying a normalized query against a normalized sentence.

    Attributes:
        edit_type: one of "exact", "substitution", "insertion", "deletion".
        edit_position: 1-based position (in the normalized QUERY) of the edit. `None` for
            an exact match (no edit was applied). For insertion/deletion, this is the
            position at which the character would be inserted / was deleted, per
            PROJECT_SPEC.md section 6.
        matching_characters: number of query characters that earned matching credit -- the
            edited/inserted/deleted character itself never counts (PROJECT_SPEC.md section 9
            / SPEC_MEMBER_2_MATCHING.md).
    """

    edit_type: str
    edit_position: Optional[int]
    matching_characters: int
