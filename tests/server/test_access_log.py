import logging
import logging.config
from logging.handlers import RotatingFileHandler

import pytest
import uvicorn.config

from server.cli.access_log import access_log_config


@pytest.fixture(autouse=True)
def restore_uvicorn_logging():
    yield
    logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)


def test_access_lines_go_to_the_file_and_not_to_the_console(tmp_path, capsys):
    path = tmp_path / "access.log"
    logging.config.dictConfig(access_log_config(path))

    logging.getLogger("uvicorn.access").info(
        '%s - "%s %s HTTP/%s" %d', "127.0.0.1:5000", "GET", "/api/health", "1.1", 200
    )

    for handler in logging.getLogger("uvicorn.access").handlers:
        handler.flush()

    written = path.read_text(encoding="utf-8")
    assert "GET /api/health HTTP/1.1" in written
    captured = capsys.readouterr()
    assert "/api/health" not in captured.out
    assert "/api/health" not in captured.err


def test_the_access_file_rotates():
    handlers = access_log_config("access.log")["handlers"]
    assert handlers["access"]["class"] == "logging.handlers.RotatingFileHandler"
    assert handlers["access"]["backupCount"] >= 1
    assert handlers["access"]["maxBytes"] > 0


def test_uvicorn_errors_stay_on_the_console(tmp_path):
    logging.config.dictConfig(access_log_config(tmp_path / "access.log"))

    resolved = logging.getLogger("uvicorn").handlers
    assert resolved
    assert all(not isinstance(h, RotatingFileHandler) for h in resolved)


def test_the_directory_is_created(tmp_path):
    path = tmp_path / "logs" / "access.log"
    logging.config.dictConfig(access_log_config(path))
    assert path.parent.is_dir()


def test_the_default_uvicorn_config_is_not_mutated():
    before = uvicorn.config.LOGGING_CONFIG["handlers"]["access"]["class"]
    access_log_config("access.log")
    assert uvicorn.config.LOGGING_CONFIG["handlers"]["access"]["class"] == before
