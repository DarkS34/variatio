"""Uvicorn's access log: written privately, with the credentials scrubbed out."""

import copy
import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn.config

ACCESS_LOG_MAX_BYTES = 1_000_000
ACCESS_LOG_BACKUPS = 3

# An invitation and a reset link travel as `?token=…` and the token IS the credential, so
# an unscrubbed access line makes the file a list of live invitations readable by anyone
# with a shell on the box. The name is matched from a list rather than as the literal
# `token`, so the next parameter carrying a secret is covered by the filter that already
# exists — over-redacting costs a log line some detail and nothing else.
SECRET_PARAM = re.compile(
    r"([?&][^=&\s]*(?:token|secret|password|passwd|signature|sig|key|code|auth)=)[^&\s]*",
    re.IGNORECASE,
)

REDACTED = "<redacted>"


def scrub(text: str) -> str:
    """Replace the value of every secret-looking query parameter with `<redacted>`."""
    return SECRET_PARAM.sub(rf"\1{REDACTED}", text)


class RedactTokens(logging.Filter):
    """A logging filter that scrubs a record before it reaches the formatter."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Scrub the record's arguments or its message, and always keep the record."""
        if isinstance(record.args, tuple):
            record.args = tuple(
                scrub(arg) if isinstance(arg, str) else arg for arg in record.args
            )
        elif not record.args and isinstance(record.msg, str):
            record.msg = scrub(record.msg)
        return True


class PrivateRotatingFileHandler(RotatingFileHandler):
    """A rotating handler whose files belong to the account running the server alone.

    The file holds request lines and addresses. `RotatingFileHandler` takes no mode, and
    the rotated copies inherit theirs from a rename — so setting it on every open covers
    `access.log` and, through the rename, every `access.log.N` after it.
    """

    def _open(self):
        """Open the stream and lock it down to 0600."""
        stream = super()._open()
        os.fchmod(stream.fileno(), 0o600)
        return stream


def access_log_path() -> Path:
    """Return where the access log is written."""
    from variatio.core.paths import LOGS_DIR

    return LOGS_DIR / "access.log"


def access_log_config(path) -> dict:
    """Build uvicorn's logging config: the private handler plus the redacting filter."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    config = copy.deepcopy(uvicorn.config.LOGGING_CONFIG)
    config["formatters"]["access"]["fmt"] = (
        '%(asctime)s %(client_addr)s - "%(request_line)s" %(status_code)s'
    )
    config["formatters"]["access"]["use_colors"] = False
    config["filters"] = {"redact_tokens": {"()": RedactTokens}}
    config["handlers"]["access"] = {
        "formatter": "access",
        "filters": ["redact_tokens"],
        "class": "server.cli.access_log.PrivateRotatingFileHandler",
        "filename": str(path),
        "maxBytes": ACCESS_LOG_MAX_BYTES,
        "backupCount": ACCESS_LOG_BACKUPS,
        "encoding": "utf-8",
    }
    return config
