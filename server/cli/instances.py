def _slug_error(*slugs: str | None) -> str | None:
    from ..settings import slug_error

    for slug in slugs:
        if slug is None:
            continue
        error = slug_error(slug)
        if error:
            return f"«{slug}» no vale como workspace. {error}"
    return None


def import_instance(args) -> int:
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
    from ..db import session_scope
    from ..db.repository import list_workspaces as rows_of
    from ..settings import workspace_for

    with session_scope() as session:
        rows = rows_of(session)
    if not rows:
        print("No hay workspaces en la base de datos.")
        return 0
    for row in rows:
        print(f"{row.id:>4}  {row.slug:<24} {row.name:<32} {workspace_for(row.slug).root}")
    return 0


# The web can create workspaces too — any account may, since «tener varios grafos» is
# «tener varios workspaces» — but the command line is what an operator uses to prepare one
# before there is anybody to hand it to.
def create_workspace(args) -> int:
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
            print(f"Ya existe el workspace '{args.slug}'.")
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
        # database at all, so the row beside it is a mirror for the panel to list by.
        locale.set_prompt_language(ws, args.language)
        print(
            f"Workspace '{workspace.slug}' creado en {ws.root}, "
            f"con los prompts en «{args.language}»"
        )
        if args.owner:
            print(f"{args.owner} es su propietario.")
        else:
            print("Sin miembros todavía: dáselos con `grant --workspace " f"{args.slug}`.")
    return 0
