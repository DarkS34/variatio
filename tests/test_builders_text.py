import json

import pytest

from builders import _source_docs
from builders.exemplars_bank_builder import ExemplarsBankBuilder

FENCED = "Intro\n\n```python\na = 1\n\nb = 2\n---\nc = 3\n```\n\nOutro"


@pytest.fixture
def bank_builder():
    return object.__new__(ExemplarsBankBuilder)


# SPLITTING ----------------------------------------------------------------------------------


def test_split_blocks_splits_on_blank_lines():
    assert _source_docs.split_blocks("uno\n\ndos\n\ntres") == ["uno", "dos", "tres"]


def test_split_blocks_prefers_explicit_separators():
    text = "uno\n\nsigue\n\n---\n\ndos"

    assert _source_docs.split_blocks(text) == ["uno\n\nsigue", "dos"]


def test_split_blocks_keeps_code_fences_intact():
    blocks = _source_docs.split_blocks(FENCED)

    assert blocks == ["Intro", "```python\na = 1\n\nb = 2\n---\nc = 3\n```", "Outro"]


def test_split_blocks_does_not_split_inside_a_fence():
    blocks = _source_docs.split_blocks(FENCED)

    assert any("---" in block and block.startswith("```") for block in blocks)


def test_split_blocks_drops_empty_pieces():
    assert _source_docs.split_blocks("\n\n\n uno \n\n\n\n") == ["uno"]


# BATCHING -----------------------------------------------------------------------------------


def _batches(builder, content: str, chunk_size: int) -> list[str]:
    builder.chunk_size = chunk_size
    return builder._build_batches(content)


def test_build_batches_packs_small_blocks_together(bank_builder):
    assert _batches(bank_builder, "aaa\n\nbbb\n\nccc", 30) == ["aaa\n\n---\n\nbbb\n\n---\n\nccc"]


def test_build_batches_emits_an_oversized_block_alone(bank_builder):
    batches = _batches(bank_builder, "aaa\n\n" + "x" * 10 + "\n\nbbb", 5)

    assert batches == ["aaa", "x" * 10, "bbb"]


def test_build_batches_flushes_before_an_oversized_block(bank_builder):
    batches = _batches(bank_builder, "aa\n\nbb\n\n" + "x" * 30, 20)

    assert batches == ["aa\n\n---\n\nbb", "x" * 30]


def test_build_batches_charges_the_separator_budget_to_the_first_block(bank_builder):
    assert _batches(bank_builder, "aa\n\nbb", 10) == ["aa", "bb"]


def test_build_batches_starts_a_new_batch_on_overflow(bank_builder):
    assert _batches(bank_builder, "aaaaaa\n\nbbbbbb", 10) == ["aaaaaa", "bbbbbb"]


def test_build_batches_separator_budget_is_asymmetric_after_a_flush(bank_builder):
    batches = _batches(bank_builder, "aaa\n\nbbb\n\nccc\n\nddd\n\neee", 20)

    assert batches == ["aaa\n\n---\n\nbbb", "ccc\n\n---\n\nddd\n\n---\n\neee"]


def test_build_batches_of_empty_content(bank_builder):
    assert _batches(bank_builder, "", 100) == []


# IDS ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bank, expected",
    [
        ({}, 0),
        ({"C001": {}, "C007": {}, "C003": {}}, 7),
        ({"C001": {}, "otro": {}, "X9": {}}, 1),
        ({"c001": {}}, 0),
        ({"C0042": {}}, 42),
    ],
)
def test_max_id_reads_the_highest_numeric_suffix(bank, expected):
    assert ExemplarsBankBuilder._max_id(bank) == expected


def test_next_id_continues_from_the_counter(bank_builder):
    bank_builder._id_counter = 7

    assert [bank_builder._next_id() for _ in range(3)] == ["C008", "C009", "C010"]


# DOCUMENT LOADING ---------------------------------------------------------------------------


@pytest.mark.parametrize("suffix", [".md", ".txt"])
def test_to_markdown_reads_plain_text_sources(tmp_path, suffix):
    path = tmp_path / f"doc{suffix}"
    path.write_text("# Título\n\nCuerpo.", encoding="utf-8")

    assert _source_docs.to_markdown(None, path) == "# Título\n\nCuerpo."


def test_to_markdown_rejects_an_unsupported_extension(tmp_path):
    with pytest.raises(ValueError, match="Unsupported file extension"):
        _source_docs.to_markdown(None, tmp_path / "doc.odt")


def test_list_source_files_selects_and_sorts_supported_sources(tmp_path):
    for name in ("b.md", "a.txt", "c.odt", "d.PDF"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    (tmp_path / "sub").mkdir()

    assert [p.name for p in _source_docs.list_source_files(tmp_path)] == ["a.txt", "b.md", "d.PDF"]


def test_list_source_files_of_an_empty_directory(tmp_path):
    assert _source_docs.list_source_files(tmp_path) == []


def test_save_json_creates_missing_parents(tmp_path):
    target = tmp_path / "nested" / "deep" / "out.json"

    _source_docs.save_json({"a": "ñ"}, target)

    assert json.loads(target.read_text(encoding="utf-8")) == {"a": "ñ"}
