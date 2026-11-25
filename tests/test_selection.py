import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def arm_ahead(self):
        self.engine.register("live-test", wait_for_limit=True, desktop_queue=True)
        return self.engine.start_selected("live-test")

    def hit_limit_after_arming(self):
        self.now[0] += 31
        self.backend.latest.update(id="later-limited-turn", status="failed",
                                   error={"codexErrorInfo": "usageLimitExceeded"}, completedAt=int(self.clock()))
        self.backend.payload = fake_payload(self.clock())
        self.engine.tick()
        return self.store.get("live-test")

    def test_custom_message_survives_reset_wait_and_is_only_sent_to_selected_chat(self):
        self.arm_ahead()
        message = "Finish the current checks.\nRecord the results in the existing report."
        waiting = self.hit_limit_after_arming()
        self.store.set_recovery_message("live-test", message, self.clock())
        self.assertEqual(self.store.get("live-test")["next_check"], waiting["next_check"])
        self.assertEqual(self.store.recovery_message("other-chat"), "")
        self.assertFalse(self.queued())
        self.assertFalse(any(message in row["reason"] for row in self.store.history()))
        reopened = Store(self.store.path)
        try:
            self.assertEqual(reopened.recovery_message("live-test"), message)
        finally:
            reopened.close()

        self.now[0] = waiting["next_check"]
        self.backend.payload = fake_payload(self.clock(), five=5, ordinary=True)
        self.engine.tick()
        self.assertEqual(len(self.queued()), 1)
        self.assertEqual(self.queued()[0]["threadId"], "live-test")
        self.assertEqual(self.queued()[0]["input"], [{"type": "text", "text": message}])
        with self.assertRaisesRegex(ValueError, "outstanding"):
            self.store.set_recovery_message("live-test", "Another message", self.clock())

    def test_empty_message_restores_default_and_overlong_message_is_rejected(self):
        from auto_resume.domain import DEFAULT_RECOVERY_MESSAGE

        self.arm_ahead()
        self.store.set_recovery_message("live-test", "Finish the report", self.clock())
        with self.assertRaisesRegex(ValueError, "4,000"):
            self.store.set_recovery_message("live-test", "x" * 4001, self.clock())
        self.store.set_recovery_message("live-test", " \n ", self.clock())
        waiting = self.hit_limit_after_arming()
        self.now[0] = waiting["next_check"]
        self.backend.payload = fake_payload(self.clock(), five=5, ordinary=True)
        self.engine.tick()
        self.assertEqual(self.queued()[0]["input"][0]["text"], DEFAULT_RECOVERY_MESSAGE)

    def test_idle_prearm_follows_manual_turns_and_resumes_once_after_limit(self):
        self.assertEqual(self.arm_ahead()["state"], State.ARMED)
        self.assertFalse(self.queued())
        self.now[0] += 31
        self.backend.latest.update(id="manual-turn", status="inProgress", completedAt=None)
        self.backend.thread["status"] = {"type": "active", "activeFlags": []}
        self.engine.tick()
        self.assertEqual(self.store.get("live-test")["state"], State.ARMED)

        self.now[0] += 31
        self.backend.latest.update(status="completed", completedAt=int(self.clock()))
        self.backend.thread["status"] = {"type": "idle"}
        self.backend.payload = fake_payload(self.clock())
        self.engine.tick()
        self.assertEqual(self.store.get("live-test")["state"], State.ARMED)
        self.assertFalse(self.queued())

        task = self.hit_limit_after_arming()
        self.assertEqual(task["state"], State.WAITING_FOR_RESET)
        context = json.loads(task["context"])
        self.assertEqual(context["turn_id"], "later-limited-turn")
        self.assertFalse(context.get("wait_for_limit"))
        self.assertFalse(self.queued())

        self.now[0] = task["next_check"]
        self.backend.payload = fake_payload(self.clock(), five=5, ordinary=True)
        self.engine.tick()
        self.assertEqual(self.store.get("live-test")["state"], State.RUNNING)
        self.assertEqual(len(self.queued()), 1)
        self.assertFalse(any(m in ("thread/resume", "turn/start") for m, _ in self.backend.calls))
        self.now[0] += 31
        self.backend.latest.update(status="completed", completedAt=int(self.clock()))
        self.engine.tick()
        self.assertEqual(self.store.get("live-test")["state"], State.COMPLETED)
        self.assertEqual(len(self.queued()), 1)

    def test_running_prearm_stops_if_user_cancels(self):
        self.backend.latest.update(status="inProgress", completedAt=None)
        self.backend.thread["status"] = {"type": "active", "activeFlags": []}
        self.assertEqual(self.arm_ahead()["state"], State.ARMED)
        self.now[0] += 31
        self.backend.latest.update(status="interrupted", completedAt=int(self.clock()))
        self.engine.tick()
        self.assertFalse(self.store.get("live-test")["eligible"])
        self.assertFalse(self.queued())

    def test_prearm_will_not_pick_up_a_failure_from_before_arming(self):
        self.arm_ahead()
        armed_at = self.clock()
        self.now[0] += 31
        self.backend.latest.update(id="older-failure", status="failed",
                                   error={"codexErrorInfo": "usageLimitExceeded"}, completedAt=int(armed_at) - 1)
        self.backend.payload = fake_payload(self.clock())
        self.engine.tick()
        self.assertEqual(self.store.get("live-test")["state"], State.PAUSED_FOR_USER)
        self.assertFalse(self.queued())

    def test_manual_activity_after_prearmed_failure_stops_later_recovery(self):
        self.arm_ahead()
        waiting = self.hit_limit_after_arming()
        self.now[0] = waiting["next_check"]
        self.backend.payload = fake_payload(self.clock(), five=5, ordinary=True)
        self.backend.latest.update(id="newer-manual-turn", status="completed", error=None,
                                   completedAt=int(self.clock()))
        self.engine.tick()
        self.assertEqual(self.store.get("live-test")["state"], State.PAUSED_FOR_USER)
        self.assertFalse(self.queued())

    def test_prearmed_failure_still_requires_included_usage_after_reset(self):
        self.arm_ahead()
        waiting = self.hit_limit_after_arming()
        self.now[0] = waiting["next_check"]
        self.backend.payload = fake_payload(self.clock(), five=5, weekly=100, ordinary=True)
        self.engine.tick()
        self.assertEqual(self.store.get("live-test")["state"], State.WEEKLY_LIMIT_REACHED)
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

    def usage_limited_goal(self, **changes):
        self.backend.goal = {"status": "usageLimited", "tokenBudget": 100, "tokensUsed": 10,
                             "objective": "Finish the test task", "createdAt": 1, **changes}
        self.backend.latest.update(status="failed", error={"codexErrorInfo": "usageLimitExceeded"})

    def test_usage_limited_goal_waits_for_reset_then_restarts_once_through_desktop(self):
        self.usage_limited_goal()
        self.backend.payload = fake_payload(self.clock())
        task = self.start()
        self.assertEqual(task["state"], State.WAITING_FOR_GOAL)
        self.assertTrue(task["eligible"])
        self.assertIn("wait for included usage", task["reason"])
        self.assertFalse(self.queued())

        self.now[0] = task["next_check"]
        self.backend.payload = fake_payload(self.clock(), five=5, ordinary=True)
        with patch("auto_resume.live.wake_queued_conversation") as wake:
            self.engine.tick()
        wake.assert_called_once_with("live-test")
        task = self.store.get("live-test")
        self.assertTrue(task["eligible"])
        self.assertEqual(task["state"], State.RUNNING)
        self.assertEqual(task["ack_turn"], "native-queued-1")
        self.assertEqual(self.backend.goal["status"], "active")
        self.assertEqual([p for m, p in self.backend.calls if m == "thread/goal/set"],
                         [{"threadId": "live-test", "status": "active", "origin": "automatic"}])
        self.assertEqual(len(self.queued()), 1)
        self.assertFalse(any(m in ("thread/resume", "turn/start") for m, _ in self.backend.calls))
        self.engine.tick()
        self.assertEqual(len(self.queued()), 1)

    def test_usage_limited_goal_with_existing_queue_does_not_reactivate(self):
        self.usage_limited_goal()
        self.backend.queued.append({"id": "manual"})
        self.assertFalse(self.start()["eligible"])
        self.assertEqual(self.backend.goal["status"], "usageLimited")
        self.assertFalse(self.queued())

    def test_goal_wake_lost_acknowledgement_never_retries(self):
        self.usage_limited_goal()
        self.backend.queue_add_lost_ack = True
        with patch("auto_resume.live.wake_queued_conversation") as wake:
            self.assertFalse(self.start()["eligible"])
            self.engine.tick()
        wake.assert_not_called()
        self.assertEqual(len(self.queued()), 1)
        self.assertEqual(self.store.db.execute("SELECT status FROM submissions").fetchone()[0], "uncertain")

    def test_goal_paused_during_recovery_is_never_reactivated(self):
        self.usage_limited_goal()
        change = self.engine._change

        def pause_on_dispatch(thread_id, state, reason, **values):
            if reason == "Reactivating the usage-limited goal":
                self.backend.goal["status"] = "paused"
            return change(thread_id, state, reason, **values)

        with patch.object(self.engine, "_change", side_effect=pause_on_dispatch):
            task = self.start()
        self.assertFalse(task["eligible"])
        self.assertEqual(self.backend.goal["status"], "paused")
        self.assertFalse(any(m == "thread/goal/set" for m, _ in self.backend.calls))
        self.assertFalse(self.queued())

    def test_usage_limited_goal_with_exhausted_budget_cannot_arm(self):
        self.usage_limited_goal(tokensUsed=100)
        self.assertFalse(self.start()["eligible"])
        self.assertFalse(self.queued())

    def test_replaced_goal_does_not_inherit_arming(self):
        self.usage_limited_goal()
        self.backend.payload = fake_payload(self.clock())
        task = self.start()
        self.now[0] = task["next_check"]
        self.backend.goal.update(status="active", objective="Different task")
        self.backend.latest.update(id="different-turn", status="inProgress", error=None, completedAt=None)
        self.engine.tick()
        self.assertFalse(self.store.get("live-test")["eligible"])
        self.assertFalse(self.queued())

    def test_usage_limited_goal_does_not_override_weekly_exhaustion(self):
        self.usage_limited_goal()
        self.backend.payload = fake_payload(self.clock(), five=5, weekly=100, ordinary=True)
        task = self.start()
        self.assertEqual(task["state"], State.WEEKLY_LIMIT_REACHED)
        self.assertFalse(task["eligible"])
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
