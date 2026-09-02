"""Tests for ZDT (Zero DownTime) on the online/serving side: `HotReloadableIndex` polls the
snapshot pointer published by `init_offline.snapshot_store` and swaps in a new `CorpusIndex`
without a restart. See src/matching/completions.py.
"""

import io
import zipfile

import pytest

from init_offline.snapshot_store import publish_snapshot
from matching.completions import HotReloadableIndex


def write_temp_zip(tmp_path, files, name="corpus.zip"):
    zip_path = tmp_path / name
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    zip_path.write_bytes(buf.getvalue())
    return str(zip_path)


def test_get_loads_the_published_snapshot_on_first_call(tmp_path):
    zip_path = write_temp_zip(tmp_path, {"a.txt": "hello world\n"})
    snapshots_dir = str(tmp_path / "snapshots")
    publish_snapshot(zip_path=zip_path, snapshots_dir=snapshots_dir)

    provider = HotReloadableIndex(snapshots_dir=snapshots_dir, check_interval_seconds=0)

    index = provider.get()

    assert index.word_candidates("hello") == [0]


def test_get_does_not_reload_within_the_check_interval_even_if_pointer_changes(tmp_path):
    snapshots_dir = str(tmp_path / "snapshots")
    first_zip = write_temp_zip(tmp_path, {"a.txt": "hello world\n"}, name="first.zip")
    second_zip = write_temp_zip(tmp_path, {"a.txt": "goodbye world\n"}, name="second.zip")
    publish_snapshot(zip_path=first_zip, snapshots_dir=snapshots_dir)

    # A long check interval means "just published" should not be observed immediately.
    provider = HotReloadableIndex(snapshots_dir=snapshots_dir, check_interval_seconds=3600)
    first_index = provider.get()
    assert first_index.word_candidates("hello") == [0]

    publish_snapshot(zip_path=second_zip, snapshots_dir=snapshots_dir)

    still_old_index = provider.get()
    assert still_old_index.word_candidates("hello") == [0]
    assert still_old_index.word_candidates("goodbye") == []


def test_get_hot_swaps_to_a_newly_published_snapshot_once_the_interval_has_elapsed(tmp_path):
    snapshots_dir = str(tmp_path / "snapshots")
    first_zip = write_temp_zip(tmp_path, {"a.txt": "hello world\n"}, name="first.zip")
    second_zip = write_temp_zip(tmp_path, {"a.txt": "goodbye world\n"}, name="second.zip")
    publish_snapshot(zip_path=first_zip, snapshots_dir=snapshots_dir)

    provider = HotReloadableIndex(snapshots_dir=snapshots_dir, check_interval_seconds=0)
    first_index = provider.get()
    assert first_index.word_candidates("hello") == [0]
    first_version = provider.current_version

    publish_snapshot(zip_path=second_zip, snapshots_dir=snapshots_dir)

    new_index = provider.get()
    assert new_index.word_candidates("goodbye") == [0]
    assert new_index.word_candidates("hello") == []
    assert provider.current_version != first_version
    # In-flight callers that already captured `first_index` keep serving it -- the swap
    # never mutates the old CorpusIndex object in place.
    assert first_index.word_candidates("hello") == [0]


def test_get_keeps_serving_the_old_index_if_the_new_snapshot_directory_is_missing(tmp_path):
    snapshots_dir = str(tmp_path / "snapshots")
    zip_path = write_temp_zip(tmp_path, {"a.txt": "hello world\n"})
    publish_snapshot(zip_path=zip_path, snapshots_dir=snapshots_dir)

    provider = HotReloadableIndex(snapshots_dir=snapshots_dir, check_interval_seconds=0)
    good_index = provider.get()
    assert good_index.word_candidates("hello") == [0]

    # Simulate a pointer that names a version whose directory was never actually built
    # (e.g. a corrupted hand-off) -- the provider must not crash or serve nothing.
    from init_offline.snapshot_store import _pointer_path

    with open(_pointer_path(snapshots_dir), "w") as f:
        f.write("does-not-exist-on-disk")

    still_good_index = provider.get()
    assert still_good_index.word_candidates("hello") == [0]


def test_falls_back_to_legacy_load_or_build_index_when_no_snapshot_was_ever_published(tmp_path):
    zip_path = write_temp_zip(tmp_path, {"a.txt": "hello world\n"})
    cache_path = str(tmp_path / "index.pickle")
    snapshots_dir = str(tmp_path / "snapshots")  # never published to

    provider = HotReloadableIndex(
        snapshots_dir=snapshots_dir,
        check_interval_seconds=0,
        legacy_zip_path=zip_path,
        legacy_cache_path=cache_path,
    )

    index = provider.get()

    assert index.word_candidates("hello") == [0]
    assert provider.current_version is None
