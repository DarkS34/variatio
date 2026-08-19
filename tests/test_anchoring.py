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


TOC_LINE = (
    "Tema I · Introducción a la Programación ................ 3   "
    "Tema II · Variables y Tipos ................ 5   "
    "Tema III · Estructuras de Control ................ 8"
)

MULTILINE_INDEX = "\n".join(
    [
        "Tema I · Introducción a la Programación ................ 3",
        "Tema II · Variables y Tipos ................ 5",
        "Tema III · Estructuras de Control ................ 8",
    ]
)


def test_navigation_detects_a_table_of_contents_line():
    assert extraction.is_navigation(TOC_LINE)


def test_navigation_detects_a_multiline_index():
    assert extraction.is_navigation(MULTILINE_INDEX)


def test_navigation_detects_a_realistic_single_line_toc():
    toc = "Tema ................ 4  " * 3
    assert extraction.is_navigation(toc)


def test_navigation_detects_middle_dot_leaders():
    toc = "Tema ····· 4  " * 3
    assert extraction.is_navigation(toc)


def test_navigation_detects_ellipsis_character_leaders():
    toc = "Tema …… 4  " * 3
    assert extraction.is_navigation(toc)


def test_navigation_keeps_real_prose():
    assert not extraction.is_navigation("Un bucle for recorre una secuencia de valores.")


def test_navigation_keeps_prose_with_an_ellipsis():
    assert not extraction.is_navigation("El bucle sigue... hasta agotar la secuencia.")


def test_navigation_keeps_prose_with_a_stray_dot_run():
    assert not extraction.is_navigation(
        "Esto es una frase normal con .... cuatro puntos raros en medio de la explicacion."
    )


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


def test_clip_returns_empty_when_no_boundary_exists():
    assert extraction.clip_to_sentence("a" * 200, 50) == ""


def test_clip_never_exceeds_max_chars():
    cases = [
        ("b" * 300, 50),
        ("Primera frase clara pero sin fin cercano " + "c" * 300 + ". Fin.", 40),
        ("Otra frase normal de longitud media para probar límites del recorte.", 25),
    ]
    for text, n in cases:
        assert len(extraction.clip_to_sentence(text, n)) <= n


CHUNK = f"""{TOC_LINE}

## Bucles

Un bucle for recorre una secuencia de valores conocidos de antemano.

El cuerpo del bucle se ejecuta una vez por elemento.
"""


def test_excerpt_finds_the_paragraph_that_talks_about_the_concept():
    text = extraction.excerpt(CHUNK, "Bucle for", 900)
    assert "recorre una secuencia" in text


def test_excerpt_never_returns_the_table_of_contents():
    text = extraction.excerpt(CHUNK, "Bucle for", 900)
    assert "Tema I" not in text
    assert "......" not in text


def test_excerpt_returns_nothing_for_an_absent_concept():
    assert extraction.excerpt(CHUNK, "Diccionario ordenado", 900) == ""


def test_excerpt_grows_into_neighbouring_paragraphs():
    text = extraction.excerpt(CHUNK, "Bucle for", 900)
    assert "una vez por elemento" in text


def test_excerpt_does_not_cut_a_paragraph_mid_word():
    long_chunk = "Recursividad " + ("palabra " * 400)
    text = extraction.excerpt(long_chunk, "Recursividad", 120)
    assert not text.endswith("palab")
    assert len(text) <= 120


def test_excerpt_never_chooses_a_navigation_paragraph_even_if_it_mentions_the_concept():
    toc_mentioning_concept = (
        "Bucle for ................ 3   Bucle while ................ 5   "
        "Bucle for anidado ................ 7"
    )
    chunk = f"""{toc_mentioning_concept}

## Otra sección

Este párrafo no habla del tema buscado en absoluto.
"""
    assert extraction.excerpt(chunk, "Bucle for", 900) == ""


def test_excerpt_returns_nothing_for_an_all_navigation_chunk():
    chunk = f"{TOC_LINE}\n\n{TOC_LINE}"
    assert extraction.excerpt(chunk, "Bucle for", 900) == ""
