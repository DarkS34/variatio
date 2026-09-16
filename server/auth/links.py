"""The link that IS an invitation: minting it, reading it back out of a paste, keeping it sealed.

Sessions and password resets keep only a digest, and so did invitations until the
administrator asked to read a link again after handing it over. What keeps that from
turning `invites` into a drawer of live credentials is where the KEY lives:
`VARIATIO_INVITE_LINK_KEY` in the environment, or else `/.invite_link_key` at the project
root, created with mode 0600 the first time a link is sealed — never in a column. A copy of
the database alone therefore opens no door, and with the key lost every link keeps working
and merely stops being showable.

Fernet — AES-CBC plus HMAC-SHA256, from `cryptography` — and not a construction of our own.
The digest is still what a request is looked up by; the sealed copy is opened only when an
administrator asks for it, and what it opens is checked against that row's digest before it
is believed, so a ciphertext copied onto another row reads as unrecoverable rather than as
the wrong link.
"""

import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger
from sqlalchemy.orm import Session

from variatio.core import paths

from ..db import identity
from ..db.models import EDITOR, Invite
from . import tokens

KEY_ENV = "VARIATIO_INVITE_LINK_KEY"
KEY_FILE = ".invite_link_key"

# What `tokens.new_token` produces: 32 random bytes as unpadded URL-safe base64.
TOKEN_SHAPE = re.compile(r"\A[A-Za-z0-9_-]{43}\Z")

# A floor against a code typed by hand ("aaaa…"), not a strength meter. A random token has
# 31.5 distinct characters on average, and the chance of one having fewer than 16 is
# 5.5e-14, so no link this system minted is ever refused by it.
MIN_DISTINCT = 16

# `token=` wherever it sits in what was pasted: a whole link, a link a mail client wrapped,
# or the bare `token=…` pair.
_TOKEN_PARAM = re.compile(r"(?:\A|[?&#;\s])token=([^&#\s]+)")

# A file another process is still writing reads empty; this is how long that is waited for.
_EMPTY_KEY_RETRIES = 20
_EMPTY_KEY_PAUSE = 0.05

_key_path: Path | None = None


def mint(
    session: Session,
    *,
    expires_at: datetime,
    workspace_id: int | None = None,
    role: str = EDITOR,
    created_by: int | None = None,
    label: str | None = None,
    token: str | None = None,
) -> tuple[Invite, str]:
    """Insert one invitation and return it with its token, a fresh one unless one is given.

    The only writer of an invitation, so the panel and the command line cannot disagree
    about what one holds. A seal that fails leaves `token_sealed` empty rather than failing
    the invitation: the link is handed over now either way, it just cannot be shown later.
    """
    token = token or tokens.new_token()
    invite = identity.create_invite(
        session,
        token_hash=tokens.digest(token),
        expires_at=expires_at,
        workspace_id=workspace_id,
        role=role,
        created_by=created_by,
        label=label,
        token_sealed=seal(token),
    )
    return invite, token


def token_from(text: str) -> str:
    """Return the token a pasted link carries, or the pasted text itself when it is bare.

    The origin is never read: a link minted while the installation answered at another
    address still names the same invitation.
    """
    text = text.strip()
    found = _TOKEN_PARAM.search(text)
    return unquote(found.group(1)) if found else text


def shape_error(token: str) -> str | None:
    """Say why this cannot be a token this system minted, or None when it can be."""
    if not TOKEN_SHAPE.match(token):
        return (
            "Eso no es un enlace de invitación: el código que va detrás de «token=» tiene "
            "43 caracteres (letras, números, «-» y «_»)."
        )
    if len(set(token)) < MIN_DISTINCT:
        return "Ese código no lo ha generado Variatio: parece escrito a mano."
    return None


def seal(token: str) -> str | None:
    """Encrypt a token for the panel, or None when no key could be had."""
    fernet = _fernet(create=True)
    if fernet is None:
        return None
    return fernet.encrypt(token.encode("ascii")).decode("ascii")


def unseal(sealed: str | None, token_hash: str) -> str | None:
    """Open a sealed token, or None when there is none, no key opens it, or it is another row's."""
    if not sealed:
        return None
    fernet = _fernet(create=False)
    if fernet is None:
        return None
    try:
        token = fernet.decrypt(sealed.encode("ascii")).decode("ascii")
    except (InvalidToken, UnicodeError, ValueError):
        return None
    return token if tokens.same(tokens.digest(token), token_hash) else None


def _fernet(create: bool) -> Fernet | None:
    """Build the cipher from the environment's key, else from the key file."""
    source = KEY_ENV
    raw = os.environ.get(KEY_ENV, "").strip()
    if not raw:
        path = key_path()
        source = str(path)
        raw = _read_key(path, create)
        if raw is None:
            return None
    try:
        return Fernet(raw.encode("ascii"))
    except (ValueError, TypeError, UnicodeError):
        logger.warning("[invitaciones] La clave de '{}' no sirve para cifrar enlaces", source)
        return None


def key_path() -> Path:
    """Where the key file is read from and, on the first seal, written to."""
    return _key_path if _key_path is not None else paths.PROJECT_ROOT / KEY_FILE


def use(path: Path | None) -> None:
    """Point the key file elsewhere — the test suite's door, like `cerebras_budget.use`."""
    global _key_path
    _key_path = path


def _read_key(path: Path, create: bool) -> str | None:
    """Read the key file, creating it the first time a link is sealed.

    `O_EXCL` settles two processes sealing the very first link at once: the loser reads the
    winner's key, waiting a moment while the file is still empty. Only sealing creates it —
    opening a sealed link with no key file has nothing to open it with.
    """
    for _ in range(_EMPTY_KEY_RETRIES):
        try:
            text = path.read_text(encoding="ascii").strip()
        except FileNotFoundError:
            if not create:
                return None
            try:
                return _create_key(path)
            except FileExistsError:
                continue
            except OSError as exc:
                logger.warning(
                    "[invitaciones] No se pudo crear la clave de los enlaces en '{}': {}", path, exc
                )
                return None
        except (OSError, UnicodeError) as exc:
            logger.warning("[invitaciones] No se pudo leer la clave de los enlaces: {}", exc)
            return None
        if text:
            return text
        time.sleep(_EMPTY_KEY_PAUSE)
    logger.warning("[invitaciones] La clave de '{}' está vacía", path)
    return None


def _create_key(path: Path) -> str:
    """Write a fresh key readable by this user alone; `FileExistsError` if another process won."""
    key = Fernet.generate_key()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(key + b"\n")
    logger.info("[invitaciones] Clave nueva para guardar los enlaces en '{}'", path)
    return key.decode("ascii")
