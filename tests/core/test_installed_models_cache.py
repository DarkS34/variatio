import pytest

from variatio.core import inference


class FakeClient:
    def __init__(self):
        self.listings = 0
        self.models = [{"model": "a:1", "size": 10}]

    def list(self):
        self.listings += 1
        return {"models": list(self.models)}

    def pull(self, model, stream=True):
        self.models.append({"model": model, "size": 20})
        return iter([{"total": 20, "completed": 20}])

    def delete(self, model):
        self.models = [m for m in self.models if m["model"] != model]


@pytest.fixture
def engine():
    engine = inference.OllamaEngine()
    engine._client = FakeClient()
    return engine


def test_the_listing_is_read_once_inside_the_ttl(engine):
    assert engine.installed_models() == ["a:1"]
    assert engine.installed_models() == ["a:1"]
    assert engine.installed_models() == ["a:1"]
    assert engine._client.listings == 1


def test_the_listing_is_read_again_once_the_ttl_is_over(engine, monkeypatch):
    engine.installed_models()
    monkeypatch.setattr(inference, "_INSTALLED_TTL_SECONDS", 0.0)
    engine.installed_models()
    assert engine._client.listings == 2


def test_a_pull_invalidates_the_listing(engine):
    assert engine.installed_models() == ["a:1"]
    engine.pull("b:2")
    assert engine.installed_models() == ["a:1", "b:2"]
    assert engine._client.listings == 2


def test_a_delete_invalidates_the_listing(engine):
    assert engine.installed_models() == ["a:1"]
    engine.delete("a:1")
    assert engine.installed_models() == []
    assert engine._client.listings == 2


def test_ensure_model_does_not_re_read_the_listing_per_model(engine):
    assert engine.ensure_model("a:1") is True
    assert engine.ensure_model("a:1") is True
    assert engine._client.listings == 1
