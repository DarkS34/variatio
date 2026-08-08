"""Parent side of the out-of-process build: spawn, pump events, translate exit codes."""

import json
import subprocess
import sys

from variant_generator import config, progress

from .protocol import MARKER
from .runner import JobControl

MAX_LOG_CHARS = 500


def run_build(artifact: str, control: JobControl) -> dict:
    command = [sys.executable, "-u", "-m", "server.jobs.build_worker", artifact]
    process = subprocess.Popen(
        command,
        cwd=str(config.PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
    )
    control.attach_process(process)

    result: dict = {"artifact": artifact}
    failure: str | None = None

    assert process.stdout is not None
    for raw in process.stdout:
        line = raw.rstrip("\n")
        if line.startswith(MARKER):
            failure = _dispatch(line[len(MARKER) :], control, result) or failure
        elif line.strip():
            control.emit("log", {"level": "INFO", "module": "build", "message": _tidy(line)})

    code = process.wait()

    if control.should_cancel() or code == 2:
        raise progress.Cancelled("build cancelled")
    if code != 0:
        raise RuntimeError(failure or f"El proceso de construcción terminó con código {code}")
    return result


def _dispatch(payload: str, control: JobControl, result: dict) -> str | None:
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        return None

    kind = event.pop("kind", None)
    if kind is None:
        return None
    if kind == "worker.result":
        result.update(event)
        return None
    if kind == "worker.failed":
        return event.get("error")
    if kind == "worker.cancelled":
        return None

    control.emit(kind, event)
    return None


def _tidy(line: str) -> str:
    # Progress bars redraw with \r; only the last frame carries information.
    return line.rsplit("\r", 1)[-1][:MAX_LOG_CHARS]
