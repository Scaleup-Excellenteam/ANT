from init_offline.models import SentenceRecord
from init_offline.text_utils import normalize
from init_offline.word_index import WordInvertedIndex


def make_sentence(sentence_id, text):
    return SentenceRecord(
        sentence_id=sentence_id,
        original_text=text,
        normalized_text=normalize(text),
        source_path="example.txt",
        offset=sentence_id,
    )


def test_finds_sentences_containing_a_word():
    sentences = [
        make_sentence(0, "this is a demo."),
        make_sentence(1, "this is a test."),
        make_sentence(2, "completely unrelated line"),
    ]
    index = WordInvertedIndex()
    index.build(sentences)

    assert index.candidates("this") == [0, 1]
    assert index.candidates("demo") == [0]
    assert index.candidates("test") == [1]


def test_unknown_word_returns_empty_list():
    index = WordInvertedIndex()
    index.build([make_sentence(0, "hello world")])

    assert index.candidates("nonexistent") == []


def test_vocabulary_contains_every_distinct_word():
    index = WordInvertedIndex()
    index.build([make_sentence(0, "to be or not to be")])

    assert set(index.vocabulary()) == {"to", "be", "or", "not"}


def test_does_not_find_mid_word_matches():
    # "symmetric" only appears mid-word inside "asymmetric" -- the word index has no way to
    # find this (that's exactly why trigram_index.py exists as a backstop).
    index = WordInvertedIndex()
    index.build([make_sentence(0, "asymmetric issues were found")])

    assert index.candidates("symmetric") == []
