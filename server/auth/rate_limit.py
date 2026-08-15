"""A sliding window per (bucket, key), in memory.

One process serves the whole installation, so a dict behind a lock is the correct
amount of machinery — the plan says as much: Postgres or memory, not Redis. When the
API grows to several processes this is the module that changes, and only this one.

Two keys per attempt, never one: the IP stops a spray across many accounts, and the
account stops a spray from many IPs. Either alone leaves the other attack open.
"""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, bucket: str, key: str, limit: int, window: float) -> float:
        """Seconds to wait before this attempt is allowed; 0.0 when it is allowed now."""
        if not key:
            return 0.0
        now = time.monotonic()
        with self._lock:
            hits = self._hits[(bucket, key)]
            while hits and now - hits[0] > window:
                hits.popleft()
            if len(hits) >= limit:
                return max(0.0, window - (now - hits[0]))
            hits.append(now)
            return 0.0

    def clear(self, bucket: str, key: str) -> None:
        """Called after a success, so a correct password forgives the failed attempts."""
        with self._lock:
            self._hits.pop((bucket, key), None)

    # Nothing evicts entries otherwise: a spray against thousands of addresses would grow
    # the dict without bound. Called from the same paths that consume the limiter.
    def sweep(self, window: float = 3600.0) -> None:
        now = time.monotonic()
        with self._lock:
            for key in [k for k, hits in self._hits.items() if not hits or now - hits[-1] > window]:
                self._hits.pop(key, None)


limiter = RateLimiter()
