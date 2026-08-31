from init_offline.models import SentenceRecord
from init_offline.text_utils import normalize
from init_offline.trigram_index import TrigramIndex


def make_sentence(sentence_id, text):
    return SentenceRecord(
        sentence_id=sentence_id,
        original_text=text,
        normalized_text=normalize(text),
        source_path="example.txt",
        offset=sentence_id,
    )


def test_finds_exact_substring_candidates():
    index = TrigramIndex()
    index.build([make_sentence(0, "to be or not to be, that is the question.")])

    candidates = index.candidates_for_text(normalize("or not"))
    assert 0 in candidates


def test_finds_mid_word_substring_that_word_index_would_miss():
    # This is the core correctness case a word-level inverted index cannot solve on its own:
    # "symmetric" is only ever a substring of "asymmetric", never a standalone word.
    index = TrigramIndex()
    index.build([make_sentence(0, "asymmetric issues were found")])

    candidates = index.candidates_for_text(normalize("symmetric"))
    assert 0 in candidates


def test_no_shared_trigrams_returns_no_candidates():
    index = TrigramIndex()
    index.build([make_sentence(0, "hello world")])

    candidates = index.candidates_for_text(normalize("zzz zzz zzz"))
    assert candidates == set()


def test_single_edit_still_finds_the_sentence_via_surviving_trigrams():
    index = TrigramIndex()
    index.build([make_sentence(0, "to be or not to be, that is the question.")])

    # "or knot" (extra k) -- one edit away from "or not"; a normal caller would only feed the
    # portion of the query it's testing, so we check a trigram present in both the true text
    # and the typo'd query survives.
    typo_query = normalize("or knot")
    candidates = index.candidates_for_text(typo_query)
    assert 0 in candidates


def test_empty_candidates_for_query_shorter_than_k():
    index = TrigramIndex()
    index.build([make_sentence(0, "hello world")])

    # length-2 query has zero trigrams -- caller must use the short-query fallback instead.
    assert index.candidates_for_text("he") == set()


def test_postings_size_reports_candidate_set_size():
    index = TrigramIndex()
    index.build(
        [
            make_sentence(0, "the cat sat"),
            make_sentence(1, "the dog ran"),
        ]
    )

    assert index.postings_size("the") == 2
    assert index.postings_size("xyz") == 0
