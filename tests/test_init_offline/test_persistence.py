"""Tests for save_index/load_index/load_or_build_index -- previously untested by the fast
suite (only manually verified against the real corpus in an earlier session). These use a
small synthetic corpus so they stay fast.
"""

import io
import os
import zipfile

from init_offline.corpus_index import CorpusIndex, load_index, load_or_build_index, save_index
from init_offline.text_utils import normalize


def write_temp_zip(tmp_path, files):
    zip_path = tmp_path / "corpus.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    zip_path.write_bytes(buf.getvalue())
    return str(zip_path)


def test_save_then_load_roundtrip_preserves_query_results(tmp_path):
    zip_path = write_temp_zip(
        tmp_path,
        {
            "a.txt": "to be or not to be, that is the question.\n",
            "b.txt": "asymmetric issues were found\n",
        },
    )
    original = CorpusIndex.build_from_zip(zip_path)
    cache_path = str(tmp_path / "index.pickle")

    save_index(original, cache_path)
    assert os.path.exists(cache_path)

    loaded = load_index(cache_path)

    assert len(loaded) == len(original)
    assert loaded.word_candidates("not") == original.word_candidates("not")
    assert loaded.trigram_candidates(normalize("symmetric")) == original.trigram_candidates(
        normalize("symmetric")
    )
    loaded_record = loaded.get_sentence(0)
    original_record = original.get_sentence(0)
    assert loaded_record == original_record


def test_load_or_build_index_builds_and_caches_when_no_cache_exists(tmp_path):
    zip_path = write_temp_zip(tmp_path, {"a.txt": "hello world\n"})
    cache_path = str(tmp_path / "index.pickle")

    assert not os.path.exists(cache_path)
    index = load_or_build_index(zip_path=zip_path, cache_path=cache_path)

    assert os.path.exists(cache_path)
    assert index.word_candidates("hello") == [0]


def test_load_or_build_index_reuses_existing_cache_without_rebuilding(tmp_path):
    zip_path = write_temp_zip(tmp_path, {"a.txt": "hello world\n"})
    cache_path = str(tmp_path / "index.pickle")

    first = CorpusIndex.build_from_zip(zip_path)
    save_index(first, cache_path)

    # Pass a zip_path that doesn't exist -- if load_or_build_index tried to rebuild instead
    # of using the cache, this would raise (or return something different from the cached
    # index) rather than transparently returning the cached content.
    nonexistent_zip_path = str(tmp_path / "does_not_exist.zip")
    second = load_or_build_index(zip_path=nonexistent_zip_path, cache_path=cache_path)

    assert len(second) == 1
    assert second.word_candidates("hello") == [0]
