import logging
import logging.config
import stat
from logging.handlers import RotatingFileHandler

import pytest
import uvicorn.config

from server.cli.access_log import PrivateRotatingFileHandler, access_log_config, scrub


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
    assert handlers["access"]["class"] == "server.cli.access_log.PrivateRotatingFileHandler"
    assert issubclass(PrivateRotatingFileHandler, RotatingFileHandler)
    assert handlers["access"]["backupCount"] >= 1
    assert handlers["access"]["maxBytes"] > 0


# The token in `?token=` IS the credential an invitation or a reset link carries, so the
# access line was a list of live invitations for anyone with a shell on the box.
def test_a_token_in_the_query_string_is_not_written_down(tmp_path):
    path = tmp_path / "access.log"
    logging.config.dictConfig(access_log_config(path))

    logging.getLogger("uvicorn.access").info(
        '%s - "%s %s HTTP/%s" %d',
        "127.0.0.1:5000",
        "GET",
        "/invite?token=Ab3-secreto_largo&next=/",
        "1.1",
        200,
    )
    for handler in logging.getLogger("uvicorn.access").handlers:
        handler.flush()

    written = path.read_text(encoding="utf-8")
    assert "Ab3-secreto_largo" not in written
    assert "token=<redacted>" in written
    # Everything else about the request survives, or the log stops being one.
    assert "/invite?" in written and "next=/" in written


def test_the_next_parameter_that_carries_a_secret_is_covered_too():
    assert scrub("/x?secret=abc") == "/x?secret=<redacted>"
    assert scrub("/x?api_key=abc&b=1") == "/x?api_key=<redacted>&b=1"
    assert scrub("/x?reset_token=abc") == "/x?reset_token=<redacted>"
    assert scrub("/x?password=abc") == "/x?password=<redacted>"
    # And what carries none is left exactly as it was.
    assert scrub("/api/jobs?workspace=aula&since=12") == "/api/jobs?workspace=aula&since=12"


def test_a_line_logged_without_arguments_is_scrubbed_as_well(tmp_path):
    path = tmp_path / "access.log"
    logging.config.dictConfig(access_log_config(path))

    logging.getLogger("uvicorn.access").info("GET /reset?token=Ab3-secreto_largo")
    for handler in logging.getLogger("uvicorn.access").handlers:
        handler.flush()

    assert "Ab3-secreto_largo" not in path.read_text(encoding="utf-8")


def test_the_file_is_only_readable_by_whoever_runs_the_server(tmp_path):
    path = tmp_path / "access.log"
    logging.config.dictConfig(access_log_config(path))
    logging.getLogger("uvicorn.access").info(
        '%s - "%s %s HTTP/%s" %d', "127.0.0.1:5000", "GET", "/api/health", "1.1", 200
    )
    for handler in logging.getLogger("uvicorn.access").handlers:
        handler.flush()

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


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
