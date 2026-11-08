"""The time left is published only for steps timed on today's engine with today's models (D-241)."""

import json

import pytest

from variatio import config
from variatio.api import rates
from variatio.settings import engine_profile, use_profile


@pytest.fixture
def measured(tmp_path, monkeypatch):
    """Point the rates at a tmp folder holding one engine's file, on that engine."""
    monkeypatch.setattr(rates, "RATES_DIR", tmp_path)
    monkeypatch.setattr(config, "INFERENCE_ENGINE", "ollama")
    for name in ("TRANSCRIBE_MODEL", "TRANSCRIBE_SEAM_MODEL", "KG_EXTRACT_MODEL"):
        monkeypatch.setattr(engine_profile(), name, "m1")
    (tmp_path / "ollama.json").write_text(json.dumps({"steps": {
        "transcribe_pages": {"unit": "page", "seconds": {"m1": 19.1, "m2": 37.0}},
        "kg_extract": {"unit": "chunk", "seconds": {"m2": 62.7}},
    }}))
    return tmp_path


def test_a_step_timed_with_the_configured_model_has_its_rate(measured):
    assert rates.step_rates()["transcribe_pages"] == {"unit": "page", "seconds": 19.1}


def test_a_step_timed_only_with_another_model_has_none(measured):
    assert "kg_extract" not in rates.step_rates()


def test_a_step_whose_phases_name_two_models_has_none(measured, monkeypatch):
    monkeypatch.setattr(engine_profile(), "TRANSCRIBE_SEAM_MODEL", "m2")
    assert "transcribe_pages" not in rates.step_rates()


def test_an_engine_with_no_file_has_no_rates(measured):
    with use_profile("cerebras+ollama"):
        assert rates.step_rates() == {}


def test_every_measured_step_names_phases_the_pipeline_declares():
    from variatio.settings.derived import PHASES

    for phases in rates.STEP_PHASES.values():
        for phase in phases:
            assert f"models.phases.{phase}" in PHASES


def test_the_shipped_file_reads():
    shipped = json.loads((rates.RATES_DIR / "ollama.json").read_text())
    assert set(shipped["steps"]) <= set(rates.STEP_PHASES)
