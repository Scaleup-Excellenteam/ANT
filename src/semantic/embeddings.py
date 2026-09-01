"""Embedding-provider boundary and Gemini API implementation."""

import os
from typing import List, Optional, Protocol, Sequence


DEFAULT_MODEL = "gemini-embedding-001"


class EmbeddingServiceError(RuntimeError):
    """A clear, provider-independent embedding failure."""


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        ...

    def embed_query(self, text: str) -> List[float]:
        ...


class GeminiEmbedder:
    """Google Gemini adapter optimized for document/query retrieval."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        timeout_ms: int = 15_000,
        client=None,
    ) -> None:
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key and client is None:
            raise EmbeddingServiceError(
                "GEMINI_API_KEY is not set. Create a key in Google AI Studio and "
                "set it only in your environment."
            )

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise EmbeddingServiceError(
                "Gemini support is not installed. Run: pip install -r requirements.txt"
            ) from exc

        self._types = types
        self._client = client or genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=timeout_ms),
        )
        self.model = model

    def _embed(self, texts: Sequence[str], task_type: str) -> List[List[float]]:
        if not texts:
            return []
        try:
            response = self._client.models.embed_content(
                model=self.model,
                contents=list(texts),
                config=self._types.EmbedContentConfig(task_type=task_type),
            )
            embeddings = response.embeddings or []
            vectors = [list(item.values or []) for item in embeddings]
        except Exception as exc:
            raise EmbeddingServiceError(
                "Gemini Embeddings is unavailable or the request failed. "
                "Check the API key, network, quota, and retry."
            ) from exc

        if len(vectors) != len(texts) or any(not vector for vector in vectors):
            raise EmbeddingServiceError("Gemini returned an invalid embedding response.")
        dimension = len(vectors[0])
        if any(len(vector) != dimension for vector in vectors):
            raise EmbeddingServiceError("Gemini returned inconsistent embedding dimensions.")
        return vectors

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> List[float]:
        return self._embed([text], "RETRIEVAL_QUERY")[0]
