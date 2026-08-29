"""What a re-extraction does to the bank that is already there: nothing, until it finishes.

Every build reads every document again, so anything already in `exemplars_bank.json` could
only come back out of them a second time. The build writes aside and puts what it made in
place whole, which is what makes «volver a extraer» mean what its confirmation says and a
cancelled one leave the workspace as it found it.
"""

import json

import pytest

from variatio.builders.exemplars_bank_builder import ExemplarsBankBuilder
from variatio.core import progress
from variatio.core.json_io import write_json
from variatio.core.workspace import Workspace
from variatio.instance.exemplars_profile import ExemplarsProfile

PROFILE = {
    "item_types": {
        "ejercicio": {
            "label": "Ejercicio",
            "primary_field": "enunciado",
            "embed_fields": ["enunciado"],
            "fields": {
                "enunciado": {"schema": {"type": "string"}, "description": "El texto."},
            },
        }
    }
}

OLD_BANK = {
    "C001": {"enunciado": "El de antes", "concepts": ["Variable"]},
    "C002": {"enunciado": "Otro de antes", "concepts": []},
    "C003": {"enunciado": "Y un tercero", "concepts": []},
}


@pytest.fixture
def ws(tmp_path):
    ws = Workspace(tmp_path / "aula", "aula")
    write_json(ws.exemplars_profile_path, PROFILE)
    ws.raw_exemplars_dir.mkdir(parents=True)
    for name in ("tema1.md", "tema2.md"):
        (ws.raw_exemplars_dir / name).write_text("Un enunciado.", encoding="utf-8")
    write_json(ws.exemplars_bank_path, OLD_BANK)
    return ws


@pytest.fixture
def builder(ws, monkeypatch):
    builder = ExemplarsBankBuilder(
        ExemplarsProfile(ws.exemplars_profile_path), workspace=ws, verbose=False
    )
    monkeypatch.setattr(builder, "bootstrap", lambda: None)
    monkeypatch.setattr(builder, "_convert", lambda files: {f: "texto" for f in files})
    return builder


def extract_one(builder):
    """One item per document, numbered by the builder itself."""

    def fake(file_path, content, tag):
        return {builder._next_id(): {"enunciado": f"nuevo de {file_path.stem}"}}

    return fake


def run(builder, ws):
    return builder.build(
        ws.raw_exemplars_dir, ws.exemplars_bank_path, ws.exemplars_bank_building_path
    )


def saved(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_a_rebuild_replaces_the_bank_instead_of_piling_up(builder, ws, monkeypatch):
    monkeypatch.setattr(builder, "_process_file", extract_one(builder))

    bank = run(builder, ws)

    assert list(bank) == ["C001", "C002"]
    assert saved(ws.exemplars_bank_path) == bank
    assert [item["enunciado"] for item in bank.values()] == [
        "nuevo de tema1",
        "nuevo de tema2",
    ]


def test_the_previous_bank_is_untouched_until_the_build_finishes(builder, ws, monkeypatch):
    monkeypatch.setattr(builder, "_process_file", extract_one(builder))
    seen = []

    def on_items(bank, new_ids):
        seen.append(
            (saved(ws.exemplars_bank_path), saved(ws.exemplars_bank_building_path))
        )
        return bank

    builder.build(
        ws.raw_exemplars_dir,
        ws.exemplars_bank_path,
        ws.exemplars_bank_building_path,
        on_items=on_items,
    )

    # Once per document, and the artifact is the old bank on both.
    assert [artifact for artifact, _ in seen] == [OLD_BANK, OLD_BANK]
    assert [sorted(working) for _, working in seen] == [["C001"], ["C001", "C002"]]


def test_a_cancelled_rebuild_gives_the_previous_bank_back(builder, ws, monkeypatch):
    def cancel_on_the_second(file_path, content, tag):
        if file_path.stem == "tema2":
            raise progress.Cancelled("cancelado")
        return {builder._next_id(): {"enunciado": "nuevo de tema1"}}

    monkeypatch.setattr(builder, "_process_file", cancel_on_the_second)

    with pytest.raises(progress.Cancelled):
        run(builder, ws)

    assert saved(ws.exemplars_bank_path) == OLD_BANK
    assert not ws.exemplars_bank_building_path.exists()


def test_what_a_dead_build_left_behind_is_swept_and_never_resumed(builder, ws, monkeypatch):
    write_json(ws.exemplars_bank_building_path, {"C009": {"enunciado": "a medias"}})
    monkeypatch.setattr(builder, "_process_file", extract_one(builder))

    bank = run(builder, ws)

    assert "C009" not in bank
    assert list(bank) == ["C001", "C002"]
    assert not ws.exemplars_bank_building_path.exists()


def test_an_extraction_that_produced_nothing_leaves_the_bank_alone(builder, ws, monkeypatch):
    monkeypatch.setattr(builder, "_process_file", lambda file_path, content, tag: {})

    assert run(builder, ws) == {}
    assert saved(ws.exemplars_bank_path) == OLD_BANK
    assert not ws.exemplars_bank_building_path.exists()
