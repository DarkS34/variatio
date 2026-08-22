from variant_generator.settings import derived


def base():
    values = {
        "engine.ollama_host": "localhost:13434",
        "models.main": "principal",
        "models.guardrail": "guardarrail",
        "models.embedding": "embebedor",
        "builders.kg_relation_schema": "es",
        "sampling.temperature_deterministic": 0.0,
        "generation.max_few_shot_examples": 4,
        "context_window.main": 65536,
        "context_window.guardrail": 4096,
        "context_window.embedding": 4096,
        "evaluation.providers": ["gemini", "groq"],
        "evaluation.models.gemini": "g-model",
        "evaluation.models.groq": "q-model",
        "evaluation.keys.gemini": "",
        "evaluation.keys.groq": "clave-groq",
    }
    for key in derived.PHASES:
        values[key] = None
    return values


def derive_ok():
    return derived.derive(base())


def test_every_phase_follows_the_main_model_when_unset():
    out = derive_ok()
    for name in derived.PHASES.values():
        assert out[name] == "principal", name


def test_an_overridden_phase_does_not_follow_the_main_model():
    values = base()
    values["models.phases.kg_taggable"] = "otro-modelo"
    out = derived.derive(values)
    assert out["KG_TAGGABLE_MODEL"] == "otro-modelo"
    assert out["KG_EXTRACT_MODEL"] == "principal"


def test_llm_context_is_keyed_by_the_resolved_model_names():
    out = derive_ok()
    assert out["LLM_CONTEXT"] == {
        "principal": 65536,
        "guardarrail": 4096,
        "embebedor": 4096,
    }


def test_changing_the_main_model_moves_the_context_key():
    values = base()
    values["models.main"] = "otro-principal"
    out = derived.derive(values)
    assert "otro-principal" in out["LLM_CONTEXT"]
    assert "principal" not in out["LLM_CONTEXT"]


def test_embedding_models_is_a_tuple_of_one():
    assert derive_ok()["EMBEDDING_MODELS"] == ("embebedor",)


def test_a_bare_host_gains_the_scheme():
    assert derive_ok()["OLLAMA_HOST"] == "http://localhost:13434"


def test_a_host_that_already_has_a_scheme_is_left_alone():
    values = base()
    values["engine.ollama_host"] = "https://gpu.interno:443"
    assert derived.derive(values)["OLLAMA_HOST"] == "https://gpu.interno:443"


def test_the_relation_schema_derives_the_prerequisite_label():
    out = derive_ok()
    assert out["KG_PREREQUISITE_RELATION"] == out["RELATION_SCHEMA"].prerequisite_verbose


def test_temperature_default_follows_the_deterministic_one():
    assert derive_ok()["TEMPERATURE_DEFAULT"] == 0.0


def test_eval_rag_top_k_follows_the_few_shot_budget():
    assert derive_ok()["EVAL_RAG_TOP_K"] == 4


def test_provider_chain_drops_none_and_duplicates():
    values = base()
    values["evaluation.providers"] = ["Gemini", "none", "groq", "gemini", ""]
    out = derived.derive(values)
    assert out["EVAL_EXTERNAL_PROVIDERS"] == ["gemini", "groq"]


def test_provider_models_and_keys_are_paired_by_provider():
    out = derive_ok()
    assert out["EVAL_PROVIDER_MODELS"]["groq"] == "q-model"
    assert out["EVAL_PROVIDER_KEYS"]["groq"] == "clave-groq"
    assert out["EVAL_PROVIDER_KEYS"]["gemini"] == ""


def test_a_legacy_single_key_lands_on_the_first_provider(monkeypatch):
    monkeypatch.setenv("EVAL_EXTERNAL_API_KEY", "clave-heredada")
    monkeypatch.setenv("EVAL_EXTERNAL_MODEL_ID", "modelo-heredado")
    values = base()
    values["evaluation.keys.gemini"] = ""
    out = derived.derive(values)
    assert out["EVAL_PROVIDER_KEYS"]["gemini"] == "clave-heredada"
    assert out["EVAL_PROVIDER_MODELS"]["gemini"] == "modelo-heredado"


def test_a_legacy_key_does_not_displace_a_declared_one(monkeypatch):
    monkeypatch.setenv("EVAL_EXTERNAL_API_KEY", "clave-heredada")
    values = base()
    values["evaluation.keys.gemini"] = "clave-propia"
    out = derived.derive(values)
    assert out["EVAL_PROVIDER_KEYS"]["gemini"] == "clave-propia"


def test_an_empty_provider_chain_does_not_crash_the_legacy_bridge(monkeypatch):
    monkeypatch.setenv("EVAL_EXTERNAL_API_KEY", "clave-heredada")
    values = base()
    values["evaluation.providers"] = ["none"]
    out = derived.derive(values)
    assert out["EVAL_EXTERNAL_PROVIDERS"] == []
