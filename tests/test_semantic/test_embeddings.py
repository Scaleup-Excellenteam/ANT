import pytest

from src.semantic.embeddings import EmbeddingServiceError, GeminiEmbedder


class Value:
    def __init__(self, values):
        self.values = values


class Response:
    def __init__(self, embeddings):
        self.embeddings = embeddings


class Models:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def embed_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class Client:
    def __init__(self, models):
        self.models = models


def test_missing_api_key_has_clear_message(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(EmbeddingServiceError, match="GEMINI_API_KEY"):
        GeminiEmbedder()


def test_document_and_query_use_distinct_retrieval_tasks():
    models = Models(Response([Value([1.0, 2.0])]))
    embedder = GeminiEmbedder(api_key="test", client=Client(models))

    embedder.embed_documents(["document"])
    embedder.embed_query("query")

    assert models.calls[0]["config"].task_type == "RETRIEVAL_DOCUMENT"
    assert models.calls[1]["config"].task_type == "RETRIEVAL_QUERY"


def test_provider_failure_is_wrapped_without_leaking_details():
    models = Models(error=RuntimeError("secret provider detail"))
    embedder = GeminiEmbedder(api_key="test", client=Client(models))
    with pytest.raises(EmbeddingServiceError, match="unavailable") as error:
        embedder.embed_query("query")
    assert "secret provider detail" not in str(error.value)


def test_malformed_provider_response_is_rejected():
    models = Models(Response([]))
    embedder = GeminiEmbedder(api_key="test", client=Client(models))
    with pytest.raises(EmbeddingServiceError, match="invalid"):
        embedder.embed_query("query")
