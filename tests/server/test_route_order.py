"""No fixed path may sit below the wildcard that would swallow it.

FastAPI matches routes in declaration order, so `/{kind}/{name}` declared before
`/{kind}/transcription` makes the second unreachable: the request lands on the wildcard
with `name="transcription"` and answers a plausible 404 from a route nobody meant to call,
on a screen that then simply renders nothing.

The detector lives here and every router test imports it rather than copying it.
"""

from fastapi import APIRouter
from fastapi.routing import APIRoute


def _routes(router):
    return [route for route in router.routes if isinstance(route, APIRoute)]


def _wildcard_shadows(router) -> list[str]:
    """Every fixed path declared after a wildcard that already matches its shape."""
    shadowed: list[str] = []
    seen_wildcards: list[list[str]] = []

    for route in _routes(router):
        parts = route.path.strip("/").split("/")
        for pattern in seen_wildcards:
            if len(pattern) != len(parts):
                continue
            # A wildcard segment eats anything; a literal one has to match exactly.
            if all(
                declared.startswith("{") or declared == actual
                for declared, actual in zip(pattern, parts)
            ) and not any(part.startswith("{") for part in parts):
                shadowed.append(route.path)
        if any(part.startswith("{") for part in parts):
            seen_wildcards.append(parts)

    return shadowed


def test_the_detector_catches_the_bug_it_was_written_for():
    # A guard nobody has seen fail is a guard nobody knows works, so this pins the
    # detector itself against the exact shape that shipped broken.
    broken = APIRouter()

    @broken.get("/sessions/{session_id}")
    def detail(session_id: str) -> dict:
        return {}

    @broken.get("/sessions/accounts")
    def accounts() -> dict:
        return {}

    assert _wildcard_shadows(broken) == ["/sessions/accounts"]


def test_a_fixed_path_declared_first_is_not_reported():
    fine = APIRouter()

    @fine.get("/sessions/accounts")
    def accounts() -> dict:
        return {}

    @fine.get("/sessions/{session_id}")
    def detail(session_id: str) -> dict:
        return {}

    assert _wildcard_shadows(fine) == []
