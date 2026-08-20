# The console script declared in pyproject. Named once, because every printed hint quotes a
# command the reader is meant to type. Naming it once did not keep it true: the entry point
# has been renamed twice and both times these strings stayed on the previous name, so
# `tests/test_cli_prog.py` now checks it against the console scripts that are installed.
PROG = "system"

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
