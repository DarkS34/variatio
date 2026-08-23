from .common import PROG, database_hint
from .lock import LockHeld, hold


def serve_lock_path():
    from variant_generator.core.paths import WORKSPACES_DIR

    return WORKSPACES_DIR / ".serve.lock"


# `serve` used to start with no database on purpose, because nothing on the request path
# read from it. Since phase 2 every request resolves a session and a membership, so
# starting without Postgres would only produce a 503 per request: it is better to say so
# once, here, than to look like the app is broken.
def serve(args) -> int:
    import uvicorn

    from ..db import is_available, session_scope
    from ..db.identity import count_users

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

    try:
        with session_scope() as session:
            if count_users(session) == 0:
                print("Todavía no hay ninguna cuenta: nadie podrá entrar.")
                print(
                    f"Crea la primera con `{PROG} create-user --username NOMBRE --admin`.\n"
                )
    except Exception:  # noqa: BLE001 - an un-migrated database is reported by the request path
        print("La base de datos responde pero no tiene el esquema. Aplica `uv run alembic upgrade head`.\n")

    uvicorn.run(
        "server.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0
