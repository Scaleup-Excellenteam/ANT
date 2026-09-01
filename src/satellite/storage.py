"""Durable SQLite cache and operation queue for satellite resilience."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import CachedValue, OperationStatus, QueuedOperation


class SatelliteStore:
    """Small local durable store; safe to reopen after an application restart."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS satellite_cache (
                    cache_key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    cached_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS satellite_operations (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_id TEXT NOT NULL UNIQUE,
                    operation_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    last_error TEXT,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_satellite_operations_status_sequence
                    ON satellite_operations(status, sequence);
                """
            )

    def put_cache(self, key: str, value: Any, cached_at: str) -> None:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO satellite_cache(cache_key, value_json, cached_at)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    value_json=excluded.value_json,
                    cached_at=excluded.cached_at
                """,
                (key, encoded, cached_at),
            )

    def get_cache(self, key: str) -> Optional[CachedValue]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT cache_key, value_json, cached_at FROM satellite_cache WHERE cache_key=?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return CachedValue(row["cache_key"], json.loads(row["value_json"]), row["cached_at"])

    def list_cache(self) -> List[CachedValue]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT cache_key, value_json, cached_at FROM satellite_cache ORDER BY cached_at DESC"
            ).fetchall()
        return [
            CachedValue(row["cache_key"], json.loads(row["value_json"]), row["cached_at"])
            for row in rows
        ]

    def cache_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM satellite_cache").fetchone()
        return int(row["total"])

    def delete_cache(self, key: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM satellite_cache WHERE cache_key=?", (key,))

    def replace_cache(self, values: Dict[str, Any], cached_at: str) -> None:
        """Atomically refresh the local cache from a complete remote snapshot."""
        rows = [
            (key, json.dumps(value, ensure_ascii=False, sort_keys=True), cached_at)
            for key, value in values.items()
        ]
        with self._connect() as connection:
            connection.execute("DELETE FROM satellite_cache")
            connection.executemany(
                """
                INSERT INTO satellite_cache(cache_key, value_json, cached_at)
                VALUES (?, ?, ?)
                """,
                rows,
            )

    def enqueue(self, operation: QueuedOperation) -> QueuedOperation:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO satellite_operations(
                    operation_id, operation_type, payload_json, created_at,
                    retry_count, status, last_error, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operation.operation_id,
                    operation.operation_type,
                    json.dumps(operation.payload, ensure_ascii=False, sort_keys=True),
                    operation.created_at,
                    operation.retry_count,
                    operation.status.value,
                    operation.last_error,
                    operation.completed_at,
                ),
            )
        return self.get_operation(operation.operation_id) or operation

    def get_operation(self, operation_id: str) -> Optional[QueuedOperation]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM satellite_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
        return self._operation_from_row(row) if row is not None else None

    def list_operations(self, pending_only: bool = False) -> List[QueuedOperation]:
        query = "SELECT * FROM satellite_operations"
        params = ()
        if pending_only:
            query += " WHERE status=?"
            params = (OperationStatus.PENDING.value,)
        query += " ORDER BY sequence"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._operation_from_row(row) for row in rows]

    def pending_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM satellite_operations WHERE status=?",
                (OperationStatus.PENDING.value,),
            ).fetchone()
        return int(row["total"])

    def mark_sent(self, operation_id: str, completed_at: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE satellite_operations
                SET status=?, completed_at=?, last_error=NULL
                WHERE operation_id=?
                """,
                (OperationStatus.SENT.value, completed_at, operation_id),
            )

    def record_retry(
        self, operation_id: str, retry_count: int, error: str, failed: bool
    ) -> None:
        status = OperationStatus.FAILED if failed else OperationStatus.PENDING
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE satellite_operations
                SET retry_count=?, status=?, last_error=?
                WHERE operation_id=?
                """,
                (retry_count, status.value, error[:500], operation_id),
            )

    @staticmethod
    def _operation_from_row(row: sqlite3.Row) -> QueuedOperation:
        return QueuedOperation(
            operation_id=row["operation_id"],
            operation_type=row["operation_type"],
            payload=json.loads(row["payload_json"]),
            created_at=row["created_at"],
            retry_count=int(row["retry_count"]),
            status=OperationStatus(row["status"]),
            last_error=row["last_error"],
            completed_at=row["completed_at"],
        )
