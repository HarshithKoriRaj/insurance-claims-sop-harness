"""Sends an approved summary at most once per summary ID, even when two requests race
(a double click, two tabs, a client retry). The summary ID is reserved in the outbox
table atomically before anything is sent; whoever loses the race sends nothing. If the
send fails, the reservation is released so a later retry can send it."""

from __future__ import annotations

import smtplib
import sqlite3
import threading
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path


class SmtpMailer:
    def __init__(self, database_path: Path | str, smtp_host: str | None, smtp_port: int, mail_from: str) -> None:
        if str(database_path) != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(database_path), check_same_thread=False, isolation_level=None)
        self._lock = threading.Lock()
        self._host, self._port, self._from = smtp_host, smtp_port, mail_from
        with self._lock:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS outbox (summary_id TEXT PRIMARY KEY, recipient TEXT NOT NULL,"
                " subject TEXT NOT NULL, body TEXT NOT NULL, sent_at TEXT NOT NULL)"
            )

    def _reserve(self, summary_id: str, to: str, subject: str, body: str) -> bool:
        with self._lock:
            cursor = self._db.execute(
                "INSERT OR IGNORE INTO outbox (summary_id, recipient, subject, body, sent_at) VALUES (?, ?, ?, ?, ?)",
                (summary_id, to, subject, body, datetime.now(UTC).isoformat()),
            )
            return cursor.rowcount == 1

    def _release(self, summary_id: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM outbox WHERE summary_id = ?", (summary_id,))

    def send(self, summary_id: str, to: str, subject: str, body: str) -> None:
        if not self._reserve(summary_id, to, subject, body):
            return  # already sent, or being sent by a concurrent request
        if not self._host:
            return  # no SMTP server configured: the outbox row is the record
        message = EmailMessage()
        message["From"] = self._from
        message["To"] = to
        message["Subject"] = subject
        message["Message-ID"] = f"<{summary_id}@claims-assistant.local>"
        message.set_content(body)
        try:
            with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
                smtp.send_message(message)
        except Exception:
            self._release(summary_id)
            raise

    def sent_count(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
