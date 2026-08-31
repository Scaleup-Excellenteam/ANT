"""Normalization + trigram extraction -- the shared contracts between Init (Member 1) and
Matching (Member 2).

Design decision: normalization of CORPUS text happens once, at build time, in
`corpus_index.CorpusIndex.build_from_zip`. Member 2 MUST apply this exact same `normalize()`
function to the user's typed query before doing any lookup, so that words/trigrams line up
character-for-character. The ORIGINAL (non-normalized) text is preserved separately in
`SentenceRecord.original_text` for output, per PROJECT_SPEC.md section 5.4.
"""

import re
from typing import Iterator

_WHITESPACE_RUN = re.compile(r"\s+")
_NON_ALNUM_SPACE = re.compile(r"[^a-z0-9 ]")

TRIGRAM_K = 3


def normalize(text: str) -> str:
    """Lowercase, DELETE punctuation (do not replace it with a space), and collapse
    whitespace runs to single spaces.

    This must stay behaviorally identical to whatever the Matching phase (Member 2) applies
    to the user's typed input before searching -- it is the shared normalization contract
    described in PROJECT_SPEC.md section 5.4, and matches the assignment's own scoring-rule
    wording verbatim: "Normalize case, remove punctuation and collapse repeated spaces
    between words." Punctuation is REMOVED, not replaced by a separator -- a word like
    "don't" normalizes to "dont" (4 characters), not "don t" (5 characters with a space that
    was never in the original text). Getting this wrong would silently change character
    counts/positions for every line containing punctuation with no adjacent whitespace
    (contractions, hyphenated compounds, abbreviations), which directly affects Member 2's
    scoring, since position-based edit penalties are computed against this normalized text.
    """
    lowered = text.lower()
    no_punctuation = _NON_ALNUM_SPACE.sub("", lowered)
    collapsed = _WHITESPACE_RUN.sub(" ", no_punctuation)
    return collapsed.strip()


def trigrams(normalized_text: str, k: int = TRIGRAM_K) -> Iterator[str]:
    """Yield every overlapping k-length substring of `normalized_text` (default k=3).

    `normalized_text` must already be normalized -- this function does no normalization of
    its own. Yields nothing if the text is shorter than `k` (see the short-query fallback
    documented in `src/init_offline/README.md` for how Member 2 should handle that case).
    """
    for i in range(len(normalized_text) - k + 1):
        yield normalized_text[i : i + k]
