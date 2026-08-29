"""The API, its job queue and its database, all optional to the pipeline.

Deliberately empty of code: `import server` must succeed with no database reachable and
without pulling FastAPI or SQLAlchemy in. The composition root is `server/app.py`, and
nothing inside this package may import it.
"""
