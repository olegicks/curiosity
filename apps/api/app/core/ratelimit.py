"""In-process fixed-window rate limiter (docs/spec/09 §9.4).

Assumes a single API instance; swap the implementation behind ``RateLimiter``
if the API is scaled horizontally.
"""

import math
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.core.errors import RateLimitedError


@dataclass(frozen=True)
class RateRule:
    name: str
    limit: int
    window_seconds: int


class RateLimiter(Protocol):
    def hit(self, rule: RateRule, key: str, now: datetime) -> None:
        """Count one request; raise RateLimitedError when the limit is exceeded."""
        ...


class FixedWindowRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[tuple[str, str, int], int] = {}

    def hit(self, rule: RateRule, key: str, now: datetime) -> None:
        ts = now.timestamp()
        window = int(ts // rule.window_seconds)
        bucket = (rule.name, key, window)
        with self._lock:
            self._prune(rule.name, window)
            count = self._counts.get(bucket, 0) + 1
            self._counts[bucket] = count
        if count > rule.limit:
            retry_after = math.ceil((window + 1) * rule.window_seconds - ts)
            raise RateLimitedError(headers={"Retry-After": str(max(retry_after, 1))})

    def _prune(self, name: str, current_window: int) -> None:
        stale = [b for b in self._counts if b[0] == name and b[2] < current_window]
        for bucket in stale:
            del self._counts[bucket]


class DisabledRateLimiter:
    def hit(self, rule: RateRule, key: str, now: datetime) -> None:
        return None
