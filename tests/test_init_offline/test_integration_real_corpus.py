"""Integration checks against the real Archive.zip corpus shipped in this repo.

These are sanity checks for the Init/Offline phase specifically (per SPEC_MEMBER_1_INIT.md
acceptance criteria: "full corpus load completes without crashing... nested folders were
traversed"). They are skipped automatically if Archive.zip isn't present (e.g. in a checkout
that didn't pull the large corpus file).

The full-trie build (`test_full_trie_build_is_queryable`) is slow (walks the whole ~122MB
corpus) and only runs when RUN_SLOW_TESTS=1 is set in the environment, so normal test runs
stay fast.
"""

import os

import pytest

from init_offline.build_index import DEFAULT_ARCHIVE_PATH, build_trie_from_zip
from init_offline.corpus_loader import iter_corpus_lines
from init_offline.trie import Trie
from init_offline.text_utils import normalize

_ARCHIVE_MISSING = not os.path.exists(DEFAULT_ARCHIVE_PATH)
_SKIP_SLOW = os.environ.get("RUN_SLOW_TESTS") != "1"


@pytest.mark.skipif(_ARCHIVE_MISSING, reason="Archive.zip not present in this checkout")
def test_nested_folder_file_is_present_in_real_corpus():
    found_nested_path = False
    for ref in iter_corpus_lines(DEFAULT_ARCHIVE_PATH):
        if ref.source_path == "python-3.8.4-docs-text/c-api/abstract.txt":
            found_nested_path = True
            break
    assert found_nested_path, "expected nested corpus file was not found by the loader"


@pytest.mark.skipif(_ARCHIVE_MISSING, reason="Archive.zip not present in this checkout")
@pytest.mark.skipif(
    _SKIP_SLOW, reason="set RUN_SLOW_TESTS=1 to run the full corpus build (slow)"
)
def test_full_trie_build_is_queryable():
    trie = build_trie_from_zip(DEFAULT_ARCHIVE_PATH)

    # Sanity: a phrase verified (by direct inspection) to exist verbatim in
    # python-3.8.4-docs-text/about.txt should be findable exactly, starting mid-sentence at a
    # word boundary.
    node = trie.walk_exact(normalize("generated from restructuredtext sources"))
    assert node is not None
    refs = trie.collect_sentence_refs(node)
    assert any(r.source_path == "python-3.8.4-docs-text/about.txt" for r in refs)
