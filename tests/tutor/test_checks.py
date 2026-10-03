"""The parts of the method a machine can verify are verified, one rule per check."""

from tutor import checks

LIMITS = {"max_questions": 3, "max_code_lines": 3, "copy_max_words": 8}


def failures(text, **overrides):
    arguments = {
        "quotes": [],
        "later": [],
        "forbidden_terms": [],
        "student_texts": [],
        "truncated": False,
        **LIMITS,
        **overrides,
    }
    return [code for code, _ in checks.check_reply(text, **arguments)]


def test_a_reply_with_one_question_and_no_code_passes():
    assert failures("Mira el apartado de funciones. ¿Qué devuelve tu función?") == []


def test_a_reply_without_a_question_fails_and_so_does_an_interrogation():
    assert failures("Revisa el apartado de funciones.") == ["no_question"]
    assert failures("¿Uno? ¿Dos? ¿Tres? ¿Cuatro?") == ["too_many_questions"]


def test_an_empty_or_cut_reply_fails():
    assert failures("   ") == ["empty"]
    assert "truncated" in failures("¿Qué ves?", truncated=True)


def test_a_line_of_the_student_s_code_may_be_quoted_but_a_program_may_not():
    quoted = "Fíjate en esta línea:\n```python\nreturn n * factorial(n)\n```\n¿Cuándo para?"
    program = "```python\ndef f(n):\n    if n == 0:\n        return 1\n    return n * f(n - 1)\n```\n¿Lo ves?"

    assert failures(quoted) == []
    assert failures(program) == ["code"]


def test_copying_a_passage_of_the_card_fails_but_naming_a_few_of_its_words_does_not():
    passage = "Una función recursiva necesita un caso base y reduce el problema en cada llamada."

    assert failures("¿Qué necesita una función recursiva para parar?", quotes=[passage]) == []
    copied = f"Según los apuntes: «{passage}» ¿Lo aplicas?"
    assert failures(copied, quotes=[passage]) == ["copied"]


def test_a_later_concept_fails_unless_the_student_brought_it_up():
    text = "¿Has pensado en la memoización para no repetir llamadas?"

    assert [c for c in failures(text, later=["Memoización"])] == ["later"]
    assert failures(text, later=["Memoización"], student_texts=["¿Y la memoización?"]) == []


def test_a_forbidden_term_fails_in_code_always_and_in_prose_only_when_unprompted():
    in_code = "¿Qué pasaría si quitas el `break` del bucle?"
    in_prose = "¿Por qué los apuntes evitan break dentro de un bucle?"

    assert failures(in_code, forbidden_terms=["break"]) == ["forbidden"]
    assert failures(in_code, forbidden_terms=["break"], student_texts=["usé break"]) == ["forbidden"]
    assert failures(in_prose, forbidden_terms=["break"]) == ["forbidden"]
    assert failures(in_prose, forbidden_terms=["break"], student_texts=["puse un break"]) == []


def test_a_sentence_that_opens_by_telling_the_student_they_are_right_fails():
    from tutor import prompts

    pattern = prompts.of("es").VALIDATION_PATTERN

    assert failures("Sí, exactamente. ¿Y qué pasa después?", validation=pattern) == ["validated"]
    assert failures("Lo has visto. Correcto: ¿y ahora?", validation=pattern) == ["validated"]
    assert failures("¿Qué crees que es exactamente el caso base?", validation=pattern) == []
    assert failures("Está bien que preguntes. ¿Qué parte te cuesta?", validation=pattern) == []
    assert failures("¡Eso es! ¿Y qué pasa después?", validation=pattern) == ["validated"]
    assert failures("Eso es un ejemplo de función. ¿Y en general?", validation=pattern) == []


def test_the_shared_run_is_counted_in_words_and_ignores_accents_and_case():
    assert checks.longest_shared_run("La Función devuelve un valor", "la funcion devuelve un valor") == 5
    assert checks.longest_shared_run("nada en común", "otra cosa distinta") == 0
