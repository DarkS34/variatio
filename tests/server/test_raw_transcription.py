from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import auth, raw_data, runtime
from server.auth.deps import Access
from server.routers.raw import router as raw_router
from variatio.core import inference
from variatio.core.workspace import Workspace

from ..evaluation.test_route_order import _wildcard_shadows

STATUS = {
    "slot": "exemplars",
    "documents": [
        {
            "name": "examen.pdf",
            "pages": 3,
            "state": "done",
            "reasons": [],
            "chars": 4120,
            "seams_merged": 1,
            "failed_pages": 0,
        }
    ],
    "done": 1,
    "pending": 0,
    "stale": 0,
    "total_pages": 3,
}


class FakeStage:
    def __init__(self):
        self.pages = {1: "primera", 2: "segunda", 3: "tercera"}
        self.calls: list[tuple] = []

    def _listing(self):
        return [
            {
                "index": i,
                "text": self.pages[i],
                "chars": len(self.pages[i]),
                "failed": self.pages[i].lstrip().startswith("> [TRANSCRIPCIÓN FALLIDA"),
            }
            for i in sorted(self.pages)
        ]

    def transcription_status(self, ws, slot):
        self.calls.append(("status", slot))
        return {**STATUS, "slot": slot}

    def document_pages_listing(self, ws, slot, name):
        self.calls.append(("listing", slot, name))
        return self._listing()

    def write_document_page(self, ws, slot, name, index, text):
        self.calls.append(("write", slot, name, index, text))
        if index not in self.pages:
            raise ValueError(f"La página {index} no existe")
        self.pages[index] = text

    def insert_document_page(self, ws, slot, name, after, text):
        self.calls.append(("insert", slot, name, after, text))
        renumbered = {i: t for i, t in self.pages.items() if i <= after}
        renumbered[after + 1] = text
        for i, t in sorted(self.pages.items()):
            if i > after:
                renumbered[i + 1] = t
        self.pages = renumbered
        return after + 1

    def delete_document_page(self, ws, slot, name, index):
        self.calls.append(("delete", slot, name, index))
        if index not in self.pages:
            raise ValueError(f"La página {index} no existe")
        remaining = [t for i, t in sorted(self.pages.items()) if i != index]
        self.pages = dict(enumerate(remaining, 1))


@pytest.fixture
def ws(tmp_path):
    workspace = Workspace(tmp_path / "aula", slug="aula")
    workspace.raw_exemplars_dir.mkdir(parents=True)
    workspace.raw_corpus_dir.mkdir(parents=True)
    (workspace.raw_exemplars_dir / "examen.pdf").write_bytes(b"%PDF-1.4 ")
    return workspace


@pytest.fixture
def stage(monkeypatch):
    fake = FakeStage()
    monkeypatch.setattr(raw_data, "_stage", lambda: fake)
    return fake


@pytest.fixture
def client(ws, stage, monkeypatch):
    monkeypatch.setattr(inference, "is_available", lambda: True)
    monkeypatch.setattr(inference, "engine_name", lambda: "ollama")

    access = Access(
        user=SimpleNamespace(id=1, name="Ana"),
        workspace=SimpleNamespace(slug="aula", name="Aula"),
        role="owner",
        ws=ws,
    )
    app = FastAPI()
    app.include_router(raw_router)
    app.dependency_overrides[auth.VIEW.dependency] = lambda: access
    app.dependency_overrides[auth.EDIT.dependency] = lambda: access
    return TestClient(app)


@pytest.fixture
def queue(monkeypatch):
    submitted: list[tuple[str, dict, str]] = []

    def submit(kind, params=None, workspace="", user_id=None, user_name=None):
        submitted.append((kind, params or {}, workspace))
        return SimpleNamespace(
            to_dict=lambda: {"id": "abc123", "kind": kind, "params": params or {}}
        )

    monkeypatch.setattr(runtime.runner, "submit", submit)
    monkeypatch.setattr(runtime.runner, "running", lambda slug=None: [])
    monkeypatch.setattr(runtime.runner, "pending", lambda slug=None: [])
    return submitted


# THE STATE OF A SLOT ---------------------------------------------------------------------


def test_the_state_of_a_slot_is_what_the_stage_reports(client, stage):
    body = client.get("/api/raw/exemplars/transcription").json()

    assert body["slot"] == "exemplars"
    assert body["documents"][0]["name"] == "examen.pdf"
    assert body["total_pages"] == 3
    assert ("status", "exemplars") in stage.calls


def test_an_unknown_slot_is_a_404_and_never_reaches_the_stage(client, stage):
    response = client.get("/api/raw/apuntes/transcription")

    assert response.status_code == 404
    assert "apuntes" in response.json()["detail"]
    assert stage.calls == []


# LAUNCHING IT ----------------------------------------------------------------------------


def test_launching_enqueues_the_job_with_its_slot(client, queue):
    body = client.post("/api/raw/exemplars/transcription").json()

    assert queue == [("transcribe", {"slot": "exemplars"}, "aula")]
    assert body["job"]["id"] == "abc123"


def test_launching_for_an_unknown_slot_is_a_404(client, queue):
    assert client.post("/api/raw/apuntes/transcription").status_code == 404
    assert queue == []


def test_launching_without_an_engine_is_refused_before_the_queue(client, queue, monkeypatch):
    monkeypatch.setattr(inference, "is_available", lambda: False)

    response = client.post("/api/raw/exemplars/transcription")

    assert response.status_code == 503
    assert queue == []


def test_the_same_slot_is_not_transcribed_twice_at_once(client, queue, monkeypatch):
    running = SimpleNamespace(
        kind="transcribe", workspace="aula", params={"slot": "exemplars"}
    )
    monkeypatch.setattr(runtime.runner, "running", lambda slug=None: [running])

    response = client.post("/api/raw/exemplars/transcription")

    assert response.status_code == 409
    assert queue == []
    # The other slot is a different piece of work and is not held back by it.
    assert client.post("/api/raw/corpus/transcription").status_code == 200


# THE PAGES OF A DOCUMENT ------------------------------------------------------------------


def test_the_pages_of_a_document_are_listed_in_order(client):
    body = client.get("/api/raw/exemplars/transcription/examen.pdf").json()

    assert body["name"] == "examen.pdf"
    assert [page["index"] for page in body["pages"]] == [1, 2, 3]
    assert body["pages"][0]["text"] == "primera"


def test_a_name_that_is_not_in_the_slot_is_a_404(client, stage):
    response = client.get("/api/raw/exemplars/transcription/otro.pdf")

    assert response.status_code == 404
    assert stage.calls == []


def test_a_name_may_not_climb_out_of_the_slot(client, stage):
    response = client.get("/api/raw/exemplars/transcription/..%2F..%2Fconfig.json")

    assert response.status_code == 404
    assert stage.calls == []


def test_saving_a_page_writes_it_and_answers_with_the_whole_document(client, stage):
    body = client.put(
        "/api/raw/exemplars/transcription/examen.pdf/2", json={"text": "corregida"}
    ).json()

    assert stage.pages[2] == "corregida"
    assert body["pages"][1]["text"] == "corregida"


def test_saving_a_page_that_does_not_exist_is_a_422(client):
    response = client.put(
        "/api/raw/exemplars/transcription/examen.pdf/9", json={"text": "x"}
    )

    assert response.status_code == 422


def test_inserting_a_page_answers_with_its_index_and_renumbers_the_rest(client, stage):
    body = client.post(
        "/api/raw/exemplars/transcription/examen.pdf", json={"after": 1, "text": "nueva"}
    ).json()

    assert body["index"] == 2
    assert [page["text"] for page in body["pages"]] == [
        "primera",
        "nueva",
        "segunda",
        "tercera",
    ]


def test_deleting_a_page_removes_it_and_renumbers_the_rest(client, stage):
    body = client.delete("/api/raw/exemplars/transcription/examen.pdf/1").json()

    assert [page["index"] for page in body["pages"]] == [1, 2]
    assert body["pages"][0]["text"] == "segunda"


def test_a_write_needs_a_name_that_is_in_the_slot(client, stage):
    assert (
        client.put(
            "/api/raw/exemplars/transcription/otro.pdf/1", json={"text": "x"}
        ).status_code
        == 404
    )
    assert client.delete("/api/raw/exemplars/transcription/otro.pdf/1").status_code == 404
    assert stage.calls == []


# THE ORDER OF THE ROUTES ------------------------------------------------------------------


def test_deleting_a_page_is_not_swallowed_by_the_document_deleter(client, stage, ws):
    response = client.delete("/api/raw/exemplars/transcription/examen.pdf/3")

    assert response.status_code == 200
    assert ("delete", "exemplars", "examen.pdf", 3) in stage.calls
    # The raw document itself is untouched: this deleted a page, not a file.
    assert (ws.raw_exemplars_dir / "examen.pdf").is_file()


def test_every_transcription_route_is_declared_above_the_document_wildcard():
    paths = [route.path for route in raw_router.routes if hasattr(route, "path")]
    wildcard = paths.index("/api/raw/{kind}/{name}")

    assert wildcard == len(paths) - 1
    assert all(
        index < wildcard
        for index, path in enumerate(paths)
        if "transcription" in path
    )


def test_no_fixed_path_of_the_raw_router_falls_below_a_wildcard():
    assert _wildcard_shadows(raw_router) == []


# WHAT THE STAGE REALLY ANSWERS ------------------------------------------------------------


def test_the_router_hands_out_the_keys_the_real_stage_writes(ws):
    # No fake in this one: everything above answers a stand-in, so this is what keeps the
    # payload the browser types against pinned to the stage's own shape.
    (ws.raw_exemplars_dir / "apuntes.md").write_text("# Tema 1", encoding="utf-8")

    state = raw_data.transcription(ws, "exemplars")

    assert set(state) >= {"slot", "documents", "done", "pending", "stale", "total_pages"}
    assert {entry["name"] for entry in state["documents"]} == {"apuntes.md", "examen.pdf"}
    assert set(state["documents"][0]) >= {
        "name",
        "pages",
        "state",
        "reasons",
        "chars",
        "seams_merged",
        "failed_pages",
    }
    assert state["pending"] == 2
