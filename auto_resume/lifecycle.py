"""One scheduler per state file, using OS locks released automatically after crashes."""
import os
from pathlib import Path

from .domain import UnsafeError


class ControllerLock:
    def __init__(self, state_path):
        self.path = Path(str(state_path) + ".controller.lock")
        self.handle = None

    def acquire(self):
        if self.path.is_symlink():
            raise UnsafeError("Controller lock must not be a symlink")
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        handle = os.fdopen(fd, "r+b", buffering=0)
        try:
            if os.name == "nt":
                import msvcrt
                if self.path.stat().st_size == 0:
                    handle.write(b"0")
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise UnsafeError("Another controller is running. Stop it before opening this controller.") from exc
        self.handle = handle

    def release(self):
        if self.handle:
            self.handle.close()
            self.handle = None
