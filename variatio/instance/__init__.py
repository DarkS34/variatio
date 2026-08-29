"""The loaders of the four instance artifacts, named after the `instance/` directory.

    knowledge_graph.py   the curated graph, one NetworkX graph per relation
    exemplars_profile.py the content schema, compiled into Pydantic models at runtime
    content_context.py   what subject the instance is about
    relations.py         the relation vocabulary, one schema per language
    locale.py            which language a workspace's prompts and schema are in

No import here: the package is a namespace, and modules are imported by name so nothing in
`variatio/` pays for a loader it does not use.
"""
