# The console script declared in pyproject. Named once, because every printed hint quotes a
# command the reader is meant to type: the entry point was renamed to `system-run` in
# 0f3ed81 and these strings kept naming the old one, which does not exist.
PROG = "system-run"

DB_HINT = (
    "Arranca la base de datos (`docker compose up -d postgres`) y aplica las migraciones "
    "(`uv run alembic upgrade head`)."
)


def database_hint() -> None:
    from ..db import database_url

    url = database_url()
    print(f"No hay conexión con la base de datos en {url.split('@')[-1]}.")
    print(DB_HINT)


# Every database subcommand fails the same way when Postgres is not up, and a SQLAlchemy
# traceback is not an error message. Two are deliberately not wrapped: `db-check`, whose
# whole job is to report that failure, and `serve`, which checks the connection itself
# before uvicorn takes over.
def guarded(func):
    def run(args) -> int:
        from sqlalchemy.exc import SQLAlchemyError

        try:
            return func(args)
        except SQLAlchemyError as exc:
            database_hint()
            print(f"\nDetalle: {type(exc).__name__}")
            return 1
        except LookupError as exc:
            print(str(exc))
            return 1

    return run
