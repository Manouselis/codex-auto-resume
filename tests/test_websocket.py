import json
import queue
import struct
import threading
import unittest
from unittest.mock import patch

from auto_resume.domain import TransientError, UnsafeError
from auto_resume.live import LiveRpc
from auto_resume.websocket import DaemonRpc, LocalWebSocket, MAX_MESSAGE


class BytesSocket:
    def __init__(self, incoming=b""):
        self.incoming = bytearray(incoming)
        self.outgoing = bytearray()

    def recv(self, count):
        part = bytes(self.incoming[:count])
        del self.incoming[:count]
        return part

    def sendall(self, data):
        self.outgoing.extend(data)


def frame(data, opcode=1, final=True):
    length = len(data)
    start = bytes([(0x80 if final else 0) | opcode])
    if length < 126:
        return start + bytes([length]) + data
    if length < 65536:
        return start + b"\x7e" + struct.pack("!H", length) + data
    return start + b"\x7f" + struct.pack("!Q", length) + data


class WebSocketTests(unittest.TestCase):
    def client(self, incoming=b""):
        client = object.__new__(LocalWebSocket)
        client.sock = BytesSocket(incoming)
        client.send_lock = threading.Lock()
        return client

    def test_masked_client_frames_and_all_length_encodings(self):
        for count in (0, 1, 125, 126, 65535, 65536):
            with self.subTest(count=count):
                client = self.client()
                payload = b"x" * count
                client.send(payload)
                raw = client.sock.outgoing
                self.assertEqual(raw[0], 0x81)
                self.assertTrue(raw[1] & 0x80)
                offset = 2
                length = raw[1] & 127
                if length == 126:
                    length = struct.unpack("!H", raw[offset:offset + 2])[0]
                    offset += 2
                elif length == 127:
                    length = struct.unpack("!Q", raw[offset:offset + 8])[0]
                    offset += 8
                self.assertEqual(length, count)
                mask = raw[offset:offset + 4]
                decoded = bytes(value ^ mask[i % 4] for i, value in enumerate(raw[offset + 4:]))
                self.assertEqual(decoded, payload)

    def test_fragmented_message_with_interleaved_ping(self):
        incoming = frame(b'{"ok":', final=False) + frame(b"ping", opcode=9) + frame(b'true}', opcode=0)
        client = self.client(incoming)
        self.assertEqual(json.loads(client.receive()), {"ok": True})
        self.assertEqual(client.sock.outgoing[0], 0x8A)

    def test_server_close_is_transient_not_a_model_retry(self):
        with self.assertRaises(TransientError):
            self.client(frame(b"", opcode=8)).receive()

    def test_oversize_rejected_before_payload_allocation(self):
        raw = b"\x81\x7f" + struct.pack("!Q", MAX_MESSAGE + 1)
        with self.assertRaises(UnsafeError):
            self.client(raw).receive()

    def test_invalid_binary_masked_and_control_frames_rejected(self):
        for raw in (frame(b"bad", opcode=2), b"\x81\x80", frame(b"x" * 126, opcode=9)):
            with self.subTest(raw=raw[:3]), self.assertRaises(UnsafeError):
                self.client(raw).receive()

    def test_live_transport_has_no_billing_or_approval_calls(self):
        rpc = LiveRpc()
        for method in ("account/login/start", "account/logout", "account/rateLimitResetCredit/consume",
                       "item/permissions/requestApproval", "command/exec", "thread/start"):
            with self.subTest(method=method), self.assertRaises(UnsafeError):
                rpc.call(method)
        self.assertIsNone(rpc.connection)

    def test_failed_rpc_does_not_retry_and_connection_closes(self):
        class FakeConnection:
            def __init__(self, *_):
                self.messages = queue.Queue()
                self.sent = []
            def send(self, data):
                message = json.loads(data)
                self.sent.append(message)
                if message.get("method") == "initialize":
                    self.messages.put(json.dumps({"id": message["id"], "result": {}}))
            def receive(self):
                value = self.messages.get()
                if value is None:
                    raise TransientError("closed")
                return value
            def close(self):
                self.messages.put(None)
        with patch("auto_resume.websocket.LocalWebSocket", FakeConnection):
            rpc = DaemonRpc(timeout=0.01)
            with self.assertRaises(TransientError):
                rpc.call("account/read")
            self.assertIsNone(rpc.connection)


if __name__ == "__main__":
    unittest.main()
