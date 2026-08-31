"""The <=1-edit substring verifier -- the algorithmic heart of Member 2's work
(SPEC_MEMBER_2_MATCHING.md checklist item 3).

Given a normalized query and a normalized candidate sentence (already both run through
Member 1's `text_utils.normalize`), decides whether the query is a substring of the sentence,
or becomes one after exactly one substitution/insertion/deletion applied to the QUERY (per
PROJECT_SPEC.md section 5.3's matching definition). More than one edit anywhere -> no match.

Deliberately NOT a general edit-distance matrix over the whole sentence: since only 0 or 1
edit is ever allowed, a single fused scan finds all three edit types together (see
`_scan_single_edit_windows`), which is both simpler to verify by hand and cheaper than an
O(len(sentence) * len(query)) DP table would be per candidate pair anyway (no matrix
allocation). This function is only ever called against the (small) set of candidate sentences
Member 1's index already narrowed down to -- never against the full corpus -- so this cost is
paid per-candidate, not per-corpus-line.

A query can match at the start, middle, or end of a sentence, and entirely inside a word --
this module places no restriction on where the matched window falls.
"""

from typing import List, Optional

from .models import MatchResult
from .scoring import score_match


def verify_match(query: str, sentence: str) -> Optional[MatchResult]:
    """Return the best-scoring `MatchResult` if `query` matches `sentence` with <=1 edit,
    else `None`. Both arguments must already be normalized (lowercase, punctuation-stripped,
    whitespace-collapsed) -- via Member 1's `text_utils.normalize`.

    "Best" matters because a query can validly match a sentence in more than one place/way
    (e.g. two different substitution positions); since more than one edit is only checked
    per candidate window, not across windows, we must pick the highest-scoring valid window
    to return.
    """
    if not query:
        return None

    if query in sentence:
        return MatchResult(edit_type="exact", edit_position=None, matching_characters=len(query))

    candidates = _scan_single_edit_windows(query, sentence)
    if not candidates:
        return None
    return max(candidates, key=score_match)


def _scan_single_edit_windows(query: str, sentence: str) -> List[MatchResult]:
    """One fused pass over every candidate start position in `sentence`, checking
    substitution, deletion, and insertion together instead of with three separate scans.

    The key idea: at a given start position, all three edit types begin the same way --
    walk forward while `query` and `sentence` agree. Call the point where they first
    disagree `front`. From there the three edit types are just three different guesses
    about WHERE the "extra" character is:
      - substitution: the very next characters differ, but the rest lines up if you
        replace that one character.
      - deletion: `query` has an extra character right there that `sentence` doesn't --
        skip it in `query` and the rest lines up.
      - insertion: `sentence` has an extra character right there that `query` doesn't --
        skip it in `sentence` and the rest lines up.
    Since `front` doesn't depend on which of these three we're checking, it's found ONCE
    per start position (not three times), and "the rest lines up" is then checked with a
    single whole-chunk string comparison (fast, implemented in C) instead of continuing to
    compare one character at a time in Python.

    Because `verify_match` already ruled out any exact match anywhere in `sentence` before
    calling this, `front` can never reach the full length of `query` while a complete
    query-length window is available -- if it did, that window would BE an exact match,
    which we already know doesn't exist. That invariant is what keeps the slice bounds
    below safe without extra special-casing.
    """
    results: List[MatchResult] = []
    qlen = len(query)
    slen = len(sentence)

    # Deletion's window (qlen - 1) is the shortest, so it accepts the widest range of start
    # positions -- use that as the outer bound; the substitution/insertion checks below
    # each additionally guard for their own (stricter) window actually fitting.
    for start in range(slen - qlen + 2):
        limit = min(qlen, slen - start)
        front = 0
        while front < limit and query[front] == sentence[start + front]:
            front += 1

        if start + qlen <= slen:  # substitution's full-length window fits
            if query[front + 1 :] == sentence[start + front + 1 : start + qlen]:
                results.append(MatchResult("substitution", front + 1, qlen - 1))

        if start + qlen - 1 <= slen:  # deletion's (qlen - 1)-length window fits
            if query[front + 1 :] == sentence[start + front : start + qlen - 1]:
                results.append(MatchResult("deletion", front + 1, qlen - 1))

        if start + qlen + 1 <= slen:  # insertion's (qlen + 1)-length window fits
            if query[front:] == sentence[start + front + 1 : start + qlen + 1]:
                results.append(MatchResult("insertion", front + 1, qlen))

    return results
