from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class RateLimitEntry:
    timestamps: list[float] = field(default_factory=list)


class SlidingWindowRateLimiter:
    """Sliding window rate limiter for webhook endpoints."""

    def __init__(
        self,
        max_requests: int = 60,
        window_seconds: int = 60,
    ) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._buckets: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        entry = self._buckets[key]
        cutoff = now - self._window

        entry.timestamps = [t for t in entry.timestamps if t > cutoff]

        if len(entry.timestamps) >= self._max:
            return False

        entry.timestamps.append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.monotonic()
        entry = self._buckets[key]
        cutoff = now - self._window
        active = [t for t in entry.timestamps if t > cutoff]
        return max(0, self._max - len(active))
