from variatio.settings import derived


def base():
    values = {
        "engine.ollama_host": "localhost:13434",
        "models.guardrail": "guardarrail",
        "models.embedding": "embebedor",
        "builders.kg_relation_schema": "es",
        "sampling.temperature_deterministic": 0.0,
        "generation.max_few_shot_examples": 4,
        "context_window.guardrail": 4096,
        "context_window.embedding": 4096,
        "context_window.overrides": 32768,
        "generation.models": ["principal"],
    }
    for key in derived.PHASES:
        values[key] = "principal"
    for phase in derived.PHASE_KEYS:
        values[f"reasoning.phases.{phase}"] = False
        values[f"reasoning.effort.{phase}"] = "low"
    return values


def derive_ok():
    return derived.derive(base())


# There is no main model to fall back to since 2026-08-28: what the registry holds for a
# phase is what the call site gets, and a phase cannot be left empty.
def test_every_phase_gets_exactly_what_its_setting_says():
    out = derive_ok()
    for name in derived.PHASES.values():
        assert out[name] == "principal", name


def test_one_phase_can_name_another_model_without_moving_the_rest():
    values = base()
    values["models.phases.kg_taggable"] = "otro-modelo"
    out = derived.derive(values)
    assert out["KG_TAGGABLE_MODEL"] == "otro-modelo"
    assert out["KG_EXTRACT_MODEL"] == "principal"


def test_llm_context_is_keyed_by_the_resolved_model_names():
    out = derive_ok()
    assert out["LLM_CONTEXT"] == {
        "guardarrail": 4096,
        "embebedor": 4096,
        "principal": 32768,
    }


def test_every_phase_model_gets_the_overrides_window():
    values = base()
    values["models.phases.kg_extract"] = "extractor"
    out = derived.derive(values)
    assert out["LLM_CONTEXT"]["extractor"] == 32768
    assert out["LLM_CONTEXT"]["principal"] == 32768


def test_a_model_no_phase_names_any_more_leaves_the_context():
    values = base()
    for key in derived.PHASES:
        values[key] = "otro-principal"
    values["generation.models"] = ["otro-principal"]
    out = derived.derive(values)
    assert "otro-principal" in out["LLM_CONTEXT"]
    assert "principal" not in out["LLM_CONTEXT"]


# The writer of a variant is the commission's since 2026-08-29, so it is not a phase model
# any more: what the CLI, the evaluation's arms and a request naming none get is the FIRST of
# the offered list.
def test_the_default_writer_is_the_first_model_offered():
    values = base()
    values["generation.models"] = ["el-primero", "el-segundo"]
    assert derived.derive(values)["VARIANT_GENERATION_LLM"] == "el-primero"


# Every offered model and not only the default: picking the second one would otherwise run
# it at whatever context its Modelfile declares, which is the reservation this map caps.
def test_every_offered_model_gets_the_overrides_window():
    values = base()
    values["generation.models"] = ["principal", "el-otro"]
    out = derived.derive(values)
    assert out["LLM_CONTEXT"]["el-otro"] == 32768


def test_embedding_models_is_a_tuple_of_one():
    assert derive_ok()["EMBEDDING_MODELS"] == ("embebedor",)


def test_a_bare_host_gains_the_scheme():
    assert derive_ok()["OLLAMA_HOST"] == "http://localhost:13434"


def test_a_host_that_already_has_a_scheme_is_left_alone():
    values = base()
    values["engine.ollama_host"] = "https://gpu.interno:443"
    assert derived.derive(values)["OLLAMA_HOST"] == "https://gpu.interno:443"


def test_temperature_default_follows_the_deterministic_one():
    assert derive_ok()["TEMPERATURE_DEFAULT"] == 0.0
