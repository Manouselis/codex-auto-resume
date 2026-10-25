#!/usr/bin/env python3
"""Reversible per-user installation, with no changes to Codex configuration."""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from build import build_app


def default_prefix():
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "Programs/CodexAutoResume"
    return Path.home() / ".local"


def quote_desktop(value):
    if any(c in value for c in "\n\r\0"):
        raise ValueError("Unsupported installation path")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$").replace("%", "%%") + '"'


def atomic_write(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("Refusing a symlink destination")
    fd, temporary = tempfile.mkstemp(prefix=".auto-resume-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, default=default_prefix())
    args = parser.parse_args(argv)
    prefix = args.prefix.expanduser().resolve()
    folder = prefix / "share/codex-auto-resume"
    marker = folder / "installation.json"
    app = folder / "codex-auto-resume.pyz"
    launcher = prefix / "bin" / ("codex-auto-resume.cmd" if os.name == "nt" else "codex-auto-resume")
    desktop = prefix / "share/applications/codex-auto-resume.desktop"
    files = [app, launcher] + ([] if os.name == "nt" else [desktop])
    if any(not p.parent.resolve().is_relative_to(prefix) for p in [*files, marker]):
        raise ValueError("Refusing installation through a symlink outside the selected prefix")
    if not marker.exists() and any(p.exists() for p in files):
        raise ValueError("Existing files are not owned by this installer; choose another prefix")
    if marker.exists():
        previous = json.loads(marker.read_text())
        if previous.get("application") != "codex-auto-resume":
            raise ValueError("Installation marker does not belong to Auto-Resume")
    if os.name == "nt":
        # cmd quoting is deliberately limited; refuse metacharacter paths.
        if any(c in str(prefix) + sys.executable for c in '%!^&|<>\r\n'):
            raise ValueError("Choose an installation and Python path without cmd metacharacters")
        script = f'@echo off\r\n"{sys.executable}" "{app}" %*\r\n'
    else:
        import shlex
        script = '#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' ' + shlex.quote(str(app)) + ' "$@"\n'
    desktop_text = ""
    if os.name != "nt":
        cmd = quote_desktop(sys.executable) + " " + quote_desktop(str(app))
        desktop_text = f"""[Desktop Entry]
Type=Application
Name=Codex Auto-Resume
Comment=Continue armed Codex tasks after included-usage reset
Exec={cmd} ui
Icon=view-refresh
Terminal=false
Categories=Development;Utility;
Actions=Toggle;Simulation;

[Desktop Action Toggle]
Name=Toggle Auto-Resume
Exec={cmd} toggle

[Desktop Action Simulation]
Name=Open safe simulation
Exec={cmd} --simulation ui
"""
    atomic_write(app, build_app())
    atomic_write(launcher, script.encode(), 0o755)
    if desktop_text:
        atomic_write(desktop, desktop_text.encode())
    metadata = {"application": "codex-auto-resume", "version": "0.4.1", "prefix": str(prefix),
                "files": [p.relative_to(prefix).as_posix() for p in files]}
    atomic_write(marker, (json.dumps(metadata, indent=2) + "\n").encode())
    print("Installed:", launcher)
    print("Open the companion:", launcher, "ui")
    print("Real continuation is available after explicit arming. No startup item was enabled.")


if __name__ == "__main__":
    main()
