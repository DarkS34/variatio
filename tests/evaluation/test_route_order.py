"""No fixed path may sit below the wildcard that would swallow it.

FastAPI matches routes in declaration order, so `/evaluations/{session_id}` declared before
`/evaluations/accounts` makes the second unreachable: the request lands on `session_detail`
with `session_id="accounts"` and answers 404 «No existe la sesión 'accounts'».

That is the worst shape a bug can have — a plausible 404 from a route nobody meant to call,
on a screen that then simply renders nothing. It cost one round of «sigo sin ver la opción»,
and it will cost another the next time somebody appends a route to the end of the file,
which is where anybody would naturally put one.
"""

from fastapi.routing import APIRoute

from evaluation.api.admin import router as admin_router
from evaluation.api.router import router as evaluation_router


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


def test_the_admin_evaluation_routes_are_all_reachable():
    assert _wildcard_shadows(admin_router) == []


def test_the_evaluation_routes_are_all_reachable():
    assert _wildcard_shadows(evaluation_router) == []


def test_the_detector_catches_the_bug_it_was_written_for():
    # A guard nobody has seen fail is a guard nobody knows works, so this pins the
    # detector itself against the exact shape that shipped broken.
    from fastapi import APIRouter

    broken = APIRouter()

    @broken.get("/evaluations/{session_id}")
    def detail(session_id: str) -> dict:
        return {}

    @broken.get("/evaluations/accounts")
    def accounts() -> dict:
        return {}

    assert _wildcard_shadows(broken) == ["/evaluations/accounts"]


def test_a_fixed_path_declared_first_is_not_reported():
    from fastapi import APIRouter

    fine = APIRouter()

    @fine.get("/evaluations/accounts")
    def accounts() -> dict:
        return {}

    @fine.get("/evaluations/{session_id}")
    def detail(session_id: str) -> dict:
        return {}

    assert _wildcard_shadows(fine) == []
