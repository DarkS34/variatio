"""A repetition loop is recognised on the tail of a text, and cut where it began.

The two shapes measured on the reference installation: a grid row written 271 times (a
line loop the model stopped on its own, cached as a page with content) and a fill-in line
copied as thousands of `\\_` (a character loop that ran to the output cap). Both are pure
functions of the text, so the engine can ask between two chunks and the cache in cold.
"""

from variatio.core import repetition
from variatio.core.repetition import Loop, cut, detect, detect_tail, quoted

ROW = "| | | |       | | | |"


def test_a_grid_of_identical_rows_is_a_line_loop_starting_at_the_first_row():
    head = "# SUMADOR / RESTADOR\n\n```\n1 0 0 0   0 1 1 0\n"
    text = head + (ROW + "\n") * 40
    loop = detect(text)
    assert loop is not None
    assert loop.unit == ROW
    assert text[loop.start :].startswith(ROW)
    assert loop.start == len(head)


def test_a_block_of_lines_repeated_is_one_loop_with_the_block_as_its_unit():
    block = "| a |\n|---|\n| 1 |\n"
    text = "Tabla:\n" + block * 12
    loop = detect(text)
    assert loop is not None
    assert loop.unit == block.rstrip("\n")
    assert loop.start == len("Tabla:\n")


def test_a_run_of_escaped_underscores_is_a_character_loop():
    text = "Nombre: " + "\\_" * 2000
    loop = detect(text)
    assert loop is not None
    assert loop.unit == "\\_"
    assert loop.start == len("Nombre: ")


def test_a_rule_of_dashes_is_a_character_loop_of_one():
    loop = detect("Texto\n" + "-" * 500)
    assert loop is not None and loop.unit == "-" and loop.start == len("Texto\n")


def test_blank_lines_alone_are_never_a_loop():
    assert detect("Texto\n" + "\n" * 100) is None
    assert detect("Texto" + " " * 800) is None


def test_a_real_table_is_not_a_loop():
    rows = "\n".join(f"| {i} | {i * i} | {i * i * i} |" for i in range(60))
    assert detect("| n | n² | n³ |\n|---|---|---|\n" + rows) is None


def test_a_short_repetition_is_content_not_a_loop():
    assert detect("a\n" * 10) is None, "ten identical lines are not twenty-four"
    assert detect("Firma: " + "_" * 80) is None, "eighty underscores are not four hundred"


def test_a_block_needs_four_repetitions_whatever_its_length():
    block = "\n".join(f"line {i}" for i in range(8)) + "\n"
    assert detect(block * 3) is None
    assert detect(block * 4) is not None


def test_the_loop_is_found_while_the_last_row_is_still_being_written():
    text = (ROW + "\n") * 30 + ROW[:5]
    loop = detect_tail(text)
    assert loop is not None and loop.unit == ROW


def test_a_loop_the_model_stopped_on_its_own_sits_in_the_middle_of_a_finished_page():
    # Page 40 of the reference subject: 271 identical rows, then the model closed the fence
    # and went on. The tail says nothing; the page holds a loop all the same.
    head = "# SUMADOR\n\n```\n1 0 0 0\n"
    text = head + (ROW + "\n") * 271 + "```\n\nCout = 0\n(Lo ignoramos)\n"
    assert detect_tail(text) is None
    loop = detect(text)
    assert loop is not None and loop.unit == ROW and loop.start == len(head)
    assert cut(text, loop) == "# SUMADOR\n\n```\n1 0 0 0\n```"


def test_a_character_run_in_the_middle_is_found_too():
    text = "Nombre: " + "\_" * 300 + "\n\nEjercicio 1. Calcula la suma.\n"
    assert detect_tail(text) is None
    loop = detect(text)
    assert loop == Loop(len("Nombre: "), "\_")


def test_a_run_of_blank_lines_followed_by_content_is_not_a_loop():
    assert detect("\n" * 60 + "\n".join(f"línea {i}" for i in range(30))) is None


def test_cut_keeps_what_came_before_and_closes_an_open_fence():
    text = "# Título\n\n```\ncabecera\n" + (ROW + "\n") * 40
    loop = detect(text)
    assert cut(text, loop) == "# Título\n\n```\ncabecera\n```"


def test_cut_leaves_a_closed_fence_alone():
    text = "```\nx\n```\n\n" + ("- punto\n" * 40)
    assert cut(text, detect(text)) == "```\nx\n```"


def test_quoted_flattens_a_block_and_bounds_its_length():
    assert quoted("| a |\n| b |") == "| a | ⏎ | b |"
    assert quoted("x" * 200) == "x" * repetition.QUOTE_CHARS + "…"


def test_the_start_offset_counts_the_original_line_endings():
    text = "uno   \ndos\n" + ("fila\n" * 30)
    loop = detect(text)
    assert loop == Loop(len("uno   \ndos\n"), "fila")
