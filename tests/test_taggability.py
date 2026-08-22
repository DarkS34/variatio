from variant_generator import taggability
from variant_generator.instance.content_context import ContentContext
from variant_generator.prompts import review_taggable_concepts_prompt

# The context is no longer a field of the profile: it is its own artifact, so the fake
# stops carrying it and the prompt is handed the rendered block, like every caller.
CONTEXT = ContentContext.from_legacy(
    {"asignatura": "Programación I", "nivel": "primero de grado"}
)


class FakeType:
    def __init__(self, key, label, description, primary_field):
        self.key = key
        self.label = label
        self.description = description
        self.primary_field = primary_field


class FakeProfile:
    item_types = {
        "coding": FakeType("coding", "Ejercicio de código", "Escribir un programa", "statement"),
        "mcq": FakeType("mcq", "Pregunta cerrada", "Elegir una opción", "statement"),
    }


def test_modalities_block_names_every_modality():
    block = taggability.modalities_block(FakeProfile())
    assert "Ejercicio de código" in block
    assert "Pregunta cerrada" in block
    assert "Escribir un programa" in block


def test_modalities_block_tolerates_a_missing_description():
    class ProfileWithBlankDescription:
        item_types = {
            "coding": FakeType("coding", "Ejercicio de código", "", "statement"),
            "mcq": FakeType("mcq", "Pregunta cerrada", None, "statement"),
        }

    block = taggability.modalities_block(ProfileWithBlankDescription())
    lines = block.splitlines()
    assert len(lines) == 2
    assert lines[0] == "- **Ejercicio de código** (`coding`)"
    assert lines[1] == "- **Pregunta cerrada** (`mcq`)"


def test_samples_block_is_empty_without_a_bank():
    assert taggability.samples_block(FakeProfile(), None, ["Recursividad"]) == ""


def test_samples_block_quotes_items_tagged_with_the_domain():
    bank = {
        "C1": {"item_type": "coding", "statement": "Escribe una función recursiva.",
               "concepts": ["Recursividad"], "primary_concept": "Recursividad"},
        "C2": {"item_type": "coding", "statement": "Fuera del dominio.",
               "concepts": ["Otro"], "primary_concept": "Otro"},
    }
    block = taggability.samples_block(FakeProfile(), bank, ["Recursividad"])
    assert "función recursiva" in block
    assert "Fuera del dominio" not in block


def test_samples_block_respects_the_per_domain_cap():
    bank = {
        f"C{i}": {
            "item_type": "coding",
            "statement": f"Ítem número {i}.",
            "concepts": ["Recursividad"],
            "primary_concept": "Recursividad",
        }
        for i in range(taggability.MAX_SAMPLES_PER_DOMAIN + 5)
    }
    block = taggability.samples_block(FakeProfile(), bank, ["Recursividad"])
    assert len(block.splitlines()) == taggability.MAX_SAMPLES_PER_DOMAIN


def test_samples_block_degrades_gracefully_without_a_matching_item_type():
    bank = {
        "C1": {
            "item_type": "unknown_type",
            "statement": "Un ítem cuyo tipo no está en el perfil.",
            "concepts": ["Recursividad"],
            "primary_concept": "Recursividad",
        },
    }
    block = taggability.samples_block(FakeProfile(), bank, ["Recursividad"])
    assert "Un ítem cuyo tipo no está en el perfil." in block


def test_samples_block_skips_an_item_with_no_usable_text():
    bank = {
        "C1": {
            "item_type": "coding",
            "statement": "",
            "concepts": ["Recursividad"],
            "primary_concept": "Recursividad",
        },
        "C2": {
            "item_type": "coding",
            "statement": "Ítem con texto.",
            "concepts": ["Recursividad"],
            "primary_concept": "Recursividad",
        },
    }
    block = taggability.samples_block(FakeProfile(), bank, ["Recursividad"])
    assert "Ítem con texto." in block
    assert block.count("\n- ") == 0
    assert len(block.splitlines()) == 1


def test_the_prompt_carries_the_context_and_the_modalities():
    prompt = review_taggable_concepts_prompt(
        "Funciones",
        "- Funciones",
        "- Recursividad",
        CONTEXT.prompt_block(),
        taggability.modalities_block(FakeProfile()),
        "",
    )
    assert "Programación I" in prompt
    assert "Ejercicio de código" in prompt
    assert "Recursividad" in prompt


def test_the_prompt_carries_the_samples_when_given():
    prompt = review_taggable_concepts_prompt(
        "Funciones",
        "- Funciones",
        "- Recursividad",
        CONTEXT.prompt_block(),
        taggability.modalities_block(FakeProfile()),
        "- Escribe una función recursiva.",
    )
    assert "EJERCICIOS REALES DEL MATERIAL DE ESTA ASIGNATURA" in prompt
    assert "Escribe una función recursiva." in prompt


def test_the_prompt_omits_the_samples_section_when_empty():
    prompt = review_taggable_concepts_prompt(
        "Funciones",
        "- Funciones",
        "- Recursividad",
        CONTEXT.prompt_block(),
        taggability.modalities_block(FakeProfile()),
        "",
    )
    assert "EJERCICIOS REALES DEL MATERIAL DE ESTA ASIGNATURA" not in prompt
