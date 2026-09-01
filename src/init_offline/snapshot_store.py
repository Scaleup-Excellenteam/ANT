"""ZDT (Zero DownTime): the filesystem hand-off between the offline corpus-build phase and
the online serving phase.

Before this module, `corpus_index.save_index`/`load_index` wrote and read a single flat
`corpus_index.pickle` cache file, overwritten in place on every rebuild. That's fine for a
one-shot local run, but it has two problems for a live service:
  1. A rebuild-in-progress can leave the online side reading a half-written pickle file.
  2. There is no way to add a new data source without either restarting the online process
     (to pick up the new cache) or racing it while the file is being overwritten.

This module fixes both by keeping every build immutable and versioned, and by handing off
"which version is current" through one small, atomically-written pointer file:

    <snapshots_dir>/
        20260101T120000Z-3f9a2b1c8e4d/corpus_index.pickle   <- immutable once built
        20260101T183000Z-a1b2c3d4e5f6/corpus_index.pickle   <- a newer, independent build
        CURRENT                                              <- one line: the live version id

`build_snapshot` builds a new versioned directory and never touches an existing one.
`set_current_version` is the only thing that ever changes `CURRENT`, and it does so with a
write-to-temp-file-then-`os.replace` (POSIX `rename(2)`), which is atomic within one
filesystem: any reader of `CURRENT` sees either the previous complete contents or the new
complete contents, never a partial write. `publish_snapshot` does both steps in the right
order (build + validate, THEN flip the pointer), so `CURRENT` only ever names a snapshot
that finished building successfully.

The online side (see `matching.completions.HotReloadableIndex`) polls `get_current_version`
and, when it changes, calls `load_snapshot` for the new version and swaps its in-memory
reference -- no restart, and in-flight requests keep using whatever snapshot object they
already hold.

`snapshots_dir` is a plain directory path: on a single machine it is local disk; across
machines it can be any shared/network filesystem (NFS, a synced cloud-storage mount, etc.)
visible to both the offline build job and the online service -- this module does not care
which, it only requires ordinary POSIX rename semantics.
"""

import hashlib
import logging
import os
import shutil
import tempfile
import time
from typing import List, Optional

from .corpus_index import DEFAULT_ARCHIVE_PATH, CorpusIndex, load_index, save_index

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_SNAPSHOTS_DIR = os.path.join(_REPO_ROOT, ".runtime", "corpus_snapshots")

POINTER_FILENAME = "CURRENT"
SNAPSHOT_INDEX_FILENAME = "corpus_index.pickle"

logger = logging.getLogger("snapshot_store")


class SnapshotValidationError(Exception):
    """Raised when a freshly built snapshot fails validation and must not be published."""


def _pointer_path(snapshots_dir: str) -> str:
    return os.path.join(snapshots_dir, POINTER_FILENAME)


def _snapshot_dir(snapshots_dir: str, version: str) -> str:
    return os.path.join(snapshots_dir, version)


def _make_version_id(zip_path: str) -> str:
    """A UTC timestamp plus a short content hash of `zip_path`.

    The timestamp keeps version ids sortable and human-traceable ("when was this built").
    The hash lets an operator tell, without diffing snapshot contents, whether two builds
    came from byte-identical source data. Hashing (not just timestamping) also means a
    caller who deliberately wants a stable id for the same bytes can still get one via the
    explicit `version=` parameter on `build_snapshot`.
    """
    hasher = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    short_hash = hasher.hexdigest()[:12]
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return f"{timestamp}-{short_hash}"


def build_snapshot(
    zip_path: str = DEFAULT_ARCHIVE_PATH,
    snapshots_dir: str = DEFAULT_SNAPSHOTS_DIR,
    version: Optional[str] = None,
) -> str:
    """Build a new, immutable, versioned snapshot from `zip_path` under `snapshots_dir` and
    return its version id. Does NOT change `CURRENT` -- see `publish_snapshot` for the
    build-then-publish entry point an offline build job should normally call.

    Raises `SnapshotValidationError` (without creating a versioned directory) if the build
    produces zero sentences -- publishing that would silently take the live service to zero
    results.
    """
    os.makedirs(snapshots_dir, exist_ok=True)
    index = CorpusIndex.build_from_zip(zip_path)
    if len(index) == 0:
        raise SnapshotValidationError(
            f"refusing to publish an empty snapshot built from {zip_path!r} (0 sentences)"
        )

    resolved_version = version or _make_version_id(zip_path)
    final_dir = _snapshot_dir(snapshots_dir, resolved_version)
    if os.path.isdir(final_dir):
        logger.info("Snapshot version already built; reusing: %s", resolved_version)
        return resolved_version

    # Build into a uniquely-named temp directory alongside the final versioned directories,
    # then rename it into place in one step, so a reader listing/loading `snapshots_dir`
    # never observes a partially-written snapshot.
    tmp_dir = tempfile.mkdtemp(prefix=f".build-{resolved_version}-", dir=snapshots_dir)
    try:
        save_index(index, os.path.join(tmp_dir, SNAPSHOT_INDEX_FILENAME))
        os.rename(tmp_dir, final_dir)
    except FileExistsError:
        # Another process published the same version concurrently -- its build is just as
        # valid as ours; discard our copy rather than crash.
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except BaseException:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    logger.info("Snapshot built: version=%s sentences=%d", resolved_version, len(index))
    return resolved_version


def set_current_version(snapshots_dir: str, version: str) -> None:
    """Atomically point `CURRENT` at `version`.

    Writes the version id to a temp file in `snapshots_dir` (same filesystem as the
    pointer), flushes and fsyncs it, then `os.replace`s it over the pointer file.
    `os.replace` is POSIX `rename(2)` under the hood, which is atomic within one
    filesystem -- a concurrent reader of `CURRENT` always sees a complete version id, never
    a truncated or half-written one.
    """
    final_dir = _snapshot_dir(snapshots_dir, version)
    if not os.path.isdir(final_dir):
        raise FileNotFoundError(f"no such snapshot version under {snapshots_dir!r}: {version!r}")

    pointer = _pointer_path(snapshots_dir)
    fd, tmp_path = tempfile.mkstemp(prefix=".CURRENT-", dir=snapshots_dir)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(version)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, pointer)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
    logger.info("CURRENT snapshot pointer set: %s -> %s", snapshots_dir, version)


def get_current_version(snapshots_dir: str) -> Optional[str]:
    """The currently-published snapshot version id, or None if nothing has been published
    yet under `snapshots_dir` (including when `snapshots_dir` itself does not exist)."""
    try:
        with open(_pointer_path(snapshots_dir), "r") as f:
            return f.read().strip() or None
    except FileNotFoundError:
        return None


def load_snapshot(snapshots_dir: str, version: str) -> CorpusIndex:
    """Load the `CorpusIndex` for one specific, already-built snapshot version."""
    return load_index(os.path.join(_snapshot_dir(snapshots_dir, version), SNAPSHOT_INDEX_FILENAME))


def list_snapshot_versions(snapshots_dir: str) -> List[str]:
    """All fully-built snapshot version ids under `snapshots_dir`, oldest first.

    Version ids are timestamp-prefixed by default, so lexical sort is also chronological
    sort. Skips the `CURRENT` pointer file, any in-progress `.build-*` temp directory, and
    any directory that doesn't (yet) contain a finished `corpus_index.pickle`.
    """
    if not os.path.isdir(snapshots_dir):
        return []
    return sorted(
        name
        for name in os.listdir(snapshots_dir)
        if name != POINTER_FILENAME
        and not name.startswith(".")
        and os.path.isfile(os.path.join(snapshots_dir, name, SNAPSHOT_INDEX_FILENAME))
    )


def publish_snapshot(
    zip_path: str = DEFAULT_ARCHIVE_PATH, snapshots_dir: str = DEFAULT_SNAPSHOTS_DIR
) -> str:
    """Build a new versioned snapshot from `zip_path`, validate it, and only then flip
    `CURRENT` to it. This is the entry point an offline build job (e.g. one adding a new
    data source) should call -- a running service polling this `snapshots_dir` (see
    `matching.completions.HotReloadableIndex`) picks up the change live, no restart.
    """
    version = build_snapshot(zip_path=zip_path, snapshots_dir=snapshots_dir)
    set_current_version(snapshots_dir, version)
    return version
