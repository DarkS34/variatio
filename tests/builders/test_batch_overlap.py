import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from variatio import config
from variatio.builders import exemplars_bank_builder
from variatio.builders.exemplars_bank_builder import ExemplarsBankBuilder
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


@pytest.fixture
def builder(tmp_path):
    path = tmp_path / "exemplars_profile.json"
    path.write_text(json.dumps(PROFILE, ensure_ascii=False), encoding="utf-8")
    return ExemplarsBankBuilder(
        ExemplarsProfile(path),
        workspace=Workspace(tmp_path, "pruebas"),
        verbose=False,
    )


def blocks(count: int, size: int) -> str:
    return "\n\n".join(f"B{index:02d} " + "x" * size for index in range(count))


# THE OVERLAP -------------------------------------------------------------------------------------


def test_consecutive_batches_share_their_boundary_block(builder, monkeypatch):
    monkeypatch.setattr(builder, "chunk_size", 300)
    batches = builder._build_batches(blocks(9, 100))
    assert len(batches) > 1
    for previous, following in zip(batches, batches[1:]):
        last = previous.split("\n\n---\n\n")[-1]
        assert following.startswith(last)


def test_the_overlap_can_be_switched_off(builder, monkeypatch):
    monkeypatch.setattr(builder, "chunk_size", 300)
    monkeypatch.setattr(config, "EB_BATCH_OVERLAP_BLOCKS", 0)
    batches = builder._build_batches(blocks(9, 100))
    for previous, following in zip(batches, batches[1:]):
        assert not following.startswith(previous.split("\n\n---\n\n")[-1])


def test_every_block_still_reaches_some_batch(builder, monkeypatch):
    monkeypatch.setattr(builder, "chunk_size", 300)
    batches = builder._build_batches(blocks(9, 100))
    for index in range(9):
        assert any(f"B{index:02d} " in batch for batch in batches)


def test_the_batches_always_advance(builder, monkeypatch):
    monkeypatch.setattr(builder, "chunk_size", 300)
    monkeypatch.setattr(config, "EB_BATCH_OVERLAP_BLOCKS", 20)
    batches = builder._build_batches(blocks(12, 140))
    assert len(batches) == len(set(batches))
    assert all(len(batch) <= 300 + 140 + 10 for batch in batches)


def test_a_block_over_the_budget_is_still_emitted_on_its_own(builder, monkeypatch):
    monkeypatch.setattr(builder, "chunk_size", 200)
    huge = "H " + "y" * 500
    batches = builder._build_batches(f"{blocks(2, 50)}\n\n{huge}")
    assert huge in batches


# THE DEDUPLICATION -------------------------------------------------------------------------------


def extract(builder, monkeypatch, per_batch: list[list[dict]]) -> dict:
    calls = iter(per_batch)

    def fake_extract_batch(batch, tag):
        return next(calls, [])

    monkeypatch.setattr(builder, "_extract_batch", fake_extract_batch)
    monkeypatch.setattr(builder, "_build_batches", lambda content: ["a", "b"])
    return builder._process_file(Path("examen.pdf"), "contenido", tag="[t]")


def item(text: str) -> dict:
    return {"item_type": "ejercicio", "enunciado": text}


def test_an_item_seen_in_both_batches_is_kept_once(builder, monkeypatch):
    items = extract(builder, monkeypatch, [[item("Suma dos números.")], [item("Suma dos números.")]])
    assert len(items) == 1


def test_the_repeat_does_not_consume_an_identifier(builder, monkeypatch):
    items = extract(
        builder,
        monkeypatch,
        [[item("Suma dos números.")], [item("Suma dos números."), item("Resta dos números.")]],
    )
    assert list(items) == ["C001", "C002"]


def test_spacing_and_case_do_not_make_two_items(builder, monkeypatch):
    items = extract(
        builder,
        monkeypatch,
        [[item("Suma dos números.")], [item("  SUMA   dos  números. ")]],
    )
    assert len(items) == 1


def test_two_genuinely_different_items_both_survive(builder, monkeypatch):
    items = extract(builder, monkeypatch, [[item("Suma.")], [item("Resta.")]])
    assert len(items) == 2


def test_an_item_the_profile_cannot_place_is_still_kept(builder, monkeypatch):
    items = extract(builder, monkeypatch, [[{"item_type": "inexistente"}], []])
    assert len(items) == 1


def test_the_source_stem_is_recorded_on_every_item(builder, monkeypatch):
    items = extract(builder, monkeypatch, [[item("Suma.")], []])
    assert all(entry["source"] == "examen" for entry in items.values())


def test_identity_ignores_everything_but_the_primary_field(builder):
    one = {"item_type": "ejercicio", "enunciado": "Suma."}
    other = {"item_type": "ejercicio", "enunciado": "Suma.", "source": "otro"}
    assert builder._identity(one) == builder._identity(other)


def test_the_builder_still_reads_its_overlap_from_the_registry():
    assert exemplars_bank_builder.config.EB_BATCH_OVERLAP_BLOCKS >= 0
    assert isinstance(SimpleNamespace(n=config.EB_BATCH_OVERLAP_BLOCKS).n, int)
