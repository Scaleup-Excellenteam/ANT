"""Reads the corpus (Archive.zip) and yields one raw line per non-empty line.

Edge-case decisions made here (per SPEC_MEMBER_1_INIT.md "Detailed Requirements"):
    - Empty lines are SKIPPED (not stored). An empty line can never usefully match any
      non-empty typed query under the assignment's substring rule.
    - Directory entries inside the zip are skipped.
    - Decoding: try UTF-8 first; fall back to latin-1 (which never raises) for any file with
      non-UTF-8 bytes, so an odd byte in one corpus file never crashes the whole build.
    - Duplicate sentences (identical text in multiple files, or repeated in one file) are NOT
      de-duplicated here -- each occurrence gets its own record with its own source/offset.
"""

import logging
import zipfile
from typing import Iterator

from .models import RawLine

logger = logging.getLogger("corpus")


def iter_corpus_lines(zip_path: str) -> Iterator[RawLine]:
    """Walk every .txt file in `zip_path` (at any folder depth) and yield one RawLine per
    non-empty line, in file order, with 0-based line offsets.
    """
    logger.info("Opening corpus archive: %s", zip_path)
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
                logger.warning("UTF-8 decode failed; using latin-1 for %s", info.filename)
                text = raw_bytes.decode("latin-1")

            for offset, line in enumerate(text.splitlines()):
                if line.strip() == "":
                    continue
                yield RawLine(
                    original_text=line,
                    source_path=info.filename,
                    offset=offset,
                )
