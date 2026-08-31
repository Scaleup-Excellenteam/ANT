from init_offline import normalize
from matching.candidates import generate_candidates


class TestShortQueryPath:
    """Normalized length <= 5 must use `index.short_query_candidates` (query lengths 1-5,
    per the handoff)."""

    def test_length_1_to_5_all_find_the_sentence(self, question_index):
        # Pre-normalized substrings of the official sentence, one per length 1-5, chosen
        # so none of them collapse via normalize()'s own strip() (e.g. a trailing space).
        for normalized in ["t", "to", "to ", "to b", "to be"]:
            assert 1 <= len(normalized) <= 5
            candidates = generate_candidates(question_index, normalized)
            assert 0 in candidates, f"expected sentence 0 as a candidate for {normalized!r}"

    def test_short_query_no_match_returns_empty_or_excludes_sentence(self, question_index):
        candidates = generate_candidates(question_index, normalize("zzzzz"))
        assert 0 not in candidates


class TestLongQueryPath:
    """Normalized length >= 6 must use word_candidates (+fuzzy fallback) unioned with
    trigram_candidates -- never trigram-only, never word-only."""

    def test_exact_words_found_via_word_candidates(self, question_index):
        normalized = normalize("be that")  # len 7
        assert len(normalized) >= 6
        candidates = generate_candidates(question_index, normalized)
        assert 0 in candidates

    def test_typo_in_anchor_word_falls_back_to_fuzzy_lookup(self, question_index):
        # "knot" is not vocabulary; fuzzy_vocabulary_lookup should surface "not".
        normalized = normalize("or knot")  # len 7
        assert len(normalized) >= 6
        candidates = generate_candidates(question_index, normalized)
        assert 0 in candidates

    def test_trigram_backstop_always_unioned(self, question_index, make_index):
        # A query whose words don't exist at all in the vocabulary (and have no fuzzy
        # match within 1 edit -- "metric" is 5 edits from the only real word,
        # "asymmetric"), but whose trigrams DO appear via mid-word overlap, must still be
        # found -- proving the trigram union isn't skipped just because the word path
        # returned nothing useful.
        index = make_index(["asymmetric warfare requires careful planning."])
        normalized = normalize("metric")  # len 6, hides entirely inside "asymmetric"
        assert len(normalized) >= 6
        candidates = generate_candidates(index, normalized)
        assert 0 in candidates


class TestEmptyQuery:
    def test_empty_normalized_query_returns_empty_set(self, question_index):
        assert generate_candidates(question_index, "") == set()
