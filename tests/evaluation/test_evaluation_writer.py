"""The writer of the two local proposals is the installation's, never the commission's.

`evaluation.local_model` is read by `run.evaluate` and put on the commission once, so both
local arms write with one model — the comparison stays about architectures — and a locked
model runs at the level the installation declared, exactly as a generation does.
"""

import pytest

from evaluation import Commission
from evaluation import config as evaluation_config
from evaluation import run as evaluation_run
from evaluation.arms import system as system_arm
from variatio import config, settings


@pytest.fixture
def offered(monkeypatch):
    monkeypatch.setattr(config, "GENERATION_MODELS", ["el-rapido", "el-que-delibera"])
    monkeypatch.setattr(config, "VARIANT_GENERATION_LLM", "el-rapido")
    monkeypatch.setattr(config, "FIXED_EFFORT_MODELS", ["el-que-delibera"])
    monkeypatch.setattr(config, "FIXED_EFFORT_LEVELS", {"el-que-delibera": "high"})


def _local_model(monkeypatch, value):
    """Answer `evaluation.local_model` with `value` on the next read of the setting."""
    real = settings.values

    def patched():
        out = real()
        out["evaluation.local_model"] = value
        return out

    monkeypatch.setattr(settings, "values", patched)


class _Type:
    key = "ejercicio"
    label = "Ejercicio"
    field_specs: dict = {}


class _Profile:
    def item_type(self, key):
        return _Type()


class _Context:
    exemplars_profile = _Profile()
    language = "es"


def _run_capturing(monkeypatch) -> list[Commission]:
    """Stub everything after the commission is built, and keep what the arms were given."""
    seen: list[Commission] = []

    def fake_arm(arm, commission, context):
        seen.append(commission)
        from evaluation import FAILED, ArmResult

        return ArmResult(arm, FAILED, None, "", "", "", "", [], 0)

    monkeypatch.setattr(evaluation_run, "_validate", lambda *a: None)
    monkeypatch.setattr(evaluation_run, "_screen", lambda *a: None)
    monkeypatch.setattr(evaluation_run, "_tag", lambda *a: None)
    monkeypatch.setattr(evaluation_run, "_safe_run", fake_arm)
    return seen


def test_an_empty_setting_means_the_same_model_that_writes_a_generation(offered, monkeypatch):
    _local_model(monkeypatch, None)
    assert evaluation_config.LOCAL_MODEL == "el-rapido"


def test_the_setting_names_the_writer_whether_offered_or_not(offered, monkeypatch):
    _local_model(monkeypatch, "el-de-la-instalacion")
    assert evaluation_config.LOCAL_MODEL == "el-de-la-instalacion"


def test_the_installations_writer_reaches_every_arm_on_the_commission(offered, monkeypatch):
    _local_model(monkeypatch, "el-que-delibera")
    seen = _run_capturing(monkeypatch)
    session = evaluation_run.evaluate(_Context(), concepts=["Función"], seed=7)
    assert len(seen) == 3
    assert {c.model for c in seen} == {"el-que-delibera"}
    # Locked at "high": reasoning ON runs at the declared level, OFF stays off.
    assert {c.effort for c in seen} == ({"high"} if session.think else {False})


def test_the_default_writer_is_the_first_offered(offered, monkeypatch):
    _local_model(monkeypatch, None)
    seen = _run_capturing(monkeypatch)
    session = evaluation_run.evaluate(_Context(), concepts=["Función"], seed=7)
    assert {c.model for c in seen} == {"el-rapido"}
    assert {c.effort for c in seen} == {session.think}


class _Generator:
    """Records the keyword arguments the system arm hands the pipeline's generator."""

    def __init__(self):
        self.calls: list[dict] = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return []


def test_the_system_arm_forwards_the_writer_and_the_effort_untouched():
    generator = _Generator()

    class Context:
        pass

    context = Context()
    context.generator = generator
    commission = Commission(
        concepts=["Función"], item_type="ejercicio", think=True, model="el-que-delibera", effort="high"
    )
    result = system_arm.run(commission, context)
    assert generator.calls[0]["model"] == "el-que-delibera"
    assert generator.calls[0]["think"] == "high"
    assert result.model == "el-que-delibera"
