import io
import zipfile

from init_offline.corpus_index import CorpusIndex, SHORT_QUERY_MAX_LENGTH
from init_offline.text_utils import normalize


def write_temp_zip(tmp_path, files):
    zip_path = tmp_path / "corpus.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    zip_path.write_bytes(buf.getvalue())
    return str(zip_path)


def test_build_from_zip_populates_all_structures(tmp_path):
    zip_path = write_temp_zip(
        tmp_path, {"a.txt": "to be or not to be, that is the question.\n"}
    )

    index = CorpusIndex.build_from_zip(zip_path)

    assert len(index.sentences) == 1
    assert index.sentences[0].original_text == "to be or not to be, that is the question."
    assert index.sentences[0].normalized_text == normalize(
        "to be or not to be, that is the question."
    )
    assert len(index.word_index) > 0
    assert len(index.trigram_index) > 0
    assert len(index.vocabulary) > 0


def test_get_sentence_returns_full_record(tmp_path):
    zip_path = write_temp_zip(tmp_path, {"a.txt": "hello world\n"})
    index = CorpusIndex.build_from_zip(zip_path)

    record = index.get_sentence(0)
    assert record.original_text == "hello world"
    assert record.source_path == "a.txt"
    assert record.offset == 0


def test_word_candidates_fast_path(tmp_path):
    zip_path = write_temp_zip(
        tmp_path,
        {
            "a.txt": "this is a demo.\n",
            "b.txt": "this is a test.\n",
        },
    )
    index = CorpusIndex.build_from_zip(zip_path)

    candidates = index.word_candidates("demo")
    assert candidates == [index.sentences[0].sentence_id]


def test_trigram_candidates_catches_mid_word_match_word_index_misses(tmp_path):
    zip_path = write_temp_zip(tmp_path, {"a.txt": "asymmetric issues were found\n"})
    index = CorpusIndex.build_from_zip(zip_path)

    # word_candidates cannot find this -- "symmetric" is never a standalone word.
    assert index.word_candidates("symmetric") == []
    # trigram_candidates can, because it doesn't care about word boundaries.
    assert 0 in index.trigram_candidates(normalize("symmetric"))


def test_short_query_candidates_finds_mid_word_match_below_guarantee_length(tmp_path):
    # length-5 query, below the length-6 trigram survival guarantee -- must go through
    # short_query_candidates, not trigram_candidates directly.
    zip_path = write_temp_zip(tmp_path, {"a.txt": "asymmetric issues were found\n"})
    index = CorpusIndex.build_from_zip(zip_path)

    query = normalize("mmetr")  # mid-word substring of "asymmetric", length 5
    assert len(query) <= SHORT_QUERY_MAX_LENGTH
    assert 0 in index.short_query_candidates(query)


def test_short_query_candidates_handles_length_below_trigram_minimum(tmp_path):
    # length-2 query can't form any trigram at all -- must still be found via the
    # vocabulary-substring fallback inside short_query_candidates.
    zip_path = write_temp_zip(tmp_path, {"a.txt": "python programming\n"})
    index = CorpusIndex.build_from_zip(zip_path)

    assert 0 in index.short_query_candidates("py")


def test_short_query_candidates_rejects_queries_above_the_length_cap(tmp_path):
    zip_path = write_temp_zip(tmp_path, {"a.txt": "hello world\n"})
    index = CorpusIndex.build_from_zip(zip_path)

    try:
        index.short_query_candidates("x" * (SHORT_QUERY_MAX_LENGTH + 1))
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for a query longer than the short-query cap")


def test_fuzzy_vocabulary_lookup_finds_typo_anchor_word(tmp_path):
    zip_path = write_temp_zip(tmp_path, {"a.txt": "python programming basics\n"})
    index = CorpusIndex.build_from_zip(zip_path)

    assert "python" in index.fuzzy_vocabulary_lookup("pythom", max_edits=1)


def test_duplicate_sentences_get_distinct_ids_and_offsets(tmp_path):
    zip_path = write_temp_zip(
        tmp_path,
        {
            "a.txt": "hello world\n",
            "b.txt": "unrelated line\nhello world\n",
        },
    )
    index = CorpusIndex.build_from_zip(zip_path)

    candidates = index.word_candidates("hello")
    assert len(candidates) == 2
    sources = {(index.get_sentence(sid).source_path, index.get_sentence(sid).offset)
               for sid in candidates}
    assert sources == {("a.txt", 0), ("b.txt", 1)}
