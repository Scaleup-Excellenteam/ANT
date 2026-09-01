from src.auto_complete_data import AutoCompleteData
from src.contextual import ContextualResult, GeneratedSuggestion
from src.satellite import (
    SatelliteConfig,
    SatelliteResilienceService,
    SatelliteStore,
    SimulatedSatelliteClient,
)
from src.translation import TranslationResult
from src.ui.web_app import create_app


class FakeGenerator:
    def generate(self, prefix, context, count=5):
        return ContextualResult(
            suggestions=(GeneratedSuggestion(f"{prefix} completed", "fake-gemini"),),
            model="fake-gemini",
            latency_ms=12,
        )


class FakeTranslator:
    def translate_to_english(self, text):
        return TranslationResult(text, "virtual machine", "he")


def fake_search(query):
    return [AutoCompleteData(f"{query} result", "demo.txt", 7, 20)]


def build_app(tmp_path):
    simulator = SimulatedSatelliteClient(
        {"mission-status": {"message": "nominal"}}, sleeper=lambda _seconds: None
    )
    service = SatelliteResilienceService(
        simulator,
        SatelliteStore(tmp_path / "ui-satellite.sqlite3"),
        SatelliteConfig(failure_threshold=2, health_timeout_ms=100, max_retries=3),
    )
    app = create_app(fake_search, FakeGenerator(), FakeTranslator(), service)
    app.config.update(TESTING=True)
    return app, service


def test_page_clearly_labels_simulation(tmp_path):
    app, _service = build_app(tmp_path)
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b"SIMULATED LINK" in response.data
    assert b"not connected to a physical satellite" in response.data


def test_existing_search_modes_remain_available(tmp_path):
    app, _service = build_app(tmp_path)
    client = app.test_client()

    corpus = client.post("/api/search", json={"query": "to pe", "mode": "corpus"})
    ai = client.post(
        "/api/search",
        json={"query": "Thank you for", "mode": "ai", "context": "email"},
    )
    translated = client.post(
        "/api/search", json={"query": "מכונה וירטואלית", "mode": "translation"}
    )

    assert corpus.status_code == 200
    assert corpus.get_json()["results"][0]["source"] == "demo.txt"
    assert ai.get_json()["results"][0]["ai_generated"] is True
    assert translated.get_json()["search_query"] == "virtual machine"


def test_complete_disconnect_cache_queue_and_reconnect_api_flow(tmp_path):
    app, _service = build_app(tmp_path)
    client = app.test_client()

    online_read = client.get("/api/satellite/data/mission-status")
    assert online_read.get_json()["result"]["source"] == "satellite"

    disconnected = client.post("/api/satellite/simulate-disconnect")
    assert disconnected.get_json()["status"] == "OFFLINE"

    cached_read = client.get("/api/satellite/data/mission-status")
    assert cached_read.get_json()["result"]["source"] == "cache"
    assert cached_read.get_json()["result"]["stale"] is True

    queued = client.post(
        "/api/satellite/data",
        json={"key": "panel-note", "value": {"message": "queued"}, "operation_id": "demo-op"},
    )
    assert queued.status_code == 202
    assert queued.get_json()["operation"]["status"] == "PENDING"
    assert client.get("/api/satellite/pending").get_json()["count"] == 1

    recovered = client.post("/api/satellite/reconnect")
    assert recovered.status_code == 200
    assert recovered.get_json()["status"] == "ONLINE"
    assert recovered.get_json()["pending_operations"] == 0
