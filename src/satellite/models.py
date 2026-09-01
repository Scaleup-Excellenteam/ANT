"""Data contracts for the simulated satellite resilience subsystem."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional


class SatelliteState(str, Enum):
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    RECOVERING = "RECOVERING"


class OperationStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


@dataclass(frozen=True)
class CachedValue:
    key: str
    value: Any
    cached_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReadResult:
    key: str
    value: Any
    source: str
    stale: bool
    cached_at: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QueuedOperation:
    operation_id: str
    operation_type: str
    payload: Dict[str, Any]
    created_at: str
    retry_count: int
    status: OperationStatus
    last_error: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result


@dataclass(frozen=True)
class WriteResult:
    operation_id: str
    status: OperationStatus
    queued: bool
    duplicate: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "status": self.status.value,
            "queued": self.queued,
            "duplicate": self.duplicate,
        }


class SatelliteError(RuntimeError):
    """Base error for the satellite abstraction."""


class SatelliteUnavailableError(SatelliteError):
    """The remote link could not complete an operation."""


class DataUnavailableError(SatelliteError):
    """Neither the satellite nor the local cache has the requested data."""
