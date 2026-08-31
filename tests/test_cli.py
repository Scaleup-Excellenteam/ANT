from src.auto_complete_data import AutoCompleteData
from src.cli import (
    EMPTY_INPUT,
    NO_MATCHES,
    format_suggestions,
    prepare_results,
    process_input,
)


def fake_search(_prefix):
    return [
        AutoCompleteData("Beta sentence", "test.txt", 2, 10),
        AutoCompleteData("Alpha sentence", "test.txt", 1, 10),
    ]


def test_first_input_is_saved():
    query, _ = process_input("", "python", fake_search)
    assert query == "python"


def test_query_continues_after_suggestions():
    query, _ = process_input("python", " programming", fake_search)
    assert query == "python programming"


def test_hash_resets_query():
    query, output = process_input("python programming", "#", fake_search)
    assert query == ""
    assert "reset" in output.lower()


def test_hash_at_end_resets_query():
    query, _ = process_input("python", " programming#", fake_search)
    assert query == ""


def test_empty_input_is_handled_without_search():
    called = False

    def should_not_run(_prefix):
        nonlocal called
        called = True
        return []

    query, output = process_input("", "", should_not_run)
    assert query == ""
    assert output == EMPTY_INPUT
    assert called is False


def test_zero_matches_is_handled():
    _, output = process_input("", "nothing", lambda _prefix: [])
    assert output == NO_MATCHES


def test_fewer_than_five_results_are_displayed():
    results = [AutoCompleteData("Only one", "one.txt", 7, 8)]
    output = format_suggestions(results)
    assert "Here are 1 suggestions:" in output
    assert "Only one" in output


def test_alphabetical_tie_break():
    ordered = prepare_results(fake_search("anything"))
    assert [item.completed_sentence for item in ordered] == [
        "Alpha sentence",
        "Beta sentence",
    ]


def test_score_is_primary_sort_key():
    results = [
        AutoCompleteData("Alpha", "a.txt", 1, 5),
        AutoCompleteData("Zulu", "z.txt", 2, 20),
    ]
    ordered = prepare_results(results)
    assert ordered[0].completed_sentence == "Zulu"


def test_only_top_five_are_kept():
    results = [
        AutoCompleteData(f"Sentence {i}", "test.txt", i, 100 - i)
        for i in range(8)
    ]
    assert len(prepare_results(results)) == 5


def test_output_contains_all_required_fields():
    result = AutoCompleteData(
        completed_sentence="Python is great.",
        source_text="python.txt",
        offset=42,
        score=20,
    )
    output = format_suggestions([result])

    assert "1." in output
    assert "Python is great." in output
    assert "python.txt" in output
    assert "42" in output
    assert "20" in output


def test_output_removes_leading_whitespace_from_sentence():
    result = AutoCompleteData(
        completed_sentence="\t    Indented sentence.",
        source_text="indented.txt",
        offset=3,
        score=12,
    )

    output = format_suggestions([result])

    assert "1. Indented sentence." in output
    assert "1. \t" not in output
