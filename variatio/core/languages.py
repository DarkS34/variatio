LANGUAGES: tuple[str, ...] = ("es", "en")

DEFAULT: str = "es"

NAMES: dict[str, str] = {"es": "Español", "en": "English"}


def normalise(value: str | None) -> str | None:
    if value is None:
        return None
    tag = str(value).strip().lower().replace("_", "-")
    if not tag:
        return None
    base = tag.split("-", 1)[0]
    return base if base in LANGUAGES else None


def resolve(value: str | None, fallback: str = DEFAULT) -> str:
    return normalise(value) or fallback


def error(value: str | None) -> str | None:
    if normalise(value) is not None:
        return None
    known = ", ".join(f"«{code}»" for code in LANGUAGES)
    return f"Idioma desconocido: «{value}». Usa uno de {known}."
