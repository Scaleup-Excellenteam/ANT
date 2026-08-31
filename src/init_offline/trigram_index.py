"""Character trigram (k=3) index -- the CORRECTNESS BACKSTOP for candidate generation.

Why k=3 (documented decision, see the analysis that preceded this implementation): a single
edit (substitution, insertion, or deletion) can only corrupt the trigrams that literally
overlap the edited character -- at most 3 of them. Trigram MATCHING here is set-based (do
query and candidate share this exact 3-character sequence anywhere?), not position-based, so
insertion/deletion shifting downstream positions doesn't matter -- the actual characters in
every trigram before or after the edit point are unchanged.

Consequence: any normalized query with more than 3 trigrams -- i.e. length >= 6 characters --
is GUARANTEED to retain at least one trigram that exactly matches the true target region, so
the corresponding sentence is guaranteed to be found. This is what closes the gap the word
index leaves open (mid-word substring matches, per PROJECT_SPEC.md section 5.3's literal
wording that a match may start at "the start, middle, or end" of a sentence).

For queries shorter than 6 characters, see the short-query fallback documented in
`src/init_offline/README.md` -- this index alone does not guarantee completeness below that
length (very short queries may have too few trigrams, or none at all if length < 3).

Postings storage (memory optimization, documented decision): a `set` is only useful while
ACCUMULATING postings during the build (need O(1) dedup as sentences stream in). Once the
corpus is fully processed, each trigram's postings are a fixed collection of ints that is only
ever iterated/unioned, never probed one-by-one -- so the finished index stores each bucket as a
sorted `array.array('L', ...)` (raw packed 4-byte integers, no per-element Python object, no
hash table) instead of a `set`. This measured ~5-8x smaller than `set[int]` for the real
corpus (see benchmark in the commit this change belongs to) with no change to correctness or
to the public `Set[int]` return type Member 2 relies on -- conversion happens at the API
boundary, and `set.update()` accepts an `array.array` directly, so query-time union code is
unchanged in shape.
"""

from array import array
from collections import defaultdict
from typing import Dict, Iterable, Set

from .models import SentenceRecord
from .text_utils import TRIGRAM_K, trigrams

MIN_QUERY_LENGTH_FOR_GUARANTEE = 2 * TRIGRAM_K  # see module docstring: 3 corrupted + 1 survivor

# Unsigned long: array module guarantees >= 4 bytes for 'L', comfortably covering corpus sizes
# far larger than this assignment's (max representable value ~4.29 billion sentences).
_POSTINGS_TYPECODE = "L"


class TrigramIndex:
    def __init__(self, k: int = TRIGRAM_K) -> None:
        self.k = k
        self._postings: Dict[str, array] = {}

    def build(self, sentences: Iterable[SentenceRecord]) -> None:
        buckets: Dict[str, set] = defaultdict(set)
        for sentence in sentences:
            # dedupe per sentence first so a repeated trigram within one line only costs one
            # set-insertion per distinct trigram, not one per occurrence.
            for trigram in set(trigrams(sentence.normalized_text, self.k)):
                buckets[trigram].add(sentence.sentence_id)
        self._postings = {
            trigram: array(_POSTINGS_TYPECODE, sorted(ids)) for trigram, ids in buckets.items()
        }

    def candidates_for_trigram(self, trigram: str) -> Set[int]:
        """sentence_ids of every sentence containing this exact trigram, anywhere."""
        return set(self._postings.get(trigram, ()))

    def candidates_for_text(self, normalized_text: str) -> Set[int]:
        """Union of candidates for every trigram in `normalized_text`.

        Empty set if `normalized_text` is shorter than k (no trigrams exist) -- callers must
        use the short-query fallback (README) in that case, not treat an empty set as "no
        matches exist".
        """
        result: Set[int] = set()
        for trigram in set(trigrams(normalized_text, self.k)):
            result.update(self._postings.get(trigram, ()))
        return result

    def postings_size(self, trigram: str) -> int:
        """How many sentences contain this trigram -- useful for Member 2 to pick the
        RAREST trigram in a query as the anchor for candidate narrowing (the common-word
        problem also applies to trigrams: with only ~37 normalized characters, a trigram
        like "the" or " an" can appear in a large fraction of all sentences).
        """
        return len(self._postings.get(trigram, ()))

    def __len__(self) -> int:
        return len(self._postings)
