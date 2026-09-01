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
import os
import pickle
import time
from typing import List, Optional

try:
    from ..init_offline import CorpusIndex, load_or_build_index, normalize
    from ..init_offline.snapshot_store import (
        DEFAULT_SNAPSHOTS_DIR,
        get_current_version,
        load_snapshot,
    )
except ImportError:
    from init_offline import CorpusIndex, load_or_build_index, normalize
    from init_offline.snapshot_store import (
        DEFAULT_SNAPSHOTS_DIR,
        get_current_version,
        load_snapshot,
    )

from .candidates import generate_candidates
from .models import AutoCompleteData
from .scoring import score_match
from .verifier import verify_match

DEFAULT_K = 5
DEFAULT_RELOAD_CHECK_INTERVAL_SECONDS = 2.0
logger = logging.getLogger("matching")


class HotReloadableIndex:
    """ZDT (Zero DownTime): serves a `CorpusIndex` and keeps it live-updated.

    Polls the `CURRENT` snapshot pointer written by `init_offline.snapshot_store` at most
    once every `check_interval_seconds` -- not on every call -- so a hot process doing many
    queries per second doesn't `stat()` the pointer file per query. Only when the pointer
    names a version different from the one already loaded does it load that snapshot and
    swap it in.

    The swap itself is one attribute assignment (`self._index = new_index`). CPython
    guarantees a single attribute assignment is atomic under the GIL, so any concurrent
    caller of `.get()` observes either the previous, fully-built index or the new,
    fully-built one -- never a half-loaded object -- and a query already in progress keeps
    using whatever `CorpusIndex` object it already holds a local reference to, since that
    reload never mutates the old object in place. No lock, restart, or dropped request is
    needed for the swap itself. (A fully concurrent/multi-threaded deployment would still
    want a lock around the *check-and-load* sequence in `_refresh_if_due` to avoid two
    threads redundantly loading the same new snapshot at once -- harmless but wasteful; this
    single-process CLI service never triggers that race.)

    If `snapshots_dir` has no `CURRENT` pointer yet (no ZDT snapshot was ever published),
    this transparently falls back to the pre-ZDT behavior -- `load_or_build_index()` against
    the flat `corpus_index.pickle` cache -- so deployments that haven't adopted snapshot
    publishing are unaffected.
    """

    def __init__(
        self,
        snapshots_dir: Optional[str] = None,
        check_interval_seconds: Optional[float] = None,
        legacy_zip_path: Optional[str] = None,
        legacy_cache_path: Optional[str] = None,
    ) -> None:
        self._snapshots_dir = (
            snapshots_dir
            if snapshots_dir is not None
            else os.getenv("ZDT_SNAPSHOTS_DIR", DEFAULT_SNAPSHOTS_DIR)
        )
        self._check_interval = (
            check_interval_seconds
            if check_interval_seconds is not None
            else float(
                os.getenv(
                    "ZDT_RELOAD_CHECK_INTERVAL_SECONDS", DEFAULT_RELOAD_CHECK_INTERVAL_SECONDS
                )
            )
        )
        self._legacy_zip_path = legacy_zip_path
        self._legacy_cache_path = legacy_cache_path
        self._index: Optional[CorpusIndex] = None
        self._version: Optional[str] = None
        self._last_check: Optional[float] = None

    @property
    def current_version(self) -> Optional[str]:
        """The snapshot version currently being served, or None while running on the
        legacy (pre-ZDT, non-versioned) fallback path.

        Future query caching must key on (current_version, normalized_query), not on
        normalized_query alone -- a hot reload can change which sentences the same query
        matches, so a version-blind cache key could serve a stale Top-5 after a swap.
        """
        return self._version

    def get(self) -> CorpusIndex:
        self._refresh_if_due()
        return self._index

    def _refresh_if_due(self) -> None:
        now = time.monotonic()
        if (
            self._index is not None
            and self._last_check is not None
            and now - self._last_check < self._check_interval
        ):
            return
        self._last_check = now

        version = get_current_version(self._snapshots_dir)
        if version is None:
            if self._index is None:
                logger.warning(
                    "No published ZDT snapshot at %s; falling back to legacy "
                    "load_or_build_index()",
                    self._snapshots_dir,
                )
                self._index = self._load_legacy()
            return

        if version == self._version:
            return

        try:
            new_index = load_snapshot(self._snapshots_dir, version)
        except (OSError, pickle.PickleError):
            logger.exception(
                "Failed to load snapshot version=%s from %s; continuing to serve version=%s",
                version,
                self._snapshots_dir,
                self._version,
            )
            if self._index is None:
                raise
            return

        previous_version = self._version
        self._index = new_index
        self._version = version
        logger.info("Hot-swapped corpus index: %s -> %s", previous_version, version)

    def _load_legacy(self) -> CorpusIndex:
        kwargs = {}
        if self._legacy_zip_path is not None:
            kwargs["zip_path"] = self._legacy_zip_path
        if self._legacy_cache_path is not None:
            kwargs["cache_path"] = self._legacy_cache_path
        return load_or_build_index(**kwargs)


# Process-wide singleton: the index is loaded/built once and reused across calls, per
# PROJECT_SPEC.md's "build once, serve many" architecture (section 3) -- never reloaded or
# rebuilt per keystroke/candidate. ZDT extends this: it is polled for a newer *published*
# snapshot on the schedule above, but never reloaded per-query.
_default_index_provider = HotReloadableIndex()


def _get_default_index() -> CorpusIndex:
    return _default_index_provider.get()


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
