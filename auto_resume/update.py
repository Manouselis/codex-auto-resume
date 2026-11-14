"""Update the installed Windows app from this project's GitHub releases."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from . import __version__
from .process import external_options


REPO = "Manouselis/codex-auto-resume"
RELEASES = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
MAX_INSTALLER_SIZE = 100 * 1024 * 1024
TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


@dataclass(frozen=True)
class Release:
    version: str
    name: str
    url: str
    digest: str
    size: int


def installed_windows_app():
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume") as key:
            executable = winreg.QueryValueEx(key, "DisplayIcon")[0]
        return Path(executable).resolve() == Path(sys.executable).resolve()
    except (OSError, TypeError, ValueError):
        return False


def check_for_update():
    cache = _cache_dir()
    try:
        (cache / f"codex-auto-resume-{__version__}-windows-x64-setup.exe").unlink(missing_ok=True)
    except OSError:
        pass  # The installer that just launched this app can still be exiting.
    request = Request(RELEASES, headers={"Accept": "application/vnd.github+json",
                                         "User-Agent": f"Codex-Auto-Resume/{__version__}"})
    with urlopen(request, timeout=8) as response:
        limit = 2 * 1024 * 1024
        payload = response.read(limit + 1)
        if len(payload) > limit:
            raise ValueError("Release feed is too large")
        releases = json.loads(payload)
    return select_release(releases)


def select_release(releases, current=__version__):
    # The project's beta releases are published as GitHub prereleases.
    newest = tuple(map(int, current.split(".")))
    selected = None
    for release in releases:
        tag = TAG.fullmatch(release.get("tag_name", ""))
        if release.get("draft") or tag is None:
            continue
        version = tuple(map(int, tag.groups()))
        if version <= newest:
            continue
        label = tag[0][1:]
        name = f"codex-auto-resume-{label}-windows-x64-setup.exe"
        url = f"https://github.com/{REPO}/releases/download/{tag[0]}/{name}"
        for asset in release.get("assets", []):
            digest = re.fullmatch(r"sha256:([0-9a-f]{64})", asset.get("digest") or "")
            size = asset.get("size")
            if (asset.get("name") == name and asset.get("browser_download_url") == url
                    and type(size) is int and 0 < size <= MAX_INSTALLER_SIZE and digest):
                selected = Release(label, name, url, digest[1], size)
                newest = version
                break
    return selected


def _cache_dir():
    return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / "codex-auto-resume/updates"


def download_update(release):
    cache = _cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    total = 0
    digest = hashlib.sha256()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=cache, suffix=".part", delete=False) as output:
            temporary = Path(output.name)
            with urlopen(release.url, timeout=15) as response:
                while chunk := response.read(64 * 1024):
                    total += len(chunk)
                    if total > release.size:
                        raise ValueError("Unexpected installer size")
                    digest.update(chunk)
                    output.write(chunk)
        if total != release.size or digest.hexdigest() != release.digest:
            raise ValueError("Installer verification failed")
        installer = cache / release.name
        temporary.replace(installer)
        return installer
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def start_installer(installer):
    # NSIS requires the unquoted /D= directory to be last, even with spaces.
    command = subprocess.list2cmdline([str(installer), "/S", f"/UPDATEPID={os.getpid()}"])
    command += " /D=" + str(Path(sys.executable).parent)
    subprocess.Popen(command, executable=str(installer), **external_options())
