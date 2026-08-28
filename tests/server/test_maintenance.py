from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from server import maintenance
from server.auth import deps
from server.db.models import VIEWER
from server.routers import maintenance as route


@pytest.fixture
def door(tmp_path, monkeypatch):
    monkeypatch.setattr(maintenance, "STATE_PATH", tmp_path / ".maintenance.json")
    monkeypatch.setattr(maintenance, "_cache", None)
    monkeypatch.setattr(maintenance, "_stamp", None)
    return maintenance


def test_a_fresh_installation_has_its_door_open(door):
    assert door.active() is False
    assert door.state()["since"] is None


def test_closing_records_the_notice_and_who_closed_it(door):
    saved = door.set_state(True, "Migrando la base de datos", "ana")
    assert saved["active"] is True
    assert saved["message"] == "Migrando la base de datos"
    assert saved["by"] == "ana"
    assert door.active() is True


# Rewording the notice while it is already closed must not restart the clock: what the
# screen reports is how long the installation has been down.
def test_rewording_while_closed_keeps_the_clock(door):
    first = door.set_state(True, "Un momento", "ana")
    again = door.set_state(True, "Cinco minutos más", "ana")
    assert again["since"] == first["since"]


def test_reopening_clears_the_notice(door):
    door.set_state(True, "Un momento", "ana")
    reopened = door.set_state(False, None, "ana")
    assert reopened["active"] is False
    assert reopened["since"] is None
    assert reopened["by"] is None


# The notice is written by a person or it is not written at all: the sentence read in its
# place is the client's, in the reader's own language, so the API must not invent one.
def test_an_empty_message_stays_empty(door):
    assert door.set_state(True, "   ", "ana")["message"] == ""


def test_a_broken_state_file_reads_as_open(door):
    door.STATE_PATH.write_text("{no es json", encoding="utf-8")
    assert door.active() is False


# The gate lives in `access_for` and nowhere else, so this is the whole of the enforcement.
def test_a_closed_door_stops_a_member(door, monkeypatch):
    door.set_state(True, "Un momento", "ana")
    user = SimpleNamespace(id=2, is_admin=False)
    workspace = SimpleNamespace(id=1, slug="default")

    with pytest.raises(HTTPException) as raised:
        deps.access_for(None, user, workspace, VIEWER)
    assert raised.value.status_code == 503
    assert raised.value.detail == door.CLOSED


def test_a_closed_door_lets_the_administrator_through(door, monkeypatch):
    door.set_state(True, "Un momento", "ana")
    monkeypatch.setattr(deps.identity, "membership", lambda *args: None)
    user = SimpleNamespace(id=1, is_admin=True)
    workspace = SimpleNamespace(id=1, slug="default")

    access = deps.access_for(None, user, workspace, VIEWER)
    assert access.as_admin is True


# Creating or activating a workspace resolves no membership, so `access_for` never sees
# them: they carry the door of their own.
def test_creating_a_workspace_is_closed_too(door):
    door.set_state(True, "Un momento", "ana")
    with pytest.raises(HTTPException) as raised:
        deps.require_open(SimpleNamespace(id=2, is_admin=False))
    assert raised.value.status_code == 503
    assert deps.require_open(SimpleNamespace(id=1, is_admin=True)).is_admin is True


def test_the_public_route_does_not_say_who_closed_it(door):
    door.set_state(True, "Un momento", "ana")
    payload = route.read()
    assert payload["active"] is True
    assert payload["message"] == "Un momento"
    assert "by" not in payload
