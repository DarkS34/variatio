"""The knowledge graph: the syllabus artifact, how it is built and what is derived from it.

    graph.py          `KnowledgeGraph`, the curated graph loaded as one NetworkX graph per relation
    context.py        `ContentContext`, what subject the instance is about
    relations.py      the relation vocabulary, one schema per language
    build/            corpus → the draft graph, and the subject's context
    descriptions.py   the concept descriptions the bank is compared against
    taggability.py    which concepts are any use as a label

Deliberately free of imports: the runtime reads `graph` and `context` on every exercise, and
importing them must not pull the builder in.
"""
