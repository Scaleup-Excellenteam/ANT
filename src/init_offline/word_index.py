"""Word-level inverted index -- the FAST PATH for candidate generation.

Maps each distinct normalized word to the sentence_ids of every sentence containing it. This
is the cheap, common-case lookup Member 2 should try first: pick an anchor word from the
query, look it up here, and you almost always get a small, precise candidate set.

On its own this index is a HEURISTIC, not a correctness guarantee -- it only finds sentences
that share a complete word with the query. Matches that fall entirely inside a word (no shared
whole word) are NOT found here; that's what `trigram_index.TrigramIndex` is for. See
`src/init_offline/README.md` for how the two combine into a correctness-complete design.

Postings storage (memory optimization, same reasoning as trigram_index.py): a `set` is only
needed during accumulation for O(1) dedup; the finished index stores each bucket as a sorted
`array.array('L', ...)` instead of a `set`/`list` of boxed ints, since postings are only ever
iterated once built. `candidates()` still returns a plain `List[int]` -- the conversion happens
at this API boundary, so Member 2's contract is unchanged.
"""

from array import array
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from .models import SentenceRecord

_POSTINGS_TYPECODE = "L"  # array module guarantees >= 4 bytes for 'L'


class WordInvertedIndex:
    def __init__(self) -> None:
        self._postings: Dict[str, array] = {}

    def build(self, sentences: Iterable[SentenceRecord]) -> None:
        buckets: Dict[str, set] = defaultdict(set)
        for sentence in sentences:
            for word in sentence.normalized_text.split(" "):
                if word:
                    buckets[word].add(sentence.sentence_id)
        self._postings = {
            word: array(_POSTINGS_TYPECODE, sorted(ids)) for word, ids in buckets.items()
        }

    def candidates(self, word: str) -> List[int]:
        """sentence_ids of every sentence containing `word` as a complete word. Empty list
        if the word never appears in the corpus -- this is a normal, expected outcome
        (e.g. the word contains the query's typo), not an error.
        """
        return list(self._postings.get(word, ()))

    def vocabulary(self) -> Tuple[str, ...]:
        """Every distinct normalized word in the corpus -- the input to building the
        vocabulary fuzzy-lookup structure.
        """
        return tuple(self._postings.keys())

    def __len__(self) -> int:
        return len(self._postings)
