"""The one writer of every JSON this system persists."""

import json
import os
import re
from pathlib import Path

from loguru import logger

# The C0 controls a text artifact can never legitimately carry. Tab, newline and carriage
# return are left alone; everything else in the range is damage by the time it gets here —
# in this system it arrives from a decoder, not from a document. `U+0000` is the one that
# makes the whole artifact unstorable: Postgres refuses it in JSONB
# («unsupported Unicode escape sequence»), so ONE of them anywhere in a bank is enough to
# break `import-instance` for that workspace and to make every later mirror fail in
# silence. Measured on a reference installation: a bank with four of them had been failing
# to mirror for as long as the damage existed, and the row in the database still held a
# version with one item more than the file.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# The same set as it appears in the DUMPED text, which is where it is cheap to look for:
# `json.dumps` escapes every control character whatever `ensure_ascii` says, and tab,
# newline and carriage return get their own short escapes rather than a `\uXXXX`, so they
# cannot match here. A literal backslash-u in somebody's text matches too; that costs one
# walk that removes nothing and says nothing.
_ESCAPED = re.compile(r"\\u00(?:[01][0-9a-fA-F]|7[fF])")


def _clean(value):
    """Return `value` with every illegitimate control character gone, and how many went."""
    if isinstance(value, str):
        stripped = _CONTROL.sub("", value)
        return stripped, len(value) - len(stripped)
    if isinstance(value, dict):
        out, removed = {}, 0
        for key, item in value.items():
            new_key, a = _clean(key)
            new_item, b = _clean(item)
            out[new_key] = new_item
            removed += a + b
        return out, removed
    if isinstance(value, list):
        out, removed = [], 0
        for item in value:
            new_item, count = _clean(item)
            out.append(new_item)
            removed += count
        return out, removed
    return value, 0


def write_json(path: str | Path, data, sort_keys: bool = False) -> Path:
    """Write `data` to `path` atomically, through a `.tmp` that replaces the file.

    A build, a tagging pass or an edit cancelled halfway must not leave half a file where
    an artifact should be: the next run would read it and fail far from the cause.

    The formatting is fixed because the approval hashes stored in the database are hashes
    of these bytes — a second writer differing in `indent` or `ensure_ascii` would
    silently make every approval look outdated.

    Control characters are removed on the way out, and said out loud when they are. They
    are never the document's: they arrive when a decoder goes wrong, and one of them makes
    the artifact impossible to store at all. Stripping restores nothing — the character
    they replaced is gone either way — but it keeps one bad byte from costing a workspace
    its whole database mirror, in silence, for months.
    """
    path = Path(path)
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=sort_keys)
    if _ESCAPED.search(text):
        data, removed = _clean(data)
        if removed:
            text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=sort_keys)
            logger.warning(
                f"Removed {removed} control character(s) from '{path.name}': they are a "
                f"decoding failure upstream, and a NUL among them makes the artifact "
                f"impossible to store"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o666)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    tmp.replace(path)
    return path
