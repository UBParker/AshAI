"""In-memory sliding-window rate limiter for FastAPI."""

from __future__ import annotations

import logging
import time
from collections import deque
from threading import Lock

logger = logging.getLogger(__name__)

# Maximum number of distinct client keys to track simultaneously.
# When this ceiling is reached the oldest entry is evicted to bound memory use.
_MAX_TRACKED_KEYS = 10_000


class SlidingWindowRateLimiter:
    """Thread-safe per-key sliding-window rate limiter.

    Tracks the timestamps of recent requests for each key (e.g. client IP or
    the string ``"global"``).  When the number of requests in the current
    window exceeds *max_requests* the limiter signals that the key is throttled
    and returns how many seconds the caller should wait before retrying.
    """

    def __init__(self, max_requests: int, window_seconds: int = 60) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # Insertion-ordered dict lets us evict the oldest key cheaply.
        self._buckets: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str) -> tuple[bool, float]:
        """Check whether a request is allowed.

        Side-effect: records the current timestamp for *key* if allowed.

        Returns:
            (allowed, retry_after_seconds) — when *allowed* is ``False``,
            *retry_after_seconds* is the number of seconds until the oldest
            recorded request expires and one more request would be permitted.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                # Evict the oldest tracked client if at capacity.
                if len(self._buckets) >= _MAX_TRACKED_KEYS:
                    oldest_key = next(iter(self._buckets))
                    del self._buckets[oldest_key]
                bucket = deque()
                self._buckets[key] = bucket

            # Drop timestamps that have fallen outside the window.
            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            if len(bucket) >= self.max_requests:
                # Tell the caller when the oldest request will expire.
                retry_after = self.window_seconds - (now - bucket[0])
                return False, max(0.0, retry_after)

            bucket.append(now)
            return True, 0.0

    def reset(self, key: str | None = None) -> None:
        """Clear rate-limit state.

        Pass *key* to reset a single client; omit (or pass ``None``) to reset
        all tracked state.  Primarily useful in tests.
        """
        with self._lock:
            if key is None:
                self._buckets.clear()
            else:
                self._buckets.pop(key, None)
