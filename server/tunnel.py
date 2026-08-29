"""The SSH port forward to the GPU box, owned by the API process.

It runs the system `ssh` binary rather than paramiko because that is what already resolves
keys, the agent, `~/.ssh/config` and `known_hosts`; `BatchMode=yes` so a password prompt
fails instead of hanging. A watchdog relaunches a dead `ssh` with backoff while the tunnel
is still wanted, and the last lines of its stderr are kept so a key problem reaches the
panel.
"""

import shutil
import subprocess
import threading
import time
from collections import deque
from urllib.parse import urlsplit

from loguru import logger

from variatio import config

BACKOFF_MIN = 5.0
BACKOFF_MAX = 60.0
STDERR_LINES = 20


class TunnelError(RuntimeError):
    """The tunnel cannot be opened, with a sentence saying what to fix."""


def local_port() -> int:
    """The port `OLLAMA_HOST` names, which is the local end of the forward."""
    host = config.OLLAMA_HOST
    if "://" not in host:
        host = f"http://{host}"
    # `urlsplit(...).port` raises `ValueError` on a non-numeric port rather than answering
    # «no hay puerto», so a mistyped OLLAMA_HOST would 500 instead of being refused.
    try:
        port = urlsplit(host).port
    except ValueError:
        port = None
    if port is None:
        raise TunnelError(f"'{config.OLLAMA_HOST}' no dice en qué puerto local escuchar")
    return port


def ssh_command() -> list[str]:
    """Build the `ssh -N -L` command line, or raise saying what the configuration lacks."""
    ssh = shutil.which("ssh")
    if ssh is None:
        raise TunnelError("No hay un cliente 'ssh' en el PATH del servidor")
    host = config.OLLAMA_SSH_HOST.strip()
    if not host:
        raise TunnelError("No hay destino: rellena OLLAMA_SSH_HOST en la configuración")
    # The destination goes last and ssh has no `--` to close its own options, so a host
    # starting with '-' would be read as one — `-oProxyCommand=…` above all. Defence in
    # depth: the `tunnel.*` settings are environment-only and unreachable from the API.
    if host.startswith("-"):
        raise TunnelError(
            f"El destino '{host}' empieza por '-': ssh lo leería como una opción suya y no "
            "como una máquina. Corrige OLLAMA_SSH_HOST en el entorno"
        )
    command = [
        ssh,
        "-N",
        "-o", "BatchMode=yes",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3",
    ]
    key = config.OLLAMA_SSH_KEY_PATH.strip()
    if key:
        command += ["-i", key]
    command += ["-L", f"{local_port()}:localhost:{config.OLLAMA_SSH_REMOTE_PORT}", host]
    return command


class SshTunnel:
    """One `ssh` subprocess, kept alive while it is wanted."""

    def __init__(self) -> None:
        """Start with no process and nothing wanted."""
        self._lock = threading.RLock()
        self._process: subprocess.Popen | None = None
        self._wanted = False
        self._since: float | None = None
        self._attempts = 0
        self._last_error: str | None = None
        self._stderr: deque[str] = deque(maxlen=STDERR_LINES)
        self._watchdog: threading.Thread | None = None
        self._stopping = threading.Event()

    def configured(self) -> bool:
        """Whether the installation names a host to forward to."""
        return bool(config.OLLAMA_SSH_HOST.strip())

    def start(self) -> dict:
        """Open the tunnel and want it open, so the watchdog reopens it if it dies."""
        with self._lock:
            command = ssh_command()
            if self._process is None or self._process.poll() is not None:
                try:
                    self._launch(command)
                except OSError as exc:
                    self._last_error = str(exc)
                    raise TunnelError(f"No se pudo lanzar 'ssh': {exc}") from exc
            self._wanted = True
            self._stopping.clear()
            if self._watchdog is None or not self._watchdog.is_alive():
                self._watchdog = threading.Thread(
                    target=self._watch, name="ssh-tunnel", daemon=True
                )
                self._watchdog.start()
        return self.status()

    def stop(self) -> dict:
        """Stop wanting the tunnel and kill it, which is also what stops the watchdog."""
        with self._lock:
            self._wanted = False
            self._stopping.set()
            self._terminate()
        logger.info("Túnel SSH apagado")
        return self.status()

    def status(self) -> dict:
        """Everything the panel draws, the last lines of `ssh`'s stderr included."""
        with self._lock:
            running = self._process is not None and self._process.poll() is None
            return {
                "configured": self.configured(),
                "host": config.OLLAMA_SSH_HOST,
                "local_port": _safe_local_port(),
                "remote_port": config.OLLAMA_SSH_REMOTE_PORT,
                "autostart": config.OLLAMA_SSH_AUTOSTART,
                "wanted": self._wanted,
                "running": running,
                "pid": self._process.pid if running and self._process else None,
                "since": self._since if running else None,
                "attempts": self._attempts,
                "last_error": self._last_error,
                "stderr": list(self._stderr),
            }

    def _launch(self, command: list[str]) -> None:
        """Spawn `ssh` and start draining its stderr."""
        self._attempts += 1
        self._stderr.clear()
        logger.info(f"Abriendo el túnel SSH hacia '{config.OLLAMA_SSH_HOST}' (intento {self._attempts})")
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self._since = time.time()
        threading.Thread(
            target=self._drain, args=(self._process,), name="ssh-tunnel-stderr", daemon=True
        ).start()

    def _drain(self, process: subprocess.Popen) -> None:
        """Keep the tail of `ssh`'s stderr, which is where a key problem is stated."""
        if process.stderr is None:
            return
        for line in process.stderr:
            text = line.rstrip()
            if text:
                self._stderr.append(text)

    def _terminate(self) -> None:
        """Ask `ssh` to stop, and kill it if it will not."""
        process = self._process
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    def _watch(self) -> None:
        """Relaunch a dead `ssh` with 5→60 s backoff for as long as the tunnel is wanted."""
        backoff = BACKOFF_MIN
        while not self._stopping.wait(1.0):
            with self._lock:
                if not self._wanted:
                    return
                process = self._process
                if process is not None and process.poll() is None:
                    backoff = BACKOFF_MIN
                    continue
                code = process.returncode if process is not None else None
                tail = self._stderr[-1] if self._stderr else ""
                self._last_error = f"ssh terminó con código {code}" + (f": {tail}" if tail else "")
                logger.warning(f"Túnel SSH caído ({self._last_error}); se reintenta en {int(backoff)} s")
            if self._stopping.wait(backoff):
                return
            with self._lock:
                if not self._wanted:
                    return
                try:
                    self._launch(ssh_command())
                except (TunnelError, OSError) as exc:
                    self._last_error = str(exc)
                    logger.warning(f"No se pudo relanzar el túnel SSH: {exc}")
            backoff = min(backoff * 2, BACKOFF_MAX)


def _safe_local_port() -> int | None:
    """The local port for the status payload, or None when it cannot be read."""
    try:
        return local_port()
    except (TunnelError, ValueError):
        return None
