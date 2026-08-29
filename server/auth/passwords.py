"""Argon2id, and the only rule about what a password may be.

Hashing is `t=3, m=64 MiB, p=4`, aimed at ~100-250 ms per verification on the target VPS
(4 vCPU, 8 GB). The parameters live inside the hash, so raising them later re-hashes each
account on its next login through `needs_rehash` and nothing has to migrate.

The policy is length plus a rejection of the obvious, not composition rules: a
requirement to add a digit and a capital produces `Password1!`, which is on every
list there is. Length is what actually costs an attacker anything.
"""

import re
import unicodedata

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

MIN_LENGTH = 12

_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,
    parallelism=4,
)

# Not a leaked-password database — those need a network call to a third party, which this
# project does not make. It is the short list that a length rule alone still lets through.
_COMMON = {
    "contraseña",
    "contrasena",
    "password",
    "passw0rd",
    "administrador",
    "administrator",
    "qwertyuiop",
    "1234567890",
    "12345678901",
    "123456789012",
    "iloveyou",
    "welcome",
    "letmein",
    "abc123",
    "generador",
    "variantes",
}


def hash_password(password: str) -> str:
    """Return the Argon2id hash to store for this password."""
    return _hasher.hash(_normalise(password))


def verify_password(password_hash: str, password: str) -> bool:
    """Return True when the password matches the stored hash."""
    try:
        return _hasher.verify(password_hash, _normalise(password))
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """Return True when this hash was made with weaker parameters than the ones in force.

    The parameters are inside the hash, so raising them re-hashes each account on its
    next login instead of migrating anything.
    """
    try:
        return _hasher.check_needs_rehash(password_hash)
    except (InvalidHashError, ValueError):
        return False


# Built on first use so that importing this module does not pay for an Argon2 hash.
_decoy: str | None = None


def waste_time() -> None:
    """Verify a decoy hash, so a missing account costs the same as a wrong password.

    Without it the response time answers the question the deliberately identical error
    message refuses to answer, and username enumeration is open again.
    """
    global _decoy
    if _decoy is None:
        _decoy = _hasher.hash("decoy-for-timing-parity")
    try:
        _hasher.verify(_decoy, "no-such-password")
    except Exception:  # noqa: BLE001, S110 - the point is the work, not the answer
        pass


def policy_error(password: str, *, account: str = "", name: str = "") -> str | None:
    """Return why this password is not acceptable, in the user's language, or None."""
    password = _normalise(password)
    if len(password) < MIN_LENGTH:
        return f"La contraseña necesita al menos {MIN_LENGTH} caracteres."
    if len(password) > 256:
        return "La contraseña no puede pasar de 256 caracteres."

    lowered = password.lower()
    if lowered in _COMMON or _stripped(lowered) in _COMMON:
        return "Esa contraseña es demasiado común. Elige otra."
    if re.fullmatch(r"(.)\1*", password):
        return "Esa contraseña es un solo carácter repetido."
    if _is_sequence(lowered):
        return "Esa contraseña es una secuencia del teclado. Elige otra."

    # `account` is the username; splitting on "@" costs nothing and keeps this right if it
    # is ever handed an address instead.
    local = account.split("@")[0].lower() if account else ""
    for personal in (local, name.lower()):
        if len(personal) >= 4 and personal in lowered:
            return "La contraseña no puede contener tu nombre ni tu usuario."
    return None


def _normalise(password: str) -> str:
    """Fold to NFKC, so a composed accent verifies against the same combining one."""
    return unicodedata.normalize("NFKC", password)


def _stripped(text: str) -> str:
    """Return the text with its accents removed."""
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))


def _is_sequence(text: str) -> bool:
    """Return True when the whole password is a run along a keyboard row or the alphabet."""
    if len(text) < MIN_LENGTH:
        return False
    rows = ("abcdefghijklmnopqrstuvwxyz", "0123456789", "qwertyuiop", "asdfghjkl", "zxcvbnm")
    for row in rows:
        doubled = row + row
        if text in doubled or text in doubled[::-1]:
            return True
    return False
