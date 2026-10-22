"""Read-only JSON-lines App Server transport; execution methods are unreachable."""
import json
import os
import queue
import shutil
import subprocess
import threading
from pathlib import Path

from .domain import TransientError, UnsafeError

READ_METHODS = frozenset({"initialize", "account/read", "account/rateLimits/read",
                          "thread/read", "thread/turns/list", "model/list"})


def find_codex() -> str:
    bundled = Path("/usr/lib/chatgpt/resources/codex")
    if bundled.is_file() and os.access(bundled, os.X_OK):
        return str(bundled)
    found = shutil.which("codex")
    if not found:
        raise UnsafeError("Codex CLI is missing. Install Codex before connecting.")
    return found


class ReadOnlyRpc:
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
                                            stderr=subprocess.DEVNULL, bufsize=0)
        except OSError as exc:
            raise UnsafeError("Unable to start the installed Codex App Server") from exc
        self.responses = queue.Queue()
        proc, responses = self.process, self.responses
        self.reader = threading.Thread(target=self._read, args=(proc, responses, self.events), daemon=True)
        self.reader.start()
        self._call("initialize", {"clientInfo": {"name": "codex_auto_resume", "title": "Codex Auto-Resume",
                                                "version": "0.2.1"},
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
            raise UnsafeError("Codex refused the read; check authentication and protocol compatibility")
        if not isinstance(response.get("result"), dict):
            raise UnsafeError("Unsupported App Server response")
        return response["result"]

    def call(self, method, params=None):
        if method not in READ_METHODS:
            raise UnsafeError("This release forbids execution, billing, auth changes, and approval methods")
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
