"""The exemplars bank: the exercises a subject already has, how they are built and tagged.

    exemplars_profile/  the content schema the bank is built against: `ExemplarsProfile`
                        (`profile.py`) and its build from the exemplars (`build.py`)
    build.py            the exemplars → the bank, following the profile
    tagging.py          `ConceptTagger`: the graph's concepts each item practises

The documents it reads come through `variatio/documents/`, where Docling and pypdfium2 — the
`builders` extra, optional — are imported lazily inside the functions that use them, so
importing anything here must not pull them in.

Deliberately free of imports: the runtime reads `exemplars_profile.profile` on every exercise,
and importing it must not pull a builder in.
"""
