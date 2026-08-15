"""Opaque tokens: generated once, shown once, stored only as a digest.

Sessions, invites and password resets are the same shape — a random string the holder
keeps and a SHA-256 the database keeps — so they share one implementation. SHA-256 and
not Argon2 on purpose: these are 256 bits of entropy from `secrets`, not a password, so
there is nothing to slow an attacker down about, and lookup is a single indexed read.
"""

import hashlib
import hmac
import secrets

TOKEN_BYTES = 32


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def same(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)
