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
"""

from collections import defaultdict
from typing import Dict, Iterable, Set

from .models import SentenceRecord
from .text_utils import TRIGRAM_K, trigrams

MIN_QUERY_LENGTH_FOR_GUARANTEE = 2 * TRIGRAM_K  # see module docstring: 3 corrupted + 1 survivor


class TrigramIndex:
    def __init__(self, k: int = TRIGRAM_K) -> None:
        self.k = k
        self._postings: Dict[str, Set[int]] = {}

    def build(self, sentences: Iterable[SentenceRecord]) -> None:
        buckets: Dict[str, Set[int]] = defaultdict(set)
        for sentence in sentences:
            # dedupe per sentence first so a repeated trigram within one line only costs one
            # set-insertion per distinct trigram, not one per occurrence.
            for trigram in set(trigrams(sentence.normalized_text, self.k)):
                buckets[trigram].add(sentence.sentence_id)
        self._postings = dict(buckets)

    def candidates_for_trigram(self, trigram: str) -> Set[int]:
        """sentence_ids of every sentence containing this exact trigram, anywhere."""
        return self._postings.get(trigram, set())

    def candidates_for_text(self, normalized_text: str) -> Set[int]:
        """Union of candidates for every trigram in `normalized_text`.

        Empty set if `normalized_text` is shorter than k (no trigrams exist) -- callers must
        use the short-query fallback (README) in that case, not treat an empty set as "no
        matches exist".
        """
        result: Set[int] = set()
        for trigram in set(trigrams(normalized_text, self.k)):
            result |= self._postings.get(trigram, set())
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
