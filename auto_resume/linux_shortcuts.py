"""Reveal the packaged launcher when the historical source entry shadows it."""
import os
import re
import stat
import sys
import tempfile
from contextlib import suppress
from pathlib import Path

DESKTOP_NAME = "codex-auto-resume.desktop"
SYSTEM_LAUNCHER = Path("/usr/bin/codex-auto-resume")
SYSTEM_ENTRY = Path("/usr/share/applications") / DESKTOP_NAME
MAX_SHORTCUT_BYTES = 8192


def quote_desktop(value):
    if any(c in value for c in "\n\r\0"):
        raise ValueError("Unsupported installation path")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$").replace("%", "%%") + '"'


def _source_entry(command, icon):
    return f"""[Desktop Entry]
Type=Application
Name=Codex Auto-Resume
Comment=Continue armed Codex tasks after included-usage reset
Exec={command} ui
Icon={icon}
StartupWMClass=CodexAutoResume
Terminal=false
Categories=Development;Utility;
Actions=Toggle;Simulation;

[Desktop Action Toggle]
Name=Toggle Auto-Resume
Exec={command} toggle

[Desktop Action Simulation]
Name=Open safe simulation
Exec={command} --simulation ui
"""


def source_entry(python, prefix):
    assets = prefix / "share/codex-auto-resume"
    command = f"{quote_desktop(str(python))} {quote_desktop(str(assets / 'codex-auto-resume.pyz'))}"
    return _source_entry(command, assets / "icon.png")


def _is_generated_source_entry(contents, data_home):
    # Compare the entire historical template. A user-edited shortcut with the
    # same name or Exec line alone is not sufficient evidence of ownership.
    match = re.search(r'^Exec=("(?:[^"\\\r\n]|\\[^\r\n])*") ', contents, re.MULTILINE)
    if not match:
        return False
    assets = data_home.resolve() / "codex-auto-resume"
    command = f"{match[1]} {quote_desktop(str(assets / 'codex-auto-resume.pyz'))}"
    return contents in (_source_entry(command, assets / "icon.png"), _source_entry(command, "view-refresh"))


def _archive_override(path, data_home):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_size > MAX_SHORTCUT_BYTES:
                return None
            contents = stream.read(MAX_SHORTCUT_BYTES + 1).decode("utf-8")
        if not _is_generated_source_entry(contents, data_home):
            return None

        fd, backup = tempfile.mkstemp(prefix=".codex-auto-resume-", suffix=".source-backup", dir=path.parent)
        os.close(fd)
        archived = False
        try:
            current = path.lstat()
            if (current.st_ino, current.st_dev, current.st_mtime_ns) != (info.st_ino, info.st_dev, info.st_mtime_ns):
                return None
            os.replace(path, backup)
            archived = True
            return Path(backup)
        finally:
            # After a successful move this path holds the user's original file.
            if not archived:
                with suppress(OSError):
                    Path(backup).unlink()
    except (OSError, ValueError):
        return None


def migrate_shortcut():
    """Run as the affected desktop user. Never touch the user's app state."""
    if not sys.platform.startswith("linux") or os.geteuid() == 0:
        return None
    if not SYSTEM_ENTRY.is_file() or not os.access(SYSTEM_LAUNCHER, os.X_OK):
        return None

    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    if not data_home.is_absolute():
        data_home = Path.home() / ".local/share"
    return _archive_override(data_home / "applications" / DESKTOP_NAME, data_home)
