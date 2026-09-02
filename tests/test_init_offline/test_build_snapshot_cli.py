"""Tests for the ZDT operator entry point: build and publish a new corpus snapshot from the
command line, list existing versions, or roll `CURRENT` back to one. This is the concrete
"add a new data source live" workflow described in the top-level README.
"""

import io
import zipfile

from init_offline.build_snapshot_cli import main
from init_offline.snapshot_store import get_current_version, publish_snapshot


def write_temp_zip(tmp_path, files, name="corpus.zip"):
    zip_path = tmp_path / name
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    zip_path.write_bytes(buf.getvalue())
    return str(zip_path)


def test_main_publishes_a_snapshot_and_flips_current(tmp_path, capsys):
    zip_path = write_temp_zip(tmp_path, {"a.txt": "hello world\n"})
    snapshots_dir = str(tmp_path / "snapshots")

    exit_code = main(["--zip", zip_path, "--snapshots-dir", snapshots_dir])

    assert exit_code == 0
    version = get_current_version(snapshots_dir)
    assert version is not None
    assert version in capsys.readouterr().out


def test_main_rejects_an_empty_corpus_and_leaves_current_unset(tmp_path, capsys):
    zip_path = write_temp_zip(tmp_path, {"empty.txt": "\n\n"})
    snapshots_dir = str(tmp_path / "snapshots")

    exit_code = main(["--zip", zip_path, "--snapshots-dir", snapshots_dir])

    assert exit_code != 0
    assert get_current_version(snapshots_dir) is None


def test_main_list_shows_published_versions_and_marks_current(tmp_path, capsys):
    zip_path = write_temp_zip(tmp_path, {"a.txt": "hello world\n"})
    snapshots_dir = str(tmp_path / "snapshots")
    version = publish_snapshot(zip_path=zip_path, snapshots_dir=snapshots_dir)

    exit_code = main(["--snapshots-dir", snapshots_dir, "--list"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert version in out
    assert "current" in out


def test_main_rollback_points_current_back_at_an_older_version(tmp_path, capsys):
    snapshots_dir = str(tmp_path / "snapshots")
    first_zip = write_temp_zip(tmp_path, {"a.txt": "hello world\n"}, name="first.zip")
    second_zip = write_temp_zip(tmp_path, {"a.txt": "goodbye world\n"}, name="second.zip")
    first_version = publish_snapshot(zip_path=first_zip, snapshots_dir=snapshots_dir)
    publish_snapshot(zip_path=second_zip, snapshots_dir=snapshots_dir)

    exit_code = main(["--snapshots-dir", snapshots_dir, "--rollback", first_version])

    assert exit_code == 0
    assert get_current_version(snapshots_dir) == first_version
