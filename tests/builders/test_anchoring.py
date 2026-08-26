import json

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


SENTENCES = (
    "Recursividad es una tecnica donde una funcion se llama a si misma. "
    "El caso base detiene la cadena de llamadas y devuelve un valor concreto. "
    "Sin caso base la recursion no termina y agota la pila de llamadas."
)


def test_excerpt_ends_at_a_sentence_boundary():
    text = extraction.excerpt(SENTENCES, "Recursividad", 150)
    assert text.endswith(".")
    assert len(text) <= 150
    assert "El caso base" in text


def test_excerpt_growth_stops_before_the_neighbour_exceeds_the_budget():
    hit_paragraph = "Un bucle for recorre una secuencia de valores."
    neighbour = "El cuerpo del bucle se ejecuta una vez por elemento recorrido."
    chunk = f"""## Bucles

{hit_paragraph}

{neighbour}
"""
    budget = len(hit_paragraph) + 2 + len(neighbour) - 1
    text = extraction.excerpt(chunk, "Bucle for", budget)
    assert neighbour not in text
    assert len(text) <= budget


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


def test_write_sources_records_the_outline_and_the_units(tmp_path):
    from variant_generator.builders.knowledge_graph_builder import curation

    path = tmp_path / "concept_sources.json"
    outline = [{"document": 0, "heading": "Tema I", "chunk": 2}]
    units = [{"name": "Uno", "heading": "Tema I", "chunk": 2}]
    cleaned = {
        "passages": {"A": [{"document": "d.pdf", "location": "", "text": "t"}]},
        "definitions": {},
        "documents": [{"name": "d.pdf"}],
        "outline": outline,
    }
    curation.write_sources(path, cleaned, {"A"}, units)

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["outline"] == outline
    assert stored["units"] == units


def test_write_sources_omits_the_two_keys_when_there_is_no_syllabus(tmp_path):
    from variant_generator.builders.knowledge_graph_builder import curation

    path = tmp_path / "concept_sources.json"
    curation.write_sources(path, {"passages": {}, "definitions": {}, "documents": []}, set())

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert "outline" not in stored
    assert "units" not in stored


def test_load_sources_keeps_what_it_does_not_know_about(tmp_path):
    from variant_generator.embedder import load_sources

    path = tmp_path / "concept_sources.json"
    path.write_text(
        json.dumps(
            {
                "documents": ["d.pdf"],
                "concepts": {"A": []},
                "definitions": {"A": "una idea"},
                "units": [{"name": "Uno", "heading": "Tema I", "chunk": 2}],
            }
        ),
        encoding="utf-8",
    )

    loaded = load_sources(path)

    assert loaded["definitions"] == {"A": "una idea"}
    assert loaded["units"] == [{"name": "Uno", "heading": "Tema I", "chunk": 2}]
    assert loaded["documents"] == ["d.pdf"]


def test_restamp_adopts_the_new_fingerprints_without_touching_the_texts(tmp_path):
    from variant_generator.embedder import ConceptDescriber, load_descriptions
    from variant_generator.instance.content_context import ContentContext
    from variant_generator.instance.knowledge_graph import KnowledgeGraph

    graph_path = tmp_path / "kg.json"
    graph_path.write_text(
        json.dumps(
            {
                "concepts_by_domains": {"Viejo": ["A", "B"]},
                "generic_non_taggable_concepts": [],
                "relations": [],
            }
        ),
        encoding="utf-8",
    )
    descriptions_path = tmp_path / "concept_descriptions.json"
    descriptions_path.write_text(
        json.dumps({"A": "texto de A", "B": "texto de B"}), encoding="utf-8"
    )
    context = ContentContext(
        {"subject": "X", "educational_level": "Y", "language_of_instruction": "es"}
    )

    def describer(path):
        return ConceptDescriber(
            KnowledgeGraph(str(path)),
            context,
            path=descriptions_path,
            sources_path=tmp_path / "concept_sources.json",
        )

    changed, total = describer(graph_path).restamp()
    assert (changed, total) == (2, 2)

    graph_path.write_text(
        json.dumps(
            {
                "concepts_by_domains": {"Tema I": ["A"], "Tema II": ["B"]},
                "generic_non_taggable_concepts": [],
                "relations": [],
            }
        ),
        encoding="utf-8",
    )

    dry = describer(graph_path)
    assert dry.restamp(dry_run=True) == (2, 2)
    assert dry.restamp(dry_run=True) == (2, 2)

    assert describer(graph_path).restamp() == (2, 2)
    assert describer(graph_path).restamp() == (0, 2)
    assert load_descriptions(descriptions_path) == {"A": "texto de A", "B": "texto de B"}
