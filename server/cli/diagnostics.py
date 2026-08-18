def db_check(_args) -> int:
    from ..db import database_url, is_available

    url = database_url()
    # Never print the password: the URL comes from the environment and usually has one.
    safe = url.split("@")[-1] if "@" in url else url
    if is_available():
        print(f"Base de datos accesible en {safe}")
        return 0
    print(f"No hay conexión con la base de datos en {safe}")
    return 1
