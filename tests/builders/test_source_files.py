"""Listing the documents of a slot: one that is not there, and the order of one that is."""

from variatio.builders.source_docs.files import list_source_files, name_order


def test_a_missing_directory_lists_nothing_whichever_way_it_is_walked(tmp_path):
    missing = tmp_path / "raw_corpus"

    assert list_source_files(missing) == []
    assert list_source_files(missing, recursive=True) == []


def test_a_path_that_is_a_file_lists_nothing(tmp_path):
    not_a_directory = tmp_path / "corpus.pdf"
    not_a_directory.write_bytes(b"%PDF-1.4")

    assert list_source_files(not_a_directory) == []
    assert list_source_files(not_a_directory, recursive=True) == []


def test_the_documents_of_a_real_directory_are_listed_in_order(tmp_path):
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "a.docx").write_bytes(b"PK")
    (tmp_path / "c.pptx").write_bytes(b"PK")
    (tmp_path / "cover.png").write_bytes(b"\x89PNG")

    assert [p.name for p in list_source_files(tmp_path)] == ["a.docx", "b.pdf", "c.pptx"]


def test_a_number_in_a_name_counts_as_its_number(tmp_path):
    for name in ("Bloque 10.pdf", "Bloque 2.pdf", "Bloque 1.pdf"):
        (tmp_path / name).write_bytes(b"%PDF-1.4")

    assert [p.name for p in list_source_files(tmp_path)] == [
        "Bloque 1.pdf",
        "Bloque 2.pdf",
        "Bloque 10.pdf",
    ]


def test_case_and_accents_do_not_move_a_name():
    names = ["Zeta.pdf", "tema1_complementos.pdf", "Álgebra.pdf", "Tema1_diapositivas.pdf", "algebra 2.pdf"]

    assert sorted(names, key=name_order) == [
        "algebra 2.pdf",
        "Álgebra.pdf",
        "tema1_complementos.pdf",
        "Tema1_diapositivas.pdf",
        "Zeta.pdf",
    ]


def test_two_names_that_fold_alike_keep_one_order():
    assert sorted(["tema.pdf", "Tema.pdf"], key=name_order) == sorted(
        ["Tema.pdf", "tema.pdf"], key=name_order
    )


def test_a_name_with_a_digit_that_is_not_a_number_still_sorts():
    assert sorted(["x².pdf", "²", "x2.pdf"], key=name_order)
