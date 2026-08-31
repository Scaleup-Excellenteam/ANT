from init_offline.models import SentenceRef
from init_offline.text_utils import normalize
from init_offline.trie import Trie


def make_ref(text, source="example.txt", offset=0):
    return SentenceRef(original_text=text, source_path=source, offset=offset)


def test_exact_full_sentence_is_walkable_from_root():
    trie = Trie()
    ref = make_ref("To be or not to be, that is the question.")
    trie.insert_sentence(normalize(ref.original_text), ref)

    node = trie.walk_exact(normalize("to be or not to be"))
    assert node is not None
    refs = trie.collect_sentence_refs(node)
    assert ref in refs


def test_substring_starting_mid_sentence_is_walkable():
    trie = Trie()
    ref = make_ref("To be or not to be, that is the question.")
    trie.insert_sentence(normalize(ref.original_text), ref)

    # "or not" starts at a word boundary in the middle of the sentence.
    node = trie.walk_exact(normalize("or not"))
    assert node is not None
    refs = trie.collect_sentence_refs(node)
    assert ref in refs


def test_substring_not_starting_at_word_boundary_is_not_walkable():
    trie = Trie()
    ref = make_ref("To be or not to be, that is the question.")
    trie.insert_sentence(normalize(ref.original_text), ref)

    # "e or not" starts mid-word ("b|e or not"), so it was never inserted as its own path --
    # exact-walk from root must fail. (Character-level typo tolerance is Member 2's job, not
    # tested here.)
    node = trie.walk_exact(normalize("e or not"))
    assert node is None


def test_collect_sentence_refs_finds_multiple_sentences_sharing_a_prefix():
    trie = Trie()
    ref_a = make_ref("this is a demo.", source="a.txt", offset=0)
    ref_b = make_ref("this is a test.", source="b.txt", offset=1)
    trie.insert_sentence(normalize(ref_a.original_text), ref_a)
    trie.insert_sentence(normalize(ref_b.original_text), ref_b)

    node = trie.walk_exact(normalize("this is a"))
    assert node is not None
    refs = trie.collect_sentence_refs(node)
    assert ref_a in refs and ref_b in refs


def test_empty_normalized_text_is_not_inserted():
    trie = Trie()
    ref = make_ref("   ")  # normalizes to ""
    trie.insert_sentence(normalize(ref.original_text), ref)

    assert trie.root.children == {}


def test_duplicate_sentences_are_kept_as_separate_refs():
    trie = Trie()
    ref_1 = make_ref("hello world", source="a.txt", offset=0)
    ref_2 = make_ref("hello world", source="b.txt", offset=5)
    trie.insert_sentence(normalize(ref_1.original_text), ref_1)
    trie.insert_sentence(normalize(ref_2.original_text), ref_2)

    node = trie.walk_exact(normalize("hello world"))
    refs = trie.collect_sentence_refs(node)
    assert ref_1 in refs
    assert ref_2 in refs
    assert len(refs) == 2
