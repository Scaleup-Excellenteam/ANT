"""Clearly labeled local simulator for the satellite client contract."""

from __future__ import annotations

import copy
import threading
import time
from typing import Any, Callable, Dict, Mapping, Optional

from .models import SatelliteUnavailableError


class SimulatedSatelliteClient:
    """In-process development simulator; it does not contact a real satellite."""

    is_simulation = True

    def __init__(
        self,
        initial_data: Optional[Mapping[str, Any]] = None,
        latency_ms: int = 0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
        self._data: Dict[str, Any] = copy.deepcopy(dict(initial_data or {}))
        self._latency_ms = latency_ms
        self._online = True
        self._processed_operations: Dict[str, bool] = {}
        self._applied_write_count = 0
        self._writes_since_online = 0
        self._fail_after_writes: Optional[int] = None
        self._sleeper = sleeper
        self._lock = threading.RLock()

    def health_check(self, timeout_ms: int) -> bool:
        with self._lock:
            self._wait(timeout_ms)
            return self._online

    def read(self, key: str, timeout_ms: int) -> Any:
        with self._lock:
            self._require_online(timeout_ms)
            if key not in self._data:
                raise KeyError(key)
            return copy.deepcopy(self._data[key])

    def write(
        self,
        operation_id: str,
        operation_type: str,
        payload: Mapping[str, Any],
        timeout_ms: int,
    ) -> bool:
        with self._lock:
            if operation_id in self._processed_operations:
                return False
            if (
                self._fail_after_writes is not None
                and self._writes_since_online >= self._fail_after_writes
            ):
                self._online = False
            self._require_online(timeout_ms)

            key = str(payload.get("key", "")).strip()
            if not key:
                raise ValueError("satellite write payload requires a non-empty key")
            normalized_type = operation_type.strip().lower()
            if normalized_type == "upsert":
                if "value" not in payload:
                    raise ValueError("upsert payload requires a value")
                self._data[key] = copy.deepcopy(payload["value"])
            elif normalized_type == "delete":
                self._data.pop(key, None)
            else:
                raise ValueError("operation_type must be 'upsert' or 'delete'")

            self._processed_operations[operation_id] = True
            self._writes_since_online += 1
            self._applied_write_count += 1
            return True

    def reconnect(self, timeout_ms: int) -> bool:
        with self._lock:
            self._online = True
            self._writes_since_online = 0
            self._wait(timeout_ms)
            return True

    def snapshot(self, timeout_ms: int) -> Dict[str, Any]:
        with self._lock:
            self._require_online(timeout_ms)
            return copy.deepcopy(self._data)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "online": self._online,
                "latency_ms": self._latency_ms,
                "simulation": True,
                "applied_writes": self._applied_write_count,
            }

    def set_online(self, online: bool) -> None:
        with self._lock:
            self._online = bool(online)
            if online:
                self._writes_since_online = 0

    def set_latency(self, latency_ms: int) -> None:
        if latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
        with self._lock:
            self._latency_ms = latency_ms

    def fail_after_successful_writes(self, count: Optional[int]) -> None:
        if count is not None and count < 0:
            raise ValueError("count cannot be negative")
        with self._lock:
            self._fail_after_writes = count
            self._writes_since_online = 0

    @property
    def applied_write_count(self) -> int:
        with self._lock:
            return self._applied_write_count

    def _require_online(self, timeout_ms: int) -> None:
        self._wait(timeout_ms)
        if not self._online:
            raise SatelliteUnavailableError("simulated satellite link is offline")

    def _wait(self, timeout_ms: int) -> None:
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        wait_ms = min(self._latency_ms, timeout_ms)
        if wait_ms:
            self._sleeper(wait_ms / 1000.0)
        if self._latency_ms > timeout_ms:
            raise SatelliteUnavailableError(
                f"simulated satellite health timeout after {timeout_ms} ms"
            )
