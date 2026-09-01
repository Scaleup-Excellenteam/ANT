import pytest

from src.auto_complete_data import AutoCompleteData
from src.contextual import ContextualResult, GeneratedSuggestion
from src.protobuf_api import autocomplete_pb2
from src.protobuf_api.service import (
    decode_search_request,
    decode_search_response,
    encode_search_request,
    handle_serialized_request,
)


class FakeGenerator:
    def generate(self, prefix, context, count=5):
        assert prefix == "Thank you for"
        assert context == "professional email"
        assert count == 2
        return ContextualResult(
            suggestions=(
                GeneratedSuggestion(
                    text="Thank you for reviewing the proposal.",
                    model="fake-gemini",
                ),
            ),
            model="fake-gemini",
            latency_ms=7,
        )


def test_search_request_binary_round_trip():
    payload = encode_search_request(
        query="to be",
        mode="corpus",
        max_results=3,
    )

    assert isinstance(payload, bytes)
    assert payload != b"to be"
    request = decode_search_request(payload)
    assert request.query == "to be"
    assert request.mode == autocomplete_pb2.SEARCH_MODE_CORPUS
    assert request.max_results == 3


def test_corpus_request_uses_existing_search_and_preserves_metadata():
    def corpus_search(query):
        assert query == "to be"
        return [
            AutoCompleteData("to be continued", "example.txt", 42, 10),
            AutoCompleteData("to be precise", "second.txt", 9, 8),
        ]

    request_bytes = encode_search_request("to be", max_results=1)
    response_bytes = handle_serialized_request(request_bytes, corpus_search)
    response = decode_search_response(response_bytes)

    assert response.error == ""
    assert response.request.query == "to be"
    assert len(response.suggestions) == 1
    suggestion = response.suggestions[0]
    assert suggestion.text == "to be continued"
    assert suggestion.WhichOneof("origin") == "corpus"
    assert suggestion.corpus.source_text == "example.txt"
    assert suggestion.corpus.offset == 42
    assert suggestion.corpus.score == 10


def test_ai_request_uses_existing_generator_and_preserves_model():
    request_bytes = encode_search_request(
        "Thank you for",
        mode="ai",
        context="professional email",
        max_results=2,
    )
    response_bytes = handle_serialized_request(
        request_bytes,
        corpus_search=lambda _query: [],
        contextual_generator=FakeGenerator(),
    )
    response = decode_search_response(response_bytes)

    assert response.error == ""
    assert len(response.suggestions) == 1
    suggestion = response.suggestions[0]
    assert suggestion.WhichOneof("origin") == "ai"
    assert suggestion.ai.model == "fake-gemini"


def test_malformed_request_returns_a_decodable_error_response():
    response_bytes = handle_serialized_request(
        b"not-a-protobuf-request",
        corpus_search=lambda _query: [],
    )
    response = decode_search_response(response_bytes)

    assert response.error == "request is not valid Protobuf data"
    assert not response.suggestions


def test_invalid_request_is_rejected_before_serialization():
    with pytest.raises(ValueError, match="max_results"):
        encode_search_request("query", max_results=6)
