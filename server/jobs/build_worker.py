"""Runs one builder out of process and reports back as newline-delimited events.

Out of process for three reasons, all of them load-bearing: a build takes hours and
must be genuinely cancellable (you cannot kill a Python thread), docling drags ~540 MB
of torch that the API should never import, and a crash on one bad PDF must not take
the server down with it.

Anything printed that is not prefixed with MARKER is somebody else's output (docling,
tqdm) and is forwarded as a log line, so the protocol survives noisy dependencies.
"""

import argparse
import json
import signal
import sys

MARKER = "@@EVT@@"


def send(kind: str, **payload) -> None:
    line = json.dumps({"kind": kind, **payload}, ensure_ascii=False, default=str)
    sys.stdout.write(f"{MARKER}{line}\n")
    sys.stdout.flush()


class StdoutEmitter:
    def __init__(self) -> None:
        self._cancelled = False

    def emit(self, kind: str, payload: dict) -> None:
        send(kind, **payload)

    def should_cancel(self) -> bool:
        return self._cancelled

    def request_cancel(self, *_args) -> None:
        self._cancelled = True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build-worker")
    parser.add_argument("artifact", choices=["content_profile", "knowledge_graph", "exemplars_bank"])
    args = parser.parse_args(argv)

    from loguru import logger

    import variant_generator
    from variant_generator import progress, stages

    emitter = StdoutEmitter()
    signal.signal(signal.SIGTERM, emitter.request_cancel)
    signal.signal(signal.SIGINT, emitter.request_cancel)

    # The package installs a colourised stdout sink on import; replace it so every
    # log line reaches the parent as structured data instead of ANSI noise.
    logger.remove()
    logger.add(
        lambda message: send(
            "log",
            level=message.record["level"].name,
            module=message.record["module"],
            message=message.record["message"],
        ),
        level="DEBUG",
        format="{message}",
    )

    progress.set_emitter(emitter)
    try:
        variant_generator.bootstrap()
        result = stages.build_artifact(args.artifact)
    except progress.Cancelled:
        send("worker.cancelled")
        return 2
    except Exception as exc:  # noqa: BLE001 - reported upstream as a job failure
        logger.exception("Build failed")
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
