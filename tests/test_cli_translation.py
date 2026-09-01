from src.auto_complete_data import AutoCompleteData
from src.cli import (
    ENGLISH_COMMAND,
    ENGLISH_MODE_ENABLED,
    NO_MATCHES,
    TRANSLATE_COMMAND,
    TRANSLATED_QUERY_PREFIX,
    TRANSLATION_MODE_ENABLED,
    TRANSLATION_UNAVAILABLE,
    process_input,
    process_input_with_mode,
)
from src.translation import TranslationError, TranslationResult

HEBREW_HELLO = "\u05e9\u05dc\u05d5\u05dd"
HEBREW_PYTHON_FUNCTION = (
    "\u05e4\u05d5\u05e0\u05e7\u05e6\u05d9\u05d9\u05ea "
    "\u05e4\u05d9\u05d9\u05ea\u05d5\u05df"
)
ARABIC_DATA_STRUCTURE = "\u0647\u064a\u0643\u0644 \u0628\u064a\u0627\u0646\u0627\u062a"
ARABIC_MISSING_PHRASE = (
    "\u0639\u0628\u0627\u0631\u0629 "
    "\u0645\u0641\u0642\u0648\u062f\u0629"
)


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
            detected_source_language="und",
        )


def one_result_search(calls):
    def search(prefix):
        calls.append(prefix)
        return [AutoCompleteData("Python function docs", "python.txt", 3, 30)]

    return search


def test_translate_command_enters_translation_mode_without_search():
    search_calls = []
    query, output, translation_mode = process_input_with_mode(
        current_query="",
        new_text=TRANSLATE_COMMAND,
        search_function=one_result_search(search_calls),
    )

    assert query == ""
    assert output == TRANSLATION_MODE_ENABLED
    assert translation_mode is True
    assert search_calls == []


def test_english_command_returns_to_normal_mode_without_search():
    search_calls = []
    query, output, translation_mode = process_input_with_mode(
        current_query=HEBREW_HELLO,
        new_text=ENGLISH_COMMAND,
        search_function=one_result_search(search_calls),
        translation_mode=True,
    )

    assert query == HEBREW_HELLO
    assert output == ENGLISH_MODE_ENABLED
    assert translation_mode is False
    assert search_calls == []


def test_hebrew_query_is_translated_then_searched():
    search_calls = []
    translator = FakeTranslator(translated_text="python function")

    query, output, translation_mode = process_input_with_mode(
        current_query="",
        new_text=HEBREW_PYTHON_FUNCTION,
        search_function=one_result_search(search_calls),
        translation_service=translator,
        translation_mode=True,
    )

    assert query == HEBREW_PYTHON_FUNCTION
    assert translation_mode is True
    assert translator.calls == [HEBREW_PYTHON_FUNCTION]
    assert search_calls == ["python function"]
    assert f"{TRANSLATED_QUERY_PREFIX} python function" in output
    assert "Python function docs" in output


def test_arabic_query_is_translated_then_searched():
    search_calls = []
    translator = FakeTranslator(translated_text="data structure")

    _, output, _ = process_input_with_mode(
        current_query="",
        new_text=ARABIC_DATA_STRUCTURE,
        search_function=one_result_search(search_calls),
        translation_service=translator,
        translation_mode=True,
    )

    assert translator.calls == [ARABIC_DATA_STRUCTURE]
    assert search_calls == ["data structure"]
    assert f"{TRANSLATED_QUERY_PREFIX} data structure" in output


def test_translation_failure_does_not_search_original_query():
    search_calls = []
    translator = FakeTranslator(error=TranslationError("request timed out"))

    query, output, translation_mode = process_input_with_mode(
        current_query="",
        new_text=HEBREW_HELLO,
        search_function=one_result_search(search_calls),
        translation_service=translator,
        translation_mode=True,
    )

    assert query == HEBREW_HELLO
    assert translation_mode is True
    assert "Translation failed: request timed out" in output
    assert search_calls == []


def test_translation_mode_without_service_does_not_search():
    search_calls = []

    _, output, translation_mode = process_input_with_mode(
        current_query="",
        new_text=HEBREW_HELLO,
        search_function=one_result_search(search_calls),
        translation_mode=True,
    )

    assert output == TRANSLATION_UNAVAILABLE
    assert translation_mode is True
    assert search_calls == []


def test_translation_mode_preserves_no_matches_message_after_successful_translation():
    translator = FakeTranslator(translated_text="missing phrase")

    _, output, _ = process_input_with_mode(
        current_query="",
        new_text=ARABIC_MISSING_PHRASE,
        search_function=lambda _prefix: [],
        translation_service=translator,
        translation_mode=True,
    )

    assert f"{TRANSLATED_QUERY_PREFIX} missing phrase" in output
    assert NO_MATCHES in output


def test_normal_english_process_input_remains_unchanged():
    called_with = []

    query, output = process_input("", "python", one_result_search(called_with))

    assert query == "python"
    assert called_with == ["python"]
    assert "Python function docs" in output
