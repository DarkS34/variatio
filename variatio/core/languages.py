"""The languages this installation speaks, and how a value is read as one of them."""

LANGUAGES: tuple[str, ...] = ("es", "en")

DEFAULT: str = "es"

NAMES: dict[str, str] = {"es": "Español", "en": "English"}


def resolve(value: str | None, fallback: str = DEFAULT) -> str:
    """Return `value` as a language we speak, falling back when it is not one."""
    return normalise(value) or fallback


def error(value: str | None) -> str | None:
    """Return why `value` is not a language we speak, or None when it is one."""
    if normalise(value) is not None:
        return None
    known = ", ".join(f"«{code}»" for code in LANGUAGES)
    return f"Idioma desconocido: «{value}». Usa uno de {known}."


def normalise(value: str | None) -> str | None:
    """Return the base tag of `value` when it names a language we speak, else None."""
    if value is None:
        return None
    tag = str(value).strip().lower().replace("_", "-")
    if not tag:
        return None
    base = tag.split("-", 1)[0]
    return base if base in LANGUAGES else None
