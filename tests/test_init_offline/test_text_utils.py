from init_offline.text_utils import normalize


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
