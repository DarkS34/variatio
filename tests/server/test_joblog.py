"""The job log on disk: one file per workspace, opened by the jobs that write into it.

The run drawer's «Registro» tab was removed on 2026-08-31 (explicit user request) and this
is where those lines go instead. What the module has to get right is the sharing: a lane
with room runs several jobs at once, so a second job of the same workspace must join the
sink that is open rather than open a second one over the same file.
"""

import threading

from loguru import logger

from server.jobs import joblog
from variatio.core import paths


def _read(path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_the_file_is_the_workspace_s_own_directory_inside_the_logs_dir():
    assert joblog.path_for("aula") == paths.LOGS_DIR / "aula" / joblog.FILE_NAME
    assert (paths.LOGS_DIR / "aula").is_dir()


def test_a_line_of_the_job_s_thread_reaches_the_file():
    joblog.attach("uno")
    try:
        logger.info("una linea de uno")
    finally:
        joblog.detach("uno")

    assert "una linea de uno" in _read(joblog.path_for("uno"))


def test_a_thread_that_never_attached_writes_nowhere():
    joblog.attach("dos")
    written: list[str] = []
    try:
        thread = threading.Thread(target=lambda: logger.info("desde fuera"))
        thread.start()
        thread.join()
        written.append(_read(joblog.path_for("dos")))
    finally:
        joblog.detach("dos")

    assert "desde fuera" not in written[0]


def test_two_jobs_of_one_workspace_share_the_sink_and_the_last_one_closes_it():
    """The second job must not open a second sink over the same file, and the first one
    leaving must not close it under the second."""
    joblog.attach("tres")
    sink = joblog._open["tres"].sink_id

    second = threading.Thread(target=lambda: joblog.attach("tres"))
    second.start()
    second.join()

    assert joblog._open["tres"].sink_id == sink
    assert len(joblog._open["tres"].threads) == 2

    joblog.detach("tres")
    assert "tres" in joblog._open

    closing = threading.Thread(target=lambda: joblog.detach("tres"))
    closing.start()
    closing.join()
    assert "tres" not in joblog._open


def test_a_job_with_no_workspace_is_a_no_op():
    joblog.attach("")
    joblog.detach("")
    assert "" not in joblog._open
