"""The loaders of the artifacts a workspace keeps in its `artifacts/` directory.

Named after what the modules do, not after the directory they read: until 2026-10-08 the
package and the directory were both `instance`, a word that also named the whole subject.

    exemplars_profile.py the content schema, compiled into Pydantic models at runtime

The graph, the subject's context and the relation vocabulary are read by `knowledge_graph/`
(`graph.py`, `context.py`, `relations.py`); the workspace's language by `utils/locale.py`.

No import here: the package is a namespace, and modules are imported by name so nothing in
`variatio/` pays for a loader it does not use.
"""
