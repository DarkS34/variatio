from variatio.builders._source_docs import chunking

DOC = """\
# Basura

## Tema I

texto uno

## Tema II

texto dos

## Tema III

texto tres
"""


def test_chunk_markdown_and_chunk_sections_split_identically():
    plain = chunking.chunk_markdown(DOC, 40)
    rich = chunking.chunk_sections(DOC, 40)
    assert [(path, body) for path, _headings, body in rich] == plain


def test_each_chunk_carries_the_headings_of_the_sections_packed_into_it():
    rich = chunking.chunk_sections(DOC, 10_000)
    assert len(rich) == 1
    _path, headings, _body = rich[0]
    assert headings == ["Basura", "Tema I", "Tema II", "Tema III"]


def test_a_chunk_per_section_carries_one_heading_each():
    rich = chunking.chunk_sections(DOC, 25)
    assert [headings for _p, headings, _b in rich] == [
        ["Basura"],
        ["Tema I"],
        ["Tema II"],
        ["Tema III"],
    ]


def test_the_section_heading_survives_a_useless_path():
    sections = chunking.split_sections(DOC)
    assert [heading for _p, heading, _b in sections] == [
        "Basura",
        "Tema I",
        "Tema II",
        "Tema III",
    ]
    assert chunking.common_path([p for p, _h, _b in sections[1:]]) == "Basura"


def test_a_section_longer_than_the_budget_opens_only_at_its_first_piece():
    long_doc = "## Tema I\n\n" + "\n\n".join(f"parrafo {i} relleno" * 3 for i in range(6))
    rich = chunking.chunk_sections(long_doc, 60)
    assert len(rich) > 1
    assert rich[0][1] == ["Tema I"]
    assert all(headings == [] for _p, headings, _b in rich[1:])


def test_a_text_without_headings_still_chunks():
    rich = chunking.chunk_sections("sin encabezados\n\notro parrafo", 10_000)
    assert rich == [("", [], "sin encabezados\n\notro parrafo")]
