"""Integration checks against the real Archive.zip corpus shipped in this repo.

Skipped automatically if Archive.zip isn't present. The full build
(`test_full_index_build_is_queryable`) is gated behind RUN_SLOW_TESTS=1 since it walks the
whole ~122MB corpus -- normal test runs stay fast.
"""

import os

import pytest

from init_offline.corpus_index import DEFAULT_ARCHIVE_PATH, CorpusIndex
from init_offline.corpus_loader import iter_corpus_lines
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
def test_full_index_build_is_queryable():
    index = CorpusIndex.build_from_zip(DEFAULT_ARCHIVE_PATH)

    # Sanity: a phrase verified (by direct inspection) to exist verbatim in
    # python-3.8.4-docs-text/about.txt, via the word-index fast path.
    candidates = index.word_candidates("restructuredtext")
    assert len(candidates) > 0
    assert any(
        index.get_sentence(sid).source_path == "python-3.8.4-docs-text/about.txt"
        for sid in candidates
    )

    # Sanity: trigram index also finds it via a mid-phrase substring.
    trigram_candidates = index.trigram_candidates(normalize("generated from restructuredtext"))
    assert set(candidates) & trigram_candidates
