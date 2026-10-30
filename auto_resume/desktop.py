"""Start a per-user background controller without tying it to a Tk window."""
import os
import shutil
import subprocess
import sys
import re
from pathlib import Path

from .domain import UnsafeError


def open_conversation(thread_id):
    """Open the selected chat via the desktop's documented URL handler."""
    if not isinstance(thread_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", thread_id):
        raise ValueError("Invalid conversation ID")
    url = "codex://threads/" + thread_id
    try:
        if os.name == "nt":
            os.startfile(url)
            return
        if sys.platform == "darwin":
            command = ["open", url]
        else:
            launcher = shutil.which("chatgpt")
            if launcher:
                command = [launcher, url]
            elif shutil.which("xdg-open"):
                command = ["xdg-open", url]
            else:
                raise OSError("No desktop URL handler")
        subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as exc:
        raise UnsafeError("Could not open Codex. Install the desktop app and its codex:// URL handler.") from exc


def ensure_background(state_path):
    """Return whether systemd owns the controller. Non-Linux uses the window."""
    if not sys.platform.startswith("linux") or not shutil.which("systemctl"):
        return False
    try:
        if subprocess.run(["systemctl", "--user", "is-active", "--quiet", "codex-auto-resume.service"],
                          capture_output=True, timeout=5).returncode == 0:
            return True
        executable = Path(sys.argv[0]).resolve()
        if executable.suffix != ".pyz" or not executable.is_file():
            return False
        # Installed units survive normal stops; the fallback also supports
        # an older installation whose only unit was transient.
        started = subprocess.run(["systemctl", "--user", "start", "codex-auto-resume.service"],
                                 capture_output=True, timeout=10)
        if started.returncode == 0:
            return True
        if not shutil.which("systemd-run"):
            return False
        result = subprocess.run(["systemd-run", "--user", "--unit=codex-auto-resume",
            "--description=Codex Auto-Resume background recovery", "--property=Restart=on-failure",
            "--property=RestartSec=5", "--property=UMask=0077", sys.executable,
            str(executable), "--state", os.fspath(state_path), "run"], capture_output=True, timeout=10)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
