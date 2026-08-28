import copy
import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn.config

ACCESS_LOG_MAX_BYTES = 1_000_000
ACCESS_LOG_BACKUPS = 3

# An invitation and a reset link travel as `?token=…` and the token IS the credential:
# whoever reads it holds the account. The access line records the query string, so the file
# was a list of live invitations, readable by anyone with a shell on the box. The name is
# matched from a list rather than as the literal `token`, so the next parameter that carries
# a secret is covered by the filter that already exists instead of by remembering to widen
# it — over-redacting a query parameter costs a log line some detail and nothing else.
SECRET_PARAM = re.compile(
    r"([?&][^=&\s]*(?:token|secret|password|passwd|signature|sig|key|code|auth)=)[^&\s]*",
    re.IGNORECASE,
)

REDACTED = "<redacted>"


def scrub(text: str) -> str:
    return SECRET_PARAM.sub(rf"\1{REDACTED}", text)


class RedactTokens(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                scrub(arg) if isinstance(arg, str) else arg for arg in record.args
            )
        elif not record.args and isinstance(record.msg, str):
            record.msg = scrub(record.msg)
        return True


# The file holds request lines and addresses, so it is nobody's but the account running the
# server. `RotatingFileHandler` takes no mode, and the rotated copies inherit theirs from a
# rename — so setting it on every open covers `access.log` and, through the rename, every
# `access.log.N` after it.
class PrivateRotatingFileHandler(RotatingFileHandler):
    def _open(self):
        stream = super()._open()
        os.fchmod(stream.fileno(), 0o600)
        return stream


def access_log_path() -> Path:
    from variatio.core.paths import PROJECT_ROOT

    return PROJECT_ROOT / "logs" / "access.log"


def access_log_config(path) -> dict:
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
