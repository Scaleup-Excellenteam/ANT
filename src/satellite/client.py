"""Transport-independent contract for a future satellite database adapter."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Protocol


class SatelliteClient(Protocol):
    """Operations required by the resilience service.

    A real HTTP/gRPC/database adapter can implement this protocol later. The rest of
    the application does not depend on the local simulator.
    """

    is_simulation: bool

    def health_check(self, timeout_ms: int) -> bool:
        ...

    def read(self, key: str, timeout_ms: int) -> Any:
        ...

    def write(
        self,
        operation_id: str,
        operation_type: str,
        payload: Mapping[str, Any],
        timeout_ms: int,
    ) -> bool:
        ...

    def reconnect(self, timeout_ms: int) -> bool:
        ...

    def snapshot(self, timeout_ms: int) -> Dict[str, Any]:
        ...

    def get_status(self) -> Dict[str, Any]:
        ...
