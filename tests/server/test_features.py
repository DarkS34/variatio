"""Who the evaluation and the tutor are for: nobody, every account, or a list.

Asked for on 2026-10-03, when one branch came to carry both: the administrator switches each
function from the panel, an account the function is not open to is refused on every route of
it, and an invitation can list its holder from the first moment. The administrator gets no
bypass — the membership check has one, this has none.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from starlette.responses import Response

from server import auth, features
from server.auth import passwords, rate_limit
from server.auth.deps import require_feature
from server.db import identity
from server.db.models import Base
from server.routers import admin as admin_routes
from server.routers.admin import FeatureBody, InviteBody, InviteEditBody
from server.routers.auth import AcceptBody, _me, accept_invite

IP = "10.0.0.3"


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(
        identity, "now", lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    monkeypatch.setattr(passwords, "hash_password", lambda password: "hashed")
    yield session
    session.close()


@pytest.fixture(autouse=True)
def forget_the_attempts():
    for bucket in ("invite", "accept"):
        for key in (IP, "admin"):
            rate_limit.limiter.clear(bucket, key)
    yield


def _user(db, username: str, is_admin: bool = False):
    return identity.create_user(
        db, username=username, name=username, password_hash="x", is_admin=is_admin
    )


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"host", b"localhost"), (b"origin", b"http://localhost")],
            "client": (IP, 1234),
            "scheme": "http",
            "server": ("localhost", 8000),
            "query_string": b"",
        }
    )


# THE THREE MODES ---------------------------------------------------------------------------------


def test_a_function_nobody_has_set_is_off_for_everybody(db):
    ana = _user(db, "ana")

    assert features.mode(db, features.TUTOR) == features.OFF
    assert features.for_user(db, ana) == {"evaluation": False, "tutor": False}


def test_all_opens_a_function_to_every_account_and_only_that_function(db):
    ana = _user(db, "ana")

    features.set_mode(db, features.TUTOR, features.ALL)

    assert features.for_user(db, ana) == {"evaluation": False, "tutor": True}


def test_selected_opens_a_function_to_the_listed_accounts_alone(db):
    ana, bea = _user(db, "ana"), _user(db, "bea")

    features.set_mode(db, features.EVALUATION, features.SELECTED)
    features.set_listed(db, features.EVALUATION, [ana.id])

    assert features.enabled(db, ana, features.EVALUATION)
    assert not features.enabled(db, bea, features.EVALUATION)


def test_the_list_survives_a_change_of_mode_and_is_replaced_whole(db):
    ana, bea = _user(db, "ana"), _user(db, "bea")
    features.set_listed(db, features.TUTOR, [ana.id])

    features.set_mode(db, features.TUTOR, features.ALL)
    features.set_mode(db, features.TUTOR, features.SELECTED)
    assert features.listed(db, features.TUTOR) == [ana.id]

    features.set_listed(db, features.TUTOR, [bea.id])
    assert features.listed(db, features.TUTOR) == [bea.id]


# THE DEPENDENCY ----------------------------------------------------------------------------------


def test_a_route_refuses_an_account_the_function_is_not_open_to_with_a_stable_code(db):
    ana = _user(db, "ana")
    check = require_feature(features.TUTOR)

    with pytest.raises(HTTPException) as refused:
        check(user=ana, session=db)

    assert refused.value.status_code == 403
    assert refused.value.headers == {"X-Error-Code": features.OFF_CODE}


def test_the_administrator_gets_no_bypass(db):
    admin = _user(db, "admin", is_admin=True)
    features.set_mode(db, features.TUTOR, features.SELECTED)

    with pytest.raises(HTTPException):
        require_feature(features.TUTOR)(user=admin, session=db)

    features.list_account(db, features.TUTOR, admin.id)
    assert require_feature(features.TUTOR)(user=admin, session=db) is None


def test_the_routers_of_both_functions_declare_their_dependency():
    from evaluation.api import router as evaluation_router
    from evaluation.api import stages as stages_router
    from tutor.api import router as tutor_router

    def declared(router):
        return [dependency.dependency for dependency in router.dependencies]

    assert auth.EVALUATION.dependency in declared(evaluation_router.router)
    assert auth.EVALUATION.dependency in declared(stages_router.router)
    assert auth.TUTOR.dependency in declared(tutor_router.router)


def test_the_generic_jobs_route_is_no_way_round_the_evaluation_s_switch(db):
    from types import SimpleNamespace

    from server.routers import jobs as jobs_router

    ana = _user(db, "ana")
    access = SimpleNamespace(user=ana, ws=None, role="viewer")

    with pytest.raises(HTTPException) as refused:
        jobs_router.submit(jobs_router.JobBody(kind="evaluate"), access=access, db=db)

    assert refused.value.status_code == 403
    assert refused.value.headers == {"X-Error-Code": features.OFF_CODE}


def test_the_session_says_which_functions_are_open_to_the_account(db):
    ana = _user(db, "ana")
    features.set_mode(db, features.EVALUATION, features.ALL)

    assert _me(db, ana)["features"] == {"evaluation": True, "tutor": False}


# THE PANEL'S ROUTES ------------------------------------------------------------------------------


def test_the_administrator_sets_a_mode_and_its_list_from_the_panel(db):
    admin, ana = _user(db, "admin", is_admin=True), _user(db, "ana")

    answer = admin_routes.set_feature(
        "tutor", FeatureBody(mode="selected", accounts=[ana.id]), admin=admin, db=db
    )

    assert answer["features"]["tutor"] == {"mode": "selected", "accounts": [ana.id]}
    assert admin_routes.read_features(db=db) == answer


def test_a_mode_sent_alone_keeps_the_list(db):
    admin, ana = _user(db, "admin", is_admin=True), _user(db, "ana")
    admin_routes.set_feature(
        "tutor", FeatureBody(mode="selected", accounts=[ana.id]), admin=admin, db=db
    )

    answer = admin_routes.set_feature("tutor", FeatureBody(mode="off"), admin=admin, db=db)

    assert answer["features"]["tutor"] == {"mode": "off", "accounts": [ana.id]}


@pytest.mark.parametrize(
    ("feature", "body", "status"),
    [
        ("chat", {"mode": "all"}, 404),
        ("tutor", {"mode": "some"}, 422),
        ("tutor", {"mode": "selected", "accounts": [999]}, 422),
    ],
)
def test_an_unknown_function_mode_or_account_is_refused(db, feature, body, status):
    admin = _user(db, "admin", is_admin=True)

    with pytest.raises(HTTPException) as refused:
        admin_routes.set_feature(feature, FeatureBody(**body), admin=admin, db=db)

    assert refused.value.status_code == status
    assert features.snapshot(db)["tutor"] == {"mode": "off", "accounts": []}


# THE INVITATION ----------------------------------------------------------------------------------


def _invite(db, admin, **terms) -> dict:
    terms = {"profile": "student", **terms}
    return admin_routes.create_invite(InviteBody(**terms), _request(), admin=admin, db=db)


def _redeem(db, link: str, username: str):
    accept_invite(
        AcceptBody(
            token=link.split("token=")[1],
            username=username,
            name=username,
            password="una-contraseña-larga",
        ),
        _request(),
        Response(),
        session=db,
    )
    return identity.get_user(db, username)


def test_an_invitation_lists_the_new_account_for_the_functions_it_names(db):
    admin = _user(db, "admin", is_admin=True)
    features.set_mode(db, features.TUTOR, features.SELECTED)
    minted = _invite(db, admin, features=["tutor"])

    assert minted["invite"]["features"] == ["tutor"]
    ana = _redeem(db, minted["link"], "ana")

    assert features.for_user(db, ana) == {"evaluation": False, "tutor": True}


def test_an_invitation_that_names_nothing_lists_nobody(db):
    admin = _user(db, "admin", is_admin=True)
    features.set_mode(db, features.TUTOR, features.SELECTED)

    ana = _redeem(db, _invite(db, admin)["link"], "ana")

    assert features.listed(db, features.TUTOR) == []
    assert not features.enabled(db, ana, features.TUTOR)


def test_an_invitation_refuses_a_function_that_does_not_exist(db):
    admin = _user(db, "admin", is_admin=True)

    with pytest.raises(HTTPException) as refused:
        _invite(db, admin, features=["chat"])

    assert refused.value.status_code == 422


def test_the_functions_of_an_unused_invitation_can_be_changed(db):
    admin = _user(db, "admin", is_admin=True)
    minted = _invite(db, admin, features=["tutor"], expires_at=datetime.now(timezone.utc) + timedelta(days=2))

    edited = admin_routes.edit_invite(
        minted["invite"]["id"], InviteEditBody(features=["evaluation"]), admin=admin, db=db
    )

    assert edited["invite"]["features"] == ["evaluation"]


# THE MODELS A SWITCHED-OFF FUNCTION NAMES --------------------------------------------------------


def test_a_function_that_is_off_does_not_ask_for_its_own_model(db, monkeypatch):
    from server.routers import health

    monkeypatch.setattr(
        health.inference,
        "required_models",
        lambda: {"GUARDRAIL_LLM": "guardian", "tutor.models.reply": "a-tutor-model"},
    )

    assert health._required(db) == {"GUARDRAIL_LLM": "guardian"}

    features.set_mode(db, features.TUTOR, features.SELECTED)
    assert health._required(db)["tutor.models.reply"] == "a-tutor-model"
