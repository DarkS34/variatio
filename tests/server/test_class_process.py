"""One process serves a whole class: a school's NAT, warm subjects, a hundred polling tabs.

Behind a school's NAT a class is one address, and the per-address limit refused the ninth
student to log in; the administrator lists the school's networks and only the account is
counted from them. One lock for every warm context made one subject's build hold up every
other subject's jobs; each subject now has its own. A hundred tabs poll `/api/health`, and
each poll read the engine across the tunnel; one reading now serves them for five seconds.
"""

import threading
import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from server import deps
from server.auth import rate_limit
from server.routers import health
from variatio import config
from variatio.core.workspace import Workspace
from variatio.settings import store
from variatio.settings.registry import REGISTRY
from variatio.settings.registry.access import networks
from variatio.settings.types import SettingError

SCHOOL = "203.0.113.0/24"


@pytest.fixture(autouse=True)
def clean_limiter():
    rate_limit.limiter._hits.clear()
    yield
    rate_limit.limiter._hits.clear()


def _from(address: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/login",
            "headers": [],
            "client": (address, 1234),
            "scheme": "http",
            "server": ("localhost", 8000),
            "query_string": b"",
        }
    )


def _logins(address: str, accounts: list[str]) -> int:
    """Return how many of these attempts got through before the first refusal."""
    for done, account in enumerate(accounts):
        try:
            rate_limit.throttle("login", _from(address), account)
        except HTTPException as refusal:
            assert refusal.status_code == 429
            return done
    return len(accounts)


# THE SCHOOL'S NETWORKS ---------------------------------------------------------------------


def test_the_ninth_login_from_one_address_is_refused(monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_NETWORKS", [])

    assert _logins("203.0.113.7", [f"alumno{n}" for n in range(9)]) == 8


def test_a_class_behind_a_listed_network_logs_in_and_each_account_keeps_its_limit(monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_NETWORKS", [SCHOOL])

    assert _logins("203.0.113.7", [f"alumno{n}" for n in range(20)]) == 20
    assert _logins("203.0.113.7", ["ana"] * 9) == 8


def test_an_address_outside_the_list_counts_as_before(monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_NETWORKS", [SCHOOL])

    assert _logins("198.51.100.4", [f"alumno{n}" for n in range(9)]) == 8


def test_a_change_to_the_list_holds_from_the_next_attempt(monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_NETWORKS", [])
    assert _logins("203.0.113.7", [f"alumno{n}" for n in range(8)]) == 8

    monkeypatch.setattr(config, "TRUSTED_NETWORKS", [SCHOOL])

    assert _logins("203.0.113.7", [f"otro{n}" for n in range(8)]) == 8


def test_an_attempt_with_no_account_keeps_its_address(monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_NETWORKS", [SCHOOL])
    limit, window = rate_limit.limits("reset")

    for _ in range(limit):
        rate_limit.throttle("reset", _from("203.0.113.7"), "")
    with pytest.raises(HTTPException):
        rate_limit.throttle("reset", _from("203.0.113.7"), "")


def test_an_ipv4_address_written_as_ipv6_is_read_as_ipv4(monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_NETWORKS", [SCHOOL])

    assert rate_limit.trusted("::ffff:203.0.113.7")
    assert not rate_limit.trusted("::ffff:198.51.100.4")
    assert not rate_limit.trusted("no es una dirección")


def test_the_list_refuses_what_is_not_one_school_s_network():
    for wide in (["0.0.0.0/0"], ["10.0.0.0/4"], ["::/0"], ["2001:db8::/16"], ["no-es-una-red"]):
        with pytest.raises(SettingError):
            networks(wide)


def test_the_list_stores_each_network_as_its_network_address():
    assert networks(["192.168.1.7", "10.1.2.3/16", "10.1.0.0/16", "2001:db8:5::/48"]) == [
        "192.168.1.7/32",
        "10.1.0.0/16",
        "2001:db8:5::/48",
    ]


def test_the_panel_cannot_save_a_network_that_wide():
    with pytest.raises(SettingError):
        store.validate_patch(list(REGISTRY), {"access.trusted_networks": ["0.0.0.0/0"]})
    saved = store.validate_patch(list(REGISTRY), {"access.trusted_networks": ["10.0.0.5"]})
    assert saved == {"access.trusted_networks": ["10.0.0.5/32"]}


# ONE LOCK PER SUBJECT ----------------------------------------------------------------------


@pytest.fixture
def registry(monkeypatch, tmp_path):
    """An empty context registry, an engine that answers, and two subjects."""
    monkeypatch.setattr(deps, "_contexts", deps.OrderedDict())
    monkeypatch.setattr(deps, "_invalid_reasons", {})
    monkeypatch.setattr(deps, "_generations", {})
    monkeypatch.setattr(deps, "_building", {})
    monkeypatch.setattr(deps, "require_inference", lambda: None)
    return SimpleNamespace(a=Workspace(tmp_path / "a", "a"), b=Workspace(tmp_path / "b", "b"))


def test_a_subject_warming_up_never_holds_up_another(monkeypatch, registry):
    started, release = threading.Event(), threading.Event()
    built = {}

    def initialize(tag, ws):
        if ws.slug == "a":
            started.set()
            release.wait(5)
        built[ws.slug] = object()
        return built[ws.slug]

    monkeypatch.setattr(deps.entrypoints, "initialize", initialize)
    warm_b = deps.get_context(registry.b)
    worker = threading.Thread(target=deps.get_context, args=(registry.a,))
    worker.start()
    assert started.wait(5)

    began = time.monotonic()
    assert deps.get_context(registry.b) is warm_b
    assert time.monotonic() - began < 0.5

    release.set()
    worker.join(5)
    assert deps.peek("a") is built["a"]


def test_two_jobs_of_one_subject_share_one_build(monkeypatch, registry):
    calls = []
    release = threading.Event()

    def initialize(tag, ws):
        calls.append(ws.slug)
        release.wait(5)
        return object()

    monkeypatch.setattr(deps.entrypoints, "initialize", initialize)
    results = []
    workers = [
        threading.Thread(target=lambda: results.append(deps.get_context(registry.a)))
        for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    time.sleep(0.1)
    release.set()
    for worker in workers:
        worker.join(5)

    assert calls == ["a"]
    assert results[0] is results[1]


def test_a_build_invalidated_while_it_ran_is_not_kept(monkeypatch, registry):
    started, release = threading.Event(), threading.Event()

    def initialize(tag, ws):
        started.set()
        release.wait(5)
        return object()

    monkeypatch.setattr(deps.entrypoints, "initialize", initialize)
    worker = threading.Thread(target=deps.get_context, args=(registry.a,))
    worker.start()
    assert started.wait(5)

    began = time.monotonic()
    deps.invalidate("a", "se corrigió el temario")
    assert time.monotonic() - began < 0.5

    release.set()
    worker.join(5)
    assert deps.peek("a") is None


# ONE READING OF THE ENGINE -----------------------------------------------------------------


@pytest.fixture
def engine(monkeypatch):
    """An engine that counts how often it is asked, and a clock the test moves."""
    calls = {"available": 0, "installed": 0, "running": 0}
    now = [1000.0]

    def available():
        calls["available"] += 1
        return True

    def installed():
        calls["installed"] += 1
        return ["qwen3.8:27b-q8_0"]

    def running():
        calls["running"] += 1
        return []

    monkeypatch.setattr(health.inference, "is_available", available)
    monkeypatch.setattr(health.inference, "installed_models", installed)
    monkeypatch.setattr(health.inference, "running_models", running)
    monkeypatch.setattr(health, "_clock", lambda: now[0])
    health.forget_reading()
    yield SimpleNamespace(calls=calls, now=now)
    health.forget_reading()


def test_fifty_polls_in_five_seconds_ask_the_engine_once(engine):
    for poll in range(50):
        engine.now[0] = 1000.0 + poll * 0.09
        reading = health.engine_reading()

    assert engine.calls == {"available": 1, "installed": 1, "running": 1}
    assert reading.available and reading.installed == ["qwen3.8:27b-q8_0"]


def test_a_reading_older_than_five_seconds_is_read_again(engine):
    health.engine_reading()
    engine.now[0] += health.READ_EVERY + 0.1

    health.engine_reading()

    assert engine.calls["available"] == 2


def test_while_one_request_reads_the_others_take_the_reading_before(engine, monkeypatch):
    first = health.engine_reading()
    engine.now[0] += health.READ_EVERY + 0.1
    assert health._reading_lock.acquire()
    try:
        assert health.engine_reading() is first
    finally:
        health._reading_lock.release()
    assert engine.calls["available"] == 1
