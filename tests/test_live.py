import copy
import queue
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path

from auto_resume.adapters import fake_payload
from auto_resume.domain import State, TransientError, UnsafeError, WriterConflictError
from auto_resume.engine import Engine
from auto_resume.live import LiveAdapter, manual_request
from auto_resume.store import Store
from auto_resume.checkpoints import CHECKPOINT_MARKER, COMPLETE_MARKER


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
        self.goal = None
        self.history = []
        self.writer_elsewhere = False
        self.queued = []
        self.queue_add_lost_ack = False
        self.queue_start_error = False
        self.after_queue_add = None
        self.queue_auto_start = False

    def call(self, method, params=None):
        params = params or {}
        self.calls.append((method, copy.deepcopy(params)))
        if method == "account/read":
            return {"account": self.account}
        if method == "account/rateLimits/read":
            return self.payload
        if method == "config/read":
            return {"config": self.config}
        if method == "thread/goal/get":
            return {"goal": self.goal}
        if method == "thread/read":
            return {"thread": copy.deepcopy(self.thread)}
        if method == "thread/turns/list":
            return {"data": copy.deepcopy([self.latest, *self.history][:params.get("limit", 100)]), "nextCursor": None}
        if method == "thread/items/list":
            selected = next(t for t in [self.latest, *self.history] if t["id"] == params["turnId"])
            return {"data": [{"turnId": selected["id"], "item": copy.deepcopy(item)}
                             for item in reversed(selected.get("items", []))], "nextCursor": None}
        if method == "thread/resume":
            if self.writer_elsewhere:
                raise WriterConflictError("The original desktop owns the conversation writer")
            self.thread["status"] = {"type": "idle"}
            if self.after_resume:
                self.after_resume()
            return {"model": self.thread["model"], "modelProvider": "openai", "cwd": self.thread["cwd"],
                    "sandbox": {"type": "readOnly"}, "approvalPolicy": "on-request", "serviceTier": "default"}
        if method == "turn/start":
            self.latest = {"id": "real-protocol-next-turn", "status": "inProgress", "error": None, "items": []}
            self.thread["status"] = {"type": "active", "activeFlags": []}
            return {"turn": self.latest}
        if method == "thread/queue/list":
            return {"data": copy.deepcopy(self.queued), "nextCursor": None}
        if method == "thread/queue/add":
            entry = {"id": "queued-submission", "clientUserMessageId": params["clientUserMessageId"],
                     "input": params["input"]}
            self.queued.append(entry)
            if self.after_queue_add:
                self.after_queue_add()
            if self.queue_add_lost_ack:
                raise TransientError("Queue acknowledgement lost")
            if self.queue_auto_start:
                self.history.insert(0, copy.deepcopy(self.latest))
                self.latest = {"id": "native-queued-" + str(sum(m == 'thread/queue/add' for m, _ in self.calls)),
                    "status": "inProgress", "error": None, "completedAt": None,
                    "items": [{"type": "userMessage", "clientId": params["clientUserMessageId"], "content": params["input"]}]}
                self.thread["status"] = {"type": "active", "activeFlags": []}
                self.queued.remove(entry)
            return {"queuedSubmission": copy.deepcopy(entry)}
        if method == "thread/queue/start":
            if self.queue_start_error:
                raise TransientError("Start acknowledgement lost")
            entry = self.queued.pop(0)
            self.latest = {"id": "queued-native-next-turn", "status": "inProgress", "error": None,
                           "items": [{"type": "userMessage", "id": entry["clientUserMessageId"]}]}
            return {"turn": self.latest}
        if method == "thread/queue/delete":
            old = len(self.queued)
            self.queued = [item for item in self.queued if item["id"] != params["queuedSubmissionId"]]
            return {"deleted": len(self.queued) != old}
        raise AssertionError(method)

    def close(self):
        pass


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # Cleanups run in reverse registration order, after tearDown. Close any
        # SQLite handles registered below before removing their directory.
        self.addCleanup(self.tmp.cleanup)
        self.clock_value = [1_800_000_000.0]
        self.clock = lambda: self.clock_value[0]
        self.backend = Backend(self.tmp.name, self.clock)
        self.adapter = LiveAdapter(self.backend, self.clock)
        self.adapter.check_enabled = lambda: True

    def request(self):
        return manual_request(self.adapter.observe("live-test"), "Continue only unfinished work")

    def writes(self):
        return [p for method, p in self.backend.calls if method == "turn/start"]

    def external_open_turn(self, status="interrupted"):
        self.backend.latest.update(status=status, completedAt=None, error=None)
        self.backend.thread["status"] = {"type": "notLoaded"}

    def armed_store(self, *, recover_context=False):
        store = Store(Path(self.tmp.name) / "external.sqlite3")
        self.addCleanup(store.close)
        store.set_enabled(True, self.clock())
        engine = Engine(store, self.adapter, self.clock)
        engine.register("live-test", recover_context=recover_context)
        return store, engine

    def test_external_open_history_is_unresolved_not_user_cancellation(self):
        for status in ("interrupted", "inProgress"):
            with self.subTest(status=status):
                self.external_open_turn(status)
                obs = self.adapter.observe("live-test")
                self.assertEqual(obs.turn_status, "unresolved")
                self.assertTrue(obs.external_unresolved)
                self.assertFalse(obs.cancelled)
                self.assertIsNone(obs.incomplete)

    def test_external_open_history_can_be_armed_without_execution(self):
        self.external_open_turn()
        store, engine = self.armed_store()
        for _ in range(3):
            engine.tick()
            self.clock_value[0] += 31
        task = store.get("live-test")
        self.assertEqual(task["state"], State.ARMED)
        self.assertTrue(task["eligible"])
        self.assertIn("confirmed turn result", task["reason"])
        self.assertFalse(any(m in ("thread/resume", "turn/start") for m, _ in self.backend.calls))

    def test_external_open_history_refuses_automatic_and_manual_dispatch(self):
        self.external_open_turn()
        request = self.request()
        for automatic in (True, False):
            with self.subTest(automatic=automatic):
                with self.assertRaisesRegex(UnsafeError, "no confirmed result"):
                    self.adapter._dispatch(request, automatic=automatic)
        self.assertFalse(any(m in ("thread/resume", "turn/start") for m, _ in self.backend.calls))

    def test_external_turn_later_fails_then_reset_continues_once(self):
        self.external_open_turn()
        store, engine = self.armed_store()
        engine.tick()
        self.clock_value[0] += 31
        self.backend.latest.update(status="failed", completedAt=int(self.clock()),
                                   error={"codexErrorInfo": "usageLimitExceeded"})
        self.backend.payload = fake_payload(self.clock())
        engine.tick()
        self.assertEqual(store.get("live-test")["state"], State.WAITING_FOR_RESET)
        self.assertEqual(self.writes(), [])
        self.clock_value[0] += 26
        self.backend.payload = fake_payload(self.clock(), five=5, ordinary=True)
        engine.tick()
        engine.tick()
        self.assertEqual(store.get("live-test")["state"], State.RUNNING)
        self.assertEqual(len(self.writes()), 1)

    def test_external_turn_later_completes_without_continuation(self):
        self.external_open_turn()
        store, engine = self.armed_store()
        self.backend.latest.update(status="completed", completedAt=int(self.clock()))
        engine.tick()
        self.assertEqual(store.get("live-test")["state"], State.COMPLETED)
        self.assertEqual(self.writes(), [])

    def test_confirmed_external_cancellation_still_rejects_arming(self):
        self.external_open_turn()
        self.backend.latest["completedAt"] = int(self.clock())
        self.assertTrue(self.adapter.observe("live-test").cancelled)
        with self.assertRaisesRegex(UnsafeError, "cancelled"):
            self.armed_store()
        self.assertEqual(self.writes(), [])

    def test_loaded_runtime_interruption_still_rejects_arming(self):
        self.external_open_turn()
        self.backend.thread["status"] = {"type": "idle"}
        self.assertTrue(self.adapter.observe("live-test").cancelled)
        with self.assertRaisesRegex(UnsafeError, "cancelled"):
            self.armed_store()

    def test_external_turn_later_cancelled_disarms(self):
        self.external_open_turn()
        store, engine = self.armed_store()
        self.backend.latest["completedAt"] = int(self.clock())
        engine.tick()
        self.assertEqual(store.get("live-test")["state"], State.PAUSED_FOR_USER)
        self.assertFalse(store.get("live-test")["eligible"])
        self.assertEqual(self.writes(), [])

    def test_external_turn_superseded_disarms(self):
        self.external_open_turn()
        store, engine = self.armed_store()
        self.backend.latest["id"] = "different-turn"
        engine.tick()
        self.assertEqual(store.get("live-test")["state"], State.PAUSED_FOR_USER)
        self.assertFalse(store.get("live-test")["eligible"])
        self.assertEqual(self.writes(), [])

    def test_unresolved_history_cannot_replace_confirmed_limit_failure(self):
        self.backend.payload = fake_payload(self.clock())
        store, engine = self.armed_store()
        engine.tick()
        self.assertEqual(store.get("live-test")["state"], State.WAITING_FOR_RESET)
        self.clock_value[0] += 26
        self.external_open_turn()
        engine.tick()
        self.assertEqual(store.get("live-test")["state"], State.PAUSED_FOR_USER)
        self.assertEqual(self.writes(), [])

    def test_unknown_history_is_not_accepted_as_external_open_turn(self):
        self.external_open_turn(status="unknown")
        self.assertFalse(self.adapter.observe("live-test").external_unresolved)
        with self.assertRaises(UnsafeError):
            self.armed_store()

    def test_external_open_history_with_pending_approval_still_rejected(self):
        self.external_open_turn()
        self.backend.events.put({"id": 42, "method": "item/permissions/requestApproval",
                                 "params": {"threadId": "live-test"}})
        with self.assertRaisesRegex(UnsafeError, "approval"):
            self.armed_store()

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

    def context_stop(self, *, text=None):
        self.backend.latest.update(status="completed", completedAt=int(self.clock()), error=None,
                                   items=[{"type": "agentMessage", "phase": "final_answer",
                                           "text": text if text is not None else "Checkpoint saved.\n" + CHECKPOINT_MARKER}])

    def test_context_recovery_requires_per_arming_opt_in(self):
        self.context_stop()
        with self.assertRaises(UnsafeError):
            self.armed_store()
        self.assertEqual(self.writes(), [])

    def test_context_checkpoint_continues_immediately_with_fresh_allowance_once(self):
        self.context_stop()
        store, engine = self.armed_store(recover_context=True)
        engine.tick()
        engine.tick()
        self.assertEqual(store.get("live-test")["state"], State.RUNNING)
        self.assertEqual(len(self.writes()), 1)
        self.assertIn(CHECKPOINT_MARKER, self.writes()[0]["input"][0]["text"])

    def test_context_stop_waits_for_quota_reset_without_losing_opt_in(self):
        self.context_stop()
        self.backend.payload = fake_payload(self.clock())
        store, engine = self.armed_store(recover_context=True)
        engine.tick()
        self.assertEqual(store.get("live-test")["state"], State.WAITING_FOR_RESET)
        self.assertEqual(self.writes(), [])
        self.clock_value[0] += 26
        self.backend.payload = fake_payload(self.clock(), five=5, ordinary=True)
        engine.tick()
        self.assertEqual(len(self.writes()), 1)

    def test_quota_failure_preserves_context_recovery_for_next_turn(self):
        self.backend.payload = fake_payload(self.clock())
        store, engine = self.armed_store(recover_context=True)
        engine.tick()
        self.clock_value[0] += 26
        self.backend.payload = fake_payload(self.clock(), five=5, ordinary=True)
        engine.tick()
        self.assertEqual(len(self.writes()), 1)
        self.clock_value[0] += 31
        self.context_stop()
        engine.tick()
        self.assertEqual(len(self.writes()), 2)

    def test_context_recovery_does_not_restart_ordinary_completion(self):
        self.backend.latest.update(status="inProgress", completedAt=None, error=None)
        self.backend.thread["status"] = {"type": "active", "activeFlags": []}
        store, engine = self.armed_store(recover_context=True)
        self.context_stop(text="The objective is achieved.\n" + COMPLETE_MARKER)
        engine.tick()
        self.assertEqual(store.get("live-test")["state"], State.COMPLETED)
        self.assertEqual(self.writes(), [])

    def test_context_recovery_weekly_exhaustion_stays_disarmed_after_reset(self):
        self.context_stop()
        self.backend.payload = fake_payload(self.clock(), five=5, weekly=100, ordinary=True)
        store, engine = self.armed_store(recover_context=True)
        engine.tick()
        self.assertEqual(store.get("live-test")["state"], State.WEEKLY_LIMIT_REACHED)
        self.clock_value[0] += 31
        self.backend.payload = fake_payload(self.clock(), five=5, weekly=5, ordinary=True)
        engine.tick()
        self.assertEqual(self.writes(), [])

    def test_context_recovery_keeps_paid_credit_and_permission_guards(self):
        self.context_stop()
        request = replace(self.request(), trigger="context_budget")
        for mutate in (
            lambda: self.backend.payload.update(ordinaryUsageAllowed=False),
            lambda: self.backend.payload["rateLimitsByLimitId"]["codex"].update(
                credits={"hasCredits": True, "unlimited": False, "balance": "10"}),
        ):
            self.backend.payload = fake_payload(self.clock(), five=5, ordinary=True)
            mutate()
            with self.assertRaises(UnsafeError):
                self.adapter.submit(request)
        self.assertEqual(self.writes(), [])

    def test_context_checkpoint_change_after_resume_never_submits(self):
        self.context_stop()
        request = replace(self.request(), trigger="context_budget")
        self.backend.after_resume = lambda: self.context_stop(text="Different checkpoint.\n" + CHECKPOINT_MARKER)
        with self.assertRaises(UnsafeError):
            self.adapter.submit(request)
        self.assertEqual(self.writes(), [])

    def test_context_recovery_respects_goal_pause_and_goal_budget(self):
        self.context_stop()
        for goal in ({"status": "paused"}, {"status": "budgetLimited"},
                     {"status": "active", "tokenBudget": 100, "tokensUsed": 100}):
            with self.subTest(goal=goal):
                self.backend.goal = goal
                with self.assertRaises(UnsafeError):
                    self.adapter.submit(replace(self.request(), trigger="context_budget"))
        self.assertEqual(self.writes(), [])

    def test_context_recovery_is_bounded_and_finishes_prior_reservations(self):
        self.context_stop()
        store, engine = self.armed_store(recover_context=True)
        for _ in range(4):
            engine.tick()
            self.clock_value[0] += 31
            self.context_stop()
        self.assertEqual(len(self.writes()), 3)
        self.assertEqual(store.get("live-test")["state"], State.PAUSED_FOR_USER)
        self.assertIn("Maximum", store.get("live-test")["reason"])

    def test_completed_checkpoint_can_be_explicitly_rearmed_with_new_mode(self):
        self.backend.latest.update(status="inProgress", completedAt=None, error=None)
        self.backend.thread["status"] = {"type": "active", "activeFlags": []}
        store, engine = self.armed_store()
        self.context_stop()
        engine.tick()
        self.assertEqual(store.get("live-test")["state"], State.COMPLETED)
        engine.register("live-test", recover_context=True)
        engine.tick()
        self.assertEqual(len(self.writes()), 1)

    def test_structured_context_window_failure_can_recover_with_opt_in(self):
        self.backend.latest["error"] = {"codexErrorInfo": "contextWindowExceeded"}
        store, engine = self.armed_store(recover_context=True)
        engine.tick()
        self.assertEqual(len(self.writes()), 1)

    def test_unknown_dispatch_trigger_is_refused(self):
        with self.assertRaises(UnsafeError):
            self.adapter.submit(replace(self.request(), trigger="anything"))
        self.assertEqual(self.writes(), [])






    def test_confirmed_preflight_refusal_is_not_an_uncertain_submission(self):
        self.context_stop()
        store, engine = self.armed_store(recover_context=True)
        self.backend.after_resume = lambda: self.backend.latest.update(id="superseding-turn")
        engine.tick()
        self.assertEqual(store.db.execute("SELECT status FROM submissions").fetchone()[0], "not_sent")
        self.assertEqual(self.writes(), [])




if __name__ == "__main__":
    unittest.main()
