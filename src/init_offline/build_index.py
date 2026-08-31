"""Top-level offline build step: corpus -> Trie, with optional on-disk caching.

Corpus location convention (documented decision, per SPEC_MEMBER_1_INIT.md "Open Questions"):
    The program expects "Archive.zip" to sit at the repository root by default. This can be
    overridden by passing an explicit path to `build_trie_from_zip()`, or via a command-line
    argument when running this module directly. There is no environment variable or config
    file for this -- the assignment brief does not specify one, and a single default path is
    the simplest convention for a 3-person team sharing one corpus file.

Caching (optional, not required by the brief; see PROJECT_SPEC.md section 9):
    Building the trie means reading and inserting every word-boundary suffix of every corpus
    line, which is the most expensive part of the offline phase. `save_trie`/`load_trie` pickle
    the built Trie to disk so repeated runs (e.g. every time Member 3's CLI starts, or every
    test run) don't have to rebuild it from scratch. This is purely a performance convenience;
    correctness does not depend on it.
"""

import os
import pickle
import sys
import time

from .corpus_loader import iter_corpus_lines
from .text_utils import normalize
from .trie import Trie

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_ARCHIVE_PATH = os.path.join(_REPO_ROOT, "Archive.zip")
DEFAULT_CACHE_PATH = os.path.join(_REPO_ROOT, "corpus_index.pickle")


def build_trie_from_zip(zip_path: str = DEFAULT_ARCHIVE_PATH) -> Trie:
    """Build a fresh Trie from the corpus at `zip_path`. This is the main hand-off function
    Member 2 (Matching) and Member 3 (Serving) can call to get a ready-to-query structure.
    """
    trie = Trie()
    for ref in iter_corpus_lines(zip_path):
        normalized = normalize(ref.original_text)
        trie.insert_sentence(normalized, ref)
    return trie


def save_trie(trie: Trie, cache_path: str = DEFAULT_CACHE_PATH) -> None:
    with open(cache_path, "wb") as f:
        pickle.dump(trie, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_trie(cache_path: str = DEFAULT_CACHE_PATH) -> Trie:
    with open(cache_path, "rb") as f:
        return pickle.load(f)


def load_or_build_trie(
    zip_path: str = DEFAULT_ARCHIVE_PATH, cache_path: str = DEFAULT_CACHE_PATH
) -> Trie:
    """Load the cached trie if present, otherwise build it from the corpus and cache it."""
    if os.path.exists(cache_path):
        return load_trie(cache_path)
    trie = build_trie_from_zip(zip_path)
    save_trie(trie, cache_path)
    return trie


def _main() -> None:
    zip_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ARCHIVE_PATH

    start = time.time()
    trie = build_trie_from_zip(zip_path)
    elapsed = time.time() - start

    # Note: this counts every word-boundary suffix insertion, not unique corpus lines --
    # each line is inserted once per word it starts with, so this number is intentionally
    # larger than the raw line count. It's a build-sanity signal, not a "sentence count".
    suffix_insertion_count = len(trie.collect_sentence_refs(trie.root))
    print(f"Built trie from: {zip_path}")
    print(f"Word-boundary suffix insertions in trie: {suffix_insertion_count}")
    print(f"Build time: {elapsed:.2f}s")

    save_trie(trie)
    print(f"Cached trie to: {DEFAULT_CACHE_PATH}")


if __name__ == "__main__":
    _main()
