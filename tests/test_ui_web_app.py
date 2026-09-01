from auto_complete_data import AutoCompleteData
from contextual import (
    ContextualResult,
    ContextualServiceError,
    GeneratedSuggestion,
)
from src.ui.web_app import create_app


def make_client(corpus_search=None, contextual_generator=None):
    app = create_app(
        corpus_search=corpus_search or (lambda _query: []),
        contextual_generator=contextual_generator,
    )
    app.config.update(TESTING=True)
    return app.test_client()


def test_get_index_serves_web_ui():
    client = make_client()

    response = client.get("/")

    assert response.status_code == 200
    assert b"Google Auto-Complete" in response.data
    assert b"Smart corpus search with Gemini assistance" in response.data


def test_english_api_search_uses_corpus_search_and_returns_metadata():
    calls = []

    def corpus_search(query):
        calls.append(query)
        return [AutoCompleteData("Python docs", "python.txt", 7, 30)]

    client = make_client(corpus_search=corpus_search)

    response = client.post(
        "/api/search",
        json={"query": " python ", "mode": "english"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert calls == ["python"]
    assert payload["mode"] == "english"
    assert payload["query"] == "python"
    assert payload["count"] == 1
    assert payload["results"] == [
        {
            "sentence": "Python docs",
            "score": 30,
            "source": "python.txt",
            "offset": 7,
        }
    ]


def test_gemini_api_search_uses_generator_without_corpus_metadata():
    corpus_calls = []

    class FakeGenerator:
        def __init__(self):
            self.calls = []

        def generate(self, prefix, context, count=5):
            self.calls.append((prefix, context, count))
            return ContextualResult(
                suggestions=(
                    GeneratedSuggestion("Hello from Gemini.", "test-gemini"),
                ),
                model="test-gemini",
                latency_ms=42,
            )

    generator = FakeGenerator()
    client = make_client(
        corpus_search=lambda query: corpus_calls.append(query),
        contextual_generator=generator,
    )

    response = client.post(
        "/api/search",
        json={"query": " Hello ", "mode": "gemini", "context": "friendly"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert corpus_calls == []
    assert generator.calls == [("Hello", "friendly", 5)]
    assert payload["mode"] == "gemini"
    assert payload["gemini_ms"] == 42
    assert payload["model"] == "test-gemini"
    assert payload["results"] == [
        {"text": "Hello from Gemini.", "ai_generated": True}
    ]
    assert "score" not in payload["results"][0]
    assert "source" not in payload["results"][0]
    assert "offset" not in payload["results"][0]


def test_empty_query_returns_bad_request():
    client = make_client()

    response = client.post("/api/search", json={"query": " ", "mode": "english"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Please enter some text."


def test_invalid_mode_returns_bad_request():
    client = make_client()

    response = client.post("/api/search", json={"query": "python", "mode": "bad"})

    assert response.status_code == 400
    assert "Invalid mode" in response.get_json()["error"]


def test_malformed_request_returns_bad_request():
    client = make_client()

    response = client.post("/api/search", data="not json")

    assert response.status_code == 400
    assert "JSON" in response.get_json()["error"]


def test_gemini_failure_returns_service_unavailable():
    class FailingGenerator:
        def generate(self, prefix, context, count=5):
            raise ContextualServiceError("Gemini timed out.")

    client = make_client(contextual_generator=FailingGenerator())

    response = client.post(
        "/api/search",
        json={"query": "Hello", "mode": "gemini"},
    )

    assert response.status_code == 503
    payload = response.get_json()
    assert payload["mode"] == "gemini"
    assert payload["results"] == []
    assert payload["error"] == "Gemini timed out."


def test_unexpected_search_exception_returns_server_error():
    def failing_search(_query):
        raise RuntimeError("index failed")

    client = make_client(corpus_search=failing_search)

    response = client.post(
        "/api/search",
        json={"query": "python", "mode": "english"},
    )

    assert response.status_code == 500
    assert response.get_json()["error"] == "Unexpected search error: index failed"
