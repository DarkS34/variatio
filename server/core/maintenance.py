"""The installation's door: open, or closed while somebody works on it.

The administrator is NOT locked out — the check lives in `auth.deps.access_for`, beside the
administrator bypass, so a closed door still has somebody able to reopen it. The state is
readable with no session, because the entrance screen has to say "this is under
mantenimiento" before it knows who is asking.

Installation state rather than a workspace's or a registry setting, so it is a gitignored
JSON file at the root: builds run in another process, and restarting the API mid-change
must not reopen the door.
"""

import json
from datetime import datetime, timezone

from loguru import logger

from variatio.core import json_io, paths

STATE_PATH = paths.PROJECT_ROOT / ".maintenance.json"

# An empty notice is a state and not a missing value: the sentence shown in its place is
# the client's, because the interface language belongs to the account.
# 400: what fits on a notice read at a glance.
MAX_MESSAGE_CHARS = 400

CLOSED = "La instalación está en mantenimiento. Vuelve a intentarlo en unos minutos."

_cache: dict | None = None
_stamp: int | None = None


def active() -> bool:
    """Report whether the installation is closed for maintenance."""
    return state()["active"]


def set_state(is_active: bool, message: str | None, by: str | None) -> dict:
    """Open or close the door, and return the state as it now stands."""
    current = state()
    text = (message or "").strip()
    # It closes once: rewording the notice does not restart the clock the screen reports.
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


def state() -> dict:
    """Return the door's state, re-reading the file only when its timestamp moved.

    Every request that resolves a membership asks this, so it cannot cost a disk read each
    time; keying the cache on the mtime keeps the answer true across processes.
    """
    global _cache, _stamp
    try:
        stamp = STATE_PATH.stat().st_mtime_ns
    except OSError:
        _cache, _stamp = _blank(), None
        return dict(_cache)
    if _cache is None or stamp != _stamp:
        _cache, _stamp = _read(), stamp
    return dict(_cache)


def _read() -> dict:
    """Read the state file, treating anything unreadable or malformed as an open door."""
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


def _blank() -> dict:
    """Return the open-door state, which is also what an unreadable file means."""
    return {"active": False, "message": "", "since": None, "by": None}
