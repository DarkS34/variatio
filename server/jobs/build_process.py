"""Parent side of the out-of-process build: spawn, pump events, translate exit codes."""

import json
import subprocess
import sys

from loguru import logger

from variatio.core import paths, progress

from .protocol import MARKER
from .runner import JobControl

MAX_LOG_CHARS = 500

# The child merges its stderr into stdout, so docling, pypdfium2 and tqdm write down this
# same pipe — and what they print includes text that came out of a document somebody
# uploaded. Without an allowlist any line starting with MARKER is an arbitrary event on the
# bus, which is broadcast to every member of the workspace: printing
# `@@EVT@@{"kind": "item.saved", ...}` from inside a PDF was enough to invent events the
# build never emitted, or a `worker.result` to falsify what the job returns.
#
# The list is what the worker ACTUALLY emits: the four step events and the percentage from
# `core/progress.py`, the `log` of its loguru sink, the builders' `artifact.progress`, and
# the `retrieval` / `item.tagged` / `repair` that the bank's tagging hook reaches, plus the
# Cerebras budget's wait. Generation's own events — `token`, `prompt`, `item.rejected`,
# `guardrail`, `admissibility` — are emitted by no build, so they stay out.
EVENT_KINDS = frozenset(
    {
        "log",
        "step.started",
        "step.progress",
        "step.total",
        "step.finished",
        "build.progress",
        "artifact.progress",
        "item.tagged",
        "retrieval",
        "repair",
        "cerebras.waiting",
    }
)

# The protocol between the worker and its parent, which never travels to the bus.
TERMINAL_KINDS = frozenset({"worker.result", "worker.failed", "worker.cancelled"})
RESULT_FIELDS = frozenset({"artifact", "size"})


def run_build(artifact: str, control: JobControl) -> dict:
    command = [sys.executable, "-u", "-m", "server.jobs.build_worker", artifact]
    # The child resolves its own paths from the slug, exactly as the CLI's `--workspace`
    # does, and the slug is not optional on either side: there is no instance a build
    # could mean without being told, so a job without a workspace is a bug here and not a
    # build of something else.
    if not control.job.workspace:
        raise ValueError("El trabajo no dice en qué workspace construir.")
    command += ["--workspace", control.job.workspace]
    process = subprocess.Popen(
        command,
        cwd=str(paths.PROJECT_ROOT),
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
    settled: set[str] = set()

    assert process.stdout is not None
    for raw in process.stdout:
        line = raw.rstrip("\n")
        if line.startswith(MARKER):
            failure = _dispatch(line[len(MARKER) :], control, result, settled) or failure
        elif line.strip():
            control.emit("log", {"level": "INFO", "module": "build", "message": _tidy(line)})

    code = process.wait()

    if control.should_cancel() or code == 2:
        raise progress.Cancelled("build cancelled")
    if code != 0:
        raise RuntimeError(failure or f"El proceso de construcción terminó con código {code}")
    return result


def _dispatch(
    payload: str, control: JobControl, result: dict, settled: set[str]
) -> str | None:
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(event, dict):
        return None

    kind = event.pop("kind", None)
    if not isinstance(kind, str):
        return None

    # One outcome per build: the worker sends exactly one as it ends, so a second is either
    # noise or a forgery, and believing it would let the last line of the pipe decide
    # whether the job went well. The fields are the worker's own two, for the same reason —
    # a forged result that arrives first must not be able to add keys of its choosing.
    if kind in TERMINAL_KINDS:
        if settled:
            logger.debug(f"[build] Se ignora un segundo desenlace «{kind}»")
            return None
        settled.add(kind)
        if kind == "worker.result":
            result.update({k: v for k, v in event.items() if k in RESULT_FIELDS})
            return None
        if kind == "worker.failed":
            error = event.get("error")
            return str(error)[:MAX_LOG_CHARS] if error else None
        return None

    if kind not in EVENT_KINDS:
        logger.debug(f"[build] Se ignora un evento no declarado «{kind}»")
        return None

    control.emit(kind, event)
    return None


def _tidy(line: str) -> str:
    # Progress bars redraw with \r; only the last frame carries information.
    return line.rsplit("\r", 1)[-1][:MAX_LOG_CHARS]
