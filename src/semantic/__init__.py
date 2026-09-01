"""Gemini-powered semantic search, kept separate from Part A matching."""

from .models import SemanticResult
from .service import SemanticSearchError, get_semantic_results

__all__ = ["SemanticResult", "SemanticSearchError", "get_semantic_results"]
