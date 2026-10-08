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
    assert failures("Piensa en lo que hace una función. ¿Qué devuelve la tuya?") == []


def test_a_reply_without_a_question_fails_and_so_does_an_interrogation():
    assert failures("Piensa en lo que devuelve tu función.") == ["no_question"]
    assert failures("¿Uno? ¿Dos? ¿Tres? ¿Cuatro?") == ["too_many_questions"]


def test_an_empty_or_cut_reply_fails():
    assert failures("   ") == ["empty"]
    assert "truncated" in failures("¿Qué ves?", truncated=True)


def test_a_line_of_the_student_s_code_may_be_quoted_but_a_program_may_not():
    quoted = "Fíjate en esta línea:\n```python\nreturn n * factorial(n)\n```\n¿Cuándo para?"
    program = "```python\ndef f(n):\n    if n == 0:\n        return 1\n    return n * f(n - 1)\n```\n¿Lo ves?"

    assert failures(quoted) == []
    assert failures(program) == ["code"]


def test_a_formula_is_not_code_and_a_diagram_of_the_model_s_own_is_refused():
    formula = "Se escribe así: $n! = n \\cdot (n-1)!$. ¿Qué pasa cuando $n = 0$?"
    drawn = "Míralo así:\n```mermaid\nflowchart LR\n  A --> B\n```\n¿Qué ves?"

    assert failures(formula) == []
    assert failures(drawn) == ["diagram"]


def test_copying_a_passage_of_the_card_fails_but_naming_a_few_of_its_words_does_not():
    passage = "Una función recursiva necesita un caso base y reduce el problema en cada llamada."

    assert failures("¿Qué necesita una función recursiva para parar?", quotes=[passage]) == []
    copied = f"Fíjate: «{passage}» ¿Lo aplicas?"
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


def test_a_reply_that_sends_the_student_to_the_notes_fails_and_a_topic_or_a_part_does_not():
    from tutor import prompts

    pattern = prompts.of("es").POINTING_PATTERN

    def pointed(text):
        return failures(text, pointing=pattern) == ["pointed"]

    assert pointed("Lo tienes en los apuntes. ¿Qué devuelve tu función?")
    assert pointed("Según tus apuntes, ¿qué hace un caso base?")
    assert pointed("Repásalo en el tema 2. ¿Qué devuelve?")
    assert pointed("Mira las diapositivas del bloque 3. ¿Qué ves?")
    assert pointed("Vuelve al tema II: ¿qué dice del caso base?")
    assert pointed("El material indica claramente que es de elección. ¿Por qué?")
    assert not pointed("¿Qué tema quieres trabajar ahora?")
    assert not pointed("En el tema de la recursividad, ¿qué detiene las llamadas?")
    assert not pointed("En el apartado 2 del ejercicio, ¿qué te piden?")
    assert not pointed("Te conviene que apuntes el valor de cada llamada. ¿Cuál es el primero?")
    assert not pointed("¿Qué pasa si dos procesos entran a la vez en la sección crítica?")
    assert not pointed("¿Qué material estéril necesitas para la cura?")

    english = prompts.of("en").POINTING_PATTERN
    assert failures("It is in the notes. What stops the calls?", pointing=english) == ["pointed"]
    assert failures("Check the slides of unit 2. What do you see?", pointing=english) == ["pointed"]
    assert failures("Which topic do you want to work on?", pointing=english) == []


def test_the_shared_run_is_counted_in_words_and_ignores_accents_and_case():
    assert checks.longest_shared_run("La Función devuelve un valor", "la funcion devuelve un valor") == 5
    assert checks.longest_shared_run("nada en común", "otra cosa distinta") == 0
