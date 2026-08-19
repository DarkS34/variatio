from variant_generator.builders.knowledge_graph_builder import extraction


def test_mentions_matches_literally():
    assert extraction.mentions("Un bucle for recorre una secuencia.", "Bucle for")


def test_mentions_ignores_accents_and_case():
    assert extraction.mentions("La RECURSION es una tecnica.", "Recursión")


def test_mentions_tolerates_plural_in_the_text():
    assert extraction.mentions("Las listas anidadas se recorren así.", "Lista anidada")


def test_mentions_tolerates_plural_in_the_name():
    assert extraction.mentions("Un algoritmo de búsqueda ordena.", "Algoritmos de búsqueda")


def test_mentions_rejects_an_unrelated_paragraph():
    assert not extraction.mentions("Se declara una variable entera.", "Bucle for")


def test_mentions_does_not_match_a_longer_unrelated_word():
    assert not extraction.mentions("Trabajamos en el basecamp del equipo.", "Base")


def test_mentions_matches_a_concept_with_parentheses():
    assert extraction.mentions(
        "El algoritmo tiene complejidad O(n) en el peor caso.", "O(n)"
    )


def test_mentions_matches_a_concept_with_parentheses_before_punctuation():
    assert extraction.mentions("La complejidad es O(n).", "O(n)")


def test_mentions_keeps_distinct_complexity_concepts_apart():
    assert not extraction.mentions("Un algoritmo O(log n) es habitual.", "O(n)")
