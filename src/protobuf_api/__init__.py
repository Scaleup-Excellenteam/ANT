"""Transport-neutral Protocol Buffers interface for autocomplete requests."""

from . import autocomplete_pb2
from .service import (
    decode_search_request,
    decode_search_response,
    encode_search_request,
    handle_serialized_request,
)

__all__ = [
    "autocomplete_pb2",
    "decode_search_request",
    "decode_search_response",
    "encode_search_request",
    "handle_serialized_request",
]
