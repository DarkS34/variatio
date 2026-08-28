"""The installation's door: open, or closed while somebody works on it.

Two rules, and both are load-bearing.

The administrator is NOT locked out. The check lives in `auth.deps.access_for`, the same
place — and the only one — where the administrator bypass already lives, so closing the
installation closes it for everyone except whoever is applying the change. A door that
also shuts on them has nothing left to reopen it from.

The state is readable with no session. The entrance screen has to be able to say «this is
under maintenance» before it knows who is asking; behind a login, the notice would only
reach the people who no longer need it.

It is installation state, not a workspace's and not a registry setting, so it is a JSON
file at the root beside `.cerebras_budget.json` and gitignored for the same reason. A
file rather than a process variable because builds run in `server/jobs/build_worker.py`,
another process, and because restarting the API mid-change must not reopen the door.
"""

import json
from datetime import datetime, timezone

from loguru import logger

from variatio.core import json_io, paths

STATE_PATH = paths.PROJECT_ROOT / ".maintenance.json"

# An empty notice is a state, not a missing value: it means nobody wrote one, and the
# sentence shown in its place is the CLIENT's — the interface language belongs to the
# account, so a default written here could only ever be right for half the readers.

# What fits on a notice read at a glance. A longer message is not read, it is skipped.
MAX_MESSAGE_CHARS = 400

CLOSED = "La instalación está en mantenimiento. Vuelve a intentarlo en unos minutos."

_cache: dict | None = None
_stamp: int | None = None


def _blank() -> dict:
    return {"active": False, "message": "", "since": None, "by": None}


def _read() -> dict:
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _blank()
    if not isinstance(raw, dict):
        return _blank()
    return {
        "active": bool(raw.get("active")),
        "message": str(raw.get("message") or "")[:MAX_MESSAGE_CHARS],
        "since": raw.get("since") or None,
        "by": raw.get("by") or None,
    }


# Every request that resolves a membership asks this, so it cannot cost a read of the
# disk each time: the file's timestamp decides whether to re-read it, which is what keeps
# the answer true across processes without making it expensive.
def state() -> dict:
    global _cache, _stamp
    try:
        stamp = STATE_PATH.stat().st_mtime_ns
    except OSError:
        _cache, _stamp = _blank(), None
        return dict(_cache)
    if _cache is None or stamp != _stamp:
        _cache, _stamp = _read(), stamp
    return dict(_cache)


def active() -> bool:
    return state()["active"]


def set_state(is_active: bool, message: str | None, by: str | None) -> dict:
    current = state()
    text = (message or "").strip()
    # It closes once: rewording the notice while it is already closed does not restart the
    # clock, because what the screen reports is how long it has been closed.
    keeps_clock = is_active and current["active"] and current["since"]
    data = {
        "active": bool(is_active),
        "message": text[:MAX_MESSAGE_CHARS],
        "since": (
            current["since"]
            if keeps_clock
            else (datetime.now(timezone.utc).isoformat(timespec="seconds") if is_active else None)
        ),
        "by": by if is_active else None,
    }
    json_io.write_json(STATE_PATH, data)
    global _cache, _stamp
    _cache, _stamp = data, STATE_PATH.stat().st_mtime_ns
    logger.info(
        f"[mantenimiento] Instalación {'cerrada' if is_active else 'abierta'}"
        + (f" por «{by}»" if is_active and by else "")
    )
    return dict(data)
