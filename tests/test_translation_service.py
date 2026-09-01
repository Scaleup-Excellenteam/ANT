import pytest

from src.translation import GoogleTranslationService, TranslationError

HEBREW_HELLO = "\u05e9\u05dc\u05d5\u05dd"
HEBREW_PYTHON_FUNCTION = (
    "\u05e4\u05d5\u05e0\u05e7\u05e6\u05d9\u05d9\u05ea "
    "\u05e4\u05d9\u05d9\u05ea\u05d5\u05df"
)


class FakeTranslation:
    def __init__(self, translated_text, detected_language_code="he"):
        self.translated_text = translated_text
        self.detected_language_code = detected_language_code


class FakeResponse:
    def __init__(self, translations):
        self.translations = translations


class FakeGoogleClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def translate_text(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def service_with_client(client):
    service = GoogleTranslationService(project_id="test-project", timeout_seconds=2.5)
    service._client = client
    return service


def test_google_service_sends_auto_detect_english_request():
    client = FakeGoogleClient(
        response=FakeResponse([FakeTranslation("python function", "he")])
    )
    service = service_with_client(client)

    result = service.translate_to_english(HEBREW_PYTHON_FUNCTION)

    assert result.original_text == HEBREW_PYTHON_FUNCTION
    assert result.translated_text == "python function"
    assert result.detected_source_language == "he"

    request = client.calls[0]["request"]
    assert request["parent"] == "projects/test-project/locations/global"
    assert request["contents"] == [HEBREW_PYTHON_FUNCTION]
    assert request["mime_type"] == "text/plain"
    assert request["target_language_code"] == "en"
    assert "source_language_code" not in request
    assert client.calls[0]["timeout"] == 2.5


def test_google_service_requires_project_id(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    service = GoogleTranslationService(project_id=None)

    with pytest.raises(TranslationError, match="GOOGLE_CLOUD_PROJECT"):
        service.translate_to_english(HEBREW_HELLO)


def test_google_service_wraps_timeout_or_api_failure():
    service = service_with_client(FakeGoogleClient(error=TimeoutError("timed out")))

    with pytest.raises(TranslationError, match="request failed"):
        service.translate_to_english(HEBREW_HELLO)


def test_google_service_rejects_malformed_response_without_translations():
    service = service_with_client(FakeGoogleClient(response=object()))

    with pytest.raises(TranslationError, match="returned no translations"):
        service.translate_to_english(HEBREW_HELLO)


def test_google_service_rejects_empty_translation():
    client = FakeGoogleClient(response=FakeResponse([FakeTranslation("   ")]))
    service = service_with_client(client)

    with pytest.raises(TranslationError, match="empty translation"):
        service.translate_to_english(HEBREW_HELLO)


def test_google_service_rejects_empty_input():
    service = service_with_client(FakeGoogleClient())

    with pytest.raises(TranslationError, match="input is empty"):
        service.translate_to_english("   ")
