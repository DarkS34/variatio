# The judge is a phase like any other: it names its own model and cannot be left empty.
def test_the_judge_model_is_a_phase_of_its_own():
    from variatio.settings.derived import PHASES, derive
    from variatio.settings.registry import REGISTRY

    assert "models.phases.admissibility" in PHASES
    assert PHASES["models.phases.admissibility"] == "ADMISSIBILITY_LLM"
    values = {setting.key: setting.default for setting in REGISTRY}
    out = derive(values)
    assert out["ADMISSIBILITY_LLM"] == values["models.phases.admissibility"]
    assert out["ADMISSIBILITY_LLM"]
