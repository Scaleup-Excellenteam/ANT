"""Shared data model for the Init/Offline phase.

Note: this is NOT the `AutoCompleteData` class from PROJECT_SPEC.md (that belongs to the
Matching phase, owned by Member 2). `SentenceRef` is the internal record the trie stores so
the Matching phase can build `AutoCompleteData` objects from it without re-reading corpus files.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SentenceRef:
    """A single corpus line (= "sentence" per the assignment's definition).

    Attributes:
        original_text: the line exactly as it appears in the source file, punctuation intact.
        source_path: path of the source file, relative to the corpus root (e.g.
            "python-3.8.4-docs-text/c-api/abstract.txt"), so output paths stay portable.
        offset: 0-based line number of this sentence within its source file.
    """

    original_text: str
    source_path: str
    offset: int
