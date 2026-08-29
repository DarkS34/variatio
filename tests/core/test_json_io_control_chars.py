"""No control character leaves this system inside an artifact.

They are never the document's: in this pipeline they arrive when a decoder goes wrong, and
one of them — `U+0000` — makes the artifact impossible to store at all. Postgres refuses it
in JSONB, so a single NUL anywhere in a bank breaks `import-instance` for that workspace
AND makes every later `mirror_artifact` fail; the mirror is best-effort, so it fails as one
warning and the row simply stops keeping up. Measured on a reference installation: a bank
carrying four of them had a file with 151 items and a database row with 152.
"""

import json

import pytest

from variatio.core.json_io import write_json


def written(tmp_path, data):
    path = write_json(tmp_path / "artifact.json", data)
    return json.loads(path.read_text(encoding="utf-8"))


def test_a_nul_never_reaches_the_file(tmp_path):
    out = written(tmp_path, {"C001": {"enunciado": "calcula el t\x00tal"}})
    assert out["C001"]["enunciado"] == "calcula el ttal"
    assert "\x00" not in json.dumps(out)


def test_the_whole_c0_range_goes_except_tab_newline_and_return(tmp_path):
    damaged = "".join(chr(c) for c in range(0x00, 0x20)) + "\x7f"
    out = written(tmp_path, {"texto": f"a{damaged}b"})
    assert out["texto"] == "a\t\n\rb"


def test_it_reaches_inside_lists_and_keys(tmp_path):
    out = written(tmp_path, {"cla\x11ve": ["u\x10no", {"anidado": "d\x1fos"}]})
    assert list(out) == ["clave"]
    assert out["clave"] == ["uno", {"anidado": "dos"}]


# The point of stripping is that the artifact can be stored. A NUL is the one Postgres
# refuses outright, so the test that matters is that what comes out is storable text.
def test_what_comes_out_is_valid_for_jsonb(tmp_path):
    out = written(tmp_path, {"a": "\x00\x01\x02", "b": ["\x1f"], "c": {"d": "\x10"}})
    assert out == {"a": "", "b": [""], "c": {"d": ""}}


def test_clean_data_is_written_byte_for_byte_as_before(tmp_path):
    """The approval hashes in the database are hashes of these bytes."""
    data = {"z": "ñandú — «acentos»", "a": [1, 2.5, None, True], "t": "con\ttab\nlínea"}
    path = write_json(tmp_path / "a.json", data)
    expected = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False)
    assert path.read_text(encoding="utf-8") == expected


def test_sort_keys_still_works(tmp_path):
    path = write_json(tmp_path / "a.json", {"b": 1, "a": 2}, sort_keys=True)
    assert path.read_text(encoding="utf-8").index('"a"') < path.read_text(encoding="utf-8").index('"b"')


def test_it_says_out_loud_how_many_it_removed(tmp_path, caplog):
    import logging

    from loguru import logger

    messages = []
    sink = logger.add(lambda m: messages.append(m), level="WARNING")
    try:
        write_json(tmp_path / "a.json", {"x": "a\x00b\x11c"})
    finally:
        logger.remove(sink)
    assert any("2 control character" in m for m in messages)


@pytest.mark.parametrize("value", ["", "sin nada raro", "tab\ty salto\n"])
def test_a_clean_string_is_untouched(tmp_path, value):
    assert written(tmp_path, {"x": value})["x"] == value
