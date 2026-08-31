"""Matching/scoring phase: owned by Member 2 (Matching + Scoring Engineer) per
SPEC_MEMBER_2_MATCHING.md. Consumes only the public API of `init_offline` (Member 1) --
see src/init_offline/README.md for that contract. Public API consumed by the Serving phase
(Member 3) is re-exported here.
"""

from .candidates import generate_candidates
from .completions import get_best_k_completions
from .models import AutoCompleteData, MatchResult
from .scoring import edit_penalty, score_match
from .verifier import verify_match

__all__ = [
    "AutoCompleteData",
    "MatchResult",
    "generate_candidates",
    "get_best_k_completions",
    "verify_match",
    "score_match",
    "edit_penalty",
]
