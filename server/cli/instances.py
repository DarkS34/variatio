"""`import-instance`, `export-instance`, `workspaces` and `create-workspace`."""


def _slug_error(*slugs: str | None) -> str | None:
    """Return the first complaint about these slugs, or None when all of them are usable."""
    from ..settings import slug_error

    for slug in slugs:
        if slug is None:
            continue
        error = slug_error(slug)
        if error:
            return f"«{slug}» no vale como espacio de trabajo. {error}"
    return None


def import_instance(args) -> int:
    """Load a workspace's directory into the database, and print what arrived."""
    from variatio.core import paths

    from ..db import session_scope
    from ..db.instance_io import import_instance as load

    error = _slug_error(args.slug, args.from_workspace)
    if error:
        print(error)
        return 1

    ws = paths.workspace(args.from_workspace or args.slug)
    with session_scope() as session:
        summary = load(session, ws, slug=args.slug, name=args.name)
    print(
        f"{summary['workspace']} (id {summary['workspace_id']}): "
        f"{len(summary['artifacts'])} artefacto(s), {summary['approvals']} aprobación(es), "
        f"{summary['raw_documents']} documento(s) en bruto"
    )
    return 0


def export_instance(args) -> int:
    """Write a workspace of the database back out to disk, and print what was written."""
    from variatio.core import paths

    from ..db import session_scope
    from ..db.instance_io import export_instance as dump

    error = _slug_error(args.slug, args.to_workspace)
    if error:
        print(error)
        return 1

    ws = paths.workspace(args.to_workspace or args.slug)
    with session_scope() as session:
        summary = dump(session, args.slug, ws)
    print(f"{summary['workspace']} → {summary['root']}: {len(summary['artifacts'])} artefacto(s)")
    return 0


def list_workspaces(_args) -> int:
    """Print every workspace of the database with the directory it reads."""
    from ..db import session_scope
    from ..db.repository import list_workspaces as rows_of
    from ..settings import workspace_for

    with session_scope() as session:
        rows = rows_of(session)
    if not rows:
        print("No hay espacios de trabajo en la base de datos.")
        return 0
    for row in rows:
        print(f"{row.id:>4}  {row.slug:<24} {row.name:<32} {workspace_for(row.slug).root}")
    return 0


def create_workspace(args) -> int:
    """Create an empty workspace, provision its tree, and optionally give it an owner.

    The web can create one too — any account may, since «tener varios grafos» is «tener
    varios workspaces» — but the command line is what an operator uses to prepare one
    before there is anybody to hand it to. The prompt language is chosen here and never
    after: it is baked into the artifacts a build writes.
    """
    from ..db import session_scope
    from ..db.identity import get_user, grant
    from ..db.models import OWNER
    from ..db.repository import create_workspace as insert, get_workspace
    from variatio.instance import locale

    from ..settings import provision, slug_error, workspace_for

    error = slug_error(args.slug)
    if error:
        print(error)
        return 1

    with session_scope() as session:
        if get_workspace(session, args.slug) is not None:
            print(f"Ya existe el espacio de trabajo '{args.slug}'.")
            return 1

        workspace = insert(
            session, args.slug, args.name or args.slug, prompt_language=args.language
        )
        if args.owner:
            user = get_user(session, args.owner)
            if user is None:
                print(f"No existe ninguna cuenta con el usuario {args.owner}.")
                return 1
            grant(session, workspace.id, user.id, OWNER)

        ws = workspace_for(args.slug)
        provision(ws)
        # The file and not the column is what a build reads: the pipeline runs with no
        # database at all, and the row beside it is a mirror for the panel to list by.
        locale.set_prompt_language(ws, args.language)
        print(
            f"Espacio de trabajo '{workspace.slug}' creado en {ws.root}, "
            f"con los prompts en «{args.language}»"
        )
        if args.owner:
            print(f"{args.owner} es su propietario.")
        else:
            print("Sin miembros todavía: dáselos con `grant --workspace " f"{args.slug}`.")
    return 0
