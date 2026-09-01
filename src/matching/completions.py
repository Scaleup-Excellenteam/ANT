"""get_best_k_completions -- Member 2's public deliverable (PROJECT_SPEC.md section 5.2 /
SPEC_MEMBER_2_MATCHING.md). Wires together Member 1's candidate-access API, this package's
<=1-edit verifier, and its scoring function.

Pipeline:
    raw prefix
        -> normalize()                                  [Member 1]
        -> generate_candidates(index, normalized_query)  [Member 2, candidates.py]
        -> index.get_sentence(sentence_id)               [Member 1]
        -> verify_match(normalized_query, ...)           [Member 2, verifier.py]
        -> score_match(...)                              [Member 2, scoring.py]
        -> AutoCompleteData(...)
        -> top-k selection by score desc, then completed_sentence alphabetically
"""

import heapq
import logging
import time
from typing import List, Optional

try:
    from ..init_offline import CorpusIndex, load_or_build_index, normalize
except ImportError:
    from init_offline import CorpusIndex, load_or_build_index, normalize

from .candidates import generate_candidates
from .models import AutoCompleteData
from .scoring import score_match
from .verifier import verify_match

DEFAULT_K = 5
logger = logging.getLogger("matching")

# Lazy, process-wide singleton: the index is loaded/built once and reused across calls, per
# PROJECT_SPEC.md's "build once, serve many" architecture (section 3) -- never reloaded or
# rebuilt per keystroke/candidate.
_default_index_instance: Optional[CorpusIndex] = None


def _get_default_index() -> CorpusIndex:
    global _default_index_instance
    if _default_index_instance is None:
        _default_index_instance = load_or_build_index()
    return _default_index_instance


def get_best_k_completions(
    prefix: str, index: Optional[CorpusIndex] = None, k: int = DEFAULT_K
) -> List[AutoCompleteData]:
    """Return the best `k` (default 5) sentence completions for `prefix`, sorted by score
    descending and tie-broken alphabetically by `completed_sentence`, per PROJECT_SPEC.md
    section 7. Returns fewer than `k` if fewer valid matches exist; never pads the result.

    `index` is an injection point for tests (a small synthetic `CorpusIndex`); production
    callers should omit it and let the module-level cached index (built/loaded once via
    `load_or_build_index`) be used.
    """
    normalized_query = normalize(prefix)
    started = time.perf_counter()
    logged_query = prefix[:200].replace("\r", "\\r").replace("\n", "\\n")
    logger.info("Query received: %r", logged_query)
    if not normalized_query:
        # An empty normalized query (e.g. blank/punctuation-only prefix) can never usefully
        # match anything, and Member 1's `short_query_candidates("")` would return a
        # near-total scan of the vocabulary -- deliberately short-circuited here.
        logger.info(
            "Returned 0 results in %.3fs; normalized query is empty",
            time.perf_counter() - started,
        )
        return []

    if index is None:
        index = _get_default_index()

    candidate_started = time.perf_counter()
    candidate_ids = generate_candidates(index, normalized_query)
    logger.debug(
        "Candidates generated: %d in %.3fs",
        len(candidate_ids),
        time.perf_counter() - candidate_started,
    )
    verified_count = 0

    def scored_matches():
        """Yield (score, completed_sentence, source_text, offset) for every candidate that
        verifies -- a plain tuple, not `AutoCompleteData`, since most candidates never make
        the final top k and building the dataclass for each one would be wasted work.
        """
        nonlocal verified_count
        for sentence_id in candidate_ids:
            record = index.get_sentence(sentence_id)
            match = verify_match(normalized_query, record.normalized_text)
            if match is None:
                continue
            verified_count += 1
            yield (score_match(match), record.original_text, record.source_path, record.offset)

    # heapq.nsmallest(k, iterable, key) is documented to be equivalent to
    # sorted(iterable, key=key)[:k] -- identical ranking semantics to a full sort, but
    # O(candidates * log k) instead of O(candidates * log candidates), and it never
    # materializes more than k items at a time (the generator above is consumed lazily).
    # Negating the score in the key makes "smallest key" mean "highest score first"; the
    # completed_sentence stays ascending for the alphabetical tie-break.
    matching_started = time.perf_counter()
    top = heapq.nsmallest(k, scored_matches(), key=lambda item: (-item[0], item[1]))
    matching_elapsed = time.perf_counter() - matching_started
    logger.debug(
        "Matching/verification completed; verified=%d in %.3fs",
        verified_count,
        matching_elapsed,
    )
    logger.debug(
        "Scoring/ranking completed; ranked=%d requested_k=%d pipeline_time=%.3fs",
        len(top),
        k,
        matching_elapsed,
    )

    results = [
        AutoCompleteData(
            completed_sentence=sentence, source_text=source, offset=offset, score=score
        )
        for score, sentence, source, offset in top
    ]
    logger.info("Returned %d results in %.3fs", len(results), time.perf_counter() - started)
    return results
