"""Listing the documents of a slot that is not there."""

from variatio.builders.source_docs.files import list_source_files


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
