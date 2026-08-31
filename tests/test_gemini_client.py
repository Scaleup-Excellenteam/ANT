import json
from urllib.error import URLError

import pytest

from src.contextual import (
    ContextualConfigurationError,
    ContextualServiceError,
    GeminiSuggestionClient,
    InvalidGeminiResponseError,
)


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, _limit):
        return self.payload


class FakeOpener:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        if self.error is not None:
            raise self.error
        return FakeHTTPResponse(self.payload)


def api_payload(suggestions):
    generated_json = json.dumps(suggestions)
    return json.dumps(
        {
            "candidates": [
                {"content": {"parts": [{"text": generated_json}]}}
            ]
        }
    ).encode("utf-8")


def test_generate_returns_validated_structured_suggestions():
    opener = FakeOpener(
        api_payload(
            [
                "We are building a secure search service.",
                "We are designing a reliable autocomplete system.",
            ]
        )
    )
    generator = GeminiSuggestionClient(
        api_key="test-key",
        opener=opener,
        model="test-gemini",
        timeout_seconds=12,
    )

    result = generator.generate("We are", "technical project update", count=2)

    assert [item.text for item in result.suggestions] == [
        "We are building a secure search service.",
        "We are designing a reliable autocomplete system.",
    ]
    assert all(item.model == "test-gemini" for item in result.suggestions)
    assert result.latency_ms >= 0

    request, timeout = opener.calls[0]
    assert timeout == 12
    assert request.method == "POST"
    assert request.get_header("X-goog-api-key") == "test-key"
    assert "test-gemini:generateContent" in request.full_url
    body = json.loads(request.data.decode("utf-8"))
    prompt = body["contents"][0]["parts"][0]["text"]
    assert "technical project update" in prompt
    config = body["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert config["responseJsonSchema"]["maxItems"] == 2


def test_generate_removes_duplicates_and_prefix_breaking_results():
    opener = FakeOpener(
        api_payload(["Hello world.", "hello WORLD.", "Not the prefix."])
    )
    generator = GeminiSuggestionClient(api_key="test-key", opener=opener)

    result = generator.generate("Hello", "friendly", count=5)

    assert [item.text for item in result.suggestions] == ["Hello world."]


def test_missing_api_key_is_a_clear_configuration_error():
    generator = GeminiSuggestionClient(environ={}, opener=FakeOpener())

    with pytest.raises(ContextualConfigurationError, match="GEMINI_API_KEY"):
        generator.generate("Hello", "friendly")


def test_network_failure_is_wrapped_without_leaking_details():
    opener = FakeOpener(error=URLError("secret transport detail"))
    generator = GeminiSuggestionClient(api_key="test-key", opener=opener)

    with pytest.raises(ContextualServiceError, match="unavailable or timed out") as exc_info:
        generator.generate("Hello", "friendly")

    assert "secret transport detail" not in str(exc_info.value)


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        json.dumps({"unexpected": []}).encode("utf-8"),
        api_payload("not-a-list"),
        api_payload(["Different prefix"]),
    ],
)
def test_invalid_responses_are_rejected(payload):
    generator = GeminiSuggestionClient(
        api_key="test-key", opener=FakeOpener(payload)
    )

    with pytest.raises(InvalidGeminiResponseError):
        generator.generate("Hello", "friendly")


def test_oversized_response_is_rejected():
    generator = GeminiSuggestionClient(
        api_key="test-key", opener=FakeOpener(b"x" * 1_000_001)
    )

    with pytest.raises(InvalidGeminiResponseError, match="oversized"):
        generator.generate("Hello", "friendly")


@pytest.mark.parametrize(
    "prefix,context,count",
    [
        ("", "friendly", 5),
        ("Hello", "", 5),
        ("Hello", "friendly", 0),
        ("Hello", "friendly", 6),
    ],
)
def test_invalid_requests_are_rejected_before_api_call(prefix, context, count):
    opener = FakeOpener()
    generator = GeminiSuggestionClient(api_key="test-key", opener=opener)

    with pytest.raises(ValueError):
        generator.generate(prefix, context, count)

    assert opener.calls == []
