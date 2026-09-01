from src.satellite import (
    SatelliteResilienceService,
    SatelliteStore,
    SimulatedSatelliteClient,
)
from src.ui.web_app import create_app


def test_ui_is_monitoring_only_without_search_panel(tmp_path):
    satellite = SatelliteResilienceService(
        SimulatedSatelliteClient(sleeper=lambda _seconds: None),
        SatelliteStore(tmp_path / "monitor.sqlite3"),
    )
    app = create_app(satellite_service=satellite)
    app.config.update(TESTING=True)

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b'id="search-form"' not in response.data
    assert b'id="search-title"' not in response.data
    assert b"Satellite Connection Resilience" in response.data
    assert b"Cached terminal activity" in response.data
