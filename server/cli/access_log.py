import copy
from pathlib import Path

import uvicorn.config

ACCESS_LOG_MAX_BYTES = 1_000_000
ACCESS_LOG_BACKUPS = 3


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
    config["handlers"]["access"] = {
        "formatter": "access",
        "class": "logging.handlers.RotatingFileHandler",
        "filename": str(path),
        "maxBytes": ACCESS_LOG_MAX_BYTES,
        "backupCount": ACCESS_LOG_BACKUPS,
        "encoding": "utf-8",
    }
    return config
