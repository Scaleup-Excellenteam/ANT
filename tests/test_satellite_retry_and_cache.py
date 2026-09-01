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


def test_retry_limit_marks_operation_failed_without_discarding_record(tmp_path):
    client = SimulatedSatelliteClient(sleeper=lambda _seconds: None)
    store = SatelliteStore(tmp_path / "retry.sqlite3")
    service = SatelliteResilienceService(
        client,
        store,
        SatelliteConfig(failure_threshold=1, health_timeout_ms=100, max_retries=1),
    )
    service.simulate_disconnect()
    service.write("upsert", {"key": "command", "value": "rotate"}, "retry-op")
    client.set_online(True)
    client.fail_after_successful_writes(0)

    assert service.recover() == SatelliteState.OFFLINE
    operation = store.get_operation("retry-op")
    assert operation.status == OperationStatus.FAILED
    assert operation.retry_count == 1
    assert operation.last_error


def test_delete_removes_cached_value_instead_of_serving_old_data(tmp_path):
    client = SimulatedSatelliteClient({"temporary": "value"}, sleeper=lambda _seconds: None)
    store = SatelliteStore(tmp_path / "delete.sqlite3")
    service = SatelliteResilienceService(client, store)
    service.read("temporary")

    result = service.write("delete", {"key": "temporary"}, "delete-op")
    service.simulate_disconnect()

    assert result.status == OperationStatus.SENT
    with pytest.raises(DataUnavailableError, match="no cached value"):
        service.read("temporary")


def test_recovery_snapshot_replaces_obsolete_cached_records(tmp_path):
    client = SimulatedSatelliteClient({"old": 1, "keep": 2}, sleeper=lambda _seconds: None)
    store = SatelliteStore(tmp_path / "refresh.sqlite3")
    service = SatelliteResilienceService(client, store)
    service.read("old")
    service.read("keep")
    client.write("remote-delete", "delete", {"key": "old"}, 100)

    assert service.recover() == SatelliteState.ONLINE
    assert store.get_cache("old") is None
    assert store.get_cache("keep").value == 2
