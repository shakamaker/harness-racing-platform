"""Tests for the async token-bucket rate limiter."""

from __future__ import annotations

import asyncio
import time

import pytest

from harness_scraper.rate_limit import TokenBucket

pytestmark = pytest.mark.asyncio


class TestTokenBucket:
    async def test_immediate_within_capacity(self) -> None:
        bucket = TokenBucket(rate_per_minute=120)
        t0 = time.monotonic()
        await bucket.acquire()
        await bucket.acquire()
        # Should be near-instant (both tokens served from initial capacity).
        assert time.monotonic() - t0 < 0.05

    async def test_waits_when_empty(self) -> None:
        bucket = TokenBucket(rate_per_minute=600, capacity=1)  # 10/s refill, cap 1
        await bucket.acquire()  # drains the bucket
        t0 = time.monotonic()
        await bucket.acquire()  # must wait ~100ms for refill
        elapsed = time.monotonic() - t0
        assert elapsed >= 0.08
        assert elapsed < 0.5

    async def test_concurrent_consumers_share_budget(self) -> None:
        bucket = TokenBucket(rate_per_minute=600, capacity=2)
        async def take() -> float:
            t = time.monotonic()
            await bucket.acquire()
            return time.monotonic() - t

        results = await asyncio.gather(*(take() for _ in range(5)))
        # First 2 should be instant; remaining 3 should each wait ~100ms more.
        instant_count = sum(1 for r in results if r < 0.05)
        assert instant_count >= 2
        assert max(results) > 0.1

    async def test_invalid_rate_rejected(self) -> None:
        with pytest.raises(ValueError):
            TokenBucket(rate_per_minute=0)

    async def test_request_exceeds_capacity(self) -> None:
        bucket = TokenBucket(rate_per_minute=60, capacity=2)
        with pytest.raises(ValueError):
            await bucket.acquire(tokens=5)
