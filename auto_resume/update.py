"""Update native installations from verified GitHub release assets."""
import hashlib
import json
import os
import platform
import plistlib
import re
import shlex
import ssl
import subprocess
import sys
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from . import __version__
from .process import external_options


REPO = "Manouselis/codex-auto-resume"
RELEASE_PAGE = f"https://github.com/{REPO}/releases"
RELEASES = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
ATOM = "{http://www.w3.org/2005/Atom}"
MAX_INSTALLER_SIZE = 100 * 1024 * 1024
TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
MAC_BUNDLE_ID = "io.github.manouselis.codex-auto-resume"
LINUX_EXECUTABLE = Path("/opt/codex-auto-resume/codex-auto-resume")
RELAUNCH = 75

UBUNTU_INSTALL = r"""
set -eu
work=$(/usr/bin/mktemp -d /tmp/codex-auto-resume.XXXXXXXX)
trap '/bin/rm -rf "$work"' EXIT
/bin/cp -- "$1" "$work/update.deb"
printf '%s  %s\n' "$2" "$work/update.deb" | /usr/bin/sha256sum --check --status
/usr/bin/apt-get -y -o DPkg::Lock::Timeout=30 install "$work/update.deb"
"""

# Stage beside the destination for same-filesystem renames and rollback.
MAC_INSTALL = r"""
set -eu
destination=$1
installer=$2
digest=$3
current=$4
version=$5
stage=$(/usr/bin/mktemp -d "${destination%/*}/.codex-auto-resume.XXXXXXXX")
mount="$stage/volume"
mounted=0
cleanup() {
    if [ -e "$stage/previous.app" ] && [ ! -e "$destination" ]; then
        /bin/mv "$stage/previous.app" "$destination" || return
    fi
    if [ "$mounted" = 1 ]; then
        /usr/bin/hdiutil detach "$mount" || return
    fi
    /bin/rm -rf "$stage"
}
trap cleanup EXIT
/bin/cp "$installer" "$stage/update.dmg"
printf '%s  %s\n' "$digest" "$stage/update.dmg" | /usr/bin/shasum -a 256 -c --status
/bin/mkdir "$mount"
/usr/bin/hdiutil attach -readonly -nobrowse -mountpoint "$mount" "$stage/update.dmg"
mounted=1
/usr/bin/ditto "$mount/Codex Auto-Resume.app" "$stage/new.app"
/usr/bin/hdiutil detach "$mount"
mounted=0
/usr/bin/codesign --verify --deep --strict "$stage/new.app"
info="$stage/new.app/Contents/Info.plist"
[ "$(/usr/libexec/PlistBuddy -c 'Print CFBundleIdentifier' "$info")" = io.github.manouselis.codex-auto-resume ]
[ "$(/usr/libexec/PlistBuddy -c 'Print CFBundleExecutable' "$info")" = 'Codex Auto-Resume' ]
[ "$(/usr/libexec/PlistBuddy -c 'Print CFBundleShortVersionString' "$info")" = "$version" ]
[ "$(/usr/libexec/PlistBuddy -c 'Print CFBundleShortVersionString' "$destination/Contents/Info.plist")" = "$current" ]
/bin/mv "$destination" "$stage/previous.app"
/bin/mv "$stage/new.app" "$destination"
"""


@dataclass(frozen=True)
class Release:
    version: str
    name: str
    url: str
    digest: str
    size: int | None


def package_target():
    arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
    if sys.platform == "win32":
        return "windows-x64-setup.exe"
    if sys.platform == "darwin":
        return f"macos-{arch}.dmg"
    if sys.platform.startswith("linux"):
        return f"linux-{arch}.deb"
    return None


def _windows_installation(executable):
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume") as key:
            registered = winreg.QueryValueEx(key, "DisplayIcon")[0]
        return Path(registered).resolve() == executable
    except (OSError, TypeError, ValueError):
        return False


def _mac_bundle(app):
    with (app / "Contents/Info.plist").open("rb") as stream:
        info = plistlib.load(stream)
    if info.get("CFBundleIdentifier") != MAC_BUNDLE_ID or info.get("CFBundleExecutable") != "Codex Auto-Resume":
        raise ValueError("Unexpected Auto-Resume app bundle")
    return info.get("CFBundleShortVersionString")


def installed_target():
    if not getattr(sys, "frozen", False):
        return None
    executable = Path(sys.executable).resolve()
    if sys.platform == "win32":
        return package_target() if _windows_installation(executable) else None
    if sys.platform.startswith("linux"):
        return package_target() if executable == LINUX_EXECUTABLE else None
    if sys.platform == "darwin":
        app = executable.parent.parent.parent
        if (app.suffix != ".app" or executable != app / "Contents/MacOS/Codex Auto-Resume"
                or "AppTranslocation" in app.parts):
            return None
        try:
            if not (os.statvfs(app).f_flag & os.ST_RDONLY) and _mac_bundle(app) == __version__:
                return package_target()
        except (OSError, ValueError, AttributeError, plistlib.InvalidFileException):
            pass
    return None


def _open_url(request, timeout):
    # A frozen macOS app can run without the build host's OpenSSL certificate paths.
    system_roots = Path("/etc/ssl/cert.pem")
    if sys.platform == "darwin" and system_roots.is_file():
        context = ssl.create_default_context()
        context.load_verify_locations(cafile=system_roots)
        return urlopen(request, timeout=timeout, context=context)
    return urlopen(request, timeout=timeout)


def check_for_update():
    target = installed_target()
    if target is None:
        return None
    cache = _cache_dir()
    try:
        (cache / f"codex-auto-resume-{__version__}-{target}").unlink(missing_ok=True)
    except OSError:
        pass  # The installer that just launched this app can still be exiting.
    try:
        return _select_feed_release(target)
    except (OSError, ValueError, ElementTree.ParseError):
        # The ordinary release feed avoids the shared anonymous REST API quota.
        payload = _read_release_data(RELEASES, 2 * 1024 * 1024, "application/vnd.github+json")
        return select_release(json.loads(payload), target=target)


def _read_release_data(url, limit, accept):
    request = Request(url, headers={"Accept": accept, "User-Agent": f"Codex-Auto-Resume/{__version__}"})
    with _open_url(request, timeout=8) as response:
        payload = response.read(limit + 1)
    if len(payload) > limit:
        raise ValueError("Release metadata is too large")
    return payload


def _select_feed_release(target, current=__version__):
    payload = _read_release_data(f"{RELEASE_PAGE}.atom", 512 * 1024, "application/atom+xml")
    feed = ElementTree.fromstring(payload)
    if feed.tag != f"{ATOM}feed":
        raise ValueError("Unexpected GitHub release feed")

    installed = tuple(map(int, current.split(".")))
    candidates = {}
    prefix = f"{RELEASE_PAGE}/tag/"
    for link in feed.findall(f"{ATOM}entry/{ATOM}link[@rel='alternate']"):
        href = link.get("href", "")
        if not href.startswith(prefix):
            continue
        tag = TAG.fullmatch(href[len(prefix):])
        if tag:
            version = tuple(map(int, tag.groups()))
            if version > installed:
                candidates[version] = tag[0]

    for version in sorted(candidates, reverse=True):
        tag = candidates[version]
        label = tag[1:]
        name = f"codex-auto-resume-{label}-{target}"
        assets = f"{RELEASE_PAGE}/download/{tag}"
        try:
            checksums = _read_release_data(f"{assets}/SHA256SUMS", 32 * 1024, "application/octet-stream")
        except HTTPError as exc:
            if exc.code == 404:
                continue
            raise
        line = re.compile(r"([0-9a-f]{64}) [ *]" + re.escape(name))
        matches = [match[1] for entry in checksums.decode("ascii").splitlines() if (match := line.fullmatch(entry))]
        if len(matches) == 1:
            return Release(label, name, f"{assets}/{name}", matches[0], None)
    if candidates:
        raise ValueError("No compatible installer checksum found in the release feed")
    return None


def select_release(releases, current=__version__, *, target):
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
        name = f"codex-auto-resume-{label}-{target}"
        url = f"{RELEASE_PAGE}/download/{tag[0]}/{name}"
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
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")
    elif sys.platform == "darwin":
        root = Path.home() / "Library/Caches"
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return root / "codex-auto-resume/updates"


def download_update(release):
    cache = _cache_dir()
    cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    total = 0
    digest = hashlib.sha256()
    temporary = None
    limit = release.size if release.size is not None else MAX_INSTALLER_SIZE
    try:
        with tempfile.NamedTemporaryFile(dir=cache, suffix=".part", delete=False) as output:
            temporary = Path(output.name)
            with _open_url(release.url, timeout=15) as response:
                while chunk := response.read(64 * 1024):
                    total += len(chunk)
                    if total > limit:
                        raise ValueError("Unexpected installer size")
                    digest.update(chunk)
                    output.write(chunk)
        if (not total or (release.size is not None and total != release.size)
                or digest.hexdigest() != release.digest):
            raise ValueError("Installer verification failed")
        installer = cache / release.name
        temporary.replace(installer)
        return installer
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _start_windows_installer(installer):
    # NSIS requires the unquoted /D= directory to be last, even with spaces.
    command = subprocess.list2cmdline([str(installer), "/S", f"/UPDATEPID={os.getpid()}"])
    command += " /D=" + str(Path(sys.executable).parent)
    options = external_options()
    options["env"] = _relaunch_env()
    subprocess.Popen(command, executable=str(installer), **options)


def _run(command, *, check=True, timeout=None):
    return subprocess.run(command, capture_output=True, check=check, timeout=timeout, **external_options())


def _install_ubuntu(installer, release):
    arch = "arm64" if release.name.endswith("-arm64.deb") else "amd64"
    fields = _run(["/usr/bin/dpkg-deb", "--showformat=${Package}\n${Version}\n${Architecture}\n",
                   "--show", str(installer)], timeout=20).stdout.decode().splitlines()
    if fields != ["codex-auto-resume", release.version, arch]:
        raise ValueError("Unexpected Auto-Resume Debian package")
    command = ["/bin/sh", "-c", UBUNTU_INSTALL, "codex-auto-resume-update", str(installer), release.digest]
    if os.geteuid() != 0:
        command = ["/usr/bin/pkexec", "--disable-internal-agent", *command]
    _run(command)

    # The installed binary changed, but an active user service still runs the old code.
    # Match normal shutdown behavior so previously armed work requires a fresh opt-in.
    units = ["codex-auto-resume-native.service", "codex-auto-resume.service"]
    with suppress(OSError, subprocess.TimeoutExpired):
        _run(["/usr/bin/systemctl", "--user", "stop", *units], check=False, timeout=30)


def _install_macos(installer, release, app):
    command = ["/bin/sh", "-c", MAC_INSTALL, "codex-auto-resume-update", str(app), str(installer),
               release.digest, __version__, release.version]
    if not os.access(app.parent, os.W_OK):
        script = 'on run argv\n  do shell script (item 1 of argv) with administrator privileges\nend run'
        command = ["/usr/bin/osascript", "-e", script, shlex.join(command)]
    _run(command)


def install_update(installer, release):
    """Install a verified download. Return whether the app must relaunch itself."""
    target = installed_target()
    if target is None or installer.name != f"codex-auto-resume-{release.version}-{target}":
        raise ValueError("Update does not match this installation")
    installer = installer.resolve()
    if sys.platform == "win32":
        _start_windows_installer(installer)
        return False
    if sys.platform == "darwin":
        _install_macos(installer, release, Path(sys.executable).resolve().parent.parent.parent)
    else:
        _install_ubuntu(installer, release)
    return True


def _relaunch_env():
    env = external_options().get("env", os.environ.copy())
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def relaunch():
    os.execve(sys.executable, [sys.executable, *sys.argv[1:]], _relaunch_env())
