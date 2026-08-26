from server import settings
from server.auth import rate_limit


def _spend(key: str, limit: int, window: float) -> None:
    rate_limit.limiter.clear("login", key)
    for _ in range(limit):
        rate_limit.limiter.check("login", key, limit, window)


def test_a_successful_login_forgives_the_account():
    limit, window = settings.RATE_LIMITS["login"]
    _spend("ana", limit, window)

    rate_limit.forgive("login", "ana")

    assert rate_limit.limiter.wait_for("login", "ana", limit, window) == 0


def test_a_successful_login_does_not_forgive_the_ip():
    limit, window = settings.RATE_LIMITS["login"]
    _spend("ana", limit, window)
    _spend("203.0.113.7", limit, window)

    rate_limit.forgive("login", "ana")

    assert rate_limit.limiter.wait_for("login", "203.0.113.7", limit, window) > 0
