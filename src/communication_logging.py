"""Transport-agnostic logging helpers for future satellite communication code.

This module records communication metadata only. It does not send, queue, compress,
or retain message payloads, and its public methods intentionally accept no payload,
credential, token, or API-key arguments.
"""

import logging
import re
import time
from typing import Callable, Dict, Optional, Union

MessageId = Union[int, str]
_SAFE_LABEL = re.compile(r"[^A-Za-z0-9_.:-]+")
_VALID_PRIORITIES = {"low", "normal", "high", "critical"}


class _RedactedCommunicationError(RuntimeError):
    """Safe exception text paired with the original traceback frames in logs."""


def _safe_label(value: object, fallback: str = "unknown") -> str:
    """Return a bounded, single-token identifier safe for structured log text."""

    sanitized = _SAFE_LABEL.sub("_", str(value).strip())[:64]
    return sanitized or fallback


class SatelliteCommunicationLogger:
    """Record future transport events without implementing the transport itself."""

    def __init__(
        self,
        clock: Callable[[], float] = time.perf_counter,
        high_latency_seconds: float = 2.0,
        low_bandwidth_kbps: float = 256.0,
    ) -> None:
        if high_latency_seconds < 0 or low_bandwidth_kbps < 0:
            raise ValueError("Communication thresholds cannot be negative")
        self._clock = clock
        self._high_latency_seconds = high_latency_seconds
        self._low_bandwidth_kbps = low_bandwidth_kbps
        self._sent_at: Dict[str, float] = {}
        self._connection_lost_at: Optional[float] = None
        self._low_bandwidth_mode = False
        self._connection = logging.getLogger("satellite.connection")
        self._latency = logging.getLogger("satellite.latency")
        self._retry = logging.getLogger("satellite.retry")
        self._queue = logging.getLogger("satellite.queue")
        self._bandwidth = logging.getLogger("satellite.bandwidth")

    def message_sent(self, message_id: MessageId, priority: str = "normal") -> None:
        priority = priority.lower()
        if priority not in _VALID_PRIORITIES:
            raise ValueError(f"Unsupported message priority: {priority}")
        safe_id = _safe_label(message_id)
        self._sent_at[safe_id] = self._clock()
        self._connection.info("Sending message id=%s priority=%s", safe_id, priority)
        self._latency.debug("Round-trip timer started id=%s", safe_id)

    def waiting_for_ack(self, message_id: MessageId) -> None:
        self._connection.debug("Waiting for ACK id=%s", _safe_label(message_id))

    def ack_received(
        self, message_id: MessageId, latency_seconds: Optional[float] = None
    ) -> Optional[float]:
        safe_id = _safe_label(message_id)
        sent_at = self._sent_at.pop(safe_id, None)
        if latency_seconds is None and sent_at is not None:
            latency_seconds = max(0.0, self._clock() - sent_at)
        if latency_seconds is None:
            self._connection.info("ACK received id=%s latency=unknown", safe_id)
            return None
        if latency_seconds < 0:
            raise ValueError("Latency cannot be negative")
        self._connection.info(
            "ACK received id=%s latency=%.3fs", safe_id, latency_seconds
        )
        self._latency.debug(
            "Round-trip latency id=%s latency=%.3fs", safe_id, latency_seconds
        )
        if latency_seconds >= self._high_latency_seconds:
            self._latency.warning(
                "High latency id=%s latency=%.3fs threshold=%.3fs",
                safe_id,
                latency_seconds,
                self._high_latency_seconds,
            )
        return latency_seconds

    def ack_timeout(self, message_id: MessageId) -> None:
        self._connection.warning("ACK timeout id=%s", _safe_label(message_id))

    def retry(self, message_id: MessageId, attempt: int, max_attempts: int) -> None:
        if attempt < 1 or max_attempts < 1 or attempt > max_attempts:
            raise ValueError("Retry attempt must be between 1 and max_attempts")
        self._retry.warning(
            "Retry %d/%d id=%s", attempt, max_attempts, _safe_label(message_id)
        )

    def retry_limit_exhausted(self, message_id: MessageId, attempts: int) -> None:
        self._sent_at.pop(_safe_label(message_id), None)
        self._retry.error(
            "Retry limit exhausted id=%s attempts=%d",
            _safe_label(message_id),
            attempts,
        )

    def connection_lost(self) -> None:
        if self._connection_lost_at is None:
            self._connection_lost_at = self._clock()
            self._connection.warning("Connection lost")
        else:
            self._connection.debug("Connection remains unavailable")

    def connection_restored(
        self, downtime_seconds: Optional[float] = None
    ) -> Optional[float]:
        if downtime_seconds is None and self._connection_lost_at is not None:
            downtime_seconds = max(0.0, self._clock() - self._connection_lost_at)
        self._connection_lost_at = None
        if downtime_seconds is None:
            self._connection.info("Connection restored downtime=unknown")
            return None
        if downtime_seconds < 0:
            raise ValueError("Downtime cannot be negative")
        self._connection.info("Connection restored downtime=%.3fs", downtime_seconds)
        return downtime_seconds

    def message_queued(self, message_id: MessageId, queue_size: int) -> None:
        if queue_size < 0:
            raise ValueError("Queue size cannot be negative")
        self._queue.info(
            "Message queued id=%s queue_size=%d", _safe_label(message_id), queue_size
        )

    def resend_queued_message(self, message_id: MessageId, queue_size: int) -> None:
        if queue_size < 0:
            raise ValueError("Queue size cannot be negative")
        safe_id = _safe_label(message_id)
        self._sent_at[safe_id] = self._clock()
        self._queue.info(
            "Resending queued message id=%s queue_size=%d", safe_id, queue_size
        )

    def message_delivered(self, message_id: MessageId) -> None:
        self._connection.info("Message delivered id=%s", _safe_label(message_id))

    def message_failed(self, message_id: MessageId, failure_code: str) -> None:
        safe_id = _safe_label(message_id)
        self._sent_at.pop(safe_id, None)
        self._connection.error(
            "Message permanently failed id=%s failure_code=%s",
            safe_id,
            _safe_label(failure_code, fallback="unspecified"),
        )

    def bandwidth_measured(self, bandwidth_kbps: float) -> None:
        if bandwidth_kbps < 0:
            raise ValueError("Bandwidth cannot be negative")
        self._bandwidth.debug("Bandwidth measured bandwidth_kbps=%.1f", bandwidth_kbps)
        is_low = bandwidth_kbps < self._low_bandwidth_kbps
        if is_low and not self._low_bandwidth_mode:
            self._bandwidth.warning(
                "Low bandwidth detected bandwidth_kbps=%.1f threshold_kbps=%.1f",
                bandwidth_kbps,
                self._low_bandwidth_kbps,
            )
            self._bandwidth.info("Low-bandwidth mode activated")
        elif not is_low and self._low_bandwidth_mode:
            self._bandwidth.info("Low-bandwidth mode deactivated")
        self._low_bandwidth_mode = is_low

    def payload_size(self, original_bytes: int, transmitted_bytes: int) -> None:
        if original_bytes < 0 or transmitted_bytes < 0:
            raise ValueError("Payload byte counts cannot be negative")
        ratio = transmitted_bytes / original_bytes if original_bytes else 0.0
        self._bandwidth.debug(
            "Payload original_bytes=%d transmitted_bytes=%d compression_ratio=%.3f",
            original_bytes,
            transmitted_bytes,
            ratio,
        )

    def unexpected_exception(
        self, operation: str, message_id: Optional[MessageId] = None
    ) -> None:
        """Log active traceback frames with redacted exception text."""

        safe_operation = _safe_label(operation, fallback="unknown")
        try:
            raise _RedactedCommunicationError(
                "communication exception details redacted"
            ) from None
        except _RedactedCommunicationError:
            if message_id is None:
                self._connection.exception(
                    "Unexpected communication error operation=%s",
                    safe_operation,
                    stack_info=True,
                )
            else:
                self._connection.exception(
                    "Unexpected communication error operation=%s id=%s",
                    safe_operation,
                    _safe_label(message_id),
                    stack_info=True,
                )
