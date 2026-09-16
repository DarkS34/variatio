"""The parser and the dispatch, and nothing else.

`.env` is loaded before the subcommand modules are imported, because they read settings
at import time.
"""

import argparse
import sys

from variatio.core import languages
from variatio.core.dotenv import load_dotenv
from variatio.core.paths import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")

from . import accounts, diagnostics, instances
from .common import PROG, guarded
from .serve import serve


def main(argv: list[str] | None = None) -> int:
    """Parse the arguments and run the subcommand, returning its exit code."""
    parser, subparsers = build_parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(_with_default_command(argv, subparsers.choices))
    return args.func(args)


def build_parser():
    """Build the argument parser, returning it with its subparsers.

    Every subcommand but `db-check` and `serve` is wrapped in `guarded()`, which turns an
    unreachable database into a message instead of a stack trace.
    """
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Arranca la API de Variatio y administra su base de datos.",
    )
    subparsers = parser.add_subparsers(dest="command")

    runner = subparsers.add_parser("serve", help="arranca la API (por defecto)")
    runner.add_argument("--host", default="127.0.0.1")
    runner.add_argument("--port", type=int, default=8000)
    runner.add_argument("--reload", action="store_true", help="recarga en caliente (desarrollo)")
    runner.set_defaults(func=serve)

    importer = subparsers.add_parser(
        "import-instance", help="carga una asignatura del disco en la base de datos"
    )
    importer.add_argument("--slug", required=True, help="nombre de la asignatura en la BD")
    importer.add_argument("--name", default=None, help="nombre legible de la asignatura")
    importer.add_argument(
        "--from-workspace",
        default=None,
        metavar="SLUG",
        help="asignatura de origen en disco; por defecto, la misma que --slug",
    )
    importer.set_defaults(func=guarded(instances.import_instance))

    exporter = subparsers.add_parser(
        "export-instance", help="escribe una asignatura de la base de datos en el disco"
    )
    exporter.add_argument("--slug", required=True, help="asignatura de la BD a exportar")
    exporter.add_argument(
        "--to-workspace",
        default=None,
        metavar="SLUG",
        help="asignatura de destino en disco; por defecto, la misma que --slug",
    )
    exporter.set_defaults(func=guarded(instances.export_instance))

    listing = subparsers.add_parser("workspaces", help="lista las asignaturas de la base de datos")
    listing.set_defaults(func=guarded(instances.list_workspaces))

    maker = subparsers.add_parser("create-workspace", help="crea una asignatura vacía")
    maker.add_argument("slug", help="identificador en minúsculas, cifras y guiones")
    maker.add_argument("--name", default="", help="nombre legible; por defecto, el slug")
    maker.add_argument("--owner", default=None, metavar="USUARIO", help="cuenta que la poseerá")
    # The language of its PROMPTS, not of whoever uses it. Chosen here because it is baked
    # into the artifacts a build writes, and cannot be changed afterwards.
    maker.add_argument(
        "--language",
        default=languages.DEFAULT,
        choices=languages.LANGUAGES,
        help="idioma de los prompts de esta instancia",
    )
    maker.set_defaults(func=guarded(instances.create_workspace))

    creator = subparsers.add_parser(
        "create-user", help="crea una cuenta (la primera, o cualquier otra sin invitación)"
    )
    creator.add_argument("--username", required=True, help="con lo que entra: minúsculas y cifras")
    creator.add_argument(
        "--email", default="", help="opcional; solo sirve para entregarle enlaces por correo"
    )
    creator.add_argument("--name", default="", help="nombre visible; por defecto, el usuario")
    creator.add_argument("--admin", action="store_true", help="administra la instalación")
    # No default: an account with no workspace is a normal account, and the first thing
    # it is offered when it enters is to create its own.
    creator.add_argument(
        "--workspace", default="", help="asignatura de la que será miembro; vacío para ninguna"
    )
    creator.add_argument(
        "--role", default="owner", choices=("viewer", "editor", "owner"), help="rol en esa asignatura"
    )
    creator.add_argument(
        "--password",
        default="",
        help="contraseña; si se omite se pregunta (o se lee de VARIATIO_PASSWORD)",
    )
    creator.add_argument(
        "--profile",
        default=None,
        choices=("teacher", "student"),
        help="perfil de evaluador: decide qué se le pregunta al comparar propuestas",
    )
    # A default here and none on the registration form: there is no browser to ask, and an
    # account with no language can read nothing.
    creator.add_argument(
        "--language",
        default=languages.DEFAULT,
        choices=languages.LANGUAGES,
        help="idioma de la interfaz para esta cuenta",
    )
    creator.set_defaults(func=guarded(accounts.create_user))

    users = subparsers.add_parser("users", help="lista las cuentas y sus roles")
    users.set_defaults(func=guarded(accounts.list_users))

    granter = subparsers.add_parser("grant", help="da o cambia el rol de una cuenta en una asignatura")
    granter.add_argument("--user", required=True, help="nombre de usuario de la cuenta")
    granter.add_argument("--workspace", required=True)
    granter.add_argument("--role", default="editor", choices=("viewer", "editor", "owner"))
    granter.set_defaults(func=guarded(accounts.grant_role))

    inviter = subparsers.add_parser("invite", help="crea invitaciones de un solo uso")
    inviter.add_argument(
        "--workspace", default="", help="asignatura a la que suma; vacío para ninguna"
    )
    inviter.add_argument("--role", default="editor", choices=("viewer", "editor", "owner"))
    inviter.add_argument(
        "--alias", default="", help="nombre interno; solo lo ve el panel de administración"
    )
    inviter.add_argument("--days", type=int, default=7, help="días hasta que caduca (7)")
    inviter.add_argument(
        "--count", type=int, default=1, help="cuántas crear a la vez, con el alias numerado"
    )
    inviter.set_defaults(func=guarded(accounts.invite))

    check = subparsers.add_parser("db-check", help="comprueba la conexión con la base de datos")
    check.set_defaults(func=diagnostics.db_check)

    return parser, subparsers


def _with_default_command(argv: list[str], commands) -> list[str]:
    """Prefix `serve` unless the first argument already names a subcommand or asks for help.

    Anything that is not a subcommand is treated as arguments to `serve`, so both forms
    this entry point already supported keep working verbatim: `system` and
    `system --port 9000 --reload`.
    """
    if not argv:
        return ["serve"]
    if argv[0] in ("-h", "--help") or argv[0] in commands:
        return argv
    return ["serve", *argv]
