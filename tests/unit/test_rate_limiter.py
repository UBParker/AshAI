"""Unit tests for the in-memory sliding-window rate limiter."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from helperai.api.rate_limiter import SlidingWindowRateLimiter, _MAX_TRACKED_KEYS


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_valid_construction(self):
        lim = SlidingWindowRateLimiter(max_requests=10, window_seconds=60)
        assert lim.max_requests == 10
        assert lim.window_seconds == 60

    def test_zero_requests_raises(self):
        with pytest.raises(ValueError, match="max_requests"):
            SlidingWindowRateLimiter(max_requests=0)

    def test_negative_requests_raises(self):
        with pytest.raises(ValueError, match="max_requests"):
            SlidingWindowRateLimiter(max_requests=-5)

    def test_zero_window_raises(self):
        with pytest.raises(ValueError, match="window_seconds"):
            SlidingWindowRateLimiter(max_requests=10, window_seconds=0)

    def test_negative_window_raises(self):
        with pytest.raises(ValueError, match="window_seconds"):
            SlidingWindowRateLimiter(max_requests=10, window_seconds=-1)


# ---------------------------------------------------------------------------
# Basic allow / deny behaviour
# ---------------------------------------------------------------------------


class TestCheckBehaviour:
    def test_first_request_allowed(self):
        lim = SlidingWindowRateLimiter(max_requests=5)
        allowed, retry_after = lim.check("client-a")
        assert allowed is True
        assert retry_after == 0.0

    def test_requests_within_limit_all_allowed(self):
        lim = SlidingWindowRateLimiter(max_requests=3)
        for _ in range(3):
            allowed, _ = lim.check("client-a")
            assert allowed is True

    def test_request_exceeding_limit_denied(self):
        lim = SlidingWindowRateLimiter(max_requests=3)
        for _ in range(3):
            lim.check("client-a")
        allowed, retry_after = lim.check("client-a")
        assert allowed is False
        assert retry_after > 0

    def test_different_clients_are_independent(self):
        lim = SlidingWindowRateLimiter(max_requests=1)
        allowed_a, _ = lim.check("client-a")
        allowed_b, _ = lim.check("client-b")
        assert allowed_a is True
        assert allowed_b is True  # different key, different bucket

    def test_denied_after_limit_for_one_client_only(self):
        lim = SlidingWindowRateLimiter(max_requests=1)
        lim.check("client-a")  # consume the single slot for A
        denied, _ = lim.check("client-a")
        allowed, _ = lim.check("client-b")
        assert denied is False
        assert allowed is True

    def test_retry_after_positive_when_denied(self):
        lim = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
        lim.check("x")
        _, retry_after = lim.check("x")
        assert 0 < retry_after <= 60

    def test_window_expiry_allows_new_requests(self):
        """Timestamps older than the window are evicted; new requests succeed."""
        lim = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)

        # Artificially place a "past" timestamp in the bucket
        past = time.monotonic() - 61  # well outside the 60-second window
        with lim._lock:
            from collections import deque
            lim._buckets["client"] = deque([past])

        # The past timestamp should be evicted → request succeeds
        allowed, _ = lim.check("client")
        assert allowed is True


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


class TestReset:
    def test_reset_specific_key(self):
        lim = SlidingWindowRateLimiter(max_requests=1)
        lim.check("client-a")
        lim.check("client-b")
        lim.reset("client-a")
        allowed, _ = lim.check("client-a")
        assert allowed is True
        # client-b should still be consumed
        denied, _ = lim.check("client-b")
        assert denied is False

    def test_reset_all_keys(self):
        lim = SlidingWindowRateLimiter(max_requests=1)
        lim.check("client-a")
        lim.check("client-b")
        lim.reset()
        for key in ("client-a", "client-b"):
            allowed, _ = lim.check(key)
            assert allowed is True

    def test_reset_nonexistent_key_is_noop(self):
        lim = SlidingWindowRateLimiter(max_requests=5)
        lim.reset("ghost")  # should not raise


# ---------------------------------------------------------------------------
# Memory cap
# ---------------------------------------------------------------------------


class TestMemoryCap:
    def test_old_client_evicted_when_at_capacity(self):
        """When _MAX_TRACKED_KEYS is reached, the oldest key is evicted."""
        lim = SlidingWindowRateLimiter(max_requests=100)

        # Fill up to the limit
        for i in range(_MAX_TRACKED_KEYS):
            lim.check(f"client-{i}")

        assert len(lim._buckets) == _MAX_TRACKED_KEYS

        # One more unique client → oldest evicted, size stays bounded
        lim.check("new-client")
        assert len(lim._buckets) == _MAX_TRACKED_KEYS
        # The very first client should have been evicted
        assert "client-0" not in lim._buckets
        assert "new-client" in lim._buckets


# ---------------------------------------------------------------------------
# Thread safety (smoke test)
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_checks_do_not_raise(self):
        import threading

        lim = SlidingWindowRateLimiter(max_requests=500)
        errors: list[Exception] = []

        def worker():
            try:
                for _ in range(50):
                    lim.check("shared-key")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
