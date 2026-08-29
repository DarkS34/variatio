"""An advisory lock on a file, so only one `serve` runs at a time."""

import atexit
import os
from pathlib import Path


class LockHeld(RuntimeError):
    """Raised when the lock file is already held by another process."""

    def __init__(self, path: Path):
        """Record which lock file was held."""
        super().__init__(str(path))
        self.path = path


def _try_lock(handle) -> bool:
    """Take the lock without blocking; False when somebody else holds it."""
    if os.name == "nt":
        import msvcrt

        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(handle) -> None:
    """Release the lock and close the handle, tolerating a failure to unlock."""
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    handle.close()


def acquire(path: Path):
    """Open the lock file and take it, or raise `LockHeld`."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    handle.seek(0)
    if not _try_lock(handle):
        handle.close()
        raise LockHeld(path)
    return handle


def release(handle) -> None:
    """Release a handle from `acquire`, tolerating None and an already-closed one."""
    if handle is None or handle.closed:
        return
    _unlock(handle)


def hold(path: Path):
    """Take the lock and keep it for the life of the process."""
    handle = acquire(path)
    atexit.register(release, handle)
    return handle
