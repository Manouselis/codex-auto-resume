"""Small RFC6455 client for the official local App Server Unix socket.

No TCP listener, remote endpoint, token handling, or third-party dependency.
"""
import base64
import hashlib
import json
import os
import queue
import socket
import stat
import struct
import threading
import subprocess
import sys
from pathlib import Path

from .domain import NotSentError, TransientError, UnsafeError, WriterConflictError
from .protocol import READ_METHODS, find_codex, start_daemon

from .process import external_options

MAX_MESSAGE = 16 * 1024 * 1024
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class ProxyStream:
    """Bounded raw-byte adapter around the official platform socket proxy."""
    def __init__(self, path, timeout):
        self.timeout = timeout
        self.pending = bytearray()
        self.chunks = queue.Queue(maxsize=256)
        self.closed = threading.Event()
        try:
            self.process = subprocess.Popen([find_codex(), "app-server", "proxy", "--sock", str(path)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                bufsize=0, **external_options())
        except OSError as exc:
            raise TransientError("Unable to open the official Codex socket proxy") from exc
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            while not self.closed.is_set():
                chunk = self.process.stdout.read(65536)
                while not self.closed.is_set():
                    try:
                        self.chunks.put(chunk, timeout=.2)
                        break
                    except queue.Full:
                        pass
                if not chunk:
                    return
        except (OSError, ValueError):
            try:
                self.chunks.put_nowait(b"")
            except queue.Full:
                pass

    def recv(self, count):
        if not self.pending:
            if self.closed.is_set():
                return b""
            try:
                self.pending.extend(self.chunks.get(timeout=self.timeout))
            except queue.Empty as exc:
                raise TransientError("Codex socket proxy timed out") from exc
        part = bytes(self.pending[:count])
        del self.pending[:count]
        return part

    def sendall(self, data):
        view = memoryview(data)
        while view:
            written = self.process.stdin.write(view)
            if not written:
                raise OSError("Codex socket proxy disconnected")
            view = view[written:]

    def settimeout(self, timeout):
        self.timeout = timeout

    def shutdown(self, _how):
        self.close()

    def close(self):
        if self.closed.is_set() and self.process.poll() is not None:
            return
        self.closed.set()
        try:
            self.chunks.put_nowait(b"")
        except queue.Full:
            pass
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        for stream in (self.process.stdin, self.process.stdout):
            stream.close()


class LocalWebSocket:
    def __init__(self, path, timeout=20):
        if sys.platform == "win32":
            # Codex's official byte proxy performs Windows rendezvous/ACL checks
            # and connects to the same daemon. Its stdout is raw WebSocket bytes,
            # NOT JSONL. Never launch a separate app-server writer here.
            self.sock = ProxyStream(path, timeout)
        else:
            if not hasattr(socket, "AF_UNIX"):
                raise UnsafeError("This platform has no supported local App Server socket transport")
            path = Path(path)
            try:
                info = path.stat()
                if not stat.S_ISSOCK(info.st_mode) or (hasattr(os, "getuid") and info.st_uid != os.getuid()):
                    raise UnsafeError("The App Server socket is not owned by the current user")
                self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.sock.settimeout(timeout)
                self.sock.connect(str(path))
            except OSError as exc:
                if hasattr(self, "sock"):
                    self.sock.close()
                raise TransientError("The local Codex connection is unavailable") from exc
        self.send_lock = threading.Lock()
        key = base64.b64encode(os.urandom(16)).decode()
        request = ("GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                   f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        header = bytearray()
        try:
            self.sock.sendall(request.encode("ascii"))
            while not header.endswith(b"\r\n\r\n"):
                if len(header) > 8192:
                    raise UnsafeError("Oversized App Server handshake")
                header.extend(self.exact(1))
            lines = header.decode("ascii").split("\r\n")
            headers = {k.strip().lower(): v.strip() for line in lines[1:] if ":" in line for k, v in [line.split(":", 1)]}
            expected = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
            if (lines[0].split()[1] != "101" or headers.get("sec-websocket-accept") != expected
                    or headers.get("upgrade", "").lower() != "websocket"):
                raise UnsafeError("The local App Server rejected the WebSocket handshake")
            self.sock.settimeout(None)  # Idle waiting is unbounded; RPC waits remain bounded.
        except Exception:
            self.close()
            raise

    def exact(self, count):
        data = bytearray()
        while len(data) < count:
            chunk = self.sock.recv(count - len(data))
            if not chunk:
                raise TransientError("App Server connection closed")
            data.extend(chunk)
        return bytes(data)

    def send(self, data, opcode=1):
        if len(data) > MAX_MESSAGE:
            raise UnsafeError("Oversized App Server message")
        length = len(data)
        header = bytes([0x80 | opcode])
        if length < 126:
            header += bytes([0x80 | length])
        elif length <= 65535:
            header += bytes([0x80 | 126]) + struct.pack("!H", length)
        else:
            header += bytes([0x80 | 127]) + struct.pack("!Q", length)
        mask = os.urandom(4)
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(data))
        with self.send_lock:
            self.sock.sendall(header + mask + masked)

    def receive(self):
        message = bytearray()
        started = False
        while True:
            first, second = self.exact(2)
            final, opcode = bool(first & 0x80), first & 0x0F
            if first & 0x70 or second & 0x80:
                raise UnsafeError("Unsupported local WebSocket frame")
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self.exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self.exact(8))[0]
            if length > MAX_MESSAGE or len(message) + length > MAX_MESSAGE:
                raise UnsafeError("Oversized local WebSocket message")
            if opcode >= 8 and (not final or length > 125):
                raise UnsafeError("Invalid control frame")
            data = self.exact(length)
            if opcode == 8:
                raise TransientError("App Server closed its connection")
            if opcode == 9:
                self.send(data, opcode=10)
                continue
            if opcode == 10:
                continue
            if opcode == 1 and not started:
                started = True
            elif opcode != 0 or not started:
                raise UnsafeError("Unsupported local WebSocket message type")
            message.extend(data)
            if final:
                return bytes(message).decode("utf-8")

    def close(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


class DaemonRpc:
    methods = READ_METHODS

    def __init__(self, socket_path=None, *, timeout=20):
        codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        self.socket_path = socket_path or codex_home / "app-server-control/app-server-control.sock"
        self.timeout = timeout
        self.lock = threading.RLock()
        self.events = queue.Queue()
        self.responses = queue.Queue()
        self.connection = None
        self.sequence = 0

    def _start(self):
        try:
            connection = LocalWebSocket(self.socket_path, self.timeout)
        except TransientError:
            start_daemon()
            connection = LocalWebSocket(self.socket_path, self.timeout)
        self.connection = connection
        self.responses = queue.Queue()
        threading.Thread(target=self._read, args=(connection, self.responses), daemon=True).start()
        self._call("initialize", {"clientInfo": {"name": "codex_auto_resume", "title": "Codex Auto-Resume",
                                                "version": "0.8.0"},
                                  "capabilities": {"experimentalApi": True}})
        self._write({"method": "initialized"})

    def _read(self, connection, responses):
        try:
            while True:
                message = json.loads(connection.receive())
                if not isinstance(message, dict):
                    raise UnsafeError("Unsupported App Server message")
                if "method" in message:
                    if "id" in message or message["method"] in {
                        "turn/completed", "thread/status/changed", "serverRequest/resolved",
                        "thread/closed", "account/rateLimits/updated", "error"
                    }:
                        self.events.put(message)
                elif "id" in message:
                    responses.put(message)
        except (OSError, ValueError, TransientError, UnsafeError) as exc:
            responses.put(TransientError("App Server disconnected") if isinstance(exc, OSError) else exc)

    def _write(self, payload):
        try:
            self.connection.send(json.dumps(payload, allow_nan=False).encode())
        except OSError as exc:
            raise TransientError("App Server connection lost") from exc

    def _call(self, method, params):
        self.sequence += 1
        request_id = self.sequence
        self._write({"id": request_id, "method": method, "params": params})
        try:
            response = self.responses.get(timeout=self.timeout)
        except queue.Empty as exc:
            raise TransientError("App Server request timed out; no write will be retried") from exc
        if isinstance(response, Exception):
            self.close()
            raise response
        if response.get("id") != request_id:
            self.close()
            raise UnsafeError("Unexpected response identity; no write will be retried")
        if "error" in response:
            error = response["error"]
            if method == "thread/resume":
                if (isinstance(error, dict) and error.get("code") == -32600
                        and error.get("message") == f"thread {params.get('threadId')} already has an active writer"):
                    raise WriterConflictError("The original desktop owns the conversation writer")
                raise NotSentError("Conversation restoration was rejected before model dispatch")
            raise UnsafeError("App Server rejected " + method + "; inspect authentication and compatibility")
        result = response.get("result")
        if not isinstance(result, dict):
            raise UnsafeError("Unsupported App Server response")
        return result

    def call(self, method, params=None):
        if method not in self.methods:
            raise UnsafeError("Billing, auth changes, approval replies and unrelated mutations are forbidden")
        with self.lock:
            try:
                if self.connection is None:
                    self._start()
                return self._call(method, params or {})
            except (TransientError, UnsafeError, OSError):
                self.close()
                raise

    def close(self):
        connection, self.connection = self.connection, None
        if connection:
            connection.close()
