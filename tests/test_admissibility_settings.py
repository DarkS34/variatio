def test_the_judge_model_follows_the_main_model_by_default():
    from variant_generator import config
    from variant_generator.settings.derived import PHASES

    assert "models.phases.admissibility" in PHASES
    assert PHASES["models.phases.admissibility"] == "ADMISSIBILITY_LLM"
    assert config.ADMISSIBILITY_LLM == config.LLM_MAIN
