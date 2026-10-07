"""Every route of the application, and the least an account needs to reach it.

With students in a subject, the level a route declares is the difference between a student
reading the exercises they generated and a student reading the bank with its solutions. So
the levels are not left to each router's memory: this test reads the routes the application
actually mounts — the evaluation's and the tutor's included — works out the level each one
declares, and compares it with the table below, row by row.

A route with no row fails, and so does a row with no route: adding a route means deciding
its level here, in a diff somebody reads. The only routes the table does not list are the
administrator's, all under `/api/admin/` — and those must all be the administrator's.

The levels: `public` (nothing asked), `session` (an account; any membership is checked inside
the route), `viewer`/`editor`/`owner` (the membership, `auth.VIEW`/`EDIT`/`MANAGE`), and
`+evaluation`/`+tutor` for the optional function's own door beside it. Several routes decide
more inside — `POST /api/jobs` lets a student queue only a commission or a comparison — and
their own tests pin that; this one pins what each route declares.
"""

from fastapi.routing import APIRoute, APIWebSocketRoute

from server import auth
from server.app import app
from server.auth import deps

ADMIN_PREFIX = "/api/admin/"

LEVELS = {
    # Account and session — before any workspace exists.
    ("POST", "/api/auth/login"): "public",
    ("POST", "/api/auth/logout"): "public",
    ("POST", "/api/auth/logout-all"): "session",
    ("GET", "/api/auth/me"): "session",
    ("PATCH", "/api/auth/me"): "session",
    ("POST", "/api/auth/language"): "session",
    ("POST", "/api/auth/password"): "session",
    ("POST", "/api/auth/forgot"): "public",
    ("POST", "/api/auth/reset"): "public",
    ("GET", "/api/auth/invites/{token}"): "public",
    ("POST", "/api/auth/accept"): "public",
    # An account that exists entering a subject with a link: the link decides where.
    ("POST", "/api/auth/join"): "session",
    ("GET", "/api/maintenance"): "public",
    # The subjects an account belongs to; each one checks the membership inside.
    ("GET", "/api/workspaces"): "session",
    ("POST", "/api/workspaces"): "session",
    ("POST", "/api/workspaces/{slug}/activate"): "session",
    ("DELETE", "/api/workspaces/{slug}"): "owner",
    ("DELETE", "/api/workspaces/{slug}/membership"): "session",
    ("GET", "/api/workspaces/{slug}/summary"): "session",
    # The people of a subject: the list is a teacher's, and what a teacher may do to whom is
    # decided inside by the person's role; changing a role is the owner's.
    ("GET", "/api/members"): "editor",
    ("POST", "/api/members/bulk"): "editor",
    ("PATCH", "/api/members/{user_id:int}"): "owner",
    ("POST", "/api/members/{user_id:int}/disable"): "editor",
    ("POST", "/api/members/{user_id:int}/enable"): "editor",
    ("DELETE", "/api/members/{user_id:int}"): "editor",
    # A teacher's links: the class link and the subject's personal invitations.
    ("POST", "/api/members/end-course"): "owner",
    ("GET", "/api/members/uses"): "editor",
    ("GET", "/api/activity/weeks"): "editor",
    ("GET", "/api/activity/weeks/{week}"): "editor",
    ("POST", "/api/activity/weeks/{week}/digest"): "editor",
    ("PATCH", "/api/members/uses"): "editor",
    ("GET", "/api/members/class-link"): "editor",
    ("GET", "/api/members/class-link/link"): "editor",
    ("POST", "/api/members/class-link"): "editor",
    ("PATCH", "/api/members/class-link"): "editor",
    ("DELETE", "/api/members/class-link"): "editor",
    ("GET", "/api/members/invites"): "editor",
    ("POST", "/api/members/invites"): "editor",
    ("GET", "/api/members/invites/{invite_id:int}/link"): "editor",
    ("DELETE", "/api/members/invites/{invite_id:int}"): "editor",
    # The chain: its state is everybody's, its history and its writes the teachers'.
    ("GET", "/api/health"): "viewer",
    ("GET", "/api/pipeline"): "viewer",
    ("GET", "/api/pipeline/phases"): "viewer",
    ("GET", "/api/pipeline/scope"): "viewer",
    ("POST", "/api/pipeline/{artifact}/approve"): "editor",
    ("POST", "/api/pipeline/{artifact}/reopen"): "editor",
    ("GET", "/api/pipeline/{artifact}/history"): "editor",
    ("POST", "/api/pipeline/{artifact}/restore"): "editor",
    # The subject's description and its types of exercise, which the generate form reads.
    ("GET", "/api/context"): "viewer",
    ("PUT", "/api/context"): "editor",
    ("POST", "/api/context/adopt-draft"): "editor",
    ("GET", "/api/profile"): "viewer",
    ("POST", "/api/profile/validate"): "editor",
    ("PUT", "/api/profile"): "editor",
    # The syllabus: a student reads it, nobody but a teacher writes it — nor reads the
    # document verbatim, the construction's working copy.
    ("GET", "/api/kg"): "viewer",
    ("GET", "/api/kg/graph"): "viewer",
    ("GET", "/api/kg/raw"): "editor",
    ("PUT", "/api/kg/raw"): "editor",
    ("GET", "/api/kg/neighbours"): "viewer",
    ("GET", "/api/kg/descriptions"): "viewer",
    ("PUT", "/api/kg/descriptions"): "editor",
    ("POST", "/api/kg/domains"): "editor",
    ("PATCH", "/api/kg/domains"): "editor",
    ("POST", "/api/kg/domains/delete"): "editor",
    ("PUT", "/api/kg/domains/order"): "editor",
    ("POST", "/api/kg/concepts"): "editor",
    ("PATCH", "/api/kg/concepts"): "editor",
    ("POST", "/api/kg/concepts/delete"): "editor",
    ("POST", "/api/kg/relations/edges"): "editor",
    ("POST", "/api/kg/relations/edges/delete"): "editor",
    ("GET", "/api/kg/curriculum"): "viewer",
    ("PUT", "/api/kg/curriculum"): "editor",
    # The bank carries its solutions, and the raw documents are the construction's: both
    # are closed to a student, reads included.
    ("GET", "/api/bank"): "editor",
    ("GET", "/api/bank/coverage"): "editor",
    ("PATCH", "/api/bank/{item_id}"): "editor",
    ("PUT", "/api/bank/{item_id}/concepts"): "editor",
    ("DELETE", "/api/bank/{item_id}"): "editor",
    ("GET", "/api/raw"): "editor",
    ("GET", "/api/raw/{kind}/transcription"): "editor",
    ("POST", "/api/raw/{kind}/transcription"): "editor",
    ("GET", "/api/raw/{kind}/transcription/{name}"): "editor",
    ("POST", "/api/raw/{kind}/transcription/{name}"): "editor",
    ("PUT", "/api/raw/{kind}/transcription/{name}/{index}"): "editor",
    ("DELETE", "/api/raw/{kind}/transcription/{name}/{index}"): "editor",
    ("POST", "/api/raw/{kind}"): "editor",
    ("DELETE", "/api/raw/{kind}/{name}"): "editor",
    # The queue: a student submits and cancels by kind and by author, decided inside.
    ("POST", "/api/jobs"): "viewer",
    ("GET", "/api/jobs"): "viewer",
    ("GET", "/api/jobs/current"): "viewer",
    ("GET", "/api/jobs/allowance"): "viewer",
    ("GET", "/api/jobs/{job_id}"): "viewer",
    ("DELETE", "/api/jobs/{job_id}"): "viewer",
    ("GET", "/api/events"): "viewer",
    # One's own exercises, deleting them included; taking one into the bank is a teacher's.
    ("GET", "/api/generations"): "viewer",
    ("GET", "/api/generations/{generation_id}"): "viewer",
    ("POST", "/api/generations/{generation_id}/promote"): "editor",
    ("DELETE", "/api/generations/{generation_id}"): "viewer",
    # The socket authenticates before it accepts (`authenticate_socket`).
    ("WS", "/ws"): "public",
    # The evaluation: whoever it is open to launches and judges their own sessions.
    ("POST", "/api/evaluation"): "viewer+evaluation",
    ("GET", "/api/evaluation"): "viewer+evaluation",
    ("DELETE", "/api/evaluation"): "viewer+evaluation",
    ("GET", "/api/evaluation/{session_id}"): "viewer+evaluation",
    ("POST", "/api/evaluation/{session_id}/triage"): "viewer+evaluation",
    ("POST", "/api/evaluation/{session_id}/decline"): "viewer+evaluation",
    ("POST", "/api/evaluation/{session_id}/choice"): "viewer+evaluation",
    ("POST", "/api/evaluation/{session_id}/rating"): "viewer+evaluation",
    ("GET", "/api/stage-evaluations/{artifact}"): "viewer+evaluation",
    ("POST", "/api/stage-evaluations/{artifact}/opened"): "editor+evaluation",
    ("PUT", "/api/stage-evaluations/{artifact}"): "editor+evaluation",
    # The tutor: a student's conversations; the subject's criteria are its teachers'.
    ("GET", "/api/tutor"): "viewer+tutor",
    ("GET", "/api/tutor/conversations"): "viewer+tutor",
    ("POST", "/api/tutor/conversations"): "viewer+tutor",
    ("GET", "/api/tutor/criteria"): "editor+tutor",
    ("PUT", "/api/tutor/criteria"): "editor+tutor",
    ("POST", "/api/tutor/criteria/build"): "editor+tutor",
    ("GET", "/api/tutor/syllabus"): "viewer+tutor",
    ("GET", "/api/tutor/notes"): "viewer+tutor",
    ("GET", "/api/tutor/notes/page"): "viewer+tutor",
    ("GET", "/api/tutor/conversations/{conversation_id}"): "viewer+tutor",
    ("POST", "/api/tutor/conversations/{conversation_id}/messages"): "viewer+tutor",
    ("POST", "/api/tutor/conversations/{conversation_id}/retry"): "viewer+tutor",
    ("DELETE", "/api/tutor/conversations/{conversation_id}/turn"): "viewer+tutor",
    ("DELETE", "/api/tutor/conversations/{conversation_id}"): "viewer+tutor",
    # The built client, which knows nothing a session has not given it.
    ("GET", "/{path:path}"): "public",
}

_MEMBERSHIP = {
    auth.VIEW.dependency: "viewer",
    auth.EDIT.dependency: "editor",
    auth.MANAGE.dependency: "owner",
}
_RANK = {"viewer": 1, "editor": 2, "owner": 3}
_FUNCTIONS = {auth.EVALUATION.dependency: "evaluation", auth.TUTOR.dependency: "tutor"}


def _routes():
    """Every HTTP and WebSocket route the application mounts, in its included routers too."""
    for route in app.routes:
        router = getattr(route, "original_router", None)
        candidates = router.routes if router is not None else [route]
        for candidate in candidates:
            if isinstance(candidate, (APIRoute, APIWebSocketRoute)):
                yield candidate


def _called(dependant, seen: set) -> set:
    """Collect every callable a route depends on, however deep."""
    for dependency in dependant.dependencies:
        seen.add(dependency.call)
        _called(dependency, seen)
    return seen


def _level(route) -> str:
    """Name the least a request needs to reach this route, as it declares it."""
    called = _called(route.dependant, set())
    levels = [_MEMBERSHIP[call] for call in called if call in _MEMBERSHIP]
    if levels:
        level = max(levels, key=_RANK.__getitem__)
    elif deps.require_admin in called:
        level = "admin"
    elif deps.current_user in called:
        level = "session"
    else:
        level = "public"
    functions = sorted(_FUNCTIONS[call] for call in called if call in _FUNCTIONS)
    return "+".join([level, *functions])


def _declared() -> dict[tuple[str, str], str]:
    """Map every route and method to the level it declares."""
    found: dict[tuple[str, str], str] = {}
    for route in _routes():
        methods = getattr(route, "methods", None) or {"WS"}
        for method in methods:
            found[(method, route.path)] = _level(route)
    return found


def test_every_route_but_the_administrators_has_a_row():
    declared = {key for key in _declared() if not key[1].startswith(ADMIN_PREFIX)}

    assert sorted(declared - set(LEVELS)) == [], "rutas sin fila en la tabla"
    assert sorted(set(LEVELS) - declared) == [], "filas sin ruta"


def test_every_route_declares_the_level_of_its_row():
    declared = _declared()
    wrong = {
        key: (declared[key], expected)
        for key, expected in LEVELS.items()
        if key in declared and declared[key] != expected
    }

    assert wrong == {}


def test_every_administrators_route_is_the_administrators():
    declared = _declared()
    admin = {key: level for key, level in declared.items() if key[1].startswith(ADMIN_PREFIX)}

    assert admin, "no se encontró ninguna ruta del administrador"
    assert {key: level for key, level in admin.items() if level != "admin"} == {}


def test_what_a_student_may_not_read_takes_a_teacher():
    """The rows the class depends on, named once more so a reader sees why they are there."""
    for key in (
        ("GET", "/api/bank"),
        ("GET", "/api/bank/coverage"),
        ("GET", "/api/raw"),
        ("GET", "/api/raw/{kind}/transcription/{name}"),
        ("GET", "/api/kg/raw"),
        ("GET", "/api/pipeline/{artifact}/history"),
    ):
        assert LEVELS[key] == "editor", key
    writes = [
        key for key, level in LEVELS.items()
        if key[1].startswith("/api/kg") and key[0] != "GET"
    ]
    assert writes and all(LEVELS[key] == "editor" for key in writes)
