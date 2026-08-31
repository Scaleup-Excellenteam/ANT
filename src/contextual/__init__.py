"""Public API for the optional Part B Gemini feature."""

from .errors import (
    ContextualCompletionError,
    ContextualConfigurationError,
    ContextualServiceError,
    InvalidGeminiResponseError,
)
from .gemini_client import GeminiSuggestionClient
from .models import ContextualResult, GeneratedSuggestion

__all__ = [
    "ContextualCompletionError",
    "ContextualConfigurationError",
    "ContextualServiceError",
    "InvalidGeminiResponseError",
    "ContextualResult",
    "GeneratedSuggestion",
    "GeminiSuggestionClient",
]
