def test_the_judge_model_follows_the_main_model_by_default():
    from variant_generator.settings.derived import PHASES, derive
    from variant_generator.settings.registry import REGISTRY

    assert "models.phases.admissibility" in PHASES
    assert PHASES["models.phases.admissibility"] == "ADMISSIBILITY_LLM"
    values = {setting.key: setting.default for setting in REGISTRY}
    out = derive(values)
    assert out["ADMISSIBILITY_LLM"] == values["models.main"]
