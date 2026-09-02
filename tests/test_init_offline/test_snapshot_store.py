"""Tests for the ZDT (Zero DownTime) offline snapshot store: versioned snapshot
directories plus the atomic CURRENT pointer that hands them off to the online side.
See src/init_offline/snapshot_store.py and the top-level README's "Zero-downtime
snapshot publishing" section.
"""

import io
import os
import zipfile

import pytest

from init_offline.snapshot_store import (
    SnapshotValidationError,
    build_snapshot,
    get_current_version,
    list_snapshot_versions,
    load_snapshot,
    publish_snapshot,
    set_current_version,
)


def write_temp_zip(tmp_path, files, name="corpus.zip"):
    zip_path = tmp_path / name
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    zip_path.write_bytes(buf.getvalue())
    return str(zip_path)


def test_build_snapshot_creates_a_versioned_directory_and_does_not_touch_current(tmp_path):
    zip_path = write_temp_zip(tmp_path, {"a.txt": "hello world\n"})
    snapshots_dir = str(tmp_path / "snapshots")

    version = build_snapshot(zip_path=zip_path, snapshots_dir=snapshots_dir)

    assert os.path.isdir(os.path.join(snapshots_dir, version))
    assert os.path.exists(os.path.join(snapshots_dir, version, "corpus_index.pickle"))
    # build_snapshot only builds -- it must not flip the pointer itself.
    assert get_current_version(snapshots_dir) is None


def test_build_snapshot_rejects_an_empty_corpus_without_creating_a_stray_directory(tmp_path):
    zip_path = write_temp_zip(tmp_path, {"empty.txt": "\n\n\n"})
    snapshots_dir = str(tmp_path / "snapshots")

    with pytest.raises(SnapshotValidationError):
        build_snapshot(zip_path=zip_path, snapshots_dir=snapshots_dir)

    # No half-built or empty-but-published snapshot should be left behind.
    if os.path.isdir(snapshots_dir):
        assert list_snapshot_versions(snapshots_dir) == []


def test_set_current_version_then_get_current_version_roundtrip(tmp_path):
    zip_path = write_temp_zip(tmp_path, {"a.txt": "hello world\n"})
    snapshots_dir = str(tmp_path / "snapshots")
    version = build_snapshot(zip_path=zip_path, snapshots_dir=snapshots_dir)

    assert get_current_version(snapshots_dir) is None
    set_current_version(snapshots_dir, version)
    assert get_current_version(snapshots_dir) == version


def test_set_current_version_rejects_an_unknown_version(tmp_path):
    snapshots_dir = str(tmp_path / "snapshots")
    os.makedirs(snapshots_dir)

    with pytest.raises(FileNotFoundError):
        set_current_version(snapshots_dir, "does-not-exist")


def test_load_snapshot_returns_a_queryable_index_matching_the_source_zip(tmp_path):
    zip_path = write_temp_zip(tmp_path, {"a.txt": "to be or not to be\n"})
    snapshots_dir = str(tmp_path / "snapshots")
    version = build_snapshot(zip_path=zip_path, snapshots_dir=snapshots_dir)

    index = load_snapshot(snapshots_dir, version)

    assert len(index) == 1
    assert index.word_candidates("be") == [0]


def test_publish_snapshot_builds_and_flips_the_pointer_in_one_call(tmp_path):
    zip_path = write_temp_zip(tmp_path, {"a.txt": "hello world\n"})
    snapshots_dir = str(tmp_path / "snapshots")

    version = publish_snapshot(zip_path=zip_path, snapshots_dir=snapshots_dir)

    assert get_current_version(snapshots_dir) == version
    assert load_snapshot(snapshots_dir, version).word_candidates("hello") == [0]


def test_publish_snapshot_with_a_second_data_source_adds_a_new_version_without_losing_the_first(
    tmp_path,
):
    snapshots_dir = str(tmp_path / "snapshots")
    first_zip = write_temp_zip(tmp_path, {"a.txt": "hello world\n"}, name="first.zip")
    second_zip = write_temp_zip(
        tmp_path, {"a.txt": "hello world\n", "b.txt": "a brand new data source\n"}, name="second.zip"
    )

    first_version = publish_snapshot(zip_path=first_zip, snapshots_dir=snapshots_dir)
    second_version = publish_snapshot(zip_path=second_zip, snapshots_dir=snapshots_dir)

    assert first_version != second_version
    # The old snapshot directory is still on disk and still loadable -- publishing a new
    # data source must not overwrite or delete the previous, still-possibly-in-use snapshot.
    assert load_snapshot(snapshots_dir, first_version).word_candidates("hello") == [0]
    new_index = load_snapshot(snapshots_dir, second_version)
    assert new_index.word_candidates("source") != []
    assert get_current_version(snapshots_dir) == second_version
    assert set(list_snapshot_versions(snapshots_dir)) == {first_version, second_version}


def test_rollback_by_pointing_current_back_at_an_older_already_built_version(tmp_path):
    snapshots_dir = str(tmp_path / "snapshots")
    first_zip = write_temp_zip(tmp_path, {"a.txt": "hello world\n"}, name="first.zip")
    second_zip = write_temp_zip(tmp_path, {"a.txt": "goodbye world\n"}, name="second.zip")

    first_version = publish_snapshot(zip_path=first_zip, snapshots_dir=snapshots_dir)
    publish_snapshot(zip_path=second_zip, snapshots_dir=snapshots_dir)

    set_current_version(snapshots_dir, first_version)

    assert get_current_version(snapshots_dir) == first_version


def test_build_snapshot_is_idempotent_for_an_explicit_version_id(tmp_path):
    zip_path = write_temp_zip(tmp_path, {"a.txt": "hello world\n"})
    snapshots_dir = str(tmp_path / "snapshots")

    first = build_snapshot(zip_path=zip_path, snapshots_dir=snapshots_dir, version="v1")
    second = build_snapshot(zip_path=zip_path, snapshots_dir=snapshots_dir, version="v1")

    assert first == second == "v1"
    assert list_snapshot_versions(snapshots_dir) == ["v1"]
