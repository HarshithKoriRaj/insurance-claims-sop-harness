"""Per-client sliding-window rate limits for a public demo. They protect the model API
budget and make it expensive to open fresh sessions just to retry verification (each
session allows three verification attempts). In memory, per process: a best-effort
guard for one small instance, not a replacement for limits at the edge."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


def parse_limit(value: str) -> tuple[int, float]:
    """"10/600" means at most 10 requests in any 600-second window."""
    count, _, seconds = value.partition("/")
    limit, window = int(count), float(seconds)
    if limit < 1 or window <= 0:
        raise ValueError(f"invalid rate limit {value!r}; expected COUNT/SECONDS")
    return limit, window


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        at = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[key]
            while hits and at - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(at)
            return True
