"""Sends an approved summary at most once per summary ID. With SMTP configured (Mailpit
in the Docker demo) the message goes to that server; either way it is recorded in the
outbox table, which is what makes a retry a no-op."""

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

    def already_sent(self, summary_id: str) -> bool:
        with self._lock:
            return self._db.execute("SELECT 1 FROM outbox WHERE summary_id = ?", (summary_id,)).fetchone() is not None

    def send(self, summary_id: str, to: str, subject: str, body: str) -> None:
        if self.already_sent(summary_id):
            return
        if self._host:
            message = EmailMessage()
            message["From"] = self._from
            message["To"] = to
            message["Subject"] = subject
            message["Message-ID"] = f"<{summary_id}@claims-assistant.local>"
            message.set_content(body)
            with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
                smtp.send_message(message)
        with self._lock:
            self._db.execute(
                "INSERT OR IGNORE INTO outbox (summary_id, recipient, subject, body, sent_at) VALUES (?, ?, ?, ?, ?)",
                (summary_id, to, subject, body, datetime.now(UTC).isoformat()),
            )

    def sent_count(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
