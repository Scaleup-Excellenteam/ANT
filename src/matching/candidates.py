"""Candidate generation -- isolated here so the strategy can be optimized later without
touching the matcher or scorer. Uses ONLY Member 1's public `CorpusIndex` API
(src/init_offline/README.md), per the strategy documented in SPEC_MEMBER_2_MATCHING.md /
the project handoff:

- normalized query length <= 5: `index.short_query_candidates` (Member 1's own short-query
  fallback, since the trigram index's completeness guarantee doesn't hold below 6 chars).
- normalized query length >= 6:
    FAST PATH: `index.word_candidates` for each query word; if a word has no exact hit,
    fall back to `index.fuzzy_vocabulary_lookup` (the typo may be inside the anchor word
    itself) and feed the results back into `word_candidates`.
    CORRECTNESS BACKSTOP: always ALSO union `index.trigram_candidates` -- this is not
    skipped just because word candidates were found, since the word index alone cannot find
    matches that fall entirely inside a word.
"""

from typing import TYPE_CHECKING, Set

if TYPE_CHECKING:
    from init_offline import CorpusIndex

# Mirrors the threshold documented in src/init_offline/README.md ("Short-query fallback") --
# below this length, `trigram_candidates` alone is not a completeness guarantee.
SHORT_QUERY_MAX_LENGTH = 5


def generate_candidates(index: "CorpusIndex", normalized_query: str) -> Set[int]:
    """sentence_ids that might match `normalized_query` with <=1 edit. A superset -- the
    caller (`completions.get_best_k_completions`) is responsible for verifying each one.
    """
    if not normalized_query:
        return set()

    if len(normalized_query) <= SHORT_QUERY_MAX_LENGTH:
        return set(index.short_query_candidates(normalized_query))

    candidate_ids: Set[int] = set()
    for word in normalized_query.split(" "):
        if not word:
            continue
        word_hits = index.word_candidates(word)
        if word_hits:
            candidate_ids.update(word_hits)
        else:
            for fuzzy_word in index.fuzzy_vocabulary_lookup(word, max_edits=1):
                candidate_ids.update(index.word_candidates(fuzzy_word))

    # Correctness backstop: always union, even when word candidates were already found --
    # it catches matches that fall entirely inside a word, which the word index cannot see.
    candidate_ids.update(index.trigram_candidates(normalized_query))
    return candidate_ids
