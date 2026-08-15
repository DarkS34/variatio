"""Argon2id, and the only rule about what a password may be.

The policy is length plus a rejection of the obvious, not composition rules: a
requirement to add a digit and a capital produces `Password1!`, which is on every
list there is. Length is what actually costs an attacker anything.
"""

import re
import unicodedata

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

MIN_LENGTH = 12

# Aimed at ~100-250 ms per verification on the target VPS (4 vCPU, 8 GB). The parameters
# are stored inside the hash, so raising them later re-hashes on next login and nothing
# has to migrate — `needs_rehash` below is what makes that automatic.
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
    return _hasher.hash(_normalise(password))


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, _normalise(password))
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except (InvalidHashError, ValueError):
        return False


# The decoy for "that address does not exist": a login against a non-existent account has
# to cost the same as one against a real account, or the response time answers the
# question the deliberately identical error message refuses to answer. Built on first use
# so that importing this module does not pay for an Argon2 hash.
_decoy: str | None = None


def waste_time() -> None:
    global _decoy
    if _decoy is None:
        _decoy = _hasher.hash("decoy-for-timing-parity")
    try:
        _hasher.verify(_decoy, "no-such-password")
    except Exception:  # noqa: BLE001, S110 - the point is the work, not the answer
        pass


def policy_error(password: str, *, email: str = "", name: str = "") -> str | None:
    """The reason this password is not acceptable, in the user's language, or None."""
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

    local = email.split("@")[0].lower() if email else ""
    for personal in (local, name.lower()):
        if len(personal) >= 4 and personal in lowered:
            return "La contraseña no puede contener tu nombre ni tu correo."
    return None


def _normalise(password: str) -> str:
    # NFKC so that a password typed with a composed accent verifies against the same one
    # typed with a combining accent: the two are the same password to the person typing.
    return unicodedata.normalize("NFKC", password)


def _stripped(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))


def _is_sequence(text: str) -> bool:
    if len(text) < MIN_LENGTH:
        return False
    rows = ("abcdefghijklmnopqrstuvwxyz", "0123456789", "qwertyuiop", "asdfghjkl", "zxcvbnm")
    for row in rows:
        doubled = row + row
        if text in doubled or text in doubled[::-1]:
            return True
    return False
