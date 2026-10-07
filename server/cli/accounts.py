"""`create-user`, `users`, `grant`, `invite` and `class-link`."""

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
    from ..db.models import TEACHER, VIA_CLI
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
            # An administrator is a teacher, whatever the flag said.
            evaluator_profile=TEACHER if args.admin else args.profile,
            ui_language=getattr(args, "language", None),
        )
        membership = "sin asignatura"
        if args.workspace:
            workspace = ensure_workspace(session, args.workspace)
            grant(session, workspace.id, user.id, args.role, via=VIA_CLI)
            membership = f"{args.role} de '{workspace.slug}'"
        profile = PROFILE_LABELS.get(user.evaluator_profile, "sin perfil")
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
    """Print every account with its roles, its flags and its profile."""
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
    from ..db.models import VIA_CLI
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
        grant(session, workspace.id, user.id, args.role, via=VIA_CLI)
        print(f"{user.username} es ahora {args.role} de '{workspace.slug}'.")
    return 0


def invite(args) -> int:
    """Mint single-use invitations and print their links, one per line.

    The link *is* the invitation: whoever opens it chooses their own username, and the
    invitation says what the account will be (`--profile`): nobody asks them. `--alias` names
    it for the administration panel only, numbered when `--count` asks for several.
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
                profile=args.profile,
            )
            link = f"{base}/invite?token={token}"
            printed.append((f"{name}\t{link}" if name else link, invite.token_sealed is not None))

    for line, _ in printed:
        print(line)
    who = PROFILE_LABELS[args.profile]
    print(
        f"Caducan en {args.days} día(s). Quien canjee cada enlace elegirá su usuario "
        f"y su cuenta será de {who}."
    )
    if not all(stored for _, stored in printed):
        print("No se ha podido guardar el enlace para volver a verlo en el panel: cópialo ahora.")
    return 0


def class_link(args) -> int:
    """Print a subject's class link, minting one when it has none or `--renew` asks for another.

    The link lets as many students in as it has seats, each choosing their own username, and
    every account it creates is a student's. Renewing retires the live one at once: whoever
    entered through it stays.
    """
    from datetime import timedelta

    from ..auth import links
    from ..db import session_scope
    from ..db.identity import live_class_link, now, revoke_class_link
    from ..db.repository import get_workspace
    from ..installation import (
        CLASS_LINK_DEFAULT_DAYS,
        CLASS_LINK_DEFAULT_SEATS,
        CLASS_LINK_MAX_SEATS,
        TEACHER_LINK_MAX_DAYS,
        public_base_url,
    )

    seats = CLASS_LINK_DEFAULT_SEATS if args.seats is None else args.seats
    days = CLASS_LINK_DEFAULT_DAYS if args.days is None else args.days
    if not 1 <= seats <= CLASS_LINK_MAX_SEATS:
        print(f"--seats va de 1 a {CLASS_LINK_MAX_SEATS}.")
        return 1
    if not 1 <= days <= TEACHER_LINK_MAX_DAYS:
        print(f"--days va de 1 a {TEACHER_LINK_MAX_DAYS}.")
        return 1

    base = public_base_url() or "http://localhost:8000"
    with session_scope() as session:
        workspace = get_workspace(session, args.workspace)
        if workspace is None:
            print(f"No existe la asignatura '{args.workspace}'.")
            return 1
        live = live_class_link(session, workspace.id)
        if live is not None and not args.renew:
            token = links.unseal(live.token_sealed, live.token_hash)
            if token is None:
                print("El enlace vivo no se puede abrir con la clave de esta instalación: usa --renew.")
                return 1
            state = "en pausa" if live.paused_at is not None else "activo"
            print(links.url_for(base, token))
            print(
                f"{live.uses} de {live.max_uses} plazas ocupadas · caduca el "
                f"{live.expires_at:%Y-%m-%d} · {state}. Para cambiarlo, usa --renew."
            )
            return 0
        if live is not None:
            revoke_class_link(session, live)
        link, token = links.mint_class_link(
            session,
            workspace_id=workspace.id,
            expires_at=now() + timedelta(days=days),
            max_uses=seats,
        )
        print(links.url_for(base, token))
        print(
            f"{'Renovado' if live is not None else 'Creado'}: {seats} plazas, caduca en {days} día(s). "
            "Cada cuenta que cree será de alumno."
        )
        if link.token_sealed is None:
            print("No se ha podido guardar el enlace para volver a verlo: cópialo ahora.")
    return 0
