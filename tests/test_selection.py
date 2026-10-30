import json
import tempfile
import unittest
from pathlib import Path

from auto_resume.adapters import fake_payload
from auto_resume.domain import State, UnsafeError
from auto_resume.engine import Engine
from auto_resume.live import LiveAdapter
from auto_resume.store import Store
from test_live import Backend


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = [1_800_000_000.0]
        self.clock = lambda: self.now[0]
        self.backend = Backend(self.tmp.name, self.clock)
        self.backend.latest.update(status="completed", error=None, completedAt=int(self.clock()), items=[])
        self.backend.thread["status"] = {"type": "idle"}
        self.backend.queue_auto_start = True
        self.adapter = LiveAdapter(self.backend, self.clock)
        self.store = Store(Path(self.tmp.name) / "state.sqlite3")
        self.addCleanup(self.store.close)
        self.engine = Engine(self.store, self.adapter, self.clock)

    def select(self):
        return self.engine.register("live-test", start_idle=True, desktop_queue=True)

    def queued(self):
        return [p for m, p in self.backend.calls if m == "thread/queue/add"]

    def start(self):
        self.select()
        return self.engine.start_selected("live-test")

    def test_idle_selection_sends_literal_continue_through_original_writer(self):
        task = self.start()
        self.assertEqual(task["state"], State.RUNNING)
        self.assertEqual(len(self.queued()), 1)
        self.assertEqual(self.queued()[0]["input"], [{"type": "text", "text": "continue"}])
        self.assertEqual(self.queued()[0]["clientUserMessageId"], task["continuation_id"])
        self.assertFalse(any(m in ("thread/resume", "turn/start") for m, _ in self.backend.calls))

    def test_normal_arming_still_cannot_automatically_restart_completion(self):
        with self.assertRaises(UnsafeError):
            self.engine.register("live-test")
        self.assertFalse(self.queued())

    def test_running_selection_only_monitors_existing_work(self):
        self.backend.latest.update(status="inProgress", completedAt=None)
        self.backend.thread["status"] = {"type": "active", "activeFlags": []}
        self.assertEqual(self.start()["state"], State.RUNNING)
        self.assertFalse(self.queued())

    def test_repeated_selection_before_dispatch_reserves_only_one_continue(self):
        self.select()
        self.select()
        self.engine.start_selected("live-test")
        self.engine.start_selected("live-test")
        self.assertEqual(len(self.queued()), 1)

    def test_selecting_an_already_started_chat_does_not_queue_again(self):
        self.start()
        self.select()
        self.engine.start_selected("live-test")
        self.assertEqual(len(self.queued()), 1)

    def test_completion_after_the_explicit_continue_stops_automation(self):
        self.start()
        self.backend.latest.update(status="completed", completedAt=int(self.clock()))
        self.now[0] += 31
        self.engine.tick()
        self.assertEqual(self.store.get("live-test")["state"], State.COMPLETED)
        self.assertFalse(self.store.get("live-test")["eligible"])
        self.now[0] += 301
        self.engine.tick()
        self.assertEqual(len(self.queued()), 1)

    def test_idle_selection_waits_for_usage_then_sends_once(self):
        self.backend.payload = fake_payload(self.clock())
        self.assertEqual(self.start()["state"], State.WAITING_FOR_RESET)
        self.assertFalse(self.queued())
        self.now[0] += 26
        self.backend.payload = fake_payload(self.clock(), five=5, ordinary=True)
        self.engine.tick()
        self.assertEqual(len(self.queued()), 1)

    def test_weekly_exhaustion_blocks_idle_start(self):
        self.backend.payload = fake_payload(self.clock(), five=5, weekly=100, ordinary=True)
        self.assertFalse(self.start()["eligible"])
        self.assertFalse(self.queued())

    def test_goal_stop_is_not_overridden_by_selection(self):
        self.backend.goal = {"status": "paused", "tokenBudget": 100, "tokensUsed": 10}
        self.assertFalse(self.start()["eligible"])
        self.assertFalse(self.queued())

    def test_pending_approval_never_receives_continue(self):
        self.backend.thread["status"] = {"type": "active", "activeFlags": ["waitingOnApproval"]}
        with self.assertRaises(UnsafeError):
            self.select()
        self.assertFalse(self.queued())

    def test_unknown_same_chat_submission_blocks_selection(self):
        self.store.db.execute("INSERT INTO submissions VALUES('unknown','live-test','uncertain',NULL,1)")
        with self.assertRaisesRegex(ValueError, "outstanding or uncertain"):
            self.select()
        self.assertFalse(self.queued())

    def test_lost_queue_acknowledgement_never_retries(self):
        self.backend.queue_add_lost_ack = True
        self.assertFalse(self.start()["eligible"])
        self.engine.tick()
        with self.assertRaisesRegex(ValueError, "outstanding or uncertain"):
            self.select()
        self.assertEqual(len(self.queued()), 1)
        self.assertEqual(self.store.db.execute("SELECT status FROM submissions").fetchone()[0], "uncertain")

    def test_existing_user_queue_is_not_overwritten(self):
        self.backend.queued.append({"id": "manual", "clientUserMessageId": "manual", "input": []})
        self.assertFalse(self.start()["eligible"])
        self.assertFalse(self.queued())
        self.assertEqual(self.backend.queued[0]["id"], "manual")

    def test_new_user_activity_after_selection_prevents_a_late_continue(self):
        self.select()
        self.backend.latest["id"] = "new-user-turn"
        self.engine.start_selected("live-test")
        self.assertFalse(self.queued())

    def test_later_quota_recovery_keeps_the_native_queue_transport(self):
        self.start()
        self.backend.latest.update(status="failed", error={"codexErrorInfo": "usageLimitExceeded"}, completedAt=int(self.clock()))
        self.now[0] += 31
        self.backend.payload = fake_payload(self.clock())
        self.engine.tick()
        task = self.store.get("live-test")
        self.assertEqual(task["state"], State.WAITING_FOR_RESET)
        self.assertTrue(json.loads(task["context"])["desktop_queue"])
        self.assertFalse(json.loads(task["context"]).get("user_start_pending"))
        self.now[0] += 26
        self.backend.payload = fake_payload(self.clock(), five=5, ordinary=True)
        self.engine.tick()
        self.assertEqual(len(self.queued()), 2)
        self.assertFalse(any(m == "thread/resume" for m, _ in self.backend.calls))
