from variatio import screening
from variatio.screening import admissibility
from variatio.prompts.es import classify_instructions_prompt


def test_the_prompt_names_every_slot_and_every_owner(owners_for, context):
    found = owners_for()
    prompt = classify_instructions_prompt(
        instructions="que vaya de una panadería",
        catalog=screening.catalog(),
        owners=found,
        targets=["Recursividad"],
        context_block=context.prompt_block(),
    )
    for slot in screening.catalog():
        assert slot.key in prompt
        assert slot.example in prompt
    assert "field:nivel_dificultad" in prompt
    assert "avanzado" in prompt
    assert "Variable" in prompt


def test_the_prompt_marks_the_targets_as_not_an_invasion(owners_for):
    prompt = classify_instructions_prompt(
        instructions="que use recursividad",
        catalog=screening.catalog(),
        owners=owners_for(),
        targets=["Recursividad"],
        context_block="",
    )
    assert "Recursividad" in prompt
    assert "practicar" in prompt.lower()


def test_the_schema_pins_the_slot_and_owner_keys(owners_for):
    schema = admissibility._schema(owners_for())
    item = schema["properties"]["requests"]["items"]
    assert set(item["properties"]["slot"]["enum"]) == {s.key for s in screening.catalog()} | {None}
    assert "field:nivel_dificultad" in item["properties"]["owner"]["enum"]
    assert item["required"] == ["text", "slot", "owner", "term"]
