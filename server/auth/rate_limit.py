"""A sliding window per (bucket, key), in memory.

One process serves the whole installation, so a dict behind a lock is the correct amount
of machinery. When the API grows to several processes this is the module that changes,
and only this one.

Two keys per attempt, never one: the IP stops a spray across many accounts, and the
account stops a spray from many IPs. Either alone leaves the other attack open.

`installation` and `deps` are imported inside the functions that need them, because this
module sits between the two halves of their import cycle.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter:
    """The attempts of every (bucket, key), as timestamps behind one lock."""

    def __init__(self) -> None:
        """Start with nothing recorded."""
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, bucket: str, key: str, limit: int, window: float) -> float:
        """Seconds to wait before this attempt is allowed; 0.0 when it is allowed now.

        Records the attempt when it is allowed, which is what `wait_for` does not.
        """
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

    def wait_for(self, bucket: str, key: str, limit: int, window: float) -> float:
        """Like `check`, without recording an attempt: how long this key is locked out."""
        if not key:
            return 0.0
        now = time.monotonic()
        with self._lock:
            hits = self._hits.get((bucket, key))
            if not hits:
                return 0.0
            live = [hit for hit in hits if now - hit <= window]
            if len(live) < limit:
                return 0.0
            return max(0.0, window - (now - live[0]))

    def clear(self, bucket: str, key: str) -> None:
        """Called after a success, so a correct password forgives the failed attempts."""
        with self._lock:
            self._hits.pop((bucket, key), None)

    def sweep(self, window: float = 3600.0) -> None:
        """Drop the keys with no attempt inside the window.

        Nothing else evicts entries: a spray against thousands of names would grow the
        dict without bound. Called from the same paths that consume the limiter.
        """
        now = time.monotonic()
        with self._lock:
            for key in [k for k, hits in self._hits.items() if not hits or now - hits[-1] > window]:
                self._hits.pop(key, None)


limiter = RateLimiter()

FALLBACK_LIMITS: dict[str, tuple[int, float]] = {"accept": (10, 3600.0)}


def limits(bucket: str) -> tuple[int, float]:
    """Return the (limit, window) this bucket is configured with."""
    from .. import installation

    declared = installation.RATE_LIMITS.get(bucket)
    return declared if declared is not None else FALLBACK_LIMITS[bucket]


def throttle(bucket: str, request: Request, account: str) -> None:
    """Record an attempt against both the caller's address and the account.

    Raises HTTPException 429 with `Retry-After` as soon as either key is over its limit.
    It lives here rather than in the router that first needed it because there is now
    more than one — invitations moved to the administration panel and would otherwise
    have arrived there with no limit, or with a second copy of this.
    """
    from .deps import client_ip

    limit, window = limits(bucket)
    limiter.sweep()
    for key in (client_ip(request), account):
        wait = limiter.check(bucket, key, limit, window)
        if wait > 0:
            raise HTTPException(
                429,
                f"Demasiados intentos. Vuelve a probar en {int(wait) + 1} segundos.",
                headers={"Retry-After": str(int(wait) + 1)},
            )


def locked_seconds(bucket: str, account: str) -> float:
    """How long the account half of the lock-out still has to run, without touching it.

    What the panel shows beside a name, and what «Desbloquear» clears. The IP half is not
    addressed by account and is not what a locked-out person is asking about.
    """
    limit, window = limits(bucket)
    return limiter.wait_for(bucket, account, limit, window)


def unlock(bucket: str, account: str) -> None:
    """Clear the account half of a bucket."""
    limiter.clear(bucket, account)


def forgive(bucket: str, account: str) -> None:
    """Forgive the account half after a success, and deliberately not the IP half.

    Clearing the IP too is what the login route used to do, and it handed the whole IP
    leg to anyone holding a single valid account: eight guesses against every other name,
    then a login of one's own, then eight more, from the same address. The IP half is
    what stops a spray across many accounts, and it expires on its own with the window.
    """
    limiter.clear(bucket, account)
