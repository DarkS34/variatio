from types import SimpleNamespace

from variant_generator import config
from variant_generator.builders.knowledge_graph_builder import curation
from variant_generator.prompts import curate_graph_domains_prompt

CONCEPTS = ["Bucle while", "Función", "Lista", "Variable"]
RELATIONS = [["Función", "tiene como prerrequisito", "Variable"]]


def answer(monkeypatch, response: str) -> list[str]:
    prompts: list[str] = []

    def fake_generate(*, model, prompt, think, format, temperature):
        prompts.append(prompt)
        return SimpleNamespace(response=response)

    monkeypatch.setattr(curation.inference, "generate", fake_generate)
    return prompts


def place_all_in_the_first_domain(monkeypatch):
    def fake_assign_round(pending, placed, relations, definitions=None, *, max_attempts):
        first = next(iter(placed))
        placed[first].extend(pending)
        return []

    monkeypatch.setattr(curation, "assign_round", fake_assign_round)


def curate(monkeypatch, response):
    prompts = answer(monkeypatch, response)
    place_all_in_the_first_domain(monkeypatch)
    result = curation.curate_domains(CONCEPTS, RELATIONS, [], {}, max_attempts=1)
    return result, prompts


def test_curate_domains_reads_the_names_the_model_writes(monkeypatch):
    result, _ = curate(monkeypatch, '{"domains": ["Fundamentos", "Estructuras"]}')
    assert list(result) == ["Fundamentos", "Estructuras"]
    assert result["Fundamentos"] == sorted(CONCEPTS)


def test_curate_domains_drops_blank_repeated_and_catch_all_names(monkeypatch):
    result, _ = curate(
        monkeypatch,
        '{"domains": ["Fundamentos", " Fundamentos ", "", "%s", 7]}'
        % config.KG_BUILDER_UNCLASSIFIED_DOMAIN,
    )
    assert list(result) == ["Fundamentos"]


def test_curate_domains_leaves_everything_unclassified_when_no_domain_is_named(monkeypatch):
    result, _ = curate(monkeypatch, '{"domains": []}')
    assert result == {config.KG_BUILDER_UNCLASSIFIED_DOMAIN: sorted(CONCEPTS)}


def test_the_naming_prompt_is_not_shown_the_relation_evidence(monkeypatch):
    _, prompts = curate(monkeypatch, '{"domains": ["Fundamentos"]}')
    assert "tiene como prerrequisito" not in prompts[0]
    for concept in CONCEPTS:
        assert f"- {concept}" in prompts[0]


def test_the_naming_prompt_asks_for_names_and_not_for_a_partition():
    prompt = curate_graph_domains_prompt("- Variable\n- Función")
    assert '"domains": ["<Nombre de dominio>", "..."]' in prompt
    assert "NO listes los conceptos" in prompt
