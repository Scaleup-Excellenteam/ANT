"""Fixtures shared by the Member 2 test suite: build small synthetic `CorpusIndex` instances
using only Member 1's public constructor/build API (`CorpusIndex()`, `.sentences`,
`.word_index.build`, `.trigram_index.build`, `.vocabulary.build`) -- never a real
Archive.zip build, so tests stay fast (PROJECT_SPEC.md section 10 / handoff instructions).
"""

import pytest

from init_offline import CorpusIndex, SentenceRecord, normalize


def build_index(lines):
    """Build a `CorpusIndex` directly from a list of raw (non-normalized) sentence strings,
    one sentence_id per line, in order. Mirrors what `CorpusIndex.build_from_zip` does
    internally, minus the zip/file-walking step.
    """
    index = CorpusIndex()
    for sentence_id, line in enumerate(lines):
        index.sentences.append(
            SentenceRecord(
                sentence_id=sentence_id,
                original_text=line,
                normalized_text=normalize(line),
                source_path="synthetic.txt",
                offset=sentence_id,
            )
        )
    index.word_index.build(index.sentences)
    index.trigram_index.build(index.sentences)
    index.vocabulary.build(index.word_index.vocabulary())
    return index


@pytest.fixture
def make_index():
    return build_index


OFFICIAL_SENTENCE = "To be or not to be, that is the question."


@pytest.fixture
def question_index(make_index):
    """The single official test sentence from PROJECT_SPEC.md section 6.3, as the only
    sentence in the corpus -- used by the official scoring-table tests.
    """
    return make_index([OFFICIAL_SENTENCE])
