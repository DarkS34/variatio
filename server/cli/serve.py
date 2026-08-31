"""`serve`: the API, behind a one-process lock and a database check."""

from .common import PROG, database_hint
from .lock import LockHeld, hold


def serve_lock_path():
    """Return the lock file that keeps a second `serve` from starting."""
    from variatio.core.paths import WORKSPACES_DIR

    return WORKSPACES_DIR / ".serve.lock"


def serve(args) -> int:
    """Start the API, refusing to run twice or without a database.

    Only one process may serve: the job queue, the rate limiter and the idle release of
    the GPU all live in the memory of one. Every request resolves a session and a
    membership, so starting without Postgres would only produce a 503 per request — it is
    better to say so once, here, than to look like the app is broken. This is one of the
    two commands `guarded()` does not wrap, because it makes that check itself.

    A database that ANSWERS is checked once more, against the migrations: a schema behind
    the code does not fail at startup, it fails on whichever request first touches the
    column that is missing, and what the person sees there is a 500 on a button that has
    nothing to do with it.
    """
    import uvicorn

    from ..db import is_available, schema, session_scope
    from ..db.identity import count_users
    from .access_log import access_log_config, access_log_path

    try:
        hold(serve_lock_path())
    except LockHeld as exc:
        print(f"Ya hay un `{PROG} serve` en marcha: el bloqueo {exc.path} está ocupado.")
        print(
            "Solo puede ejecutarse uno a la vez — la cola de trabajos, el límite de peticiones "
            "y la descarga de la GPU viven en memoria de un único proceso."
        )
        return 1

    if not is_available():
        database_hint()
        return 1

    stale = schema.mismatch()
    if stale is not None:
        print(stale)
        return 1

    try:
        with session_scope() as session:
            if count_users(session) == 0:
                print("Todavía no hay ninguna cuenta: nadie podrá entrar.")
                print(
                    f"Crea la primera con `{PROG} create-user --username NOMBRE --admin`.\n"
                )
    except Exception:  # noqa: BLE001 - a schema at head that still refuses is not this check's
        print(f"La base de datos responde pero rechaza la consulta. Prueba `{schema.MIGRATE}`.\n")

    uvicorn.run(
        "server.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
        log_config=access_log_config(access_log_path()),
    )
    return 0
