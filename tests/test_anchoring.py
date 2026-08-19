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


TOC_LINE = "| Tema I  ·  Introducción a la Programación  ................................  3"


def test_navigation_detects_a_table_of_contents_line():
    assert extraction.is_navigation(TOC_LINE)


def test_navigation_detects_a_multiline_index():
    assert extraction.is_navigation(f"{TOC_LINE}\n| Iterables y secuencias  .......  12")


def test_navigation_keeps_real_prose():
    assert not extraction.is_navigation("Un bucle for recorre una secuencia de valores.")


def test_navigation_keeps_prose_with_an_ellipsis():
    assert not extraction.is_navigation("El bucle sigue... hasta agotar la secuencia.")


def test_clip_returns_short_text_untouched():
    assert extraction.clip_to_sentence("Frase corta.", 900) == "Frase corta."


def test_clip_cuts_at_a_sentence_boundary():
    text = "Primera frase. Segunda frase que ya no cabe entera en el presupuesto."
    assert extraction.clip_to_sentence(text, 30) == "Primera frase."


def test_clip_falls_back_to_a_word_boundary():
    text = "palabra " * 20
    clipped = extraction.clip_to_sentence(text, 30)
    assert not clipped.endswith("palab")
    assert clipped.split() == ["palabra"] * 3
