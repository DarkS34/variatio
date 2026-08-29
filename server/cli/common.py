"""What every subcommand shares: the program's own name, and the database guard."""

# The console script declared in pyproject. Named once, because every printed hint quotes a
# command the reader is meant to type — and naming it once did not keep it true, so
# `tests/server/test_cli_prog.py` checks it against the console scripts that are installed.
PROG = "system"

DB_HINT = (
    "Arranca la base de datos (`docker compose up -d postgres`) y aplica las migraciones "
    "(`uv run alembic upgrade head`)."
)


def database_hint() -> None:
    """Print where the database was expected and the two commands that bring it up."""
    from ..db import database_url

    url = database_url()
    print(f"No hay conexión con la base de datos en {url.split('@')[-1]}.")
    print(DB_HINT)


def refusal(exc) -> str:
    """The one readable line inside a SQLAlchemy error, without the SQL and the params.

    `str()` of a `DBAPIError` carries the whole statement and every bound parameter, which
    for an artifact is hundreds of kilobytes. What says what went wrong is the driver's own
    exception, and its first line is the sentence a person can act on.
    """
    original = getattr(exc, "orig", None) or exc
    return str(original).strip().splitlines()[0]


def guarded(func):
    """Wrap a subcommand so a database failure prints a message instead of a stack trace.

    Two failures reach here and they are not the same: the database cannot be REACHED, and
    the database rejected what it was asked. Only the first is answered with «arranca la
    base de datos» — telling somebody to start a Postgres they already have running is how
    a corrupt artifact spent months looking like a connection problem. Two subcommands are
    deliberately not wrapped: `db-check`, whose whole job is to report that failure, and
    `serve`, which checks the connection itself before uvicorn takes over.
    """

    def run(args) -> int:
        """Run the subcommand, turning a database or lookup failure into a message."""
        from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError

        try:
            return func(args)
        except (OperationalError, InterfaceError) as exc:
            database_hint()
            print(f"\nDetalle: {type(exc).__name__}")
            return 1
        except SQLAlchemyError as exc:
            print(f"La base de datos rechazó la operación ({type(exc).__name__}):")
            print(f"  {refusal(exc)}")
            return 1
        except LookupError as exc:
            print(str(exc))
            return 1

    return run
