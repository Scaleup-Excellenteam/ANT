"""Operator entry point for the offline half of ZDT (Zero DownTime): build a new versioned
corpus snapshot from a data source and publish it so an already-running service picks it up
live, no restart. See `snapshot_store.py` and the top-level README's
"Zero-downtime snapshot publishing" section for the full offline -> filesystem -> online
hand-off.

Publish a new data source:
    python -m src.init_offline.build_snapshot_cli --zip resources/Archive.zip

Publish from a data source into a shared/remote snapshots directory a running service
elsewhere is watching (this module only needs ordinary filesystem access to that path --
local disk, NFS, a synced cloud-storage mount, etc.):
    python -m src.init_offline.build_snapshot_cli \\
        --zip /path/to/new_source.zip --snapshots-dir /srv/shared/corpus_snapshots

List built versions (marks the one currently live):
    python -m src.init_offline.build_snapshot_cli --list

Roll back to a previously built version without rebuilding it:
    python -m src.init_offline.build_snapshot_cli --rollback 20260101T000000Z-3f9a2b1c8e4d
"""

import argparse
from typing import Optional, Sequence

try:
    from .corpus_index import DEFAULT_ARCHIVE_PATH
    from .snapshot_store import (
        DEFAULT_SNAPSHOTS_DIR,
        SnapshotValidationError,
        get_current_version,
        list_snapshot_versions,
        publish_snapshot,
        set_current_version,
    )
except ImportError:  # Supports direct execution from the src directory.
    from corpus_index import DEFAULT_ARCHIVE_PATH
    from snapshot_store import (
        DEFAULT_SNAPSHOTS_DIR,
        SnapshotValidationError,
        get_current_version,
        list_snapshot_versions,
        publish_snapshot,
        set_current_version,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build and publish a new ZDT corpus snapshot, or manage existing ones."
    )
    parser.add_argument(
        "--zip", default=DEFAULT_ARCHIVE_PATH, help="Corpus zip to build the new snapshot from."
    )
    parser.add_argument(
        "--snapshots-dir",
        default=DEFAULT_SNAPSHOTS_DIR,
        help="Directory the online service polls for the live snapshot (local or shared/remote).",
    )
    parser.add_argument(
        "--list", action="store_true", help="List built snapshot versions and exit."
    )
    parser.add_argument(
        "--rollback",
        metavar="VERSION",
        default=None,
        help="Point CURRENT back at an already-built version (no rebuild) and exit.",
    )
    args = parser.parse_args(argv)

    if args.list:
        current = get_current_version(args.snapshots_dir)
        versions = list_snapshot_versions(args.snapshots_dir)
        if not versions:
            print(f"No snapshots built yet under {args.snapshots_dir}")
            return 0
        for version in versions:
            marker = " (current)" if version == current else ""
            print(f"{version}{marker}")
        return 0

    if args.rollback:
        try:
            set_current_version(args.snapshots_dir, args.rollback)
        except FileNotFoundError as exc:
            print(f"Rollback failed: {exc}")
            return 1
        print(f"CURRENT snapshot rolled back to: {args.rollback}")
        return 0

    try:
        version = publish_snapshot(zip_path=args.zip, snapshots_dir=args.snapshots_dir)
    except SnapshotValidationError as exc:
        print(f"Snapshot build failed validation; CURRENT was not changed: {exc}")
        return 1

    print(f"Published snapshot version={version} at {args.snapshots_dir}")
    print("A running service polling this snapshots_dir will pick it up live, no restart needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
