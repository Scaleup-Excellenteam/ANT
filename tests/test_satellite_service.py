import logging

import pytest

from src.satellite import (
    DataUnavailableError,
    OperationStatus,
    SatelliteConfig,
    SatelliteResilienceService,
    SatelliteState,
    SatelliteStore,
    SimulatedSatelliteClient,
)


def build_service(tmp_path, initial_data=None, failure_threshold=3, max_retries=3):
    client = SimulatedSatelliteClient(initial_data=initial_data, sleeper=lambda _seconds: None)
    store = SatelliteStore(tmp_path / "satellite.sqlite3")
    service = SatelliteResilienceService(
        client,
        store,
        SatelliteConfig(
            failure_threshold=failure_threshold,
            health_timeout_ms=100,
            max_retries=max_retries,
        ),
    )
    return service, client, store


def test_online_read_uses_satellite_and_updates_cache(tmp_path):
    service, _client, store = build_service(tmp_path, {"telemetry": {"temperature": 21}})

    result = service.read("telemetry")

    assert result.source == "satellite"
    assert result.stale is False
    assert result.value == {"temperature": 21}
    assert store.get_cache("telemetry").value == {"temperature": 21}


def test_health_threshold_then_cached_read_is_marked_stale(tmp_path, caplog):
    service, client, _store = build_service(
        tmp_path, {"telemetry": {"temperature": 21}}, failure_threshold=3
    )
    fresh = service.read("telemetry")
    client.set_online(False)

    assert service.check_health() == SatelliteState.DEGRADED
    assert service.check_health() == SatelliteState.DEGRADED
    with caplog.at_level(logging.WARNING, logger="satellite.resilience"):
        assert service.check_health() == SatelliteState.OFFLINE
        fallback = service.read("telemetry")

    assert fallback.value == fresh.value
    assert fallback.source == "cache"
    assert fallback.stale is True
    assert fallback.cached_at == fresh.cached_at
    assert "event=connection_lost" in caplog.text
    assert "event=cache_fallback" in caplog.text


def test_offline_read_without_cache_is_clearly_unavailable(tmp_path):
    service, _client, _store = build_service(tmp_path)
    service.simulate_disconnect()

    with pytest.raises(DataUnavailableError, match="no cached value"):
        service.read("missing")


def test_offline_write_is_durably_queued_once(tmp_path):
    service, _client, store = build_service(tmp_path)
    service.simulate_disconnect()

    first = service.write(
        "upsert", {"key": "command", "value": {"action": "rotate"}}, "op-1"
    )
    duplicate = service.write(
        "upsert", {"key": "command", "value": {"action": "rotate"}}, "op-1"
    )

    assert first.status == OperationStatus.PENDING
    assert first.queued is True
    assert duplicate.duplicate is True
    assert store.pending_count() == 1
    assert SatelliteStore(store.database_path).pending_count() == 1


def test_reconnect_replays_queue_and_returns_online(tmp_path):
    service, client, store = build_service(tmp_path)
    service.simulate_disconnect()
    service.write("upsert", {"key": "command", "value": "rotate"}, "op-1")

    state = service.reconnect()

    assert state == SatelliteState.ONLINE
    assert store.pending_count() == 0
    assert store.get_operation("op-1").status == OperationStatus.SENT
    assert client.read("command", 100) == "rotate"


def test_partial_recovery_keeps_only_unacknowledged_operation_pending(tmp_path):
    service, client, store = build_service(tmp_path)
    service.simulate_disconnect()
    for number in range(1, 4):
        service.write(
            "upsert",
            {"key": f"command-{number}", "value": number},
            f"op-{number}",
        )
    client.set_online(True)
    client.fail_after_successful_writes(2)

    state = service.recover()

    assert state == SatelliteState.OFFLINE
    operations = store.list_operations()
    assert [item.status for item in operations] == [
        OperationStatus.SENT,
        OperationStatus.SENT,
        OperationStatus.PENDING,
    ]
    assert [item.operation_id for item in service.pending_operations()] == ["op-3"]


def test_simulator_operation_ids_prevent_duplicate_application():
    client = SimulatedSatelliteClient(sleeper=lambda _seconds: None)
    payload = {"key": "command", "value": "rotate"}

    assert client.write("same-id", "upsert", payload, 100) is True
    assert client.write("same-id", "upsert", payload, 100) is False
    assert client.applied_write_count == 1


def test_configured_latency_timeout_counts_as_failure(tmp_path):
    service, client, _store = build_service(tmp_path, failure_threshold=1)
    client.set_latency(101)

    assert service.check_health() == SatelliteState.OFFLINE
