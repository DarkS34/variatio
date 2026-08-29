"""`db-check`: does the database answer, and where was it looked for?"""


def db_check(_args) -> int:
    """Report whether the database answers, and at which host.

    Deliberately outside `guarded()`: reporting that failure is this command's whole job.
    """
    from ..db import database_url, is_available

    url = database_url()
    # Never print the password: the URL comes from the environment and usually has one.
    safe = url.split("@")[-1] if "@" in url else url
    if is_available():
        print(f"Base de datos accesible en {safe}")
        return 0
    print(f"No hay conexión con la base de datos en {safe}")
    return 1
