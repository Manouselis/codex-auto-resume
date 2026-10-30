#!/usr/bin/env python3
"""Remove only files recorded by this project's installer; preserve user state."""
import argparse
import json
from pathlib import Path

from install import default_prefix


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, default=default_prefix())
    args = parser.parse_args(argv)
    prefix = args.prefix.expanduser().resolve()
    marker = prefix / "share/codex-auto-resume/installation.json"
    if not marker.is_file() or marker.is_symlink():
        raise ValueError("No managed Auto-Resume installation found")
    data = json.loads(marker.read_text())
    if data.get("application") != "codex-auto-resume" or data.get("prefix") != str(prefix):
        raise ValueError("Invalid installation manifest")
    allowed = {"share/codex-auto-resume/codex-auto-resume.pyz", "bin/codex-auto-resume",
               "bin/codex-auto-resume.cmd", "share/applications/codex-auto-resume.desktop",
               "share/codex-auto-resume/icon.png", "share/systemd/user/codex-auto-resume.service"}
    if not isinstance(data.get("files"), list) or not set(data["files"]) <= allowed:
        raise ValueError("Manifest contains unexpected paths")
    for name in data["files"]:
        path = prefix / name
        if not path.resolve().is_relative_to(prefix) or path.is_symlink():
            raise ValueError("Refusing unsafe uninstall path")
    for name in data["files"]:
        (prefix / name).unlink(missing_ok=True)
    marker.unlink()
    try:
        marker.parent.rmdir()
    except OSError:
        pass
    print("Uninstalled Auto-Resume. Local task history was preserved. Codex files were not changed.")


if __name__ == "__main__":
    main()
