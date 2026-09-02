import os

from study import config as study_config


def base():
    return {
        "evaluation.providers": ["gemini", "mistral", "groq"],
        "evaluation.models.gemini": "g-model",
        "evaluation.models.mistral": "m-model",
        "evaluation.models.groq": "q-model",
        "evaluation.keys.gemini": "",
        "evaluation.keys.mistral": "clave-mistral",
        "evaluation.keys.groq": "clave-groq",
        "evaluation.timeout": 60.0,
    }


def derive(values, few_shot: int = 4):
    return study_config.derive(values, dict(os.environ), few_shot)


def derive_ok():
    return derive(base())


def test_rag_top_k_follows_the_few_shot_budget():
    assert derive_ok()["RAG_TOP_K"] == 4


def test_provider_chain_drops_none_and_duplicates():
    values = base()
    values["evaluation.providers"] = ["Gemini", "none", "groq", "gemini", ""]
    out = derive(values)
    assert out["EXTERNAL_PROVIDERS"] == ["gemini", "groq"]


def test_a_provider_is_two_settings_and_nothing_else_to_declare():
    """The maps are read off the registry, so a new name needs no third list."""
    out = derive_ok()
    assert out["PROVIDER_MODELS"]["mistral"] == "m-model"
    assert out["PROVIDER_KEYS"]["mistral"] == "clave-mistral"


def test_provider_models_and_keys_are_paired_by_provider():
    out = derive_ok()
    assert out["PROVIDER_MODELS"]["groq"] == "q-model"
    assert out["PROVIDER_KEYS"]["groq"] == "clave-groq"
    assert out["PROVIDER_KEYS"]["gemini"] == ""


def test_a_legacy_single_key_lands_on_the_first_provider(monkeypatch):
    monkeypatch.setenv("EVAL_EXTERNAL_API_KEY", "clave-heredada")
    monkeypatch.setenv("EVAL_EXTERNAL_MODEL_ID", "modelo-heredado")
    values = base()
    values["evaluation.keys.gemini"] = ""
    out = derive(values)
    assert out["PROVIDER_KEYS"]["gemini"] == "clave-heredada"
    assert out["PROVIDER_MODELS"]["gemini"] == "modelo-heredado"


def test_a_legacy_key_does_not_displace_a_declared_one(monkeypatch):
    monkeypatch.setenv("EVAL_EXTERNAL_API_KEY", "clave-heredada")
    values = base()
    values["evaluation.keys.gemini"] = "clave-propia"
    out = derive(values)
    assert out["PROVIDER_KEYS"]["gemini"] == "clave-propia"


def test_an_empty_provider_chain_does_not_crash_the_legacy_bridge(monkeypatch):
    monkeypatch.setenv("EVAL_EXTERNAL_API_KEY", "clave-heredada")
    values = base()
    values["evaluation.providers"] = ["none"]
    out = derive(values)
    assert out["EXTERNAL_PROVIDERS"] == []
