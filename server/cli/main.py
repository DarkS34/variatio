import argparse
import sys

from variatio.core.dotenv import load_dotenv
from variatio.core.paths import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")

from . import accounts, diagnostics, instances
from .common import PROG, guarded
from .serve import serve


def build_parser():
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Arranca la API del generador de variantes y administra su base de datos.",
    )
    subparsers = parser.add_subparsers(dest="command")

    runner = subparsers.add_parser("serve", help="arranca la API (por defecto)")
    runner.add_argument("--host", default="127.0.0.1")
    runner.add_argument("--port", type=int, default=8000)
    runner.add_argument("--reload", action="store_true", help="recarga en caliente (desarrollo)")
    runner.set_defaults(func=serve)

    importer = subparsers.add_parser(
        "import-instance", help="carga un workspace del disco en la base de datos"
    )
    importer.add_argument("--slug", required=True, help="nombre del workspace en la BD")
    importer.add_argument("--name", default=None, help="nombre legible del workspace")
    importer.add_argument(
        "--from-workspace",
        default=None,
        metavar="SLUG",
        help="workspace de origen en disco; por defecto, el mismo que --slug",
    )
    importer.set_defaults(func=guarded(instances.import_instance))

    exporter = subparsers.add_parser(
        "export-instance", help="escribe un workspace de la base de datos en el disco"
    )
    exporter.add_argument("--slug", required=True, help="workspace de la BD a exportar")
    exporter.add_argument(
        "--to-workspace",
        default=None,
        metavar="SLUG",
        help="workspace de destino en disco; por defecto, el mismo que --slug",
    )
    exporter.set_defaults(func=guarded(instances.export_instance))

    listing = subparsers.add_parser("workspaces", help="lista los workspaces de la base de datos")
    listing.set_defaults(func=guarded(instances.list_workspaces))

    maker = subparsers.add_parser("create-workspace", help="crea un workspace vacío")
    maker.add_argument("slug", help="identificador en minúsculas, cifras y guiones")
    maker.add_argument("--name", default="", help="nombre legible; por defecto, el slug")
    maker.add_argument("--owner", default=None, metavar="USUARIO", help="cuenta que lo poseerá")
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
        "--workspace", default="", help="workspace del que será miembro; vacío para ninguno"
    )
    creator.add_argument(
        "--role", default="owner", choices=("viewer", "editor", "owner"), help="rol en ese workspace"
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
    creator.set_defaults(func=guarded(accounts.create_user))

    users = subparsers.add_parser("users", help="lista las cuentas y sus roles")
    users.set_defaults(func=guarded(accounts.list_users))

    granter = subparsers.add_parser("grant", help="da o cambia el rol de una cuenta en un workspace")
    granter.add_argument("--user", required=True, help="nombre de usuario de la cuenta")
    granter.add_argument("--workspace", required=True)
    granter.add_argument("--role", default="editor", choices=("viewer", "editor", "owner"))
    granter.set_defaults(func=guarded(accounts.grant_role))

    inviter = subparsers.add_parser("invite", help="crea una invitación de un solo uso")
    inviter.add_argument(
        "--workspace", default="", help="workspace al que suma; vacío para ninguno"
    )
    inviter.add_argument("--role", default="editor", choices=("viewer", "editor", "owner"))
    inviter.add_argument(
        "--profile",
        default=None,
        choices=("teacher", "student"),
        help="perfil con el que nacerá la cuenta que canjee el enlace",
    )
    inviter.set_defaults(func=guarded(accounts.invite))

    check = subparsers.add_parser("db-check", help="comprueba la conexión con la base de datos")
    check.set_defaults(func=diagnostics.db_check)

    return parser, subparsers


# Anything that is not one of the subcommands is treated as arguments to `serve`, so the two
# forms this entry point already supported keep working verbatim: `system` and
# `system --port 9000 --reload`.
def _with_default_command(argv: list[str], commands) -> list[str]:
    if not argv:
        return ["serve"]
    if argv[0] in ("-h", "--help") or argv[0] in commands:
        return argv
    return ["serve", *argv]


def main(argv: list[str] | None = None) -> int:
    parser, subparsers = build_parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(_with_default_command(argv, subparsers.choices))
    return args.func(args)
