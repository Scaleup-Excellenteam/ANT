from src.auto_complete_data import AutoCompleteData
from src.contextual import ContextualResult, GeneratedSuggestion
from src.enhanced_cli import run_feature_cli
from src.satellite import (
    SatelliteConfig,
    SatelliteResilienceService,
    SatelliteStore,
    SatelliteTerminalActivityRecorder,
    SQLiteSimulatedSatelliteClient,
)
from src.translation import TranslationResult
from src.ui.web_app import create_app


class FakeGenerator:
    def generate(self, prefix, context, count=5):
        return ContextualResult(
            suggestions=(GeneratedSuggestion(f"{prefix} completed", "fake"),),
            model="fake",
            latency_ms=1,
        )


class FakeTranslator:
    def translate_to_english(self, text):
        return TranslationResult(text, "translated", "he")


def fake_search(query):
    return [AutoCompleteData(f"{query} result", "demo.txt", 1, 10)]


def shared_services(tmp_path):
    remote_path = tmp_path / "simulated-remote.sqlite3"
    local_path = tmp_path / "local-resilience.sqlite3"
    first_client = SQLiteSimulatedSatelliteClient(
        remote_path, {"mission-status": "nominal"}, latency_ms=0
    )
    second_client = SQLiteSimulatedSatelliteClient(remote_path, latency_ms=0)
    config = SatelliteConfig(failure_threshold=3, health_timeout_ms=100, max_retries=3)
    first = SatelliteResilienceService(first_client, SatelliteStore(local_path), config)
    second = SatelliteResilienceService(second_client, SatelliteStore(local_path), config)
    return first, second, first_client, second_client


def test_shared_simulator_propagates_link_state_and_idempotency(tmp_path):
    _first, _second, first_client, second_client = shared_services(tmp_path)
    first_client.set_online(False)

    assert second_client.health_check(100) is False

    second_client.reconnect(100)
    payload = {"key": "query", "value": "to pe"}
    assert first_client.write("shared-op", "upsert", payload, 100) is True
    assert second_client.write("shared-op", "upsert", payload, 100) is False
    assert second_client.read("query", 100) == "to pe"


def test_terminal_input_is_recorded_without_changing_cli_behavior(tmp_path, monkeypatch, capsys):
    terminal_service, _monitor, _first_client, _second_client = shared_services(tmp_path)
    recorder = SatelliteTerminalActivityRecorder(terminal_service)
    inputs = iter(["to pe", "~"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))

    run_feature_cli(fake_search, FakeGenerator(), FakeTranslator(), recorder)

    output = capsys.readouterr().out
    records = terminal_service.cached_values()
    assert "to pe result" in output
    assert len(records) == 1
    assert records[0].key.startswith("terminal-query:")
    assert records[0].value["query"] == "to pe"
    assert records[0].value["source"] == "terminal"


def test_terminal_to_monitor_cache_queue_and_recovery_flow(tmp_path):
    terminal_service, monitor_service, _terminal_client, _monitor_client = shared_services(tmp_path)
    recorder = SatelliteTerminalActivityRecorder(terminal_service)
    app = create_app(fake_search, FakeGenerator(), FakeTranslator(), monitor_service)
    app.config.update(TESTING=True)
    web = app.test_client()

    recorder.record_query("first terminal query", "corpus", "general")
    cached = web.get("/api/satellite/cache").get_json()["records"]
    assert any(item["value"]["query"] == "first terminal query" for item in cached)

    assert web.post("/api/satellite/simulate-disconnect").get_json()["status"] == "OFFLINE"
    recorder.record_query("query during outage", "corpus", "general")
    pending = web.get("/api/satellite/pending").get_json()
    assert pending["count"] == 1
    assert pending["operations"][0]["payload"]["value"]["query"] == "query during outage"

    recovered = web.post("/api/satellite/reconnect")
    assert recovered.status_code == 200
    assert recovered.get_json()["pending_operations"] == 0
    cached_after = web.get("/api/satellite/cache").get_json()["records"]
    assert any(
        isinstance(item["value"], dict)
        and item["value"].get("query") == "query during outage"
        for item in cached_after
    )
