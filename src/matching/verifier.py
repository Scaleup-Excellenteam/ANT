"""The <=1-edit substring verifier -- the algorithmic heart of Member 2's work
(SPEC_MEMBER_2_MATCHING.md checklist item 3).

Given a normalized query and a normalized candidate sentence (already both run through
Member 1's `text_utils.normalize`), decides whether the query is a substring of the sentence,
or becomes one after exactly one substitution/insertion/deletion applied to the QUERY (per
PROJECT_SPEC.md section 5.3's matching definition). More than one edit anywhere -> no match.

Deliberately NOT a general edit-distance matrix over the whole sentence: since only 0 or 1
edit is ever allowed, each edit type has a dedicated O(len(sentence) * len(query)) scan using
a linear two-pointer check per candidate window, which is both simpler to verify by hand and
cheaper than an O(len(sentence) * len(query)) DP table would be per candidate pair anyway (no
matrix allocation, early-exit on a second mismatch). This function is only ever called against
the (small) set of candidate sentences Member 1's index already narrowed down to -- never
against the full corpus -- so this cost is paid per-candidate, not per-corpus-line.

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

    candidates: List[MatchResult] = []
    candidates.extend(_find_substitutions(query, sentence))
    candidates.extend(_find_deletions(query, sentence))
    candidates.extend(_find_insertions(query, sentence))

    if not candidates:
        return None
    return max(candidates, key=score_match)


def _find_substitutions(query: str, sentence: str) -> List[MatchResult]:
    """Windows of `sentence` the same length as `query` that differ in exactly one
    character position.
    """
    results: List[MatchResult] = []
    qlen = len(query)
    slen = len(sentence)
    if qlen == 0 or slen < qlen:
        return results

    for start in range(slen - qlen + 1):
        diff_index = None
        diff_count = 0
        for i in range(qlen):
            if query[i] != sentence[start + i]:
                diff_count += 1
                if diff_count > 1:
                    break
                diff_index = i
        if diff_count == 1:
            results.append(
                MatchResult(
                    edit_type="substitution",
                    edit_position=diff_index + 1,
                    matching_characters=qlen - 1,
                )
            )
    return results


def _find_deletions(query: str, sentence: str) -> List[MatchResult]:
    """Windows of `sentence` one shorter than `query` that equal `query` with exactly one
    character removed (the query has one extra character not present in the sentence).
    """
    results: List[MatchResult] = []
    qlen = len(query)
    window_len = qlen - 1
    if window_len < 0:
        return results
    slen = len(sentence)
    if slen < window_len:
        return results

    for start in range(slen - window_len + 1):
        window = sentence[start : start + window_len]
        position = _one_deletion_position(query, window)
        if position is not None:
            results.append(
                MatchResult(
                    edit_type="deletion", edit_position=position + 1, matching_characters=qlen - 1
                )
            )
    return results


def _find_insertions(query: str, sentence: str) -> List[MatchResult]:
    """Windows of `sentence` one longer than `query` that equal `query` with exactly one
    character inserted (the sentence has one extra character not present in the query).
    """
    results: List[MatchResult] = []
    qlen = len(query)
    window_len = qlen + 1
    slen = len(sentence)
    if slen < window_len:
        return results

    for start in range(slen - window_len + 1):
        window = sentence[start : start + window_len]
        position = _one_insertion_position(query, window)
        if position is not None:
            results.append(
                MatchResult(
                    edit_type="insertion", edit_position=position + 1, matching_characters=qlen
                )
            )
    return results


def _one_deletion_position(query: str, window: str) -> Optional[int]:
    """If `window` (len(query) - 1 chars) equals `query` with exactly one character
    removed, return the 0-based index of the removed character in `query`; else `None`.

    Standard two-pointer "one edit distance" check, specialized to the deletion case.
    """
    qi = wi = 0
    qlen, wlen = len(query), len(window)
    skip_index = None

    while qi < qlen and wi < wlen:
        if query[qi] == window[wi]:
            qi += 1
            wi += 1
        else:
            if skip_index is not None:
                return None
            skip_index = qi
            qi += 1

    if skip_index is None and qi == qlen - 1 and wi == wlen:
        # Only the last character of `query` is left over -- deleting it completes the match.
        skip_index = qi
        qi += 1

    if skip_index is not None and qi == qlen and wi == wlen:
        return skip_index
    return None


def _one_insertion_position(query: str, window: str) -> Optional[int]:
    """If `window` (len(query) + 1 chars) equals `query` with exactly one character
    inserted, return the 0-based index in `query` where the insertion happened; else `None`.

    Mirror of `_one_deletion_position` with the roles of query/window swapped (the extra
    character lives in `window` instead of `query`).
    """
    qi = wi = 0
    qlen, wlen = len(query), len(window)
    insert_index = None

    while qi < qlen and wi < wlen:
        if query[qi] == window[wi]:
            qi += 1
            wi += 1
        else:
            if insert_index is not None:
                return None
            insert_index = qi
            wi += 1

    if insert_index is None and wi == wlen - 1 and qi == qlen:
        # Only the last character of `window` is left over -- it's the inserted one.
        insert_index = qi
        wi += 1

    if insert_index is not None and qi == qlen and wi == wlen:
        return insert_index
    return None
