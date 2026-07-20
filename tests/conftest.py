import json
import os
from pathlib import Path

import pytest

from system import inference
from system.content_profile import ContentProfile
from system.embedder import Embedder
from system.inference import GenerationResponse
from system.knowledge_graph import KnowledgeGraph

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MIN_KG_PATH = FIXTURES_DIR / "knowledge_graph_min.json"
MIN_PROFILE_PATH = FIXTURES_DIR / "content_profile_min.json"
SNAPSHOTS_DIR = FIXTURES_DIR / "prompts"


@pytest.fixture
def assert_snapshot():
    def _assert(name: str, actual: str) -> None:
        path = SNAPSHOTS_DIR / f"{name}.txt"
        if os.environ.get("UPDATE_SNAPSHOTS"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(actual, encoding="utf-8", newline="\n")
            return
        if not path.exists():
            raise AssertionError(
                f"Missing snapshot '{name}'. Review the output and run with UPDATE_SNAPSHOTS=1."
            )
        assert actual == path.read_text(encoding="utf-8")

    return _assert


@pytest.fixture
def min_kg_data() -> dict:
    with MIN_KG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def kg() -> KnowledgeGraph:
    return KnowledgeGraph(MIN_KG_PATH)


@pytest.fixture
def write_kg(tmp_path):
    def _write(data: dict) -> KnowledgeGraph:
        path = tmp_path / "kg.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return KnowledgeGraph(path)

    return _write


@pytest.fixture
def min_profile_data() -> dict:
    with MIN_PROFILE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def profile() -> ContentProfile:
    return ContentProfile(MIN_PROFILE_PATH)


@pytest.fixture
def write_profile(tmp_path):
    def _write(data: dict) -> ContentProfile:
        path = tmp_path / "content_profile.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return ContentProfile(path)

    return _write


@pytest.fixture
def embedder(kg) -> Embedder:
    instance = object.__new__(Embedder)
    instance.knowledge_graph = kg
    return instance


@pytest.fixture
def scripted_generate(monkeypatch):
    def _install(*responses: str) -> list[dict]:
        calls: list[dict] = []
        queue = list(responses)

        def _generate(model: str, prompt: str, think: bool | None = None):
            calls.append({"model": model, "prompt": prompt, "think": think})
            return GenerationResponse(response=queue.pop(0) if queue else "")

        monkeypatch.setattr(inference, "generate", _generate)
        return calls

    return _install


@pytest.fixture
def scripted_embed(monkeypatch):
    def _install(vector_for: dict[str, list[float]] | None = None) -> list[dict]:
        calls: list[dict] = []

        def _embed(model: str, text: str) -> list[float]:
            calls.append({"model": model, "text": text})
            if vector_for and text in vector_for:
                return list(vector_for[text])
            return [float(len(text) % 7 + 1), 1.0, 0.0]

        monkeypatch.setattr(inference, "embed", _embed)
        return calls

    return _install


class _StubEmbedder:
    def __init__(self, candidates: list[tuple[str, float]]):
        self.candidates = candidates
        self.concept_descriptions: dict[str, str] = {}

    def top_k_concepts(self, text: str, k: int) -> list[tuple[str, float]]:
        return self.candidates[:k]


@pytest.fixture
def stub_embedder():
    return _StubEmbedder


@pytest.fixture
def tagger():
    from system.concept_tagger import ConceptTagger

    return ConceptTagger(
        _StubEmbedder([("Bucles", 0.9), ("Variables", 0.5)]),
        "tagger-model",
        primary_field="statement",
        context={"materia": "Programación I"},
    )


@pytest.fixture
def generator(kg, profile):
    from system.content_generator import ContentGenerator

    return ContentGenerator(
        knowledge_graph=kg,
        exemplars_bank={},
        embedder=_StubEmbedder([]),
        content_profile=profile,
        generator_model="generator-model",
    )


@pytest.fixture
def captured_logs():
    from loguru import logger

    records = []
    sink_id = logger.add(lambda message: records.append(message.record), level="DEBUG")
    yield records
    logger.remove(sink_id)
