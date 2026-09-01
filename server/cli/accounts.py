"""`create-user`, `users`, `grant` and `invite`."""

# What the two profiles are called when a command prints one. The web keeps its own copy
# for the same reason every other label does: this one is read in a terminal.
PROFILE_LABELS = {"teacher": "docente", "student": "alumno"}


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
        membership = "sin espacio de trabajo"
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
                f"{roles or '(sin espacios de trabajo)'}{flags}"
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
            print(f"No existe el espacio de trabajo '{args.workspace}'. Créalo con `import-instance`.")
            return 1
        grant(session, workspace.id, user.id, args.role)
        print(f"{user.username} es ahora {args.role} de '{workspace.slug}'.")
    return 0


def invite(args) -> int:
    """Mint a single-use invitation and print its link.

    The link *is* the invitation: whoever opens it chooses their own username and says
    whether they teach or study, so it binds the access and nothing else.
    """
    from ..auth import tokens
    from ..db import session_scope
    from ..db.identity import create_invite
    from ..db.repository import get_workspace
    from ..settings import INVITE_TTL, public_base_url

    with session_scope() as session:
        workspace_id = None
        if args.workspace:
            workspace = get_workspace(session, args.workspace)
            if workspace is None:
                print(f"No existe el espacio de trabajo '{args.workspace}'.")
                return 1
            workspace_id = workspace.id

        token = tokens.new_token()
        create_invite(
            session,
            token_hash=tokens.digest(token),
            ttl=INVITE_TTL,
            workspace_id=workspace_id,
            role=args.role,
        )

    base = public_base_url() or "http://localhost:8000"
    print(f"{base}/invite?token={token}")
    print("Quien lo canjee elegirá su usuario y dirá si da clase o si estudia.")
    return 0
