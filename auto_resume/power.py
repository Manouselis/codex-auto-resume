"""Hold a Linux sleep inhibitor only while recovery is explicitly armed.

Screen locking, display blanking, shutdown and lid policy are not modified.
"""
import select
import shutil
import subprocess
import sys
import time


class AwakeLease:
    def __init__(self, *, enabled=True, clock=time.monotonic):
        self.enabled = enabled and sys.platform.startswith("linux")
        self.clock = clock
        self.process = None
        self.retry_at = 0
        self.status = "Not requested"

    def update(self, armed):
        if not armed or not self.enabled:
            self.close()
            return
        if self.process and self.process.poll() is None:
            return
        self.close()
        if self.clock() < self.retry_at:
            self.status = "Sleep prevention unavailable; keep laptop awake"
            return
        self.retry_at = self.clock() + 60
        binary = shutil.which("systemd-inhibit")
        if not binary:
            self.status = "Sleep prevention unavailable; keep laptop awake"
            return
        try:
            self.process = subprocess.Popen([binary, "--what=sleep", "--mode=block",
                "--who=Codex Auto-Resume", "--why=Recovery is armed; allow work while the screen is locked",
                sys.executable, "-c",
                "import sys; print('ready', flush=True); sys.stdin.buffer.read()"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            ready, _, _ = select.select([self.process.stdout], [], [], 1)
            if not ready or self.process.stdout.readline() != b"ready\n":
                raise OSError("Sleep inhibitor not acquired")
            self.status = "Screen may lock · sleep prevented while armed"
        except (OSError, ValueError):
            self.close()
            self.status = "Sleep prevention unavailable; keep laptop awake"

    def close(self):
        process, self.process = self.process, None
        if process:
            try:
                process.stdin.close()
                process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
                process.wait(timeout=1)
            finally:
                process.stdout.close()
        self.status = "Not requested"
