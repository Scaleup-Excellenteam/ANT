"""Production wiring for the semantic index and Gemini provider."""

import pickle
from pathlib import Path
from typing import List, Optional

from .embeddings import EmbeddingServiceError, GeminiEmbedder
from .index import SemanticIndex
from .models import SemanticResult

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEMANTIC_INDEX_PATH = REPO_ROOT / "semantic_index.pickle"

SemanticSearchError = EmbeddingServiceError
_index: Optional[SemanticIndex] = None
_embedder: Optional[GeminiEmbedder] = None


def get_semantic_results(query: str, k: int = 5) -> List[SemanticResult]:
    global _index, _embedder
    if not query.strip():
        return []
    if not DEFAULT_SEMANTIC_INDEX_PATH.exists():
        raise SemanticSearchError(
            "Semantic index not found. Build it with: "
            "python -m src.semantic.build_index"
        )
    if _index is None:
        try:
            _index = SemanticIndex.load(DEFAULT_SEMANTIC_INDEX_PATH)
        except (OSError, ValueError, pickle.UnpicklingError) as exc:
            raise SemanticSearchError(
                "The semantic index could not be loaded. Rebuild it."
            ) from exc
    if _embedder is None:
        _embedder = GeminiEmbedder()
    return _index.search(query, _embedder, k=k)
