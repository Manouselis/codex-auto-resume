import copy
import queue
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path

from auto_resume.adapters import fake_payload
from auto_resume.domain import UnsafeError
from auto_resume.engine import Engine
from auto_resume.live import LiveAdapter, manual_request
from auto_resume.store import Store


class Backend:
    def __init__(self, cwd, clock=time.time):
        self.clock = clock
        self.payload = fake_payload(clock(), five=5, ordinary=True)
        self.account = {"type": "chatgpt", "planType": "plus"}
        self.thread = {"id": "live-test", "historyMode": "paginated", "model": "simulation-model",
                       "modelProvider": "openai", "cwd": cwd, "reasoningEffort": "medium",
                       "status": {"type": "notLoaded"}}
        self.latest = {"id": "failed-turn", "status": "failed", "error": {"codexErrorInfo": "usageLimitExceeded"},
                       "items": [], "completedAt": int(clock())}
        self.config = {"model_provider": None, "service_tier": "default", "model_providers": {},
                       "chatgpt_base_url": "https://chatgpt.com/backend-api/", "openai_base_url": None}
        self.events = queue.Queue()
        self.calls = []
        self.after_resume = None

    def call(self, method, params=None):
        params = params or {}
        self.calls.append((method, copy.deepcopy(params)))
        if method == "account/read":
            return {"account": self.account}
        if method == "account/rateLimits/read":
            return self.payload
        if method == "config/read":
            return {"config": self.config}
        if method == "thread/read":
            return {"thread": copy.deepcopy(self.thread)}
        if method == "thread/turns/list":
            return {"data": [copy.deepcopy(self.latest)], "nextCursor": None}
        if method == "thread/resume":
            self.thread["status"] = {"type": "idle"}
            if self.after_resume:
                self.after_resume()
            return {"model": self.thread["model"], "modelProvider": "openai", "cwd": self.thread["cwd"],
                    "sandbox": {"type": "readOnly"}, "approvalPolicy": "on-request", "serviceTier": "default"}
        if method == "turn/start":
            self.latest = {"id": "real-protocol-next-turn", "status": "inProgress", "error": None, "items": []}
            self.thread["status"] = {"type": "active", "activeFlags": []}
            return {"turn": self.latest}
        raise AssertionError(method)

    def close(self):
        pass


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock_value = [1_800_000_000.0]
        self.clock = lambda: self.clock_value[0]
        self.backend = Backend(self.tmp.name, self.clock)
        self.adapter = LiveAdapter(self.backend, self.clock)
        self.adapter.check_enabled = lambda: True

    def tearDown(self):
        self.tmp.cleanup()

    def request(self):
        return manual_request(self.adapter.observe("live-test"), "Continue only unfinished work")

    def writes(self):
        return [p for method, p in self.backend.calls if method == "turn/start"]

    def test_real_dispatch_method_no_longer_unconditionally_refuses(self):
        request = self.request()
        self.assertEqual(self.adapter.submit(request), "real-protocol-next-turn")
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(self.writes()[0]["threadId"], "live-test")
        self.assertEqual(self.writes()[0]["clientUserMessageId"], request.continuation_id)
        self.assertNotIn("sandboxPolicy", self.writes()[0])
        self.assertNotIn("approvalPolicy", self.writes()[0])
        self.assertNotIn("model", self.writes()[0])

    def test_engine_drives_live_protocol_after_reset_once(self):
        store = Store(Path(self.tmp.name) / "state.sqlite3")
        try:
            self.backend.payload = fake_payload(self.clock())
            engine = Engine(store, self.adapter, self.clock)
            store.set_enabled(True, self.clock())
            engine.register("live-test")
            engine.tick()
            self.clock_value[0] += 26
            self.backend.payload = fake_payload(self.clock(), five=5, ordinary=True)
            engine.tick()
            engine.tick()
            self.assertEqual(len(self.writes()), 1)
            self.assertEqual(store.get("live-test")["ack_turn"], "real-protocol-next-turn")
        finally:
            store.close()

    def test_backend_cache_delay_retries_reads_then_continues(self):
        store = Store(Path(self.tmp.name) / "delayed.sqlite3")
        try:
            self.backend.payload = fake_payload(self.clock())
            engine = Engine(store, self.adapter, self.clock)
            store.set_enabled(True, self.clock())
            engine.register("live-test")
            engine.tick()
            self.clock_value[0] += 26
            engine.tick()
            self.assertEqual(self.writes(), [])
            self.assertEqual(store.get("live-test")["retries"], 1)
            self.clock_value[0] += 16
            self.backend.payload = fake_payload(self.clock(), five=5, ordinary=True)
            engine.tick()
            self.assertEqual(len(self.writes()), 1)
        finally:
            store.close()

    def test_weekly_exhausted_zero_real_protocol_submissions(self):
        request = self.request()
        self.backend.payload["rateLimitsByLimitId"]["codex"]["secondary"]["usedPercent"] = 100
        with self.assertRaises(UnsafeError):
            self.adapter.submit(request)
        self.assertEqual(self.writes(), [])

    def test_paid_balance_blocks_real_dispatch(self):
        request = self.request()
        self.backend.payload["rateLimitsByLimitId"]["codex"]["credits"] = {"hasCredits": True, "unlimited": False, "balance": "10"}
        with self.assertRaises(UnsafeError):
            self.adapter.submit(request)
        self.assertEqual(self.writes(), [])

    def test_nonincluded_request_cannot_bypass_policy(self):
        request = replace(self.request(), included_only=False)
        with self.assertRaises(UnsafeError):
            self.adapter.submit(request)
        self.assertEqual(self.writes(), [])

    def test_permission_false_null_or_missing(self):
        request = self.request()
        for permission in (False, None):
            self.backend.payload["ordinaryUsageAllowed"] = permission
            with self.assertRaises(UnsafeError):
                self.adapter.submit(request)
        self.assertEqual(self.writes(), [])

    def test_api_auth_rejected(self):
        self.backend.account = {"type": "apiKey"}
        with self.assertRaises(UnsafeError):
            self.adapter.observe("live-test")

    def test_custom_provider_and_endpoint_rejected(self):
        request = self.request()
        self.backend.config["model_provider"] = "custom"
        with self.assertRaises(UnsafeError):
            self.adapter.submit(request)
        self.backend.config["model_provider"] = None
        self.backend.config["chatgpt_base_url"] = "https://untrusted.example"
        with self.assertRaises(UnsafeError):
            self.adapter.submit(request)
        self.assertEqual(self.writes(), [])

    def test_fast_tier_refused(self):
        request = self.request()
        self.backend.config["service_tier"] = "fast"
        with self.assertRaises(UnsafeError):
            self.adapter.submit(request)
        self.assertEqual(self.writes(), [])

    def test_task_changes_after_resume_no_submission(self):
        request = self.request()
        self.backend.after_resume = lambda: self.backend.latest.update(id="new-user-turn", status="completed")
        with self.assertRaises(UnsafeError):
            self.adapter.submit(request)
        self.assertEqual(self.writes(), [])

    def test_completed_or_cancelled_never_automatically_replayed(self):
        for status in ("completed", "interrupted"):
            self.backend.latest["status"] = status
            request = self.request()
            with self.assertRaises(UnsafeError):
                self.adapter.submit(request)
        self.assertEqual(self.writes(), [])

    def test_outstanding_approval_never_answered(self):
        request = self.request()
        self.backend.events.put({"id": 42, "method": "item/permissions/requestApproval", "params": {"threadId": "live-test"}})
        with self.assertRaises(UnsafeError):
            self.adapter.submit(request)
        self.assertEqual(self.writes(), [])
        self.assertFalse(any("Approval" in method for method, _ in self.backend.calls))

    def test_disable_during_restore_stops_dispatch(self):
        request = self.request()
        self.backend.after_resume = lambda: setattr(self.adapter, "check_enabled", lambda: False)
        with self.assertRaises(UnsafeError):
            self.adapter.submit(request)
        self.assertEqual(self.writes(), [])

    def test_every_model_bucket_is_checked_without_guessing_slug(self):
        self.backend.payload["rateLimitsByLimitId"]["codex"]["normalModelSlug"] = None
        self.assertEqual(self.adapter.observe("live-test").bucket_ids, ("codex",))
        other = copy.deepcopy(self.backend.payload["rateLimitsByLimitId"]["codex"])
        other["limitId"] = "other-model"
        other["secondary"]["usedPercent"] = 100
        self.backend.payload["rateLimitsByLimitId"]["other-model"] = other
        request = self.request()
        with self.assertRaises(UnsafeError):
            self.adapter.submit(request)
        self.assertEqual(self.writes(), [])

    def test_account_change_between_reads_rejected(self):
        request = self.request()
        self.backend.payload["accountId"] = "different-account"
        with self.assertRaises(UnsafeError):
            self.adapter.submit(request)
        self.assertEqual(self.writes(), [])


if __name__ == "__main__":
    unittest.main()
