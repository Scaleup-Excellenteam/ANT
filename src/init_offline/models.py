"""Shared data records for the Init/Offline phase.

`SentenceRecord` is NOT the `AutoCompleteData` class from PROJECT_SPEC.md (that belongs to the
Matching phase, owned by Member 2). It's the internal record Member 1's indexes point at, so
Member 2 can build `AutoCompleteData` objects straight from it without re-reading corpus files.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RawLine:
    """One corpus line exactly as read from disk, before normalization/ID assignment.

    Produced by `corpus_loader.iter_corpus_lines`; consumed only inside the build step
    (`corpus_index.CorpusIndex.build_from_zip`). Not part of the Member 2 hand-off contract.
    """

    original_text: str
    source_path: str
    offset: int


@dataclass(frozen=True)
class SentenceRecord:
    """A single corpus line ("sentence" per the assignment's definition), fully prepared.

    Attributes:
        sentence_id: dense 0-based index into `CorpusIndex.sentences` -- this is the value
            stored in every index's postings lists.
        original_text: the line exactly as it appears in the source file, punctuation intact.
            Use this for `AutoCompleteData.completed_sentence`.
        normalized_text: `original_text` run through `text_utils.normalize()` once, at build
            time. Member 2 should normalize the user's query with the SAME function and compare
            against this field -- never against `original_text` directly.
        source_path: path of the source file, relative to the corpus root.
        offset: 0-based line number of this sentence within its source file.
    """

    sentence_id: int
    original_text: str
    normalized_text: str
    source_path: str
    offset: int
