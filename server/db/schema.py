"""Whether the database's schema is the one this code was written against.

A database that answers is not a database that is up to date, and the difference is
invisible until a request touches the column the migration would have added: what reaches
the person is a 500 on an unrelated button — deleting a workspace loads its generations to
cascade them, so a missing `generations.model` broke a route that has nothing to do with
which model wrote anything. Comparing the revisions costs one query and turns that into a
sentence naming the command that fixes it.

Alembic is imported inside the functions, so `import server.db` stays free of it.
"""

from variatio.core.paths import PROJECT_ROOT

from .session import engine

MIGRATE = "uv run alembic upgrade head"


def _script():
    """Return the migration directory, addressed absolutely and not through the CWD."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config()
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    return ScriptDirectory.from_config(config)


def head_revisions() -> set[str]:
    """Return the revisions this checkout's migrations end at."""
    return set(_script().get_heads())


def applied_revisions() -> set[str]:
    """Return the revisions the database says it is at, empty when it has never migrated."""
    from alembic.runtime.migration import MigrationContext

    with engine().connect() as connection:
        return set(MigrationContext.configure(connection).get_current_heads())


def _known(revisions: set[str]) -> bool:
    """Return whether this checkout's migrations know every revision the database names."""
    script = _script()
    for revision in revisions:
        try:
            if script.get_revision(revision) is None:
                return False
        except Exception:  # noqa: BLE001 - an unresolvable revision is the answer itself
            return False
    return True


def mismatch() -> str | None:
    """Return what to say about the schema, or None when there is nothing to say.

    None covers three states and they are all «do not stand in the way»: the schema is at
    head, the migrations cannot be read at all (a checkout without them is not this
    check's business), and the database cannot be reached — that failure has its own
    message and its own caller.
    """
    try:
        head = head_revisions()
    except Exception:  # noqa: BLE001 - no migrations to compare against is not a fault
        return None
    if not head:
        return None

    try:
        applied = applied_revisions()
    except Exception:  # noqa: BLE001 - an unreachable database is reported by its own check
        return None

    if applied == head:
        return None

    if not applied:
        return (
            "La base de datos responde pero no tiene el esquema: le falta `alembic_version`.\n"
            f"Aplica las migraciones: `{MIGRATE}`."
        )

    now, expected = ", ".join(sorted(applied)), ", ".join(sorted(head))
    if not _known(applied):
        return (
            f"La base de datos está en «{now}», una revisión que este código no conoce: "
            f"espera «{expected}».\n"
            "El código es más antiguo que la base de datos; actualízalo antes de servir."
        )
    return (
        f"El esquema de la base de datos está en «{now}» y este código espera «{expected}».\n"
        f"Aplica las migraciones: `{MIGRATE}`."
    )
