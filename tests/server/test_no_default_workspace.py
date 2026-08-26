from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from server import settings
from server.auth import deps
from variatio.core import paths


@pytest.fixture
def nobody(monkeypatch):
    """An account that belongs to no workspace, which is a normal account since 2026-08-26."""
    monkeypatch.setattr(deps.identity, "memberships_for", lambda *args: [])
    monkeypatch.setattr(deps.identity, "membership", lambda *args: None)
    return SimpleNamespace(id=2, is_admin=False, active_workspace_id=None)


def test_an_account_with_no_membership_lands_nowhere(nobody):
    assert deps.current_workspace_for(None, nobody) is None


# The one that used to be the exception. An administrator with no membership was dropped
# into the first workspace of the installation, which is entering somebody else's instance
# without having asked for it; the switcher lists every one of them for an administrator,
# so choosing is still one click and it is a choice.
def test_an_administrator_with_no_membership_lands_nowhere_either(monkeypatch, nobody):
    monkeypatch.setattr(
        deps.repository,
        "list_workspaces",
        lambda *args: [SimpleNamespace(id=1, slug="alguna")],
    )
    admin = SimpleNamespace(id=1, is_admin=True, active_workspace_id=None)

    assert deps.current_workspace_for(None, admin) is None


def test_the_first_membership_is_still_where_an_account_lands(monkeypatch):
    workspace = SimpleNamespace(id=7, slug="aula")
    monkeypatch.setattr(
        deps.identity, "memberships_for", lambda *args: [(SimpleNamespace(role="owner"), workspace)]
    )
    user = SimpleNamespace(id=2, is_admin=False, active_workspace_id=None)

    assert deps.current_workspace_for(None, user) is workspace


# A request that names no workspace is answered, not guessed at: there is no instance left
# to fall back to, and the message is what the panel turns into «crea el tuyo».
def test_a_request_that_names_none_is_told_so(nobody):
    with pytest.raises(HTTPException) as raised:
        deps.resolve_workspace(None, nobody, None)
    assert raised.value.status_code == 403
    assert raised.value.detail == deps.NO_WORKSPACE


# `default` was refused as a name while it was the instance everything fell back to. With
# the fallback gone the name owns nothing, and refusing it would be one special case kept
# for its own sake.
def test_default_is_a_name_anybody_may_use():
    assert settings.slug_error("default") is None
    assert paths.workspace("default").slug == "default"
