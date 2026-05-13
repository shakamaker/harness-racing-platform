"""Async token-bucket rate limiter (CLAUDE.md §4.1.5).

Default budget is 30 requests/minute, shared across all states. Concurrent
fetchers ``await`` ``acquire()``; if the bucket is empty they sleep until the
next token is available.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass(slots=True)
class _BucketState:
    tokens: float
    last_refill_ts: float


class TokenBucket:
    """Simple monotonic-clock token bucket.

    Not thread-safe — owns an ``asyncio.Lock`` for cross-task coordination
    within a single event loop.
    """

    def __init__(self, *, rate_per_minute: int, capacity: int | None = None) -> None:
        if rate_per_minute <= 0:
            raise ValueError("rate_per_minute must be positive")
        self._rate_per_s = rate_per_minute / 60.0
        self._capacity = float(capacity if capacity is not None else rate_per_minute)
        self._state = _BucketState(tokens=self._capacity, last_refill_ts=time.monotonic())
        self._lock = asyncio.Lock()

    @property
    def capacity(self) -> float:
        return self._capacity

    async def acquire(self, tokens: float = 1.0) -> None:
        if tokens > self._capacity:
            raise ValueError(f"requested {tokens} tokens > capacity {self._capacity}")
        while True:
            async with self._lock:
                wait_s = self._take_or_calc_wait(tokens)
                if wait_s == 0.0:
                    return
            # Sleep outside the lock so other tasks can refill / consume.
            await asyncio.sleep(wait_s)

    def _take_or_calc_wait(self, tokens: float) -> float:
        now = time.monotonic()
        elapsed = now - self._state.last_refill_ts
        self._state.tokens = min(
            self._capacity, self._state.tokens + elapsed * self._rate_per_s
        )
        self._state.last_refill_ts = now
        if self._state.tokens >= tokens:
            self._state.tokens -= tokens
            return 0.0
        missing = tokens - self._state.tokens
        return missing / self._rate_per_s
