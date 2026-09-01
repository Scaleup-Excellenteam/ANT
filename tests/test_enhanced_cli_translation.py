from src.auto_complete_data import AutoCompleteData
from src.enhanced_cli import (
    CORPUS_MODE,
    TRANSLATION_MODE,
    SessionState,
    process_session_input,
    prompt_for,
    run_feature_cli,
)
from src.translation import TranslationError, TranslationResult

HEBREW_PYTHON_FUNCTION = "\u05e4\u05d5\u05e0\u05e7\u05e6\u05d9\u05d9\u05ea \u05e4\u05d9\u05d9\u05ea\u05d5\u05df"


class FakeTranslator:
    def __init__(self, translated_text="python function", error=None):
        self.translated_text = translated_text
        self.error = error
        self.calls = []

    def translate_to_english(self, text):
        self.calls.append(text)
        if self.error is not None:
            raise self.error
        return TranslationResult(
            original_text=text,
            translated_text=self.translated_text,
            detected_source_language="he",
        )


def translated_search(calls):
    def search(query):
        calls.append(query)
        return [AutoCompleteData("Python function docs", "python.txt", 3, 30)]

    return search


def test_translate_command_enters_combined_translation_mode_and_resets_query():
    state = SessionState(query="old query")

    result = process_session_input(state, "/translate", lambda _query: [], None)

    assert result.state.mode == TRANSLATION_MODE
    assert result.state.query == ""
    assert "target=English" in prompt_for(result.state)


def test_combined_translation_mode_translates_before_corpus_search():
    search_calls = []
    translator = FakeTranslator()

    result = process_session_input(
        SessionState(mode=TRANSLATION_MODE),
        HEBREW_PYTHON_FUNCTION,
        translated_search(search_calls),
        contextual_generator=None,
        translation_service=translator,
    )

    assert translator.calls == [HEBREW_PYTHON_FUNCTION]
    assert search_calls == ["python function"]
    assert "Translated English query: python function" in result.output
    assert "Python function docs" in result.output


def test_combined_translation_failure_keeps_query_and_does_not_search():
    search_calls = []
    translator = FakeTranslator(error=TranslationError("request timed out"))

    result = process_session_input(
        SessionState(mode=TRANSLATION_MODE),
        HEBREW_PYTHON_FUNCTION,
        translated_search(search_calls),
        contextual_generator=None,
        translation_service=translator,
    )

    assert result.state.query == HEBREW_PYTHON_FUNCTION
    assert "Translation failed: request timed out" in result.output
    assert search_calls == []


def test_english_command_returns_to_corpus_mode():
    state = SessionState(mode=TRANSLATION_MODE, query=HEBREW_PYTHON_FUNCTION)

    result = process_session_input(state, "/english", lambda _query: [], None)

    assert result.state.mode == CORPUS_MODE
    assert result.state.query == ""


def test_full_combined_translation_cli_flow(monkeypatch, capsys):
    inputs = iter(["/translate", HEBREW_PYTHON_FUNCTION, "~"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))

    run_feature_cli(
        translated_search([]),
        contextual_generator=None,
        translation_service=FakeTranslator(),
    )

    output = capsys.readouterr().out
    assert "Translation mode enabled" in output
    assert "Translated English query: python function" in output
    assert "Python function docs" in output
    assert "Goodbye." in output
