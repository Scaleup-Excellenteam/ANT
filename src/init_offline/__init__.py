"""Offline/init phase: corpus loading and search-structure building.

Owned by Member 1 (Init/Offline Builder) per SPEC_MEMBER_1_INIT.md.
Public API consumed by the Matching phase (Member 2) is re-exported here.
See README.md for the full hand-off contract.
"""

from .corpus_index import (
    CorpusIndex,
    load_index,
    load_or_build_index,
    save_index,
)
from .models import RawLine, SentenceRecord
from .snapshot_store import (
    DEFAULT_SNAPSHOTS_DIR,
    SnapshotValidationError,
    build_snapshot,
    get_current_version,
    list_snapshot_versions,
    load_snapshot,
    publish_snapshot,
    set_current_version,
)
from .text_utils import normalize, trigrams
from .trigram_index import TrigramIndex
from .vocabulary_trie import VocabularyTrie
from .word_index import WordInvertedIndex

__all__ = [
    "CorpusIndex",
    "load_index",
    "load_or_build_index",
    "save_index",
    "RawLine",
    "SentenceRecord",
    "normalize",
    "trigrams",
    "TrigramIndex",
    "VocabularyTrie",
    "WordInvertedIndex",
    # ZDT: versioned snapshot store (see snapshot_store.py)
    "DEFAULT_SNAPSHOTS_DIR",
    "SnapshotValidationError",
    "build_snapshot",
    "get_current_version",
    "list_snapshot_versions",
    "load_snapshot",
    "publish_snapshot",
    "set_current_version",
]
