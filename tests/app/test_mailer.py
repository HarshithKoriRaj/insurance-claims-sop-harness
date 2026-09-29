import threading

import pytest

from app.summaries import mailer as mailer_module
from app.summaries.mailer import SmtpMailer


class _BarrierSmtp:
    """Stands in for smtplib.SMTP; holds every sender at a barrier so they overlap."""

    barrier: threading.Barrier
    delivered: list[str] = []

    def __init__(self, host, port, timeout):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def send_message(self, message):
        type(self).delivered.append(message["Message-ID"])
        try:
            type(self).barrier.wait(timeout=1)
        except threading.BrokenBarrierError:
            pass


def test_two_racing_sends_of_one_summary_deliver_once(tmp_path, monkeypatch):
    _BarrierSmtp.barrier = threading.Barrier(2)
    _BarrierSmtp.delivered = []
    monkeypatch.setattr(mailer_module.smtplib, "SMTP", _BarrierSmtp)
    sender = SmtpMailer(tmp_path / "outbox.sqlite3", "smtp.test", 1025, "from@example.com")
    threads = [
        threading.Thread(target=sender.send, args=("SUMMARY-1", "margaret@email.com", "subject", "body"))
        for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(_BarrierSmtp.delivered) == 1
    assert sender.sent_count() == 1


def test_a_failed_send_can_be_retried(tmp_path, monkeypatch):
    class _Down(_BarrierSmtp):
        def send_message(self, message):
            raise OSError("connection refused")

    monkeypatch.setattr(mailer_module.smtplib, "SMTP", _Down)
    sender = SmtpMailer(tmp_path / "outbox.sqlite3", "smtp.test", 1025, "from@example.com")
    with pytest.raises(OSError):
        sender.send("SUMMARY-2", "margaret@email.com", "subject", "body")
    assert sender.sent_count() == 0
    _BarrierSmtp.barrier = threading.Barrier(1)
    _BarrierSmtp.delivered = []
    monkeypatch.setattr(mailer_module.smtplib, "SMTP", _BarrierSmtp)
    sender.send("SUMMARY-2", "margaret@email.com", "subject", "body")
    assert len(_BarrierSmtp.delivered) == 1 and sender.sent_count() == 1
