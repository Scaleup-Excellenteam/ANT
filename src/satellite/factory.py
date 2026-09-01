"""Shared construction for CLI and monitoring UI satellite services."""

from __future__ import annotations

import os
from pathlib import Path

from .service import SatelliteConfig, SatelliteResilienceService
from .sqlite_simulator import SQLiteSimulatedSatelliteClient
from .storage import SatelliteStore

REPO_ROOT = Path(__file__).resolve().parents[2]


def build_shared_satellite_service() -> SatelliteResilienceService:
    runtime_dir = REPO_ROOT / ".runtime"
    local_database = Path(
        os.getenv("SATELLITE_STATE_DB", str(runtime_dir / "satellite_local.sqlite3"))
    )
    simulated_remote_database = Path(
        os.getenv(
            "SATELLITE_SIMULATOR_DB",
            str(runtime_dir / "satellite_remote_simulator.sqlite3"),
        )
    )
    simulator = SQLiteSimulatedSatelliteClient(
        simulated_remote_database,
        initial_data={
            "mission-status": {
                "message": "Nominal simulated telemetry",
                "sequence": 1,
            }
        },
        latency_ms=int(os.getenv("SATELLITE_SIMULATED_LATENCY_MS", "250")),
    )
    return SatelliteResilienceService(
        simulator,
        SatelliteStore(local_database),
        SatelliteConfig.from_environment(),
    )
