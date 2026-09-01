"""Adapters between Protobuf wire messages and the existing search components.

This module deliberately accepts and returns bytes. A caller can carry those bytes
over a file, queue, socket, HTTP, or gRPC, but transport is outside this interface.
"""

import time
from typing import Callable, List, Optional, Protocol

from google.protobuf.message import DecodeError

from . import autocomplete_pb2

try:
    from ..auto_complete_data import AutoCompleteData
    from ..cli import prepare_results
    from ..contextual import ContextualCompletionError, ContextualResult
    from ..enhanced_cli import DEFAULT_CONTEXT
except ImportError:  # Supports direct execution from the src directory.
    from auto_complete_data import AutoCompleteData
    from cli import prepare_results
    from contextual import ContextualCompletionError, ContextualResult
    from enhanced_cli import DEFAULT_CONTEXT

MAX_RESULTS = 5
CorpusSearch = Callable[[str], List[AutoCompleteData]]


class ContextualGenerator(Protocol):
    def generate(self, prefix: str, context: str, count: int = 5) -> ContextualResult:
        ...


def encode_search_request(
    query: str,
    mode: str = "corpus",
    context: str = "",
    max_results: int = MAX_RESULTS,
) -> bytes:
    """Build and serialize a request for use by another component or client."""
    mode_value = {
        "corpus": autocomplete_pb2.SEARCH_MODE_CORPUS,
        "ai": autocomplete_pb2.SEARCH_MODE_AI,
    }.get(mode.lower())
    if mode_value is None:
        raise ValueError("mode must be 'corpus' or 'ai'")

    request = autocomplete_pb2.SearchRequest(
        query=query,
        mode=mode_value,
        context=context,
        max_results=max_results,
    )
    _validate_request(request)
    return request.SerializeToString()


def decode_search_request(payload: bytes) -> autocomplete_pb2.SearchRequest:
    """Parse and validate a serialized request."""
    request = autocomplete_pb2.SearchRequest()
    try:
        request.ParseFromString(payload)
    except DecodeError as exc:
        raise ValueError("request is not valid Protobuf data") from exc
    _validate_request(request)
    return request


def decode_search_response(payload: bytes) -> autocomplete_pb2.SearchResponse:
    """Parse a serialized response for a client."""
    response = autocomplete_pb2.SearchResponse()
    try:
        response.ParseFromString(payload)
    except DecodeError as exc:
        raise ValueError("response is not valid Protobuf data") from exc
    return response


def handle_serialized_request(
    payload: bytes,
    corpus_search: CorpusSearch,
    contextual_generator: Optional[ContextualGenerator] = None,
) -> bytes:
    """Deserialize a request, run the selected component, and serialize a response."""
    response = autocomplete_pb2.SearchResponse()
    started = time.perf_counter()

    try:
        request = decode_search_request(payload)
        response.request.CopyFrom(request)
        limit = request.max_results or MAX_RESULTS

        if request.mode == autocomplete_pb2.SEARCH_MODE_CORPUS:
            results = prepare_results(corpus_search(request.query))[:limit]
            for result in results:
                suggestion = response.suggestions.add(text=result.completed_sentence)
                suggestion.corpus.source_text = result.source_text
                suggestion.corpus.offset = result.offset
                suggestion.corpus.score = result.score
        else:
            if contextual_generator is None:
                raise ValueError("AI mode requires a contextual generator")
            result = contextual_generator.generate(
                prefix=request.query,
                context=request.context.strip() or DEFAULT_CONTEXT,
                count=limit,
            )
            for generated in result.suggestions[:limit]:
                suggestion = response.suggestions.add(text=generated.text)
                suggestion.ai.model = generated.model
    except (ValueError, ContextualCompletionError, OSError) as exc:
        response.error = str(exc)

    response.latency_ms = round((time.perf_counter() - started) * 1000)
    return response.SerializeToString()


def _validate_request(request: autocomplete_pb2.SearchRequest) -> None:
    if not request.query.strip():
        raise ValueError("query must not be empty")
    if request.mode not in (
        autocomplete_pb2.SEARCH_MODE_CORPUS,
        autocomplete_pb2.SEARCH_MODE_AI,
    ):
        raise ValueError("request mode must be CORPUS or AI")
    if request.max_results > MAX_RESULTS:
        raise ValueError(f"max_results must be between 0 and {MAX_RESULTS}")
