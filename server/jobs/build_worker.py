"""Run one builder out of process and report back as newline-delimited events.

Out of process for three reasons, all load-bearing: a build takes hours and must be
genuinely cancellable (a Python thread cannot be killed), docling drags ~540 MB of torch the
API should never import, and a crash on one bad PDF must not take the server down.

The consequence for the builders is that they call `inference.generate()` and never
`generate_stream()` — every token would become a JSON line on this pipe for hours — and that
cancellation is per chunk, through `progress.checkpoint()`.

Anything printed without the MARKER prefix is somebody else's output (docling, tqdm) and is
forwarded as a log line, so the protocol survives noisy dependencies.

Nothing else in the package may import this module: it runs as `__main__`, and an earlier
import would make runpy warn on every build. That is why MARKER lives in `protocol`.
"""

import argparse
import json
import signal
import sys

from .protocol import MARKER


def send(kind: str, **payload) -> None:
    """Write one marked event on stdout and flush, so the parent sees it as it happens."""
    line = json.dumps({"kind": kind, **payload}, ensure_ascii=False, default=str)
    sys.stdout.write(f"{MARKER}{line}\n")
    sys.stdout.flush()


class StdoutEmitter:
    """The `progress.Emitter` of the child: every event goes down the pipe as a marked line."""

    def __init__(self) -> None:
        """Start uncancelled."""
        self._cancelled = False

    def emit(self, kind: str, payload: dict) -> None:
        """Send one progress event to the parent."""
        send(kind, **payload)

    def should_cancel(self) -> bool:
        """Whether a signal has asked this build to stop."""
        return self._cancelled

    def request_cancel(self, *_args) -> None:
        """Raise the cancel flag. Installed as the SIGTERM and SIGINT handler."""
        self._cancelled = True


def main(argv: list[str] | None = None) -> int:
    """Build one artifact of one workspace. 0 built, 1 failed, 2 cancelled."""
    parser = argparse.ArgumentParser(prog="build-worker")
    parser.add_argument("artifact", choices=["exemplars_profile", "knowledge_graph", "exemplars_bank"])
    parser.add_argument("--workspace", required=True, help="Workspace slug")
    args = parser.parse_args(argv)

    from loguru import logger

    import variatio
    from variatio import config, stages
    from variatio.core import paths, progress

    emitter = StdoutEmitter()
    signal.signal(signal.SIGTERM, emitter.request_cancel)
    signal.signal(signal.SIGINT, emitter.request_cancel)

    # The package installs a colourised stdout sink on import; replace it so every log line
    # reaches the parent as structured data instead of ANSI noise.
    logger.remove()
    logger.add(
        lambda message: send(
            "log",
            level=message.record["level"].name,
            module=message.record["module"],
            message=message.record["message"],
        ),
        level=config.LOG_LEVEL,
        format="{message}",
    )

    progress.set_emitter(emitter)
    try:
        variatio.bootstrap()
        result = stages.build_artifact(args.artifact, paths.workspace(args.workspace))
    except progress.Cancelled:
        send("worker.cancelled")
        return 2
    except Exception as exc:  # noqa: BLE001 - reported upstream as a job failure
        logger.exception("La construcción falló")
        send("worker.failed", error=f"{type(exc).__name__}: {exc}")
        return 1

    if emitter.should_cancel():
        send("worker.cancelled")
        return 2

    size = len(result) if isinstance(result, dict) else None
    send("worker.result", artifact=args.artifact, size=size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
