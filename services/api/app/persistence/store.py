"""Sessions in SQLite. Each session is one row holding its state as JSON plus a version
number: a write based on an older version is refused instead of overwriting newer state.
Only a hash of the session token is stored."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
from datetime import datetime
from pathlib import Path


class SessionNotFound(KeyError):
    """Unknown session or wrong token; the two are deliberately indistinguishable."""


class StaleSession(RuntimeError):
    pass


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SessionStore:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._lock = threading.Lock()
        with self._lock:
            if str(path) != ":memory:":
                self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS sessions ("
                " id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, version INTEGER NOT NULL,"
                " state TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )

    @staticmethod
    def new_credentials() -> tuple[str, str]:
        return secrets.token_urlsafe(12), secrets.token_urlsafe(32)

    def create(self, session_id: str, token: str, state_json: str, now: datetime) -> int:
        with self._lock:
            self._db.execute(
                "INSERT INTO sessions (id, token_hash, version, state, updated_at) VALUES (?, ?, 1, ?, ?)",
                (session_id, _hash(token), state_json, now.isoformat()),
            )
        return 1

    def load(self, session_id: str, token: str) -> tuple[int, str]:
        with self._lock:
            row = self._db.execute(
                "SELECT token_hash, version, state FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if row is None or not secrets.compare_digest(row[0], _hash(token)):
            raise SessionNotFound(session_id)
        return row[1], row[2]

    def save(self, session_id: str, version: int, state_json: str, now: datetime) -> int:
        with self._lock:
            cursor = self._db.execute(
                "UPDATE sessions SET state = ?, version = version + 1, updated_at = ? WHERE id = ? AND version = ?",
                (state_json, now.isoformat(), session_id, version),
            )
        if cursor.rowcount != 1:
            raise StaleSession(session_id)
        return version + 1
