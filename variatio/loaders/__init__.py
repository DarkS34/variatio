"""The loaders of the artifacts a workspace keeps in its `artifacts/` directory.

Named after what the modules do, not after the directory they read: until 2026-10-08 the
package and the directory were both `instance`, a word that also named the whole subject.

    knowledge_graph.py   the curated graph, one NetworkX graph per relation
    exemplars_profile.py the content schema, compiled into Pydantic models at runtime
    content_context.py   what subject the instance is about
    relations.py         the relation vocabulary, one schema per language
    locale.py            which language a workspace's prompts and schema are in

No import here: the package is a namespace, and modules are imported by name so nothing in
`variatio/` pays for a loader it does not use.
"""
