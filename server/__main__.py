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


def _serve(args) -> int:
    import uvicorn

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
