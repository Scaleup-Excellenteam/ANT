"""CorpusIndex -- the single object Member 1 hands off to Member 2 (Matching) and Member 3
(Serving). See `src/init_offline/README.md` for the full hand-off contract and the
short-query fallback usage pattern (query lengths 1-5).
"""

import os
import pickle
import time
from typing import List

from .corpus_loader import iter_corpus_lines
from .models import SentenceRecord
from .text_utils import normalize
from .trigram_index import TrigramIndex
from .vocabulary_trie import VocabularyTrie
from .word_index import WordInvertedIndex

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_ARCHIVE_PATH = os.path.join(_REPO_ROOT, "Archive.zip")
DEFAULT_CACHE_PATH = os.path.join(_REPO_ROOT, "corpus_index.pickle")

# Below this normalized query length, the trigram index's "at least one surviving trigram"
# correctness guarantee does not hold (see trigram_index.py module docstring) -- callers must
# use the short-query fallback documented in README.md instead of relying on
# `trigram_candidates` alone.
SHORT_QUERY_MAX_LENGTH = 5


class CorpusIndex:
    def __init__(self) -> None:
        self.sentences: List[SentenceRecord] = []
        self.word_index = WordInvertedIndex()
        self.trigram_index = TrigramIndex()
        self.vocabulary = VocabularyTrie()

    # ---- build ----------------------------------------------------------------

    @classmethod
    def build_from_zip(cls, zip_path: str = DEFAULT_ARCHIVE_PATH) -> "CorpusIndex":
        index = cls()
        for sentence_id, raw_line in enumerate(iter_corpus_lines(zip_path)):
            index.sentences.append(
                SentenceRecord(
                    sentence_id=sentence_id,
                    original_text=raw_line.original_text,
                    normalized_text=normalize(raw_line.original_text),
                    source_path=raw_line.source_path,
                    offset=raw_line.offset,
                )
            )
        index.word_index.build(index.sentences)
        index.trigram_index.build(index.sentences)
        index.vocabulary.build(index.word_index.vocabulary())
        return index

    # ---- public query API (Member 2 / Member 3 hand-off) -----------------------

    def get_sentence(self, sentence_id: int) -> SentenceRecord:
        """The full sentence record for a candidate `sentence_id` -- includes original text,
        source path, and offset, ready to become an `AutoCompleteData`.
        """
        return self.sentences[sentence_id]

    def word_candidates(self, word: str) -> List[int]:
        """sentence_ids of sentences containing `word` as a complete word (fast path)."""
        return self.word_index.candidates(word)

    def trigram_candidates(self, normalized_text: str):
        """sentence_ids sharing at least one trigram with `normalized_text` (correctness
        backstop -- see trigram_index.py). Only a completeness GUARANTEE for
        len(normalized_text) >= 6; for shorter text see `short_query_candidates`.
        """
        return self.trigram_index.candidates_for_text(normalized_text)

    def short_query_candidates(self, normalized_query: str):
        """Correctness-complete-ish candidate set for queries with 1-5 normalized characters.

        See README.md "Short-query fallback (lengths 1-5)" for the full rationale. Combines:
          - trigram candidates for whatever trigrams exist (0 if len < 3, else len-2 of them)
          - every sentence containing a vocabulary word that itself contains the query as a
            substring (catches matches entirely inside one word, and catches the case where a
            length-1/2 query is too short to form any trigram at all)
        """
        if len(normalized_query) > SHORT_QUERY_MAX_LENGTH:
            raise ValueError(
                f"short_query_candidates is only for queries of length <= "
                f"{SHORT_QUERY_MAX_LENGTH}; got length {len(normalized_query)}"
            )
        candidates = set(self.trigram_index.candidates_for_text(normalized_query))
        for word in self.vocabulary.words_containing_substring(normalized_query):
            candidates.update(self.word_index.candidates(word))
        return candidates

    def fuzzy_vocabulary_lookup(self, word: str, max_edits: int = 1) -> List[str]:
        """Vocabulary words within `max_edits` edits of `word` -- for finding an anchor word
        that itself contains the query's one allowed typo.
        """
        return self.vocabulary.fuzzy_lookup(word, max_edits)

    def __len__(self) -> int:
        return len(self.sentences)


# ---- persistence ---------------------------------------------------------------


def save_index(index: CorpusIndex, cache_path: str = DEFAULT_CACHE_PATH) -> None:
    with open(cache_path, "wb") as f:
        pickle.dump(index, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_index(cache_path: str = DEFAULT_CACHE_PATH) -> CorpusIndex:
    with open(cache_path, "rb") as f:
        return pickle.load(f)


def load_or_build_index(
    zip_path: str = DEFAULT_ARCHIVE_PATH, cache_path: str = DEFAULT_CACHE_PATH
) -> CorpusIndex:
    """Load the cached index if present, otherwise build it from the corpus and cache it."""
    if os.path.exists(cache_path):
        return load_index(cache_path)
    index = CorpusIndex.build_from_zip(zip_path)
    save_index(index, cache_path)
    return index


def build_and_report(zip_path: str = DEFAULT_ARCHIVE_PATH) -> CorpusIndex:
    """Build from scratch and print size/timing stats -- used by the CLI entry point and by
    the benchmark run. Does not read or write the pickle cache.
    """
    start = time.time()
    index = CorpusIndex.build_from_zip(zip_path)
    elapsed = time.time() - start

    print(f"Built corpus index from: {zip_path}")
    print(f"Sentences: {len(index.sentences)}")
    print(f"Distinct words (vocabulary size): {len(index.vocabulary)}")
    print(f"Distinct trigrams: {len(index.trigram_index)}")
    print(f"Build time: {elapsed:.2f}s")
    return index


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ARCHIVE_PATH
    built = build_and_report(path)
    save_index(built)
    print(f"Cached index to: {DEFAULT_CACHE_PATH}")
