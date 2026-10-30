"""Hold a Linux sleep inhibitor only while recovery is explicitly armed.

Screen locking, display blanking, shutdown and lid policy are not modified.
"""
import select
import shutil
import subprocess
import sys
import time
import threading

from .process import external_options


class AwakeLease:
    def __init__(self, *, enabled=True, clock=time.monotonic):
        self.enabled = enabled
        self.windows = None
        self.clock = clock
        self.process = None
        self.retry_at = 0
        self.status = "Not requested"

    def update(self, armed):
        if not armed or not self.enabled:
            self.close()
            return
        if self.windows or (self.process and self.process.poll() is None):
            return
        self.close()
        if self.clock() < self.retry_at:
            self.status = "Sleep prevention unavailable; keep laptop awake"
            return
        self.retry_at = self.clock() + 60
        if sys.platform == "win32":
            lease = WindowsAwake()
            if lease.ready.wait(2) and lease.acquired:
                self.windows = lease
                self.status = "Screen may lock · idle sleep prevented while armed"
                return
            lease.close()
            self.status = "Sleep prevention unavailable; keep laptop awake"
            return
        if sys.platform == "darwin":
            try:
                self.process = subprocess.Popen(["/usr/bin/caffeinate", "-i"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **external_options())
                self.status = "Screen may lock · idle sleep prevented while armed"
            except OSError:
                self.status = "Sleep prevention unavailable; keep laptop awake"
            return
        binary = shutil.which("systemd-inhibit")
        if not binary:
            self.status = "Sleep prevention unavailable; keep laptop awake"
            return
        try:
            self.process = subprocess.Popen([binary, "--what=sleep", "--mode=block",
                "--who=Codex Auto-Resume", "--why=Recovery is armed; allow work while the screen is locked",
                *([sys.executable, "--inhibit-wait"] if getattr(sys, "frozen", False) else
                  [sys.executable, "-c", "import sys; print('ready', flush=True); sys.stdin.buffer.read()"] )],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, **external_options())
            ready, _, _ = select.select([self.process.stdout], [], [], 1)
            if not ready or self.process.stdout.readline() != b"ready\n":
                raise OSError("Sleep inhibitor not acquired")
            self.status = "Screen may lock · sleep prevented while armed"
        except (OSError, ValueError):
            self.close()
            self.status = "Sleep prevention unavailable; keep laptop awake"

    def close(self):
        if self.windows:
            self.windows.close()
            self.windows = None
        process, self.process = self.process, None
        if process:
            try:
                if process.stdin is not None:
                    process.stdin.close()
                else:
                    process.terminate()
                process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
                process.wait(timeout=1)
            finally:
                if process.stdout is not None:
                    process.stdout.close()
        self.status = "Not requested"


class WindowsAwake:
    """Keep the power request on its owning thread; never keep the display on."""
    def __init__(self):
        self.ready = threading.Event()
        self.stop = threading.Event()
        self.acquired = False
        self.thread = threading.Thread(target=self._hold, daemon=True)
        self.thread.start()

    def _hold(self):
        try:
            import ctypes
            api = ctypes.windll.kernel32.SetThreadExecutionState
            # ES_CONTINUOUS | ES_SYSTEM_REQUIRED; no ES_DISPLAY_REQUIRED.
            self.acquired = bool(api(0x80000001))
            self.ready.set()
            if self.acquired:
                self.stop.wait()
                api(0x80000000)
        except (AttributeError, OSError):
            self.ready.set()

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)
