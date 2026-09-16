"""`create-user`, `users`, `grant` and `invite`."""

# What the two profiles are called when a command prints one. The web keeps its own copy
# for the same reason every other label does: this one is read in a terminal.
PROFILE_LABELS = {"teacher": "docente", "student": "alumno"}


def create_user(args) -> int:
    """Create one account, with an optional membership.

    The first account is created here and not on the web, so that there is no moment in
    the system's life when it accepts a registration without credentials; every later one
    arrives through a single-use invitation. Naming a workspace attaches the account to
    it, and belonging to none is a normal state.
    """
    from ..auth import passwords
    from ..db import session_scope
    from ..db.identity import (
        create_user as insert,
        get_user,
        grant,
        normalise_username,
        username_error,
    )
    from ..db.repository import ensure_workspace

    username = normalise_username(args.username)
    error = username_error(username)
    if error:
        print(error)
        return 1

    password = _ask_password(args)
    if password is None:
        return 1

    error = passwords.policy_error(password, account=username, name=args.name or "")
    if error:
        print(error)
        return 1

    with session_scope() as session:
        if get_user(session, username) is not None:
            print(f"Ya existe una cuenta con el usuario {username}.")
            return 1
        user = insert(
            session,
            username=username,
            name=args.name or username,
            password_hash=passwords.hash_password(password),
            email=args.email or None,
            is_admin=args.admin,
            email_verified=bool(args.email),
            evaluator_profile=getattr(args, "profile", None),
            ui_language=getattr(args, "language", None),
        )
        membership = "sin asignatura"
        if args.workspace:
            workspace = ensure_workspace(session, args.workspace)
            grant(session, workspace.id, user.id, args.role)
            membership = f"{args.role} de '{workspace.slug}'"
        profile = PROFILE_LABELS.get(user.evaluator_profile, "sin perfil de evaluador")
        print(
            f"Cuenta creada: {user.username} "
            f"({'administrador' if user.is_admin else 'usuario'}), "
            f"{membership}, {profile}."
        )
    return 0


def _ask_password(args) -> str | None:
    """Take the password from the flag or the environment, or ask for it twice.

    None when the two do not match, or when the prompt was cancelled.
    """
    import getpass
    import os

    if args.password:
        return args.password
    from_env = os.environ.get("VARIATIO_PASSWORD")
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


def list_users(_args) -> int:
    """Print every account with its roles, its flags and its evaluator profile."""
    from ..db import session_scope
    from ..db.identity import list_users as rows_of, memberships_for

    with session_scope() as session:
        users = rows_of(session)
        if not users:
            print("No hay cuentas. Crea la primera con `create-user --username NOMBRE --admin`.")
            return 0
        for user in users:
            roles = ", ".join(f"{w.slug}:{m.role}" for m, w in memberships_for(session, user.id))
            flags = " [admin]" if user.is_admin else ""
            flags += " [desactivada]" if not user.active else ""
            profile = PROFILE_LABELS.get(user.evaluator_profile, "—")
            print(
                f"{user.id:>4}  {user.username:<24} {profile:<8} "
                f"{roles or '(sin asignaturas)'}{flags}"
            )
    return 0


def grant_role(args) -> int:
    """Give an account a role in a workspace, or name whichever of the two is missing."""
    from ..db import session_scope
    from ..db.identity import get_user, grant
    from ..db.repository import get_workspace

    with session_scope() as session:
        user = get_user(session, args.user)
        if user is None:
            print(f"No existe ninguna cuenta con el usuario {args.user}.")
            return 1
        workspace = get_workspace(session, args.workspace)
        if workspace is None:
            print(f"No existe la asignatura '{args.workspace}'. Créala con `import-instance`.")
            return 1
        grant(session, workspace.id, user.id, args.role)
        print(f"{user.username} es ahora {args.role} de '{workspace.slug}'.")
    return 0


def invite(args) -> int:
    """Mint single-use invitations and print their links, one per line.

    The link *is* the invitation: whoever opens it chooses their own username and says
    whether they teach or study, so it binds the access and nothing else. `--alias` names it
    for the administration panel only, numbered when `--count` asks for several.
    """
    from datetime import timedelta

    from ..auth import links
    from ..db import session_scope
    from ..db.identity import batch_labels, label_error, normalise_label, now
    from ..db.repository import get_workspace
    from ..installation import INVITE_BATCH_MAX, public_base_url

    if args.days <= 0:
        print("--days tiene que ser un número de días mayor que cero.")
        return 1
    if not 1 <= args.count <= INVITE_BATCH_MAX:
        print(f"--count va de 1 a {INVITE_BATCH_MAX}.")
        return 1
    label = normalise_label(args.alias)
    error = label_error(label)
    if error:
        print(error)
        return 1

    base = public_base_url() or "http://localhost:8000"
    printed = []
    with session_scope() as session:
        workspace_id = None
        if args.workspace:
            workspace = get_workspace(session, args.workspace)
            if workspace is None:
                print(f"No existe la asignatura '{args.workspace}'.")
                return 1
            workspace_id = workspace.id
        try:
            labels = batch_labels(session, label, args.count)
        except ValueError as exc:
            print(exc)
            return 1

        expires_at = now() + timedelta(days=args.days)
        for name in labels:
            invite, token = links.mint(
                session,
                expires_at=expires_at,
                workspace_id=workspace_id,
                role=args.role,
                label=name,
            )
            link = f"{base}/invite?token={token}"
            printed.append((f"{name}\t{link}" if name else link, invite.token_sealed is not None))

    for line, _ in printed:
        print(line)
    print(
        f"Caducan en {args.days} día(s). Quien canjee cada enlace elegirá su usuario "
        "y dirá si da clase o si estudia."
    )
    if not all(stored for _, stored in printed):
        print("No se ha podido guardar el enlace para volver a verlo en el panel: cópialo ahora.")
    return 0
