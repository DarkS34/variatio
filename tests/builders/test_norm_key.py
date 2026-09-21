"""The mechanical merge key singularises the head of a noun phrase as well as its last word."""

from variatio.builders.knowledge_graph_builder import cleaning


def test_a_plural_head_before_de_merges_with_its_singular():
    # Measured on the reference graph: «Casos de uso» and «Caso de Uso» survived as two
    # taggable concepts because only the last word was ever singularised.
    assert cleaning.norm_key("Casos de uso") == cleaning.norm_key("Caso de Uso")
    assert cleaning.norm_key("Diagramas de clases") == cleaning.norm_key("Diagrama de clases")
    assert cleaning.norm_key("Tipos abstractos de datos") == cleaning.norm_key("Tipo abstracto de datos")
    assert cleaning.norm_key("Types of data") == cleaning.norm_key("Type of data")


def test_the_last_word_rule_still_holds():
    assert cleaning.norm_key("Listas") == cleaning.norm_key("Lista")
    assert cleaning.norm_key("Casos de usos") == cleaning.norm_key("Caso de uso")


def test_a_word_in_the_middle_is_never_touched():
    # The deliberate heuristic: an adjective that does not agree is not merged by force.
    assert cleaning.norm_key("Listas anidadas") != cleaning.norm_key("Lista anidadas")
    # A singular head ending in «s» is cut like a last word always was («análisis» → «analisi»):
    # harmless, because a key is only ever compared with another key, never shown.
    assert cleaning.norm_key("Análisis de requisitos") == cleaning.norm_key("Analisi de requisito")
    # A short word is never cut.
    assert cleaning.norm_key("Los de siempre") == "los de siempre"


def test_the_preposition_at_the_very_start_is_not_a_head():
    assert cleaning.norm_key("de Morgan") == "de morgan"
    assert cleaning.norm_key("O(n)") == "o(n)"
