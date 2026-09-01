"""Transparent terminal activity recorder backed by satellite resilience."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from .service import SatelliteResilienceService

logger = logging.getLogger("satellite.activity")


class SatelliteTerminalActivityRecorder:
    def __init__(self, service: SatelliteResilienceService) -> None:
        self.service = service

    def record_query(self, query: str, mode: str, context: str) -> None:
        """Mirror a terminal query without ever blocking normal autocomplete behavior."""
        operation_id = str(uuid.uuid4())
        value: Dict[str, Any] = {
            "query": query,
            "mode": mode,
            "context": context,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "source": "terminal",
        }
        try:
            result = self.service.write(
                "upsert",
                {"key": f"terminal-query:{operation_id}", "value": value},
                operation_id=operation_id,
            )
            logger.info(
                "event=terminal_query_recorded operation_id=%s status=%s",
                operation_id,
                result.status.value,
            )
        except Exception as exc:  # Satellite recording must not break autocomplete.
            logger.warning(
                "event=terminal_query_record_failed error_type=%s", type(exc).__name__
            )
