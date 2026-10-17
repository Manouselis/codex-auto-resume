import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from auto_resume.domain import TransientError, UnsafeError
from auto_resume.lifecycle import ControllerLock
from auto_resume.protocol import ReadOnlyRpc


MOCK = r'''
import json,sys,time
for line in sys.stdin:
    p=json.loads(line)
    if "id" not in p: continue
    method=p["method"]
    if method=="initialize":
        print(json.dumps({"id":p["id"],"result":{"userAgent":"mock-app-server"}}),flush=True)
    elif method=="account/read":
        print(json.dumps({"id":p["id"],"result":{"account":{"type":"chatgpt","planType":"plus"}}}),flush=True)
    elif method=="thread/read":
        mode=p["params"].get("threadId")
        if mode=="timeout":time.sleep(5)
        elif mode=="approval":print(json.dumps({"id":99,"method":"item/permissions/requestApproval","params":{}}),flush=True)
        elif mode=="format":print('[]',flush=True)
        elif mode=="exit":sys.exit(0)
        elif mode=="error":print(json.dumps({"id":p["id"],"error":{"code":-1,"message":"PRIVATE TOKEN MUST NOT LEAK"}}),flush=True)
        else:print(json.dumps({"id":p["id"],"result":{"thread":{"id":mode}}}),flush=True)
    else:
        print(json.dumps({"id":p["id"],"result":{}}),flush=True)
'''


class RpcTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name) / "mock_server.py"
        path.write_text(MOCK)
        self.rpc = ReadOnlyRpc([sys.executable, "-u", str(path)], timeout=0.3)

    def tearDown(self):
        self.rpc.close()
        self.tmp.cleanup()

    def test_initialize_and_read(self):
        result = self.rpc.call("account/read")
        self.assertEqual(result["account"]["type"], "chatgpt")
        self.assertEqual(self.rpc.call("thread/read", {"threadId": "my-thread"})["thread"]["id"], "my-thread")

    def test_local_controls_do_not_require_installed_codex(self):
        from unittest.mock import patch
        with patch("auto_resume.protocol.find_codex", side_effect=UnsafeError("missing")):
            rpc = ReadOnlyRpc()
            self.assertIsNone(rpc.process)
            with self.assertRaises(UnsafeError):
                rpc.call("account/read")

    def test_billing_execution_and_approval_methods_are_forbidden(self):
        for method in ("turn/start", "turn/steer", "thread/resume", "thread/start",
                       "account/rateLimitResetCredit/consume", "account/login/start",
                       "item/permissions/requestApproval", "account/logout", "command/exec"):
            with self.subTest(method=method), self.assertRaises(UnsafeError):
                self.rpc.call(method)
        self.assertIsNone(self.rpc.process)

    def test_approval_request_never_answered(self):
        with self.assertRaises(UnsafeError):
            self.rpc.call("thread/read", {"threadId": "approval"})
        self.assertIsNone(self.rpc.process)

    def test_unknown_response_schema(self):
        with self.assertRaises(UnsafeError):
            self.rpc.call("thread/read", {"threadId": "format"})

    def test_disconnect_reconnect_read_only(self):
        with self.assertRaises(TransientError):
            self.rpc.call("thread/read", {"threadId": "exit"})
        self.assertEqual(self.rpc.call("account/read")["account"]["planType"], "plus")

    def test_timeout_then_reconnect(self):
        with self.assertRaises(TransientError):
            self.rpc.call("thread/read", {"threadId": "timeout"})
        self.assertEqual(self.rpc.call("account/read")["account"]["type"], "chatgpt")

    def test_backend_error_text_is_not_exposed(self):
        with self.assertRaises(UnsafeError) as caught:
            self.rpc.call("thread/read", {"threadId": "error"})
        self.assertNotIn("PRIVATE TOKEN", str(caught.exception))

    def test_single_controller_and_release(self):
        state = Path(self.tmp.name) / "state.sqlite3"
        first, second = ControllerLock(state), ControllerLock(state)
        first.acquire()
        try:
            with self.assertRaises(UnsafeError):
                second.acquire()
        finally:
            first.release()
        second.acquire()
        second.release()

    def test_os_releases_lock_after_crash(self):
        state = str(Path(self.tmp.name) / "crash.sqlite3")
        code = "from auto_resume.lifecycle import ControllerLock;import os; lock=ControllerLock(" + repr(state) + ");lock.acquire();os._exit(0)"
        subprocess.run([sys.executable, "-c", code], check=True)
        lock = ControllerLock(state)
        lock.acquire()
        lock.release()


if __name__ == "__main__":
    unittest.main()
