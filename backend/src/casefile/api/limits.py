"""Rate limits per visitor (D57).

A public server has to stop one visitor from filling it with games or hammering the
model. Each limit counts requests per client address in a sliding window, in memory:
one server process needs nothing more, and a restart forgetting the counts is harmless.
"""

import threading
import time
from collections import deque
from collections.abc import Callable


class RateLimitedError(Exception):
    """Too many requests from one visitor. Nothing was done."""

    def __init__(self, retry_after_s: int) -> None:
        super().__init__(f"too many requests; try again in {retry_after_s} s")
        self.retry_after_s = retry_after_s


class RateLimiter:
    """At most ``limit`` hits per key in any ``window_s`` seconds."""

    def __init__(
        self, limit: int, window_s: float, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._limit = limit
        self._window_s = window_s
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> None:
        """Count one request, or raise ``RateLimitedError`` without counting it."""
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self._window_s:
                hits.popleft()
            if len(hits) >= self._limit:
                raise RateLimitedError(max(1, int(hits[0] + self._window_s - now + 0.999)))
            hits.append(now)
            if len(self._hits) > 10_000:
                self._forget_idle(now)

    def _forget_idle(self, now: float) -> None:
        """Drop visitors with no hits in the window, so memory stays bounded."""
        for key in [k for k, h in self._hits.items() if not h or h[-1] <= now - self._window_s]:
            del self._hits[key]
