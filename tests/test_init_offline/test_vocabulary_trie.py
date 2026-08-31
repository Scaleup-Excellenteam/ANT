from init_offline.vocabulary_trie import VocabularyTrie


def build_trie(words):
    trie = VocabularyTrie()
    trie.build(words)
    return trie


def test_contains_exact_words():
    trie = build_trie(["python", "java", "rust"])
    assert trie.contains("python")
    assert not trie.contains("pythom")


def test_len_reports_vocabulary_size():
    trie = build_trie(["a", "b", "c"])
    assert len(trie) == 3


def test_fuzzy_lookup_finds_exact_match():
    trie = build_trie(["python", "java"])
    assert trie.fuzzy_lookup("python", max_edits=1) == ["python"]


def test_fuzzy_lookup_finds_single_substitution():
    trie = build_trie(["python", "java", "rust"])
    # 'pythxn' is 'python' with the 5th character substituted (o -> x).
    assert "python" in trie.fuzzy_lookup("pythxn", max_edits=1)


def test_fuzzy_lookup_finds_single_insertion_in_query():
    # query has an extra character the vocab word doesn't -- "pythonn" -> "python"
    trie = build_trie(["python"])
    assert "python" in trie.fuzzy_lookup("pythonn", max_edits=1)


def test_fuzzy_lookup_finds_single_deletion_in_query():
    # query is missing a character the vocab word has -- "pyton" -> "python"
    trie = build_trie(["python"])
    assert "python" in trie.fuzzy_lookup("pyton", max_edits=1)


def test_fuzzy_lookup_excludes_words_needing_two_edits():
    trie = build_trie(["python"])
    assert "python" not in trie.fuzzy_lookup("pyxyn", max_edits=1)


def test_words_containing_substring_finds_mid_word_matches():
    trie = build_trie(["asymmetric", "symmetry", "unrelated"])
    matches = trie.words_containing_substring("symmetric")
    assert matches == ["asymmetric"]


def test_words_containing_substring_empty_string_returns_all():
    trie = build_trie(["a", "b"])
    assert set(trie.words_containing_substring("")) == {"a", "b"}
