import json
from pathlib import Path


# One writer for every JSON this system persists, and it is not a convenience wrapper.
#
# Atomicity: a build, a tagging pass or an edit that is cancelled halfway must not leave
# half a file where an artifact should be — the next run would read it and fail somewhere
# far away from the cause.
#
# Formatting: the approval hashes stored in the database are hashes of these bytes, so a
# second writer that differed in `indent` or `ensure_ascii` would silently make every
# approval look outdated. There used to be six copies of these five lines, which is exactly
# how that stops being true.
def write_json(path: str | Path, data, sort_keys: bool = False) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=sort_keys)
    tmp.replace(path)
    return path