"""The RAG arm sees the bank and the bare output shape, and none of the profile's prose."""

import json
from pathlib import Path

import pytest

from evaluation import prompts as evaluation_prompts
from variatio.instance.exemplars_profile import ExemplarsProfile

MODALITY = {
    "label": "Ejercicio",
    "description": "El alumno escribe código.",
    "primary_field": "enunciado",
    "embed_fields": ["enunciado"],
    "general_generation_rules": ["El enunciado debe nombrar la entrada."],
    "fields": {
        "enunciado": {
            "schema": {"type": "string"},
            "description": "La tarea que se plantea.",
            "guidance": {"generation": "Empieza por un verbo."},
        },
        "nivel_dificultad": {
            "schema": {"type": "string", "enum": ["basico", "intermedio", "avanzado"]},
            "description": "«basico»: una estructura. «intermedio»: dos. «avanzado»: recursión.",
            "decided_by": "user",
        },
    },
}
PROFILE = {"item_types": {"ejercicio": MODALITY}}


@pytest.fixture
def item_type(tmp_path: Path):
    """One modality with a description, a guidance and a difficulty criterion on it."""
    path = tmp_path / "exemplars_profile.json"
    path.write_text(json.dumps(PROFILE, ensure_ascii=False), encoding="utf-8")
    return ExemplarsProfile(path).item_type(None)


def test_the_output_schema_keeps_the_shape_and_drops_every_sentence(item_type):
    schema = item_type.output_schema()
    assert set(schema["properties"]) == {"enunciado", "nivel_dificultad"}
    assert schema["properties"]["nivel_dificultad"]["enum"] == ["basico", "intermedio", "avanzado"]
    assert set(schema["required"]) == {"enunciado", "nivel_dificultad"}
    rendered = item_type.output_schema_str()
    for word in ("description", "title", "guidance", "tarea", "recursión", "verbo", "escribe código"):
        assert word not in rendered


@pytest.mark.parametrize("language", ["es", "en"])
def test_the_rag_prompt_carries_no_rules_and_no_profile_prose(item_type, language):
    prompt = evaluation_prompts.of(language).rag_generation_prompt(
        naive_prompt="Necesito un ejercicio.",
        theory_block="--- «apuntes.pdf», fragmento 2\nUna lista se recorre con un bucle.",
        exercises_block="--- «hoja1.pdf», fragmento 1\nSuma dos números.",
        schema=item_type.output_schema_str(),
    )
    assert "Una lista se recorre con un bucle." in prompt
    assert "Suma dos números." in prompt
    assert prompt.index("apuntes.pdf") < prompt.index("hoja1.pdf")
    assert '"enum"' in prompt
    for leak in ("nombrar la entrada", "La tarea", "recursión", "verbo", "REDACCIÓN", "WRITING RULES"):
        assert leak not in prompt
