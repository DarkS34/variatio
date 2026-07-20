import ast
from pathlib import Path

from system import config, inference, utils


def _configured_llms() -> set[str]:
    return {value for name, value in vars(config).items() if name.endswith("_LLM")}


def test_config_has_no_duplicate_assignments():
    tree = ast.parse(Path(config.__file__).read_text(encoding="utf-8"))
    names = [
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    ]
    duplicates = sorted({name for name in names if names.count(name) > 1})

    assert duplicates == []


def test_prepare_models_installs_every_configured_llm(monkeypatch):
    installed: list[str] = []
    monkeypatch.setattr(inference, "ensure_model", lambda model: installed.append(model) or True)
    monkeypatch.setattr(inference, "warmup", lambda model, is_embedding=False: None)

    utils.prepare_models()

    assert set(installed) == _configured_llms()


def test_prepare_models_warms_the_embedding_model_as_embedding(monkeypatch):
    warmed: dict[str, bool] = {}
    monkeypatch.setattr(inference, "ensure_model", lambda model: True)
    monkeypatch.setattr(
        inference, "warmup", lambda model, is_embedding=False: warmed.__setitem__(model, is_embedding)
    )

    utils.prepare_models()

    assert warmed[config.EMBEDDING_LLM] is True
    assert all(not v for k, v in warmed.items() if k != config.EMBEDDING_LLM)


def test_prepare_models_raises_when_a_model_cannot_be_installed(monkeypatch):
    monkeypatch.setattr(inference, "ensure_model", lambda model: False)
    monkeypatch.setattr(inference, "warmup", lambda model, is_embedding=False: None)

    try:
        utils.prepare_models()
    except RuntimeError as e:
        assert "Failed to install model" in str(e)
    else:
        raise AssertionError("expected RuntimeError")


def test_ollama_host_always_carries_a_scheme():
    assert config.OLLAMA_HOST.startswith(("http://", "https://"))


def test_instance_and_cache_paths_live_under_project_root():
    paths = [
        config.KG_PATH,
        config.EXEMPLARS_BANK_PATH,
        config.CONTENT_PROFILE_PATH,
        config.CONCEPT_DESCRIPTIONS_PATH,
        config.CONCEPTS_EMBEDDINGS_PATH,
        config.EXEMPLARS_BANK_EMBEDDINGS_PATH,
    ]

    for path in paths:
        assert config.PROJECT_ROOT in path.parents
