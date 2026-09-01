"""Outage detection, cache fallback, durable queueing, and ordered recovery."""

from __future__ import annotations

import logging
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional

from .client import SatelliteClient
from .models import (
    DataUnavailableError,
    OperationStatus,
    QueuedOperation,
    ReadResult,
    SatelliteState,
    SatelliteUnavailableError,
    WriteResult,
)
from .storage import SatelliteStore

logger = logging.getLogger("satellite.resilience")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SatelliteConfig:
    failure_threshold: int = 3
    health_timeout_ms: int = 1500
    max_retries: int = 3

    def __post_init__(self) -> None:
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if self.health_timeout_ms < 1:
            raise ValueError("health_timeout_ms must be positive")
        if self.max_retries < 1:
            raise ValueError("max_retries must be at least 1")

    @classmethod
    def from_environment(cls) -> "SatelliteConfig":
        return cls(
            failure_threshold=int(os.getenv("SATELLITE_FAILURE_THRESHOLD", "3")),
            health_timeout_ms=int(os.getenv("SATELLITE_HEALTH_TIMEOUT_MS", "1500")),
            max_retries=int(os.getenv("SATELLITE_MAX_RETRIES", "3")),
        )


class SatelliteResilienceService:
    """Coordinates a generic remote client with local durable state."""

    def __init__(
        self,
        client: SatelliteClient,
        store: SatelliteStore,
        config: Optional[SatelliteConfig] = None,
        clock: Callable[[], str] = _utc_now,
    ) -> None:
        self.client = client
        self.store = store
        self.config = config or SatelliteConfig.from_environment()
        self._clock = clock
        self._state = SatelliteState.ONLINE
        self._consecutive_failures = 0
        self._last_successful_contact: Optional[str] = None
        self._lock = threading.RLock()

    def check_health(self) -> SatelliteState:
        """Run one health check and apply the configured failure threshold."""
        with self._lock:
            try:
                healthy = self.client.health_check(self.config.health_timeout_ms)
            except (OSError, TimeoutError, SatelliteUnavailableError):
                healthy = False
            if not healthy:
                self._record_failure("health_check_failed")
                return self._state

            previous = self._state
            self._record_success()
            if previous == SatelliteState.OFFLINE and self.store.pending_count():
                self._recover_locked(skip_health_check=True)
            else:
                self._set_state(SatelliteState.ONLINE)
            return self._state

    def read(self, key: str) -> ReadResult:
        normalized_key = key.strip()
        if not normalized_key:
            raise ValueError("satellite read key cannot be empty")
        with self._lock:
            if self._state != SatelliteState.OFFLINE:
                try:
                    value = self.client.read(normalized_key, self.config.health_timeout_ms)
                    cached_at = self._clock()
                    self.store.put_cache(normalized_key, value, cached_at)
                    self._record_success()
                    self._set_state(SatelliteState.ONLINE)
                    return ReadResult(
                        key=normalized_key,
                        value=value,
                        source="satellite",
                        stale=False,
                        cached_at=cached_at,
                    )
                except KeyError:
                    self._record_success()
                    raise DataUnavailableError(
                        f"record {normalized_key!r} does not exist on the simulated satellite"
                    )
                except (OSError, TimeoutError, SatelliteUnavailableError) as exc:
                    self._record_failure(type(exc).__name__)

            cached = self.store.get_cache(normalized_key)
            if cached is None:
                raise DataUnavailableError(
                    f"record {normalized_key!r} is unavailable and no cached value exists"
                )
            logger.warning(
                "event=cache_fallback key=%s cached_at=%s", normalized_key, cached.cached_at
            )
            return ReadResult(
                key=normalized_key,
                value=cached.value,
                source="cache",
                stale=True,
                cached_at=cached.cached_at,
            )

    def write(
        self,
        operation_type: str,
        payload: Mapping[str, Any],
        operation_id: Optional[str] = None,
    ) -> WriteResult:
        normalized_type = operation_type.strip().lower()
        if normalized_type not in {"upsert", "delete"}:
            raise ValueError("operation_type must be 'upsert' or 'delete'")
        safe_payload = dict(payload)
        if not str(safe_payload.get("key", "")).strip():
            raise ValueError("satellite write payload requires a non-empty key")
        identifier = operation_id or str(uuid.uuid4())

        with self._lock:
            existing = self.store.get_operation(identifier)
            if existing is not None:
                return WriteResult(
                    identifier,
                    existing.status,
                    queued=existing.status == OperationStatus.PENDING,
                    duplicate=True,
                )

            if self._state != SatelliteState.OFFLINE:
                try:
                    duplicate = not self.client.write(
                        identifier,
                        normalized_type,
                        safe_payload,
                        self.config.health_timeout_ms,
                    )
                    self._record_success()
                    self._update_cache_after_write(normalized_type, safe_payload)
                    sent = self._new_operation(
                        identifier, normalized_type, safe_payload, OperationStatus.SENT
                    )
                    self.store.enqueue(sent)
                    self.store.mark_sent(identifier, self._clock())
                    return WriteResult(identifier, OperationStatus.SENT, False, duplicate)
                except (OSError, TimeoutError, SatelliteUnavailableError) as exc:
                    self._record_failure(type(exc).__name__)

            queued = self._new_operation(
                identifier, normalized_type, safe_payload, OperationStatus.PENDING
            )
            self.store.enqueue(queued)
            logger.info(
                "event=operation_queued operation_id=%s operation_type=%s pending=%d",
                identifier,
                normalized_type,
                self.store.pending_count(),
            )
            return WriteResult(identifier, OperationStatus.PENDING, True)

    def reconnect(self) -> SatelliteState:
        """Request reconnection and replay pending writes in creation order."""
        with self._lock:
            self._set_state(SatelliteState.RECOVERING)
            try:
                if not self.client.reconnect(self.config.health_timeout_ms):
                    raise SatelliteUnavailableError("satellite reconnect was rejected")
            except (OSError, TimeoutError, SatelliteUnavailableError) as exc:
                self._set_offline_after_recovery_failure(type(exc).__name__)
                return self._state
            return self._recover_locked(skip_health_check=True)

    def recover(self) -> SatelliteState:
        with self._lock:
            return self._recover_locked(skip_health_check=False)

    def simulate_disconnect(self) -> SatelliteState:
        """Developer-only control; available only when the injected client is a simulator."""
        setter = getattr(self.client, "set_online", None)
        if not getattr(self.client, "is_simulation", False) or setter is None:
            raise RuntimeError("disconnect control is available only for the local simulator")
        with self._lock:
            setter(False)
            self._consecutive_failures = self.config.failure_threshold
            self._set_state(SatelliteState.OFFLINE)
            logger.warning(
                "event=connection_lost failures=%d reason=simulated_disconnect",
                self._consecutive_failures,
            )
            return self._state

    def set_simulated_latency(self, latency_ms: int) -> None:
        setter = getattr(self.client, "set_latency", None)
        if not getattr(self.client, "is_simulation", False) or setter is None:
            raise RuntimeError("latency control is available only for the local simulator")
        setter(latency_ms)

    def pending_operations(self) -> List[QueuedOperation]:
        return self.store.list_operations(pending_only=True)

    def all_operations(self) -> List[QueuedOperation]:
        return self.store.list_operations(pending_only=False)

    def cached_values(self):
        return self.store.list_cache()

    def status(self) -> Dict[str, Any]:
        client_status = self.client.get_status()
        mode = {
            SatelliteState.ONLINE: "LIVE",
            SatelliteState.DEGRADED: "CACHE FALLBACK READY",
            SatelliteState.OFFLINE: "CACHE FALLBACK",
            SatelliteState.RECOVERING: "SYNCHRONIZING",
        }[self._state]
        return {
            "status": self._state.value,
            "mode": mode,
            "latency_ms": client_status.get("latency_ms"),
            "pending_operations": self.store.pending_count(),
            "cached_records": self.store.cache_count(),
            "consecutive_failures": self._consecutive_failures,
            "failure_threshold": self.config.failure_threshold,
            "health_timeout_ms": self.config.health_timeout_ms,
            "last_successful_contact": self._last_successful_contact,
            "simulation": bool(client_status.get("simulation", False)),
        }

    def _recover_locked(self, skip_health_check: bool) -> SatelliteState:
        self._set_state(SatelliteState.RECOVERING)
        logger.info(
            "event=recovery_started pending=%d", self.store.pending_count()
        )
        if not skip_health_check:
            try:
                if not self.client.health_check(self.config.health_timeout_ms):
                    raise SatelliteUnavailableError("satellite health check failed")
            except (OSError, TimeoutError, SatelliteUnavailableError) as exc:
                self._set_offline_after_recovery_failure(type(exc).__name__)
                return self._state

        for operation in self.store.list_operations(pending_only=True):
            try:
                duplicate = not self.client.write(
                    operation.operation_id,
                    operation.operation_type,
                    operation.payload,
                    self.config.health_timeout_ms,
                )
                self.store.mark_sent(operation.operation_id, self._clock())
                self._update_cache_after_write(operation.operation_type, operation.payload)
                logger.info(
                    "event=operation_replayed operation_id=%s duplicate=%s pending=%d",
                    operation.operation_id,
                    duplicate,
                    self.store.pending_count(),
                )
            except (OSError, TimeoutError, SatelliteUnavailableError) as exc:
                retries = operation.retry_count + 1
                failed = retries >= self.config.max_retries
                self.store.record_retry(operation.operation_id, retries, type(exc).__name__, failed)
                logger.warning(
                    "event=replay_failed operation_id=%s retry=%d max_retries=%d",
                    operation.operation_id,
                    retries,
                    self.config.max_retries,
                )
                self._set_offline_after_recovery_failure(type(exc).__name__)
                return self._state

        try:
            snapshot = self.client.snapshot(self.config.health_timeout_ms)
            self.store.replace_cache(snapshot, self._clock())
        except (OSError, TimeoutError, SatelliteUnavailableError) as exc:
            self._set_offline_after_recovery_failure(type(exc).__name__)
            return self._state

        self._record_success()
        self._set_state(SatelliteState.ONLINE)
        logger.info("event=recovery_completed pending=0")
        return self._state

    def _new_operation(
        self,
        operation_id: str,
        operation_type: str,
        payload: Dict[str, Any],
        status: OperationStatus,
    ) -> QueuedOperation:
        now = self._clock()
        return QueuedOperation(
            operation_id=operation_id,
            operation_type=operation_type,
            payload=payload,
            created_at=now,
            retry_count=0,
            status=status,
            completed_at=now if status == OperationStatus.SENT else None,
        )

    def _update_cache_after_write(
        self, operation_type: str, payload: Mapping[str, Any]
    ) -> None:
        if operation_type == "upsert":
            self.store.put_cache(str(payload["key"]), payload["value"], self._clock())
        elif operation_type == "delete":
            self.store.delete_cache(str(payload["key"]))

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._last_successful_contact = self._clock()

    def _record_failure(self, reason: str) -> None:
        self._consecutive_failures += 1
        target = (
            SatelliteState.OFFLINE
            if self._consecutive_failures >= self.config.failure_threshold
            else SatelliteState.DEGRADED
        )
        old = self._state
        self._set_state(target)
        if target == SatelliteState.OFFLINE and old != SatelliteState.OFFLINE:
            logger.warning(
                "event=connection_lost failures=%d reason=%s",
                self._consecutive_failures,
                reason,
            )

    def _set_offline_after_recovery_failure(self, reason: str) -> None:
        self._consecutive_failures = max(
            self._consecutive_failures + 1, self.config.failure_threshold
        )
        self._set_state(SatelliteState.OFFLINE)
        logger.warning("event=recovery_interrupted reason=%s", reason)

    def _set_state(self, state: SatelliteState) -> None:
        self._state = state
