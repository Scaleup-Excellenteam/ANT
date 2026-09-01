"""Public API for satellite connection-loss resilience."""

from .activity import SatelliteTerminalActivityRecorder
from .client import SatelliteClient
from .factory import build_shared_satellite_service
from .models import (
    DataUnavailableError,
    OperationStatus,
    QueuedOperation,
    ReadResult,
    SatelliteError,
    SatelliteState,
    SatelliteUnavailableError,
    WriteResult,
)
from .service import SatelliteConfig, SatelliteResilienceService
from .simulator import SimulatedSatelliteClient
from .sqlite_simulator import SQLiteSimulatedSatelliteClient
from .storage import SatelliteStore

__all__ = [
    "DataUnavailableError",
    "OperationStatus",
    "SatelliteTerminalActivityRecorder",
    "QueuedOperation",
    "ReadResult",
    "SatelliteClient",
    "SatelliteConfig",
    "SatelliteError",
    "SatelliteResilienceService",
    "SatelliteState",
    "SatelliteStore",
    "SatelliteUnavailableError",
    "SimulatedSatelliteClient",
    "SQLiteSimulatedSatelliteClient",
    "WriteResult",
    "build_shared_satellite_service",
]
