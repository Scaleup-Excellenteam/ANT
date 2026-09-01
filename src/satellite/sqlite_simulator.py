"""Process-shared SQLite simulator for local satellite demonstrations.

This models a remote system for development only. Keeping the simulated remote state
in a separate SQLite file lets the terminal process and monitoring UI observe the same
link status and records without pretending to contact physical satellite hardware.
"""

from __future__ import annotations

import copy
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from .models import SatelliteUnavailableError


class SQLiteSimulatedSatelliteClient:
    is_simulation = True

    def __init__(
        self,
        database_path: Path,
        initial_data: Optional[Mapping[str, Any]] = None,
        latency_ms: int = 250,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._sleeper = sleeper
        self._initialize(initial_data or {}, latency_ms)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self, initial_data: Mapping[str, Any], latency_ms: int) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS simulator_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS simulator_records (
                    record_key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS simulator_operations (
                    operation_id TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO simulator_settings VALUES ('online', '1')"
            )
            connection.execute(
                "INSERT OR IGNORE INTO simulator_settings VALUES ('latency_ms', ?)",
                (str(latency_ms),),
            )
            connection.executemany(
                "INSERT OR IGNORE INTO simulator_records(record_key, value_json) VALUES (?, ?)",
                [
                    (key, json.dumps(value, ensure_ascii=False, sort_keys=True))
                    for key, value in initial_data.items()
                ],
            )

    def health_check(self, timeout_ms: int) -> bool:
        self._wait(timeout_ms)
        return self._is_online()

    def read(self, key: str, timeout_ms: int) -> Any:
        self._require_online(timeout_ms)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value_json FROM simulator_records WHERE record_key=?", (key,)
            ).fetchone()
        if row is None:
            raise KeyError(key)
        return copy.deepcopy(json.loads(row["value_json"]))

    def write(
        self,
        operation_id: str,
        operation_type: str,
        payload: Mapping[str, Any],
        timeout_ms: int,
    ) -> bool:
        self._wait(timeout_ms)
        key = str(payload.get("key", "")).strip()
        if not key:
            raise ValueError("satellite write payload requires a non-empty key")
        normalized_type = operation_type.strip().lower()
        if normalized_type not in {"upsert", "delete"}:
            raise ValueError("operation_type must be 'upsert' or 'delete'")

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if not self._is_online(connection):
                raise SatelliteUnavailableError("simulated satellite link is offline")
            duplicate = connection.execute(
                "SELECT 1 FROM simulator_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
            if duplicate is not None:
                return False
            if normalized_type == "upsert":
                if "value" not in payload:
                    raise ValueError("upsert payload requires a value")
                connection.execute(
                    """
                    INSERT INTO simulator_records(record_key, value_json) VALUES (?, ?)
                    ON CONFLICT(record_key) DO UPDATE SET value_json=excluded.value_json
                    """,
                    (key, json.dumps(payload["value"], ensure_ascii=False, sort_keys=True)),
                )
            else:
                connection.execute("DELETE FROM simulator_records WHERE record_key=?", (key,))
            connection.execute(
                "INSERT INTO simulator_operations(operation_id) VALUES (?)", (operation_id,)
            )
        return True

    def reconnect(self, timeout_ms: int) -> bool:
        self.set_online(True)
        self._wait(timeout_ms)
        return True

    def snapshot(self, timeout_ms: int) -> Dict[str, Any]:
        self._require_online(timeout_ms)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT record_key, value_json FROM simulator_records ORDER BY record_key"
            ).fetchall()
        return {row["record_key"]: json.loads(row["value_json"]) for row in rows}

    def get_status(self) -> Dict[str, Any]:
        with self._connect() as connection:
            online = self._is_online(connection)
            latency_ms = int(self._setting("latency_ms", connection))
            writes = connection.execute(
                "SELECT COUNT(*) AS total FROM simulator_operations"
            ).fetchone()["total"]
        return {
            "online": online,
            "latency_ms": latency_ms,
            "simulation": True,
            "applied_writes": int(writes),
            "shared_backend": True,
        }

    def set_online(self, online: bool) -> None:
        self._set_setting("online", "1" if online else "0")

    def set_latency(self, latency_ms: int) -> None:
        if latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
        self._set_setting("latency_ms", str(latency_ms))

    def _require_online(self, timeout_ms: int) -> None:
        self._wait(timeout_ms)
        if not self._is_online():
            raise SatelliteUnavailableError("simulated satellite link is offline")

    def _wait(self, timeout_ms: int) -> None:
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        latency_ms = int(self._setting("latency_ms"))
        wait_ms = min(latency_ms, timeout_ms)
        if wait_ms:
            self._sleeper(wait_ms / 1000.0)
        if latency_ms > timeout_ms:
            raise SatelliteUnavailableError(
                f"simulated satellite health timeout after {timeout_ms} ms"
            )

    def _is_online(self, connection: Optional[sqlite3.Connection] = None) -> bool:
        return self._setting("online", connection) == "1"

    def _setting(
        self, key: str, connection: Optional[sqlite3.Connection] = None
    ) -> str:
        if connection is not None:
            row = connection.execute(
                "SELECT setting_value FROM simulator_settings WHERE setting_key=?", (key,)
            ).fetchone()
            return str(row["setting_value"])
        with self._connect() as owned_connection:
            row = owned_connection.execute(
                "SELECT setting_value FROM simulator_settings WHERE setting_key=?", (key,)
            ).fetchone()
        return str(row["setting_value"])

    def _set_setting(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO simulator_settings(setting_key, setting_value) VALUES (?, ?)
                ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value
                """,
                (key, value),
            )
