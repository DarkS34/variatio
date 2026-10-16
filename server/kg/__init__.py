"""Step 2, «Temario»: the knowledge graph, as the canvas reads it and as a teacher edits it.

    router.py  `/api/kg`: the graph and its concepts, domains and relations, and the course's
               progress
    view.py    the graph as the canvas wants it: positional nodes and links, by domain
    edit.py    editing the graph: domains, concepts, relations and descriptions

Building the graph is the library's (`variatio/builders/knowledge_graph_builder/`) and a job
of the chain (`pipeline/jobs.py`).
"""
