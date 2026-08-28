import json
import os

import pytest

from variatio.core.json_io import write_json

DATA = {"b": "ñandú «ok»", "a": [1, 2, {"c": None}]}


def test_it_does_not_follow_a_planted_temp_symlink(tmp_path):
    outside = tmp_path / "objetivo.txt"
    outside.write_text("intacto", encoding="utf-8")
    target = tmp_path / "doc.json"
    os.symlink(outside, tmp_path / "doc.json.tmp")

    write_json(target, DATA)

    assert outside.read_text(encoding="utf-8") == "intacto"
    assert not target.is_symlink()
    assert json.loads(target.read_text(encoding="utf-8")) == DATA


def test_a_leftover_temp_file_does_not_wedge_the_writer(tmp_path):
    target = tmp_path / "doc.json"
    (tmp_path / "doc.json.tmp").write_text("medio archivo de una ejecución cancelada", encoding="utf-8")

    write_json(target, DATA)

    assert json.loads(target.read_text(encoding="utf-8")) == DATA
    assert not (tmp_path / "doc.json.tmp").exists()


# The approval hashes stored in the database are hashes of exactly these bytes.
@pytest.mark.parametrize("sort_keys", [False, True])
def test_the_bytes_are_the_ones_the_approvals_are_hashes_of(tmp_path, sort_keys):
    target = tmp_path / "doc.json"
    write_json(target, DATA, sort_keys=sort_keys)

    assert target.read_bytes() == json.dumps(
        DATA, ensure_ascii=False, indent=2, sort_keys=sort_keys
    ).encode("utf-8")


def test_it_replaces_a_symlinked_destination_instead_of_writing_through_it(tmp_path):
    outside = tmp_path / "objetivo.txt"
    outside.write_text("intacto", encoding="utf-8")
    target = tmp_path / "doc.json"
    os.symlink(outside, target)

    write_json(target, DATA)

    assert outside.read_text(encoding="utf-8") == "intacto"
    assert not target.is_symlink()
