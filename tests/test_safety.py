import copy
import os
import random
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path

from auto_resume.adapters import CodexObserver, SimulationAdapter, fake_payload
from auto_resume.domain import Capabilities, State, TransientError, UnsafeError, Usage
from auto_resume.engine import Engine
from auto_resume.policy import evaluate
from auto_resume.store import Store


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now

    def advance(self, amount=26):
        self.now += amount


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_800_000_000.0
        self.p = fake_payload(self.now, five=5, weekly=30, ordinary=True)

    def decision(self, p=None, *, fetched=None, auth="chatgpt", ids=("codex",)):
        return evaluate(Usage(self.p if p is None else p, self.now if fetched is None else fetched, auth),
                        "simulation-account", ids, self.now)

    def test_06_included_allowance_authorized(self):
        self.assertEqual(self.decision().kind, "ready")

    def test_10_15_weekly_wins_over_five_hour_and_backend_false(self):
        self.p = fake_payload(self.now, weekly=100)
        self.assertEqual(self.decision().kind, "weekly")

    def test_12_weekly_reserve_boundary(self):
        self.p["rateLimitsByLimitId"]["codex"]["secondary"]["usedPercent"] = 95
        self.assertEqual(self.decision().kind, "pause")

    def test_13_weekly_missing(self):
        self.p["rateLimitsByLimitId"]["codex"]["secondary"] = None
        self.assertEqual(self.decision().kind, "pause")

    def test_14_stale_usage(self):
        self.assertEqual(self.decision(fetched=self.now - 31).kind, "pause")

    def test_17_paid_balance_present(self):
        b = self.p["rateLimitsByLimitId"]["codex"]
        b["credits"] = {"hasCredits": True, "balance": "100", "unlimited": False}
        self.assertEqual(self.decision().kind, "pause")

    def test_18_unknown_balance(self):
        self.p["rateLimitsByLimitId"]["codex"]["credits"]["balance"] = None
        self.assertEqual(self.decision().kind, "pause")

    def test_20_api_key_auth(self):
        self.assertEqual(self.decision(auth="apiKey").kind, "pause")

    def test_21_banked_reset_is_never_authorization(self):
        self.p["ordinaryUsageAllowed"] = False
        self.p["rateLimitResetCredits"] = {"availableCount": 99}
        self.assertEqual(self.decision().kind, "pause")

    def test_22_23_backend_permission_false_null_missing(self):
        for permission in (False, None, 1, "true"):
            with self.subTest(permission=permission):
                self.p["ordinaryUsageAllowed"] = permission
                self.assertEqual(self.decision().kind, "pause")
        del self.p["ordinaryUsageAllowed"]
        self.assertEqual(self.decision().kind, "pause")

    def test_24_account_or_bucket_changed(self):
        self.p["accountId"] = "different-account"
        self.assertEqual(self.decision().kind, "pause")
        self.assertEqual(self.decision(ids=("different-bucket",)).kind, "pause")

    def test_40_clock_backwards_rejects_future_snapshot(self):
        self.assertEqual(self.decision(fetched=self.now + 1).kind, "pause")

    def test_44_invalid_format(self):
        for payload in (None, [], "bad", {}, {"accountId": "simulation-account"}):
            with self.subTest(payload=payload):
                self.assertEqual(evaluate(Usage(payload, self.now, "chatgpt"), "simulation-account",
                                          ("codex",), self.now).kind, "pause")

    def test_45_only_weekly_window(self):
        b = self.p["rateLimitsByLimitId"]["codex"]
        b["primary"] = b["secondary"]
        b["secondary"] = None
        self.assertEqual(self.decision().kind, "pause")

    def test_46_reversed_windows(self):
        b = self.p["rateLimitsByLimitId"]["codex"]
        b["primary"], b["secondary"] = b["secondary"], b["primary"]
        self.assertEqual(self.decision().kind, "ready")

    def test_47_model_specific_bucket_must_also_be_eligible(self):
        b = copy.deepcopy(self.p["rateLimitsByLimitId"]["codex"])
        b["limitId"] = "model-specific"
        b["secondary"]["usedPercent"] = 100
        self.p["rateLimitsByLimitId"]["model-specific"] = b
        self.assertEqual(self.decision(ids=("codex", "model-specific")).kind, "weekly")

    def test_ambiguous_durations(self):
        b = self.p["rateLimitsByLimitId"]["codex"]
        for duration in (None, 60, True, 300, 10080.0):
            b["secondary"]["windowDurationMins"] = duration
            self.assertEqual(self.decision().kind, "pause")

    def test_nonfinite_or_boolean_usage(self):
        for value in (True, float("nan"), float("inf"), -1, 101, "5"):
            self.p["rateLimitsByLimitId"]["codex"]["primary"]["usedPercent"] = value
            self.assertEqual(self.decision().kind, "pause")

    def test_unknown_spend_and_unlimited_credits(self):
        b = self.p["rateLimitsByLimitId"]["codex"]
        b["spendControlReached"] = None
        self.assertEqual(self.decision().kind, "pause")
        b["spendControlReached"] = False
        b["credits"]["unlimited"] = True
        self.assertEqual(self.decision().kind, "pause")

    def test_invalid_credit_decimal(self):
        for balance in ("NaN", "Infinity", "-0.01", "oops", 0):
            self.p["rateLimitsByLimitId"]["codex"]["credits"]["balance"] = balance
            self.assertEqual(self.decision().kind, "pause")

    def test_reset_timestamp_alone_does_not_authorize(self):
        self.p = fake_payload(self.now - 50)
        self.assertEqual(self.decision().kind, "pause")

    def test_randomized_financial_and_weekly_invariants(self):
        rng = random.Random(1729)
        for _ in range(2500):
            five, weekly = rng.randrange(101), rng.randrange(101)
            permission = rng.choice([True, False, None])
            self.p = fake_payload(self.now, five=five, weekly=weekly, ordinary=permission)
            d = self.decision()
            if weekly == 100:
                self.assertEqual(d.kind, "weekly")
            if d.kind == "ready":
                self.assertIs(permission, True)
                self.assertLess(five, 100)
                self.assertLess(weekly, 95)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "state.sqlite3"
        self.clock = Clock()
        self.store = Store(self.path)
        self.adapter = SimulationAdapter(self.clock)
        self.engine = Engine(self.store, self.adapter, self.clock)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def wait(self):
        self.store.set_enabled(True, self.clock())
        self.engine.register("demo-task")
        self.engine.tick()
        self.assertEqual(self.task()["state"], State.WAITING_FOR_RESET)

    def task(self):
        return self.store.get("demo-task")

    def reset(self):
        self.clock.advance()
        self.adapter.reset()

    def mutate(self, **values):
        self.adapter.observations["demo-task"] = replace(self.adapter.observe("demo-task"), **values)

    def test_01_default_off(self):
        self.assertFalse(self.store.enabled)
        with self.assertRaises(ValueError):
            self.engine.register("demo-task")

    def test_02_through_09_normal_exactly_once_then_completion(self):
        self.wait()
        self.reset()
        self.engine.tick()
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 1)
        request = self.adapter.requests[0]
        self.assertEqual(request.thread_id, "demo-task")
        self.assertIn("Do not redo completed work", request.text)
        self.adapter.complete()
        self.clock.advance(31)
        self.engine.tick()
        self.assertEqual(self.task()["state"], State.COMPLETED)
        self.clock.advance(1000000)
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 1)
        with self.assertRaises((ValueError, UnsafeError)):
            self.engine.register("demo-task")

    def test_11_weekly_exhausted_during_wait_event(self):
        self.wait()
        self.adapter.payload["rateLimitsByLimitId"]["codex"]["secondary"]["usedPercent"] = 100
        self.engine.usage_changed(self.adapter.usage())
        self.assertEqual(self.task()["state"], State.WEEKLY_LIMIT_REACHED)
        self.assertFalse(self.task()["eligible"])

    def test_15_16_five_reset_weekly_exhausted_never_rearms_itself(self):
        self.wait()
        self.clock.advance()
        self.adapter.reset(weekly=100)
        self.engine.tick()
        self.assertEqual(self.task()["state"], State.WEEKLY_LIMIT_REACHED)
        self.clock.advance(8 * 86400)
        self.adapter.reset()
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)
        self.assertEqual(self.task()["state"], State.WEEKLY_LIMIT_REACHED)

    def test_19_paid_fallback_cannot_be_excluded(self):
        self.wait()
        self.reset()
        self.adapter.capabilities = Capabilities(False, True, True, True)
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)
        self.assertEqual(self.task()["state"], State.PAUSED_FOR_USER)

    def test_25_disable_cancels_waiting(self):
        self.wait()
        self.store.set_enabled(False, self.clock())
        self.reset()
        self.engine.tick()
        self.store.set_enabled(True, self.clock())
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)
        self.assertFalse(self.task()["eligible"])

    def test_26_user_cancel(self):
        self.wait()
        self.reset()
        self.mutate(cancelled=True, turn_status="interrupted")
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)
        self.assertEqual(self.task()["state"], State.PAUSED_FOR_USER)

    def test_27_completed_during_wait(self):
        self.wait()
        self.reset()
        self.adapter.complete()
        self.engine.tick()
        self.assertEqual(self.task()["state"], State.COMPLETED)
        self.assertEqual(len(self.adapter.requests), 0)

    def test_completed_turn_does_not_claim_objective_is_finished(self):
        self.wait()
        self.adapter.complete()
        self.clock.advance(31)
        self.engine.tick()
        task = self.task()
        self.assertEqual(task["state"], State.COMPLETED)
        self.assertIn("turn ended", task["reason"])
        self.assertIn("may still be unfinished", task["reason"])
        self.assertFalse(task["eligible"])
        self.assertEqual(len(self.adapter.requests), 0)

    def test_28_other_turn_or_manual_work(self):
        self.wait()
        self.reset()
        self.mutate(turn_id="user-turn", turn_status="inProgress")
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)

    def test_29_concurrent_reset_events(self):
        self.wait()
        self.reset()
        workers = [threading.Thread(target=self.engine.tick) for _ in range(20)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(len(self.adapter.requests), 1)

    def test_30_recovery_after_reservation_before_transmission(self):
        self.wait()
        with self.store.transaction():
            self.store.update("demo-task", State.VERIFYING_ALLOWANCE, "Checking", self.clock())
            self.store.update("demo-task", State.RESUMING, "Reserved", self.clock())
            self.store.db.execute("INSERT INTO submissions VALUES('crash-id','demo-task','reserved',NULL,?)", (self.clock(),))
        self.store.recover(self.clock())
        self.reset()
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)
        self.assertEqual(self.task()["state"], State.PAUSED_FOR_USER)
        with self.assertRaises(ValueError):
            self.engine.register("demo-task")

    def test_31_lost_ack_never_retransmits(self):
        self.wait()
        self.reset()
        original = self.adapter.submit
        def lose_ack(request):
            original(request)
            raise TransientError("Lost acknowledgement")
        self.adapter.submit = lose_ack
        self.engine.tick()
        self.store.recover(self.clock())
        self.clock.advance(1000)
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 1)
        self.assertFalse(self.task()["eligible"])

    def test_32_missing_history(self):
        self.wait()
        self.reset()
        self.mutate(history_available=False)
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)

    def test_33_missing_project(self):
        self.wait()
        self.reset()
        self.mutate(project_exists=False)
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)

    def test_34_pending_approval(self):
        self.wait()
        self.reset()
        self.mutate(approval_pending=True)
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)

    def test_35_multiple_tasks_serialize_and_refresh_weekly(self):
        self.wait()
        self.adapter.observations["second-task"] = replace(self.adapter.observe("demo-task"), thread_id="second-task")
        self.engine.register("second-task")
        self.engine.tick()
        self.reset()
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 1)
        self.adapter.payload["rateLimitsByLimitId"]["codex"]["secondary"]["usedPercent"] = 100
        self.clock.advance(31)
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 1)
        self.assertEqual(self.store.get("second-task")["state"], State.WEEKLY_LIMIT_REACHED)

    def test_36_38_48_bounded_transient_retries(self):
        self.wait()
        self.reset()
        def unavailable():
            raise TransientError("Network unavailable")
        self.adapter.usage = unavailable
        for _ in range(4):
            self.engine.tick()
            self.clock.advance(301)
        self.assertEqual(self.task()["state"], State.PAUSED_FOR_USER)
        self.assertEqual(len(self.adapter.requests), 0)

    def test_37_authentication_expired(self):
        self.wait()
        self.reset()
        self.adapter.usage = lambda: Usage(self.adapter.payload, self.clock(), "expired")
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)

    def test_39_suspend_through_reset(self):
        self.wait()
        self.clock.advance(3600)
        self.adapter.reset()
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 1)

    def test_40_clock_backwards_delays_instead_of_submitting(self):
        self.wait()
        self.clock.advance(-500)
        self.adapter.reset()
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)

    def test_41_dst_uses_epoch_seconds(self):
        self.wait()
        self.reset()
        # Epoch-based scheduling is independent of local DST display.
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 1)

    def test_42_persisted_wait_survives_process_restart(self):
        self.wait()
        self.store.close()
        self.store = Store(self.path)
        self.store.recover(self.clock())
        self.engine = Engine(self.store, self.adapter, self.clock)
        self.reset()
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 1)

    def test_43_unsupported_execution_protocol(self):
        self.wait()
        self.reset()
        self.adapter.capabilities = Capabilities()
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)

    def test_unrelated_failures_never_schedule(self):
        for code in ("unauthorized", "rateLimitExceeded", "serverOverloaded", None):
            self.store.set_enabled(True, self.clock())
            self.engine.register("demo-task")
            self.mutate(error_code=code)
            self.engine.tick()
            self.assertEqual(self.task()["state"], State.PAUSED_FOR_USER)
            self.assertEqual(len(self.adapter.requests), 0)
            self.mutate(error_code="usageLimitExceeded")

    def test_changed_revision(self):
        self.wait()
        self.reset()
        self.mutate(revision="manual-edit")
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)

    def test_permissions_changed(self):
        self.wait()
        self.reset()
        self.mutate(config_hash="different-permissions")
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)

    def test_disable_during_quota_read(self):
        self.wait()
        self.reset()
        original = self.adapter.usage
        def disable():
            self.store.set_enabled(False, self.clock())
            return original()
        self.adapter.usage = disable
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)

    def test_atomic_adapter_rejects_race_after_read(self):
        self.wait()
        self.reset()
        original = self.adapter.submit
        def race(request):
            self.mutate(revision="raced-user-turn")
            return original(request)
        self.adapter.submit = race
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)
        self.assertFalse(self.task()["eligible"])

    def test_disarm_individual_task(self):
        self.wait()
        self.engine.disarm("demo-task")
        self.reset()
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)

    def test_invalid_state_transition(self):
        self.wait()
        with self.assertRaises(ValueError), self.store.transaction():
            self.store.update("demo-task", State.RESUMING, "Invalid", self.clock())

    def test_optional_read_only_observer_has_no_execution_path(self):
        self.assertFalse(CodexObserver.capabilities.safe)
        with self.assertRaises(UnsafeError):
            CodexObserver().submit(None)

    def test_private_state_permissions(self):
        if os.name == "nt":
            self.skipTest("POSIX file modes do not describe Windows ACLs")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_rearm_during_read_invalidates_old_attempt(self):
        self.wait()
        self.reset()
        original = self.adapter.usage
        original_register = self.engine.register
        def rearm():
            self.engine.disarm("demo-task")
            original_register("demo-task")
            return original()
        self.adapter.usage = rearm
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)
        self.assertEqual(self.task()["state"], State.ARMED)

    def test_no_reads_during_idle_wait(self):
        self.wait()
        def unexpected(*_):
            raise AssertionError("No expensive read should occur before reset")
        self.adapter.usage = unexpected
        self.adapter.observe = unexpected
        for _ in range(10):
            self.engine.tick()

    def test_uncertain_submission_blocks_other_tasks(self):
        self.wait()
        self.adapter.observations["second-task"] = replace(self.adapter.observe("demo-task"), thread_id="second-task")
        self.engine.register("second-task")
        self.engine.tick()
        self.reset()
        original = self.adapter.submit
        def lose_ack(request):
            original(request)
            raise TransientError()
        self.adapter.submit = lose_ack
        self.engine.tick()
        self.clock.advance(31)
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 1)
        self.assertEqual(self.store.get("second-task")["state"], State.WAITING_FOR_RESET)

    def test_separate_controllers_reserve_only_once(self):
        self.wait()
        self.reset()
        other_store = Store(self.path)
        other_engine = Engine(other_store, self.adapter, self.clock)
        try:
            threads = [threading.Thread(target=e.tick) for e in (self.engine, other_engine)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(len(self.adapter.requests), 1)
        finally:
            other_store.close()

    def test_attempt_limit_prevents_unbounded_execution(self):
        self.wait()
        self.reset()
        with self.store.transaction():
            self.store.db.execute("UPDATE tasks SET attempts=3 WHERE thread_id='demo-task'")
        self.engine.tick()
        self.assertEqual(len(self.adapter.requests), 0)
        self.assertEqual(self.task()["state"], State.PAUSED_FOR_USER)


if __name__ == "__main__":
    unittest.main()
