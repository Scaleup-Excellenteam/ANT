"""Offline/init phase: corpus loading and search-structure building.

Owned by Member 1 (Init/Offline Builder) per SPEC_MEMBER_1_INIT.md.
Public API consumed by the Matching phase (Member 2) is re-exported here.
"""

from .models import SentenceRef
from .text_utils import normalize
from .trie import Trie, TrieNode
from .corpus_loader import iter_corpus_lines
from .build_index import build_trie_from_zip

__all__ = [
    "SentenceRef",
    "normalize",
    "Trie",
    "TrieNode",
    "iter_corpus_lines",
    "build_trie_from_zip",
]
