"""Reads the corpus (Archive.zip) and yields one record per non-empty line.

Edge-case decisions made here (per SPEC_MEMBER_1_INIT.md section "Detailed Requirements"):
    - Empty lines are SKIPPED (not stored as empty sentences). Rationale: an empty line can
      never usefully match any non-empty typed query under the assignment's substring rule,
      and storing it would only add dead trie branches.
    - Directory entries inside the zip are skipped.
    - Decoding: try UTF-8 first; if a file has any byte sequence that isn't valid UTF-8, fall
      back to latin-1 (which never raises, since every byte value is a valid latin-1 code
      point). This is a deliberate "never crash on odd bytes" choice for a corpus that is
      supposed to be plain English text; it is not a silent-failure clause -- corpus lines are
      still stored and searchable, just possibly with a few substituted characters for the
      rare non-UTF-8 file.
    - Duplicate sentences (identical text appearing in multiple files, or multiple times in one
      file) are NOT de-duplicated -- each occurrence is stored as its own SentenceRef with its
      own source_path/offset, since the assignment's output requires the source file and offset
      of the actual match, and collapsing duplicates would lose that information.
"""

import zipfile
from typing import Iterator

from .models import SentenceRef


def iter_corpus_lines(zip_path: str) -> Iterator[SentenceRef]:
    """Walk every .txt file in `zip_path` (at any folder depth) and yield one SentenceRef
    per non-empty line, in file order, with 0-based line offsets.
    """
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            if not info.filename.lower().endswith(".txt"):
                continue

            raw_bytes = archive.read(info)
            try:
                text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = raw_bytes.decode("latin-1")

            for offset, line in enumerate(text.splitlines()):
                if line.strip() == "":
                    continue
                yield SentenceRef(
                    original_text=line,
                    source_path=info.filename,
                    offset=offset,
                )
