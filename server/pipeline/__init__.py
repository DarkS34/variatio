"""The chain of the three steps: approvals, artifact writes, the label review, the subject's
context, and the construction's jobs and their gates.

    approvals.py     what is approved, what each artifact depends on, its history
    storage.py       the one writer of an artifact's files, mirrored to the database
    taggability.py   whether the label review can be skipped
    context_edit.py  hand edits of the subject's context
    chain.py         what a job chains after it
    gates.py         what must be settled before a job kind may run
    view.py          the chain and the queue, as `/api/pipeline` answers them
    jobs.py          the construction's job kinds, registered by `install()`
    routes/          `/api/pipeline` and `/api/context`

The jobs and the routes are leaves: only `server/app.py` and `server/routing.py` import them.
"""
