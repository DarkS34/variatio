"""`db-check`: does the database answer, at which revision, and where was it looked for?"""


def db_check(_args) -> int:
    """Report whether the database answers, at which host, and at which revision.

    Deliberately outside `guarded()`: reporting that failure is this command's whole job.
    The revision is here because a database that answers can still be behind the code, and
    that state reaches a person as a 500 on whichever button touches the missing column
    first — this is the command they are pointed at when something looks broken.
    """
    from ..db import database_url, is_available, schema

    url = database_url()
    # Never print the password: the URL comes from the environment and usually has one.
    safe = url.split("@")[-1] if "@" in url else url
    if not is_available():
        print(f"No hay conexión con la base de datos en {safe}")
        return 1

    print(f"Base de datos accesible en {safe}")
    stale = schema.mismatch()
    if stale is not None:
        print(stale)
        return 1

    applied = ", ".join(sorted(schema.applied_revisions()))
    print(f"Esquema al día: revisión «{applied}»")
    return 0
