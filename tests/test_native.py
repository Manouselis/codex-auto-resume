import copy
import json
import tempfile
import unittest
from pathlib import Path

from auto_resume.adapters import fake_payload
from auto_resume.checkpoints import CHECKPOINT_MARKER
from auto_resume.domain import State
from auto_resume.engine import Engine
from auto_resume.live import LiveAdapter
from auto_resume.native import NativeController
from auto_resume.store import Store
from test_live import Backend


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = [1_800_000_000.0]
        self.clock = lambda: self.now[0]
        self.backend = Backend(self.tmp.name, self.clock)
        self.backend.latest.update(status="completed", completedAt=int(self.clock()), error=None,
            items=[{"type": "agentMessage", "phase": "final_answer", "text": "Saved checkpoint.\n" + CHECKPOINT_MARKER}])
        self.adapter = LiveAdapter(self.backend, self.clock)
        self.store = Store(Path(self.tmp.name) / "native.sqlite3")
        self.addCleanup(self.store.close)
        self.store.set_enabled(True, self.clock())
        self.engine = Engine(self.store, self.adapter, self.clock)
        self.engine.register("live-test", recover_context=True, native_heartbeat="native-test")
        self.native = NativeController(self.store, self.adapter, self.clock)

    def wake(self, turn_id="wake-one"):
        self.backend.history.insert(0, copy.deepcopy(self.backend.latest))
        self.backend.latest = {"id": turn_id, "status": "inProgress", "error": None, "completedAt": None,
                               "items": [{"type": "userMessage", "content": [{"type": "text",
                                   "text": "[codex-auto-resume:native-heartbeat=native-test]\nContinue the checkpoint."}]}]}
        self.backend.thread["status"] = {"type": "active", "activeFlags": []}

    def checkpoint(self):
        self.native.finish("live-test", "native-test", "checkpoint")
        self.backend.latest.update(status="completed", completedAt=int(self.clock()),
            items=[{"type": "agentMessage", "phase": "final_answer", "text": "Saved next step.\n" + CHECKPOINT_MARKER}])

    def claim(self):
        return self.native.claim("live-test", "native-test")

    def test_native_arming_never_uses_an_external_writer(self):
        self.engine.tick()
        self.assertEqual(self.store.get("live-test")["state"], State.ARMED)
        self.assertFalse(any(m in ("thread/resume", "turn/start", "thread/queue/add", "thread/queue/start")
                             for m, _ in self.backend.calls))

    def test_guard_only_admits_an_already_started_native_turn(self):
        self.assertEqual(self.claim()["action"], "wait")
        self.wake()
        self.assertEqual(self.claim()["action"], "continue")
        self.assertEqual(self.store.get("live-test")["ack_turn"], "wake-one")
        self.assertFalse(any(m in ("thread/resume", "turn/start") for m, _ in self.backend.calls))

    def test_native_reservation_is_idempotent_for_same_work_turn(self):
        self.wake()
        self.assertEqual(self.claim()["action"], "continue")
        self.assertEqual(self.claim()["action"], "continue")
        self.assertEqual(self.store.get("live-test")["attempts"], 1)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM submissions").fetchone()[0], 1)

    def test_repeated_claim_still_checks_fresh_allowance(self):
        self.wake()
        self.assertEqual(self.claim()["action"], "continue")
        self.backend.payload = fake_payload(self.clock(), five=5, weekly=100, ordinary=True)
        self.assertEqual(self.claim()["action"], "pause")
        self.assertFalse(self.store.get("live-test")["eligible"])

    def test_controller_restart_preserves_native_slot_for_terminal_history_check(self):
        self.wake()
        self.assertEqual(self.claim()["action"], "continue")
        self.store.recover(self.clock())
        self.assertEqual(self.store.get("live-test")["state"], State.RUNNING)
        self.backend.latest.update(status="failed", error={"codexErrorInfo": "usageLimitExceeded"},
                                   completedAt=int(self.clock()))
        self.wake("after-reset")
        self.assertEqual(self.claim()["action"], "continue")
        self.assertEqual(self.store.get("live-test")["attempts"], 2)

    def test_checkpoint_then_native_wake_preserves_original_identity(self):
        self.wake()
        self.claim()
        self.checkpoint()
        self.wake("wake-two")
        self.assertEqual(self.claim()["action"], "continue")
        self.assertEqual(self.store.get("live-test")["attempts"], 2)
        self.assertEqual(json.loads(self.store.get("live-test")["context"])["model"], "simulation-model")

    def test_ordinary_completion_does_not_admit_more_research(self):
        self.backend.latest["items"][-1]["text"] = "The objective is achieved."
        self.wake()
        self.assertEqual(self.claim()["action"], "pause")
        self.assertFalse(self.store.get("live-test")["eligible"])

    def test_confirmed_cancellation_does_not_admit_more_research(self):
        self.backend.latest.update(status="interrupted", error=None)
        self.wake()
        self.assertEqual(self.claim()["action"], "pause")

    def test_global_off_blocks_native_research(self):
        self.wake()
        self.store.set_enabled(False, self.clock())
        self.assertEqual(self.claim()["action"], "pause")
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM submissions").fetchone()[0], 0)

    def test_native_heartbeat_identity_is_pinned(self):
        self.wake()
        self.assertEqual(self.native.claim("live-test", "other-heartbeat")["action"], "pause")

    def test_exhausted_usage_waits_without_claiming_work(self):
        self.wake()
        self.backend.payload = fake_payload(self.clock())
        self.assertEqual(self.claim()["action"], "wait")
        self.assertEqual(self.store.get("live-test")["attempts"], 0)

    def test_weekly_exhaustion_is_a_sticky_native_stop(self):
        self.wake()
        self.backend.payload = fake_payload(self.clock(), five=5, weekly=100, ordinary=True)
        self.assertEqual(self.claim()["action"], "pause")
        self.assertEqual(self.store.get("live-test")["state"], State.WEEKLY_LIMIT_REACHED)

    def test_native_goal_budget_guard(self):
        self.wake()
        self.backend.goal = {"status": "active", "tokenBudget": 20, "tokensUsed": 20}
        self.assertEqual(self.claim()["action"], "pause")

    def test_native_paid_balance_blocks_substantive_work(self):
        self.wake()
        self.backend.payload["rateLimitsByLimitId"]["codex"]["credits"] = {
            "hasCredits": True, "unlimited": False, "balance": "20"}
        result = self.claim()
        self.assertEqual(result["action"], "pause")
        self.assertIn("paid credits", result["reason"])

    def test_unrelated_uncertain_submission_blocks_native_work(self):
        self.wake()
        self.store.db.execute("INSERT INTO submissions VALUES(?,?,?,?,?)", ("unknown", "other", "uncertain", None, self.clock()))
        self.assertEqual(self.claim()["action"], "wait")
        self.assertEqual(self.store.get("live-test")["attempts"], 0)

    def test_native_work_turn_cap_is_enforced(self):
        task = self.store.get("live-test")
        context = json.loads(task["context"])
        context["native_max_attempts"] = 1
        self.store.db.execute("UPDATE tasks SET context=? WHERE thread_id=?", (json.dumps(context), "live-test"))
        self.wake()
        self.claim()
        self.checkpoint()
        self.wake("wake-two")
        self.assertEqual(self.claim()["action"], "pause")
        self.assertEqual(self.store.get("live-test")["attempts"], 1)

    def test_native_objective_completion_disarms_and_finishes_reservation(self):
        self.wake()
        self.claim()
        self.native.finish("live-test", "native-test", "complete")
        self.assertEqual(self.store.get("live-test")["state"], State.COMPLETED)
        self.assertFalse(self.store.get("live-test")["eligible"])
        self.assertEqual(self.store.db.execute("SELECT status FROM submissions").fetchone()[0], "finished")

    def test_manual_intervening_turn_is_not_mistaken_for_a_native_wake(self):
        self.wake("manual-user-turn")
        self.backend.latest.update(status="completed", completedAt=int(self.clock()),
                                   items=[{"type": "userMessage", "content": [{"type": "text", "text": "Do different work"}]}])
        self.wake("actual-heartbeat")
        self.assertEqual(self.claim()["action"], "pause")
