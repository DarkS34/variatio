"""The chain of the three steps: approvals, artifact writes, and the construction's jobs and
their gates. The label review's record and the subject's context are `server/knowledge_graph/`.

    approvals.py     what is approved, what each artifact depends on, its history
    storage.py       the one writer of an artifact's files, mirrored to the database
    chain.py         what a job chains after it
    gates.py         what must be settled before a job kind may run
    view.py          the chain and the queue, as `/api/pipeline` answers them
    jobs.py          the construction's job kinds, registered by `install()`
    routes/          `/api/pipeline`

The jobs and the routes are leaves: only `server/app.py` and `server/routing.py` import them.
"""
