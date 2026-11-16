"""Start a per-user background controller without tying it to a Tk window."""
import os
import shutil
import subprocess
import sys
import re
from pathlib import Path

from .domain import UnsafeError
from .process import external_options


def open_conversation(thread_id):
    """Open the selected chat via the desktop's documented URL handler."""
    if not isinstance(thread_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", thread_id):
        raise ValueError("Invalid conversation ID")
    _open_codex_url("codex://threads/" + thread_id)


def wake_queued_conversation(thread_id):
    """Ask the desktop to load a queued chat without changing the visible chat."""
    if not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", thread_id):
        raise ValueError("A Codex conversation UUID is required")
    _open_codex_url("codex://threads/wake/" + thread_id)


def _open_codex_url(url):
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
                         stderr=subprocess.DEVNULL, start_new_session=True, **external_options())
    except OSError as exc:
        raise UnsafeError("Could not open Codex. Install the desktop app and its codex:// URL handler.") from exc


def ensure_background(state_path):
    """Return whether systemd owns the controller. Non-Linux uses the window."""
    if not sys.platform.startswith("linux") or not shutil.which("systemctl"):
        return False
    legacy_unit = "codex-auto-resume.service"
    frozen = getattr(sys, "frozen", False)
    units = ("codex-auto-resume-native.service", legacy_unit) if frozen else (legacy_unit,)
    try:
        if subprocess.run(["systemctl", "--user", "is-active", "--quiet", *units],
                          capture_output=True, timeout=5, **external_options()).returncode == 0:
            return True
        executable = Path(sys.argv[0]).resolve()
        if (executable.suffix != ".pyz" and not frozen) or not executable.is_file():
            return False
        # A source install can leave a user unit pointing to an older zipapp.
        # Native installs start their own executable once any old controller exits.
        if not frozen and subprocess.run(["systemctl", "--user", "start", legacy_unit],
                                         capture_output=True, timeout=10, **external_options()).returncode == 0:
            return True
        if not shutil.which("systemd-run"):
            return False
        command = [sys.executable] if frozen else [sys.executable, str(executable)]
        result = subprocess.run(["systemd-run", "--user", "--unit=" + units[0],
            "--description=Codex Auto-Resume background recovery", "--property=Restart=on-failure",
            "--property=RestartSec=5", "--property=UMask=0077", *command, "--state", os.fspath(state_path), "run"], capture_output=True, timeout=10, **external_options())
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
