from init_offline.text_utils import normalize, trigrams


def test_lowercases():
    assert normalize("To Be") == "to be"


def test_strips_punctuation():
    assert normalize("be, that") == "be that"


def test_collapses_whitespace_runs():
    assert normalize("to be        zat") == "to be zat"


def test_strips_leading_trailing_whitespace():
    assert normalize("  to be  ") == "to be"


def test_equivalent_inputs_normalize_identically():
    variants = ["to be zat,", "to be, zat", "to be              zat"]
    normalized = {normalize(v) for v in variants}
    assert len(normalized) == 1


def test_trigrams_basic():
    assert list(trigrams("to be")) == ["to ", "o b", " be"]


def test_trigrams_too_short_yields_nothing():
    assert list(trigrams("to")) == []
    assert list(trigrams("")) == []


def test_trigrams_exact_length_three_yields_one():
    assert list(trigrams("cat")) == ["cat"]


def test_single_edit_corrupts_at_most_three_trigrams():
    # "asymmetric" vs "asvmmetric" (one substitution at index 2: y -> v)
    original = trigrams("asymmetric")
    edited = trigrams("asvmmetric")
    shared = set(original) & set(edited)
    total_trigrams = len("asymmetric") - 2
    # at least (total - 3) trigrams must survive a single edit unchanged
    assert len(shared) >= total_trigrams - 3
