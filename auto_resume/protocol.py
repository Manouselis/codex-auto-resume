"""Runtime discovery and restricted JSON-lines App Server clients."""
import json
import os
import queue
import shutil
import subprocess
import threading
import sys
from pathlib import Path

from . import __version__
from .domain import TransientError, UnsafeError
from .process import external_options

READ_METHODS = frozenset({"initialize", "account/read", "account/rateLimits/read",
                          "thread/read", "thread/turns/list", "model/list"})


class DaemonPackageError(TransientError):
    """The discovered runtime can run App Server but has no managed daemon package."""

    def __init__(self, binary):
        super().__init__("The installed Codex runtime has no managed daemon package")
        self.binary = binary


def _windows_store_runtimes():
    """Resolve the current user's Store installation without browsing WindowsApps."""
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32")
    family = "OpenAI.Codex_2p2nqsd0c76g0"
    packages = kernel.GetPackagesByPackageFamily
    packages.argtypes = (wintypes.LPCWSTR, ctypes.POINTER(wintypes.UINT),
                         ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(wintypes.UINT), wintypes.LPWSTR)
    get_path = kernel.GetPackagePathByFullName
    get_path.argtypes = (wintypes.LPCWSTR, ctypes.POINTER(wintypes.UINT), wintypes.LPWSTR)
    count, length = wintypes.UINT(), wintypes.UINT()
    insufficient_buffer = 122
    if packages(family, ctypes.byref(count), None, ctypes.byref(length), None) != insufficient_buffer:
        return
    names = (wintypes.LPWSTR * count.value)()
    buffer = ctypes.create_unicode_buffer(length.value)
    if packages(family, ctypes.byref(count), names, ctypes.byref(length), buffer) != 0:
        return
    # MSIX package names contain four numeric version components before architecture.
    for name in sorted(names, key=lambda name: tuple(map(int, name.split("_")[1].split("."))), reverse=True):
        size = wintypes.UINT()
        if get_path(name, ctypes.byref(size), None) == insufficient_buffer:
            path = ctypes.create_unicode_buffer(size.value)
            if get_path(name, ctypes.byref(size), path) == 0:
                yield Path(path.value) / "app/resources/codex.exe"


def find_codex() -> str:
    # Desktop launches do not inherit shell PATH customizations. Search only
    # standard per-user/system installation roots; never execute from a project.
    home = Path.home()
    codex_home = Path(os.environ.get("CODEX_HOME") or home / ".codex")
    candidates = []
    if sys.platform == "darwin":
        for base in (Path("/Applications"), home / "Applications"):
            for app in ("ChatGPT.app", "Codex.app"):
                candidates += [base / app / "Contents/Resources/codex",
                               base / app / "Contents/Resources/bin/codex"]
    elif sys.platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local"))
        programs = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        candidates += [local / "Programs/OpenAI/Codex/bin/codex.exe",
                       local / "Programs/ChatGPT/resources/codex.exe",
                       local / "Programs/Codex/resources/codex.exe",
                       programs / "ChatGPT/resources/codex.exe",
                       programs / "Codex/resources/codex.exe"]
    else:
        candidates += [Path("/usr/lib/chatgpt/resources/codex"),
                       Path("/opt/ChatGPT/resources/codex"), Path("/opt/Codex/resources/codex")]
    executable = "codex.exe" if sys.platform == "win32" else "codex"
    candidates += [home / ".local/bin" / executable, codex_home / "bin" / executable]
    if sys.platform == "darwin":
        candidates += [Path("/opt/homebrew/bin/codex"), Path("/usr/local/bin/codex")]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    if sys.platform == "win32":
        # Use the selected package even when a Start-menu launch has no shell PATH.
        candidates = [codex_home / "packages/app-server-daemon/current/bin/codex.exe",
                      codex_home / "packages/standalone/current/bin/codex.exe",
                      codex_home / "packages/standalone/current/codex.exe"]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        for candidate in _windows_store_runtimes():
            if candidate.is_file():
                return str(candidate)
    found = shutil.which(executable)
    if found:
        return found
    # The desktop's managed daemon is a full Codex runtime. Prefer the newest
    # installed binary without reading credentials or modifying Codex packages.
    releases = codex_home / "packages/app-server-daemon/releases"
    installed = [p for p in releases.glob("*/bin/" + executable) if p.is_file() and os.access(p, os.X_OK)]
    if installed:
        return str(max(installed, key=lambda p: p.stat().st_mtime_ns))
    raise UnsafeError("Codex was not found. Install the Codex desktop app, open it and sign in, then reopen Auto-Resume.")


def start_daemon():
    """Start the official per-user transport; this never starts a model turn."""
    binary = find_codex()
    try:
        subprocess.run([binary, "app-server", "daemon", "start"], capture_output=True,
                       timeout=30, check=True, **external_options())
    except subprocess.CalledProcessError as exc:
        if b"no complete local package" in (exc.stderr or b""):
            raise DaemonPackageError(binary) from exc
        raise TransientError("Unable to start the Codex connection; check the installed Codex runtime") from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise TransientError("Unable to start the Codex connection; check the installed Codex runtime") from exc


class _StdioRpc:
    methods = READ_METHODS
    forbidden_method = "This release forbids execution, billing, auth changes, and approval methods"

    def __init__(self, command=None, *, timeout=10):
        self.command = command
        self.timeout = timeout
        self.lock = threading.RLock()
        self.events = None
        self.process = None
        self.responses = queue.Queue()
        self.sequence = 0
        self.reader = None

    def _start(self):
        command = self.command or [find_codex(), "app-server", "--listen", "stdio://"]
        try:
            # Codex owns credentials. No token file is opened by this application.
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL, bufsize=0, **external_options())
        except OSError as exc:
            raise UnsafeError("Unable to start the installed Codex App Server") from exc
        self.responses = queue.Queue()
        proc, responses = self.process, self.responses
        self.reader = threading.Thread(target=self._read, args=(proc, responses, self.events), daemon=True)
        self.reader.start()
        self._call("initialize", {"clientInfo": {"name": "codex_auto_resume", "title": "Codex Auto-Resume",
                                                "version": __version__},
                                  "capabilities": {"experimentalApi": True}})
        self._write({"method": "initialized"})

    @staticmethod
    def _read(proc, responses, events=None):
        try:
            while True:
                line = proc.stdout.readline(16 * 1024 * 1024 + 1)
                if not line:
                    responses.put(TransientError("Codex App Server disconnected"))
                    return
                if len(line) > 16 * 1024 * 1024 or not line.endswith(b"\n"):
                    raise ValueError("Oversized protocol message")
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("Invalid protocol message")
                if "method" in message and events is not None:
                    method = message["method"]
                    if "id" in message or method in {
                        "turn/completed", "thread/status/changed", "serverRequest/resolved",
                        "thread/closed", "account/rateLimits/updated", "error"
                    }:
                        events.put(message)
                elif "id" in message:
                    if "method" in message:
                        # A read-only client cannot answer approvals or auth requests.
                        responses.put(UnsafeError("Server requested interactive permission; inspect Codex"))
                    else:
                        responses.put(message)
        except (ValueError, OSError):
            responses.put(UnsafeError("Codex protocol format is unsupported"))

    def _write(self, payload):
        try:
            self.process.stdin.write((json.dumps(payload, allow_nan=False) + "\n").encode())
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise TransientError("Codex App Server disconnected") from exc

    def _call(self, method, params):
        self.sequence += 1
        seq = self.sequence
        self._write({"id": seq, "method": method, "params": params})
        try:
            response = self.responses.get(timeout=self.timeout)
        except queue.Empty as exc:
            raise TransientError("Codex App Server timed out") from exc
        if isinstance(response, Exception):
            raise response
        if response.get("id") != seq:
            raise UnsafeError("Unexpected App Server response identity")
        if "error" in response:
            # Do not log backend text: it may include account or conversation details.
            raise UnsafeError("App Server rejected " + method + "; inspect authentication and compatibility")
        if not isinstance(response.get("result"), dict):
            raise UnsafeError("Unsupported App Server response")
        return response["result"]

    def call(self, method, params=None):
        if method not in self.methods:
            raise UnsafeError(self.forbidden_method)
        with self.lock:
            try:
                if self.process is None or self.process.poll() is not None:
                    self.close()
                    self._start()
                return self._call(method, params or {})
            except (TransientError, UnsafeError):
                self.close()
                raise

    def close(self):
        proc, self.process = self.process, None
        if proc is not None:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
            for pipe in (proc.stdin, proc.stdout):
                if pipe:
                    pipe.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class ReadOnlyRpc(_StdioRpc):
    """Observe the installed runtime without issuing writes."""


class DesktopQueueRpc(_StdioRpc):
    """Read saved state and use the native queue without acquiring a thread writer."""

    methods = READ_METHODS | {"config/read", "thread/list", "thread/items/list",
                             "thread/goal/get", "thread/goal/set", "thread/queue/list", "thread/queue/add"}
    forbidden_method = "The bundled Codex connection supports desktop conversations through the native queue"
