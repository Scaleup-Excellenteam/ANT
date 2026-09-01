"""Command-line Protobuf round-trip client for the autocomplete project."""

import argparse
from typing import Optional, Sequence

from . import autocomplete_pb2
from .service import (
    decode_search_request,
    decode_search_response,
    encode_search_request,
    handle_serialized_request,
)

try:
    from ..contextual import GeminiSuggestionClient
    from ..matching import get_best_k_completions
except ImportError:  # Supports direct execution from the src directory.
    from contextual import GeminiSuggestionClient
    from matching import get_best_k_completions


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Encode a search request, process it, and decode its Protobuf response."
    )
    parser.add_argument("--query", default="to be")
    parser.add_argument("--mode", choices=("corpus", "ai"), default="corpus")
    parser.add_argument("--context", default="general, clear English")
    parser.add_argument("--max-results", type=int, default=5)
    args = parser.parse_args(argv)

    request_bytes = encode_search_request(
        query=args.query,
        mode=args.mode,
        context=args.context if args.mode == "ai" else "",
        max_results=args.max_results,
    )
    decoded_request = decode_search_request(request_bytes)
    mode_name = autocomplete_pb2.SearchMode.Name(decoded_request.mode)

    print(f"Encoded SearchRequest: {len(request_bytes)} bytes")
    print(f"Binary payload (hex): {request_bytes.hex()}")
    print(
        "Decoded SearchRequest: "
        f"query={decoded_request.query!r}, mode={mode_name}, "
        f"max_results={decoded_request.max_results}"
    )

    generator = GeminiSuggestionClient() if args.mode == "ai" else None
    response_bytes = handle_serialized_request(
        request_bytes,
        corpus_search=get_best_k_completions,
        contextual_generator=generator,
    )
    response = decode_search_response(response_bytes)

    print(f"Encoded SearchResponse: {len(response_bytes)} bytes")
    print(f"Decoded SearchResponse: latency_ms={response.latency_ms}")
    if response.error:
        print(f"Error: {response.error}")
        return 1

    for rank, suggestion in enumerate(response.suggestions, start=1):
        origin = suggestion.WhichOneof("origin")
        if origin == "corpus":
            details = (
                f"source={suggestion.corpus.source_text}:"
                f"{suggestion.corpus.offset}, score={suggestion.corpus.score}"
            )
        else:
            details = f"model={suggestion.ai.model}"
        display_text = suggestion.text.lstrip()
        while display_text and not display_text[0].isprintable():
            display_text = display_text[1:].lstrip()
        print(f"{rank}. {display_text} ({origin}: {details})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
