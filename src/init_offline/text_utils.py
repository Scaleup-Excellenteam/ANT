"""Normalization shared contract between Init (this module) and Matching (Member 2).

Design decision (documented per SPEC_MEMBER_1_INIT.md "Open Questions"):
    Normalization of CORPUS text happens at build/load time, here, when inserting into the
    trie. The Matching phase must apply this exact same `normalize()` function to the user's
    typed query before walking the trie, so that trie edges and the query are comparable
    character-for-character. The ORIGINAL (non-normalized) text is preserved separately in
    `SentenceRef.original_text` for output, per PROJECT_SPEC.md section 5.4.
"""

import re

_WHITESPACE_RUN = re.compile(r"\s+")
_NON_ALNUM_SPACE = re.compile(r"[^a-z0-9 ]")


def normalize(text: str) -> str:
    """Lowercase, drop punctuation, and collapse whitespace runs to single spaces.

    This must stay behaviorally identical to whatever the Matching phase (Member 2) applies
    to the user's typed input before searching -- it is the shared normalization contract
    described in PROJECT_SPEC.md section 5.4 (case-insensitive, punctuation-insensitive,
    whitespace-run-insensitive matching).
    """
    lowered = text.lower()
    no_punctuation = _NON_ALNUM_SPACE.sub(" ", lowered)
    collapsed = _WHITESPACE_RUN.sub(" ", no_punctuation)
    return collapsed.strip()
