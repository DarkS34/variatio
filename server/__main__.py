import argparse

DB_HINT = (
    "Arranca la base de datos (`docker compose up -d postgres`) y aplica las migraciones "
    "(`uv run alembic upgrade head`)."
)


# Every database subcommand fails the same way when Postgres is not up, and a SQLAlchemy
# traceback is not an error message. `serve` is deliberately not wrapped: the API starts
# fine without a database today.
def _guarded(func):
    def run(args) -> int:
        from sqlalchemy.exc import SQLAlchemyError

        try:
            return func(args)
        except SQLAlchemyError as exc:
            from .db import database_url

            url = database_url()
            print(f"No hay conexión con la base de datos en {url.split('@')[-1]}.")
            print(DB_HINT)
            print(f"\nDetalle: {type(exc).__name__}")
            return 1
        except LookupError as exc:
            print(str(exc))
            return 1

    return run


# `serve` used to start with no database on purpose, because nothing on the request path
# read from it. Since phase 2 every request resolves a session and a membership, so
# starting without Postgres would only produce a 503 per request: it is better to say so
# once, here, than to look like the app is broken.
def _serve(args) -> int:
    import uvicorn

    from .db import is_available, session_scope
    from .db.identity import count_users

    if not is_available():
        from .db import database_url

        print(f"No hay conexión con la base de datos en {database_url().split('@')[-1]}.")
        print(DB_HINT)
        return 1

    try:
        with session_scope() as session:
            if count_users(session) == 0:
                print("Todavía no hay ninguna cuenta: nadie podrá entrar.")
                print("Crea la primera con `variant-generator-server create-user --admin`.\n")
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


def _import_instance(args) -> int:
    from variant_generator import config

    from .db import session_scope
    from .db.instance_io import import_instance

    ws = config.workspace(args.from_workspace)
    with session_scope() as session:
        summary = import_instance(session, ws, slug=args.slug, name=args.name)
    print(
        f"{summary['workspace']} (id {summary['workspace_id']}): "
        f"{len(summary['artifacts'])} artefacto(s), {summary['approvals']} aprobación(es), "
        f"{summary['raw_documents']} documento(s) en bruto"
    )
    return 0


def _export_instance(args) -> int:
    from variant_generator import config

    from .db import session_scope
    from .db.instance_io import export_instance

    ws = config.workspace(args.to_workspace)
    with session_scope() as session:
        summary = export_instance(session, args.slug, ws)
    print(f"{summary['workspace']} → {summary['root']}: {len(summary['artifacts'])} artefacto(s)")
    return 0


def _list_workspaces(_args) -> int:
    from .db import session_scope
    from .db.repository import list_workspaces

    with session_scope() as session:
        rows = list_workspaces(session)
    if not rows:
        print("No hay workspaces en la base de datos.")
        return 0
    for row in rows:
        print(f"{row.id:>4}  {row.slug:<24} {row.name}")
    return 0


# IDENTITY ------------------------------------------------------------------------------


# The first account is created here and not on the web, so that there is no moment in the
# system's life when it accepts a registration without credentials. Every later account
# arrives through a single-use invitation.
def _create_user(args) -> int:
    from .auth import passwords
    from .db import session_scope
    from .db.identity import create_user, get_user, grant, normalise_email
    from .db.repository import ensure_workspace

    password = _ask_password(args)
    if password is None:
        return 1

    email = normalise_email(args.email)
    error = passwords.policy_error(password, email=email, name=args.name or "")
    if error:
        print(error)
        return 1

    with session_scope() as session:
        if get_user(session, email) is not None:
            print(f"Ya existe una cuenta con el correo {email}.")
            return 1
        user = create_user(
            session,
            email=email,
            name=args.name or email.split("@")[0],
            password_hash=passwords.hash_password(password),
            is_admin=args.admin,
            email_verified=True,
        )
        workspace = ensure_workspace(session, args.workspace)
        grant(session, workspace.id, user.id, args.role)
        print(
            f"Cuenta creada: {user.email} ({'administrador' if user.is_admin else 'usuario'}), "
            f"{args.role} de '{workspace.slug}'."
        )
    return 0


def _list_users(_args) -> int:
    from .db import session_scope
    from .db.identity import list_users, memberships_for

    with session_scope() as session:
        users = list_users(session)
        if not users:
            print("No hay cuentas. Crea la primera con `create-user --admin`.")
            return 0
        for user in users:
            roles = ", ".join(f"{w.slug}:{m.role}" for m, w in memberships_for(session, user.id))
            flags = " [admin]" if user.is_admin else ""
            flags += " [desactivada]" if not user.active else ""
            print(f"{user.id:>4}  {user.email:<32} {roles or '(sin workspaces)'}{flags}")
    return 0


def _grant(args) -> int:
    from .db import session_scope
    from .db.identity import get_user, grant
    from .db.repository import get_workspace

    with session_scope() as session:
        user = get_user(session, args.email)
        if user is None:
            print(f"No existe ninguna cuenta con el correo {args.email}.")
            return 1
        workspace = get_workspace(session, args.workspace)
        if workspace is None:
            print(f"No existe el workspace '{args.workspace}'. Créalo con `import-instance`.")
            return 1
        grant(session, workspace.id, user.id, args.role)
        print(f"{user.email} es ahora {args.role} de '{workspace.slug}'.")
    return 0


def _invite(args) -> int:
    from .auth import mail, tokens
    from .db import session_scope
    from .db.identity import create_invite
    from .db.repository import get_workspace
    from .settings import INVITE_TTL, public_base_url

    with session_scope() as session:
        workspace_id = None
        if args.workspace:
            workspace = get_workspace(session, args.workspace)
            if workspace is None:
                print(f"No existe el workspace '{args.workspace}'.")
                return 1
            workspace_id = workspace.id

        token = tokens.new_token()
        create_invite(
            session,
            token_hash=tokens.digest(token),
            ttl=INVITE_TTL,
            email=args.email,
            workspace_id=workspace_id,
            role=args.role,
        )

    base = public_base_url() or "http://localhost:8000"
    link = f"{base}/invitacion?token={token}"
    if args.email and mail.send(
        args.email,
        "Te han invitado al generador de variantes",
        f"Crea tu cuenta con este enlace, válido {INVITE_TTL.days} días:\n{link}\n",
    ):
        print(f"Invitación enviada a {args.email}.")
    print(link)
    return 0


def _ask_password(args) -> str | None:
    import getpass
    import os

    if args.password:
        return args.password
    from_env = os.environ.get("VG_PASSWORD")
    if from_env:
        return from_env
    try:
        first = getpass.getpass("Contraseña: ")
        second = getpass.getpass("Repítela: ")
    except (EOFError, KeyboardInterrupt):
        print("\nCancelado.")
        return None
    if first != second:
        print("Las dos contraseñas no coinciden.")
        return None
    return first


def _db_check(_args) -> int:
    from .db import database_url, is_available

    url = database_url()
    # Never print the password: the URL comes from the environment and usually has one.
    safe = url.split("@")[-1] if "@" in url else url
    if is_available():
        print(f"Base de datos accesible en {safe}")
        return 0
    print(f"No hay conexión con la base de datos en {safe}")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="variant-generator-server",
        description="Arranca la API del generador de variantes y administra su base de datos.",
    )
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser("serve", help="arranca la API (por defecto)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true", help="recarga en caliente (desarrollo)")
    serve.set_defaults(func=_serve)

    importer = subparsers.add_parser(
        "import-instance", help="carga un workspace del disco en la base de datos"
    )
    importer.add_argument("--slug", default="default", help="nombre del workspace en la BD")
    importer.add_argument("--name", default=None, help="nombre legible del workspace")
    importer.add_argument(
        "--from-workspace",
        default=None,
        metavar="SLUG",
        help="workspace de origen en disco; omitido significa la instancia de un solo usuario",
    )
    importer.set_defaults(func=_guarded(_import_instance))

    exporter = subparsers.add_parser(
        "export-instance", help="escribe un workspace de la base de datos en el disco"
    )
    exporter.add_argument("--slug", default="default", help="workspace de la BD a exportar")
    exporter.add_argument(
        "--to-workspace",
        default=None,
        metavar="SLUG",
        help="workspace de destino en disco; omitido significa la instancia de un solo usuario",
    )
    exporter.set_defaults(func=_guarded(_export_instance))

    listing = subparsers.add_parser("workspaces", help="lista los workspaces de la base de datos")
    listing.set_defaults(func=_guarded(_list_workspaces))

    creator = subparsers.add_parser(
        "create-user", help="crea una cuenta (la primera, o cualquier otra sin invitación)"
    )
    creator.add_argument("--email", required=True)
    creator.add_argument("--name", default="", help="nombre visible; por defecto, el del correo")
    creator.add_argument("--admin", action="store_true", help="administra la instalación")
    creator.add_argument("--workspace", default="default", help="workspace del que será miembro")
    creator.add_argument(
        "--role", default="owner", choices=("viewer", "editor", "owner"), help="rol en ese workspace"
    )
    creator.add_argument(
        "--password",
        default="",
        help="contraseña; si se omite se pregunta (o se lee de VG_PASSWORD)",
    )
    creator.set_defaults(func=_guarded(_create_user))

    users = subparsers.add_parser("users", help="lista las cuentas y sus roles")
    users.set_defaults(func=_guarded(_list_users))

    granter = subparsers.add_parser("grant", help="da o cambia el rol de una cuenta en un workspace")
    granter.add_argument("--email", required=True)
    granter.add_argument("--workspace", default="default")
    granter.add_argument("--role", default="editor", choices=("viewer", "editor", "owner"))
    granter.set_defaults(func=_guarded(_grant))

    inviter = subparsers.add_parser("invite", help="crea una invitación de un solo uso")
    inviter.add_argument("--email", default=None, help="dirección a la que va dirigida")
    inviter.add_argument("--workspace", default="default", help="workspace al que suma; '' para ninguno")
    inviter.add_argument("--role", default="editor", choices=("viewer", "editor", "owner"))
    inviter.set_defaults(func=_guarded(_invite))

    check = subparsers.add_parser("db-check", help="comprueba la conexión con la base de datos")
    check.set_defaults(func=_db_check)

    # Anything that is not one of the subcommands is treated as arguments to `serve`, so
    # the two forms this entry point already supported keep working verbatim:
    # `variant-generator-server` and `variant-generator-server --port 9000 --reload`.
    import sys

    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in ("-h", "--help") and argv[0] not in subparsers.choices:
        argv = ["serve", *argv]
    elif not argv:
        argv = ["serve"]

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
